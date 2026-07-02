import json

import pytest

from plexget import auth


class FakeAccount:
    def __init__(self, token, client_id):
        self.token = token
        self.client_id = client_id


class FakePin:
    def __init__(self, client_id, ok=True, token="pin-token"):
        self.id = client_id
        self.pin = "P4X9"
        self._ok = ok
        self.token = token
        self.ran = False

    def run(self):
        self.ran = True

    def waitForLogin(self):
        return self._ok


def test_load_cache_generates_stable_client_id(tmp_path):
    token1, cid1 = auth.load_cache(tmp_path)
    token2, cid2 = auth.load_cache(tmp_path)
    assert token1 is None
    assert cid1 == cid2  # persisted, stable
    assert (tmp_path / "auth.json").exists()


def test_explicit_token_short_circuits(tmp_path):
    made = {}
    def account_factory(token, client_id):
        made["token"] = token
        return FakeAccount(token, client_id)

    acct = auth.login(
        token="explicit",
        account_factory=account_factory,
        pin_factory=lambda cid: pytest.fail("PIN must not run"),
        config_dir=tmp_path,
    )
    assert made["token"] == "explicit"
    assert acct.token == "explicit"


def test_cached_token_is_reused(tmp_path):
    auth.save_token(tmp_path, "cached-token")
    acct = auth.login(
        account_factory=lambda token, cid: FakeAccount(token, cid),
        pin_factory=lambda cid: pytest.fail("PIN must not run"),
        config_dir=tmp_path,
    )
    assert acct.token == "cached-token"


def test_pin_flow_runs_and_persists_token(tmp_path):
    printed = []
    acct = auth.login(
        force_pin=True,
        account_factory=lambda token, cid: FakeAccount(token, cid),
        pin_factory=lambda cid: FakePin(cid, ok=True, token="pin-token"),
        print_fn=printed.append,
        config_dir=tmp_path,
    )
    assert acct.token == "pin-token"
    saved = json.loads((tmp_path / "auth.json").read_text())
    assert saved["token"] == "pin-token"
    assert any("P4X9" in line for line in printed)  # code shown to user


def test_pin_flow_failure_raises(tmp_path):
    with pytest.raises(auth.AuthError):
        auth.login(
            force_pin=True,
            account_factory=lambda token, cid: FakeAccount(token, cid),
            pin_factory=lambda cid: FakePin(cid, ok=False),
            config_dir=tmp_path,
        )
