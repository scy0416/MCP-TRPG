"""Runtime configuration for the MCP-TRPG service."""

from dataclasses import dataclass
from os import environ
from urllib.parse import urlsplit

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
DEFAULT_SUPABASE_URL = "http://127.0.0.1:54321"
DEFAULT_MCP_RESOURCE_URL = "http://127.0.0.1:8000/mcp"


def _validate_http_url(name: str, value: str) -> str:
    parsed = urlsplit(value)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"{name} must be an absolute HTTP URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError(f"{name} must not contain credentials, a query, or a fragment")
    if parsed.scheme == "http" and parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError(f"{name} must use HTTPS outside loopback development")
    if parsed.scheme not in {"http", "https"}:
        raise ValueError(f"{name} must use HTTP or HTTPS")
    return value.rstrip("/")


@dataclass(frozen=True, slots=True)
class Settings:
    """Environment-backed settings used by local and hosted runtimes."""

    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    supabase_url: str = DEFAULT_SUPABASE_URL
    supabase_auth_issuer: str = f"{DEFAULT_SUPABASE_URL}/auth/v1"
    supabase_jwks_url: str = f"{DEFAULT_SUPABASE_URL}/auth/v1/.well-known/jwks.json"
    supabase_publishable_key: str = ""
    mcp_resource_url: str = DEFAULT_MCP_RESOURCE_URL

    @classmethod
    def from_env(cls) -> "Settings":
        """Load settings and reject an invalid TCP port early."""
        host = environ.get("HOST", DEFAULT_HOST)
        raw_port = environ.get("PORT", str(DEFAULT_PORT))

        try:
            port = int(raw_port)
        except ValueError as exc:
            raise ValueError("PORT must be an integer") from exc

        if not 1 <= port <= 65_535:
            raise ValueError("PORT must be between 1 and 65535")

        supabase_url = _validate_http_url(
            "SUPABASE_URL",
            environ.get("SUPABASE_URL", DEFAULT_SUPABASE_URL),
        )
        default_issuer = f"{supabase_url}/auth/v1"
        issuer = _validate_http_url(
            "SUPABASE_AUTH_ISSUER",
            environ.get("SUPABASE_AUTH_ISSUER", default_issuer),
        )
        jwks_url = _validate_http_url(
            "SUPABASE_JWKS_URL",
            environ.get("SUPABASE_JWKS_URL", f"{issuer}/.well-known/jwks.json"),
        )
        resource_url = _validate_http_url(
            "MCP_RESOURCE_URL",
            environ.get("MCP_RESOURCE_URL", DEFAULT_MCP_RESOURCE_URL),
        )
        if urlsplit(resource_url).path.rstrip("/") != "/mcp":
            raise ValueError("MCP_RESOURCE_URL must identify the /mcp endpoint")

        publishable_key = environ.get("SUPABASE_PUBLISHABLE_KEY", "")
        if any(character.isspace() for character in publishable_key):
            raise ValueError("SUPABASE_PUBLISHABLE_KEY must not contain whitespace")

        return cls(
            host=host,
            port=port,
            supabase_url=supabase_url,
            supabase_auth_issuer=issuer,
            supabase_jwks_url=jwks_url,
            supabase_publishable_key=publishable_key,
            mcp_resource_url=resource_url,
        )


settings = Settings.from_env()
