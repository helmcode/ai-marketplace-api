from jose import jwt, JWTError
from cryptography.fernet import Fernet
import httpx
import base64

from app.config import get_settings
from app.core.exceptions import UnauthorizedError

settings = get_settings()

_jwks_cache: dict | None = None


async def get_jwks() -> dict:
    """Fetch Auth0 JWKS with caching."""
    global _jwks_cache
    if _jwks_cache is not None:
        return _jwks_cache

    if not settings.auth0_domain:
        raise UnauthorizedError("Auth0 not configured")

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://{settings.auth0_domain}/.well-known/jwks.json"
        )
        response.raise_for_status()
        _jwks_cache = response.json()
        return _jwks_cache


def find_rsa_key(jwks: dict, kid: str) -> dict:
    """Find the RSA key matching the key ID."""
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return {
                "kty": key["kty"],
                "kid": key["kid"],
                "use": key["use"],
                "n": key["n"],
                "e": key["e"]
            }
    raise UnauthorizedError("Unable to find appropriate key")


async def verify_jwt(token: str) -> dict:
    """Verify Auth0 JWT token and return payload."""
    try:
        unverified_header = jwt.get_unverified_header(token)
        jwks = await get_jwks()
        rsa_key = find_rsa_key(jwks, unverified_header["kid"])

        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=["RS256"],
            audience=settings.auth0_audience,
            issuer=f"https://{settings.auth0_domain}/"
        )
        return payload
    except JWTError as e:
        raise UnauthorizedError(f"Invalid token: {str(e)}")


def get_fernet() -> Fernet:
    """Get Fernet instance for encryption/decryption."""
    key = settings.encryption_key
    if not key:
        raise ValueError("ENCRYPTION_KEY not configured")
    if len(key) != 44:
        key = base64.urlsafe_b64encode(key.encode()[:32].ljust(32, b'\0')).decode()
    return Fernet(key.encode())


def encrypt_value(value: str) -> str:
    """Encrypt a sensitive value."""
    f = get_fernet()
    return f.encrypt(value.encode()).decode()


def decrypt_value(encrypted: str) -> str:
    """Decrypt a sensitive value."""
    f = get_fernet()
    return f.decrypt(encrypted.encode()).decode()
