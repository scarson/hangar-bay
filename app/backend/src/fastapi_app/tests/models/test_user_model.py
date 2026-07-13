# ABOUTME: Registration + column-shape guards for the SSO User model.
# ABOUTME: BigInteger character_id, nullable token-vault columns, legacy stub columns gone.
from sqlalchemy import BigInteger

from fastapi_app.db import Base
from fastapi_app.models import User


def test_user_registered_with_bigint_character_id():
    assert "users" in Base.metadata.tables
    cols = Base.metadata.tables["users"].columns
    assert isinstance(cols["character_id"].type, BigInteger)
    assert cols["character_id"].unique is True
    assert cols["character_id"].nullable is False


def test_user_has_token_vault_columns_all_nullable():
    cols = Base.metadata.tables["users"].columns
    for name in ("esi_access_token", "esi_refresh_token", "esi_scopes"):
        assert cols[name].nullable is True
    assert cols["character_name"].nullable is False
    assert cols["owner_hash"].nullable is False
    assert cols["owner_hash"].index is True


def test_legacy_user_columns_are_gone():
    cols = Base.metadata.tables["users"].columns
    for legacy in ("username", "email", "hashed_password", "user_type", "is_admin"):
        assert legacy not in cols


def test_user_defaults_instantiate():
    u = User(character_id=91_000_001, character_name="Sesta Hound", owner_hash="abc")
    assert isinstance(u.character_id, int)
    assert u.esi_access_token is None
    # created_at/updated_at are server defaults — they fill at flush, not at construction.
