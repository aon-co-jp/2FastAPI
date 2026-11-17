"""Flask-JWT-Extended -> small PyJWT based shim (same claims, same HTTP error answers) for converted FastAPI code."""

JWT_MIDDLEWARE = """@%(app)s.middleware("http")
async def _jwt_ctx(request, call_next):
    token = _JWT_REQ.set(request)
    try:
        return await call_next(request)
    finally:
        _JWT_REQ.reset(token)
"""

JWT_HELPER = """import contextvars as _jcv
import datetime as _jdt
import functools as _jft
import inspect as _jinsp
import re as _jre
import uuid as _juuid

import jwt as _pyjwt

_JWT_REQ = _jcv.ContextVar("_jwt_req", default=None)
_JWT_CLAIMS = _jcv.ContextVar("_jwt_claims", default=None)
_JWT_APP = None


class _JWTManager:
    def __init__(self, app=None):
        global _JWT_APP
        _JWT_APP = app

    def init_app(self, app):
        global _JWT_APP
        _JWT_APP = app


def _jcfg(key, default=None):
    cfg = getattr(_JWT_APP, "config", None) or {}
    return cfg.get(key, default)


def _jsecret():
    return _jcfg("JWT_SECRET_KEY") or _jcfg("SECRET_KEY")


def _jexp(kind, delta):
    if delta is None:
        delta = _jcfg("JWT_ACCESS_TOKEN_EXPIRES", _jdt.timedelta(minutes=15)) if kind == "access" else _jcfg("JWT_REFRESH_TOKEN_EXPIRES", _jdt.timedelta(days=30))
    if delta is False:
        return None
    if isinstance(delta, (int, float)):
        delta = _jdt.timedelta(seconds=delta)
    return delta


def _jmake(kind, identity, fresh, expires_delta, additional_claims):
    now = _jdt.datetime.now(_jdt.timezone.utc)
    claims = {"fresh": fresh, "iat": now, "jti": str(_juuid.uuid4()), "type": kind, _jcfg("JWT_IDENTITY_CLAIM", "sub"): identity, "nbf": now}
    exp = _jexp(kind, expires_delta)
    if exp is not None:
        claims["exp"] = now + exp
    if additional_claims:
        claims.update(additional_claims)
    return _pyjwt.encode(claims, _jsecret(), algorithm=_jcfg("JWT_ALGORITHM", "HS256"))


def create_access_token(identity, fresh=False, expires_delta=None, additional_claims=None, **kw):
    return _jmake("access", identity, fresh, expires_delta, additional_claims)


def create_refresh_token(identity, expires_delta=None, additional_claims=None, **kw):
    return _jmake("refresh", identity, False, expires_delta, additional_claims)


class _JWTError(Exception):
    def __init__(self, status, msg):
        self.status = status
        self.msg = msg


def _jverify(optional=False, refresh=False):
    req = _JWT_REQ.get()
    header = req.headers.get(_jcfg("JWT_HEADER_NAME", "Authorization")) if req is not None else None
    if not header:
        if optional:
            _JWT_CLAIMS.set(None)
            return None
        raise _JWTError(401, "Missing %s Header" % _jcfg("JWT_HEADER_NAME", "Authorization"))
    htype = _jcfg("JWT_HEADER_TYPE", "Bearer")
    hname = _jcfg("JWT_HEADER_NAME", "Authorization")
    header = header.strip().strip(",")
    if not header:
        if optional:
            _JWT_CLAIMS.set(None)
            return None
        raise _JWTError(401, "Missing %s Header" % hname)
    if htype:
        cands = [x for x in _jre.split(", *", header) if x and x.split()[0] == htype]
        if len(cands) != 1:
            if optional:
                _JWT_CLAIMS.set(None)
                return None
            raise _JWTError(401, "Missing '%s' type in '%s' header. Expected '%s: %s <JWT>'" % (htype, hname, hname, htype))
        parts = cands[0].split()
        if len(parts) != 2:
            raise _JWTError(422, "Bad %s header. Expected '%s: %s <JWT>'" % (hname, hname, htype))
        token = parts[1]
    else:
        parts = header.split()
        if len(parts) != 1:
            raise _JWTError(422, "Bad %s header. Expected '%s: <JWT>'" % (hname, hname))
        token = parts[0]
    try:
        claims = _pyjwt.decode(token, _jsecret(), algorithms=[_jcfg("JWT_ALGORITHM", "HS256")], options={"verify_aud": False})
    except _pyjwt.ExpiredSignatureError:
        raise _JWTError(401, "Token has expired")
    except _pyjwt.InvalidTokenError as e:
        raise _JWTError(422, str(e))
    if claims.get("type") != ("refresh" if refresh else "access"):
        raise _JWTError(422, "Only refresh tokens are allowed" if refresh else "Only non-refresh tokens are allowed")
    _JWT_CLAIMS.set(claims)
    return claims


def verify_jwt_in_request(optional=False, fresh=False, refresh=False, locations=None, **kw):
    claims = _jverify(optional, refresh)
    if fresh and claims is not None and not claims.get("fresh"):
        raise _JWTError(401, "Fresh token required")
    return None if claims is None else ({}, claims)


def get_jwt():
    return _JWT_CLAIMS.get() or {}


def get_jwt_identity():
    return get_jwt().get(_jcfg("JWT_IDENTITY_CLAIM", "sub"))


def jwt_required(optional=False, fresh=False, refresh=False, locations=None, **kw):
    def deco(func):
        def check():
            try:
                verify_jwt_in_request(optional, fresh, refresh)
            except _JWTError as e:
                return JSONResponse({"msg": e.msg}, status_code=e.status)
            return None

        if _jinsp.iscoroutinefunction(func):
            @_jft.wraps(func)
            async def awrapper(*a, **k):
                bad = check()
                return bad if bad is not None else await func(*a, **k)

            return awrapper

        @_jft.wraps(func)
        def wrapper(*a, **k):
            bad = check()
            return bad if bad is not None else func(*a, **k)

        return wrapper

    return deco
"""
