import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from tofastapi import _autoupdate as u  # noqa: E402


def test_version_order_and_prerelease():
    assert u.is_newer("v0.5.1", "0.5.0")
    assert u.is_newer("0.10.0", "0.9.9")
    assert not u.is_newer("v0.5.0", "0.5.0")
    assert not u.is_newer("v0.3.0-alpha", "0.5.0")
    assert not u.is_newer("garbage", "0.5.0")


def test_sha256_text_and_trust():
    h = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    assert u.parse_sha256_text(h + "  f.whl\n") == h
    assert u.parse_sha256_text("zz") is None and u.parse_sha256_text("") is None
    assert u.is_trusted_url("https://github.com/aon-co-jp/2FastAPI/releases/download/v1/x.whl")
    assert not u.is_trusted_url("https://evil.example/aon-co-jp/2FastAPI/releases/download/v1/x.whl")
    assert not u.is_trusted_url("https://github.com/other/MFastAPI/releases/download/v1/x.whl")


def test_disabled_under_pytest_and_env(monkeypatch):
    assert u.disabled()  # PYTEST_CURRENT_TEST
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv(u.ENV_OFF, raising=False)
    assert not u.disabled()
    monkeypatch.setenv(u.ENV_OFF, "1")
    assert u.disabled()


def test_maybe_start_never_raises_and_is_quiet_when_disabled(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    u.maybe_start()  # pytest 中は無効
    assert not (tmp_path / ".2fastapi").exists()


def test_sha256_file(tmp_path):
    p = tmp_path / "a"
    p.write_bytes(b"abc")
    assert u.sha256_file(str(p)) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_setup_asset_name_is_known():
    assert u.setup_asset_name() in ("2FastAPI-Setup-x64.exe", "2FastAPI-Setup-arm64.exe")
