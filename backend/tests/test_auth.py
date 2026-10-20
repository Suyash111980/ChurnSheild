from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient
from jwt.exceptions import PyJWKClientConnectionError

from app.api.dependencies import auth
from app.api.dependencies.datasets import require_owned_dataset
from app.repositories import learner_repository
from app.repositories import dataset_repository
from app.core.config import settings
from app.main import app

ISSUER = "https://unit-test.supabase.co/auth/v1"
SUBJECT = str(uuid4())
DATASET_ID = str(uuid4())


class FakeJwksClient:
    def __init__(self, public_key):
        self.public_key = public_key

    def get_signing_key_from_jwt(self, _token):
        return SimpleNamespace(key=self.public_key)


class FakeProfileQuery:
    def __init__(self, rows):
        self.rows = rows
        self.filters = []

    def table(self, table_name):
        assert table_name == "profiles"
        return self

    def select(self, columns):
        assert columns == "id, role, approval_status"
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def limit(self, count):
        assert count == 1
        return self

    def execute(self):
        return SimpleNamespace(data=self.rows)


class FakeLearnerQuery:
    def table(self, table_name):
        assert table_name == "learners_latest_prediction"
        return self

    def select(self, columns, **kwargs):
        assert columns == "*"
        assert kwargs == {"count": "exact"}
        return self

    def eq(self, _field, _value):
        return self

    def order(self, column, desc=False):
        assert (column, desc) in {
            ("created_at", True),
            ("id", True),
        }
        return self

    def range(self, _first, _last):
        return self

    def execute(self):
        return SimpleNamespace(data=[], count=0)


@pytest.fixture
def signing_keys():
    private_key = ec.generate_private_key(ec.SECP256R1())
    return private_key, private_key.public_key()


@pytest.fixture
def auth_setup(monkeypatch, signing_keys):
    private_key, public_key = signing_keys
    monkeypatch.setattr(settings, "supabase_url", "https://unit-test.supabase.co")
    monkeypatch.setattr(settings, "supabase_jwt_issuer", "")
    monkeypatch.setattr(settings, "supabase_jwt_algorithm", "ES256")
    fake_profile = FakeProfileQuery(
        [{"id": SUBJECT, "role": "admin", "approval_status": "approved"}]
    )
    monkeypatch.setattr(auth, "supabase", fake_profile)
    monkeypatch.setattr(auth, "_jwks_client", lambda _url: FakeJwksClient(public_key))
    return private_key, fake_profile


def make_token(private_key, **overrides):
    now = datetime.now(timezone.utc)
    claims = {
        "sub": SUBJECT,
        "aud": "authenticated",
        "role": "authenticated",
        "iss": ISSUER,
        "iat": now,
        "exp": now + timedelta(minutes=5),
    }
    claims.update(overrides)
    return jwt.encode(
        claims,
        private_key,
        algorithm="ES256",
        headers={"kid": "test-key"},
    )


def credentials(token):
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def test_valid_token_resolves_profile_role(auth_setup):
    private_key, profile_query = auth_setup

    user = auth.get_current_user(credentials(make_token(private_key)))

    assert user == {
        "id": SUBJECT,
        "database_role": "admin",
        "app_role": "admin",
        "approval_status": "approved",
    }
    assert profile_query.filters == [("id", SUBJECT)]


def test_configured_approved_admin_is_master_admin(auth_setup, monkeypatch):
    private_key, _ = auth_setup
    monkeypatch.setattr(settings, "master_admin_user_id", SUBJECT)
    user = auth.get_current_user(credentials(make_token(private_key)))
    assert user["app_role"] == "master_admin"


def test_master_admin_designation_does_not_override_profile_role(auth_setup, monkeypatch):
    private_key, profile_query = auth_setup
    monkeypatch.setattr(settings, "master_admin_user_id", SUBJECT)
    profile_query.rows = [{"id": SUBJECT, "role": "educator", "approval_status": "approved"}]
    with pytest.raises(HTTPException) as error:
        auth.get_current_user(credentials(make_token(private_key)))
    assert error.value.status_code == 403


def test_missing_token_is_unauthorized():
    with pytest.raises(HTTPException) as error:
        auth.get_current_user(None)

    assert error.value.status_code == 401
    assert error.value.headers["WWW-Authenticate"] == "Bearer"


def test_malformed_token_is_unauthorized(auth_setup):
    with pytest.raises(HTTPException) as error:
        auth.get_current_user(credentials("not-a-jwt"))

    assert error.value.status_code == 401


@pytest.mark.parametrize(
    "claims",
    [
        {"exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        {"iss": "https://wrong.example/auth/v1"},
        {"aud": "wrong-audience"},
        {"sub": "not-a-uuid"},
        {"role": "service_role"},
    ],
)
def test_invalid_claims_are_unauthorized(auth_setup, claims):
    private_key, _ = auth_setup

    with pytest.raises(HTTPException) as error:
        auth.get_current_user(credentials(make_token(private_key, **claims)))

    assert error.value.status_code == 401


def test_bad_signature_is_unauthorized(auth_setup):
    private_key, _ = auth_setup
    wrong_key = ec.generate_private_key(ec.SECP256R1())

    with pytest.raises(HTTPException) as error:
        auth.get_current_user(credentials(make_token(wrong_key)))

    assert error.value.status_code == 401


def test_jwks_outage_is_service_unavailable(auth_setup, monkeypatch):
    private_key, _ = auth_setup

    class UnavailableJwks:
        def get_signing_key_from_jwt(self, _token):
            raise PyJWKClientConnectionError("provider unavailable")

    monkeypatch.setattr(auth, "_jwks_client", lambda _url: UnavailableJwks())
    with pytest.raises(HTTPException) as error:
        auth.get_current_user(credentials(make_token(private_key)))

    assert error.value.status_code == 503


def test_jwks_outage_is_503_over_http(auth_setup, monkeypatch):
    private_key, _ = auth_setup

    class UnavailableJwks:
        def get_signing_key_from_jwt(self, _token):
            raise PyJWKClientConnectionError("provider unavailable")

    monkeypatch.setattr(auth, "_jwks_client", lambda _url: UnavailableJwks())
    response = TestClient(app).get(
        f"/api/v1/learners?dataset_id={DATASET_ID}",
        headers={"Authorization": f"Bearer {make_token(private_key)}"},
    )

    assert response.status_code == 503


@pytest.mark.parametrize("database_role", ["educator", "analyst"])
def test_unsupported_database_roles_are_denied(auth_setup, database_role):
    private_key, profile_query = auth_setup
    profile_query.rows = [
        {"id": SUBJECT, "role": database_role, "approval_status": "approved"}
    ]

    with pytest.raises(HTTPException) as error:
        auth.get_current_user(credentials(make_token(private_key)))
    assert error.value.status_code == 403


def test_admin_can_access_learners_over_http(auth_setup, monkeypatch):
    private_key, profile_query = auth_setup
    profile_query.rows = [
        {"id": SUBJECT, "role": "admin", "approval_status": "approved"}
    ]
    monkeypatch.setattr(learner_repository, "supabase", FakeLearnerQuery())

    def owned_dataset(_user=Depends(auth.get_current_user)):
        return {"id": DATASET_ID, "owner_id": SUBJECT, "status": "processed"}

    app.dependency_overrides[require_owned_dataset] = owned_dataset

    response = TestClient(app).get(
        f"/api/v1/learners?dataset_id={DATASET_ID}",
        headers={"Authorization": f"Bearer {make_token(private_key)}"},
    )

    assert response.status_code == 200
    assert response.json()["data"] == []


@pytest.mark.parametrize("database_role", ["educator", "analyst"])
def test_unsupported_database_roles_are_denied_over_http(auth_setup, database_role):
    private_key, profile_query = auth_setup
    profile_query.rows = [{"id": SUBJECT, "role": database_role, "approval_status": "approved"}]
    response = TestClient(app).get(
        f"/api/v1/learners?dataset_id={DATASET_ID}",
        headers={"Authorization": f"Bearer {make_token(private_key)}"},
    )
    assert response.status_code == 403


def test_missing_profile_fails_closed(auth_setup, monkeypatch):
    private_key, profile_query = auth_setup
    profile_query.rows = []

    with pytest.raises(HTTPException) as error:
        auth.get_current_user(credentials(make_token(private_key)))

    assert error.value.status_code == 403


def test_missing_profile_is_forbidden_over_http(auth_setup):
    private_key, profile_query = auth_setup
    profile_query.rows = []

    response = TestClient(app).get(
        f"/api/v1/learners?dataset_id={DATASET_ID}",
        headers={"Authorization": f"Bearer {make_token(private_key)}"},
    )

    assert response.status_code == 403


@pytest.mark.parametrize(
    ("approval_status", "expected_detail"),
    [
        ("pending", "awaiting administrator approval"),
        ("denied", "denied access"),
    ],
)
def test_pending_and_denied_profiles_are_forbidden_over_http(
    auth_setup, approval_status, expected_detail
):
    private_key, profile_query = auth_setup
    profile_query.rows = [
        {"id": SUBJECT, "role": "educator", "approval_status": approval_status}
    ]

    response = TestClient(app).get(
        f"/api/v1/learners?dataset_id={DATASET_ID}",
        headers={"Authorization": f"Bearer {make_token(private_key)}"},
    )

    assert response.status_code == 403
    assert expected_detail in response.json()["detail"]


def test_account_status_endpoint_exposes_only_callers_approval_state(auth_setup):
    private_key, profile_query = auth_setup
    profile_query.rows = [
        {"id": SUBJECT, "role": "analyst", "approval_status": "pending"}
    ]

    response = TestClient(app).get(
        "/api/v1/auth/status",
        headers={"Authorization": f"Bearer {make_token(private_key)}"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": SUBJECT,
        "app_role": None,
        "approval_status": "pending",
    }


def test_unknown_profile_role_fails_closed(auth_setup):
    private_key, profile_query = auth_setup
    profile_query.rows = [
        {
            "id": SUBJECT,
            "role": "unexpected",
            "approval_status": "approved",
        }
    ]

    with pytest.raises(HTTPException) as error:
        auth.get_current_user(credentials(make_token(private_key)))

    assert error.value.status_code == 403


def test_profile_service_outage_is_service_unavailable(auth_setup, monkeypatch):
    private_key, _ = auth_setup

    class BrokenProfileQuery:
        def table(self, _table_name):
            raise RuntimeError("internal database diagnostic")

    monkeypatch.setattr(auth, "supabase", BrokenProfileQuery())
    with pytest.raises(HTTPException) as error:
        auth.get_current_user(credentials(make_token(private_key)))

    assert error.value.status_code == 503
    assert "internal database diagnostic" not in error.value.detail


def test_role_dependency_allows_or_denies_as_configured():
    user = {"id": SUBJECT, "database_role": "admin", "app_role": "admin"}
    assert auth.require_roles("admin")(current_user=user) == user
    with pytest.raises(HTTPException) as error:
        auth.require_roles("master_admin")(current_user=user)
    assert error.value.status_code == 403
    for unsupported_role in ("retention_manager", "data_analyst"):
        with pytest.raises(ValueError):
            auth.require_roles(unsupported_role)


def test_missing_supabase_configuration_is_unavailable(auth_setup, monkeypatch):
    private_key, _ = auth_setup
    monkeypatch.setattr(settings, "supabase_url", "")

    with pytest.raises(HTTPException) as error:
        auth.get_current_user(credentials(make_token(private_key)))

    assert error.value.status_code == 503


@pytest.mark.parametrize(
    ("approval_status", "expected_detail"),
    [
        ("pending", "awaiting administrator approval"),
        ("denied", "denied access"),
        (None, "requires administrator review"),
    ],
)
def test_unapproved_profiles_are_forbidden(auth_setup, approval_status, expected_detail):
    private_key, profile_query = auth_setup
    profile_query.rows = [
        {"id": SUBJECT, "role": "educator", "approval_status": approval_status}
    ]

    with pytest.raises(HTTPException) as error:
        auth.get_current_user(credentials(make_token(private_key)))

    assert error.value.status_code == 403
    assert expected_detail in error.value.detail


def test_approval_status_endpoint_returns_own_unapproved_status(auth_setup):
    private_key, profile_query = auth_setup
    profile_query.rows = [
        {"id": SUBJECT, "role": "educator", "approval_status": "pending"}
    ]

    profile = auth.get_authenticated_profile(credentials(make_token(private_key)))

    assert profile["approval_status"] == "pending"
    with pytest.raises(HTTPException) as error:
        auth.get_current_user(credentials(make_token(private_key)))
    assert error.value.status_code == 403


@pytest.mark.parametrize(("database_role", "expected_status"), [("admin", 503), ("educator", 403), ("analyst", 403)])
def test_only_admin_can_reach_dataset_upload_operation(
    auth_setup, monkeypatch, database_role, expected_status
):
    private_key, profile_query = auth_setup
    profile_query.rows = [
        {"id": SUBJECT, "role": database_role, "approval_status": "approved"}
    ]
    # Admin passes authorization but stops at the intentionally unconfigured
    # database boundary; other roles are forbidden before that boundary.
    monkeypatch.setattr(dataset_repository, "supabase", None)
    response = TestClient(app).post(
        "/api/v1/datasets/upload",
        headers={"Authorization": f"Bearer {make_token(private_key)}"},
        files={"file": ("input.csv", b"data", "text/csv")},
    )
    assert response.status_code == expected_status
