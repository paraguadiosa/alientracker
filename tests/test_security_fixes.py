"""Regression tests for the security review fixes."""

import os

import pytest

from beaverhabits.app import crud
from beaverhabits.app.auth import user_create
from beaverhabits.app.db import create_db_and_tables, engine


async def test_get_user_image_returns_stored_row():
    """crud.get_user_image must return the row (previously returned None)."""
    await create_db_and_tables()
    email = f"img-{os.urandom(4).hex()}@test.com"
    user = await user_create(email=email, password="TestPassword123!")

    payload = b"\x89PNG\r\n\x1a\n" + b"fake-png-body"
    saved = await crud.save_user_image(user, payload)
    assert saved.unique_id is not None

    fetched = await crud.get_user_image(saved.unique_id, user)
    assert fetched is not None
    assert fetched.blob == payload

    # Cross-user isolation: another user must not see this image.
    other = await user_create(
        email=f"other-{os.urandom(4).hex()}@test.com", password="x"
    )
    assert await crud.get_user_image(saved.unique_id, other) is None

    await engine.dispose()


def test_insecure_defaults_refuse_to_boot_in_non_dev(monkeypatch):
    """A non-dev deploy using default secrets must fail fast at startup."""
    from beaverhabits.configs import settings
    from beaverhabits.main import app, lifespan

    async def run():
        async with lifespan(app):
            pass

    monkeypatch.setattr(settings, "ENV", "prod")
    monkeypatch.setattr(settings, "JWT_SECRET", "SECRET")
    monkeypatch.setattr(settings, "NICEGUI_STORAGE_SECRET", "dev")
    monkeypatch.setattr(settings, "RESET_PASSWORD_TOKEN_SECRET", "")

    import asyncio

    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        asyncio.run(run())


def test_strong_secrets_boot_in_non_dev(monkeypatch):
    from beaverhabits.configs import settings
    from beaverhabits.main import app, lifespan

    async def run():
        async with lifespan(app):
            pass

    monkeypatch.setattr(settings, "ENV", "prod")
    monkeypatch.setattr(settings, "JWT_SECRET", "x" * 48)
    monkeypatch.setattr(settings, "NICEGUI_STORAGE_SECRET", "y" * 48)
    monkeypatch.setattr(settings, "RESET_PASSWORD_TOKEN_SECRET", "z" * 48)

    import asyncio

    asyncio.run(run())
