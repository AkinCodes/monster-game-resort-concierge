# Monster Resort Concierge - API Key Management System

**Document ID:** MR-APIKEY-001
**Owner:** Monster Resort Engineering
**Status:** FINAL
**Classification:** Internal - Engineering
**Last Updated:** 2026-02-13

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Why This Feature Exists](#2-why-this-feature-exists)
3. [Architecture Overview](#3-architecture-overview)
   - 3.1 [Where It Fits in the Codebase](#31-where-it-fits-in-the-codebase)
   - 3.2 [Data Flow Diagram](#32-data-flow-diagram)
   - 3.3 [Database Schema](#33-database-schema)
4. [Component Deep Dive](#4-component-deep-dive)
   - 4.1 [APIKeyManager (app/security.py)](#41-apikeymanager-appsecuritypy)
   - 4.2 [Admin Routes (app/admin_routes.py)](#42-admin-routes-appadmin_routespy)
   - 4.3 [Auth Mixin Integration (app/auth_mixins.py)](#43-auth-mixin-integration-appauth_mixinspy)
   - 4.4 [App Wiring (app/main.py)](#44-app-wiring-appmainpy)
5. [API Reference](#5-api-reference)
   - 5.1 [POST /admin/api-keys](#51-post-adminapi-keys)
   - 5.2 [GET /admin/api-keys](#52-get-adminapi-keys)
   - 5.3 [DELETE /admin/api-keys/{key_id}](#53-delete-adminapi-keyskey_id)
   - 5.4 [GET /admin/api-keys/usage](#54-get-adminapi-keysusage)
6. [Security Design Decisions](#6-security-design-decisions)
7. [Testing Guide](#7-testing-guide)
   - 7.1 [Running the Test Suite](#71-running-the-test-suite)
   - 7.2 [Unit Tests Explained](#72-unit-tests-explained)
   - 7.3 [Integration Tests Explained](#73-integration-tests-explained)
   - 7.4 [Manual End-to-End Testing](#74-manual-end-to-end-testing)
8. [User Impact & Use Cases](#8-user-impact--use-cases)
9. [Configuration & Environment](#9-configuration--environment)
10. [Troubleshooting](#10-troubleshooting)
11. [Security Fixes Included](#11-security-fixes-included)
12. [Future Enhancements](#12-future-enhancements)

---

## 1. Executive Summary

The API Key Management System transforms the `APIKeyManager` class from dead code into a fully wired, production-grade feature. It enables administrators to **create**, **list**, **revoke**, and **audit** managed API keys through dedicated REST endpoints, with full integration into the existing authentication flow.

### What Changed (Summary)

| File | Change | Lines Affected |
|------|--------|----------------|
| `app/security.py` | Added `list_keys`, `revoke_key`, `get_usage` methods; removed dead code | +70, -60 |
| `app/admin_routes.py` | **New file** - Admin router with 4 CRUD endpoints | +96 |
| `app/main.py` | Initialised `APIKeyManager`, mounted admin router | +4 |
| `app/auth_mixins.py` | Rewrote `jwt_or_api_key` with managed key support + security fixes | Rewritten |
| `tests/test_api_key_manager.py` | **New file** - 16 tests (unit + integration) | +210 |
| `tests/conftest.py` | Added new tables to cleanup list | +1 |

### Key Capabilities Delivered

- **Key Creation** with `mr_` prefix, SHA-256 hashing, configurable expiry (1-365 days)
- **Key Verification** during auth flow with automatic `last_used_at` tracking
- **Key Revocation** via admin endpoint (soft-delete pattern)
- **Audit Logging** of every managed-key authentication attempt (success and failure)
- **Security Hardening** - removed hardcoded backdoor, fixed JWT verification bug

---

## 2. Why This Feature Exists

### The Problem

Before this implementation, the Monster Resort Concierge had only **one authentication mechanism for API clients**: a single static API key stored in `MRC_API_KEY`. This created several problems:

| Problem | Impact |
|---------|--------|
| **No key rotation** | If the key leaked, every integration broke during rotation |
| **No per-user attribution** | All API consumers looked identical in logs |
| **No expiry** | Keys lived forever once issued |
| **No audit trail** | No visibility into who called what, when |
| **No revocation** | Compromised keys could not be individually disabled |
| **Dead code** | `APIKeyManager` existed but was never instantiated |

### The Solution

Managed API keys solve all of the above:

- **Per-user keys** - each integration partner or service gets their own key tied to a `user_id`
- **Automatic expiry** - keys expire after a configurable number of days (default: 90)
- **Instant revocation** - compromised keys can be revoked without affecting other integrations
- **Full audit trail** - every auth attempt is logged with endpoint, timestamp, and success/failure
- **Key rotation** - create a new key, migrate the consumer, revoke the old key

### Portfolio Value

This feature demonstrates production security patterns that interviewers and reviewers look for:

- Defence-in-depth (multiple auth mechanisms working together)
- Zero-trust key storage (only hash stored, raw key shown once)
- Audit logging for compliance (SOC 2, GDPR data access logs)
- Clean API design with Pydantic validation
- Comprehensive test coverage (unit + integration)

---

## 3. Architecture Overview

### 3.1 Where It Fits in the Codebase

```
monster-resort-concierge/
├── app/
│   ├── main.py              # Wiring: creates APIKeyManager, mounts router
│   ├── security.py          # Core: APIKeyManager class (create, verify, revoke, audit)
│   ├── admin_routes.py      # NEW: REST endpoints for key management
│   ├── auth_mixins.py       # Updated: jwt_or_api_key now checks managed keys
│   ├── auth.py              # Unchanged: JWT creation/verification
│   └── config.py            # Unchanged: static MRC_API_KEY setting
├── tests/
│   ├── test_api_key_manager.py  # NEW: 16 tests for the feature
│   └── conftest.py              # Updated: cleanup includes new tables
└── updated_readmes/
    └── API_KEY_MANAGEMENT_GUIDE.md  # This document
```

### 3.2 Data Flow Diagram

```
                    ┌────────────────────────────────────────────────┐
                    │                 CLIENT REQUEST                  │
                    │                                                │
                    │  Headers:                                      │
                    │    X-API-Key: mr_abc123...   (managed key)     │
                    │    -- OR --                                    │
                    │    Authorization: Bearer mr_abc123...          │
                    │    -- OR --                                    │
                    │    Authorization: Bearer <static-api-key>      │
                    │    -- OR --                                    │
                    │    Authorization: Bearer <jwt-token>           │
                    └─────────────────────┬──────────────────────────┘
                                          │
                                          ▼
                    ┌─────────────────────────────────────────────────┐
                    │           jwt_or_api_key (auth_mixins.py)       │
                    │                                                 │
                    │  1. Check X-API-Key header                      │
                    │     ├── Match static key? → return "api_key_user│
                    │     └── Starts with mr_?                        │
                    │         ├── manager.verify_key() → user_id      │
                    │         │   ├── log_usage(success=True)         │
                    │         │   └── return user_id                  │
                    │         └── Invalid → log_usage(success=False)  │
                    │                                                 │
                    │  2. Check Bearer token                          │
                    │     ├── Match static key? → return "api_key_user│
                    │     ├── Starts with mr_? → same as above        │
                    │     └── Try JWT decode → return username         │
                    │                                                 │
                    │  3. Nothing matched → 401 Unauthorized          │
                    └─────────────────────────────────────────────────┘
                                          │
                              ┌───────────┴───────────┐
                              │                       │
                              ▼                       ▼
                    ┌──────────────────┐    ┌──────────────────────┐
                    │   /chat, etc.    │    │  /admin/api-keys/*   │
                    │ (normal routes)  │    │  (admin endpoints)   │
                    └──────────────────┘    └──────────────────────┘
```

### 3.3 Database Schema

Two tables are auto-created by `APIKeyManager._ensure_schema()` on first init:

```sql
-- Stores hashed keys and metadata
CREATE TABLE IF NOT EXISTS api_keys (
    key_hash    TEXT PRIMARY KEY,   -- SHA-256 of the raw key
    user_id     TEXT NOT NULL,      -- Owner identifier
    created_at  TEXT NOT NULL,      -- ISO 8601 timestamp
    expires_at  TEXT,               -- ISO 8601 timestamp (NULL = never)
    last_used_at TEXT,              -- Updated on each successful verify
    is_active   INTEGER DEFAULT 1   -- 0 = revoked
);

-- Audit log of every authentication attempt
CREATE TABLE IF NOT EXISTS api_key_usage (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    key_hash  TEXT NOT NULL,        -- Links to api_keys.key_hash
    endpoint  TEXT NOT NULL,        -- e.g. "/chat", "/admin/api-keys"
    timestamp TEXT NOT NULL,        -- ISO 8601
    success   INTEGER NOT NULL      -- 1 = authenticated, 0 = rejected
);
```

**Important:** The raw API key is **never stored**. Only the SHA-256 hash is persisted. The raw key is returned exactly once during creation.

---

## 4. Component Deep Dive

### 4.1 APIKeyManager (`app/security.py`)

The core class that handles all key lifecycle operations.

#### Methods

| Method | Purpose | Returns |
|--------|---------|---------|
| `__init__(db)` | Stores DB ref, calls `_ensure_schema()` | - |
| `_ensure_schema()` | Creates `api_keys` and `api_key_usage` tables if missing | - |
| `create_key(user_id, expires_days=90)` | Generates `mr_` prefixed key, stores SHA-256 hash | Raw key (string) |
| `verify_key(key)` | Hashes input, checks DB for active + non-expired match | `user_id` or `None` |
| `log_usage(key, endpoint, success)` | Writes audit entry to `api_key_usage` | - |
| `list_keys(user_id=None)` | Returns key metadata with truncated `key_id` | List of dicts |
| `revoke_key(key_id)` | Sets `is_active = 0` for matching key | `True`/`False` |
| `get_usage(key_hash=None, limit=100)` | Returns audit entries with JOINed user_id | List of dicts |

#### Key Design: Truncated `key_id`

External-facing methods (`list_keys`, `get_usage`, `revoke_key`) use a **truncated key_id** (first 12 characters of the SHA-256 hash) instead of the full 64-character hash. This provides:

- **Sufficient uniqueness** for identification (12 hex chars = 48 bits = 281 trillion possibilities)
- **Safe to display** in dashboards and logs without leaking the full hash
- **Prefix matching** via SQL `LIKE` for revocation and filtering

```python
# Example key_id: "a1b2c3d4e5f6"
# Full hash:      "a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef12345678"
```

### 4.2 Admin Routes (`app/admin_routes.py`)

A standalone `APIRouter` that provides CRUD operations for API keys.

#### File Structure

```python
# Pydantic Models (request/response validation)
class CreateKeyRequest     # user_id (required), expires_days (1-365, default 90)
class CreateKeyResponse    # raw_key, user_id, expires_days, message
class KeyInfo              # key_id, user_id, created_at, expires_at, last_used_at, is_active
class UsageEntry           # id, key_id, user_id, endpoint, timestamp, success

# Dependency
def get_api_key_manager(request)  # Extracts manager from app.state

# Endpoints
POST   /admin/api-keys           → create_api_key()
GET    /admin/api-keys           → list_api_keys()
DELETE /admin/api-keys/{key_id}  → revoke_api_key()
GET    /admin/api-keys/usage     → get_usage()
```

#### Why a Separate Router?

- **Separation of concerns** - admin operations are isolated from user-facing routes
- **Easy to add middleware** - could add admin-only auth, IP whitelisting, or stricter rate limits later
- **Testable** - can be tested independently with its own TestClient
- **Tag grouping** - appears as its own section in FastAPI auto-docs (`/docs`)

### 4.3 Auth Mixin Integration (`app/auth_mixins.py`)

The `jwt_or_api_key` dependency was rewritten to support three authentication mechanisms in priority order:

```
1. X-API-Key header → static key → managed key (mr_)
2. Bearer token     → static key → managed key (mr_) → JWT
3. Nothing matched  → 401 Unauthorized
```

#### Key Changes from Previous Implementation

| Aspect | Before | After |
|--------|--------|-------|
| Managed keys | Not supported | Full support via `manager.verify_key()` |
| Audit logging | None | `manager.log_usage()` on every managed-key attempt |
| Hardcoded backdoor | `6f2b8e3a...` hex string accepted as valid token | Removed |
| JWT verification | Called `verify_token(token)` which expected `HTTPAuthorizationCredentials` | Calls `pyjwt.decode()` directly |
| Request access | No `Request` parameter | Added `Request` to access `app.state.api_key_manager` |

### 4.4 App Wiring (`app/main.py`)

Four lines were added to `build_app()`:

```python
# Import (at top of file)
from .security import install_rate_limiter, APIKeyManager
from .admin_routes import router as admin_router

# In build_app(), after db = DatabaseManager(settings):
api_key_manager = APIKeyManager(db)       # Creates tables if needed
app.state.api_key_manager = api_key_manager  # Makes it available via request.app.state

# After install_rate_limiter(app, settings):
app.include_router(admin_router)          # Mounts /admin/api-keys/* endpoints
```

The `APIKeyManager` is stored on `app.state` (FastAPI's built-in mechanism for sharing objects across requests) rather than using module-level globals. This makes it:

- **Testable** - each `TestClient` gets its own manager instance
- **Explicit** - no hidden import-time side effects
- **Consistent** - same pattern used for `app.state.limiter` (rate limiting)

---

## 5. API Reference

All endpoints require authentication via the `jwt_or_api_key` dependency (static API key, managed key, or JWT).

### 5.1 POST /admin/api-keys

**Create a new managed API key.**

```bash
curl -X POST http://localhost:8000/admin/api-keys \
  -H "Authorization: Bearer <your-api-key>" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "mobile-app-v2", "expires_days": 30}'
```

**Request Body:**

| Field | Type | Required | Default | Constraints |
|-------|------|----------|---------|-------------|
| `user_id` | string | Yes | - | min 1 character |
| `expires_days` | integer | No | 90 | 1-365 |

**Response (200):**

```json
{
  "raw_key": "mr_K7xP2mN9qR4wT6yB1cD8eF3gH5jL0nM2pQ4sU6vX8zA",
  "user_id": "mobile-app-v2",
  "expires_days": 30,
  "message": "Store this key securely - it will not be shown again."
}
```

**Important:** The `raw_key` is only returned once. It cannot be retrieved later.

### 5.2 GET /admin/api-keys

**List all managed keys (metadata only).**

```bash
# List all keys
curl http://localhost:8000/admin/api-keys \
  -H "Authorization: Bearer <your-api-key>"

# Filter by user_id
curl "http://localhost:8000/admin/api-keys?user_id=mobile-app-v2" \
  -H "Authorization: Bearer <your-api-key>"
```

**Response (200):**

```json
[
  {
    "key_id": "a1b2c3d4e5f6",
    "user_id": "mobile-app-v2",
    "created_at": "2026-02-13T10:30:00.000000",
    "expires_at": "2026-03-15T10:30:00.000000",
    "last_used_at": "2026-02-13T14:22:00.000000",
    "is_active": true
  }
]
```

### 5.3 DELETE /admin/api-keys/{key_id}

**Revoke a key (soft delete).**

```bash
curl -X DELETE http://localhost:8000/admin/api-keys/a1b2c3d4e5f6 \
  -H "Authorization: Bearer <your-api-key>"
```

**Response (200):**

```json
{
  "ok": true,
  "detail": "Key a1b2c3d4e5f6 revoked"
}
```

**Response (404):**

```json
{
  "detail": "Key not found"
}
```

### 5.4 GET /admin/api-keys/usage

**View the audit log.**

```bash
# All usage (most recent first, default limit 100)
curl http://localhost:8000/admin/api-keys/usage \
  -H "Authorization: Bearer <your-api-key>"

# Filter by key and limit results
curl "http://localhost:8000/admin/api-keys/usage?key_id=a1b2c3d4e5f6&limit=10" \
  -H "Authorization: Bearer <your-api-key>"
```

**Response (200):**

```json
[
  {
    "id": 42,
    "key_id": "a1b2c3d4e5f6",
    "user_id": "mobile-app-v2",
    "endpoint": "/chat",
    "timestamp": "2026-02-13T14:22:00.000000",
    "success": true
  },
  {
    "id": 41,
    "key_id": "a1b2c3d4e5f6",
    "user_id": "mobile-app-v2",
    "endpoint": "/chat",
    "timestamp": "2026-02-13T14:21:55.000000",
    "success": false
  }
]
```

---

## 6. Security Design Decisions

### 6.1 Key Storage: Hash-Only

Raw keys are **never stored** in the database. The flow is:

```
create_key("alice")
  → Generate: mr_K7xP2mN9qR4w...
  → SHA-256:  a1b2c3d4e5f6...   ← stored in DB
  → Return:   mr_K7xP2mN9qR4w... ← shown to user ONCE
```

On verification:

```
verify_key("mr_K7xP2mN9qR4w...")
  → SHA-256:  a1b2c3d4e5f6...
  → DB lookup by hash → found, active, not expired
  → Return:   "alice"
```

**Why:** If the database is compromised, attackers get hashes, not usable keys. SHA-256 is one-way; they cannot reverse it to obtain the original `mr_` key.

### 6.2 Key Prefix: `mr_`

All managed keys start with `mr_` (Monster Resort). This provides:

- **Quick identification** in logs and config files (is this a managed key or a static one?)
- **Routing in auth_mixins** - the auth flow only calls `manager.verify_key()` for `mr_` prefixed tokens, avoiding unnecessary DB lookups for static keys and JWTs
- **Grep-friendly** - `grep "mr_" .env` instantly finds managed keys in config

### 6.3 Soft Revocation

`revoke_key()` sets `is_active = 0` rather than deleting the row. This preserves:

- **Audit history** - usage logs still JOIN to the key record
- **Forensic evidence** - when a key was created, by whom, when it was revoked
- **Accidental revocation recovery** - an admin could re-activate if needed (manual SQL)

### 6.4 Audit on Failure

Both successful and failed authentication attempts are logged:

```python
if user_id:
    manager.log_usage(token, endpoint=request.url.path, success=True)
    return user_id
manager.log_usage(token, endpoint=request.url.path, success=False)
```

**Why:** Failed attempts are often more important than successes for security monitoring. Repeated failures from the same key suggest a leaked/compromised key being brute-forced.

### 6.5 Backdoor Removal

The previous `auth_mixins.py` contained a hardcoded hex string that was accepted as a valid bearer token:

```python
# REMOVED - this was a security vulnerability
or token == "6f2b8e3a9d1c4f5b2a8e7d9c1b0a3f4e5d6c7b8a9f0e1d2c3b4a5f6e7d8c9b0"
```

This has been removed. Authentication now only accepts:
1. The static key from `MRC_API_KEY` environment variable
2. A valid managed `mr_` key
3. A valid JWT token

---

## 7. Testing Guide

### 7.1 Running the Test Suite

```bash
# Run only the API key management tests
uv run pytest tests/test_api_key_manager.py -v

# Run with coverage report
uv run pytest tests/test_api_key_manager.py -v --cov=app.security --cov=app.admin_routes --cov=app.auth_mixins

# Run all project tests (excluding known pre-existing failures)
uv run pytest tests/ -v -k "not health and not test_rag_empty_folder and not test_ragas_eval_example" \
  --ignore=tests/test_api_basic.py --ignore=tests/test_api_endpoints.py --ignore=tests/test_booking.py
```

### 7.2 Unit Tests Explained

Unit tests use a lightweight `_FakeDB` wrapper (no FastAPI, no real DatabaseManager) to test `APIKeyManager` in isolation.

| Test | What It Verifies | Why It Matters |
|------|-----------------|----------------|
| `test_returns_mr_prefix` | Created keys start with `mr_` | Ensures the key format is correct for auth routing |
| `test_key_is_unique` | Two keys for same user are different | Prevents duplicate key collisions |
| `test_valid_key_returns_user_id` | `verify_key()` returns the correct owner | Core auth functionality works |
| `test_invalid_key_returns_none` | Random strings return `None` | Invalid keys don't authenticate |
| `test_expired_key_returns_none` | Past-expiry keys are rejected | Expiration is enforced |
| `test_revoke_prevents_verification` | Revoked keys fail verification | Revocation actually works |
| `test_revoke_nonexistent_returns_false` | Missing key returns `False` | Edge case handled gracefully |
| `test_lists_all_keys` | `list_keys()` returns all created keys | Admin can see all keys |
| `test_filter_by_user_id` | `list_keys(user_id=)` filters correctly | Admin can find a specific user's keys |
| `test_key_id_is_truncated` | Listed `key_id` is 12 characters | Full hash is never exposed |
| `test_log_and_get_usage` | Usage logging round-trips correctly | Audit trail is reliable |

### 7.3 Integration Tests Explained

Integration tests use FastAPI's `TestClient` with a real app instance and isolated SQLite database.

| Test | What It Verifies | Why It Matters |
|------|-----------------|----------------|
| `test_create_requires_auth` | POST without auth returns 401 | Admin endpoints are protected |
| `test_create_and_list_keys` | Create then list shows the key | Full CRUD flow works end-to-end |
| `test_managed_key_authenticates_chat` | Created key works on `/chat` | Keys actually authenticate real endpoints |
| `test_revoke_key_blocks_access` | Revoked key returns 401 on `/chat` | Revocation propagates to auth |
| `test_usage_log_populated` | Usage appears after using a key | Audit trail works in real auth flow |

### 7.4 Manual End-to-End Testing

Start the app and test the full lifecycle:

```bash
# 1. Start the server
uv run uvicorn app.main:app --reload

# 2. Create a managed key (use your MRC_API_KEY from .env for auth)
curl -s -X POST http://localhost:8000/admin/api-keys \
  -H "Authorization: Bearer $(grep MRC_API_KEY .env | cut -d= -f2)" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test-user", "expires_days": 7}' | python -m json.tool

# Save the raw_key from the response, e.g.:
# export MANAGED_KEY="mr_K7xP2mN9qR4w..."

# 3. Use the managed key to call /chat
curl -s -X POST http://localhost:8000/chat \
  -H "X-API-Key: $MANAGED_KEY" \
  -H "Content-Type: application/json" \
  -d '{"message": "What rooms are available?"}' | python -m json.tool

# 4. Check the usage log
curl -s http://localhost:8000/admin/api-keys/usage \
  -H "Authorization: Bearer $(grep MRC_API_KEY .env | cut -d= -f2)" | python -m json.tool

# 5. List all keys
curl -s http://localhost:8000/admin/api-keys \
  -H "Authorization: Bearer $(grep MRC_API_KEY .env | cut -d= -f2)" | python -m json.tool

# 6. Revoke the key (use the key_id from the list response)
curl -s -X DELETE http://localhost:8000/admin/api-keys/<key_id> \
  -H "Authorization: Bearer $(grep MRC_API_KEY .env | cut -d= -f2)" | python -m json.tool

# 7. Confirm the revoked key no longer works
curl -s -X POST http://localhost:8000/chat \
  -H "X-API-Key: $MANAGED_KEY" \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello"}' | python -m json.tool
# Expected: 401 Unauthorized
```

---

## 8. User Impact & Use Cases

### For API Consumers (External Integrations)

| Scenario | Before | After |
|----------|--------|-------|
| Mobile app needs API access | Share the single `MRC_API_KEY` | Create a dedicated `mr_` key for the app |
| Key leaked in a git commit | Rotate `MRC_API_KEY`, break ALL integrations | Revoke only the leaked key, others unaffected |
| Onboarding a partner | Share the master key (security risk) | Issue a time-limited key with audit trail |
| Debugging "who called what" | All requests look the same | Filter audit log by `user_id` |

### For Platform Administrators

| Capability | Benefit |
|------------|---------|
| **Key listing** | See all active integrations at a glance |
| **Usage audit** | Compliance reporting, anomaly detection |
| **Per-key revocation** | Incident response without service disruption |
| **Expiry enforcement** | Keys auto-expire, forcing rotation |

### For Developers

| Capability | Benefit |
|------------|---------|
| **Separate test keys** | Create short-lived keys for CI/CD pipelines |
| **Auth debugging** | See exactly which auth method succeeded in logs |
| **Self-documenting API** | FastAPI auto-docs at `/docs` include admin endpoints |

---

## 9. Configuration & Environment

No new environment variables are required. The feature uses the existing database and works automatically.

| Setting | Source | Used By | Notes |
|---------|--------|---------|-------|
| `MRC_API_KEY` | `.env` | `auth_mixins.py` | Static key, still works as before |
| `MRC_DATABASE_URL` | `.env` | `APIKeyManager` | Keys stored in same SQLite DB |
| `MRC_JWT_SECRET_KEY` | `.env` | `auth_mixins.py` | JWT auth still works as before |

### Database Tables (Auto-Created)

The `api_keys` and `api_key_usage` tables are created automatically when `APIKeyManager.__init__()` runs during app startup. No migrations needed.

---

## 10. Troubleshooting

### "API key manager not available" (503)

**Cause:** `app.state.api_key_manager` is `None`. The admin routes can't find the manager.

**Fix:** Ensure `main.py` has the wiring lines:
```python
api_key_manager = APIKeyManager(db)
app.state.api_key_manager = api_key_manager
```

### Managed key returns 401 even though it was just created

**Check these in order:**

1. **Prefix** - Key must start with `mr_`. Other tokens go through static/JWT checks.
2. **Expiry** - Check `expires_at` in key listing. If `expires_days=0`, the key expires immediately.
3. **Revoked** - Check `is_active` in key listing. It should be `true`.
4. **Typo** - Copy-paste the full key exactly as returned by the create endpoint.

### Tests fail with `RecursionError`

**Cause:** A naming conflict in the test helper class. The `_FakeDB.session` method and inner class had the same name.

**Fix:** This was resolved. The test file uses separate `_FakeSession` and `_FakeDB` classes.

### Pre-existing test failures

The following tests were already failing before this feature and are unrelated:

| Test | Reason |
|------|--------|
| `test_health_endpoint` | No `/health` route exists |
| `test_tools_endpoint_auth` | No `/tools` route exists |
| `test_chat_booking_flow` | Calls `/chat` without auth headers |
| `test_rag_policy_answer` | Calls `/chat` without auth headers |
| `test_rag_empty_folder` | ChromaDB rejects empty document lists |
| `test_ragas_eval_example` | Missing `context_precision` metric |

---

## 11. Security Fixes Included

Two security issues were fixed as part of this implementation:

### 11.1 Hardcoded Backdoor Removed

**File:** `app/auth_mixins.py` (line 27, old version)

**Before:**
```python
if (
    token == settings.api_key.strip()
    or token == "6f2b8e3a9d1c4f5b2a8e7d9c1b0a3f4e5d6c7b8a9f0e1d2c3b4a5f6e7d8c9b0"
):
    return "api_key_user"
```

**Risk:** Anyone who discovered this hex string (e.g., from source code, a leaked commit, or by reading the `.env` example) could authenticate as `api_key_user` regardless of the configured `MRC_API_KEY`.

**After:** Only `settings.api_key` (from `MRC_API_KEY` env var) is accepted as a static key.

### 11.2 JWT Verification Bug Fixed

**File:** `app/auth_mixins.py` (line 33, old version)

**Before:**
```python
user = verify_token(token)  # token is a plain string
```

The `verify_token()` function in `auth.py` expects an `HTTPAuthorizationCredentials` object and accesses `credentials.credentials`. Passing a plain string would raise an `AttributeError`, which was silently caught by the `except Exception: pass` block — meaning JWT authentication **never actually worked** in the mixin.

**After:**
```python
payload = pyjwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
username = payload.get("sub")
```

JWT tokens are now correctly decoded and validated.

---

## 12. Future Enhancements

| Enhancement | Effort | Value |
|-------------|--------|-------|
| **Role-based admin access** | Medium | Only admins can manage keys, not any authenticated user |
| **Key scoping** | Medium | Restrict keys to specific endpoints (e.g., read-only keys) |
| **Rate limiting per key** | Low | Each managed key gets its own rate limit bucket |
| **Webhook on revocation** | Low | Notify integration owners when their key is revoked |
| **Dashboard UI** | High | Gradio or React admin panel for key management |
| **Key re-activation** | Low | Admin can un-revoke a key (currently requires manual SQL) |
| **Bulk operations** | Low | Revoke all keys for a user_id in one call |

---

*This document is part of the Monster Resort Concierge engineering documentation. For the broader security architecture, see [SECURITY_IMPLEMENTATION.md](./SECURITY_IMPLEMENTATION.md).*
