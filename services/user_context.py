"""Replaceable current-user abstraction for local and future SSO deployments."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path


@dataclass(frozen=True)
class CurrentUser:
    user_id: str
    display_name: str
    roles: tuple[str, ...]
    branch_id: str | None = None
    branch_code: str | None = None
    branch_name: str | None = None


def load_current_user(config_path: str | Path = "config/local_user.json") -> CurrentUser:
    """Load the local prototype user; an SSO adapter can replace this function."""
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Local user configuration was not found: {path}")
    with path.open("r", encoding="utf-8") as stream:
        payload = json.load(stream)
    user_id = str(payload.get("user_id", "")).strip()
    display_name = str(payload.get("display_name", "")).strip()
    roles = payload.get("roles", [])
    def optional_text(key: str) -> str | None:
        value = payload.get(key)
        if value is None:
            return None
        return str(value).strip() or None

    branch_id = optional_text("branch_id")
    branch_code = optional_text("branch_code")
    branch_name = optional_text("branch_name")
    if not user_id or not display_name:
        raise ValueError("Local user config requires non-blank user_id and display_name")
    if not isinstance(roles, list) or not all(isinstance(role, str) for role in roles):
        raise ValueError("Local user config roles must be a list of strings")
    return CurrentUser(
        user_id, display_name, tuple(roles), branch_id, branch_code, branch_name
    )
