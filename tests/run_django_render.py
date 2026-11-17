"""Run requests against the original Django project in a fresh interpreter. Usage: run_django_render.py <proj> <req.json>"""
import json
import os
import sys

proj, req = sys.argv[1], sys.argv[2]
sys.path.insert(0, proj)
import django  # noqa: E402
from django.conf import settings  # noqa: E402

settings.configure(ROOT_URLCONF="config.urls", ALLOWED_HOSTS=["*"], DEBUG=False, SECRET_KEY="x", INSTALLED_APPS=[],
                   TEMPLATES=[{"BACKEND": "django.template.backends.django.DjangoTemplates", "DIRS": [os.path.join(proj, "shop", "templates")]}])
django.setup()
from django.test import Client  # noqa: E402

c = Client()
print(json.dumps([[r.status_code, r.content.decode()] for r in (c.get(u) for _, u, _ in json.load(open(req)))]))
