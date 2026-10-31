from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException
from app.core.config import settings

def cipher() -> Fernet:
    if not settings.github_token_encryption_key:
        raise HTTPException(status_code=503, detail="GITHUB_TOKEN_ENCRYPTION_KEY is not configured")
    try:
        return Fernet(settings.github_token_encryption_key.encode("utf-8"))
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=503, detail="GITHUB_TOKEN_ENCRYPTION_KEY must be a valid Fernet key") from exc

def encrypt_token(token: str) -> str:
    return cipher().encrypt(token.encode("utf-8")).decode("ascii")

def decrypt_token(value: str) -> str:
    try:
        return cipher().decrypt(value.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, UnicodeError) as exc:
        raise HTTPException(status_code=503, detail="Stored GitHub credential cannot be decrypted; verify the encryption key") from exc
