# Alientracker Security Review (Red Team / Blue Team)

Reviewer: Hermes (red team) vs. the Alientracker codebase (blue team).
Scope: full source tree at the time of review, focused on the
Alientracker-specific ("vibecoded") changes on top of Beaver Habit Tracker.
Method: source review plus working proof-of-concept exploits run against the
app with `uv run`.

Each finding lists: severity, location, how it was exploited, and the fix.

## Executive summary

The app ships with **public default secrets** and a header-based auth path that
trusts the network. A deployment that does not override the defaults can be
fully compromised: an attacker can forge non-expiring JWTs and impersonate any
user whose UUID they learn, and can authenticate as any existing user
(including the admin) by sending a single spoofed HTTP header.

Two clear functional bugs were also found:

- The app does **not start on Python 3.12 or 3.13** (a `SyntaxError` in the API
  router), despite `pyproject.toml` declaring `requires-python >= 3.12`.
- Uploaded note images **can never be displayed** (`crud.get_user_image` has no
  `return` statement).

This PR fixes the critical bugs and adds a fail-fast guard that refuses to
boot a non-`dev` deployment which still uses the insecure defaults. Remaining
items are documented below for follow-up.

## PoC evidence

Two runnable proofs are included in this branch (not committed to `main`):

- `poc_takeover.py` — forges a non-expiring auth JWT with the default
  `JWT_SECRET="SECRET"` and impersonates a user.
- `poc_header.py` — authenticates as the admin using only a spoofed
  `X-Remote-Email` header.

Both reproduce `[OK]` against the running app.

---

## Findings

### CRIT-1. Insecure default secrets allow JWT / session forgery

**Severity: Critical**
**Location:** `beaverhabits/configs.py`

```python
NICEGUI_STORAGE_SECRET: str = "dev"
JWT_SECRET: str = "SECRET"
RESET_PASSWORD_TOKEN_SECRET: str = ""
JWT_LIFETIME_SECONDS: int = 0
```

`JWT_SECRET` is the HMAC key for every access token. `NICEGUI_STORAGE_SECRET`
signs the browser session that carries the `auth_token`. Both defaults are part
of the public source tree, so any deployment that does not override them lets an
attacker forge valid tokens.

`JWT_LIFETIME_SECONDS = 0` makes `fastapi_users` omit the `exp` claim
(`generate_jwt` only adds `exp` when `lifetime_seconds` is truthy), so forged
tokens **never expire**.

`RESET_PASSWORD_TOKEN_SECRET = ""` is empty by default. The GUI forgot-password
flow (`views.forgot_password` -> `user_create_reset_token`) asserts it is
non-empty and raises `AssertionError`, so the feature is broken out of the box.

**Exploit (run):** `uv run python poc_takeover.py`

1. Victim registers. The `/auth/register` response is `UserRead`, which
   includes the victim `id` (UUID). The same UUID is also written to the logs
   on registration (`User has registered: victim@example.com(<uuid>)`) and is
   shipped to Sentry when `SENTRY_DSN` is set (`send_default_pii=True`).
2. Attacker forges a JWT with `{"sub": victim_uuid, "aud":
   "fastapi-users:auth"}` signed with `"SECRET"`. No `exp` is added.
3. `GET /users/me` and `GET /api/v1/habits` succeed as the victim.

```
victim uuid (leaked at registration): 96634fed-...
forged token payload: {'sub': '96634fed-...', 'aud': 'fastapi-users:auth'}
GET /users/me -> 200 victim@example.com
[OK] forged a non-expiring token and impersonated the victim
```

The fastapi-users **reset-password** router is not directly forgeable: its
tokens carry a `password_fgpt` claim bound to the current password hash, so a
forged reset token is rejected. The auth JWT has no such protection.

**Fix (this PR):** added a startup guard in `beaverhabits/main.py` that raises
`RuntimeError` and refuses to boot when `ENV != "dev"` and any of
`JWT_SECRET == "SECRET"`, `NICEGUI_STORAGE_SECRET == "dev"`, or
`RESET_PASSWORD_TOKEN_SECRET == ""` is still in use.

**Recommended follow-up:** generate strong random secrets at deploy time, set
a non-zero `JWT_LIFETIME_SECONDS` (e.g. `86400`), and stop logging user UUIDs.

### CRIT-2. Trusted email header spoofing = authentication bypass

**Severity: Critical (when `TRUSTED_EMAIL_HEADER` is set)**
**Location:** `beaverhabits/app/dependencies.py` -> `get_trusted_header_email`

```python
def get_trusted_header_email(request: Request) -> Optional[str]:
    if not settings.TRUSTED_EMAIL_HEADER:
        return None
    return request.headers.get(settings.TRUSTED_EMAIL_HEADER)
```

When an operator sets `TRUSTED_EMAIL_HEADER` (e.g. behind an auth proxy), the
app trusts that header unconditionally. There is no check that the request came
from a trusted proxy. If the app is reachable on a path that does not strip the
header, any caller can authenticate as any existing user by setting the header
themselves.

**Exploit (run):**

```
TRUSTED_EMAIL_HEADER=X-Remote-Email uv run python poc_header.py
GET /api/v1/habits/export with spoofed header -> 200 {"habits":[]}
[OK] authenticated as admin with only a spoofed header
```

**Fix (recommended, not in this PR):**

- Document that `TRUSTED_EMAIL_HEADER` requires a reverse proxy that strips the
  header from client traffic.
- Optionally only honour the header when `request.client.host` is in an
  allowlist of proxy IPs.

### CRIT-3. App does not start on Python 3.12 / 3.13

**Severity: Critical (portability)**
**Location:** `beaverhabits/routes/api.py`

```python
except ValueError, KeyError:   # SyntaxError before Python 3.14
    pass
```

`except A, B:` without parentheses is a `SyntaxError` on Python 3.13 and
earlier. `pyproject.toml` declares `requires-python = ">=3.12"`, so the whole
`routes/api.py` module fails to import on 3.12/3.13, which prevents the app
from starting. Verified:

```
3.13: SyntaxError -> multiple exception types must be parenthesized
```

**Fix (this PR):** changed to `except (ValueError, KeyError):`.

### HIGH-1. `TRUSTED_LOCAL_EMAIL` auto-provisions users

**Severity: High (when set)**
**Location:** `beaverhabits/app/dependencies.py` -> `current_active_user`

When `TRUSTED_LOCAL_EMAIL` is set, the app auto-creates a user for that email
on the first unauthenticated request and authenticates as them. If this is set
in an environment that is reachable beyond localhost, anyone is logged in as
that user (potentially the admin if the email matches `ADMIN_EMAIL`).

**Fix (recommended):** restrict this path to loopback clients, or remove it in
favour of `TRUSTED_EMAIL_HEADER` behind a proxy.

### MED-1. API tokens stored in plaintext

**Severity: Medium**
**Location:** `beaverhabits/app/db.py` (`UserApiTokenModel.token`),
`beaverhabits/app/crud.py`

Permanent API tokens are stored as plaintext in the database and looked up by
exact match. A database leak (backup, dump, read-only SQL injection elsewhere)
makes every token immediately usable. Tokens never expire.

**Fix (recommended):** store only `sha256(token)`; return the raw token once at
creation time and never display it again. This is a behaviour change for the
tokens page, so it is left for a follow-up.

### MED-2. Sensitive tokens written to logs

**Severity: Medium**
**Location:** `beaverhabits/views.py`

`forgot_password` previously logged the full reset token at debug level. Reset
tokens are short-lived but enough to take over an account within their
lifetime.

**Fix (this PR):** the token is no longer logged; only the email is.

`login_user` logs only the first four characters of the access token, which is
acceptable. The registration log still prints the user UUID (see CRIT-1) and
should be redacted in production.

### LOW-1. Custom CSS is rendered into a `<style>` block

**Severity: Low (self-only)**
**Location:** `beaverhabits/views.py` -> `sanitize_css` / `apply_theme_style`

User-supplied CSS is stripped of HTML tags with `re.sub(r"<[^>]*>", "", css)`
and injected into `<style>{css}</style>`. The tag strip is effective against a
`</style>` breakout, so this is not cross-user XSS. However CSS itself can make
outbound requests (`@import url(...)`, `background-image: url(...)`). Since the
CSS only renders for the user who set it, the impact is limited to self-induced
data exfiltration.

**Fix (recommended):** add a Content-Security-Policy that blocks
`style-src 'unsafe-inline'` external loads, or disable custom CSS in
multi-tenant deployments.

### LOW-2. Note image upload has no size / type validation

**Severity: Low**
**Location:** `beaverhabits/routes/routes.py` -> `upload_note_image`

`POST /assets` accepts arbitrary bytes with no maximum size and no
content-type check, storing them as a blob. A user can abuse this as private
storage and cause memory pressure with large uploads.

**Fix (recommended):** enforce a max size and validate the `image/*` type.

### LOW-3. WebSocket token passed as a query parameter

**Severity: Low**
**Location:** `beaverhabits/routes/api.py` -> `sync_ws`

`/api/v1/sync/ws?token=...` authenticates via the URL query string. Query
strings are commonly logged by proxies and may appear in server access logs.

**Fix (recommended):** use the `Sec-WebSocket-Protocol` subprotocol or a
short-lived ticket.

---

## Code-review notes (non-security)

- `crud.get_user_image` had **no `return` statement** and always returned
  `None`, so `GET /assets/{image_id}` always returned `404` even for images
  that had just been uploaded. The same file had a dead `return user_image`
  after `return None` in `get_user_by_api_token`. Both fixed in this PR; a
  regression test was added.
- `current_admin_user` returns `401 Unauthorized` for non-admins. `403
  Forbidden` is more correct and avoids confusing auth tooling.
- The HTTP `AuthMiddleware` redirects **every** `401` to `/login`, including
  API responses. API clients expect a `401` JSON body, not a `302` to an HTML
  login page. Consider exempting `/api/`.
- Branding leftovers: `PAGE_TITLE` is still `"Beaver Habit Tracker"`,
  `custom_headers()` hardcodes `https://beaverhabits.com` in meta/OG/Twitter
  tags and JSON-LD, and the manifest is named "Beaver". For an
  "Alientracker"-themed app these should be configurable.
- `main.Digest` is a middleware function named with a capital letter; rename to
  `request_digest` for readability.
- Broad `except Exception:` blocks in `app/auth.py` swallow and hide errors;
  prefer specific exceptions.
- `ratelimiter` keys on `f"{args}_{kwargs}"`, which is trivially bypassable by
  varying arguments and is bounded to a single process. Move to a per-identity
  store (e.g. the user email / IP) backed by Redis for multi-worker correctness.

## Fixes included in this PR

| File | Change |
|------|--------|
| `beaverhabits/routes/api.py` | `except (ValueError, KeyError):` (CRIT-3) |
| `beaverhabits/app/crud.py` | `get_user_image` now returns the row; removed dead code |
| `beaverhabits/main.py` | fail-fast guard for insecure default secrets (CRIT-1) |
| `beaverhabits/views.py` | stop logging the reset token (MED-2) |
| `tests/test_security_fixes.py` | regression tests for the above |

Test suite: `83 passed`.
