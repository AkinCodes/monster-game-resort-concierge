import os
from dotenv import load_dotenv

# Load .env file BEFORE reading any environment variables
load_dotenv()

# No default value - forces explicit configuration
SECRET_KEY = os.getenv("MRC_JWT_SECRET_KEY")

if not SECRET_KEY:
    raise ValueError(
        "MRC_JWT_SECRET_KEY environment variable is required. "
        "Add it to your .env file with a strong random value (min 32 chars). "
        "Generate one with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
    )

# Reject weak/default secrets at startup
if SECRET_KEY == "changeme-super-secret-key":
    raise ValueError(
        "JWT secret is still set to the default placeholder value. "
        "Generate a strong secret with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
    )

if len(SECRET_KEY) < 32:
    raise ValueError(
        f"JWT secret must be at least 32 characters for security. "
        f"Current length: {len(SECRET_KEY)}. "
        "Generate a strong secret with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
    )

ALGORITHM = "HS256"
