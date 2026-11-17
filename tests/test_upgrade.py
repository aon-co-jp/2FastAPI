"""2fastapi upgrade: 実 venv での「上げて試験 -> 成功なら書き換え / 失敗なら元のまま」の両経路。

オフライン: file:// の PEP 503 索引に作り物のホイール(fakedep 1.0 / 2.0 / 3.0b1)を置く。
"""
import json
import os
import subprocess
import sys
import zipfile

import pytest

from tofastapi import upgrade as up


def make_wheel(dirpath, name, version, body):
    fn = "%s-%s-py3-none-any.whl" % (name, version)
    di = "%s-%s.dist-info" % (name, version)
    with zipfile.ZipFile(os.path.join(dirpath, fn), "w") as z:
        z.writestr(name + "/__init__.py", body)
        z.writestr(di + "/METADATA", "Metadata-Version: 2.1\nName: %s\nVersion: %s\n" % (name, version))
        z.writestr(di + "/WHEEL", "Wheel-Version: 1.0\nGenerator: t\nRoot-Is-Purelib: true\nTag: py3-none-any\n")
        z.writestr(di + "/RECORD", "")
    return fn


@pytest.fixture()
def index(tmp_path):
    d = tmp_path / "idx" / "fakedep"
    d.mkdir(parents=True)
    names = [make_wheel(str(d), "fakedep", v, "__version__ = %r\nGOOD = %s\n" % (v, v.startswith(("1.", "2.")))) for v in ("1.0", "2.0", "3.0b1")]
    (d / "index.html").write_text("".join('<a href="%s">%s</a>\n' % (n, n) for n in names), encoding="utf-8")
    return (tmp_path / "idx").as_uri() + "/"


def project(tmp_path, check_body, pin="fakedep==1.0", name="proj"):
    p = tmp_path / name
    p.mkdir()
    (p / "requirements.txt").write_text("# deps\n%s ; python_version >= '3.8'\n" % pin, encoding="utf-8")
    (p / "check.py").write_text(check_body, encoding="utf-8")
    (p / "pyproject.toml").write_text('[project]\nname="x"\nversion="0"\ndependencies = [\n  "%s",\n]\n' % pin, encoding="utf-8")
    return p


def test_version_parsing():
    assert up.is_newer("2.0", "1.9") and up.is_newer("1.10", "1.9") and not up.is_newer("1.0", "1.0.0")
    assert up.parse_version("3.0b1")[1] is True and up.parse_version("3.0")[1] is False
    assert up.rewrite("flask==2.0 ; x\nflask-sqlalchemy == 3.0.1  # c\n", "req", {"flask": "3.1.0", "flask-sqlalchemy": "3.1.1"}) == "flask==3.1.0 ; x\nflask-sqlalchemy == 3.1.1  # c\n"


def test_check_lists_without_changing(tmp_path, index):
    p = project(tmp_path, "pass\n")
    before = (p / "requirements.txt").read_text()
    rows = up.plan(str(p), ["fakedep"], index=index)
    assert rows[0]["current"] == "1.0" and rows[0]["latest"] == "2.0" and rows[0]["newer"]  # 3.0b1 は先行版なので除外
    r = subprocess.run([sys.executable, "-m", "tofastapi", "upgrade", str(p), "--check", "--package", "fakedep", "--index-url", index], capture_output=True, text=True, env=dict(os.environ, TOFASTAPI_NO_UPDATE="1"))
    assert r.returncode == 0 and "fakedep" in r.stdout and "UPGRADE" in r.stdout
    assert (p / "requirements.txt").read_text() == before


def test_apply_success_rewrites_pins(tmp_path, index):
    p = project(tmp_path, "import fakedep, sys\nsys.exit(0 if fakedep.GOOD else 1)\n")
    res = up.apply(str(p), ["fakedep"], index=index, test_cmd='"{python}" check.py')
    assert res["status"] == "upgraded", res
    assert "fakedep==2.0" in (p / "requirements.txt").read_text() and "# deps" in (p / "requirements.txt").read_text()
    assert '"fakedep==2.0"' in (p / "pyproject.toml").read_text()
    assert up.apply(str(p), ["fakedep"], index=index, test_cmd="false")["status"] == "uptodate"


def test_apply_failure_leaves_files_untouched(tmp_path, index):
    p = project(tmp_path, "import fakedep, sys\nsys.exit(0 if fakedep.__version__ == '1.0' else 1)\n")
    before = {f: (p / f).read_text() for f in ("requirements.txt", "pyproject.toml")}
    res = up.apply(str(p), ["fakedep"], index=index, test_cmd='"{python}" check.py')
    assert res["status"] == "failed" and res["stage"] == "tests"
    assert {f: (p / f).read_text() for f in before} == before


def test_resolution_failure_and_no_tests_and_no_network(tmp_path, index):
    p = project(tmp_path, "pass\n", pin="fakedep==1.0")
    (p / "requirements.txt").write_text("fakedep==1.0\nmissing-pkg-xyz==1.0\n")
    before = (p / "requirements.txt").read_text()
    res = up.apply(str(p), ["fakedep"], index=index, test_cmd="true")
    assert res["status"] == "failed" and res["stage"] == "resolve"
    assert (p / "requirements.txt").read_text() == before
    q = project(tmp_path / "q" if (tmp_path / "q").mkdir() is None else tmp_path, "pass\n")
    (q / "check.py").unlink()
    with pytest.raises(up.UpgradeError, match="no tests"):
        up.apply(str(q), ["fakedep"], index=index)
    with pytest.raises(up.UpgradeError, match="network or index"):
        up.plan(str(q), ["fakedep"], index=(tmp_path / "nonexistent").as_uri() + "/x/")


def test_project_pytest_path_real_pypi(tmp_path):
    """実 PyPI で、プロジェクトの pytest が上げた版で走る経路(ネットワーク無しなら飛ばす)。"""
    try:
        latest = up.latest_version("six", up.DEFAULT_INDEX)
    except up.UpgradeError:
        pytest.skip("no network")
    p = tmp_path / "proj"
    (p / "tests").mkdir(parents=True)
    (p / "requirements.txt").write_text("six==1.15.0\n")
    (p / "tests" / "test_six.py").write_text("import six\n\ndef test_ok():\n    assert six.__version__ != ''\n")
    res = up.apply(str(p), ["six"])
    assert res["status"] == "upgraded" and ("six==" + latest) in (p / "requirements.txt").read_text()
    (p / "requirements.txt").write_text("six==1.15.0\n")
    (p / "tests" / "test_six.py").write_text("import six\n\ndef test_pinned():\n    assert six.__version__ == '1.15.0'\n")
    res = up.apply(str(p), ["six"])
    assert res["status"] == "failed" and res["stage"] == "tests"
    assert (p / "requirements.txt").read_text() == "six==1.15.0\n"
