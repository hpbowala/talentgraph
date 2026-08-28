"""Cognito gating: header parsing, Cognito's verdict, and the FastAPI gate.

The gate is default-deny, so the cases that matter most are the ones where a
request should NOT get through.
"""

import pytest
from botocore.exceptions import ClientError
from fastapi.testclient import TestClient

from app import auth
from app.api.server import app


class FakeCognito:
    """Stands in for the cognito-idp client: accepts one token, rejects the rest."""

    def __init__(self, good_token: str = "good-token", code: str = "NotAuthorizedException"):
        self.good_token = good_token
        self.code = code
        self.calls: list[str] = []

    def get_user(self, AccessToken: str) -> dict:  # noqa: N803 — boto3's parameter name
        self.calls.append(AccessToken)
        if AccessToken == self.good_token:
            return {"Username": "operator"}
        raise ClientError({"Error": {"Code": self.code, "Message": "nope"}}, "GetUser")


@pytest.fixture()
def cognito(monkeypatch) -> FakeCognito:
    """Enable auth with a stubbed Cognito, and restore the unset default after."""
    fake = FakeCognito()
    monkeypatch.setattr(auth, "USER_POOL_ID", "us-east-1_test")
    monkeypatch.setattr(auth, "_client", fake)
    return fake


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


# ---- header parsing ---------------------------------------------------------


@pytest.mark.parametrize("header", [None, "", "Basic abc", "Bearer", "Bearer   ", "token abc"])
def test_bearer_token_rejects_unusable_headers(header):
    with pytest.raises(auth.AuthError):
        auth.bearer_token(header)


def test_bearer_token_is_case_insensitive_and_strips():
    assert auth.bearer_token("bearer  abc  ") == "abc"


# ---- token verification -----------------------------------------------------


def test_verify_access_token_returns_username(cognito):
    assert auth.verify_access_token("good-token") == "operator"
    assert cognito.calls == ["good-token"]


@pytest.mark.parametrize(
    "code", ["NotAuthorizedException", "UserNotFoundException", "InvalidParameterException"]
)
def test_verify_access_token_maps_rejection_to_auth_error(monkeypatch, code):
    monkeypatch.setattr(auth, "USER_POOL_ID", "us-east-1_test")
    monkeypatch.setattr(auth, "_client", FakeCognito(code=code))
    with pytest.raises(auth.AuthError):
        auth.verify_access_token("bad-token")


def test_verify_access_token_reraises_unexpected_errors(monkeypatch):
    """An outage must surface as a 500, not as 'please sign in again'."""
    monkeypatch.setattr(auth, "USER_POOL_ID", "us-east-1_test")
    monkeypatch.setattr(auth, "_client", FakeCognito(code="ServiceUnavailable"))
    with pytest.raises(ClientError):
        auth.verify_access_token("bad-token")


def test_authenticate_is_a_no_op_when_no_pool_is_configured(monkeypatch):
    monkeypatch.setattr(auth, "USER_POOL_ID", "")
    assert auth.authenticate(None) is None


# ---- the FastAPI gate -------------------------------------------------------


PROTECTED = [
    ("get", "/conversations"),
    ("get", "/conversations/abc"),
    ("delete", "/conversations/abc"),
    ("get", "/cvs"),
    ("post", "/cvs"),
    ("delete", "/cvs/x.pdf"),
    ("post", "/chat"),
]


@pytest.mark.parametrize(("method", "path"), PROTECTED)
def test_routes_reject_requests_without_a_token(client, cognito, method, path):
    assert getattr(client, method)(path).status_code == 401


@pytest.mark.parametrize(("method", "path"), PROTECTED)
def test_routes_reject_an_invalid_token(client, cognito, method, path):
    res = getattr(client, method)(path, headers={"Authorization": "Bearer wrong"})
    assert res.status_code == 401


def test_health_stays_public(client, cognito):
    assert client.get("/health").status_code == 200
    assert cognito.calls == []


def test_a_valid_token_reaches_the_route(client, cognito):
    res = client.get("/conversations", headers={"Authorization": "Bearer good-token"})
    assert res.status_code == 200
    assert cognito.calls == ["good-token"]


def test_routes_are_open_when_no_pool_is_configured(client, monkeypatch):
    """Local dev keeps working without AWS — the point of the config switch."""
    monkeypatch.setattr(auth, "USER_POOL_ID", "")
    assert client.get("/conversations").status_code == 200
