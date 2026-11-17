"""Flask -> FastAPI converter (libcst: comments and formatting are kept)."""
from __future__ import annotations

from typing import List, Optional, Set

import libcst as cst
from libcst.metadata import MetadataWrapper, PositionProvider

from .common import (
    ParamSet,
    Result,
    Warn,
    convert_rule,
    count_name,
    dotted,
    ident,
    is_stringish,
    make_param,
    order_params,
    str_value,
)

HTTP_SHORTCUTS = {"get", "post", "put", "delete", "patch", "head", "options"}
UNSUPPORTED_NAMES = {
    "session": "flask.session (use starlette SessionMiddleware: `app.add_middleware(SessionMiddleware, secret_key=...)` and `request.session`)",
    "g": "flask.g (use request.state or dependencies)",
    "flash": "flask.flash",
    "get_flashed_messages": "flask.get_flashed_messages",
    "current_app": "flask.current_app (use the `app` object or request.app)",
    "make_response": "flask.make_response (return a fastapi Response)",
    "send_file": "flask.send_file (use fastapi.responses.FileResponse)",
    "send_from_directory": "flask.send_from_directory (use FileResponse / StaticFiles)",
    "stream_with_context": "flask.stream_with_context (use StreamingResponse)",
    "render_template": "flask.render_template (use fastapi.templating.Jinja2Templates: `templates.TemplateResponse(request, name, ctx)`)",
    "render_template_string": "flask.render_template_string",
    "Response": "flask.Response (use fastapi.Response; arguments differ: status -> status_code, mimetype -> media_type)",
    "after_this_request": "flask.after_this_request",
    "has_request_context": "flask.has_request_context",
}
KNOWN_EXT = {
    "flask_sqlalchemy": "Flask-SQLAlchemy: not converted. Use SQLAlchemy sessions with a `Depends(get_db)` dependency.",
    "flask_login": "Flask-Login: not converted. Use `fastapi.security` / a `Depends(current_user)` dependency.",
    "flask_wtf": "Flask-WTF: not converted. Use pydantic models for form validation.",
    "flask_migrate": "Flask-Migrate: use Alembic directly.",
    "flask_restful": "Flask-RESTful: Resource classes are not converted; rewrite each method as a route.",
    "flask_marshmallow": "Flask-Marshmallow: use pydantic models.",
    "flask_jwt_extended": "Flask-JWT-Extended: use fastapi.security (OAuth2PasswordBearer) with PyJWT.",
    "flask_socketio": "Flask-SocketIO: use FastAPI WebSockets or python-socketio ASGI app.",
    "flask_caching": "Flask-Caching: use fastapi-cache2 or your own dependency.",
    "flask_limiter": "Flask-Limiter: use slowapi.",
    "flask_session": "Flask-Session: use starlette SessionMiddleware.",
    "flask_babel": "Flask-Babel: not converted.",
    "flask_mail": "Flask-Mail: use fastapi-mail.",
    "flask_compress": "Flask-Compress: use starlette GZipMiddleware.",
}


def _code(node: cst.CSTNode) -> str:
    return cst.Module([]).code_for_node(node)


def _kw(args, name: str):
    for a in args:
        if a.keyword is not None and a.keyword.value == name:
            return a.value
    return None


def _pos(args):
    return [a for a in args if a.keyword is None and a.star == ""]


def _literal_type(node: cst.CSTNode) -> Optional[str]:
    if isinstance(node, cst.Integer):
        return "int"
    if isinstance(node, cst.Float):
        return "float"
    if isinstance(node, (cst.SimpleString, cst.FormattedString)):
        return "str"
    if isinstance(node, cst.Name) and node.value in ("True", "False"):
        return "bool"
    return None


class BodyRewriter(cst.CSTTransformer):
    """Rewrites the Flask request/response API inside one view function body."""

    def __init__(self, notes: List[str]):
        super().__init__()
        self.params = ParamSet()
        self.fastapi: Set[str] = set()
        self.responses: Set[str] = set()
        self.typing: Set[str] = set()
        self.need_uuid = False
        self.notes = notes  # human readable warnings for this view
        self.depth = 0
        self.need_request = False
        self.need_templates = False
        self.need_upload = False
        self.need_session = False
        self.flask_names: Set[str] = set()

    # ---- flask.session / flask.g
    def leave_Name(self, original, updated):
        v = original.value
        if v in ("session", "g") and v in self.flask_names:
            self.need_request = True
            if v == "session":
                self.need_session = True
                return cst.parse_expression("request.session")
            return cst.parse_expression("request.state")
        return updated

    def leave_Arg(self, original, updated):
        if original.keyword is not None and original.keyword.value in ("session", "g"):
            return updated.with_changes(keyword=original.keyword)
        return updated

    def leave_Param(self, original, updated):
        return updated.with_changes(name=original.name)

    # ---- nested defs keep their own returns
    def visit_FunctionDef(self, node: cst.FunctionDef):
        self.depth += 1

    def leave_FunctionDef(self, original, updated):
        self.depth -= 1
        return updated

    def visit_Lambda(self, node):
        self.depth += 1

    def leave_Lambda(self, original, updated):
        self.depth -= 1
        return updated

    # ---- request accessors
    def _param(self, key: str, kind: str, default_node, type_node, required: bool) -> cst.Name:
        name = ident(key)
        ann = _code(type_node) if type_node is not None else None
        dflt = _code(default_node) if default_node is not None else None
        if ann is None:
            ann = "str"  # request values are strings unless type= is given (keeps Flask/Django semantics)
        if kind == "body":
            self.fastapi.add("Body")
            self.typing.add("Any")
            if required:
                self.params.add(name, "Any", "Body(..., embed=True)")
            else:
                self.typing.add("Optional")
                self.params.add(name, "Optional[Any]", "Body(%s, embed=True)" % (dflt if dflt is not None else "None"))
        elif kind == "query":
            if required:
                self.params.add(name, ann or "str", None)
            elif dflt is None:
                self.typing.add("Optional")
                self.params.add(name, "Optional[%s]" % (ann or "str"), "None")
            else:
                self.params.add(name, ann, dflt) if ann else self.params.add(name, "str", dflt)
        else:
            cls = {"form": "Form", "header": "Header", "cookie": "Cookie"}[kind]
            self.fastapi.add(cls)
            if required:
                self.params.add(name, ann or "str", "%s(...)" % cls)
            elif dflt is None:
                self.typing.add("Optional")
                self.params.add(name, "Optional[%s]" % (ann or "str"), "%s(None)" % cls)
            else:
                self.params.add(name, ann or "str", "%s(%s)" % (cls, dflt))
        return cst.Name(name)

    def leave_Call(self, original, updated):
        d = dotted(updated.func)
        args = list(updated.args)
        pos = _pos(args)
        if d in ("request.args.get", "request.values.get", "request.form.get", "request.headers.get", "request.cookies.get") and pos:
            key = str_value(pos[0].value)
            if key is None:
                self.notes.append("dynamic key in %s(...) was left unchanged" % d)
                return updated
            kind = {"args": "query", "values": "query", "form": "form", "headers": "header", "cookies": "cookie"}[d.split(".")[1]]
            if kind == "header":
                key = key.lower().replace("-", "_")
            default = pos[1].value if len(pos) > 1 else _kw(args, "default")
            return self._param(key, kind, default, _kw(args, "type"), False)
        if d == "request.args.getlist" and pos and str_value(pos[0].value):
            name = ident(str_value(pos[0].value))
            self.fastapi.add("Query")
            self.typing.add("List")
            self.params.add(name, "List[str]", "Query(default=[])")
            return cst.Name(name)
        if d == "request.get_json":
            self.fastapi.add("Body")
            self.typing.add("Any")
            self.params.add("payload", "Any", "Body(None)")
            return cst.Name("payload")
        if d == "jsonify":
            if not args:
                return cst.parse_expression("{}")
            if len(args) == 1 and args[0].keyword is None and args[0].star == "":
                return args[0].value.with_changes() if not isinstance(args[0].value, cst.Name) else args[0].value
            if all(a.keyword is not None for a in args):
                return updated.with_changes(func=cst.Name("dict"))
            return cst.List([cst.Element(a.value) for a in args])
        if d == "redirect" and pos:
            self.responses.add("RedirectResponse")
            code = pos[1].value if len(pos) > 1 else _kw(args, "code")
            return cst.parse_expression("RedirectResponse(%s, status_code=%s)" % (_code(pos[0].value), _code(code) if code is not None else "302"))
        if d == "url_for" and pos and str_value(pos[0].value):
            if str_value(pos[0].value) == "static" or "." in str_value(pos[0].value):
                self.notes.append("url_for('%s') (static files / blueprint endpoint) was left unchanged" % str_value(pos[0].value))
                return updated
            self.need_request = True
            rest = ", ".join(_code(a) for a in args[1:])
            return cst.parse_expression("str(request.url_for(%s%s))" % (_code(pos[0].value), (", " + rest) if rest else ""))
        if d == "render_template" and pos and str_value(pos[0].value) is not None:
            self.need_request = True
            self.need_templates = True
            entries = []
            for a in args[1:]:
                if a.keyword is not None:
                    entries.append("%r: %s" % (a.keyword.value, _code(a.value)))
                elif a.star == "**":
                    entries.append("**%s" % _code(a.value))
            self.notes.append("render_template -> Jinja2Templates: check url_for(...) inside the templates")
            return cst.parse_expression("templates.TemplateResponse(request, %s, {%s})" % (_code(pos[0].value), ", ".join(entries)))
        if d == "request.files.get" and pos and str_value(pos[0].value):
            name = ident(str_value(pos[0].value))
            self.fastapi |= {"File", "UploadFile"}
            self.typing.add("Optional")
            self.params.add(name, "Optional[UploadFile]", "File(None)")
            self.need_upload = True
            self.notes.append("request.files -> UploadFile wrapped in _Upload (sync read()/save()/filename, like Werkzeug FileStorage)")
            return cst.parse_expression("_Upload(%s)" % name) if False else cst.parse_expression("(_Upload(%s) if %s is not None else None)" % (name, name))
        if d in ("render_template", "render_template_string", "make_response", "send_file", "send_from_directory", "flash", "stream_with_context"):
            self.notes.append("%s(...) is not converted automatically" % d)
        return updated

    def leave_Subscript(self, original, updated):
        d = dotted(updated.value)
        if d in ("request.args", "request.values", "request.form", "request.headers", "request.cookies") and len(updated.slice) == 1:
            el = updated.slice[0].slice
            key = str_value(el.value) if isinstance(el, cst.Index) else None
            if key is not None:
                kind = {"args": "query", "values": "query", "form": "form", "headers": "header", "cookies": "cookie"}[d.split(".")[1]]
                if kind == "header":
                    key = key.lower().replace("-", "_")
                return self._param(key, kind, None, None, True)
        if d == "request.files" and len(updated.slice) == 1:
            el = updated.slice[0].slice
            key = str_value(el.value) if isinstance(el, cst.Index) else None
            if key is not None:
                name = ident(key)
                self.fastapi |= {"File", "UploadFile"}
                self.params.add(name, "UploadFile", "File(...)")
                self.need_upload = True
                self.notes.append("request.files -> UploadFile wrapped in _Upload (sync read()/save()/filename, like Werkzeug FileStorage)")
                return cst.parse_expression("_Upload(%s)" % name)
        return updated

    def leave_Attribute(self, original, updated):
        if original.attr.value in ("session", "g"):
            updated = updated.with_changes(attr=original.attr)
        d = dotted(updated)
        if d == "request.json":
            self.fastapi.add("Body")
            self.typing.add("Any")
            self.params.add("payload", "Any", "Body(None)")
            return cst.Name("payload")
        if d == "request.path":
            return cst.parse_expression("request.url.path")
        if d == "request.remote_addr":
            return cst.parse_expression("request.client.host")
        if d == "request.is_json":
            self.notes.append("request.is_json has no equivalent (check the Content-Type header)")
        return updated

    # ---- statements / returns
    def leave_SimpleStatementLine(self, original, updated):
        if len(updated.body) == 1 and isinstance(updated.body[0], cst.Assign):
            a = updated.body[0]
            if len(a.targets) == 1 and isinstance(a.targets[0].target, cst.Name) and isinstance(a.value, cst.Name) and a.value.value == a.targets[0].target.value:
                return cst.RemoveFromParent()  # `q = q` left over from parameter extraction
        if len(updated.body) == 1 and isinstance(updated.body[0], cst.Expr) and isinstance(updated.body[0].value, cst.Call):
            call = updated.body[0].value
            if dotted(call.func) == "abort" and call.args:
                pos = _pos(list(call.args))
                code = _code(pos[0].value)
                detail = None
                if len(pos) > 1:
                    detail = _code(pos[1].value)
                elif _kw(call.args, "description") is not None:
                    detail = _code(_kw(call.args, "description"))
                elif _kw(call.args, "message") is not None:
                    detail = _code(_kw(call.args, "message"))
                self.fastapi.add("HTTPException")
                src = "raise HTTPException(status_code=%s%s)" % (code, (", detail=" + detail) if detail else "")
                new = cst.parse_statement(src)
                return new.with_changes(leading_lines=updated.leading_lines)
        return updated

    def leave_Return(self, original, updated):
        if self.depth > 0 or updated.value is None:
            return updated
        v, ov = updated.value, original.value
        if isinstance(ov, cst.Tuple) and 2 <= len(ov.elements) <= 3 and isinstance(v, cst.Tuple):
            body_o = ov.elements[0].value
            body, status = v.elements[0].value, v.elements[1].value
            headers = v.elements[2].value if len(v.elements) == 3 else None
            is_json = isinstance(body_o, (cst.Dict, cst.List)) or (isinstance(body_o, cst.Call) and dotted(body_o.func) == "jsonify") or not is_stringish(body_o)
            cls = "JSONResponse" if is_json else "HTMLResponse"
            self.responses.add(cls)
            extra = (", headers=%s" % _code(headers)) if headers is not None else ""
            expr = "%s(content=%s, status_code=%s%s)" % (cls, _code(body), _code(status), extra)
            return updated.with_changes(value=cst.parse_expression(expr))
        if is_stringish(v):
            self.responses.add("HTMLResponse")
            return updated.with_changes(value=cst.parse_expression("HTMLResponse(content=%s)" % _code(v)))
        return updated


class _PostRewriter(cst.CSTTransformer):
    """Second pass: bare request.args / request.cookies etc. that the first pass could not turn into parameters."""

    def __init__(self):
        super().__init__()
        self.query_params = False

    def leave_Attribute(self, original, updated):
        if dotted(updated) == "request.args":
            self.query_params = True
            return cst.parse_expression("request.query_params")
        return updated


class FlaskConverter(cst.CSTTransformer):
    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(self):
        super().__init__()
        self.warnings: List[Warn] = []
        self.apps: Set[str] = set()
        self.routers: Set[str] = set()
        self.imported: Set[str] = set()
        self.fastapi: Set[str] = {"FastAPI"}
        self.responses: Set[str] = set()
        self.typing: Set[str] = set()
        self.need_uvicorn = False
        self.need_uuid = False
        self.need_cors = False
        self.used_router = False
        self.routes = 0
        self.warned_config = False
        self.hooks = []
        self.need_templates = False
        self.need_upload = False
        self.need_session = False
        self.need_sqla = False
        self.need_login = False
        self.login_vars = []
        self.sqla_vars = []
        self.uses_config = False
        self.flask_names: Set[str] = set()
        self.classviews = {}  # name -> ClassDef (Flask-RESTful Resource / MethodView)
        self.class_routes = {}  # name -> [(obj, rule)]
        self.api_obj = {}  # flask_restful Api variable -> app/blueprint name

    def _line(self, node) -> int:
        try:
            return self.get_metadata(PositionProvider, node).start.line
        except Exception:
            return 0

    def warn(self, node, code: str, msg: str):
        self.warnings.append(Warn(self._line(node), code, msg))

    # ---- imports
    def visit_Module(self, node: cst.Module):
        names_app, names_bp = set(), set()

        class Scan(cst.CSTVisitor):
            def visit_Assign(self, n: cst.Assign):
                if isinstance(n.value, cst.Call) and len(n.targets) == 1 and isinstance(n.targets[0].target, cst.Name):
                    f = dotted(n.value.func)
                    if f in ("Flask", "flask.Flask"):
                        names_app.add(n.targets[0].target.value)
                    elif f in ("Blueprint", "flask.Blueprint"):
                        names_bp.add(n.targets[0].target.value)

        node.visit(Scan())
        self.apps, self.routers = names_app, names_bp
        import re as _re

        self.uses_config = any(_re.search(r"\b%s\.config\b" % _re.escape(a), cst.Module([]).code_for_node(node)) for a in names_app)

    def leave_ImportFrom(self, original, updated):
        mod = dotted(updated.module) if updated.module is not None else None
        if mod == "flask.views":
            return cst.RemoveFromParent()
        if mod == "flask":
            if isinstance(updated.names, cst.ImportStar):
                self.warn(original, "import-star", "`from flask import *` cannot be converted precisely")
            else:
                for alias in updated.names:
                    n = alias.name.value
                    self.imported.add(alias.asname.name.value if alias.asname is not None else n)
                    if n in ("session", "g") and alias.asname is None:
                        self.flask_names.add(n)
                        if n == "session":
                            self.warn(original, "session", "flask.session -> request.session (Starlette SessionMiddleware, secret from env SECRET_KEY: set a real one; the cookie format differs from Flask's)")
                        else:
                            self.warn(original, "flask-g", "flask.g -> request.state (per-request, set attributes only)")
                    elif n in UNSUPPORTED_NAMES:
                        self.warn(original, "flask-api", UNSUPPORTED_NAMES[n])
            return cst.RemoveFromParent()
        if mod == "flask_sqlalchemy":
            self.need_sqla = True
            self.fastapi.add("HTTPException")
            self.warn(original, "flask-sqlalchemy", "Flask-SQLAlchemy -> a small SQLAlchemy shim (_SQLAlchemy: db.Model/db.session/Model.query/create_all, session scoped per request). Set SQLALCHEMY_DATABASE_URI in app.config or env DATABASE_URL")
            return cst.RemoveFromParent()
        if mod == "flask_login":
            self.need_login = True
            self.need_session = True
            self.responses.add("RedirectResponse")
            self.fastapi.add("HTTPException")
            self.warn(original, "flask-login", "Flask-Login -> a small session based shim (LoginManager/UserMixin/login_user/logout_user/current_user/login_required on request.session). Set a real SECRET_KEY; `fresh_login_required` behaves like `login_required` and remember-me cookies are not issued (session only)")
            return cst.RemoveFromParent()
        if mod == "flask_cors":
            self.need_cors = True
            return cst.RemoveFromParent()
        if mod == "flask_restful":
            names = [a.name.value for a in updated.names] if not isinstance(updated.names, cst.ImportStar) else []
            extra = [n for n in names if n not in ("Api", "Resource", "abort")]
            if extra:
                self.warn(original, "extension", "flask_restful %s: not converted (use pydantic models / Body())" % ", ".join(extra))
            return cst.RemoveFromParent()
        if mod and mod.split(".")[0] in KNOWN_EXT:
            self.warn(original, "extension", KNOWN_EXT[mod.split(".")[0]])
        return updated

    def leave_Import(self, original, updated):
        for alias in updated.names:
            n = dotted(alias.name) or ""
            if n == "flask":
                self.warn(original, "import-flask", "`import flask` usage (flask.xxx) is not converted; use `from flask import ...` style or convert by hand")
            elif n.split(".")[0] in KNOWN_EXT:
                self.warn(original, "extension", KNOWN_EXT[n.split(".")[0]])
        return updated

    # ---- app objects
    def leave_Assign(self, original, updated):
        if isinstance(updated.value, cst.Call) and len(updated.targets) == 1:
            f = dotted(updated.value.func)
            if f in ("Flask", "flask.Flask"):
                extra = [a for a in updated.value.args[1:] if a.keyword is not None and a.keyword.value in ("template_folder", "static_folder", "static_url_path", "instance_path")]
                if extra:
                    self.warn(original, "flask-app", "Flask(%s) options (templates/static) are not converted: use Jinja2Templates / app.mount('/static', StaticFiles(...))" % ", ".join(a.keyword.value for a in extra))
                return updated.with_changes(value=cst.parse_expression("FastAPI()"))
            if f in ("LoginManager", "flask_login.LoginManager") and isinstance(updated.targets[0].target, cst.Name):
                self.need_login = True
                self.login_vars.append(updated.targets[0].target.value)
                return updated.with_changes(value=cst.parse_expression("_LoginManager()"))
            if f in ("SQLAlchemy", "flask_sqlalchemy.SQLAlchemy") and isinstance(updated.targets[0].target, cst.Name):
                self.need_sqla = True
                self.fastapi.add("HTTPException")
                var = updated.targets[0].target.value
                self.sqla_vars.append(var)
                first = sorted(self.apps)[0] if self.apps else "None"
                return updated.with_changes(value=cst.parse_expression("_SQLAlchemy(%s)" % first))
            if f in ("Api", "flask_restful.Api") and isinstance(updated.targets[0].target, cst.Name):
                a0 = updated.value.args[0].value if updated.value.args else None
                self.api_obj[updated.targets[0].target.value] = a0.value if isinstance(a0, cst.Name) else "app"
                return cst.RemoveFromParent()
            if f in ("Blueprint", "flask.Blueprint"):
                self.fastapi.add("APIRouter")
                prefix = _kw(updated.value.args, "url_prefix")
                return updated.with_changes(value=cst.parse_expression("APIRouter(%s)" % (("prefix=" + _code(prefix)) if prefix is not None else "")))
        return updated

    def leave_SimpleStatementLine(self, original, updated):
        if len(updated.body) == 1 and isinstance(updated.body[0], cst.Expr) and isinstance(updated.body[0].value, cst.Call):
            call = updated.body[0].value
            d = dotted(call.func) or ""
            parts = d.split(".")
            if len(parts) == 2 and parts[0] in self.apps and parts[1] == "run":
                self.need_uvicorn = True
                kws = []
                for a in call.args:
                    if a.keyword is not None and a.keyword.value in ("host", "port"):
                        kws.append("%s=%s" % (a.keyword.value, _code(a.value)))
                    elif a.keyword is not None and a.keyword.value == "debug":
                        self.warn(original, "debug", "app.run(debug=...) -> run `uvicorn module:app --reload` for auto-reload")
                new = cst.parse_statement("uvicorn.run(%s%s)" % (parts[0], (", " + ", ".join(kws)) if kws else ""))
                return new.with_changes(leading_lines=updated.leading_lines)
            if len(parts) == 2 and parts[1] == "init_app" and (parts[0] in self.sqla_vars or parts[0] in self.login_vars):
                return cst.RemoveFromParent()
            if len(parts) == 2 and parts[1] == "register_blueprint" and call.args:
                prefix = _kw(call.args[1:], "url_prefix")
                new = cst.parse_statement("%s.include_router(%s%s)" % (parts[0], _code(call.args[0].value), (", prefix=" + _code(prefix)) if prefix is not None else ""))
                return new.with_changes(leading_lines=updated.leading_lines)
            if len(parts) == 2 and parts[1] == "add_resource" and len(call.args) >= 2 and isinstance(call.args[0].value, cst.Name):
                target = self.api_obj.get(parts[0], parts[0])
                for a in call.args[1:]:
                    if a.keyword is None and str_value(a.value):
                        self.class_routes.setdefault(call.args[0].value.value, []).append((target, str_value(a.value)))
                return cst.RemoveFromParent()
            if len(parts) == 2 and parts[1] == "add_url_rule" and call.args:
                rule = str_value(call.args[0].value)
                vf = _kw(call.args, "view_func")
                if rule and isinstance(vf, cst.Call) and isinstance(vf.func, cst.Attribute) and vf.func.attr.value == "as_view" and isinstance(vf.func.value, cst.Name):
                    self.class_routes.setdefault(vf.func.value.value, []).append((parts[0], rule))
                    return cst.RemoveFromParent()
            if d == "CORS" and call.args:
                self.need_cors = True
                app = _code(call.args[0].value)
                new = cst.parse_statement('%s.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])' % app)
                return new.with_changes(leading_lines=updated.leading_lines)
            if len(parts) == 2 and parts[0] in self.apps and parts[1] in ("before_request", "after_request", "errorhandler"):
                self.warn(original, "hooks", "app.%s(...) is not converted: use middleware (`@app.middleware('http')`) / exception handlers" % parts[1])
        return updated

    def leave_With(self, original, updated):
        if len(updated.items) == 1 and isinstance(updated.items[0].item, cst.Call):
            d = dotted(updated.items[0].item.func) or ""
            if d.endswith(".app_context") or d.endswith(".test_request_context"):
                if isinstance(updated.body, cst.IndentedBlock):
                    return cst.FlattenSentinel(list(updated.body.body))
        return updated

    # ---- routes
    def _routes_of(self, fn: cst.FunctionDef):
        """[(object, path, methods)], other decorators"""
        routes, others = [], []
        for dec in fn.decorators:
            c = dec.decorator
            if isinstance(c, cst.Attribute) and isinstance(c.value, cst.Name) and (c.value.value in self.apps or c.value.value in self.routers):
                if c.attr.value in ("before_request", "after_request", "teardown_request", "teardown_appcontext", "before_first_request"):
                    self.hooks.append((c.value.value, c.attr.value, dec))
                    continue
                if c.attr.value in ("context_processor", "template_filter"):
                    self.warn(fn, "hooks", "@%s.%s is not converted (use middleware / exception handlers)" % (c.value.value, c.attr.value))
            if isinstance(c, cst.Call) and isinstance(c.func, cst.Attribute) and isinstance(c.func.value, cst.Name):
                obj, attr = c.func.value.value, c.func.attr.value
                if obj in self.apps or obj in self.routers:
                    if attr == "route" or attr in HTTP_SHORTCUTS:
                        args = list(c.args)
                        pos = _pos(args)
                        rule = str_value(pos[0].value) if pos else str_value(_kw(args, "rule"))
                        if rule is None:
                            self.warn(fn, "dynamic-route", "route rule is not a string literal: left unchanged")
                            others.append(dec)
                            continue
                        if attr == "route":
                            m = _kw(args, "methods")
                            if m is None:
                                methods = ["GET"]
                            elif isinstance(m, (cst.List, cst.Tuple, cst.Set)) and all(str_value(e.value) for e in m.elements):
                                methods = [str_value(e.value).upper() for e in m.elements]
                            else:
                                self.warn(fn, "dynamic-route", "`methods=` is not a literal list: left unchanged")
                                others.append(dec)
                                continue
                        else:
                            methods = [attr.upper()]
                        routes.append((obj, rule, methods))
                        continue
                    if attr in ("errorhandler", "before_request", "after_request", "teardown_request", "teardown_appcontext", "before_first_request"):
                        self.hooks.append((obj, attr, dec))
                        continue
                    if attr in ("context_processor", "template_filter"):
                        self.warn(fn, "hooks", "@%s.%s is not converted (use middleware / exception handlers)" % (obj, attr))
            others.append(dec)
        return routes, others

    def leave_FunctionDef(self, original, updated):
        self.hooks = []
        routes, others = self._routes_of(updated)
        if self.hooks and not routes:
            return self._convert_hook(original, updated, self.hooks, others)
        if not routes:
            if any(isinstance(d.decorator, cst.Attribute) and isinstance(d.decorator.value, cst.Name) and d.decorator.value.value in self.login_vars
                   and d.decorator.attr.value in ("user_loader", "request_loader", "unauthorized_handler") for d in updated.decorators):
                notes: List[str] = []
                rw = BodyRewriter(notes)
                rw.flask_names = self.flask_names
                body = updated.body.visit(rw).visit(_PostRewriter())
                self.fastapi |= rw.fastapi
                self.responses |= rw.responses
                self.typing |= rw.typing
                return updated.with_changes(body=body)
            return updated
        return self._convert_view(original, updated, routes, others)

    def _convert_hook(self, original, updated, hooks, others):
        obj, attr, dec = hooks[0]
        notes: List[str] = []
        rw = BodyRewriter(notes)
        rw.flask_names = self.flask_names
        body = updated.body.visit(rw)
        body = body.visit(_PostRewriter())
        self.fastapi.add("Request")
        for n in notes:
            self.warn(original, "convert", "%s: %s" % (original.name.value, n))
        if rw.params.order:
            self.warn(original, "hooks", "%s uses request parameters that cannot be injected into middleware: left unchanged" % original.name.value)
            return updated
        self.fastapi |= rw.fastapi
        self.responses |= rw.responses
        self.typing |= rw.typing
        if attr == "errorhandler":
            call = dec.decorator
            if not call.args:
                return updated
            src = "%s.exception_handler(%s)" % (obj, _code(call.args[0].value))
            first = updated.params.params[0].name.value if updated.params.params else "e"
            params = updated.params.with_changes(params=[make_param("request", "Request", None), make_param(first, None, None)])
            return updated.with_changes(decorators=[cst.Decorator(decorator=cst.parse_expression(src))] + others, params=params, body=body)
        if attr == "before_first_request":
            return updated.with_changes(decorators=[cst.Decorator(decorator=cst.parse_expression('%s.on_event("startup")' % obj))] + others, body=body)
        if attr in ("teardown_request", "teardown_appcontext"):
            exc = updated.params.params[0].name.value if updated.params.params else None
            tr = cst.parse_statement("try:\n    return await call_next(request)\nfinally:\n    pass\n")
            tr = tr.with_changes(finalbody=cst.Finally(body=body))
            pre = [cst.parse_statement("%s = None" % exc)] if exc else []
            params = [make_param("request", "Request", None), make_param("call_next", None, None)]
            return updated.with_changes(
                decorators=[cst.Decorator(decorator=cst.parse_expression('%s.middleware("http")' % obj))] + others,
                asynchronous=cst.Asynchronous(),
                params=updated.params.with_changes(params=params),
                body=cst.IndentedBlock(body=pre + [tr]),
            )
        stmts = list(body.body)
        if attr == "before_request":
            stmts.append(cst.parse_statement("return await call_next(request)"))
        else:
            resp = updated.params.params[0].name.value if updated.params.params else "response"
            stmts.insert(0, cst.parse_statement("%s = await call_next(request)" % resp))
        params = [make_param("request", "Request", None), make_param("call_next", None, None)]
        return updated.with_changes(
            decorators=[cst.Decorator(decorator=cst.parse_expression('%s.middleware("http")' % obj))] + others,
            asynchronous=cst.Asynchronous(),
            params=updated.params.with_changes(params=params),
            body=body.with_changes(body=stmts),
        )

    def _convert_view(self, original, updated, routes, others, drop_self=False):
        notes: List[str] = []
        rw = BodyRewriter(notes)
        rw.flask_names = self.flask_names
        body = updated.body.visit(rw)
        post = _PostRewriter()
        body = body.visit(post)
        # path parameters from the rule(s)
        ann = {}
        for _, rule, _ in routes:
            for n, t in convert_rule(rule)[1]:
                ann[n] = t
                if t == "uuid.UUID":
                    self.need_uuid = True
        params = []
        src_params = list(updated.params.params)
        if drop_self and src_params and src_params[0].name.value == "self":
            src_params = src_params[1:]
        for p in src_params:
            if p.annotation is None and p.name.value in ann and ann[p.name.value] != "str":
                p = p.with_changes(annotation=cst.Annotation(cst.parse_expression(ann[p.name.value])))
            params.append(p)
        existing = {p.name.value for p in params}
        for p in rw.params.params():
            if p.name.value not in existing:
                params.append(p)
        if (rw.need_request or post.query_params or count_name(body, "request") > 0) and "request" not in existing:
            self.fastapi.add("Request")
            params.append(make_param("request", "Request", None))
        updated_params = updated.params.with_changes(params=order_params(params))
        # decorators
        new_decs = []
        for obj, rule, methods in routes:
            path = convert_rule(rule)[0]
            if len(methods) == 1:
                src = "@%s.%s(%r)" % (obj, methods[0].lower(), path)
            else:
                src = "@%s.api_route(%r, methods=%r)" % (obj, path, methods)
            src = src.replace("'", '"')
            new_decs.append(cst.Decorator(decorator=cst.parse_expression(src[1:])))
            self.routes += 1
        self.fastapi |= rw.fastapi
        self.responses |= rw.responses
        self.typing |= rw.typing
        self.need_templates = self.need_templates or rw.need_templates
        self.need_upload = self.need_upload or rw.need_upload
        self.need_session = self.need_session or rw.need_session
        for n in notes:
            self.warn(original, "convert", "%s: %s" % (original.name.value, n))
        return updated.with_changes(decorators=new_decs + others, params=updated_params, body=body)

    def leave_ClassDef(self, original, updated):
        for b in updated.bases:
            n = dotted(b.value) or ""
            if n.split(".")[-1] in ("MethodView", "Resource"):
                self.classviews[original.name.value] = updated
                return cst.RemoveFromParent()
        return updated

    # ---- module assembly
    def _class_view_functions(self):
        funcs = []
        for cname, cdef in self.classviews.items():
            routes = self.class_routes.get(cname)
            if not routes:
                self.warn(cdef, "class-view", "class %s is never registered with add_resource/add_url_rule: not converted" % cname)
                continue
            for st in cdef.body.body:
                if isinstance(st, cst.FunctionDef) and st.name.value in HTTP_SHORTCUTS:
                    rts = [(obj, rule, [st.name.value.upper()]) for obj, rule in routes]
                    fn = st.with_changes(name=cst.Name("%s_%s" % (cname, st.name.value)), leading_lines=[cst.EmptyLine(), cst.EmptyLine()])
                    conv = self._convert_view(st, fn, rts, [], drop_self=True)
                    if count_name(conv.body, "self") > 0:
                        self.warn(st, "class-view", "%s.%s uses self: check the converted function" % (cname, st.name.value))
                    funcs.append(conv)
        return funcs

    def leave_Module(self, original, updated):
        body0 = list(updated.body)
        extra = self._class_view_functions()
        if extra:
            pos_main = len(body0)
            for i, st in enumerate(body0):
                if isinstance(st, cst.If) and "__name__" in cst.Module([]).code_for_node(st.test):
                    pos_main = i
                    break
            body0[pos_main:pos_main] = extra
        code_of = cst.Module([]).code_for_node

        def _after_app(stmts, pos_after=0):
            for i, st in enumerate(body0):
                if isinstance(st, cst.SimpleStatementLine) and st.body and isinstance(st.body[0], cst.Assign) and code_of(st.body[0].value).startswith("FastAPI("):
                    return i, code_of(st.body[0].targets[0].target)
            return None, None

        app_i, app_name = _after_app(body0)
        if self.uses_config and app_i is not None:
            body0.insert(app_i + 1, cst.parse_statement("%s.config = {}" % app_name))
        if self.need_session:
            # the secret key is usually assigned after FastAPI(); add the middleware after the last such statement
            at, secret = app_i, 'os.environ.get("SECRET_KEY", "change-me")'
            for i, st in enumerate(body0):
                if isinstance(st, cst.SimpleStatementLine) and st.body and isinstance(st.body[0], cst.Assign):
                    tgt = code_of(st.body[0].targets[0].target)
                    if app_name and tgt in ("%s.secret_key" % app_name, '%s.config["SECRET_KEY"]' % app_name, "%s.config['SECRET_KEY']" % app_name):
                        at, secret = i, "%s" % tgt
            if at is not None:
                body0.insert(at + 1, cst.parse_statement("%s.add_middleware(SessionMiddleware, secret_key=%s)" % (app_name, secret)))
        if self.need_login and app_name and app_i is not None:
            body0.insert(app_i + 1, cst.parse_statement(LOGIN_MIDDLEWARE % {"app": app_name}))
        if self.need_sqla and app_name:
            for i, st in enumerate(body0):
                if isinstance(st, cst.SimpleStatementLine) and st.body and isinstance(st.body[0], cst.Assign) and code_of(st.body[0].value).startswith("_SQLAlchemy("):
                    v = code_of(st.body[0].targets[0].target)
                    body0.insert(i + 1, cst.parse_statement(SQLA_MIDDLEWARE % {"app": app_name, "db": v}))
                    break
        if self.need_templates:
            for i, st in enumerate(body0):
                if isinstance(st, cst.SimpleStatementLine) and st.body and isinstance(st.body[0], cst.Assign) and cst.Module([]).code_for_node(st.body[0].value).startswith("FastAPI("):
                    body0.insert(i + 1, cst.parse_statement('templates = Jinja2Templates(directory="templates")'))
                    break
        updated = updated.with_changes(body=body0)
        lines = []
        if self.typing:
            lines.append("from typing import %s" % ", ".join(sorted(self.typing)))
        if self.need_uuid:
            lines.append("import uuid")
        if self.need_uvicorn:
            lines.append("import uvicorn")
        lines.append("from fastapi import %s" % ", ".join(sorted(self.fastapi)))
        if self.responses:
            lines.append("from fastapi.responses import %s" % ", ".join(sorted(self.responses)))
        if self.need_session:
            lines.append("import os")
            lines.append("from starlette.middleware.sessions import SessionMiddleware")
        if self.need_cors:
            lines.append("from fastapi.middleware.cors import CORSMiddleware")
        if self.need_templates:
            lines.append("from fastapi.templating import Jinja2Templates")
        header = [cst.parse_statement(s) for s in lines]
        body = list(updated.body)
        idx = 0
        if body and isinstance(body[0], cst.SimpleStatementLine) and body[0].body and isinstance(body[0].body[0], cst.Expr) and isinstance(body[0].body[0].value, (cst.SimpleString, cst.ConcatenatedString)):
            idx = 1
        while idx < len(body) and isinstance(body[idx], cst.SimpleStatementLine) and body[idx].body and isinstance(body[idx].body[0], cst.ImportFrom) and dotted(body[idx].body[0].module or cst.Name("")) == "__future__":
            idx += 1
        helper = []
        if self.need_upload:
            helper = [cst.parse_statement(UPLOAD_HELPER)]
        if self.need_sqla:
            helper += list(cst.parse_module(SQLA_HELPER).body)
        if self.need_login:
            helper += list(cst.parse_module(LOGIN_HELPER).body)
        return updated.with_changes(body=body[:idx] + header + helper + body[idx:])


LOGIN_MIDDLEWARE = """@%(app)s.middleware("http")
async def _login_ctx(request, call_next):
    token = _LOGIN_REQ.set(request)
    try:
        return await call_next(request)
    finally:
        _LOGIN_REQ.reset(token)
"""

LOGIN_HELPER = """import contextvars as _lcv
import functools as _ft
import inspect as _insp
import urllib.parse as _up

_LOGIN_REQ = _lcv.ContextVar("_login_req", default=None)
_LM = None


class UserMixin:
    is_active = True
    is_anonymous = False

    @property
    def is_authenticated(self):
        return True

    def get_id(self):
        return str(self.id)


class _Anonymous:
    is_authenticated = False
    is_active = False
    is_anonymous = True

    def get_id(self):
        return None


class _LoginManager:
    login_view = None
    user_callback = None

    def __init__(self, app=None):
        global _LM
        _LM = self

    def init_app(self, app):
        return None

    def user_loader(self, f):
        self.user_callback = f
        return f

    request_callback = None

    def request_loader(self, f):
        self.request_callback = f
        return f

    unauthorized_callback = None

    def unauthorized_handler(self, f):
        self.unauthorized_callback = f
        return f


def _login_session():
    req = _LOGIN_REQ.get()
    return req.session if req is not None else {}


def login_user(user, remember=False, **kw):
    _login_session()["_user_id"] = user.get_id()
    _login_session()["_fresh"] = True
    return True


def logout_user():
    _login_session().pop("_user_id", None)
    _login_session().pop("_fresh", None)
    return True


class _CurrentUser:
    def _get(self):
        uid = _login_session().get("_user_id")
        if uid is not None and _LM is not None and _LM.user_callback is not None:
            return _LM.user_callback(uid) or _Anonymous()
        req = _LOGIN_REQ.get()
        if _LM is not None and _LM.request_callback is not None and req is not None:
            return _LM.request_callback(req) or _Anonymous()
        return _Anonymous()

    def __getattr__(self, name):
        return getattr(self._get(), name)

    def __bool__(self):
        return True


current_user = _CurrentUser()


def _unauthorized():
    req = _LOGIN_REQ.get()
    if _LM is not None and _LM.unauthorized_callback is not None:
        return _LM.unauthorized_callback()
    view = _LM.login_view if _LM is not None else None
    if view and req is not None:
        target = req.url_for(view).path + "?next=" + _up.quote(req.url.path, safe="")
        return RedirectResponse(target, status_code=302)
    raise HTTPException(status_code=401, detail="Unauthorized")


def _guard(func, fresh):
    def ok():
        if not current_user.is_authenticated:
            return False
        if fresh and not _login_session().get("_fresh", False):
            raise HTTPException(status_code=401, detail="Needs refresh")
        return True

    if _insp.iscoroutinefunction(func):
        @_ft.wraps(func)
        async def awrapper(*a, **k):
            if not ok():
                return _unauthorized()
            return await func(*a, **k)

        return awrapper

    @_ft.wraps(func)
    def wrapper(*a, **k):
        if not ok():
            return _unauthorized()
        return func(*a, **k)

    return wrapper


def login_required(func):
    return _guard(func, False)


def fresh_login_required(func):
    return _guard(func, True)
"""


SQLA_MIDDLEWARE = """@%(app)s.middleware("http")
async def _sqla_scope(request, call_next):
    token = _REQ_ID.set(next(_REQ_COUNTER))
    try:
        return await call_next(request)
    finally:
        %(db)s.session.remove()
        _REQ_ID.reset(token)
"""

SQLA_HELPER = """import contextvars as _cv
import itertools as _it
import re as _re

import sqlalchemy as _sa
from sqlalchemy import orm as _orm

_REQ_ID = _cv.ContextVar("_req_id", default=0)
_REQ_COUNTER = _it.count(1)


class _BaseQuery(_orm.Query):
    def get_or_404(self, ident):
        rv = self.get(ident)
        if rv is None:
            raise HTTPException(status_code=404)
        return rv

    def first_or_404(self):
        rv = self.first()
        if rv is None:
            raise HTTPException(status_code=404)
        return rv


class _Pagination:
    def __init__(self, items, page, per_page, total):
        self.items, self.page, self.per_page, self.total = items, page, per_page, total
        self.pages = (total + per_page - 1) // per_page if per_page else 0
        self.has_prev = page > 1
        self.has_next = page < self.pages
        self.prev_num = page - 1 if self.has_prev else None
        self.next_num = page + 1 if self.has_next else None

    def __iter__(self):
        return iter(self.items)


def _paginate(self, page=1, per_page=20, error_out=True, **kw):
    page = max(int(page or 1), 1)
    per_page = max(int(per_page or 20), 1)
    items = self.limit(per_page).offset((page - 1) * per_page).all()
    return _Pagination(items, page, per_page, self.order_by(None).count())


_BaseQuery.paginate = _paginate


class _QueryProp:
    def __get__(self, obj, cls):
        return _SQLAlchemy._current.session.query(cls)


class _SQLAlchemy:
    \"\"\"Minimal stand-in for Flask-SQLAlchemy (db.Model, db.session, Model.query, create_all).\"\"\"

    _current = None

    def __init__(self, app=None):
        import os as _os

        _SQLAlchemy._current = self
        self._app = app
        self._engine = None
        self._binds = {}
        outer = self

        class _Session(_orm.Session):
            def get_bind(self, mapper=None, clause=None, **kw):
                key = getattr(getattr(mapper, "class_", None), "__bind_key__", None)
                return outer.get_engine(key)

        def _tablename(cls):
            return _re.sub(r"(?<!^)(?=[A-Z])", "_", cls.__name__).lower()

        base = _orm.declarative_base()
        base.query = _QueryProp()
        base.__tablename__ = _orm.declared_attr(_tablename)
        self.Model = base
        self.session = _orm.scoped_session(_orm.sessionmaker(class_=_Session, query_cls=_BaseQuery), scopefunc=_REQ_ID.get)
        self._os = _os

    def _make_engine(self, url):
        kw = {}
        if url.startswith("sqlite"):
            kw["connect_args"] = {"check_same_thread": False}
            if url in ("sqlite://", "sqlite:///:memory:"):
                kw["poolclass"] = _sa.pool.StaticPool
        return _sa.create_engine(url, **kw)

    def get_engine(self, key=None):
        cfg = getattr(self._app, "config", None) or {}
        if key is None:
            if self._engine is None:
                url = cfg.get("SQLALCHEMY_DATABASE_URI") or self._os.environ.get("DATABASE_URL") or "sqlite:///app.db"
                self._engine = self._make_engine(url)
            return self._engine
        if key not in self._binds:
            self._binds[key] = self._make_engine((cfg.get("SQLALCHEMY_BINDS") or {})[key])
        return self._binds[key]

    @property
    def engine(self):
        return self.get_engine(None)

    def _tables_by_bind(self, bind_key="__all__"):
        out = {}
        for m in self.Model.registry.mappers:
            key = getattr(m.class_, "__bind_key__", None)
            if bind_key == "__all__" or bind_key == key:
                out.setdefault(key, []).append(m.local_table)
        return out

    def create_all(self, bind_key="__all__"):
        for key, tables in self._tables_by_bind(bind_key).items():
            self.Model.metadata.create_all(self.get_engine(key), tables=tables)

    def drop_all(self, bind_key="__all__"):
        for key, tables in self._tables_by_bind(bind_key).items():
            self.Model.metadata.drop_all(self.get_engine(key), tables=tables)

    def get_or_404(self, model, ident):
        rv = self.session.get(model, ident)
        if rv is None:
            raise HTTPException(status_code=404)
        return rv

    def __getattr__(self, name):
        for mod in (_sa, _orm):
            if hasattr(mod, name):
                return getattr(mod, name)
        raise AttributeError(name)
"""


UPLOAD_HELPER = """class _Upload:
    \"\"\"Werkzeug FileStorage-like wrapper around Starlette's UploadFile (sync API).\"\"\"

    def __init__(self, f):
        self._f = f
        self.filename = f.filename
        self.content_type = f.content_type
        self.stream = f.file

    def read(self, *a):
        return self._f.file.read(*a)

    def save(self, dst):
        import shutil
        with open(dst, "wb") as out:
            shutil.copyfileobj(self._f.file, out)
"""


def convert_source(src: str) -> Result:
    module = cst.parse_module(src)
    wrapper = MetadataWrapper(module)
    conv = FlaskConverter()
    new = wrapper.visit(conv)
    # route functions that are not used in `request.xxx` leftovers etc. are reported by the converter itself
    return Result(code=new.code, warnings=conv.warnings, routes=conv.routes)
