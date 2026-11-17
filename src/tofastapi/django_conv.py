"""Django -> FastAPI converter: urls.py (path/re_path/include) + function-based views (libcst, comments are kept)."""
from __future__ import annotations

import os
import re
from typing import Dict, List, Optional, Set, Tuple

import libcst as cst
from libcst.metadata import MetadataWrapper, PositionProvider

from .common import ParamSet, Result, Warn, convert_rule, count_name, dotted, ident, make_param, order_params, str_value
from .flask_conv import BodyRewriter, _code, _kw, _pos

REQUEST_KINDS = {
    "request.GET": "query",
    "request.POST": "form",
    "request.COOKIES": "cookie",
    "request.headers": "header",
    "request.META": "meta",
    "request.query_params": "query",
    "request.data": "body",
}
SHORTCUT_STATUS = {
    "HttpResponseNotFound": 404,
    "HttpResponseBadRequest": 400,
    "HttpResponseForbidden": 403,
    "HttpResponseServerError": 500,
    "HttpResponseGone": 410,
}
RAISE_STATUS = {"Http404": 404, "PermissionDenied": 403, "SuspiciousOperation": 400}
DROP_DECORATORS = {"csrf_exempt", "never_cache", "csrf_protect", "ensure_csrf_cookie", "cache_page", "vary_on_headers", "xframe_options_exempt"}
DRF_DROP_DECORATORS = {"renderer_classes", "parser_classes", "throttle_classes"}
DRF_AUTH_DECORATORS = {"permission_classes", "authentication_classes"}
DRF_FIELD_TYPES = {
    "CharField": "str", "EmailField": "str", "URLField": "str", "SlugField": "str", "RegexField": "str", "ChoiceField": "str",
    "IntegerField": "int", "FloatField": "float", "DecimalField": "float", "BooleanField": "bool",
    "UUIDField": "uuid.UUID", "DateTimeField": "datetime.datetime", "DateField": "datetime.date", "TimeField": "datetime.time",
    "ListField": "list", "DictField": "dict", "JSONField": "Any",
}
DRF_REMOVE_MODULES = {"rest_framework.response", "rest_framework.decorators", "rest_framework.status", "rest_framework.views", "rest_framework.serializers", "rest_framework.permissions", "rest_framework.authentication", "rest_framework.renderers", "rest_framework.parsers", "rest_framework.throttling"}
DRF_REMOVE_NAMES = {"status", "serializers", "views", "response", "decorators"}
METHOD_DECORATORS = {"api_view": None, "require_GET": ["GET"], "require_POST": ["POST"], "require_safe": ["GET", "HEAD"], "require_http_methods": None}


HTTP_METHODS = ("get", "post", "put", "patch", "delete", "head")


class DjangoRewriter(BodyRewriter):
    def __init__(self, notes: List[str]):
        super().__init__(notes)
        self.methods_seen: Set[str] = set()
        self.serializers: Set[str] = set()
        self.serial_vars: Set[str] = set()
        self.need_templates = False

    def _kind_param(self, base: str, key: str, default, type_node, required: bool):
        kind = REQUEST_KINDS[base]
        if kind == "meta":
            if key.startswith("HTTP_"):
                key = key[5:]
            kind = "header"
            key = key.lower()
        elif kind == "header":
            key = key.lower().replace("-", "_")
        return self._param(key, kind, default, type_node, required)

    def leave_Comparison(self, original, updated):
        # request.method == "POST"  -> remember the method for the route decorator
        if dotted(updated.left) == "request.method":
            for c in updated.comparisons:
                v = str_value(c.comparator)
                if v:
                    self.methods_seen.add(v.upper())
        return updated

    def leave_Call(self, original, updated):
        d = dotted(updated.func) or ""
        args = list(updated.args)
        pos = _pos(args)
        base, _, last = d.rpartition(".")
        if base in REQUEST_KINDS and last == "get" and pos:
            key = str_value(pos[0].value)
            if key is None:
                self.notes.append("dynamic key in %s(...) was left unchanged" % d)
                return updated
            default = pos[1].value if len(pos) > 1 else _kw(args, "default")
            return self._kind_param(base, key, default, None, False)
        if base in ("request.GET", "request.POST", "request.query_params") and last == "getlist" and pos and str_value(pos[0].value):
            name = ident(str_value(pos[0].value))
            self.typing.add("List")
            if base in ("request.GET", "request.query_params"):
                self.fastapi.add("Query")
                self.params.add(name, "List[str]", "Query(default=[])")
            else:
                self.fastapi.add("Form")
                self.params.add(name, "List[str]", "Form(default=[])")
            return cst.Name(name)
        if base in self.serial_vars and last == "is_valid":
            return cst.Name("True")
        if d == "Response":
            data = pos[0].value if pos else _kw(args, "data")
            status = _kw(args, "status")
            if data is None:
                self.fastapi.add("Response")
                return cst.parse_expression("Response(status_code=%s)" % (_code(status) if status is not None else "200"))
            self.responses.add("JSONResponse")
            return cst.parse_expression("JSONResponse(content=%s, status_code=%s)" % (_code(data), _code(status) if status is not None else "200"))
        if d == "JsonResponse" and pos:
            self.responses.add("JSONResponse")
            status = _kw(args, "status")
            extra = [a for a in args if a.keyword is not None and a.keyword.value in ("headers",)]
            src = "JSONResponse(content=%s, status_code=%s%s)" % (_code(pos[0].value), _code(status) if status is not None else "200", "".join(", " + _code(a) for a in extra))
            return cst.parse_expression(src)
        if d == "HttpResponse":
            content = pos[0].value if pos else (_kw(args, "content") or cst.SimpleString('""'))
            status = _kw(args, "status")
            ctype = _kw(args, "content_type")
            if ctype is not None:
                self.responses.add("Response") if False else self.fastapi.add("Response")
                src = "Response(content=%s, status_code=%s, media_type=%s)" % (_code(content), _code(status) if status is not None else "200", _code(ctype))
            else:
                self.responses.add("HTMLResponse")
                src = "HTMLResponse(content=%s, status_code=%s)" % (_code(content), _code(status) if status is not None else "200")
            return cst.parse_expression(src)
        if d in ("HttpResponseRedirect", "HttpResponsePermanentRedirect") and pos:
            self.responses.add("RedirectResponse")
            return cst.parse_expression("RedirectResponse(%s, status_code=%d)" % (_code(pos[0].value), 302 if d == "HttpResponseRedirect" else 301))
        if d in SHORTCUT_STATUS:
            self.responses.add("HTMLResponse")
            content = _code(pos[0].value) if pos else '""'
            return cst.parse_expression("HTMLResponse(content=%s, status_code=%d)" % (content, SHORTCUT_STATUS[d]))
        if d == "HttpResponseNotAllowed":
            self.fastapi.add("Response")
            return cst.parse_expression("Response(status_code=405)")
        if d == "redirect" and pos and str_value(pos[0].value) is not None and (str_value(pos[0].value).startswith(("/", "http://", "https://"))):
            self.responses.add("RedirectResponse")
            return cst.parse_expression("RedirectResponse(%s, status_code=302)" % _code(pos[0].value))
        if d in ("render", "render_to_response") and len(pos) >= 1:
            # render(request, "t.html", ctx, status=..) / render_to_response("t.html", ctx) (Django < 3.0) -> Jinja2Templates
            if d == "render":
                rest = pos[1:]
            else:
                rest = pos
                self.need_request = True
            if rest and str_value(rest[0].value) is not None:
                ctx = rest[1].value if len(rest) > 1 else _kw(args, "context")
                status = _kw(args, "status")
                self.need_templates = True
                self.need_request = True
                src = "templates.TemplateResponse(request, %s, %s%s)" % (_code(rest[0].value), _code(ctx) if ctx is not None else "{}", ", status_code=%s" % _code(status) if status is not None else "")
                self.notes.append("%s(...) -> Jinja2Templates: check Django template tags in %s" % (d, str_value(rest[0].value)))
                return cst.parse_expression(src)
        if d in ("render", "redirect", "reverse", "get_object_or_404", "get_list_or_404", "render_to_string", "get_template", "login", "logout", "authenticate"):
            self.notes.append("%s(...) is not converted automatically" % d)
        if d.endswith(".objects.get") or ".objects." in d:
            self.notes.append("Django ORM call %s(...) is not converted (use SQLAlchemy / Tortoise / SQLModel)" % d)
        return updated

    def leave_Subscript(self, original, updated):
        d = dotted(updated.value)
        if d in REQUEST_KINDS and len(updated.slice) == 1:
            el = updated.slice[0].slice
            key = str_value(el.value) if isinstance(el, cst.Index) else None
            if key is not None:
                return self._kind_param(d, key, None, None, True)
        return updated

    def leave_Attribute(self, original, updated):
        d = dotted(updated)
        m = re.match(r"^status\.HTTP_(\d\d\d)_", d or "")
        if m:
            return cst.Integer(m.group(1))
        base, _, last = (d or "").rpartition(".")
        if base in self.serial_vars and last in ("validated_data", "data"):
            return cst.parse_expression("%s.model_dump(exclude_none=True)" % base)
        if base in self.serial_vars and last == "errors":
            self.notes.append("serializer errors: FastAPI answers invalid input with 422 automatically (DRF used 400)")
        if d == "request.path":
            return cst.parse_expression("request.url.path")
        if d in ("request.user", "request.session", "request.FILES", "request.body"):
            self.notes.append("%s needs manual work (auth/session middleware, UploadFile, `await request.body()`)" % d)
        return updated

    def leave_Raise(self, original, updated):
        exc = updated.exc
        name = None
        args: List[cst.Arg] = []
        if isinstance(exc, cst.Name):
            name = exc.value
        elif isinstance(exc, cst.Call) and isinstance(exc.func, cst.Name):
            name = exc.func.value
            args = list(exc.args)
        if name in RAISE_STATUS:
            self.fastapi.add("HTTPException")
            detail = ", detail=%s" % _code(args[0].value) if args else ""
            return updated.with_changes(exc=cst.parse_expression("HTTPException(status_code=%d%s)" % (RAISE_STATUS[name], detail)))
        return updated

    def leave_SimpleStatementLine(self, original, updated):
        if len(updated.body) == 1 and isinstance(updated.body[0], cst.Assign):
            a = updated.body[0]
            # ser = XSerializer(data=request.data)  ->  body parameter `ser: X`
            if len(a.targets) == 1 and isinstance(a.targets[0].target, cst.Name) and isinstance(a.value, cst.Call):
                fn = dotted(a.value.func)
                dv = _kw(list(a.value.args), "data")
                if fn in self.serializers and dv is not None and dotted(dv) == "request.data":
                    var = a.targets[0].target.value
                    self.fastapi.add("Body")
                    self.params.add(var, fn, "Body(...)")
                    self.serial_vars.add(var)
                    return cst.RemoveFromParent()
            if len(a.targets) == 1 and isinstance(a.targets[0].target, cst.Name) and isinstance(a.value, cst.Name) and a.value.value == a.targets[0].target.value:
                return cst.RemoveFromParent()
        return updated

    def leave_Return(self, original, updated):
        if self.depth > 0 or updated.value is None:
            return updated
        ov = original.value
        # `return Response(data)` (DRF, no status) -> `return data`
        if isinstance(ov, cst.Call) and dotted(ov.func) == "Response":
            oargs = list(ov.args)
            if len(oargs) == 1 and oargs[0].keyword is None:
                call = updated.value
                if isinstance(call, cst.Call) and call.args:
                    return updated.with_changes(value=call.args[0].value)
        # `return JsonResponse(data)` (no status/headers) -> `return data`
        if isinstance(ov, cst.Call) and dotted(ov.func) == "JsonResponse":
            oargs = list(ov.args)
            if len(oargs) >= 1 and oargs[0].keyword is None and all(a.keyword is not None and a.keyword.value == "safe" for a in oargs[1:]):
                call = updated.value
                if isinstance(call, cst.Call) and call.args:
                    return updated.with_changes(value=call.args[0].value)
        return updated


class ViewsConverter(cst.CSTTransformer):
    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(self, routes: Dict[str, List[Tuple[str, List[Tuple[str, str]]]]]):
        super().__init__()
        self.routes = routes
        self.warnings: List[Warn] = []
        self.fastapi: Set[str] = {"APIRouter"}
        self.responses: Set[str] = set()
        self.typing: Set[str] = set()
        self.need_uuid = False
        self.count = 0
        self.depth = 0
        self.need_templates = False
        self.serializers: Set[str] = set()
        self.need_pydantic = False
        self.need_datetime = False
        self.need_field = False

    def visit_Module(self, node):
        for st in node.body:
            if isinstance(st, cst.ClassDef) and self._is_plain_serializer(st):
                self.serializers.add(st.name.value)
        return True

    @staticmethod
    def _is_plain_serializer(c):
        bs = [dotted(b.value) or "" for b in c.bases]
        return any(b.split(".")[-1] == "Serializer" for b in bs) and not any(b.split(".")[-1] == "ModelSerializer" for b in bs)

    def _serializer_model(self, original, cname):
        lines = ["class %s(BaseModel):" % cname]
        n = 0
        for st in original.body.body:
            if not (isinstance(st, cst.SimpleStatementLine) and st.body and isinstance(st.body[0], cst.Assign)):
                continue
            a = st.body[0]
            if len(a.targets) != 1 or not isinstance(a.targets[0].target, cst.Name) or not isinstance(a.value, cst.Call):
                continue
            fname = a.targets[0].target.value
            fcls = (dotted(a.value.func) or "").split(".")[-1]
            args = list(a.value.args)
            ro = _kw(args, "read_only")
            if ro is not None and dotted(ro) == "True":
                continue
            typ = DRF_FIELD_TYPES.get(fcls)
            if typ is None:
                self.warn(st, "serializer", "field %s.%s (%s) has no pydantic equivalent: typed as Any" % (cname, fname, fcls))
                typ = "Any"
            if typ == "Any":
                self.typing.add("Any")
            if typ.startswith("uuid."):
                self.need_uuid = True
            if typ.startswith("datetime."):
                self.need_datetime = True
            req = _kw(args, "required")
            dflt = _kw(args, "default")
            opts = []
            for k, v in (("max_length", "max_length"), ("min_length", "min_length"), ("max_value", "le"), ("min_value", "ge")):
                kv = _kw(args, k)
                if kv is not None and typ in ("str", "int", "float"):
                    opts.append("%s=%s" % (v, _code(kv)))
            rhs = None
            if dflt is not None:
                rhs = _code(dflt)
            elif req is not None and dotted(req) == "False":
                self.typing.add("Optional")
                typ = "Optional[%s]" % typ
                rhs = "None"
            if opts:
                self.need_field = True
                rhs = "Field(%s)" % ", ".join([rhs if rhs is not None else "..."] + opts)
            lines.append("    %s: %s%s" % (fname, typ, (" = " + rhs) if rhs is not None else ""))
            n += 1
        if n == 0:
            lines.append("    pass")
        self.need_pydantic = True
        return cst.parse_statement("\n".join(lines))

    def _line(self, node) -> int:
        try:
            return self.get_metadata(PositionProvider, node).start.line
        except Exception:
            return 0

    def warn(self, node, code, msg):
        self.warnings.append(Warn(self._line(node), code, msg))

    def leave_ImportFrom(self, original, updated):
        mod = dotted(updated.module) if updated.module is not None else ""
        if updated.relative:
            if mod and mod.split(".")[0] in ("models", "forms", "serializers"):
                self.warn(original, "orm", "`%s` is Django-specific (models/forms/serializers) and is not converted" % mod)
            return updated
        if mod in DRF_REMOVE_MODULES:
            return cst.RemoveFromParent()
        if mod == "rest_framework" and not isinstance(updated.names, cst.ImportStar) and all(a.name.value in DRF_REMOVE_NAMES for a in updated.names):
            return cst.RemoveFromParent()
        if mod in ("django.http", "django.shortcuts", "django.core.exceptions", "django.views.decorators.csrf", "django.views.decorators.http", "django.views.decorators.cache", "django.views.decorators.clickjacking"):
            return cst.RemoveFromParent()
        if mod.startswith("django.db") or mod.startswith("django.contrib"):
            self.warn(original, "django-api", "`%s` is not converted (ORM / contrib apps)" % mod)
        elif mod.startswith("django.views.generic") or mod.startswith("rest_framework"):
            self.warn(original, "class-view", "`%s`: class-based views / DRF are not converted" % mod)
        elif mod.startswith("django"):
            self.warn(original, "django-api", "`%s` is Django-specific and not converted" % mod)
        return updated

    def visit_ClassDef(self, node):
        self.depth += 1

    def leave_ClassDef(self, original, updated):
        self.depth -= 1
        cname = original.name.value
        bases = [dotted(b.value) or "" for b in updated.bases]
        if self._is_plain_serializer(original):
            self.warn(original, "serializer", "serializer %s converted to a pydantic model (validate/create/update methods are dropped)" % cname)
            return self._serializer_model(original, cname)
        if cname in self.routes and any(b.split(".")[-1] == "TemplateView" and not b.startswith("rest_framework") for b in bases):
            conv = self._template_view(original, updated, cname)
            if conv is not None:
                return cst.FlattenSentinel(conv)
        plain_view = any(b.split(".")[-1] in ("View", "APIView") and not b.startswith("rest_framework.generics") for b in bases)
        if plain_view and cname in self.routes:
            funcs = []
            for st in updated.body.body:
                if not isinstance(st, cst.FunctionDef):
                    if isinstance(st, cst.SimpleStatementLine) and st.body and isinstance(st.body[0], cst.Assign):
                        self.warn(st, "class-view", "class attribute in %s is not converted: inline it where used" % cname)
                    continue
                m = st.name.value
                if m in HTTP_METHODS:
                    fn = st.with_changes(name=cst.Name("%s_%s" % (cname, m)), leading_lines=[cst.EmptyLine(), cst.EmptyLine()])
                    conv = self._convert(st, fn, cname, [m.upper()], True)
                    if count_name(conv.body, "self") > 0:
                        self.warn(st, "class-view", "%s.%s uses `self`: check the converted function" % (cname, m))
                    funcs.append(conv)
                elif m in ("dispatch", "setup", "get_context_data", "options"):
                    self.warn(st, "class-view", "%s.%s is not converted" % (cname, m))
                else:
                    self.warn(st, "class-view", "helper method %s.%s was dropped: move it to a module-level function" % (cname, m))
            if not funcs:
                self.warn(original, "class-view", "class %s has no HTTP method handlers" % cname)
                return updated
            self.warn(original, "class-view", "class %s converted to one route function per HTTP method (%s)" % (cname, ", ".join(f.name.value for f in funcs)))
            return cst.FlattenSentinel(funcs)
        for b in bases:
            if b.endswith(("View", "ViewSet", "APIView", "Model", "Form", "ModelForm", "Serializer")):
                self.warn(original, "class-view", "class `%s(%s)` is not converted" % (cname, b))
        return updated

    def _template_view(self, original, updated, cname):
        tmpl = None
        ctx = None
        for st in updated.body.body:
            if isinstance(st, cst.SimpleStatementLine) and st.body and isinstance(st.body[0], cst.Assign):
                a = st.body[0]
                if len(a.targets) == 1 and dotted(a.targets[0].target) == "template_name":
                    tmpl = str_value(a.value)
            elif isinstance(st, cst.FunctionDef) and st.name.value == "get_context_data":
                ctx = st
        if tmpl is None:
            self.warn(original, "class-view", "TemplateView %s has no literal template_name: not converted" % cname)
            return None
        self.need_templates = True
        self.fastapi.add("Request")
        path, plist = self.routes[cname][0]
        params = ["request: Request"] + ["%s: %s" % (n, t) for n, t in plist]
        out = []
        kw = ", ".join("%s=%s" % (n, n) for n, _ in plist)
        if ctx is not None:
            helper = ctx.with_changes(
                name=cst.Name("_%s_context" % cname),
                params=cst.Parameters(star_kwarg=cst.Param(name=cst.Name("kwargs"))),
                leading_lines=[cst.EmptyLine(), cst.EmptyLine()],
            )
            helper = helper.visit(_SuperCtx())
            if count_name(helper.body, "self") > 0:
                self.warn(ctx, "class-view", "%s.get_context_data uses `self`: check the converted function" % cname)
            out.append(helper)
            ctxsrc = "_%s_context(%s)" % (cname, kw)
        else:
            ctxsrc = "{%s}" % ", ".join("%r: %s" % (n, n) for n, _ in plist)
        fn = cst.parse_statement(
            "@router.get(%r)\ndef %s_get(%s):\n    return templates.TemplateResponse(request, %r, %s)\n"
            % (path, cname, ", ".join(params), tmpl, ctxsrc)
        )
        self.count += 1
        for p2, _ in self.routes[cname][1:]:
            self.warn(original, "class-view", "%s is mounted at several paths; only %s is converted" % (cname, path))
            break
        self.warn(original, "class-view", "TemplateView %s -> %s_get using Jinja2Templates: check Django template tags in %s" % (cname, cname, tmpl))
        out.append(fn)
        return out

    def leave_FunctionDef(self, original, updated):
        name = original.name.value
        if self.depth or name not in self.routes:
            return updated
        return self._convert(original, updated, name, None, False)

    def _convert(self, original, updated, name, methods, drop_self):
        others = []
        for dec in updated.decorators:
            c = dec.decorator
            dn = dotted(c.func) if isinstance(c, cst.Call) else dotted(c)
            dn = (dn or "").split(".")[-1]
            if dn in DROP_DECORATORS:
                continue
            if dn in DRF_DROP_DECORATORS:
                continue
            if dn in DRF_AUTH_DECORATORS:
                self.warn(original, "auth", "@%s on %s is not converted: use a FastAPI dependency" % (dn, name))
                continue
            if dn in ("method_decorator",):
                self.warn(original, "auth", "@method_decorator on %s is not converted" % name)
                continue
            if dn in METHOD_DECORATORS:
                if METHOD_DECORATORS[dn] is not None:
                    methods = list(METHOD_DECORATORS[dn])
                elif isinstance(c, cst.Call) and c.args and isinstance(c.args[0].value, (cst.List, cst.Tuple)):
                    methods = [str_value(e.value).upper() for e in c.args[0].value.elements if str_value(e.value)]
                continue
            if dn in ("login_required", "permission_required", "user_passes_test"):
                self.warn(original, "auth", "@%s on %s is not converted: use a FastAPI dependency" % (dn, name))
            others.append(dec)
        notes: List[str] = []
        rw = DjangoRewriter(notes)
        rw.serializers = self.serializers
        body = updated.body.visit(rw)
        if methods is None:
            seen = rw.methods_seen
            methods = sorted(seen | {"GET"}) if seen else ["GET"]
        # parameters: drop the request argument when it is no longer used
        params = list(updated.params.params)
        if drop_self and params:
            params = params[1:]
        req_name = params[0].name.value if params else None
        keep_request = False
        if req_name:
            if req_name != "request":
                body = body.visit(_Rename(req_name, "request"))
            keep_request = count_name(body, "request") > 0 or rw.need_request
            params = params[1:]
        ann: Dict[str, str] = {}
        for _, plist in self.routes[name]:
            for n, t in plist:
                ann[n] = t
                if t == "uuid.UUID":
                    self.need_uuid = True
        newp = []
        for p in params:
            if p.annotation is None and p.name.value in ann and ann[p.name.value] != "str":
                p = p.with_changes(annotation=cst.Annotation(cst.parse_expression(ann[p.name.value])))
            newp.append(p)
        existing = {p.name.value for p in newp}
        for p in rw.params.params():
            if p.name.value not in existing:
                newp.append(p)
        if keep_request:
            self.fastapi.add("Request")
            newp.append(make_param("request", "Request", None))
        decs = []
        fname = updated.name.value
        for path, _ in self.routes[name]:
            if len(methods) == 1:
                src = "router.%s(%r)" % (methods[0].lower(), path)
            else:
                src = "router.api_route(%r, methods=%r)" % (path, methods)
            decs.append(cst.Decorator(decorator=cst.parse_expression(src.replace("'", '"'))))
            self.count += 1
        self.fastapi |= rw.fastapi
        self.responses |= rw.responses
        self.typing |= rw.typing
        if rw.need_templates:
            self.need_templates = True
        for n in notes:
            self.warn(original, "convert", "%s: %s" % (name, n))
        return updated.with_changes(decorators=decs + others, params=updated.params.with_changes(params=order_params(newp)), body=body)

    def leave_Module(self, original, updated):
        lines = []
        if self.typing:
            lines.append("from typing import %s" % ", ".join(sorted(self.typing)))
        if self.need_uuid:
            lines.append("import uuid")
        lines.append("from fastapi import %s" % ", ".join(sorted(self.fastapi)))
        if self.responses:
            lines.append("from fastapi.responses import %s" % ", ".join(sorted(self.responses)))
        if self.need_templates:
            lines.append("from fastapi.templating import Jinja2Templates")
        if self.need_pydantic:
            lines.append("from pydantic import BaseModel" + (", Field" if self.need_field else ""))
        if self.need_datetime:
            lines.append("import datetime")
        header = [cst.parse_statement(s) for s in lines]
        body = list(updated.body)
        idx = 0
        if body and isinstance(body[0], cst.SimpleStatementLine) and body[0].body and isinstance(body[0].body[0], cst.Expr) and isinstance(body[0].body[0].value, (cst.SimpleString, cst.ConcatenatedString)):
            idx = 1
        while idx < len(body) and isinstance(body[idx], cst.SimpleStatementLine) and body[idx].body and isinstance(body[idx].body[0], cst.ImportFrom) and dotted(body[idx].body[0].module or cst.Name("")) == "__future__":
            idx += 1
        body = body[:idx] + header + body[idx:]
        # `router = APIRouter()` after the last top-level import
        last = -1
        for i, st in enumerate(body):
            if isinstance(st, cst.SimpleStatementLine) and st.body and isinstance(st.body[0], (cst.Import, cst.ImportFrom)):
                last = i
        body.insert(last + 1, cst.parse_statement("\nrouter = APIRouter()\n") if False else cst.parse_statement("router = APIRouter()"))
        if self.need_templates:
            body.insert(last + 2, cst.parse_statement('templates = Jinja2Templates(directory="templates")'))
        return updated.with_changes(body=body)


class _SuperCtx(cst.CSTTransformer):
    """super().get_context_data(...) -> dict(kwargs)"""

    def leave_Call(self, original, updated):
        if dotted(updated.func) == "super().get_context_data" or (
            isinstance(updated.func, cst.Attribute)
            and updated.func.attr.value == "get_context_data"
            and isinstance(updated.func.value, cst.Call)
            and dotted(updated.func.value.func) == "super"
        ):
            return cst.parse_expression("dict(kwargs)")
        return updated


class _Rename(cst.CSTTransformer):
    def __init__(self, old, new):
        super().__init__()
        self.old, self.new = old, new

    def leave_Name(self, original, updated):
        return updated.with_changes(value=self.new) if updated.value == self.old else updated


# ------------------------------------------------------------------ urls.py


def _re_to_path(pattern: str, warns: List[str]) -> Tuple[str, List[Tuple[str, str]]]:
    """Django re_path regex -> FastAPI path (named groups only; the regex constraint is dropped, digits -> int)."""
    pat = pattern.lstrip("^").rstrip("$")
    params: List[Tuple[str, str]] = []

    def sub(m):
        name, rx = m.group(1), m.group(2)
        # Django passes regex groups as str, so keep str; the constraint itself is dropped (reported)
        if rx not in ("[^/]+", r"\w+", r"[-\w]+", ".+", ".*"):
            warns.append("group %s (%s) constraint dropped (value stays a str, like Django)" % (name, rx))
        params.append((name, "str"))
        return "{%s}" % name

    out = re.sub(r"\(\?P<(\w+)>((?:[^()\\]|\\.)*)\)", sub, pat)
    if "(" in out or out != re.sub(r"\\(.)", r"\1", out) and re.search(r"[\[\]+*?|]", out):
        warns.append("regex `%s` could only be converted approximately (constraints dropped)" % pattern)
    out = re.sub(r"\\(.)", r"\1", out)
    out = out.replace("?", "")
    return out, params


def parse_urls(src: str):
    """-> [(kind, pattern, view)], view = ("include", module) | ("view", dotted) | ("cbv", dotted) | ("other", code); and imports map."""
    mod = cst.parse_module(src)
    imports: Dict[str, Tuple[str, int]] = {}  # local name -> (module, level) ; for `from X import name`: (X.name-or-X, level)
    entries = []

    class V(cst.CSTVisitor):
        def visit_ImportFrom(self, n: cst.ImportFrom):
            level = len(n.relative)
            m = dotted(n.module) if n.module is not None else ""
            if isinstance(n.names, cst.ImportStar):
                return
            for a in n.names:
                local = a.asname.name.value if a.asname else a.name.value
                imports[local] = (m, level, a.name.value)

        def visit_Import(self, n: cst.Import):
            for a in n.names:
                local = a.asname.name.value if a.asname else dotted(a.name).split(".")[0]
                imports[local] = (dotted(a.name), 0, None)

        def visit_Assign(self, n: cst.Assign):
            if any(isinstance(t.target, cst.Name) and t.target.value == "urlpatterns" for t in n.targets) and isinstance(n.value, (cst.List, cst.Tuple)):
                for el in n.value.elements:
                    c = el.value
                    if not isinstance(c, cst.Call):
                        continue
                    fn = dotted(c.func)
                    if fn not in ("path", "re_path", "url") or len(c.args) < 2:
                        continue
                    pat = str_value(c.args[0].value)
                    if pat is None:
                        continue
                    v = c.args[1].value
                    if isinstance(v, cst.Call) and dotted(v.func) == "include":
                        a0 = v.args[0].value if v.args else None
                        target = str_value(a0) or (dotted(a0) if a0 is not None else None)
                        entries.append((fn, pat, ("include", target or "")))
                    elif isinstance(v, cst.Call) and isinstance(v.func, cst.Attribute) and v.func.attr.value == "as_view":
                        entries.append((fn, pat, ("cbv", dotted(v.func.value) or "")))
                    elif dotted(v):
                        entries.append((fn, pat, ("view", dotted(v))))
                    else:
                        entries.append((fn, pat, ("other", _code(v))))

    mod.visit(V())
    return entries, imports


def _module_file(root: str, module: str) -> Optional[str]:
    p = os.path.join(root, *module.split("."))
    for cand in (p + ".py", os.path.join(p, "__init__.py")):
        if os.path.isfile(cand):
            return cand
    return None


def _resolve(urls_file: str, root: str, imports, dotted_name: str) -> Optional[Tuple[str, str]]:
    """`views.fn` / `fn` -> (views file, function name)."""
    head, _, rest = dotted_name.partition(".")
    if head not in imports:
        return None
    m, level, orig = imports[head]
    base_dir = os.path.dirname(urls_file)
    if level:
        d = base_dir
        for _ in range(level - 1):
            d = os.path.dirname(d)
        parts = ([m] if m else [])
        rel = os.path.relpath(d, root).replace(os.sep, ".")
        prefix = [] if rel == "." else [rel]
        base_mod = ".".join(prefix + parts)
    else:
        base_mod = m
    if rest:  # views.fn : `from . import views` (orig == "views") or `import app.views`
        module = (base_mod + "." + orig) if orig else base_mod
        f = _module_file(root, module)
        return (f, rest) if f else None
    # `from .views import fn`
    f = _module_file(root, base_mod)
    return (f, orig) if f else None


def _join(prefix: str, pat: str) -> str:
    s = prefix + pat
    return "/" + s.lstrip("/")


def collect_routes(root: str, urls_file: str, prefix: str = "", seen=None, warns=None):
    """-> {views file: {function: [(fastapi path, [(param, annotation)])]}}"""
    seen = seen or set()
    warns = warns if warns is not None else []
    out: Dict[str, Dict[str, list]] = {}
    if urls_file in seen:
        return out
    seen = seen | {urls_file}
    with open(urls_file, encoding="utf-8") as fh:
        entries, imports = parse_urls(fh.read())
    for kind, pat, view in entries:
        if kind in ("re_path", "url"):
            local = []
            conv, params = _re_to_path(pat, local)
            for w in local:
                warns.append(Warn(0, "regex", "%s: %s" % (os.path.basename(urls_file), w)))
        else:
            conv, params = convert_rule(pat)
        if view[0] == "include":
            target = view[1]
            f = None
            if target in imports:  # include(blog_urls) after `from blog import urls as blog_urls`
                m, level, orig = imports[target]
                f = _module_file(root, (m + "." + orig) if orig else m)
            elif target:
                f = _module_file(root, target)
            if f is None:
                warns.append(Warn(0, "include", "include(%r) could not be resolved to a file" % target))
                continue
            sub = collect_routes(root, f, _join(prefix, conv) if conv else prefix, seen, warns)
            for vf, fns in sub.items():
                for fn, rl in fns.items():
                    out.setdefault(vf, {}).setdefault(fn, []).extend(rl)
        elif view[0] == "cbv":
            r = _resolve(urls_file, root, imports, view[1])
            if r is None:
                warns.append(Warn(0, "view", "class view %r could not be resolved" % view[1]))
                continue
            f, fn = r
            out.setdefault(f, {}).setdefault(fn, []).append((_join(prefix, conv), params))
        elif view[0] == "view":
            r = _resolve(urls_file, root, imports, view[1])
            if r is None:
                warns.append(Warn(0, "view", "view %r could not be resolved" % view[1]))
                continue
            f, fn = r
            out.setdefault(f, {}).setdefault(fn, []).append((_join(prefix, conv), params))
        else:
            warns.append(Warn(0, "view", "%s(%r): class-based or dynamic view %r is not converted" % (kind, pat, view[1])))
    return out


def _find_root_urls(project: str) -> Tuple[str, str]:
    if os.path.isfile(os.path.join(project, "manage.py")):
        for dp, dn, fn in os.walk(project):
            if "settings.py" in fn:
                with open(os.path.join(dp, "settings.py"), encoding="utf-8") as fh:
                    m = re.search(r"ROOT_URLCONF\s*=\s*['\"]([\w.]+)['\"]", fh.read())
                if m:
                    f = _module_file(project, m.group(1))
                    if f:
                        return project, f
        raise SystemExit("ROOT_URLCONF not found in settings.py")
    if os.path.isfile(os.path.join(project, "urls.py")):
        return project, os.path.join(project, "urls.py")
    raise SystemExit("no manage.py or urls.py found in %s" % project)


def convert_project(project: str, out_dir: str) -> Result:
    project = os.path.abspath(project)
    root, urls_file = _find_root_urls(project)
    warns: List[Warn] = []
    routes = collect_routes(root, urls_file, "", None, warns)
    os.makedirs(out_dir, exist_ok=True)
    total = 0
    modules = []
    for vf, fns in routes.items():
        with open(vf, encoding="utf-8") as fh:
            src = fh.read()
        conv = ViewsConverter({fn: rl for fn, rl in fns.items()})
        new = MetadataWrapper(cst.parse_module(src)).visit(conv)
        rel = os.path.relpath(vf, root)
        dest = os.path.join(out_dir, rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(new.code)
        # keep package markers
        d = os.path.dirname(rel)
        while d:
            init_src = os.path.join(root, d, "__init__.py")
            init_dst = os.path.join(out_dir, d, "__init__.py")
            if os.path.isfile(init_src) and not os.path.exists(init_dst):
                os.makedirs(os.path.dirname(init_dst), exist_ok=True)
                with open(init_dst, "w", encoding="utf-8") as fh:
                    fh.write("")
            d = os.path.dirname(d)
        for w in conv.warnings:
            warns.append(Warn(w.line, w.code, "%s: %s" % (rel, w.msg)))
        total += conv.count
        modules.append(rel[:-3].replace(os.sep, "."))
        missing = [fn for fn in fns if not re.search(r"(def|class)\s+%s\b" % re.escape(fn), src)]
        for fn in missing:
            warns.append(Warn(0, "view", "%s: view function %s not found (class-based view?)" % (rel, fn)))
    # Django templates (root `templates/` and `<app>/templates/`) are merged into `templates/` for Jinja2Templates
    import shutil

    for dp, dns, _ in os.walk(root):
        dns[:] = [x for x in dns if x not in (".git", "node_modules", "__pycache__", "venv", ".venv", "site-packages")]
        if os.path.basename(dp) == "templates" and os.path.abspath(dp) != os.path.abspath(os.path.join(out_dir, "templates")):
            shutil.copytree(dp, os.path.join(out_dir, "templates"), dirs_exist_ok=True)
            dns[:] = []
    lines = ["from fastapi import FastAPI", ""]
    for i, m in enumerate(modules):
        lines.append("from %s import router as router_%d" % (m, i))
    lines += ["", "app = FastAPI()"]
    for i in range(len(modules)):
        lines.append("app.include_router(router_%d)" % i)
    with open(os.path.join(out_dir, "main.py"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    report = ["# 2FastAPI conversion report", "", "Routes written: %d" % total, "Run: `uvicorn main:app --reload`", "", "## Warnings (manual work needed)", ""]
    report += ["- %s" % w for w in warns] or ["- none"]
    with open(os.path.join(out_dir, "CONVERSION_REPORT.md"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(report) + "\n")
    return Result(code="", warnings=warns, routes=total)
