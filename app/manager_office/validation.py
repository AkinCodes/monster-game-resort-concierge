import re
from datetime import datetime, timedelta
from email_validator import validate_email as _validate_email, EmailNotValidError
import bleach
import re
from datetime import datetime, timedelta
from typing import Optional
import bleach
from app.cctv.logging_utils import ValidationError


def sanitize_html(text: str) -> str:
    """Remove all HTML tags"""
    return bleach.clean(text, tags=[], strip=True)


def validate_message(message) -> str:
    """Validate and sanitize user message"""
    if message is None:
        raise ValidationError("Message cannot be None")
    if isinstance(message, dict):
        if "text" not in message:
            raise ValidationError("Message dict must have 'text' key")
        user_text = message["text"]
    else:
        user_text = str(message)
    user_text = user_text.strip()
    if not user_text:
        raise ValidationError("Message cannot be empty")
    if len(user_text) > 5000:
        raise ValidationError("Message too long (max 5000 characters)")
    # SQL injection
    dangerous_sql = [
        "DROP TABLE",
        "DELETE FROM",
        "INSERT INTO",
        "UPDATE ",
        "--",
        "/*",
        "*/",
        "';",
        "OR 1=1",
    ]
    if any(pattern in user_text.upper() for pattern in dangerous_sql):
        raise ValidationError("Potentially malicious SQL detected")
    # XSS prevention
    xss_patterns = [
        r"<script[^>]*>.*?</script>",
        r"javascript:",
        r"on\w+\s*=",  # Event handlers
        r"<iframe",
        r"<object",
        r"<embed",
    ]
    for pattern in xss_patterns:
        if re.search(pattern, user_text, re.IGNORECASE):
            raise ValidationError("Potentially malicious HTML detected")
    # Sanitize HTML
    user_text = sanitize_html(user_text)
    return user_text


def validate_guest_name(name: str) -> str:
    """Validate guest name"""
    if not name or len(name) < 2:
        raise ValidationError("Guest name too short (minimum 2 characters)")
    if len(name) > 100:
        raise ValidationError("Guest name too long (maximum 100 characters)")
    # Allow letters, spaces, hyphens, apostrophes
    if not re.match(r"^[a-zA-Z\s\-'.]+$", name):
        raise ValidationError("Guest name contains invalid characters")
    return name.strip()


def validate_date(date_str: str, field_name: str = "Date") -> str:
    """Validate date format and range"""
    try:
        date = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        raise ValidationError(f"{field_name} must be in YYYY-MM-DD format")
    # Check not too far in past
    if date < datetime.now() - timedelta(days=1):
        raise ValidationError(f"{field_name} cannot be in the past")
    # Check not too far in future (1 year)
    if date > datetime.now() + timedelta(days=365):
        raise ValidationError(f"{field_name} cannot be more than 1 year in the future")
    return date_str


def validate_booking(
    guest_name: str, room_type: str, check_in: str, check_out: str, guests: int
) -> dict:
    """Validate complete booking request"""
    errors = []
    # Validate guest name
    try:
        guest_name = validate_guest_name(guest_name)
    except ValidationError as e:
        errors.append(str(e))
    # Validate room type
    valid_rooms = ["Standard Lair", "Deluxe Crypt", "Crypt Suite", "Penthouse Tomb"]
    if room_type not in valid_rooms:
        errors.append(f"Invalid room type. Must be one of: {', '.join(valid_rooms)}")
    # Validate dates
    try:
        check_in = validate_date(check_in, "Check-in date")
        check_out = validate_date(check_out, "Check-out date")
        # Check check_out after check_in
        ci = datetime.strptime(check_in, "%Y-%m-%d")
        co = datetime.strptime(check_out, "%Y-%m-%d")
        if co <= ci:
            errors.append("Check-out must be after check-in")
        if (co - ci).days > 30:
            errors.append("Maximum stay is 30 nights")
    except ValidationError as e:
        errors.append(str(e))
    # Validate guests
    if not isinstance(guests, int) or guests < 1:
        errors.append("Number of guests must be at least 1")
    if guests > 10:
        errors.append("Maximum 10 guests per room")
    if errors:
        raise ValidationError("; ".join(errors))
    return {
        "guest_name": guest_name,
        "room_type": room_type,
        "check_in": check_in,
        "check_out": check_out,
        "guests": guests,
    }


def validate_email(email: str) -> str:
    """Validate email format"""
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if not re.match(pattern, email):
        raise ValidationError("Invalid email format")
    return email.lower()


def validate_email(email: str) -> str:
    try:
        v = _validate_email(email)
        return v.email.lower()
    except EmailNotValidError as e:
        raise ValidationError(f"Invalid email format: {e}")
