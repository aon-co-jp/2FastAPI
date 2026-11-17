"""Source-version detection (automatic) and target FastAPI version handling (optional, default = latest).

Detection only reads files (requirements*.txt, pyproject.toml, setup.py/cfg, Pipfile, constraints) and looks for
version-specific code patterns; it never imports the scanned project.
"""
from __future__ import annotations

import os
import re
from typing import Dict, List, Optional, Tuple

LATEST = "latest"
# Starlette 0.29 / FastAPI 0.108 changed TemplateResponse to (request, name, context)
NEW_TEMPLATE_RESPONSE = (0, 108, 0)

_PKGS = ("flask", "django", "werkzeug", "flask-sqlalchemy", "flask-login", "djangorestframework", "flask-restful", "flask-cors")
_REQ = re.compile(r"(?im)^\s*[\"']?(%s)\s*(?:\[[^\]]*\])?\s*(==|>=|~=|<=|<|>|=)\s*v?([0-9][0-9A-Za-z.\-*]*)" % "|".join(re.escape(p) for p in _PKGS))
_REQ_ANY = re.compile(r"(?i)[\"']?(%s)\s*(?:\[[^\]]*\])?\s*(==|>=|~=|<=|<|>)\s*v?([0-9][0-9A-Za-z.*]*)" % "|".join(re.escape(p) for p in _PKGS))
_FILES = ("requirements.txt", "requirements-dev.txt", "requirements_dev.txt", "pyproject.toml", "setup.py", "setup.cfg", "Pipfile", "constraints.txt")


def parse_version(v: str) -> Tuple[int, ...]:
    out = []
    for part in re.split(r"[.\-+]", v.strip()):
        m = re.match(r"\d+", part)
        if not m:
            break
        out.append(int(m.group()))
    return tuple(out) or (0,)


def normalize_target(v: Optional[str]) -> str:
    """'' / None / 'latest' -> 'latest'; otherwise the dotted version (validated)."""
    if v is None or str(v).strip().lower() in ("", "latest", "newest"):
        return LATEST
    s = str(v).strip().lstrip("=v ")
    if not re.fullmatch(r"\d+(\.\d+){0,2}", s):
        raise ValueError("invalid FastAPI version: %r (use e.g. 0.115.0 or latest)" % v)
    return s


def _read(path: str) -> str:
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def detect_source(root: str, sources: Optional[List[str]] = None) -> Dict[str, Dict[str, str]]:
    """Return {package: {"version": "2.3", "how": "requirements.txt (>=)"}} for Flask/Django and their extensions.

    `root` is the project directory; `sources` are code strings used for pattern based hints when no pin is found.
    """
    found: Dict[str, Dict[str, str]] = {}
    root = os.path.abspath(root)
    dirs = [root]
    parent = os.path.dirname(root)
    if parent and parent != root:
        dirs.append(parent)
    for d in dirs:
        for fn in _FILES:
            text = _read(os.path.join(d, fn))
            if not text:
                continue
            for m in list(_REQ.finditer(text)) + list(_REQ_ANY.finditer(text)):
                name, op, ver = m.group(1).lower(), m.group(2), m.group(3)
                if name not in found:
                    found[name] = {"version": ver, "how": "%s (%s)" % (fn, op)}
    code = "\n".join(sources or [])
    if code:
        hints = _code_hints(code)
        for name, (ver, why) in hints.items():
            if name not in found:
                found[name] = {"version": ver, "how": "code pattern: " + why}
    for name in ("flask", "django"):
        if name not in found:
            try:
                from importlib.metadata import version as _v

                found[name] = {"version": _v(name), "how": "installed in this environment (no pin found)"}
            except Exception:
                pass
    return found


def _code_hints(code: str) -> Dict[str, Tuple[str, str]]:
    h: Dict[str, Tuple[str, str]] = {}
    if re.search(r"before_first_request|flask\.json\.JSONEncoder|from flask import[^\n]*\bescape\b|_request_ctx_stack", code):
        h["flask"] = ("<2.3", "uses an API removed in Flask 2.3/3.0 (before_first_request / JSONEncoder / escape)")
    elif re.search(r"@\w+\.(get|post|put|delete|patch)\(", code):
        h["flask"] = (">=2.0", "uses @app.get/@app.post shortcuts")
    if re.search(r"render_to_response", code):
        h["django"] = ("<3.0", "uses render_to_response (removed in Django 3.0)")
    elif re.search(r"from django\.conf\.urls import[^\n]*\burl\b|ugettext|from django\.utils\.encoding import force_text", code):
        h["django"] = ("<4.0", "uses django.conf.urls.url / ugettext (removed in Django 4.0)")
    elif re.search(r"DEFAULT_AUTO_FIELD|from django\.urls import[^\n]*\bpath\b", code):
        h["django"] = (">=3.2", "uses django.urls.path / DEFAULT_AUTO_FIELD")
    return h


def describe_source(detected: Dict[str, Dict[str, str]]) -> List[str]:
    return ["%s %s  [%s]" % (k, v["version"], v["how"]) for k, v in sorted(detected.items())]


def target_tuple(target: str) -> Optional[Tuple[int, ...]]:
    return None if target == LATEST else parse_version(target)


def adapt_code(code: str, target: str) -> Tuple[str, List[str]]:
    """Make converted code match the requested FastAPI version. Returns (code, notes). `latest` leaves it as generated."""
    t = target_tuple(target)
    notes: List[str] = []
    if t is not None and t < NEW_TEMPLATE_RESPONSE and "templates.TemplateResponse(request," in code:
        new, n = re.subn(r"templates\.TemplateResponse\(request, ([^,\n]+), \{", r'templates.TemplateResponse(\1, {"request": request, ', code)
        if n:
            code = new
            notes.append("FastAPI %s: TemplateResponse(name, {\"request\": request, ...}) form used (the (request, name, context) form needs FastAPI >= 0.108)" % target)
        if "templates.TemplateResponse(request," in code:
            notes.append("FastAPI %s: some TemplateResponse(request, name, ctx) calls could not be rewritten automatically; change them to the old (name, {'request': request, ...}) form" % target)
    return code, notes


def requirements(kind: str, target: str, code: str) -> List[str]:
    reqs = ["fastapi" if target == LATEST else "fastapi==%s" % target, "uvicorn"]
    if "Form(" in code or "File(" in code or "UploadFile" in code:
        reqs.append("python-multipart")
    if "Jinja2Templates" in code:
        reqs.append("jinja2")
    if "SessionMiddleware" in code:
        reqs.append("itsdangerous")
    if "_SQLAlchemy" in code:
        reqs.append("sqlalchemy")
    if "werkzeug" in code:
        reqs.append("werkzeug")
    return reqs
