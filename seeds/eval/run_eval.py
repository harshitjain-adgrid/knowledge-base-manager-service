"""
Measures retrieval quality against the evaluation sets.

  python seeds/eval/run_eval.py --base http://127.0.0.1:8000
  python seeds/eval/run_eval.py --only action --sweep

Two things are measured, and they fail for different reasons, so they are
reported separately:

  product  — does the right document reach the assistant's context?
  action   — does the catalogue retrieve the right API for a merchant message,
             and does a non-instruction correctly fail to reach the bar?

Both go through /search. The knowledge base retrieves; the collapsing and
ranking that turn chunk hits into one API live in selection.py, beside this
script, because deciding what to do with a retrieval is the orchestrator's job
and not the service's.

Results are broken down by tier. An overall number hides the only failures that
matter: a wrong action taken confidently, or a question mistaken for a command.
"""

import argparse
import getpass
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.request

import yaml

import selection

HERE = pathlib.Path(__file__).parent
TIERS = ["easy", "medium", "confusable", "negative"]


# ── transport ────────────────────────────────────────────────────────────────

def sign_in(base, username, password):
    request = urllib.request.Request(
        f"{base}/api/v1/auth/login",
        data=json.dumps({"username": username, "password": password}).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode())["token"]
    except urllib.error.HTTPError as error:
        sys.exit(f"Sign-in failed: {error.code} {error.read().decode()[:200]}")


def post(base, token, path, body, kb):
    request = urllib.request.Request(
        f"{base}{path}", data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json",
                 "X-Knowledge-Base": kb},
        method="POST")
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as error:
        return {"__error__": f"{error.code} {error.read().decode()[:200]}"}


# ── reporting ────────────────────────────────────────────────────────────────

class Tally:
    def __init__(self):
        self.rows = []

    def add(self, tier, passed, detail):
        self.rows.append((tier, passed, detail))

    def report(self, title, show_failures=True):
        print(f"\n{'=' * 74}\n{title}\n{'=' * 74}")
        overall_pass = sum(1 for _, ok, _ in self.rows if ok)

        for tier in TIERS:
            rows = [r for r in self.rows if r[0] == tier]
            if not rows:
                continue
            passed = sum(1 for _, ok, _ in rows if ok)
            bar = "█" * round(20 * passed / len(rows))
            print(f"  {tier:<12} {passed:>3}/{len(rows):<3} "
                  f"{100 * passed / len(rows):>5.1f}%  {bar}")

        print(f"  {'overall':<12} {overall_pass:>3}/{len(self.rows):<3} "
              f"{100 * overall_pass / len(self.rows):>5.1f}%")

        if show_failures:
            failures = [(t, d) for t, ok, d in self.rows if not ok]
            if failures:
                print(f"\n  {len(failures)} failing:")
                for tier, detail in failures:
                    print(f"    [{tier}] {detail}")

        return overall_pass, len(self.rows)


# ── action selection ─────────────────────────────────────────────────────────

def resolve(base, token, kb, message, top_k, overrides=None):
    """Retrieve from the knowledge base, then decide locally."""
    result = post(base, token, "/api/v1/search",
                  {"query": message, "top_k": selection.DEFAULT_POOL_SIZE}, kb)
    if "__error__" in result:
        return None, result["__error__"], 0.0

    decision = selection.decide(result["results"], top_k=top_k, **(overrides or {}))
    return decision, None, result["embed_ms"] + result["search_ms"]


def eval_actions(base, token, kb, top_k, overrides=None, quiet=False):
    cases = yaml.safe_load((HERE / "action_queries.yaml").read_text(encoding="utf-8"))["queries"]
    tally = Tally()
    latencies = []

    for case in cases:
        decision, error, elapsed = resolve(base, token, kb, case["q"], top_k, overrides)
        if error:
            tally.add(case["tier"], False, f"{case['q']!r} -> {error}")
            continue

        latencies.append(elapsed)
        top = decision.candidates[0].api_id if decision.candidates else None
        confidence = decision.confidence
        expected = case.get("expect")

        if expected is None:
            # A question, not an instruction. Passing means NOT reaching the bar.
            passed = confidence != "high"
            detail = (f"{case['q']!r} -> would act on {top} "
                      f"({decision.top_score:.3f}, {confidence})")
        else:
            passed = top == expected and confidence == "high"
            if top == expected and confidence != "high":
                detail = (f"{case['q']!r} -> right API ({expected}) but "
                          f"{confidence}: {decision.reason}")
            else:
                detail = (f"{case['q']!r} -> {top} @{decision.top_score:.3f}, "
                          f"wanted {expected}")
            if case.get("not_expect") and top == case["not_expect"]:
                detail += "  [picked the sibling it was warned about]"

        tally.add(case["tier"], passed, detail)

    passed, total = tally.report("ACTION SELECTION", show_failures=not quiet)
    if latencies and not quiet:
        print(f"\n  retrieval latency: {sum(latencies) / len(latencies):.0f}ms mean, "
              f"{max(latencies):.0f}ms worst")
    return passed, total


# ── product knowledge ────────────────────────────────────────────────────────

def eval_product(base, token, kb, top_k, min_score):
    cases = yaml.safe_load((HERE / "product_queries.yaml").read_text(encoding="utf-8"))["queries"]
    tally = Tally()

    for case in cases:
        result = post(base, token, "/api/v1/search",
                      {"query": case["q"], "top_k": top_k}, kb)
        if "__error__" in result:
            tally.add(case["tier"], False, f"{case['q']!r} -> {result['__error__']}")
            continue

        hits = result["results"]
        titles = [h["document_title"] for h in hits]
        best = hits[0]["similarity"] if hits else 0.0
        expected = case.get("expect")

        if expected is None:
            # Nothing covers it. Passing means the best match is weak enough
            # that the assistant will say so instead of answering from noise.
            passed = best < min_score
            detail = (f"{case['q']!r} -> {titles[0] if titles else 'nothing'} "
                      f"@{best:.3f}, above the {min_score} floor")
        else:
            passed = expected in titles
            rank = titles.index(expected) + 1 if passed else None
            detail = (f"{case['q']!r} -> wanted {expected!r}, got "
                      f"{titles[:3]}")
            if passed and rank and rank > 1:
                detail = f"{case['q']!r} -> {expected!r} at rank {rank}"

            # A confusable case names the neighbour it is easily mistaken for.
            # Retrieving both is fine; retrieving the neighbour *first* is not,
            # because the assistant answers from what it reads first.
            rival = case.get("not_expect")
            if rival and rival in titles:
                rival_rank = titles.index(rival) + 1
                if rank is None or rival_rank < rank:
                    passed = False
                    detail = (f"{case['q']!r} -> {rival!r} at rank {rival_rank} "
                              f"beat {expected!r} at rank {rank}")

        tally.add(case["tier"], passed, detail)

    return tally.report(f"PRODUCT KNOWLEDGE  (recall@{top_k})")


# ── threshold sweep ──────────────────────────────────────────────────────────

def sweep(base, token, kb, top_k):
    """
    Try combinations of the two thresholds that decide act / ask / decline.

    The point is not to find the highest number. It is to find a setting where
    the negative tier stays near perfect — because taking a wrong action is a
    much more expensive mistake than failing to take a right one.
    """
    print("\n" + "=" * 74)
    print("THRESHOLD SWEEP")
    print("=" * 74)
    print(f"  {'min_score':>9} {'margin':>7} | {'easy':>6} {'medium':>7} "
          f"{'confus':>7} {'negativ':>8} | {'overall':>8}")
    print("  " + "-" * 70)

    cases = yaml.safe_load((HERE / "action_queries.yaml").read_text(encoding="utf-8"))["queries"]

    # Resolve once per query at permissive thresholds, then re-apply the
    # decision rules offline. One embedding call per query instead of one per
    # query per combination — the sweep is a scoring exercise, not a retrieval
    # one, and the retrieval does not change.
    resolved = []
    for case in cases:
        decision, error, _ = resolve(base, token, kb, case["q"], top_k,
                                     {"min_score": 0.0, "decision_margin": 0.0})
        resolved.append((case, decision if not error else None))

    best = None
    for min_score in (0.50, 0.55, 0.60, 0.62, 0.65, 0.68, 0.70, 0.75):
        for margin in (0.00, 0.01, 0.02, 0.03, 0.04, 0.06):
            per_tier = {tier: [0, 0] for tier in TIERS}

            for case, decision in resolved:
                if decision is None or not decision.candidates:
                    per_tier[case["tier"]][1] += 1
                    continue
                candidates = decision.candidates
                top_score = candidates[0].score
                gap = (candidates[0].score - candidates[1].score
                       if len(candidates) > 1 else 1.0)

                if top_score < min_score:
                    confidence = "low"
                elif gap < margin:
                    confidence = "ambiguous"
                else:
                    confidence = "high"

                expected = case.get("expect")
                if expected is None:
                    ok = confidence != "high"
                else:
                    ok = candidates[0].api_id == expected and confidence == "high"

                per_tier[case["tier"]][1] += 1
                per_tier[case["tier"]][0] += 1 if ok else 0

            cells = []
            total_pass = total = 0
            for tier in TIERS:
                passed, count = per_tier[tier]
                total_pass += passed
                total += count
                cells.append(f"{(100 * passed / count if count else 0):>6.0f}%")

            overall = 100 * total_pass / total if total else 0
            negative_rate = (100 * per_tier["negative"][0] / per_tier["negative"][1]
                             if per_tier["negative"][1] else 0)
            # Ranked on overall accuracy, with the negative rate as the tiebreak.
            # Deliberately not negatives-first: no threshold separates a question
            # from an instruction — "explain how settlements work" and "show me
            # my settlements" score alike — so demanding a clean negative tier
            # only picks the setting that refuses almost everything.
            key = (overall, negative_rate)
            if best is None or key > best[0]:
                best = (key, min_score, margin, overall)

            print(f"  {min_score:>9.2f} {margin:>7.2f} | " + " ".join(cells)
                  + f" | {overall:>7.1f}%")

    if best:
        print(f"\n  best overall: min_score={best[1]}, "
              f"decision_margin={best[2]} ({best[3]:.1f}%)")
        print("  note: the negative tier is bounded by what a similarity score can")
        print("        express. Separating a question from an instruction is the")
        print("        orchestrator's intent step, upstream of this call.")


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    parser.add_argument("--user", default="admin")
    parser.add_argument("--password", default=os.environ.get("CHOTU_PASSWORD"))
    parser.add_argument("--product-kb", default="product-knowledge")
    parser.add_argument("--api-kb", default="api-catalog")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--product-floor", type=float, default=0.70,
                        help="Below this a product answer is treated as 'I don't know'.")
    parser.add_argument("--only", choices=["product", "action"])
    parser.add_argument("--sweep", action="store_true",
                        help="Try threshold combinations instead of scoring one.")
    args = parser.parse_args()

    base = args.base.rstrip("/")
    password = args.password or getpass.getpass(f"Password for {args.user}: ")
    token = sign_in(base, args.user, password)

    started = time.time()

    if args.sweep:
        sweep(base, token, args.api_kb, args.top_k)
        return

    results = []
    if args.only != "action":
        results.append(eval_product(base, token, args.product_kb,
                                    args.top_k, args.product_floor))
    if args.only != "product":
        results.append(eval_actions(base, token, args.api_kb, args.top_k))

    passed = sum(p for p, _ in results)
    total = sum(t for _, t in results)
    print(f"\n{'=' * 74}\n{passed}/{total} checks passed "
          f"({100 * passed / total:.1f}%) in {time.time() - started:.0f}s")
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
