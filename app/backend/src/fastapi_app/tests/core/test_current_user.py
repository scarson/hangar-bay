# ABOUTME: get_current_user resolves session->users row and forces re-login on miss/mismatch (design §4.1).
# ABOUTME: Direct-call unit tests; HTTP-level coverage (401 anon, cross-user) lands in Phase 2's CRUD suite.
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from fastapi_app.core import session as sess
from fastapi_app.core.config import settings
from fastapi_app.core.current_user import get_current_user
from fastapi_app.models import User
from fastapi_app.tests.fake_redis import FakeRedis

pytestmark = pytest.mark.asyncio


def _request_with_sid(sid):
    return SimpleNamespace(cookies={settings.SESSION_COOKIE_NAME: sid})


async def _mint(redis, *, user_id, character_id):
    sid = await sess.create_session(
        redis, user_id=user_id, character_id=character_id, character_name="Sesta Hound"
    )
    payload = await sess.read_session(redis, sid)
    return sid, payload


async def test_happy_path_returns_user_and_keeps_session(db_session):
    redis = FakeRedis()
    user = User(character_id=91000001, character_name="Sesta Hound", owner_hash="OWN1")
    db_session.add(user)
    await db_session.flush()
    sid, payload = await _mint(redis, user_id=user.id, character_id=user.character_id)
    result = await get_current_user(
        request=_request_with_sid(sid), session=payload, db=db_session, redis=redis
    )
    assert result.id == user.id
    assert await redis.exists(f"session:{sid}") == 1  # session preserved


async def test_missing_row_401_and_session_deleted(db_session):
    redis = FakeRedis()
    # No users row for user_id=987654 (e.g. session survived a dev DB wipe).
    sid, payload = await _mint(redis, user_id=987654, character_id=91000001)
    with pytest.raises(HTTPException) as exc:
        await get_current_user(
            request=_request_with_sid(sid), session=payload, db=db_session, redis=redis
        )
    assert exc.value.status_code == 401
    assert await redis.exists(f"session:{sid}") == 0  # forced re-login


async def test_wrong_character_id_401_and_session_deleted(db_session):
    redis = FakeRedis()
    user = User(character_id=91000001, character_name="Sesta Hound", owner_hash="OWN1")
    db_session.add(user)
    await db_session.flush()
    # Session points at the right users.id but a DIFFERENT character_id (reassigned-id hazard).
    sid, payload = await _mint(redis, user_id=user.id, character_id=91000999)
    with pytest.raises(HTTPException) as exc:
        await get_current_user(
            request=_request_with_sid(sid), session=payload, db=db_session, redis=redis
        )
    assert exc.value.status_code == 401
    assert await redis.exists(f"session:{sid}") == 0
