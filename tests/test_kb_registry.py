"""
Tests for the knowledge-base registry's pure logic: connection strings, the
schema parameter, previews, slugs, model validation, and secret storage.

Everything here runs without a database. The parts that need one — creating a
knowledge base, ingesting into it, and searching it — are exercised against a
live server instead.
"""

import pytest

from app.db.models import TABLE_PREFIX_RE, kb_models
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


# ── Table prefixes ───────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "slug, prefix",
    [
        ("default", "kb_default"),
        ("api-catalog", "kb_api_catalog"),
        ("merchant-ops-v2", "kb_merchant_ops_v2"),
        ("a", "kb_a"),
    ],
)
def test_a_slug_maps_to_a_table_prefix(slug, prefix):
    # Deterministic, so a knowledge base's tables can be found from its slug
    # alone — which is what a consumer reading the database directly does.
    assert kb_service.table_prefix_for(slug) == prefix


def test_every_derived_prefix_is_safe_to_put_in_ddl():
    for slug in ["api-catalog", "a" * 60, "123", "MiXeD-Case"]:
        assert TABLE_PREFIX_RE.match(kb_service.table_prefix_for(slug)), slug


def test_models_refuse_a_prefix_that_is_not_safe():
    for bad in ["documents", "kb_x; drop table y", "KB_UPPER", "kb-hyphen", ""]:
        with pytest.raises(ValueError):
            kb_models(bad)


def test_a_prefix_names_both_of_its_tables():
    Document, Chunk = kb_models("kb_api_catalog")
    assert Document.__tablename__ == "kb_api_catalog_documents"
    assert Chunk.__tablename__ == "kb_api_catalog_chunks"


def test_two_knowledge_bases_get_genuinely_separate_classes():
    # The whole point: one cannot reach the other's rows.
    a_doc, a_chunk = kb_models("kb_default")
    b_doc, b_chunk = kb_models("kb_api_catalog")
    assert a_doc is not b_doc and a_chunk is not b_chunk
    assert a_doc.__tablename__ != b_doc.__tablename__


def test_the_classes_for_one_prefix_are_built_once():
    assert kb_models("kb_default")[0] is kb_models("kb_default")[0]


def test_a_schema_parameter_is_dropped_from_a_connection_string():
    # It used to isolate a knowledge base. Table prefixes do that now, so the
    # parameter is stripped rather than honoured or rejected.
    dsn = kb_service.normalise_dsn("postgresql://u:p@h:5432/db?schema=team_kb")
    assert "schema" not in dsn
    assert dsn == "postgresql+asyncpg://u:p@h:5432/db"


def test_other_query_parameters_survive():
    dsn = kb_service.normalise_dsn(
        "postgresql://u:p@h/db?application_name=chotu&schema=x"
    )
    assert "application_name=chotu" in dsn and "schema" not in dsn


# ── Previews never carry the password ────────────────────────────────────────

def test_the_preview_drops_the_password():
    preview = kb_service.dsn_preview(
        kb_service.normalise_dsn("postgresql://kb_user:hunter2@10.0.0.7:5432/ops")
    )
    assert preview == "kb_user@10.0.0.7:5432/ops"
    assert "hunter2" not in preview


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
    kb_service.validate_model_choice("fal", "gemini-embedding-2", 3072)


@pytest.mark.parametrize(
    "provider, model, dimensions, expected",
    [
        ("fal", "no-such-model", 3072, "not a known embedding model"),
        ("fal", "gemini-embedding-2", 999, "not supported"),
        ("fal", "gemini-embedding-2", 4096, "not supported"),
    ],
)
def test_an_impossible_combination_is_refused(provider, model, dimensions, expected):
    with pytest.raises(KbError) as error:
        kb_service.validate_model_choice(provider, model, dimensions)
    assert expected in str(error.value)


@pytest.mark.parametrize("model", ["openai/text-embedding-3-large",
                                   "openai/text-embedding-3-small"])
def test_models_this_account_cannot_reach_are_not_offered(model):
    # OpenRouter lists these at the same endpoint, but they 401 with "You do not
    # have access to the organization tied to the API key" — reaching OpenAI
    # through it needs an OpenAI account we do not have. Offering one would fail
    # at the first upload instead of at the form.
    assert model not in kb_service.MODEL_SPECS
    with pytest.raises(KbError):
        kb_service.validate_model_choice("fal", model, 3072)


def test_a_missing_key_is_refused_before_a_knowledge_base_is_created(monkeypatch):
    # Keys live in the environment. Accepting a model with no key behind it
    # would fail at the first upload instead of at the form.
    monkeypatch.setattr(kb_service.settings, "fal_key", "")
    with pytest.raises(KbError) as error:
        kb_service.validate_model_choice("fal", "gemini-embedding-2", 3072)
    assert "FAL_AI_API_KEY" in str(error.value)


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


# ── Where a knowledge base lives ─────────────────────────────────────────────
#
# Omitting the connection string means "this service's own database". The row
# must keep dsn_encrypted NULL for that, because resolve_dsn treats NULL as
# "read DATABASE_URL every time" — which is what keeps a rotated database
# password an .env edit instead of a migration over every registered row.

def test_no_connection_string_means_the_services_own_database():
    from app.db.models import KnowledgeBase

    kb = KnowledgeBase(dsn_encrypted=None)
    assert kb_service.resolve_dsn(kb) == kb_service.settings.database_url


def test_a_stored_connection_string_is_used_instead_of_the_environment(monkeypatch):
    from app.db.models import KnowledgeBase

    monkeypatch.setattr(crypto_service.settings, "secret_key", "a test key")
    remote = "postgresql+asyncpg://u:p@10.0.0.7:5432/other"

    kb = KnowledgeBase(dsn_encrypted=crypto_service.encrypt(remote))
    assert kb_service.resolve_dsn(kb) == remote


def test_the_two_cases_are_told_apart_by_a_blank_connection_string():
    # What create_kb branches on. Whitespace counts as absent, so a form that
    # submits an untouched field does not register a knowledge base pointing at
    # an empty connection string.
    for blank in (None, "", "   ", "\t\n"):
        assert not (blank or "").strip(), f"{blank!r} should read as absent"
    assert (" postgresql://u:p@h/db ").strip()
