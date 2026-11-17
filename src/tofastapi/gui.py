# -*- coding: utf-8 -*-
"""2FastAPI graphical wizard: pick the source folder, pick projects, pick the destination folder and target, convert.

Folder pickers are the operating system's own file dialogs (File Explorer on Windows).
Languages: English + Japanese together by default; 13 languages selectable.
"""
from __future__ import annotations

import os
import subprocess
import sys
from typing import List

from . import __version__
from .i18n import LANGS, is_rtl, text


def _icon_path() -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    for cand in (os.path.join(base, "2fastapi.ico"), os.path.join(base, "tofastapi", "2fastapi.ico"), os.path.join(os.path.dirname(os.path.abspath(__file__)), "2fastapi.ico")):
        if os.path.isfile(cand):
            return cand
    return ""


def install_shortcut() -> List[str]:
    """Windows: create a desktop shortcut (and a Start menu entry) that opens this wizard with the 2FastAPI icon."""
    if os.name != "nt":
        print("Shortcuts are created on Windows only. / ショートカット作成は Windows のみです。")
        return []
    if getattr(sys, "frozen", False):
        target, args = sys.executable, "gui"
    else:
        exe = sys.executable
        pw = os.path.join(os.path.dirname(exe), "pythonw.exe")
        target, args = (pw if os.path.isfile(pw) else exe), "-m tofastapi gui"
    icon = _icon_path()
    made = []
    ps = (
        "$s=New-Object -ComObject WScript.Shell;"
        "$d=[Environment]::GetFolderPath('Desktop');$m=Join-Path ([Environment]::GetFolderPath('Programs')) '2FastAPI.lnk';"
        "foreach($p in @((Join-Path $d '2FastAPI.lnk'),$m)){$l=$s.CreateShortcut($p);$l.TargetPath='%s';$l.Arguments='%s';"
        "$l.Description='2FastAPI - Flask/Django to FastAPI/MFastAPI';%s$l.Save();Write-Output $p}"
    ) % (target.replace("'", "''"), args, ("$l.IconLocation='%s';" % icon.replace("'", "''")) if icon else "")
    out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True)
    made = [x.strip() for x in out.stdout.splitlines() if x.strip()]
    for m in made:
        print("created:", m)
    if out.returncode != 0:
        print(out.stderr, file=sys.stderr)
    return made


def main(selftest: bool = False, install_shortcut: bool = False) -> int:  # noqa: F811 (flag name mirrors the CLI)
    if install_shortcut:
        return 0 if globals()["_install"]() else 1
    from ._autoupdate import maybe_start

    maybe_start()  # 起動時の自動バージョンアップ(24時間に1回。TOFASTAPI_NO_UPDATE=1 で停止)
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    root = tk.Tk()
    root.title("2FastAPI " + __version__)
    root.geometry("760x560")
    root.minsize(560, 420)
    ic = _icon_path()
    if ic and os.name == "nt":
        try:
            root.iconbitmap(ic)
        except Exception:
            pass

    state = {"lang": "default", "page": 0, "src": "", "dst": "", "projects": [], "checks": [], "target": tk.StringVar(value="fastapi"), "result": None}
    langvar = tk.StringVar(value=LANGS[0][1])
    top = ttk.Frame(root, padding=(12, 8))
    top.pack(fill="x")
    lang_lbl = ttk.Label(top)
    lang_lbl.pack(side="left")
    combo = ttk.Combobox(top, textvariable=langvar, values=[n for _, n, _ in LANGS], state="readonly", width=28)
    combo.pack(side="left", padx=8)
    body = ttk.Frame(root, padding=12)
    body.pack(fill="both", expand=True)
    nav = ttk.Frame(root, padding=12)
    nav.pack(fill="x", side="bottom")  # primary buttons stay pinned to the bottom

    def T(k, **kw):
        return text(state["lang"], k, **kw)

    def anchor():
        return "e" if is_rtl(state["lang"]) else "w"

    def clear():
        for w in body.winfo_children():
            w.destroy()
        for w in nav.winfo_children():
            w.destroy()

    def question(txt):
        ttk.Label(body, text=txt, wraplength=700, justify="right" if is_rtl(state["lang"]) else "left", font=("", 11)).pack(anchor=anchor(), pady=(0, 12), fill="x")

    def folder_row(key):
        row = ttk.Frame(body)
        row.pack(fill="x", pady=4)
        var = tk.StringVar(value=state[key])
        ent = ttk.Entry(row, textvariable=var)
        ent.pack(side="left", fill="x", expand=True)

        def pick():
            d = filedialog.askdirectory(initialdir=var.get() or os.path.expanduser("~"), mustexist=(key == "src"))
            if d:
                var.set(os.path.normpath(d))

        ttk.Button(row, text=T("browse"), command=pick).pack(side="left", padx=(8, 0))
        var.trace_add("write", lambda *_: state.__setitem__(key, var.get()))
        return var, pick

    def render():
        lang_lbl.config(text=T("language"))
        clear()
        p = state["page"]
        if p == 0:
            question(T("q_src"))
            var, pick = folder_row("src")
            ttk.Button(nav, text=T("next"), command=go_scan).pack(side="right")
            if not state["src"] and not selftest:
                root.after(200, pick)  # open the file dialog straight away, as asked
        elif p == 1:
            question(T("found", n=len(state["projects"])) if state["projects"] else T("none"))
            state["checks"] = []
            box = ttk.Frame(body)
            box.pack(fill="both", expand=True)
            for pr in state["projects"]:
                v = tk.BooleanVar(value=True)
                state["checks"].append(v)
                rel = os.path.relpath(pr.path, state["src"]) if os.path.abspath(pr.path) != os.path.abspath(state["src"]) else "."
                ttk.Checkbutton(box, variable=v, text="%s  [%s]  ~%d routes  %s" % (pr.name, pr.kind, pr.routes, rel)).pack(anchor="w")
            ttk.Button(nav, text=T("back"), command=lambda: goto(0)).pack(side="left")
            if state["projects"]:
                ttk.Button(nav, text=T("next"), command=go_dst).pack(side="right")
        elif p == 2:
            question(T("q_dst"))
            if not state["dst"]:
                state["dst"] = os.path.abspath(state["src"]).rstrip("\\/") + "-fastapi"
            folder_row("dst")
            ttk.Label(body, text=T("q_target")).pack(anchor=anchor(), pady=(16, 4))
            ttk.Radiobutton(body, text=T("t_fastapi"), variable=state["target"], value="fastapi").pack(anchor=anchor())
            ttk.Radiobutton(body, text=T("t_mfastapi"), variable=state["target"], value="mfastapi").pack(anchor=anchor())
            ttk.Button(nav, text=T("back"), command=lambda: goto(1)).pack(side="left")
            ttk.Button(nav, text=T("convert"), command=go_convert).pack(side="right")
        else:
            r = state["result"] or {"n": 0, "w": 0, "dest": state["dst"], "err": ""}
            if r.get("err"):
                question(T("err") + ": " + r["err"])
            else:
                question(T("done", n=r["n"], w=r["w"]))
            ttk.Button(nav, text=T("close"), command=root.destroy).pack(side="right")
            if not r.get("err"):
                ttk.Button(nav, text=T("open"), command=lambda: _open_folder(r["dest"])).pack(side="right", padx=8)

    def goto(p):
        state["page"] = p
        render()

    def go_scan():
        src = state["src"].strip()
        if not src or not os.path.isdir(src):
            messagebox.showwarning("2FastAPI", T("q_src"))
            return
        try:
            from .scan import scan
        except Exception:
            messagebox.showerror("2FastAPI", T("missing"))
            return
        try:
            state["projects"] = scan(src)
        except ImportError:
            messagebox.showerror("2FastAPI", T("missing"))
            return
        state["dst"] = ""
        goto(1)

    def go_dst():
        if not any(v.get() for v in state["checks"]):
            messagebox.showwarning("2FastAPI", T("nosel"))
            return
        goto(2)

    def go_convert():
        dst = state["dst"].strip()
        if not dst:
            messagebox.showwarning("2FastAPI", T("nodst"))
            return
        chosen = [p for p, v in zip(state["projects"], state["checks"]) if v.get()]
        if os.path.abspath(dst) == os.path.abspath(state["src"]):
            messagebox.showwarning("2FastAPI", T("same"))
            return
        try:
            from .scan import convert_project_to

            n = w = 0
            for pr in chosen:
                out = os.path.join(dst, pr.name) if len(chosen) > 1 else dst
                _, warns = convert_project_to(pr, out, state["target"].get())
                n += 1
                w += len(warns)
            state["result"] = {"n": n, "w": w, "dest": dst, "err": ""}
        except Exception as e:  # shown to the user, never silent
            state["result"] = {"n": 0, "w": 0, "dest": dst, "err": "%s: %s" % (type(e).__name__, e)}
        goto(3)

    def on_lang(_=None):
        for c, n, _d in LANGS:
            if n == langvar.get():
                state["lang"] = c
        render()

    combo.bind("<<ComboboxSelected>>", on_lang)
    render()
    if selftest:
        # build every page in every language, then exit (used by tests / CI)
        for c, _n, _d in LANGS:
            state["lang"] = c
            for pg in (0, 1, 2, 3):
                state["page"] = pg
                render()
        root.update_idletasks()
        root.destroy()
        print("gui selftest ok")
        return 0
    root.mainloop()
    return 0


def _open_folder(path: str) -> None:
    try:
        if os.name == "nt":
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception:
        pass


_install = install_shortcut
