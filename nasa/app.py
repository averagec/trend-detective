"""Vercel entrypoint for the Flask API (the `nasa` service in vercel.json).

Vercel imports this file and serves the `app` object. The app itself is built in
src/trend_detective/app/web.py; nothing here does any work beyond creating it.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))  # the package lives in src/

from trend_detective.app.web import create_app  # noqa: E402

app = create_app()
