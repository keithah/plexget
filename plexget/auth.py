from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Callable, Optional

import platformdirs


class AuthError(Exception):
    pass


def config_dir() -> Path:
    return Path(platformdirs.user_config_path("plexget"))


def _cache_file(directory: Path) -> Path:
    return directory / "auth.json"


def _read(directory: Path) -> dict:
    path = _cache_file(directory)
    if path.exists():
        try:
            return json.loads(path.read_text())
        except (ValueError, OSError):
            return {}
    return {}


def _write(directory: Path, data: dict) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    _cache_file(directory).write_text(json.dumps(data, indent=2))


def load_cache(directory: Path) -> tuple[Optional[str], str]:
    data = _read(directory)
    client_id = data.get("client_id")
    if not client_id:
        client_id = uuid.uuid4().hex
        data["client_id"] = client_id
        _write(directory, data)
    return data.get("token"), client_id


def save_token(directory: Path, token: str) -> None:
    data = _read(directory)
    data["token"] = token
    if not data.get("client_id"):
        data["client_id"] = uuid.uuid4().hex
    _write(directory, data)


def login(
    *,
    token: Optional[str] = None,
    force_pin: bool = False,
    account_factory: Callable[[str, str], object],
    pin_factory: Callable[[str], object],
    print_fn: Callable[[str], None] = print,
    sleep: Callable[[float], None] = time.sleep,
    config_dir: Optional[Path] = None,
):
    directory = config_dir if config_dir is not None else globals()["config_dir"]()
    cached_token, client_id = load_cache(directory)

    if token:
        return account_factory(token, client_id)

    if not force_pin and cached_token:
        try:
            return account_factory(cached_token, client_id)
        except Exception:  # noqa: BLE001 - stale token; fall through to PIN
            pass

    pin = pin_factory(client_id)
    pin.run()
    print_fn(f"Go to https://plex.tv/link and enter code: {pin.pin}")
    if not pin.waitForLogin():
        raise AuthError("PIN login was not approved.")
    save_token(directory, pin.token)
    return account_factory(pin.token, client_id)
