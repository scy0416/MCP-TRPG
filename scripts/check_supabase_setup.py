"""Validate the committed Supabase configuration without exposing credentials."""

import argparse
import os
import tomllib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "supabase" / "config.toml"


def validate_local_config() -> None:
    with CONFIG_PATH.open("rb") as config_file:
        config = tomllib.load(config_file)

    expected_values = {
        ("project_id",): "mcp-trpg",
        ("api", "enabled"): True,
        ("api", "auto_expose_new_tables"): False,
        ("db", "major_version"): 17,
        ("db", "migrations", "enabled"): True,
        ("auth", "enabled"): True,
        ("auth", "minimum_password_length"): 8,
        ("auth", "oauth_server", "enabled"): False,
        ("realtime", "enabled"): False,
        ("storage", "enabled"): False,
        ("edge_runtime", "enabled"): False,
        ("analytics", "enabled"): False,
    }

    for path, expected in expected_values.items():
        value = config
        for key in path:
            value = value[key]
        if value != expected:
            dotted_path = ".".join(path)
            raise ValueError(f"{dotted_path} must be {expected!r}, got {value!r}")


def validate_remote_environment() -> None:
    required_names = (
        "SUPABASE_URL",
        "SUPABASE_PUBLISHABLE_KEY",
        "SUPABASE_PROJECT_REF",
    )
    missing_names = [name for name in required_names if not os.environ.get(name)]
    if missing_names:
        joined_names = ", ".join(missing_names)
        raise ValueError(f"Missing remote Supabase settings: {joined_names}")

    supabase_url = os.environ["SUPABASE_URL"]
    if not supabase_url.startswith("https://"):
        raise ValueError("Hosted SUPABASE_URL must use HTTPS")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--require-remote",
        action="store_true",
        help="also require hosted project environment variables",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    validate_local_config()
    if args.require_remote:
        validate_remote_environment()
    print("Supabase setup validation passed")


if __name__ == "__main__":
    main()
