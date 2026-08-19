"""
Resolve a merchant message to an API and — for the real ones — actually call it.

  python seeds/eval/try_action.py "what's the temperature outside" --latitude 28.61 --longitude 77.21
  python seeds/eval/try_action.py "dollar to rupee rate" --from USD --to INR
  python seeds/eval/try_action.py "buy one get one on coffee"

This is a **reference for the orchestrator**, not part of the service. The
service selects; calling is the orchestrator's job, and deliberately not
something the knowledge base does.

What it demonstrates is the whole contract-consuming loop in one file:

  1. resolve the message                        -> api_id, confidence, contract
  2. branch on confidence                       -> act / ask / treat as a question
  3. fill required fields from what is known    -> and prompt for what is missing
  4. build the request from the contract        -> base_url, path, constants, field `in`
  5. call it, for cards marked `status: live`

Cards marked `status: example` are synthetic and are never called — their paths
do not exist. The weather and reference domains are real and will return real
data.
"""

import argparse
import getpass
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

# Several public APIs return 403 to a bare urllib default.
UA = "Mozilla/5.0 (compatible; chotu-orchestrator-demo/1.0)"


def call_json(url, *, method="GET", body=None, headers=None, timeout=30):
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"User-Agent": UA, "Accept": "application/json", **(headers or {})},
        method=method,
    )
    if body is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode()
            return response.status, (json.loads(raw) if raw.strip() else None)
    except urllib.error.HTTPError as error:
        raw = error.read().decode()
        try:
            return error.code, json.loads(raw)
        except Exception:
            return error.code, raw[:400]


def build_request(contract: dict, supplied: dict) -> tuple[str, str, dict | None, list[str]]:
    """
    Turn a contract plus the values we know into an actual HTTP request.

    This is the part an orchestrator has to write once. Everything it needs is
    in the card: where the API lives, which values are fixed, and where each
    collected value belongs in the request.
    """
    method = str(contract.get("method", "GET")).upper()
    base_url = str(contract.get("base_url") or "").rstrip("/")
    path = str(contract.get("path") or "")
    constants = contract.get("constants") or {}
    body_root = contract.get("body_root")
    fields = contract.get("fields") or []

    query: dict = dict(constants) if method == "GET" else {}
    body: dict = {} if method != "GET" else {}
    missing: list[str] = []

    for field in fields:
        if not isinstance(field, dict):
            continue
        name = str(field.get("name") or "")
        if not name:
            continue

        value = supplied.get(name, field.get("default"))
        if value is None:
            if field.get("required"):
                missing.append(name)
            continue

        # Where the value goes. Defaults follow the method, so most cards say
        # nothing and still build correctly.
        location = str(field.get("in") or ("query" if method == "GET" else "body"))
        if location == "path":
            path = path.replace("{%s}" % name, urllib.parse.quote(str(value)))
        elif location == "query":
            query[name] = value
        elif location == "body":
            body[name] = value

    if method != "GET":
        # Constants sit at the top level; collected fields nest under body_root
        # when the API wraps its payload — which is how one endpoint can serve
        # two actions.
        wrapped = {**constants}
        if body_root:
            wrapped[body_root] = body
        else:
            wrapped.update(body)
        body = wrapped

    url = f"{base_url}{path}"
    if query:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(query)

    return method, url, (body if method != "GET" else None), missing


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("message", help="What the merchant said.")
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    parser.add_argument("--kb", default="api-catalog")
    parser.add_argument("--user", default="admin")
    parser.add_argument("--password", default=os.environ.get("CHOTU_PASSWORD"))
    parser.add_argument("--no-call", action="store_true",
                        help="Resolve and build the request, but do not send it.")
    known, extra = parser.parse_known_args()

    # Anything else on the command line stands in for values the orchestrator
    # would have extracted from the conversation.
    supplied: dict = {}
    for i in range(0, len(extra) - 1, 2):
        if extra[i].startswith("--"):
            raw = extra[i + 1]
            try:
                supplied[extra[i][2:]] = json.loads(raw)
            except Exception:
                supplied[extra[i][2:]] = raw

    base = known.base.rstrip("/")
    password = known.password or getpass.getpass(f"Password for {known.user}: ")
    status, login = call_json(f"{base}/api/v1/auth/login", method="POST",
                              body={"username": known.user, "password": password})
    if status != 200:
        sys.exit(f"Sign-in failed: {status} {login}")
    token = login["token"]

    # ── 1. resolve ──
    status, result = call_json(
        f"{base}/api/v1/actions/resolve", method="POST",
        body={"message": known.message, "top_k": 3},
        headers={"Authorization": f"Bearer {token}", "X-Knowledge-Base": known.kb},
        timeout=120,
    )
    if status != 200:
        sys.exit(f"Resolve failed: {status} {result}")

    print(f"\n  message     {known.message!r}")
    print(f"  confidence  {result['confidence']}  —  {result['reason']}")
    print(f"  domains     {', '.join(result['domains_kept'])}"
          + ("  (narrowing gave way)" if result["fallback_used"] else ""))

    if not result["candidates"]:
        sys.exit("\n  Nothing matched.")

    for index, candidate in enumerate(result["candidates"]):
        marker = "->" if index == 0 else "  "
        print(f"  {marker} {candidate['score']:.4f}  {candidate['api_id']:<28} "
              f"{candidate['method']} {candidate['path']}")

    # ── 2. branch on confidence, exactly as an orchestrator would ──
    if result["confidence"] == "low":
        sys.exit("\n  Too weak to act on. Treat this as a question for the "
                 "product knowledge base instead.")
    if result["confidence"] == "ambiguous":
        top, second = result["candidates"][0], result["candidates"][1]
        sys.exit(f"\n  Ambiguous. Ask the merchant: did you mean "
                 f"{top['title']!r} or {second['title']!r}?")

    chosen = result["candidates"][0]
    contract = chosen["contract"]

    # ── 3. fill what we know, prompt for what we do not ──
    method, url, body, missing = build_request(contract, supplied)

    if missing:
        print("\n  Still needed before this can be called:")
        for name in missing:
            field = next((f for f in contract.get("fields", [])
                          if f.get("name") == name), {})
            print(f"    {name:<16} {field.get('prompt', '(no prompt on this card)')}")
        print("\n  Supply them on the command line, e.g. "
              + " ".join(f"--{name} VALUE" for name in missing[:3]))
        return

    if chosen.get("mpin_required"):
        print("\n  This action is MPIN-gated. An orchestrator would ask for the "
              "MPIN here, before sending anything.")

    # ── 4. the request the contract describes ──
    print(f"\n  {method} {url}")
    if body:
        print("  " + json.dumps(body, indent=2, ensure_ascii=False).replace("\n", "\n  "))

    # ── 5. call it, but only when the card says it is real ──
    if contract.get("status") != "live":
        print("\n  Not calling: this card is synthetic seed data and its path "
              "does not exist. Only the weather and reference domains are real.")
        return
    if known.no_call:
        print("\n  Not calling: --no-call.")
        return

    status, response = call_json(url, method=method, body=body)
    print(f"\n  -> {status}")
    print("  " + json.dumps(response, indent=2, ensure_ascii=False)[:1400]
          .replace("\n", "\n  "))


if __name__ == "__main__":
    main()
