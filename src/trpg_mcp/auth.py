"""Supabase JWT verification for the MCP resource server."""

import asyncio
from typing import Protocol
from uuid import UUID

import jwt
from jwt import InvalidTokenError, PyJWK, PyJWKClient, PyJWKClientError
from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings

from trpg_mcp.config import Settings

ALLOWED_SIGNING_ALGORITHMS = frozenset({"RS256", "ES256"})
MAX_TOKEN_LENGTH = 16_384


class SigningKeyProvider(Protocol):
    """Resolve a verified public signing key for a JWT."""

    def get_signing_key_from_jwt(self, token: str) -> PyJWK: ...


class SupabaseTokenVerifier(TokenVerifier):
    """Verify audience-bound, asymmetric Supabase OAuth access tokens."""

    def __init__(
        self,
        *,
        issuer: str,
        audience: str,
        jwks_url: str,
        signing_key_provider: SigningKeyProvider | None = None,
        clock_skew_seconds: int = 30,
    ) -> None:
        self.issuer = issuer
        self.audience = audience
        self.clock_skew_seconds = clock_skew_seconds
        self._signing_key_provider = signing_key_provider or PyJWKClient(
            jwks_url,
            cache_keys=True,
            cache_jwk_set=True,
            lifespan=300,
            timeout=5,
        )

    async def verify_token(self, token: str) -> AccessToken | None:
        """Return MCP access information only after every security check passes."""
        if not token or len(token) > MAX_TOKEN_LENGTH:
            return None

        try:
            header = jwt.get_unverified_header(token)
            algorithm = header.get("alg")
            if algorithm not in ALLOWED_SIGNING_ALGORITHMS or not header.get("kid"):
                return None

            signing_key = await asyncio.to_thread(
                self._signing_key_provider.get_signing_key_from_jwt,
                token,
            )
            claims = jwt.decode(
                token,
                signing_key,
                algorithms=[algorithm],
                audience=self.audience,
                issuer=self.issuer,
                leeway=self.clock_skew_seconds,
                options={
                    "require": [
                        "aud",
                        "client_id",
                        "exp",
                        "iat",
                        "iss",
                        "role",
                        "sub",
                    ]
                },
            )
            return self._to_access_token(token, claims)
        except (InvalidTokenError, PyJWKClientError, TypeError, ValueError):
            return None

    def _to_access_token(self, token: str, claims: dict[str, object]) -> AccessToken | None:
        subject = claims.get("sub")
        client_id = claims.get("client_id")
        expires_at = claims.get("exp")
        if not isinstance(subject, str) or not isinstance(client_id, str) or not client_id:
            return None
        if not isinstance(expires_at, int) or claims.get("role") != "authenticated":
            return None

        try:
            UUID(subject)
        except ValueError:
            return None

        user_id = claims.get("user_id")
        if user_id is not None and user_id != subject:
            return None

        scopes = _extract_scopes(claims)
        return AccessToken(
            token=token,
            client_id=client_id,
            scopes=scopes,
            expires_at=expires_at,
            resource=self.audience,
            subject=subject,
            claims={"iss": self.issuer, "aud": claims["aud"], "role": "authenticated"},
        )


def _extract_scopes(claims: dict[str, object]) -> list[str]:
    raw_scope = claims.get("scope")
    if isinstance(raw_scope, str):
        return list(dict.fromkeys(raw_scope.split()))

    raw_scopes = claims.get("scopes")
    if isinstance(raw_scopes, list) and all(isinstance(scope, str) for scope in raw_scopes):
        return list(dict.fromkeys(raw_scopes))
    return []


def create_auth(settings: Settings) -> tuple[AuthSettings, SupabaseTokenVerifier]:
    """Create MCP SDK authorization settings and the Supabase verifier."""
    auth_settings = AuthSettings(
        issuer_url=settings.supabase_auth_issuer,
        resource_server_url=settings.mcp_resource_url,
        required_scopes=[],
    )
    verifier = SupabaseTokenVerifier(
        issuer=settings.supabase_auth_issuer,
        audience=settings.mcp_resource_url,
        jwks_url=settings.supabase_jwks_url,
    )
    return auth_settings, verifier
