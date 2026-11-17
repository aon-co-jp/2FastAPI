"""Run a list of requests against the converted FastAPI app in a fresh interpreter (avoids module name clashes with the Django original)."""
import json
import os
import sys

os.environ.setdefault('DATABASE_URL', 'sqlite://')

out_dir, req_file = sys.argv[1], sys.argv[2]
sys.path.insert(0, out_dir)
from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

client = TestClient(main.app, follow_redirects=False)
res = []
for method, url, kw in json.load(open(req_file)):
    r = client.request(method, url, **kw)
    ct = r.headers.get("content-type", "")
    res.append([r.status_code, r.json() if "json" in ct else r.text, r.headers.get("location")])
print(json.dumps(res))
