# Monster Resort Concierge - Security Implementation Documentation

**Document ID:** MR-SEC-001
**Owner:** Monster Resort Engineering & Security
**Status:** FINAL
**Classification:** Internal - Engineering
**Last Updated:** 2026-02-04

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Security Architecture Overview](#2-security-architecture-overview)
3. [Authentication Layer](#3-authentication-layer)
   - 3.1 [JWT (JSON Web Token) Authentication](#31-jwt-json-web-token-authentication)
   - 3.2 [API Key Authentication](#32-api-key-authentication)
   - 3.3 [Hybrid Auth Mixin (jwt_or_api_key)](#33-hybrid-auth-mixin-jwt_or_api_key)
4. [API Key Management System](#4-api-key-management-system)
5. [Input Validation & Sanitisation](#5-input-validation--sanitisation)
   - 5.1 [Message Validation](#51-message-validation)
   - 5.2 [SQL Injection Prevention](#52-sql-injection-prevention)
   - 5.3 [XSS Prevention](#53-xss-prevention)
   - 5.4 [Business Logic Validation](#54-business-logic-validation)
6. [Rate Limiting](#6-rate-limiting)
7. [Configuration Security](#7-configuration-security)
8. [Database Security](#8-database-security)
9. [Container & Infrastructure Security](#9-container--infrastructure-security)
10. [Logging, Monitoring & Audit Trail](#10-logging-monitoring--audit-trail)
11. [CI/CD Security](#11-cicd-security)
12. [Security Testing](#12-security-testing)
13. [Threat Model & OWASP Mapping](#13-threat-model--owasp-mapping)
14. [Known Limitations & Remediation Plan](#14-known-limitations--remediation-plan)
15. [Security Checklist for Deployment](#15-security-checklist-for-deployment)

---

## 1. Executive Summary

The Monster Resort Concierge implements a **defence-in-depth** security strategy across multiple layers: authentication, input validation, rate limiting, secure configuration, database protection, container hardening, and observability. The system supports two independent authentication mechanisms (JWT and API Key) that can be used separately or combined via a hybrid mixin, providing flexibility for both human users and service-to-service integrations.

### Key Security Features at a Glance

| Layer | Implementation | File(s) |
|-------|---------------|---------|
| Authentication (Human Users) | JWT with HS256 + bcrypt passwords | `app/auth.py` |
| Authentication (Services) | Bearer token API keys | `app/security.py` |
| Hybrid Auth | JWT OR API Key per request | `app/auth_mixins.py` |
| API Key Lifecycle | SHA-256 hashing, rotation, expiry, audit | `app/security.py` (APIKeyManager) |
| Input Validation | Bleach sanitisation, regex pattern matching | `app/validation.py` |
| Rate Limiting | SlowAPI (per-IP, configurable) | `app/security.py` |
| Configuration | Pydantic validators, env-only secrets | `app/config.py` |
| Database | Parameterised queries, transactions, WAL | `app/database.py` |
| Container | Non-root user, health checks, slim base | `Dockerfile` |
| Monitoring | Prometheus metrics, JSON structured logs | `app/monitoring.py`, `app/logging_utils.py` |
| CI/CD | Linting, test suite, isolated environments | `.github/workflows/ci.yml` |

---

## 2. Security Architecture Overview

```
                          ┌─────────────────────────────────────┐
                          │          INTERNET / CLIENT           │
                          └──────────────┬──────────────────────┘
                                         │
                                         ▼
                          ┌─────────────────────────────────────┐
                          │        RATE LIMITER (SlowAPI)       │
                          │   60 requests/minute per IP         │
                          │   429 Too Many Requests on breach   │
                          └──────────────┬──────────────────────┘
                                         │
                                         ▼
                          ┌─────────────────────────────────────┐
                          │     PROMETHEUS METRICS MIDDLEWARE    │
                          │   Records: method, path, status,    │
                          │   latency for every request         │
                          └──────────────┬──────────────────────┘
                                         │
                                         ▼
                          ┌─────────────────────────────────────┐
                          │       AUTHENTICATION GATEWAY        │
                          │                                     │
                          │  ┌───────────┐    ┌──────────────┐  │
                          │  │    JWT    │ OR │   API Key    │  │
                          │  │  (Human) │    │  (Service)   │  │
                          │  └───────────┘    └──────────────┘  │
                          │                                     │
                          │  jwt_or_api_key() resolves which    │
                          │  mechanism the request is using     │
                          └──────────────┬──────────────────────┘
                                         │
                                         ▼
                          ┌─────────────────────────────────────┐
                          │       INPUT VALIDATION LAYER        │
                          │                                     │
                          │  • Bleach HTML sanitisation          │
                          │  • SQL injection pattern detection  │
                          │  • XSS pattern detection            │
                          │  • Length limits (5000 chars max)    │
                          │  • Business rule validation         │
                          └──────────────┬──────────────────────┘
                                         │
                                         ▼
                          ┌─────────────────────────────────────┐
                          │        APPLICATION LOGIC            │
                          │   Agent → Tools → RAG → Database    │
                          └──────────────┬──────────────────────┘
                                         │
                                         ▼
                          ┌─────────────────────────────────────┐
                          │         DATABASE LAYER              │
                          │  • Parameterised queries (?)        │
                          │  • Transaction rollback on error    │
                          │  • WAL mode for concurrency         │
                          │  • Automatic backups                │
                          └─────────────────────────────────────┘
```

### Design Principles

1. **Defence in Depth** - No single layer is solely responsible for security. Even if authentication is bypassed, input validation catches injection attacks. Even if validation fails, parameterised queries prevent SQL injection at the database level.
2. **Fail Closed** - Missing or invalid credentials result in `401 Unauthorized`. Missing or invalid input results in `400 Bad Request`. The system never falls through to unprotected execution.
3. **Least Privilege** - The Docker container runs as a non-root user (`appuser`). The database uses minimal permissions. API keys are scoped per-user.
4. **Secrets Never in Code** - All secrets are loaded from environment variables via Pydantic settings. Startup validators reject weak or default values.

---

## 3. Authentication Layer

The system implements **two independent authentication mechanisms** that can be used individually or combined. This provides flexibility: human users authenticate with username/password to receive a JWT, while automated services or API consumers use long-lived API keys.

### 3.1 JWT (JSON Web Token) Authentication

**File:** `app/auth.py`

JWT authentication is used for interactive user sessions (e.g., a user logging in via the Gradio UI or a frontend application).

#### How It Works

```
┌──────────┐     POST /login          ┌──────────────┐
│  Client  │ ──────────────────────▶  │  FastAPI      │
│          │  { username, password }   │  /login       │
└──────────┘                          └──────┬───────┘
                                             │
                                             ▼
                                      ┌──────────────┐
                                      │ users_db     │
                                      │ (in-memory)  │
                                      │              │
                                      │ Lookup user  │
                                      │ by username  │
                                      └──────┬───────┘
                                             │
                                             ▼
                                      ┌──────────────┐
                                      │ passlib      │
                                      │ bcrypt       │
                                      │              │
                                      │ Verify hash  │
                                      │ against pwd  │
                                      └──────┬───────┘
                                             │
                                             ▼
                                      ┌──────────────┐
                                      │ PyJWT        │
                                      │              │
                                      │ Sign token   │
                                      │ HS256 algo   │
                                      │ 30-min exp   │
                                      └──────┬───────┘
                                             │
                                             ▼
                                      { "token": "eyJ..." }
```

#### Implementation Details

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| **Algorithm** | HS256 (HMAC-SHA256) | Industry standard symmetric signing. Suitable for single-service architectures where the same server issues and verifies tokens. |
| **Token Expiry** | 30 minutes | Short-lived to limit the damage window if a token is compromised. Balances security with usability. |
| **Secret Key** | Loaded from `MRC_JWT_SECRET_KEY` env var | Never hardcoded. Startup validation rejects keys shorter than 32 characters or set to the placeholder value. |
| **Password Hashing** | bcrypt via passlib | Adaptive hashing algorithm with automatic salting. Cost factor makes brute-force attacks computationally expensive. |

#### Startup Security Checks (auth.py:57-79)

The system performs **three critical validations** at import time, before the server starts:

```python
# 1. Secret must exist
if not SECRET_KEY:
    raise ValueError("MRC_JWT_SECRET_KEY environment variable is required.")

# 2. Secret must not be the default placeholder
if SECRET_KEY == "changeme-super-secret-key":
    raise ValueError("JWT secret is still set to the default placeholder value.")

# 3. Secret must be strong enough
if len(SECRET_KEY) < 32:
    raise ValueError("JWT secret must be at least 32 characters for security.")
```

This means the application **will refuse to start** if the JWT secret is missing, weak, or left as a default. This is a deliberate "fail loud" strategy that prevents accidental deployment with insecure configuration.

#### Token Verification Flow (auth.py:95-107)

```python
def verify_token(credentials):
    try:
        payload = jwt.decode(credentials, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return username
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
```

Key security properties:
- **Algorithm pinning**: Only `HS256` is accepted, preventing algorithm confusion attacks (e.g., `none` algorithm bypass).
- **Explicit claim validation**: The `sub` (subject) claim must be present.
- **Separate error messages**: Expired tokens get a distinct error from invalid tokens, helping legitimate users understand what went wrong without leaking information to attackers.

---

### 3.2 API Key Authentication

**File:** `app/security.py`

API key authentication is used for service-to-service communication, CLI tools, and automated integrations where a login flow is impractical.

#### How It Works

```
┌──────────┐     POST /chat                    ┌───────────────┐
│  Client  │ ──────────────────────────────▶   │  FastAPI       │
│          │  Authorization: Bearer <key>       │  /chat         │
└──────────┘                                   └───────┬───────┘
                                                       │
                                                       ▼
                                               ┌───────────────┐
                                               │ Parse Header  │
                                               │               │
                                               │ Extract token │
                                               │ after "Bearer"│
                                               └───────┬───────┘
                                                       │
                                                       ▼
                                               ┌───────────────┐
                                               │ Compare with  │
                                               │ settings.     │
                                               │ api_key       │
                                               │ (from .env)   │
                                               └───────┬───────┘
                                                       │
                                             ┌─────────┴──────────┐
                                             │                    │
                                        Match ✓              No Match ✗
                                             │                    │
                                             ▼                    ▼
                                     Return user           401 Unauthorized
                                     identity              + Log warning
```

#### Validation Steps (security.py:273-304)

1. **Header presence check**: If no `Authorization` header exists, return `401` with a helpful message explaining the expected format.
2. **Format validation**: If the header doesn't start with `Bearer `, return `401` with format guidance.
3. **Token extraction**: Strip the `Bearer ` prefix and whitespace.
4. **Comparison**: Match against `settings.api_key` (loaded from `MRC_API_KEY` environment variable).
5. **Logging**: All failed attempts are logged with the first 8 characters of the received token for debugging (never the full key).

---

### 3.3 Hybrid Auth Mixin (jwt_or_api_key)

**File:** `app/auth_mixins.py`

The hybrid mixin is the **primary authentication dependency** used on protected routes like `/chat`. It accepts either authentication method, enabling both human users and automated services to access the same endpoints.

#### Resolution Order

```python
async def jwt_or_api_key(
    x_api_key: str = Header(default=None),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    # 1. Try X-API-Key header first
    if x_api_key matches settings.api_key → return "api_key_user"

    # 2. Try Authorization: Bearer header
    if credentials.scheme == "bearer":
        # 2a. Check if it's the master API key
        if token matches settings.api_key → return "api_key_user"

        # 2b. Try to decode as JWT
        try verify_token(token) → return username
        except → fall through

    # 3. Nothing worked
    raise 401 Unauthorized
```

#### Why Two Headers?

| Header | Use Case | Example |
|--------|----------|---------|
| `X-API-Key: <key>` | Simple API integrations, scripts, Postman | `curl -H "X-API-Key: abc123" /chat` |
| `Authorization: Bearer <token>` | JWT from login, or API key via standard OAuth2 header | `curl -H "Authorization: Bearer eyJ..." /chat` |

This dual-header approach follows industry conventions where `X-API-Key` is the traditional API key header, and `Authorization: Bearer` is the OAuth2/JWT standard. Supporting both reduces friction for integrators.

---

## 4. API Key Management System

**File:** `app/security.py` (APIKeyManager class)

Beyond the simple key comparison, the project includes a full **API Key Lifecycle Management** system with rotation, expiration, and audit logging.

### Key Lifecycle

```
 ┌──────────┐     create_key()     ┌──────────────┐
 │  Admin   │ ──────────────────▶  │ APIKeyManager │
 │          │  user_id, ttl=90d    │               │
 └──────────┘                      └──────┬───────┘
                                          │
                                  ┌───────▼────────┐
                                  │ Generate Key   │
                                  │ mr_<random32>  │
                                  │                │
                                  │ SHA-256 hash   │
                                  │ the key        │
                                  └───────┬────────┘
                                          │
                              ┌───────────▼────────────┐
                              │  Store in DB:          │
                              │  • key_hash (SHA-256)  │
                              │  • user_id             │
                              │  • created_at          │
                              │  • expires_at          │
                              │  • is_active = 1       │
                              └───────────┬────────────┘
                                          │
                                          ▼
                              Return raw key ONCE
                              (never stored in plaintext)
```

### Database Schema

```sql
CREATE TABLE IF NOT EXISTS api_keys (
    key_hash     TEXT PRIMARY KEY,   -- SHA-256 of the raw key
    user_id      TEXT NOT NULL,       -- Owner of the key
    created_at   TEXT NOT NULL,       -- ISO 8601 timestamp
    expires_at   TEXT,                -- Null = never expires
    last_used_at TEXT,                -- Updated on each use
    is_active    INTEGER DEFAULT 1    -- Soft delete / revocation
);

CREATE TABLE IF NOT EXISTS api_key_usage (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    key_hash  TEXT NOT NULL,           -- Which key was used
    endpoint  TEXT NOT NULL,           -- Which endpoint was hit
    timestamp TEXT NOT NULL,           -- When
    success   INTEGER NOT NULL         -- 1 = success, 0 = failure
);
```

### Security Properties

| Property | Implementation | Why It Matters |
|----------|---------------|----------------|
| **Keys are never stored in plaintext** | Only the SHA-256 hash is persisted. The raw key is returned once at creation and never again. | Even if the database is compromised, attackers cannot extract usable API keys. |
| **Keys have a prefix** | All keys start with `mr_` (e.g., `mr_abc123...`) | Makes it easy to identify Monster Resort keys in logs, helps secret scanners detect leaked keys. |
| **Keys expire** | Default 90-day expiration, checked on every verification | Forces regular rotation, limits the damage window of a compromised key. |
| **Keys can be revoked** | `is_active` flag allows instant revocation without deletion | Preserves audit trail while immediately blocking access. |
| **Usage is audited** | Every key use records the endpoint, timestamp, and success/failure | Enables detection of anomalous access patterns (e.g., a key suddenly hitting endpoints it never accessed before). |
| **Last-used tracking** | `last_used_at` is updated on each successful verification | Allows identification of stale keys that should be rotated or revoked. |

### Key Verification Flow (security.py:233-260)

```python
def verify_key(self, key: str) -> Optional[str]:
    key_hash = hashlib.sha256(key.encode()).hexdigest()
    row = db.execute("SELECT ... WHERE key_hash = ?", (key_hash,))

    if not row:           return None  # Key doesn't exist
    if expired(row):      return None  # Key has expired (log warning)
    if not row.is_active: return None  # Key has been revoked (log warning)

    update_last_used(key_hash)         # Track usage
    return row.user_id                 # Return authenticated identity
```

---

## 5. Input Validation & Sanitisation

**File:** `app/validation.py`

All user input passes through a multi-stage validation pipeline before reaching the application logic. This is the **last line of defence** before data enters the system.

### 5.1 Message Validation

The `validate_message()` function applies the following checks in order:

```
User Input
    │
    ▼
┌──────────────────┐
│ 1. Null Check    │ → "Message cannot be None"
└────────┬─────────┘
         ▼
┌──────────────────┐
│ 2. Type Check    │ → Extracts text from dict or converts to string
└────────┬─────────┘
         ▼
┌──────────────────┐
│ 3. Empty Check   │ → "Message cannot be empty"
└────────┬─────────┘
         ▼
┌──────────────────┐
│ 4. Length Check   │ → Max 5000 characters
└────────┬─────────┘
         ▼
┌──────────────────┐
│ 5. SQL Injection │ → Pattern matching against known payloads
│    Detection     │
└────────┬─────────┘
         ▼
┌──────────────────┐
│ 6. XSS Detection │ → Regex matching against script/event patterns
└────────┬─────────┘
         ▼
┌──────────────────┐
│ 7. HTML Sanitise │ → Bleach strips ALL HTML tags
└────────┬─────────┘
         ▼
    Clean Output
```

### 5.2 SQL Injection Prevention

**Two layers of protection:**

#### Layer 1: Pattern Detection (validation.py:33-45)

```python
dangerous_sql = [
    "DROP TABLE", "DELETE FROM", "INSERT INTO",
    "UPDATE ", "--", "/*", "*/", "';", "OR 1=1",
]
if any(pattern in user_text.upper() for pattern in dangerous_sql):
    raise ValidationError("Potentially malicious SQL detected")
```

This catches common SQL injection payloads at the input boundary, before they reach any database code. The patterns are checked case-insensitively against the uppercase input.

#### Layer 2: Parameterised Queries (database.py)

Even if a malicious payload bypasses the pattern detection, all database queries use parameterised placeholders (`?`), which prevent SQL injection at the driver level:

```python
# SAFE: Parameterised query - user input is never interpolated into SQL
conn.execute(
    "INSERT INTO bookings (booking_reference, session_id, guest_name, ...) VALUES (?, ?, ?, ...)",
    (booking_ref, session_id, guest_name, ...)
)

# SAFE: Parameterised lookup
conn.execute(
    "SELECT * FROM bookings WHERE booking_reference = ? OR session_id = ?",
    (booking_id, booking_id)
)
```

SQLite's `?` placeholder ensures the database driver treats user input as **data**, never as **SQL commands**.

### 5.3 XSS Prevention

**Two layers of protection:**

#### Layer 1: Regex Pattern Detection (validation.py:47-57)

```python
xss_patterns = [
    r"<script[^>]*>.*?</script>",  # Script tags
    r"javascript:",                 # JS protocol
    r"on\w+\s*=",                   # Event handlers (onclick=, onerror=, etc.)
    r"<iframe",                     # Iframe injection
    r"<object",                     # Object tag
    r"<embed",                      # Embed tag
]
```

These regex patterns catch the most common XSS vectors including script injection, event handler injection, and iframe/object embedding.

#### Layer 2: Bleach Sanitisation (validation.py:12-14)

```python
def sanitize_html(text: str) -> str:
    return bleach.clean(text, tags=[], strip=True)
```

Even if a novel XSS payload bypasses the regex patterns, `bleach.clean()` with `tags=[]` strips **all** HTML tags from the output. The `strip=True` parameter removes the tags entirely rather than escaping them, leaving only the text content.

### 5.4 Business Logic Validation

The `validate_booking()` function (validation.py:90-130) validates all booking-related input:

| Field | Validation Rules |
|-------|-----------------|
| **Guest Name** | 2-100 characters, only letters/spaces/hyphens/apostrophes, regex enforced |
| **Room Type** | Must be one of: "Standard Lair", "Deluxe Crypt", "Crypt Suite", "Penthouse Tomb" |
| **Check-in Date** | YYYY-MM-DD format, cannot be in the past, cannot be more than 1 year in future |
| **Check-out Date** | YYYY-MM-DD format, must be after check-in, maximum 30-night stay |
| **Guests** | Integer, minimum 1, maximum 10 |
| **Email** | RFC-compliant validation via `email_validator` library |

---

## 6. Rate Limiting

**File:** `app/security.py` (install_rate_limiter function)

Rate limiting protects the application from abuse, denial-of-service attacks, and excessive API usage.

### Configuration

| Parameter | Value | Source |
|-----------|-------|--------|
| **Rate Limit** | 60 requests/minute | `MRC_RATE_LIMIT_PER_MINUTE` env var |
| **Key Function** | `get_remote_address` (client IP) | SlowAPI default |
| **Exceeded Response** | HTTP 429 Too Many Requests | SlowAPI default handler |

### Implementation (security.py:334-357)

```python
def install_rate_limiter(app, settings: Settings) -> None:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded

    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=[f"{settings.rate_limit_per_minute}/minute"],
    )
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

### Graceful Degradation

The `install_rate_limiter` function handles the case where SlowAPI is not installed by logging a warning and continuing without rate limiting. This prevents the application from crashing due to a missing optional dependency:

```python
except ImportError:
    logger.warning("slowapi not installed, rate limiting disabled")
    return
```

---

## 7. Configuration Security

**File:** `app/config.py`

All application configuration is managed through Pydantic `BaseSettings`, which provides type-safe, validated configuration loaded from environment variables.

### Environment Variable Mapping

All settings use the `MRC_` prefix to avoid collisions with other applications:

| Environment Variable | Setting | Security Relevance |
|---------------------|---------|-------------------|
| `MRC_JWT_SECRET_KEY` | JWT signing secret | Must be 32+ chars, no default |
| `MRC_API_KEY` | API authentication key | Auto-generated if not set (dev), 32+ chars required (prod) |
| `MRC_OPENAI_API_KEY` | OpenAI API access | Required in prod/staging, optional in dev |
| `MRC_ANTHROPIC_API_KEY` | Anthropic API access (multi-model fallback) | Required if Anthropic is in the fallback chain |
| `MRC_OLLAMA_BASE_URL` | Ollama endpoint for local model fallback | Optional; defaults to localhost |
| `MRC_RATE_LIMIT_PER_MINUTE` | Rate limit threshold | Default: 60 |
| `MRC_ENVIRONMENT` | Runtime environment | Validates: dev, staging, prod, production |

### Production vs Development Security

The configuration system enforces **different security requirements** based on the environment:

```python
@field_validator("api_key", mode="before")
def validate_api_key_strength(cls, v, info):
    env = info.data.get("environment", "dev")
    if env == "dev":
        return v  # Auto-generated key is fine for development
    if env in ["prod", "production", "staging"]:
        if not v or len(v) < 32:
            raise ValueError(
                "API_KEY must be explicitly set and at least 32 characters in production"
            )
    return v
```

| Check | Dev | Staging/Prod |
|-------|-----|-------------|
| API Key present | Auto-generated if missing | **Required** |
| API Key length | Any | **32+ characters** |
| OpenAI API Key | Optional (mock responses) | **Required** |
| JWT Secret | Must be set | Must be set |
| JWT Secret strength | 32+ chars | 32+ chars |

### Multi-Model API Key Management

With the introduction of multi-model LLM orchestration (`app/llm_providers.py`), the system now manages API keys for multiple providers (OpenAI, Anthropic, Ollama). All keys follow the same `MRC_` prefix convention and are loaded via `app/config.py`. In AWS deployments (`deploy/aws/`), these keys are stored in **AWS Secrets Manager** and injected into ECS Fargate task definitions as environment variables, ensuring secrets never appear in container images or task configurations.

### Secrets Never Committed

The `.gitignore` file includes `.env`, preventing accidental commit of secrets:

```gitignore
.env
```

---

## 8. Database Security

**File:** `app/database.py`

### Parameterised Queries

Every SQL query uses `?` placeholders. There are **zero instances** of string interpolation or f-string formatting in SQL queries. This is the strongest protection against SQL injection.

### Transaction Safety

All database operations use a context manager that automatically commits on success and rolls back on failure:

```python
@contextmanager
def get_connection(self) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(self.db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise DatabaseError(f"Database transaction failed: {e}")
    finally:
        conn.close()
```

### Schema Versioning

The database uses a `schema_migrations` table to track the current schema version, preventing data corruption from mismatched schema expectations:

```sql
CREATE TABLE IF NOT EXISTS schema_migrations (
    version    INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);
```

### Performance Indexes

Indexes are created on frequently-queried columns to prevent slow queries that could be exploited for denial-of-service:

```sql
CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id);
CREATE INDEX IF NOT EXISTS idx_bookings_session_id ON bookings(session_id);
CREATE INDEX IF NOT EXISTS idx_bookings_reference  ON bookings(booking_reference);
```

### PostgreSQL Security (Production)

When using PostgreSQL (`MRC_DATABASE_URL=postgresql://...`):
- **Connection pooling** with `pool_pre_ping=True` detects stale connections
- **Parameterized queries** via SQLAlchemy `text()` — same SQL injection protection as SQLite
- **Credentials in environment variables** — never hardcoded, loaded from `.env` or Docker secrets
- **Network isolation** — in Docker Compose, postgres is only accessible from the `api` service (no external port binding in production)
- **Health checks** — `pg_isready` validates the database is accepting connections before the API starts

### Redis Security

When Redis is enabled (`MRC_REDIS_ENABLED=true`):
- **No authentication by default** in development (Docker Compose)
- **Production recommendation:** Enable Redis AUTH and TLS
- **Data serialization:** JSON-first with pickle fallback — be aware of pickle deserialization risks in shared environments
- **Graceful degradation:** If Redis becomes unavailable, the app falls back to in-memory cache — no data exposure

---

## 9. Container & Infrastructure Security

### Dockerfile Security Measures

**File:** `Dockerfile`

| Measure | Implementation | Why |
|---------|---------------|-----|
| **Slim base image** | `FROM python:3.11-slim` | Minimal attack surface - fewer pre-installed packages means fewer potential vulnerabilities |
| **Non-root user** | `RUN useradd -m -u 1000 appuser` + `USER appuser` | Limits damage if the container is compromised. An attacker gains `appuser` privileges, not root. |
| **No cache** | `pip install --no-cache-dir` | Reduces image size and removes cached package files that could leak information |
| **Clean apt cache** | `rm -rf /var/lib/apt/lists/*` | Removes package manager metadata, reducing attack surface |
| **Health check** | `HEALTHCHECK` directive | Enables orchestrator (Docker/K8s) to detect and restart unhealthy containers |
| **Explicit port** | `EXPOSE 8000` | Documents the expected network interface; only one port exposed |

### Docker Compose Security

**File:** `docker-compose.yml`

| Measure | Implementation |
|---------|---------------|
| **Secrets via env vars** | `MRC_API_KEY=${MRC_API_KEY}` - Loaded from host environment, not hardcoded |
| **Volume mounts for data** | Database, PDFs, and logs are on volumes, not inside the container |
| **Restart policy** | `restart: unless-stopped` - Auto-recovery from crashes |
| **Health checks** | HTTP health check with interval, timeout, retries, and start period |
| **Isolated networks** | Services communicate via Docker's internal network |

---

## 10. Logging, Monitoring & Audit Trail

### Structured JSON Logging

**File:** `app/logging_utils.py`

All log entries in the file handler are formatted as JSON, making them parseable by log aggregation systems (ELK, Datadog, Splunk):

```json
{
    "timestamp": "2026-02-04T10:30:00.000000",
    "level": "WARNING",
    "logger": "monster_resort",
    "message": "Invalid API key attempt (received: 6f2b8e3a...)",
    "module": "security",
    "function": "api_key_auth_enhanced",
    "line": 300
}
```

### Log Rotation

| Log File | Max Size | Backups | Content |
|----------|----------|---------|---------|
| `monster_resort.log` | 10 MB | 5 | All log levels |
| `monster_resort_errors.log` | 10 MB | 5 | ERROR and above only |

### Prometheus Metrics

**File:** `app/monitoring.py`

Security-relevant metrics tracked:

| Metric | Type | Labels | Security Use |
|--------|------|--------|-------------|
| `mrc_http_requests_total` | Counter | method, path, status | Detect unusual traffic patterns, brute-force attempts (spike in 401s) |
| `mrc_http_request_latency_seconds` | Histogram | path | Detect DoS (latency spike), timing attacks |
| `mrc_errors_total` | Counter | error_type | Detect attack patterns (spike in ValidationError) |
| `mrc_bookings_total` | Counter | hotel | Detect fraudulent booking patterns |
| `mrc_ai_tokens_total` | Counter | model | Detect prompt injection / token exhaustion attacks |
| `mrc_active_sessions` | Gauge | - | Detect session fixation / flooding |

### Security Event Logging

The following security-relevant events are explicitly logged:

| Event | Log Level | Location |
|-------|-----------|----------|
| Missing Authorization header | WARNING | security.py:283 |
| Invalid Authorization format | WARNING | security.py:290 |
| Invalid API key attempt | WARNING | security.py:300 |
| Successful API key validation | DEBUG | security.py:303 |
| Expired API key used | WARNING | security.py:249 |
| Inactive/revoked key used | WARNING | security.py:253 |
| API key created | INFO | security.py:230 |
| SQL injection attempt | ERROR (via ValidationError) | validation.py:45 |
| XSS attempt | ERROR (via ValidationError) | validation.py:57 |
| Database transaction failure | ERROR | database.py:83 |

---

## 11. CI/CD Security

**File:** `.github/workflows/ci.yml`

### Pipeline Steps

```
Push to main / PR to main
         │
         ▼
┌──────────────────┐
│ 1. Checkout Code │
└────────┬─────────┘
         ▼
┌──────────────────┐
│ 2. Setup Python  │ ← Pinned to 3.11
│    3.11          │
└────────┬─────────┘
         ▼
┌──────────────────┐
│ 3. Install Deps  │
└────────┬─────────┘
         ▼
┌──────────────────┐
│ 4. Lint (flake8) │ ← Catches code quality issues
└────────┬─────────┘
         ▼
┌──────────────────┐
│ 5. Run Tests     │ ← Isolated environment (test DB, dummy keys)
│    pytest --cov  │
└────────┬─────────┘
         ▼
┌──────────────────┐
│ 6. Upload        │
│    Coverage      │
└──────────────────┘
```

### CI Environment Isolation

```yaml
env:
  MRC_ENVIRONMENT: test
  MRC_DATABASE_URL: sqlite:///./test_ci.db    # Isolated test database
  MRC_OPENAI_API_KEY: dummy                    # No real API calls
  MRC_API_KEY: dummy                           # No real auth
```

Tests run against a fresh SQLite database with dummy credentials, ensuring no production data is accessed during CI.

---

## 12. Security Testing

**File:** `tests/test_api_endpoints.py`

### SQL Injection Tests (test_api_endpoints.py:48-63)

```python
def test_sql_injection_prevention(client):
    malicious_inputs = [
        "'; DROP TABLE bookings; --",
        "1' OR '1'='1",
        "admin'--",
        "1'; DELETE FROM sessions; --",
    ]
    for malicious in malicious_inputs:
        response = client.post("/chat", json={"message": malicious})
        assert response.status_code in [200, 400]
        if response.status_code == 200:
            # Verify database integrity is maintained
            health = client.get("/health")
            assert health.status_code == 200
```

### XSS Prevention Tests (test_api_endpoints.py:66-76)

```python
def test_xss_prevention(client):
    xss_inputs = [
        "<script>alert('xss')</script>",
        "<img src=x onerror=alert('xss')>",
        "javascript:alert('xss')",
    ]
    for xss in xss_inputs:
        response = client.post("/chat", json={"message": xss})
        assert response.status_code in [200, 400]
```

### Rate Limiting Tests (test_api_endpoints.py:78-88)

```python
def test_rate_limiting(client):
    for i in range(70):  # Over the 60/min limit
        response = client.post("/chat", json={"message": f"Test {i}"})
        if i < 60:
            assert response.status_code in [200, 201]
        else:
            assert response.status_code == 429  # Rate limited
```

---

## 13. Threat Model & OWASP Mapping

### OWASP Top 10 (2021) Coverage

| # | OWASP Category | Status | Implementation |
|---|---------------|--------|----------------|
| A01 | **Broken Access Control** | Mitigated | JWT + API Key auth on all protected routes. `Depends(jwt_or_api_key)` enforced at the route level. |
| A02 | **Cryptographic Failures** | Mitigated | bcrypt for passwords, SHA-256 for API keys, HS256 for JWT. No plaintext secrets stored. |
| A03 | **Injection** | Mitigated | Parameterised SQL queries, input sanitisation (bleach), regex pattern detection for SQL/XSS. |
| A04 | **Insecure Design** | Mitigated | Defence-in-depth architecture, fail-closed auth, Pydantic validation. |
| A05 | **Security Misconfiguration** | Mitigated | Startup validators reject weak secrets. Production requires explicit, strong API keys. Non-root Docker. |
| A06 | **Vulnerable Components** | Partial | Dependencies pinned in `requirements.txt`. No automated dependency scanning (Dependabot/Snyk). |
| A07 | **Auth Failures** | Mitigated | bcrypt password hashing, short-lived JWTs (30 min), API key expiration (90 days), rate limiting. |
| A08 | **Software & Data Integrity** | Partial | CI/CD runs linting and tests. No artifact signing or SBOM generation. |
| A09 | **Logging & Monitoring Failures** | Mitigated | Structured JSON logging, Prometheus metrics, error-specific log files, security event logging. |
| A10 | **SSRF** | N/A | The application does not make user-controlled outbound requests. |

### LLM-Specific Threats (OWASP Top 10 for LLMs)

| Threat | Status | Implementation |
|--------|--------|----------------|
| **Prompt Injection** | Partial | System prompt uses clear instruction boundaries ("MANDATORY RULES"). Input validation strips HTML/script tags. Further hardening recommended. |
| **Data Leakage** | Mitigated | RAG context is scoped to the knowledge base. No user PII is included in prompts beyond the current session. |
| **Token Exhaustion** | Monitored | `mrc_ai_tokens_total` Prometheus counter tracks token usage per model. Rate limiting caps requests at 60/min. |
| **Model Denial of Service** | Mitigated | Rate limiting + input length cap (5000 chars) prevent excessive LLM calls. |

---

## 14. Known Limitations & Remediation Plan

### Priority 1 - Critical

| Issue | Risk | Remediation |
|-------|------|-------------|
| **Hardcoded test API key in `auth_mixins.py:27`** | Bypass authentication by using the known key `6f2b8e3a...` | Remove the hardcoded key comparison. Rely solely on `settings.api_key`. |
| **In-memory user store (`users_db.py`)** | No persistent user management, no password change, no account lockout | Migrate to database-backed user store with account lockout after N failed attempts. |
| **No HTTPS enforcement** | Traffic can be intercepted in transit | Deploy behind a reverse proxy (nginx/Caddy) with TLS termination, or add `--ssl-keyfile` to Uvicorn. |

### Priority 2 - High

| Issue | Risk | Remediation |
|-------|------|-------------|
| **No dependency vulnerability scanning** | Known CVEs in dependencies go undetected | Add Dependabot or Snyk to CI pipeline. |
| **No CORS configuration** | Potential for cross-origin attacks if frontend is on a different domain | Add FastAPI `CORSMiddleware` with explicit allowed origins. |
| **Grafana default admin password** | `GF_SECURITY_ADMIN_PASSWORD=admin` in docker-compose.yml | Change to a strong password loaded from environment variable. |
| **`/metrics` endpoint is unauthenticated** | Prometheus metrics are publicly accessible | Add authentication or restrict to internal network. |

### Priority 3 - Medium

| Issue | Risk | Remediation |
|-------|------|-------------|
| **No request ID propagation** | Difficult to trace a single request across logs | Add `X-Request-ID` header middleware with OpenTelemetry. |
| **BM25 index not persisted** | Rebuilt on every restart (performance, not security) | Pickle the BM25 index on shutdown, reload on startup. |
| **No API versioning** | Breaking changes could affect integrations | Add `/v1/` prefix to all routes. |
| **Broad `except Exception` blocks** | May swallow security-relevant errors | Replace with specific exception types. |

---

## 15. Security Checklist for Deployment

Use this checklist before deploying to any environment:

### Pre-Deployment

- [ ] **Secrets**: Generate new `MRC_JWT_SECRET_KEY` (min 32 chars): `python -c "import secrets; print(secrets.token_urlsafe(32))"`
- [ ] **Secrets**: Generate new `MRC_API_KEY` (min 32 chars): `python -c "import secrets; print(secrets.token_urlsafe(32))"`
- [ ] **Secrets**: Verify `MRC_OPENAI_API_KEY` is set and valid
- [ ] **Secrets**: Verify `MRC_ANTHROPIC_API_KEY` is set if Anthropic fallback is enabled
- [ ] **Secrets**: For AWS deployments, verify all `MRC_` secrets are stored in AWS Secrets Manager (not in task definitions or environment files)
- [ ] **Secrets**: Ensure `.env` is NOT committed to git (`git status` check)
- [ ] **Hardcoded keys**: Remove test key from `auth_mixins.py:27`
- [ ] **Environment**: Set `MRC_ENVIRONMENT=production`
- [ ] **Grafana**: Change default admin password in `docker-compose.yml`
- [ ] **Dependencies**: Run `pip audit` or Snyk to check for known vulnerabilities

### Infrastructure

- [ ] **TLS**: Deploy behind a reverse proxy with HTTPS (nginx/Caddy/ALB)
- [ ] **Firewall**: Restrict `/metrics` endpoint to internal network
- [ ] **Firewall**: Restrict database port (if using external DB)
- [ ] **Docker**: Verify container runs as non-root (`docker exec <container> whoami`)
- [ ] **AWS**: Verify ECS task roles follow least-privilege (only ECR pull, CloudWatch logs, Secrets Manager read)
- [ ] **AWS**: Verify CloudWatch log groups have appropriate retention policies
- [ ] **Backups**: Verify database backup schedule is active

### Monitoring

- [ ] **Prometheus**: Verify scraping is active at `/metrics`
- [ ] **Grafana**: Set up alerts for:
  - Error rate > 5% over 5 minutes
  - Latency p99 > 5 seconds
  - 401 status code spike (>20 in 1 minute)
  - Rate limit breaches (429 responses)
- [ ] **Logs**: Verify JSON logs are being shipped to aggregation service
- [ ] **Error log**: Verify `monster_resort_errors.log` is being monitored

### Post-Deployment

- [ ] **Smoke test**: `curl https://your-domain/health` returns `{"ok": true}`
- [ ] **Auth test**: `curl https://your-domain/chat` without auth returns `401`
- [ ] **Auth test**: `curl -H "Authorization: Bearer <key>" https://your-domain/chat` with valid key returns `200`
- [ ] **Rate limit test**: Verify 429 response after 60 rapid requests
- [ ] **SQL injection test**: Send `'; DROP TABLE bookings; --` and verify database integrity

---

*This document is maintained by the Monster Resort Engineering team. For security incidents, contact the on-call security engineer immediately.*

*Document Version: 1.0 | Classification: Internal - Engineering | Review Cycle: Quarterly*
