"""Unit tests for fail-closed Supabase JWT validation."""

import time
from collections.abc import Mapping
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt import PyJWK, PyJWKClientError
from jwt.algorithms import RSAAlgorithm

from trpg_mcp.auth import SupabaseTokenVerifier

ISSUER = "https://project.supabase.co/auth/v1"
AUDIENCE = "https://trpg.example.com/mcp"
CLIENT_ID = "oauth-client-id"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def signing_material() -> tuple[rsa.RSAPrivateKey, PyJWK]:
    private_key = rsa.generate_private_key(public_exponent=65_537, key_size=2048)
    jwk = RSAAlgorithm.to_jwk(private_key.public_key(), as_dict=True)
    jwk.update({"alg": "RS256", "kid": "test-key", "use": "sig"})
    return private_key, PyJWK.from_dict(jwk)


class StaticSigningKeyProvider:
    def __init__(self, signing_key: PyJWK) -> None:
        self.signing_key = signing_key

    def get_signing_key_from_jwt(self, token: str) -> PyJWK:
        return self.signing_key


class FailingSigningKeyProvider:
    def get_signing_key_from_jwt(self, token: str) -> PyJWK:
        raise PyJWKClientError("unknown signing key")


def _claims(**overrides: object) -> dict[str, object]:
    now = int(time.time())
    claims: dict[str, object] = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "sub": str(uuid4()),
        "user_id": None,
        "role": "authenticated",
        "client_id": CLIENT_ID,
        "iat": now,
        "exp": now + 300,
        "scope": "openid email email",
    }
    claims.update(overrides)
    if claims["user_id"] is None:
        claims["user_id"] = claims["sub"]
    return claims


def _encode(
    private_key: rsa.RSAPrivateKey,
    claims: Mapping[str, object],
    *,
    headers: Mapping[str, object] | None = None,
) -> str:
    return jwt.encode(
        dict(claims),
        private_key,
        algorithm="RS256",
        headers=dict(headers or {"kid": "test-key"}),
    )


def _verifier(signing_key: PyJWK) -> SupabaseTokenVerifier:
    return SupabaseTokenVerifier(
        issuer=ISSUER,
        audience=AUDIENCE,
        jwks_url="https://project.supabase.co/auth/v1/.well-known/jwks.json",
        signing_key_provider=StaticSigningKeyProvider(signing_key),
        clock_skew_seconds=0,
    )


@pytest.mark.anyio
async def test_valid_oauth_token_resolves_principal(
    signing_material: tuple[rsa.RSAPrivateKey, PyJWK],
) -> None:
    private_key, signing_key = signing_material
    claims = _claims()

    access = await _verifier(signing_key).verify_token(_encode(private_key, claims))

    assert access is not None
    assert access.subject == claims["sub"]
    assert access.client_id == CLIENT_ID
    assert access.resource == AUDIENCE
    assert access.scopes == ["openid", "email"]


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("claim", "value"),
    [
        ("aud", "https://other.example.com/mcp"),
        ("iss", "https://attacker.example.com/auth/v1"),
        ("exp", 1),
        ("role", "service_role"),
        ("sub", "not-a-uuid"),
        ("user_id", str(uuid4())),
    ],
)
async def test_invalid_security_claim_is_rejected(
    signing_material: tuple[rsa.RSAPrivateKey, PyJWK],
    claim: str,
    value: object,
) -> None:
    private_key, signing_key = signing_material
    token = _encode(private_key, _claims(**{claim: value}))

    assert await _verifier(signing_key).verify_token(token) is None


@pytest.mark.anyio
async def test_missing_oauth_client_id_is_rejected(
    signing_material: tuple[rsa.RSAPrivateKey, PyJWK],
) -> None:
    private_key, signing_key = signing_material
    claims = _claims()
    del claims["client_id"]

    assert await _verifier(signing_key).verify_token(_encode(private_key, claims)) is None


@pytest.mark.anyio
async def test_symmetric_algorithm_is_rejected_before_key_lookup() -> None:
    token = jwt.encode(
        _claims(),
        "local-shared-secret-that-is-long-enough",
        algorithm="HS256",
        headers={"kid": "symmetric-key"},
    )
    verifier = SupabaseTokenVerifier(
        issuer=ISSUER,
        audience=AUDIENCE,
        jwks_url="https://project.supabase.co/auth/v1/.well-known/jwks.json",
        signing_key_provider=FailingSigningKeyProvider(),
    )

    assert await verifier.verify_token(token) is None


@pytest.mark.anyio
async def test_unknown_jwks_key_fails_closed(
    signing_material: tuple[rsa.RSAPrivateKey, PyJWK],
) -> None:
    private_key, _ = signing_material
    verifier = SupabaseTokenVerifier(
        issuer=ISSUER,
        audience=AUDIENCE,
        jwks_url="https://project.supabase.co/auth/v1/.well-known/jwks.json",
        signing_key_provider=FailingSigningKeyProvider(),
    )

    assert await verifier.verify_token(_encode(private_key, _claims())) is None
