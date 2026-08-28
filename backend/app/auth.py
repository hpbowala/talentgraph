"""Cognito access-token verification, shared by both API adapters.

Auth is enabled by configuration rather than by a flag: with COGNITO_USER_POOL_ID
unset — the local default — every request is allowed through, so `make serve`
still needs no AWS account. The deployed stack always sets it, so the public
CloudFront URL is always gated.

Tokens are checked by handing them to Cognito's GetUser API rather than by
verifying the JWT signature locally. That needs no crypto dependency and no JWKS
cache, which matters because the Lambda proxy ships as a plain asset directory
with no bundling step; at single-operator scale the extra round trip is not
worth a build pipeline to avoid.
"""

import os

from dotenv import load_dotenv

# Loaded here, not just in app.llm.provider: this module is imported before it
# (see app/api/server.py), so without this the pool id in backend/.env would be
# read before the file had been parsed — and the gate would silently stay open.
# Existing environment variables win, so the Makefile and the shell still override.
load_dotenv()

USER_POOL_ID = os.getenv("COGNITO_USER_POOL_ID", "")

_client = None


class AuthError(Exception):
    """Raised when a request carries no usable access token."""


def auth_enabled() -> bool:
    return bool(USER_POOL_ID)


def _cognito():
    import boto3  # noqa: PLC0415 — only needed when auth is configured

    global _client
    if _client is None:
        _client = boto3.client("cognito-idp")
    return _client


def bearer_token(header: str | None) -> str:
    """Pull the token out of an `Authorization: Bearer <token>` header."""
    if not header:
        raise AuthError("Missing Authorization header")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise AuthError("Authorization header must be 'Bearer <token>'")
    return token.strip()


def verify_access_token(token: str) -> str:
    """Return the username the token belongs to, or raise AuthError.

    Cognito rejects expired, tampered and revoked tokens itself, so there is no
    signature, issuer or expiry check to duplicate here.
    """
    from botocore.exceptions import ClientError  # noqa: PLC0415

    try:
        return _cognito().get_user(AccessToken=token)["Username"]
    except ClientError as err:
        code = err.response["Error"]["Code"]
        if code in ("NotAuthorizedException", "UserNotFoundException", "InvalidParameterException"):
            raise AuthError("Invalid or expired access token") from err
        raise


def authenticate(header: str | None) -> str | None:
    """Verify an Authorization header. Returns the username, or None when auth
    is not configured; raises AuthError if a configured pool rejects the token."""
    if not auth_enabled():
        return None
    return verify_access_token(bearer_token(header))
