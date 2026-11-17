"""Command line.

2fastapi flask app.py -o app_fastapi.py
2fastapi django project_dir -o out_dir
2fastapi scan DIR [--json]            list Flask / Django projects found below DIR
2fastapi auto DIR [-o OUT] [--yes]    scan, ask (English / Japanese) what and where to convert, convert
2fastapi gui | web                   graphical wizard (folder pickers, 13 languages) / the same in the browser (local only)
2fastapi convert --kind flask|django --path P -o OUT   (used by the VS Code extension)
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from . import __version__


def main(argv=None) -> int:
    from ._autoupdate import maybe_start

    maybe_start()  # 起動時の自動バージョンアップ(24時間に1回、切り離して確認。TOFASTAPI_NO_UPDATE=1 で停止)
    ap = argparse.ArgumentParser(prog="2fastapi", description="Convert Flask / Django code to FastAPI (MFastAPI compatible).")
    ap.add_argument("--version", action="version", version="2fastapi " + __version__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("flask", help="convert a Flask module")
    f.add_argument("path")
    f.add_argument("-o", "--output", help="output file (default: stdout)")
    d = sub.add_parser("django", help="convert a Django project/app (urls.py + views.py)")
    d.add_argument("path", help="project directory (containing manage.py) or an app directory")
    d.add_argument("-o", "--output", required=True, help="output directory")
    s = sub.add_parser("scan", help="find Flask / Django projects below a directory")
    s.add_argument("path")
    s.add_argument("--json", action="store_true", help="machine-readable output")
    a = sub.add_parser("auto", help="scan a directory (or convert one file), asking where to put the result")
    a.add_argument("path")
    a.add_argument("-o", "--output", help="destination root (default: <path>-fastapi)")
    a.add_argument("-y", "--yes", action="store_true", help="no questions: convert everything, create folders")
    a.add_argument("--select", help="comma-separated project numbers (skip the question)")
    a.add_argument("--fastapi-version", default=None, help="FastAPI version to generate for (default: latest)")
    c = sub.add_parser("convert", help="convert one scanned project")
    c.add_argument("--kind", required=True, choices=["flask", "django"])
    c.add_argument("--path", required=True)
    c.add_argument("-o", "--output", required=True)
    c.add_argument("--json", action="store_true")
    c.add_argument("--fastapi-version", default=None, help="FastAPI version to generate for (default: latest). The source Flask/Django version is detected automatically.")
    c.add_argument("--target", choices=["fastapi", "mfastapi"], default="fastapi", help="mfastapi also writes run_mfastapi.py and requirements.txt")
    w = sub.add_parser("web", help="open the browser wizard (served on this PC only)")
    w.add_argument("--no-browser", action="store_true")
    w.add_argument("--port", type=int, default=0)
    g = sub.add_parser("gui", help="open the graphical wizard (folder pickers, 13 languages)")
    g.add_argument("--selftest", action="store_true", help=argparse.SUPPRESS)
    g.add_argument("--install-shortcut", action="store_true", help="create a desktop shortcut with an icon (Windows)")
    ns = ap.parse_args(argv)

    cmd = ns.cmd
    if cmd == "web":
        from .web import serve

        return serve(open_browser=not ns.no_browser, port=ns.port)
    if cmd == "gui":
        from .gui import main as gui_main

        return gui_main(selftest=ns.selftest, install_shortcut=ns.install_shortcut)
    if cmd == "scan":
        from .scan import scan

        projects = scan(ns.path)
        if ns.json:
            print(json.dumps([p.to_dict() for p in projects], ensure_ascii=False))
        else:
            for i, p in enumerate(projects, 1):
                print("[%d] %s  %s  routes~%d  %s" % (i, p.kind, p.name, p.routes, p.path))
            if not projects:
                print("No Flask or Django project found. / Flask・Django のプロジェクトは見つかりませんでした。")
        return 0
    if cmd == "convert":
        from .scan import convert_project_to, scan

        projects = [p for p in scan(ns.path) if p.kind == ns.kind and os.path.abspath(p.path) == os.path.abspath(ns.path)]
        if not projects:  # a path that the scan did not report: treat it as a project of the given kind
            from .scan import Project

            p = Project(ns.kind, os.path.basename(os.path.abspath(ns.path)), os.path.abspath(ns.path))
            if ns.kind == "flask":
                p.files = [os.path.relpath(os.path.join(dp, fn), p.path) for dp, _, fns in os.walk(p.path) for fn in fns if fn.endswith(".py")]
                p.entry = p.files[0] if p.files else ""
            projects = [p]
        routes, warns = convert_project_to(projects[0], ns.output, ns.target, ns.fastapi_version)
        if ns.json:
            print(json.dumps({"routes": routes, "warnings": warns, "dest": os.path.abspath(ns.output), "detected": projects[0].detected, "fastapi_version": ns.fastapi_version or "latest"}, ensure_ascii=False))
        else:
            print("wrote %s (%d routes)" % (ns.output, routes), file=sys.stderr)
            for w in warns:
                print("warning: %s" % w, file=sys.stderr)
        return 0
    if cmd == "auto" and os.path.isdir(ns.path):
        from .scan import run_auto

        run_auto(ns.path, ns.output, assume_yes=ns.yes, select=ns.select, fastapi_version=ns.fastapi_version)
        return 0
    if cmd == "auto":
        cmd = "flask"
    if cmd == "flask":
        from .flask_conv import convert_source

        with open(ns.path, encoding="utf-8") as fh:
            src = fh.read()
        res = convert_source(src)
        out_path = getattr(ns, "output", None)
        if out_path:
            if os.path.isdir(out_path) or out_path.endswith(("/", "\\")):
                os.makedirs(out_path, exist_ok=True)
                out_path = os.path.join(out_path, os.path.basename(ns.path))
            with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(res.code)
            print("wrote %s (%d routes)" % (out_path, res.routes), file=sys.stderr)
        else:
            sys.stdout.write(res.code)
        for w in res.warnings:
            print("warning: %s" % w, file=sys.stderr)
        return 0
    from .django_conv import convert_project

    res = convert_project(ns.path, ns.output)
    print("wrote %s (%d routes)" % (ns.output, res.routes), file=sys.stderr)
    for w in res.warnings:
        print("warning: %s" % w, file=sys.stderr)
    return 0
