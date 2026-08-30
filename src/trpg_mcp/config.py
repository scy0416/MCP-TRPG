"""Runtime configuration for the MCP-TRPG service."""

from dataclasses import dataclass
from os import environ

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000


@dataclass(frozen=True, slots=True)
class Settings:
    """Environment-backed settings used by local and hosted runtimes."""

    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT

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

        return cls(host=host, port=port)


settings = Settings.from_env()
