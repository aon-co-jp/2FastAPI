#!/usr/bin/env bash
# Test environment in WSL: uv venv with libcst, flask, django, fastapi, httpx, pytest
export PATH="$HOME/.local/bin:/usr/bin:/bin"
uv venv -q --python 3.12 "$HOME/2fa-venv" 2>&1 | tail -1
. "$HOME/2fa-venv/bin/activate"
uv pip install -q libcst flask django "fastapi" httpx uvicorn pytest python-multipart jinja2 flask-cors flask-sqlalchemy flask-login itsdangerous marshmallow flask-jwt-extended flask-restful djangorestframework 2>&1 | tail -2
python -c "import libcst, flask, django, fastapi; print('env ok', libcst.__name__, flask.__version__ if hasattr(flask,'__version__') else '', django.__version__, fastapi.__version__)"
