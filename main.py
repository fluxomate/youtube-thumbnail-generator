#!/usr/bin/env python
"""Production entrypoint for Thumbnail Studio.

A host's process manager runs `python main.py`. It launches the Flask app
(in `studio/server.py`) under gunicorn, binding to $PORT. Falls back to the
Flask server if gunicorn isn't available (e.g. local Windows).

For local development you can also just run:  python studio/server.py
"""
import os
import sys

PORT = os.environ.get("PORT", "5005")
HERE = os.path.dirname(os.path.abspath(__file__))

try:
    # Preferred: gunicorn, single worker (the app keeps in-process job state) + threads.
    os.execvp("gunicorn", [
        "gunicorn", "--chdir", "studio", "server:app",
        "--workers", "1", "--threads", "8", "--timeout", "300",
        "--bind", f"0.0.0.0:{PORT}",
    ])
except FileNotFoundError:
    # Fallback: the Flask server directly (fine for local / low traffic).
    sys.path.insert(0, os.path.join(HERE, "studio"))
    os.chdir(os.path.join(HERE, "studio"))
    from server import app  # noqa: E402
    app.run(host="0.0.0.0", port=int(PORT), threaded=True)
