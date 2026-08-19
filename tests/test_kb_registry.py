"""
Tests for the knowledge-base registry's pure logic: connection strings, the
schema parameter, previews, slugs, model validation, and secret storage.

Everything here runs without a database. The parts that need one — creating a
knowledge base, ingesting into it, and searching it — are exercised against a
live server instead.
"""

import pytest

from app.db.database import split_schema
from app.services import crypto_service, kb_service
from app.services.kb_service import KbError


# ── Connection strings ───────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "given",
    [
        "postgresql://u:p@h:5432/db",
        "postgres://u:p@h:5432/db",
        "postgresql+asyncpg://u:p@h:5432/db",
    ],
)
def test_every_accepted_spelling_normalises_to_the_async_driver(given):
    assert kb_service.normalise_dsn(given) == "postgresql+asyncpg://u:p@h:5432/db"


def test_surrounding_whitespace_is_forgiven():
    assert kb_service.normalise_dsn("  postgresql://u:p@h/db\n").startswith(
        "postgresql+asyncpg://"
    )


@pytest.mark.parametrize(
    "bad, expected",
    [
        ("", "required"),
        ("   ", "required"),
        ("mysql://root@localhost/app", "Postgres"),
        ("redis://localhost:6379", "Postgres"),
        ("just some text", "Postgres"),
        ("postgresql://u:p@/db", "no host"),
        ("postgresql://u:p@host:5432", "no database name"),
        ("postgresql://u:p@host:5432/", "no database name"),
    ],
)
def test_unusable_connection_strings_are_refused_with_a_reason(bad, expected):
    with pytest.raises(KbError) as error:
        kb_service.normalise_dsn(bad)
    assert expected in str(error.value)


# ── The schema parameter ─────────────────────────────────────────────────────

def test_a_schema_survives_normalisation():
    dsn = kb_service.normalise_dsn("postgresql://u:p@h:5432/db?schema=team_kb")
    assert dsn == "postgresql+asyncpg://u:p@h:5432/db?schema=team_kb"


def test_split_schema_separates_the_url_from_the_schema():
    url, schema = split_schema("postgresql+asyncpg://u:p@h:5432/db?schema=team_kb")
    assert url == "postgresql+asyncpg://u:p@h:5432/db"
    assert schema == "team_kb"


def test_split_schema_leaves_an_ordinary_url_alone():
    assert split_schema("postgresql+asyncpg://u:p@h/db") == (
        "postgresql+asyncpg://u:p@h/db",
        None,
    )


def test_other_query_parameters_are_kept():
    url, schema = split_schema(
        "postgresql+asyncpg://u:p@h/db?schema=team_kb&application_name=chotu"
    )
    assert schema == "team_kb"
    assert "application_name=chotu" in url
    assert "schema=" not in url


@pytest.mark.parametrize(
    "bad", ["Team-KB", "1team", "team kb", "team;drop", "public.evil", "a" * 70]
)
def test_a_schema_name_that_would_need_quoting_is_refused(bad):
    # Schema names reach DDL, so anything that is not a plain identifier is
    # rejected at the door rather than escaped later.
    with pytest.raises(KbError):
        kb_service.normalise_dsn(f"postgresql://u:p@h/db?schema={bad}")


# ── Previews never carry the password ────────────────────────────────────────

def test_the_preview_drops_the_password():
    preview = kb_service.dsn_preview(
        kb_service.normalise_dsn("postgresql://kb_user:hunter2@10.0.0.7:5432/ops")
    )
    assert preview == "kb_user@10.0.0.7:5432/ops"
    assert "hunter2" not in preview


def test_the_preview_names_the_schema():
    preview = kb_service.dsn_preview(
        kb_service.normalise_dsn("postgresql://u:secret@h:5432/db?schema=team_kb")
    )
    assert preview == "u@h:5432/db (schema team_kb)"
    assert "secret" not in preview


def test_the_preview_survives_a_password_with_url_characters():
    preview = kb_service.dsn_preview(
        kb_service.normalise_dsn("postgresql://u:p%40ss%3Aword@h:5432/db")
    )
    assert "p@ss" not in preview and "ss:word" not in preview
    assert preview == "u@h:5432/db"


# ── Slugs ────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "name, slug",
    [
        ("Merchant Ops", "merchant-ops"),
        ("Merchant Ops (v2)", "merchant-ops-v2"),
        ("  Spaces   Everywhere  ", "spaces-everywhere"),
        ("UPPER CASE", "upper-case"),
        ("!!!", "kb"),
        ("", "kb"),
    ],
)
def test_slugs_are_derived_predictably(name, slug):
    assert kb_service.slugify(name) == slug


def test_a_derived_slug_always_satisfies_the_pattern_the_api_enforces():
    for name in ["Merchant Ops", "a" * 200, "café ☕ knowledge", "123"]:
        assert kb_service.SLUG_RE.match(kb_service.slugify(name)), name


# ── Model validation ─────────────────────────────────────────────────────────

def test_a_known_model_at_a_supported_width_is_accepted():
    kb_service.validate_model_choice("gemini", "gemini-embedding-2", 3072)


@pytest.mark.parametrize(
    "provider, model, dimensions, expected",
    [
        ("gemini", "no-such-model", 3072, "not a known embedding model"),
        ("fal", "gemini-embedding-2", 3072, "is a gemini model"),
        ("gemini", "gemini-embedding-2", 999, "not supported"),
        ("gemini", "gemini-embedding-2", 4096, "not supported"),
    ],
)
def test_an_impossible_combination_is_refused(provider, model, dimensions, expected):
    with pytest.raises(KbError) as error:
        kb_service.validate_model_choice(provider, model, dimensions)
    assert expected in str(error.value)


def test_a_provider_without_a_configured_key_is_refused():
    # Keys live in the environment, one per provider. Offering a model whose
    # provider has no key would fail at the first upload instead of at the form.
    with pytest.raises(KbError) as error:
        kb_service.validate_model_choice("fal", "openai/text-embedding-3-large", 3072)
    assert "FAL_KEY" in str(error.value)


def test_every_offered_model_reports_the_widths_it_accepts():
    for option in kb_service.available_models():
        assert option["allowed_dimensions"], option["model"]
        assert option["default_dimensions"] in option["allowed_dimensions"]


# ── Secret storage ───────────────────────────────────────────────────────────

def test_a_connection_string_round_trips_through_encryption():
    secret = "postgresql+asyncpg://u:hunter2@10.0.0.7:5432/ops"
    stored = crypto_service.encrypt(secret)

    assert stored.startswith(crypto_service.PREFIX)
    assert "hunter2" not in stored
    assert crypto_service.decrypt(stored) == secret


def test_encrypting_the_same_value_twice_gives_different_ciphertext():
    # Otherwise two knowledge bases on the same host would be identifiable as
    # such from the table alone.
    secret = "postgresql+asyncpg://u:p@h/db"
    assert crypto_service.encrypt(secret) != crypto_service.encrypt(secret)


def test_a_value_stored_before_encryption_existed_is_still_readable():
    plain = "postgresql+asyncpg://u:p@h/db"
    assert crypto_service.decrypt(plain) == plain


def test_a_value_from_a_different_key_reports_a_configuration_problem(monkeypatch):
    from cryptography.fernet import Fernet

    stored = crypto_service.encrypt("postgresql+asyncpg://u:p@h/db")
    monkeypatch.setattr(
        crypto_service.settings, "secret_key", Fernet.generate_key().decode()
    )

    with pytest.raises(crypto_service.SecretsUnavailable) as error:
        crypto_service.decrypt(stored)
    assert "SECRET_KEY has changed" in str(error.value)


def test_without_a_secret_key_nothing_can_be_stored(monkeypatch):
    monkeypatch.setattr(crypto_service.settings, "secret_key", "")

    assert crypto_service.is_available() is False
    with pytest.raises(crypto_service.SecretsUnavailable) as error:
        crypto_service.encrypt("anything")
    assert "SECRET_KEY is not set" in str(error.value)


def test_a_passphrase_that_is_not_a_fernet_key_still_works(monkeypatch):
    # Someone will type a password in here rather than generating a key. That
    # should work, not fail with a base64 error from three layers down.
    monkeypatch.setattr(crypto_service.settings, "secret_key", "correct horse battery")

    stored = crypto_service.encrypt("postgresql+asyncpg://u:p@h/db")
    assert crypto_service.decrypt(stored) == "postgresql+asyncpg://u:p@h/db"
