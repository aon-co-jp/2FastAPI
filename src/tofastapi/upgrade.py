"""利用者のプロジェクトの固定版(requirements / pyproject)を上流の新版へ上げる。明示コマンドのみ(自動では絶対に動かない)。

2fastapi upgrade PROJECT --check            固定版と最新版の差を一覧(何も変更しない)
2fastapi upgrade PROJECT --apply            別の一時 venv にコピーして版を上げ、テストを実行。全成功なら固定版を書き換え、失敗なら何も変えず原因を報告

標準ライブラリのみ。ネットワーク無し・依存解決の失敗・テスト無しはいずれも「何も変更せず」止まる。
"""
from __future__ import annotations

import html
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request

DEFAULT_PACKAGES = [
    "flask", "django", "fastapi", "starlette", "djangorestframework", "flask-sqlalchemy", "sqlalchemy",
    "marshmallow", "flask-jwt-extended", "pydantic", "uvicorn", "mfastapi",
]
DEFAULT_INDEX = "https://pypi.org/simple/"
SKIP_DIRS = {".git", ".hg", ".venv", "venv", "env", "node_modules", "__pycache__", ".tox", ".mypy_cache", ".pytest_cache", "site-packages"}

REQ_RE = re.compile(r"^(\s*)([A-Za-z0-9][A-Za-z0-9_.\-]*)(\[[^\]]*\])?(\s*==\s*)([^\s;#,]+)")
PYPROJ_RE = re.compile(r"""(["'])(\s*)([A-Za-z0-9][A-Za-z0-9_.\-]*)(\[[^\]]*\])?(\s*==\s*)([^\s;"',]+)""")


class UpgradeError(Exception):
    """安全に止まる理由(何も変更していない)。"""


def norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


# ---- version handling -------------------------------------------------------
_V = re.compile(r"^v?(\d+(?:\.\d+)*)(?:[-_.]?(a|b|c|rc|alpha|beta|pre|preview)[-_.]?(\d*))?(?:[-_.]?post[-_.]?(\d*))?(?:[-_.]?dev[-_.]?(\d*))?(?:\+.*)?$", re.I)


def parse_version(v: str):
    """(比較キー, 先行版か)。解釈できない版は None。"""
    m = _V.match(v.strip())
    if not m:
        return None
    rel = [int(x) for x in m.group(1).split(".")]
    while len(rel) > 1 and rel[-1] == 0:
        rel.pop()
    pre = m.group(2) is not None or m.group(5) is not None
    phase = {"a": 0, "alpha": 0, "b": 1, "beta": 1, "c": 2, "rc": 2, "pre": 2, "preview": 2}.get((m.group(2) or "").lower(), 3)
    if m.group(5) is not None and m.group(2) is None:
        phase = -1
    key = (tuple(rel), phase, int(m.group(3) or 0) if m.group(2) else 0, int(m.group(4) or 0) if m.group(4) is not None else -1)
    return key, pre


def is_newer(latest: str, current: str) -> bool:
    a, b = parse_version(latest), parse_version(current)
    if a is None or b is None:
        return False
    return a[0] > b[0]


# ---- latest version lookup (PEP 503 simple index) ------------------------------
_FILE_RE = re.compile(r"^(?P<name>.+?)-(?P<ver>\d[^-]*?)(?:-.*\.whl|\.tar\.gz|\.zip|\.tar\.bz2)$")


def index_url(explicit: str | None = None) -> str:
    u = explicit or os.environ.get("TOFASTAPI_INDEX_URL") or os.environ.get("PIP_INDEX_URL") or DEFAULT_INDEX
    return u if u.endswith("/") else u + "/"


def _read(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "2fastapi-upgrade", "Accept": "text/html"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def latest_version(name: str, index: str) -> str | None:
    """安定版の最新(先行版・yank済み・解釈不能は除く)。見つからなければ None。ネットワーク不良は UpgradeError。"""
    try:
        url = index + norm(name) + "/"
        page = _read(url + "index.html" if url.startswith("file:") else url)
    except Exception as e:  # noqa: BLE001
        if getattr(e, "code", None) == 404:
            return None
        raise UpgradeError("network or index unavailable (%s): %s" % (index, e)) from e
    best = None
    for m in re.finditer(r"<a\s+([^>]*)>([^<]*)</a>", page, re.I):
        attrs, text = m.group(1), html.unescape(m.group(2)).strip()
        if "data-yanked" in attrs:
            continue
        fm = _FILE_RE.match(text)
        if not fm or norm(fm.group("name")) != norm(name):
            continue
        pv = parse_version(fm.group("ver"))
        if pv is None or pv[1]:
            continue
        if best is None or pv[0] > best[0]:
            best = (pv[0], fm.group("ver"))
    return best[1] if best else None


# ---- project files -------------------------------------------------------------
def find_files(root: str):
    reqs, pyp = [], []
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in SKIP_DIRS and not d.endswith(".egg-info")]
        for fn in fns:
            p = os.path.join(dp, fn)
            if re.match(r"^requirements.*\.txt$", fn, re.I):
                reqs.append(p)
            elif fn == "pyproject.toml" and dp == root:
                pyp.append(p)
    return sorted(reqs), sorted(pyp)


def read_text(p: str) -> str:
    with open(p, encoding="utf-8", newline="") as fh:
        return fh.read()


def pins(root: str):
    """固定版の一覧: [{file, name, current}]"""
    out = []
    reqs, pyp = find_files(root)
    for p in reqs:
        for line in read_text(p).splitlines():
            m = REQ_RE.match(line)
            if m:
                out.append({"file": p, "name": norm(m.group(2)), "current": m.group(5)})
    for p in pyp:
        for m in PYPROJ_RE.finditer(read_text(p)):
            out.append({"file": p, "name": norm(m.group(3)), "current": m.group(6)})
    return out


def rewrite(text: str, kind: str, updates: dict) -> str:
    def rep_req(line: str) -> str:
        m = REQ_RE.match(line)
        if m and norm(m.group(2)) in updates:
            return line[: m.start(5)] + updates[norm(m.group(2))] + line[m.end(5):]
        return line

    if kind == "req":
        return "".join(rep_req(l) for l in text.splitlines(keepends=True))

    def rep_py(m):
        n = norm(m.group(3))
        if n in updates:
            return m.group(0)[: m.start(6) - m.start(0)] + updates[n]
        return m.group(0)

    return PYPROJ_RE.sub(rep_py, text)


def select(pin_list, packages, all_pins):
    if all_pins:
        return list(pin_list)
    want = {norm(p) for p in (packages or DEFAULT_PACKAGES)}
    return [p for p in pin_list if p["name"] in want]


def plan(root: str, packages=None, all_pins=False, index=None):
    """差分の一覧。[{name, current, latest, newer, files}]。ネットワーク不良は UpgradeError。"""
    idx = index_url(index)
    chosen = select(pins(root), packages, all_pins)
    names = sorted({p["name"] for p in chosen})
    rows = []
    for n in names:
        mine = [p for p in chosen if p["name"] == n]
        cur = mine[0]["current"]
        latest = latest_version(n, idx)
        rows.append({"name": n, "current": cur, "latest": latest, "newer": bool(latest and is_newer(latest, cur)),
                     "files": sorted({os.path.relpath(p["file"], root) for p in mine}),
                     "mixed": len({p["current"] for p in mine}) > 1})
    return rows


# ---- apply ---------------------------------------------------------------------
def has_tests(root: str) -> bool:
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in SKIP_DIRS]
        if dp[len(root):].count(os.sep) > 2:
            dns[:] = []
        for fn in fns:
            if (fn.startswith("test_") and fn.endswith(".py")) or fn.endswith("_test.py"):
                return True
    return False


def _run(cmd, cwd, env, timeout):
    return subprocess.run(cmd, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace", timeout=timeout)


def _tail(s: str, n: int = 25) -> str:
    return "\n".join(s.strip().splitlines()[-n:])


def requirement_args(copy_root: str):
    reqs, pyp = find_files(copy_root)
    args = []
    for p in reqs:
        if os.path.basename(p).lower() == "requirements.txt" or not args:
            args += ["-r", p]
    if args:
        return args
    deps = []
    for p in pyp:
        m = re.search(r"(?ms)^dependencies\s*=\s*\[(.*?)\]", read_text(p))
        if m:
            deps += [x[1] for x in re.findall(r"""(["'])(.*?)\1""", m.group(0)[m.group(0).index("[") :]) if x[1]]
    return deps


def apply(root: str, packages=None, all_pins=False, index=None, test_cmd=None, timeout=1800, log=print):
    """戻り値 dict: status = upgraded | uptodate | failed ; 失敗・停止時は元のファイルを一切変更しない。"""
    root = os.path.abspath(root)
    rows = plan(root, packages, all_pins, index)
    if not rows:
        raise UpgradeError("no pinned (==) dependency to upgrade in requirements*.txt / pyproject.toml")
    todo = {r["name"]: r["latest"] for r in rows if r["newer"]}
    if not todo:
        return {"status": "uptodate", "rows": rows, "updated": {}}
    if not test_cmd and not has_tests(root):
        raise UpgradeError("no tests found: nothing was changed (add tests or pass --test-cmd)")
    idx = index_url(index)
    work = tempfile.mkdtemp(prefix="2fastapi-upgrade-")
    try:
        copy_root = os.path.join(work, "project")
        shutil.copytree(root, copy_root, ignore=shutil.ignore_patterns(*SKIP_DIRS, "*.egg-info", "*.pyc"))
        # 1) 別コピーの固定版を書き換える
        reqs, pyp = find_files(copy_root)
        for kind, files in (("req", reqs), ("py", pyp)):
            for p in files:
                old = read_text(p)
                new = rewrite(old, kind, todo)
                if new != old:
                    with open(p, "w", encoding="utf-8", newline="") as fh:
                        fh.write(new)
        # 2) 一時 venv
        venv = os.path.join(work, "venv")
        r = _run([sys.executable, "-m", "venv", venv], work, None, 600)
        if r.returncode:
            return {"status": "failed", "stage": "venv", "rows": rows, "updated": {}, "detail": _tail(r.stdout)}
        py = os.path.join(venv, "Scripts" if os.name == "nt" else "bin", "python" + (".exe" if os.name == "nt" else ""))
        env = dict(os.environ, PIP_INDEX_URL=idx, PIP_DISABLE_PIP_VERSION_CHECK="1", PIP_NO_INPUT="1")
        env.pop("PYTHONPATH", None)
        extra = requirement_args(copy_root)
        log("installing upgraded dependencies in a temporary venv ...")
        r = _run([py, "-m", "pip", "install", "--quiet"] + extra, copy_root, env, timeout)
        if r.returncode:
            return {"status": "failed", "stage": "resolve", "rows": rows, "updated": {}, "detail": _tail(r.stdout)}
        if not test_cmd:
            r = _run([py, "-m", "pip", "install", "--quiet", "pytest"], copy_root, env, timeout)
            if r.returncode:
                return {"status": "failed", "stage": "resolve", "rows": rows, "updated": {}, "detail": _tail(r.stdout)}
        # 3) テスト
        log("running the project's tests on the upgraded versions ...")
        env["PYTHONPATH"] = os.pathsep.join([copy_root, os.path.join(copy_root, "src")])
        if test_cmd:
            cmd = test_cmd.replace("{python}", py)
            r = subprocess.run(cmd, shell=True, cwd=copy_root, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace", timeout=timeout)
        else:
            r = _run([py, "-m", "pytest", "-q", "-p", "no:cacheprovider"], copy_root, env, timeout)
        if r.returncode:
            return {"status": "failed", "stage": "tests", "rows": rows, "updated": {}, "detail": _tail(r.stdout, 40)}
        # 4) 全成功 → 元のファイルを書き換える(途中で失敗したら元に戻す)
        saved = {}
        reqs0, pyp0 = find_files(root)
        try:
            for kind, files in (("req", reqs0), ("py", pyp0)):
                for p in files:
                    old = read_text(p)
                    new = rewrite(old, kind, todo)
                    if new != old:
                        saved[p] = old
                        with open(p, "w", encoding="utf-8", newline="") as fh:
                            fh.write(new)
        except Exception as e:  # noqa: BLE001
            for p, old in saved.items():
                with open(p, "w", encoding="utf-8", newline="") as fh:
                    fh.write(old)
            return {"status": "failed", "stage": "write", "rows": rows, "updated": {}, "detail": str(e)}
        return {"status": "upgraded", "rows": rows, "updated": todo, "files": sorted(os.path.relpath(p, root) for p in saved)}
    finally:
        shutil.rmtree(work, ignore_errors=True)


def format_rows(rows) -> str:
    if not rows:
        return "no pinned (==) dependency found / 固定版(==)の依存は見つかりませんでした"
    w = max(len(r["name"]) for r in rows)
    out = []
    for r in rows:
        mark = "UPGRADE" if r["newer"] else ("unknown" if r["latest"] is None else "ok")
        out.append("%-*s  %-12s -> %-12s  %s%s" % (w, r["name"], r["current"], r["latest"] or "?", mark, "  (different pins in several files)" if r["mixed"] else ""))
    return "\n".join(out)


def run(path: str, check: bool, do_apply: bool, packages=None, all_pins=False, index=None, test_cmd=None, as_json=False) -> int:
    """CLI から呼ぶ。終了コード: 0 正常(更新なし/成功/--check) 1 テスト等で失敗(変更なし) 2 安全に停止(ネットワーク・テスト無しなど)"""
    import json

    for st in (sys.stdout, sys.stderr):  # Windows の cp1252/cp932 でも日本語で落ちない
        try:
            st.reconfigure(errors="replace")
        except Exception:  # noqa: BLE001
            pass
    if not os.path.isdir(path):
        print("not a directory: %s" % path, file=sys.stderr)
        return 2
    try:
        if do_apply:
            res = apply(path, packages, all_pins, index, test_cmd, log=lambda m: print(m, file=sys.stderr))
        else:
            res = {"status": "check", "rows": plan(path, packages, all_pins, index)}
    except UpgradeError as e:
        print("stopped (nothing changed): %s" % e, file=sys.stderr)
        if as_json:
            print(json.dumps({"status": "stopped", "reason": str(e)}, ensure_ascii=False))
        return 2
    if as_json:
        print(json.dumps(res, ensure_ascii=False))
    else:
        print(format_rows(res["rows"]))
        st = res["status"]
        if st == "upgraded":
            print("upgraded and tests passed: %s (files: %s)" % (", ".join("%s %s" % kv for kv in sorted(res["updated"].items())), ", ".join(res["files"])))
        elif st == "uptodate":
            print("already up to date / すべて最新です")
        elif st == "failed":
            print("FAILED at %s - nothing was changed / 失敗(%s)・元のファイルは変更していません" % (res["stage"], res["stage"]))
            print(res["detail"])
        elif st == "check":
            n = sum(1 for r in res["rows"] if r["newer"])
            print("%d package(s) can be upgraded. Nothing was changed; run with --apply to test and upgrade. / %d 件。何も変更していません。--apply で試験のうえ更新します。" % (n, n))
    return 1 if res["status"] == "failed" else 0
