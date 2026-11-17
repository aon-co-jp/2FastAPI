import json
import os
import subprocess
import sys

import pytest

from tofastapi.django_conv import convert_project

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.abspath(os.path.join(HERE, "..", "examples", "drf_proj2"))

REQUESTS = [
    ["GET", "/api/items/", {}],
    ["GET", "/api/items/?limit=1", {}],
    ["POST", "/api/items/", {"json": {"name": "zed"}}],
    ["POST", "/api/items/", {"json": {}}],
    ["GET", "/api/items/1/", {}],
    ["GET", "/api/items/9/", {}],
    ["PUT", "/api/items/2/", {"json": {"name": "deux"}}],
    ["DELETE", "/api/items/2/", {}],
]


def test_viewset_same_responses(tmp_path):
    out = str(tmp_path / "out")
    res = convert_project(PROJ, out)
    req = str(tmp_path / "req.json")
    json.dump(REQUESTS, open(req, "w"))
    p = subprocess.run([sys.executable, os.path.join(HERE, "run_requests.py"), out, req], capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    fa = json.loads(p.stdout.strip().splitlines()[-1])
    p = subprocess.run([sys.executable, os.path.join(HERE, "run_drf_reference.py"), PROJ, req], capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    dr = json.loads(p.stdout.strip().splitlines()[-1])
    for (m, url, _), a, b in zip(REQUESTS, dr, fa):
        assert a[0] == b[0], (m, url, a, b)
        if a[0] < 400 and a[1] != "":
            assert a[1] == b[1], (m, url, a, b)
    src = open(os.path.join(out, "api", "views.py")).read()
    assert "rest_framework" not in src
    assert res.routes == 5
