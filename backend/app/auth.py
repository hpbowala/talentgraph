"""Cognito access-token verification, shared by both API adapters.

With COGNITO_USER_POOL_ID unset — the local default — every request is allowed
through. Tokens are checked via Cognito's GetUser rather than by verifying the
JWT locally, which keeps the Lambda proxy free of a bundling step.
"""

import os

from dotenv import load_dotenv

# Imported before app.llm.provider, so the pool id would otherwise be read
# before backend/.env was parsed and the gate would silently stay open.
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

    Cognito rejects expired, tampered and revoked tokens itself.
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
