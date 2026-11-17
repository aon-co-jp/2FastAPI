"""render() / render_to_response() -> Jinja2Templates (differential for render, conversion check for the pre-3.0 render_to_response)."""
import json
import os
import subprocess
import sys

from tofastapi.django_conv import convert_project

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.abspath(os.path.join(HERE, "..", "examples", "django_proj2"))
REQUESTS = [["GET", "/hello/", {}], ["GET", "/hello/?name=amy", {}], ["GET", "/nf/", {}]]


def _django(tmp):
    req = os.path.join(tmp, "_dj.json")
    json.dump(REQUESTS, open(req, "w"))
    p = subprocess.run([sys.executable, os.path.join(HERE, "run_django_render.py"), PROJ, req], capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout.strip().splitlines()[-1])


def _run(out, reqs):
    req = os.path.join(out, "_req.json")
    json.dump(reqs, open(req, "w"))
    p = subprocess.run([sys.executable, os.path.join(HERE, "run_requests.py"), out, req], capture_output=True, text=True, cwd=out)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout.strip().splitlines()[-1])


def test_render_matches_django(tmp_path):
    out = str(tmp_path / "out")
    res = convert_project(PROJ, out)
    assert os.path.isfile(os.path.join(out, "templates", "shop", "hello.html"))
    fa = _run(out, REQUESTS)
    dj = _django(str(tmp_path))
    for (m, u, _), a, b in zip(REQUESTS, dj, fa):
        assert a[0] == b[0], (u, a, b)
        assert a[1].strip() == b[1].strip(), (u, a, b)


def test_render_to_response(tmp_path):
    proj = tmp_path / "p"
    (proj / "config").mkdir(parents=True)
    (proj / "config" / "__init__.py").write_text("")
    (proj / "config" / "urls.py").write_text('from django.urls import path\nfrom . import views\nurlpatterns = [path("old/", views.old)]\n')
    (proj / "config" / "views.py").write_text('from django.shortcuts import render_to_response\n\n\ndef old(request):\n    return render_to_response("t.html", {"name": "legacy"})\n')
    (proj / "config" / "settings.py").write_text("ROOT_URLCONF = 'config.urls'\n")
    (proj / "manage.py").write_text("")
    (proj / "templates").mkdir()
    (proj / "templates" / "t.html").write_text("<p>{{ name }}</p>")
    out = str(tmp_path / "out")
    convert_project(str(proj), out)
    src = open(os.path.join(out, "config", "views.py"), encoding="utf-8").read()
    assert "templates.TemplateResponse(request, 't.html'" in src or 'templates.TemplateResponse(request, "t.html"' in src
    got = _run(out, [["GET", "/old/", {}]])
    assert got[0][0] == 200 and got[0][1].strip() == "<p>legacy</p>", got
