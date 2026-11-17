"""Source version detection + target FastAPI version."""
import os
import shutil

import pytest

from tofastapi import versions as V
from tofastapi.scan import scan, convert_project_to

HERE = os.path.dirname(os.path.abspath(__file__))


def test_detect_from_requirements(tmp_path):
    (tmp_path / "requirements.txt").write_text("Flask==2.0.3\nflask-login>=0.6\nDjango~=4.2\n")
    d = V.detect_source(str(tmp_path))
    assert d["flask"]["version"] == "2.0.3" and d["flask-login"]["version"] == "0.6" and d["django"]["version"] == "4.2"


def test_detect_from_code_pattern(tmp_path):
    d = V.detect_source(str(tmp_path), ["@app.before_first_request\ndef f(): pass"])
    assert d["flask"]["version"] == "<2.3"


def test_normalize_target():
    assert V.normalize_target(None) == "latest" and V.normalize_target("") == "latest"
    assert V.normalize_target("0.110") == "0.110"
    with pytest.raises(ValueError):
        V.normalize_target("abc")


def test_old_template_response_form(tmp_path):
    src = os.path.join(HERE, "..", "examples", "flask_app2")
    p = [x for x in scan(src) if x.kind == "flask"][0]
    new = str(tmp_path / "new")
    old = str(tmp_path / "old")
    convert_project_to(p, new)
    convert_project_to(p, old, fastapi_version="0.100.0")
    a = open(os.path.join(new, "app.py"), encoding="utf-8").read()
    b = open(os.path.join(old, "app.py"), encoding="utf-8").read()
    assert "TemplateResponse(request," in a
    assert 'TemplateResponse("' in b and '"request": request' in b
    assert "fastapi==0.100.0" in open(os.path.join(old, "requirements.txt")).read()
    assert open(os.path.join(new, "requirements.txt")).read().startswith("fastapi\n")
    assert "Source (detected)" in open(os.path.join(new, "CONVERSION_REPORT.md"), encoding="utf-8").read()


def test_render_to_response_hints_old_django():
    from tofastapi import versions as V

    d = V.detect_source("/nonexistent-project", ["from django.shortcuts import render_to_response\n"])
    assert d["django"]["version"] == "<3.0"
