"""JWT verification for Supabase-issued access tokens.

The backend NEVER trusts a client-supplied user id. Every protected route
depends on `get_current_user`, which verifies the token's signature and
reads the user id out of the verified claims — that id is what gets
written to `scans.user_id`, so a forged request can't write or read
another user's history (RLS is the second, independent layer of defense
on top of this).

Newer Supabase projects sign tokens asymmetrically (ES256/RS256) and
publish verification keys via JWKS; older projects use a single shared
HS256 secret. We support both — try JWKS first (by `kid`), fall back to
the shared secret if the project is on the legacy scheme.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.core.config import get_settings
from app.core.jwks import get_key_for_kid

bearer_scheme = HTTPBearer(auto_error=False)


def _decode(token: str) -> dict:
    unverified_header = jwt.get_unverified_header(token)
    alg = unverified_header.get("alg", "HS256")
    kid = unverified_header.get("kid")

    if alg != "HS256" and kid:
        jwk = get_key_for_kid(kid)
        if jwk is None:
            raise JWTError(f"No matching JWKS key for kid={kid}")
        return jwt.decode(token, jwk, algorithms=[alg], audience="authenticated")

    settings = get_settings()
    return jwt.decode(
        token, settings.supabase_jwt_secret, algorithms=["HS256"], audience="authenticated"
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> str:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )

    try:
        payload = _decode(credentials.credentials)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject claim",
        )
    return user_id
