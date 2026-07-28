"""JWT verification for Supabase-issued access tokens.

The backend NEVER trusts a client-supplied user id. Every protected route
depends on `get_current_user`, which verifies the token's signature and
reads the user id out of the verified claims — that id is what gets
written to `scans.user_id`, so a forged request can't write or read
another user's history (RLS is the second, independent layer of defense
on top of this).

Newer Supabase projects sign tokens asymmetrically (ES256/RS256) and
publish verification keys via JWKS; older projects use a single shared
HS256 secret. We support both — but the algorithm used to verify is NEVER
taken from the token's own (attacker-controlled) header. For the JWKS path
we use the `alg` from the matched JWK itself (server-controlled key
metadata, looked up by `kid`), and the legacy path is only reachable when
there's no `kid` at all, with a configured, non-empty secret required —
otherwise we fail closed. This closes the classic JWT "algorithm
confusion" attack (forge alg=HS256, sign with an empty/guessed secret).
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.core.config import get_settings
from app.core.jwks import get_key_for_kid

bearer_scheme = HTTPBearer(auto_error=False)


def _decode(token: str) -> dict:
    unverified_header = jwt.get_unverified_header(token)
    kid = unverified_header.get("kid")

    if kid:
        jwk = get_key_for_kid(kid)
        if jwk is None:
            raise JWTError(f"No matching JWKS key for kid={kid}")
        # Algorithm comes from the matched JWK's own metadata, never from
        # the token's header — the token cannot pick its own verification algorithm.
        jwk_alg = jwk.get("alg")
        if jwk_alg not in {"ES256", "RS256"}:
            raise JWTError(f"Unsupported or missing JWK algorithm: {jwk_alg}")
        return jwt.decode(token, jwk, algorithms=[jwk_alg], audience="authenticated")

    settings = get_settings()
    if not settings.supabase_jwt_secret:
        # No kid (not a JWKS-signed token) and no legacy secret configured —
        # fail closed rather than verifying against an empty/absent key.
        raise JWTError("No JWKS kid on token and no legacy JWT secret configured")

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
