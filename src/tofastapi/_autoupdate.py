"""起動時の自動バージョンアップ(標準ライブラリのみ)。

仕組み: アプリの起動時(`accelerate()` など)に `maybe_start()` を呼ぶ。前回の確認から24時間以上たっていたら、
切り離した子プロセス(`python -m tofastapi._autoupdate`)で GitHub の最新リリースを調べ、新しければ
`pip download --no-index`(PyPI は見ない)でその環境に合うホイールを取得し、**リリースの `<ファイル名>.sha256`
と一致したときだけ** `pip install` する。起動は遅くならない。更新は次回の起動から有効で、その旨を一度だけ表示する。
信頼の根拠は GitHub への TLS と SHA-256(電子署名ではない)。`.sha256` が無いリリースへは更新しない。

止めるには環境変数 ``TOFASTAPI_NO_UPDATE=1``(``CI`` や pytest 実行中も自動で止まる)。失敗は黙って次回に回し、
理由は ``~/.2fastapi/last_error`` に残す。手動実行: ``python -m tofastapi._autoupdate --now``。
"""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request

REPO = "aon-co-jp/2FastAPI"
DIST = "tofastapi"
ENV_OFF = "TOFASTAPI_NO_UPDATE"
STATE_DIRNAME = ".2fastapi"
INTERVAL = 24 * 3600
TRUSTED_PREFIX = "https://github.com/%s/releases/download/" % REPO


def current_version():
    try:
        from importlib.metadata import version

        return version(DIST)
    except Exception:
        return current_version_frozen()


def parse_version(s):
    s = str(s).strip().lstrip("v")
    core = s.split("-")[0].split("+")[0]
    parts = core.split(".")
    try:
        nums = tuple(int(p) for p in parts[:3])
    except ValueError:
        return None
    return nums + (0,) * (3 - len(nums))


def is_newer(tag, current):
    a, b = parse_version(tag), parse_version(current)
    if a is None or b is None or "-" in str(tag):  # 先行版(-alpha 等)へは上げない
        return False
    return a > b


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_sha256_text(text):
    parts = text.split()
    if not parts:
        return None
    h = parts[0].lower()
    return h if len(h) == 64 and all(c in "0123456789abcdef" for c in h) else None


def is_trusted_url(url):
    return url.startswith(TRUSTED_PREFIX)


def disabled():
    v = os.environ.get(ENV_OFF)
    return bool((v and v != "0") or os.environ.get("CI") or os.environ.get("PYTEST_CURRENT_TEST"))


def state_dir():
    return os.path.join(os.path.expanduser("~"), STATE_DIRNAME)


def _read(name):
    try:
        with open(os.path.join(state_dir(), name), encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return None


def _write(name, text):
    try:
        os.makedirs(state_dir(), exist_ok=True)
        with open(os.path.join(state_dir(), name), "w", encoding="utf-8") as f:
            f.write(text)
    except OSError:
        pass


def maybe_start():
    """起動時に呼ぶ。通知と、必要なら切り離した確認の起動だけを行い、すぐ戻る。例外は外へ出さない。"""
    try:
        if disabled():
            return
        if getattr(sys, "frozen", False):
            return _frozen_start()
        done = _read("updated")
        if done:
            sys.stderr.write("%s: %s に更新しました(今回の起動から有効)\n" % (DIST, done))
            try:
                os.remove(os.path.join(state_dir(), "updated"))
            except OSError:
                pass
        try:
            last = float(_read("last_check") or 0)
        except ValueError:
            last = 0
        if time.time() - last < INTERVAL:
            return
        _write("last_check", str(int(time.time())))  # 先に記録(失敗しても連打しない)
        kw = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL, "close_fds": True}
        if os.name == "nt":
            kw["creationflags"] = 0x00000008 | 0x08000000  # DETACHED_PROCESS | CREATE_NO_WINDOW
        else:
            kw["start_new_session"] = True
        subprocess.Popen([sys.executable, "-m", __name__], **kw)
    except Exception:
        pass


SETUP_FLAGS = ["/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS", "/RESTARTAPPLICATIONS"]


def setup_asset_name():
    import platform

    return "2FastAPI-Setup-%s.exe" % ("arm64" if platform.machine().lower() in ("arm64", "aarch64") else "x64")


def _frozen_start():
    """インストーラー版(PyInstaller)。pip は使えないので、公式の Setup を取得・検証して置き、次の起動で静かに実行する。"""
    if os.name != "nt":
        return _frozen_notice()  # .deb / .pkg 版: システム側の管理なので自動では書き換えない(新版の通知だけ)
    pending = os.path.join(state_dir(), "pending-setup.exe")
    if os.path.exists(pending) and _read("pending_version"):
        ver = _read("pending_version")
        for n in ("pending_version",):
            try:
                os.remove(os.path.join(state_dir(), n))
            except OSError:
                pass
        _write("updated", ver)
        subprocess.Popen([pending] + SETUP_FLAGS, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=0x00000008 | 0x08000000)
        return
    try:
        last = float(_read("last_check") or 0)
    except ValueError:
        last = 0
    if time.time() - last < INTERVAL:
        return
    _write("last_check", str(int(time.time())))
    import threading

    def work():
        try:
            fetch_setup()
        except Exception as e:  # noqa: BLE001
            _write("last_error", repr(e))

    threading.Thread(target=work, daemon=True).start()


NOTICE_URL = "https://github.com/%s/releases/latest" % REPO


def _frozen_notice():
    """macOS の .pkg / Linux の .deb 版。自分自身を書き換えず、新しい版があることを一度だけ stderr に知らせる。

    確認は24時間に1回、切り離したスレッドで行う(起動は遅くならない)。導入し直すのは利用者(新しい .pkg / .deb を入れる)。
    """
    ver = _read("available")
    if ver:
        print("%s: 新しい版 %s があります。%s から .pkg / .deb を入れ直してください(自動では更新しません。止めるには %s=1)" % (DIST, ver, NOTICE_URL, ENV_OFF), file=sys.stderr)
        try:
            os.remove(os.path.join(state_dir(), "available"))
        except OSError:
            pass
    try:
        last = float(_read("last_check") or 0)
    except ValueError:
        last = 0
    if time.time() - last < INTERVAL:
        return
    import threading

    threading.Thread(target=check_available, daemon=True).start()


def check_available():
    """最新リリースを調べ、新しければ状態ディレクトリの `available` に版名を書く。版名、無ければ None。"""
    try:
        rel = json.loads(_get("https://api.github.com/repos/%s/releases/latest" % REPO))
        tag = rel["tag_name"]
        _write("last_check", str(int(time.time())))
        if is_newer(tag, current_version_frozen()):
            _write("available", tag.lstrip("v"))
            return tag.lstrip("v")
    except Exception as e:  # noqa: BLE001
        _write("last_error", repr(e))
    return None


def fetch_setup():
    """新しい Setup を取得して sha256 を確かめ、状態ディレクトリへ置く。置いた版名、不要なら None。"""
    cur = current_version_frozen()
    rel = json.loads(_get("https://api.github.com/repos/%s/releases/latest" % REPO))
    tag = rel["tag_name"]
    if not is_newer(tag, cur):
        return None
    assets = {a["name"]: a["browser_download_url"] for a in rel.get("assets", [])}
    name = setup_asset_name()
    url, sha_url = assets.get(name), assets.get(name + ".sha256")
    if not url or not sha_url:
        raise RuntimeError("資産または `.sha256` が無いリリースへは更新しない")
    if not (is_trusted_url(url) and is_trusted_url(sha_url)):
        raise RuntimeError("信頼できない取得先")
    want = parse_sha256_text(_get(sha_url).decode("utf-8", "replace"))
    data = _get(url, timeout=600)
    got = hashlib.sha256(data).hexdigest()
    if want is None or got != want:
        raise RuntimeError("sha256 不一致(期待 %s、実際 %s)" % (want, got))
    os.makedirs(state_dir(), exist_ok=True)
    tmp = os.path.join(state_dir(), "pending-setup.exe.part")
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, os.path.join(state_dir(), "pending-setup.exe"))
    _write("pending_version", tag.lstrip("v"))
    return tag.lstrip("v")


def current_version_frozen():
    try:
        from . import __version__

        return __version__
    except Exception:
        return "0"


def _get(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": DIST + "-updater"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def update_now():
    """最新リリースを調べて必要なら更新する。更新した版名、更新不要なら None。失敗は例外。"""
    cur = current_version()
    rel = json.loads(_get("https://api.github.com/repos/%s/releases/latest" % REPO))
    tag = rel["tag_name"]
    if not is_newer(tag, cur):
        return None
    ver = tag.lstrip("v")
    assets = {a["name"]: a["browser_download_url"] for a in rel.get("assets", [])}
    if not all(is_trusted_url(u) for u in assets.values()):
        raise RuntimeError("信頼できない取得先")
    pip = [sys.executable, "-m", "pip", "--disable-pip-version-check", "--quiet"]
    with tempfile.TemporaryDirectory(prefix=DIST + "-update-") as tmp:
        # PyPI は見ない(同名パッケージの差し替えを避ける)。この環境に合う1つを pip に選ばせる。
        subprocess.run(
            pip + ["download", "--no-deps", "--no-index", "--only-binary=:all:", "-d", tmp, "-f", "https://github.com/%s/releases/expanded_assets/%s" % (REPO, tag), "%s==%s" % (DIST, ver)],
            check=True, timeout=600, stdin=subprocess.DEVNULL,
        )
        files = [f for f in os.listdir(tmp) if f.endswith(".whl")]
        if len(files) != 1:
            raise RuntimeError("ホイールを1つに絞れない: %r" % files)
        path = os.path.join(tmp, files[0])
        sha_url = assets.get(files[0] + ".sha256")
        if not sha_url:
            raise RuntimeError("`.sha256` が無いリリースへは更新しない")
        want = parse_sha256_text(_get(sha_url).decode("utf-8", "replace"))
        got = sha256_file(path)
        if want is None or got != want:
            raise RuntimeError("sha256 不一致(期待 %s、実際 %s)" % (want, got))
        subprocess.run(pip + ["install", "--no-deps", "--no-index", path], check=True, timeout=600, stdin=subprocess.DEVNULL)
    _write("updated", ver)
    return ver


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    now = "--now" in argv
    if disabled() and not now:
        return 0
    if now and disabled():
        print("%s: 自動更新は無効です(環境変数 %s / CI / pytest)" % (DIST, ENV_OFF))
        return 0
    try:
        ver = update_now()
    except Exception as e:  # noqa: BLE001 - 失敗は理由を残して次回へ
        _write("last_error", repr(e))
        if now:
            print("%s: 更新できません: %s" % (DIST, e), file=sys.stderr)
            return 1
        return 0
    if now:
        print("%s: %s" % (DIST, ("%s に更新しました" % ver) if ver else "最新です(%s)" % current_version()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
