"""DRF ModelViewSet / ModelSerializer + Django models.Model -> SQLAlchemy + pydantic + generated CRUD routes."""
from __future__ import annotations

import os
from typing import Dict, List, Optional

import libcst as cst

from .common import dotted, str_value
from .flask_conv import _code, _kw

# Django field -> (python type, SQLAlchemy column type template)
FIELD_MAP = {
    "CharField": ("str", "String({max_length})"), "SlugField": ("str", "String({max_length})"), "EmailField": ("str", "String({max_length})"),
    "URLField": ("str", "String({max_length})"), "TextField": ("str", "Text"),
    "IntegerField": ("int", "Integer"), "BigIntegerField": ("int", "Integer"), "SmallIntegerField": ("int", "Integer"),
    "PositiveIntegerField": ("int", "Integer"), "FloatField": ("float", "Float"), "BooleanField": ("bool", "Boolean"),
}


def scan_models(root: str) -> Dict[str, dict]:
    """Every `models.py` under root -> {ModelName: {table, fields: [dict]}} (only the simple field types in FIELD_MAP)."""
    out: Dict[str, dict] = {}
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in (".git", "node_modules", "__pycache__", "venv", ".venv", "site-packages", "migrations")]
        if "models.py" not in fns:
            continue
        app = os.path.basename(dp)
        try:
            mod = cst.parse_module(open(os.path.join(dp, "models.py"), encoding="utf-8").read())
        except Exception:
            continue
        for st in mod.body:
            if not isinstance(st, cst.ClassDef) or not any((dotted(b.value) or "").endswith("Model") for b in st.bases):
                continue
            fields = []
            ok = True
            for s2 in st.body.body:
                if not (isinstance(s2, cst.SimpleStatementLine) and s2.body and isinstance(s2.body[0], cst.Assign)):
                    continue
                a = s2.body[0]
                if len(a.targets) != 1 or not isinstance(a.targets[0].target, cst.Name) or not isinstance(a.value, cst.Call):
                    continue
                fcls = (dotted(a.value.func) or "").split(".")[-1]
                if fcls not in FIELD_MAP:
                    ok = False
                    fields.append({"name": a.targets[0].target.value, "unsupported": fcls})
                    continue
                args = list(a.value.args)
                d = _kw(args, "default")
                fields.append({
                    "name": a.targets[0].target.value, "cls": fcls,
                    "max_length": _code(_kw(args, "max_length")) if _kw(args, "max_length") is not None else "255",
                    "null": _kw(args, "null") is not None and dotted(_kw(args, "null")) == "True",
                    "blank": _kw(args, "blank") is not None and dotted(_kw(args, "blank")) == "True",
                    "default": _code(d) if d is not None else None,
                })
            out[st.name.value] = {"table": "%s_%s" % (app, st.name.value.lower()), "fields": fields, "ok": ok}
    return out


def meta_value(cls: cst.ClassDef, key: str):
    """`class Meta: key = ...` -> the CST value or None."""
    for st in cls.body.body:
        if isinstance(st, cst.ClassDef) and st.name.value == "Meta":
            for s2 in st.body.body:
                if isinstance(s2, cst.SimpleStatementLine) and s2.body and isinstance(s2.body[0], cst.Assign):
                    a = s2.body[0]
                    if isinstance(a.targets[0].target, cst.Name) and a.targets[0].target.value == key:
                        return a.value
    return None


def serializer_fields(cls: cst.ClassDef, model: dict) -> Optional[List[dict]]:
    """Fields the ModelSerializer exposes (Meta.fields list or '__all__'; read_only_fields respected)."""
    f = meta_value(cls, "fields")
    names = ["id"] + [x["name"] for x in model["fields"]]
    if f is not None and str_value(f) != "__all__":
        if not isinstance(f, (cst.List, cst.Tuple)):
            return None
        names = [str_value(e.value) for e in f.elements]
        if None in names:
            return None
    ro = meta_value(cls, "read_only_fields")
    rset = set()
    if isinstance(ro, (cst.List, cst.Tuple)):
        rset = {str_value(e.value) for e in ro.elements}
    by = {x["name"]: x for x in model["fields"]}
    res = []
    for n in names:
        if n == "id":
            res.append({"name": "id", "ro": True})
        elif n in by and "unsupported" not in by[n]:
            res.append(dict(by[n], ro=n in rset))
        else:
            return None
    return res


def _pyexpr(fd: dict) -> str:
    typ = FIELD_MAP[fd["cls"]][0]
    return typ


def schema_code(cname: str, fields: List[dict]) -> str:
    lines = ["class %s(BaseModel):" % cname]
    for fd in fields:
        if fd["name"] == "id":
            lines.append("    id: Optional[int] = None")
            continue
        typ = _pyexpr(fd)
        if fd["cls"] in ("CharField", "SlugField", "EmailField", "URLField") and not fd["blank"]:
            rhs = "Field(%s, min_length=1, max_length=%s)" % (fd["default"] if fd["default"] is not None else ("None" if fd["null"] else "..."), fd["max_length"])
        elif fd["cls"] in ("CharField", "SlugField", "EmailField", "URLField"):
            rhs = "Field(%s, max_length=%s)" % (fd["default"] if fd["default"] is not None else ("None" if fd["null"] else repr("")), fd["max_length"])
        elif fd["default"] is not None:
            rhs = fd["default"]
        elif fd["cls"] == "BooleanField":
            rhs = "False"
        elif fd["null"] or fd["blank"]:
            rhs = "None"
        else:
            rhs = None
        if fd["null"] or (rhs == "None"):
            typ = "Optional[%s]" % typ
        lines.append("    %s: %s%s" % (fd["name"], typ, (" = " + rhs) if rhs is not None else ""))
    return "\n".join(lines)


def table_code(mname: str, model: dict) -> str:
    lines = ["class %s(_Base):" % mname, "    __tablename__ = %r" % model["table"], "    id = Column(Integer, primary_key=True, autoincrement=True)"]
    for fd in model["fields"]:
        if "unsupported" in fd:
            continue
        ctype = FIELD_MAP[fd["cls"]][1].format(max_length=fd["max_length"])
        extra = ""
        if fd["null"]:
            extra += ", nullable=True"
        else:
            extra += ", nullable=False"
        if fd["default"] is not None:
            extra += ", default=%s" % fd["default"]
        elif fd["cls"] == "BooleanField":
            extra += ", default=False"
        elif fd["blank"] and not fd["null"]:
            extra += ", default=%s" % ("''" if FIELD_MAP[fd["cls"]][0] == "str" else "None")
        lines.append("    %s = Column(%s%s)" % (fd["name"], ctype, extra))
    return "\n".join(lines)


PRELUDE = '''import os
from sqlalchemy import Boolean, Column, Float, Integer, String, Text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

_url = os.environ.get("DATABASE_URL", "sqlite:///db.sqlite3")
_engine = create_engine(_url, connect_args={"check_same_thread": False}, **({"poolclass": StaticPool} if _url in ("sqlite://", "sqlite:///:memory:") else {}))
_Base = declarative_base()
_Session = sessionmaker(bind=_engine)


def _get_db():
    db = _Session()
    try:
        yield db
    finally:
        db.close()


def _row(obj, names):
    return {n: getattr(obj, n) for n in names}


def _bad(exc):
    errs = {}
    for e in exc.errors():
        errs.setdefault(str(e["loc"][0]) if e["loc"] else "non_field_errors", []).append(e["msg"])
    return JSONResponse(errs, status_code=400)
'''

CREATE_TABLES = "_Base.metadata.create_all(_engine)"


def prelude_code(tables: Dict[str, str]) -> str:
    pre = PRELUDE.replace("from sqlalchemy.orm import", "from pydantic import ValidationError\nfrom sqlalchemy.orm import Session,", 1)
    return pre + "\n\n" + "\n\n\n".join(tables.values()) + "\n\n\n" + CREATE_TABLES + "\n"


def viewset_code(cname: str, mname: str, sname: str, fields: List[dict], paths_list: List[str], paths_detail: List[str], actions: set, ro_names: set) -> str:
    names = [f["name"] for f in fields]
    writable = [n for n in names if n != "id" and n not in ro_names]
    out = []
    pre = "%s_" % cname
    nm = "[%s]" % ", ".join(repr(n) for n in names)
    wr = "[%s]" % ", ".join(repr(n) for n in writable)

    def deco(meth, paths):
        return "\n".join('@router.%s(%r)' % (meth, p) for p in paths)

    if "list" in actions:
        out.append('%s\ndef %slist(db: Session = Depends(_get_db)):\n    return [_row(o, %s) for o in db.query(%s).order_by(%s.id).all()]\n' % (deco("get", paths_list), pre, nm, mname, mname))
    if "create" in actions:
        out.append('''%s
async def %screate(request: Request, db: Session = Depends(_get_db)):
    try:
        data = await request.json()
        item = %s.model_validate({k: v for k, v in data.items() if k in %s})
    except ValidationError as e:
        return _bad(e)
    except Exception:
        return JSONResponse({"non_field_errors": ["Invalid data."]}, status_code=400)
    obj = %s(**{k: getattr(item, k) for k in %s})
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return JSONResponse(_row(obj, %s), status_code=201)
''' % (deco("post", paths_list), pre, sname, wr, mname, wr, nm))
    getter = '''    try:
        obj = db.get(%s, int(pk))
    except ValueError:
        obj = None
    if obj is None:
        return JSONResponse({"detail": "Not found."}, status_code=404)
''' % mname
    if "retrieve" in actions:
        out.append('%s\ndef %sretrieve(pk: str, db: Session = Depends(_get_db)):\n%s    return _row(obj, %s)\n' % (deco("get", paths_detail), pre, getter, nm))
    for act, meth, partial in (("update", "put", False), ("partial_update", "patch", True)):
        if act in actions:
            merge = '    cur = _row(obj, %s)\n' % wr if partial else '    cur = {}\n'
            out.append('''%s
async def %s%s(pk: str, request: Request, db: Session = Depends(_get_db)):
%s%s    try:
        data = await request.json()
        data = {k: v for k, v in data.items() if k in %s}
        item = %s.model_validate({**cur, **data})
    except ValidationError as e:
        return _bad(e)
    except Exception:
        return JSONResponse({"non_field_errors": ["Invalid data."]}, status_code=400)
    for k in data:
        setattr(obj, k, getattr(item, k))
    db.commit()
    db.refresh(obj)
    return _row(obj, %s)
''' % (deco(meth, paths_detail), pre, act, getter, merge, wr, sname, nm))
    if "destroy" in actions:
        out.append('%s\ndef %sdestroy(pk: str, db: Session = Depends(_get_db)):\n%s    db.delete(obj)\n    db.commit()\n    return Response(status_code=204)\n' % (deco("delete", paths_detail), pre, getter))
    return "\n\n".join(out)


