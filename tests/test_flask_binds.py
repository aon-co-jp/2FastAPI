"""Flask-SQLAlchemy multiple binds (differential)."""
import os

from fastapi.testclient import TestClient

from helpers import convert_and_load, load

APP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "examples", "flask_app7", "app.py")


def test_binds():
    fl = load(APP, "orig_flask_app7").app.test_client()
    res, mod = convert_and_load(APP)
    fa = TestClient(mod.app)
    a, b = fl.get("/counts"), fa.get("/counts")
    assert a.status_code == b.status_code == 200
    assert a.get_json() == b.json() == {"main": 1, "other": 2, "o": ["o1", "o2"]}
