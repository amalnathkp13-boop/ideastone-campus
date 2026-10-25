"""Check the running local ERP's browser and installable app icons."""

import base64
import json
import re
from pathlib import Path
from urllib.request import urlopen


root = Path(__file__).resolve().parents[3]
icons = root / "addons/ideastone_campus/static/src/img/icons"
prefix = "/ideastone_campus/static/src/img/icons/"

with urlopen("http://localhost/web/login", timeout=10) as response:
    head = response.read().decode().split("</head>", 1)[0]

for name in ("favicon.ico", "favicon-32x32.png", "favicon-16x16.png", "apple-touch-icon.png"):
    assert head.count(prefix + name) == 1, name

with urlopen("http://localhost/web/manifest.webmanifest", timeout=10) as response:
    manifest = json.load(response)

assert manifest["name"] == "VCET Campus ERP"
assert manifest["scope"] == "/web" and manifest["start_url"] == "/web"
assert len(manifest["icons"]) == 3
assert manifest["icons"][2]["purpose"] == "maskable"

for icon in manifest["icons"]:
    path = icon["src"]
    assert path.startswith(prefix), path
    with urlopen("http://localhost" + path, timeout=10) as response:
        assert response.read() == (icons / path.removeprefix(prefix)).read_bytes(), path

with urlopen("http://localhost/web/offline", timeout=10) as response:
    offline_icon = re.search(rb"data:image/[^;]+;base64,([A-Za-z0-9+/=]+)", response.read())
assert offline_icon
assert base64.b64decode(offline_icon[1]) == (icons / "android-chrome-192x192.png").read_bytes()

print("VCET icon links, manifest, and served assets: OK")
