"""Flask-SQLAlchemy + marshmallow + Flask-JWT-Extended -> converted FastAPI (differential)."""
import datetime
import os

import jwt as pyjwt
from fastapi.testclient import TestClient

from helpers import convert_and_load, load

APP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "examples", "flask_app8", "app.py")
SECRET = "jwt-test-secret-that-is-long-enough-32b"


def _both():
    fl = load(APP, "orig_flask_app8").app.test_client()
    res, mod = convert_and_load(APP)
    return fl, TestClient(mod.app), res


def _cmp(a, b, what):
    assert a.status_code == b.status_code, (what, a.status_code, b.status_code, b.text)
    ja = a.get_json()
    jb = b.json()
    assert ja == jb, (what, ja, jb)


def test_register_login_protected():
    fl, fa, res = _both()
    assert "flask_jwt_extended" not in res.code
    for what, m, u, j in [
        ("bad body", "POST", "/register", {"name": "x"}),
        ("bad short", "POST", "/register", {"name": "ann", "password": "ab"}),
        ("ok", "POST", "/register", {"name": "ann", "password": "secret1"}),
        ("age", "POST", "/register", {"name": "bob", "password": "secret2", "age": 40}),
        ("dup", "POST", "/register", {"name": "ann", "password": "secret1"}),
        ("badlogin", "POST", "/login", {"name": "ann", "password": "nope"}),
    ]:
        _cmp(fl.open(u, method=m, json=j), fa.request(m, u, json=j), what)
    ta = fl.post("/login", json={"name": "ann", "password": "secret1"}).get_json()
    tb = fa.post("/login", json={"name": "ann", "password": "secret1"}).json()
    assert set(ta) == set(tb) == {"access_token", "refresh_token"}
    # each app with its own token, and the Flask token on the FastAPI app (same claims/secret)
    for what, ha, hb in [
        ("none", {}, {}),
        ("own", {"Authorization": "Bearer " + ta["access_token"]}, {"Authorization": "Bearer " + tb["access_token"]}),
        ("cross", {"Authorization": "Bearer " + ta["access_token"]}, {"Authorization": "Bearer " + ta["access_token"]}),
        ("garbage", {"Authorization": "Bearer abc"}, {"Authorization": "Bearer abc"}),
        ("scheme", {"Authorization": "Basic zzz"}, {"Authorization": "Basic zzz"}),
        ("refresh as access", {"Authorization": "Bearer " + ta["refresh_token"]}, {"Authorization": "Bearer " + ta["refresh_token"]}),
    ]:
        _cmp(fl.get("/me", headers=ha), fa.get("/me", headers=hb), what)
        _cmp(fl.get("/maybe", headers=ha), fa.get("/maybe", headers=hb), "maybe " + what)
    bad = pyjwt.encode({"sub": "1", "type": "access", "fresh": False, "jti": "x", "iat": 1, "nbf": 1, "exp": 2}, SECRET, algorithm="HS256")
    wrong = pyjwt.encode({"sub": "1", "type": "access", "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)}, "another-secret-that-is-long-enough-xx", algorithm="HS256")
    for what, tok in [("expired", bad), ("wrong signature", wrong)]:
        h = {"Authorization": "Bearer " + tok}
        _cmp(fl.get("/me", headers=h), fa.get("/me", headers=h), what)
    for what, ha, hb in [
        ("refresh ok", {"Authorization": "Bearer " + ta["refresh_token"]}, {"Authorization": "Bearer " + tb["refresh_token"]}),
        ("refresh with access", {"Authorization": "Bearer " + ta["access_token"]}, {"Authorization": "Bearer " + tb["access_token"]}),
    ]:
        a, b = fl.post("/refresh", headers=ha), fa.post("/refresh", headers=hb)
        assert a.status_code == b.status_code, (what, a.status_code, b.status_code, b.text)
        assert a.get_json().get("type") == b.json().get("type") and a.get_json().get("msg") == b.json().get("msg")
