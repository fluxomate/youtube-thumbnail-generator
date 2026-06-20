"""Shared helpers for the YouTube thumbnail generator skill.

Everything here is local except calls to fal.ai. The fal API key is read from
the FAL_KEY environment variable (fal_client picks it up automatically).
"""

import os
import sys
import json
import time
import pathlib
import urllib.request

try:
    import fal_client
except ImportError:
    sys.exit(
        "fal_client is not installed. Run:  python -m pip install fal-client\n"
        "Then make sure FAL_KEY is set in your environment."
    )


def require_key() -> None:
    """Fail fast with a friendly message if the fal key is missing."""
    if not os.environ.get("FAL_KEY"):
        sys.exit(
            "FAL_KEY is not set.\n"
            "  PowerShell (this session): $env:FAL_KEY = 'your-key-here'\n"
            "  Permanent: setx FAL_KEY \"your-key-here\"  (then restart the terminal)\n"
            "Get a key at https://fal.ai/dashboard/keys"
        )


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def upload_refs(paths):
    """Upload local reference images to fal and return their hosted URLs.

    nano-banana/edit needs URLs, not local files, so we upload first.
    """
    urls = []
    for p in paths:
        path = pathlib.Path(p).expanduser()
        if not path.exists():
            sys.exit(f"Reference image not found: {path}")
        _log(f"  uploading ref: {path.name}")
        urls.append(fal_client.upload_file(str(path)))
    return urls


def _on_update(update):
    """Stream queue/log progress to stderr so the user sees life."""
    try:
        from fal_client import InProgress

        if isinstance(update, InProgress):
            for log in getattr(update, "logs", []) or []:
                msg = log.get("message") if isinstance(log, dict) else str(log)
                if msg:
                    _log(f"  · {msg}")
    except Exception:
        pass


def run_model(endpoint: str, arguments: dict) -> dict:
    """Call a fal endpoint and return the result dict.

    Uses subscribe() so long-running jobs stream progress instead of timing out.
    """
    require_key()
    _log(f"calling {endpoint} ...")
    result = fal_client.subscribe(
        endpoint,
        arguments=arguments,
        with_logs=True,
        on_queue_update=_on_update,
    )
    return result


def download(url: str, dest: pathlib.Path) -> pathlib.Path:
    """Download a result image URL to a local path."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(url, str(dest))
    return dest


def slugify(text: str, maxlen: int = 40) -> str:
    keep = []
    for ch in text.lower().strip():
        if ch.isalnum():
            keep.append(ch)
        elif ch in " -_":
            keep.append("-")
    slug = "".join(keep)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-")[:maxlen] or "untitled"


def write_sidecar(image_path: pathlib.Path, meta: dict) -> None:
    """Write a .json sidecar next to an image recording how it was made."""
    side = image_path.with_suffix(image_path.suffix + ".json")
    side.write_text(json.dumps(meta, indent=2), encoding="utf-8")


def timestamp() -> str:
    return time.strftime("%Y%m%d-%H%M%S")
