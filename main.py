#!/usr/bin/env python
"""WSGI entrypoint for Thumbnail Studio.

Exposes the Flask app as `app` so a host can run `gunicorn main:app`.
For local development you can also run:  python main.py  (or python studio/server.py)
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "studio"))

from server import app  # noqa: E402  (importing also seeds a blank workspace if STUDIO_MEMORY is set)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5005")), threaded=True)
