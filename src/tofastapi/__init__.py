"""2FastAPI (to FastAPI): convert Flask / Django code to FastAPI-compatible code (MFastAPI compatible)."""
__version__ = "0.5.0"


def __getattr__(name):  # lazy: the GUI can start before the conversion library (libcst) is imported
    if name in ("Result", "Warn"):
        from . import common

        return getattr(common, name)
    if name == "convert_flask":
        from .flask_conv import convert_source

        return convert_source
    raise AttributeError(name)
