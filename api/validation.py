"""
Input hardening for uploaded files. The API and UI both call `validate_and_decode`
before any text ever reaches the model.

Checks: extension, size limit, empty file, safe decode, control-character stripping.
"""
import os

MAX_FILE_SIZE_MB = float(os.getenv("MAX_FILE_SIZE_MB", "2"))
ALLOWED_EXTENSIONS = (".txt",)


class InputValidationError(ValueError):
    """Raised for any rejected upload; the API maps it to HTTP 400."""


def validate_and_decode(filename: str, raw: bytes) -> str:
    """Validate an uploaded file and return clean, decoded text.

    Raises InputValidationError with a user-facing message on any problem.
    """
    if not filename or not filename.lower().endswith(ALLOWED_EXTENSIONS):
        raise InputValidationError("Only .txt files are accepted.")

    max_bytes = MAX_FILE_SIZE_MB * 1024 * 1024
    if len(raw) > max_bytes:
        raise InputValidationError(f"File too large — limit is {MAX_FILE_SIZE_MB:g} MB.")

    if not raw.strip():
        raise InputValidationError("File is empty.")

    # Never trust the bytes are valid UTF-8; replace undecodable bytes rather than crash.
    text = raw.decode("utf-8", errors="replace")

    # Drop control characters (e.g. null bytes) but keep tab / newline / carriage return.
    text = "".join(ch for ch in text if ch in "\t\n\r" or ord(ch) >= 32)

    if not text.strip():
        raise InputValidationError("File contains no readable text.")

    return text
