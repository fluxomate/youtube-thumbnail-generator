"""Supabase Storage backing for per-user workspaces.

The local workspace dir (on the Railway volume) is a cache; this module makes
Supabase Storage the durable source of truth: changed files are pushed up, and a
fresh container/volume pulls a user's files back down. Service-role key only.
"""
import os
import json
import pathlib
import urllib.request
import urllib.error

BUCKET = "workspaces"


def _cfg():
    return (os.environ.get("SUPABASE_URL") or "").rstrip("/"), (os.environ.get("SUPABASE_SERVICE_KEY") or "")


def enabled():
    url, svc = _cfg()
    return bool(url and svc)


def _headers(extra=None):
    _, svc = _cfg()
    h = {"apikey": svc, "Authorization": "Bearer " + svc}
    if extra:
        h.update(extra)
    return h


def upload(key, local_path):
    """Upsert a single object."""
    url, _ = _cfg()
    try:
        data = pathlib.Path(local_path).read_bytes()
        req = urllib.request.Request(
            f"{url}/storage/v1/object/{BUCKET}/{key}", data=data, method="POST",
            headers=_headers({"x-upsert": "true", "Content-Type": "application/octet-stream"}))
        urllib.request.urlopen(req, timeout=60).read()
        return True
    except Exception:
        return False


def delete_prefix(prefix):
    """Delete every object under a prefix (a file or a whole folder)."""
    keys = [o["key"] for o in _walk(prefix)]
    if not keys:
        # maybe it's a single object
        keys = [prefix]
    url, _ = _cfg()
    try:
        body = json.dumps({"prefixes": keys}).encode()
        req = urllib.request.Request(f"{url}/storage/v1/object/{BUCKET}", data=body, method="DELETE",
                                     headers=_headers({"Content-Type": "application/json"}))
        urllib.request.urlopen(req, timeout=30).read()
        return True
    except Exception:
        return False


def _list_folder(prefix):
    url, _ = _cfg()
    body = json.dumps({"prefix": prefix, "limit": 1000,
                       "sortBy": {"column": "name", "order": "asc"}}).encode()
    try:
        req = urllib.request.Request(f"{url}/storage/v1/object/list/{BUCKET}", data=body, method="POST",
                                     headers=_headers({"Content-Type": "application/json"}))
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8")) or []
    except Exception:
        return []


def _walk(prefix):
    """Yield {key} for every file under prefix (recursing into folders)."""
    out = []
    pfx = prefix.rstrip("/")
    stack = [pfx]
    while stack:
        cur = stack.pop()
        for item in _list_folder(cur + "/"):
            name = item.get("name")
            if not name:
                continue
            full = f"{cur}/{name}"
            if item.get("id") is None:  # folder
                stack.append(full)
            else:
                out.append({"key": full})
    return out


def download_all(user_id, dest_dir):
    """Pull every object under <user_id>/ into dest_dir. Returns count downloaded."""
    url, _ = _cfg()
    dest_dir = pathlib.Path(dest_dir)
    files = _walk(user_id)
    n = 0
    for f in files:
        key = f["key"]
        rel = key[len(user_id) + 1:]  # strip "<uid>/"
        target = dest_dir / rel
        try:
            req = urllib.request.Request(f"{url}/storage/v1/object/{BUCKET}/{key}", headers=_headers())
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            n += 1
        except Exception:
            pass
    return n


def sync_up_changed(base, user_id, since_ts):
    """Upload every file under base modified at/after since_ts, keyed <user_id>/<rel>."""
    base = pathlib.Path(base)
    if not base.exists():
        return 0
    n = 0
    for p in base.rglob("*"):
        if not p.is_file():
            continue
        try:
            if p.stat().st_mtime >= since_ts - 1:
                rel = p.relative_to(base).as_posix()
                if upload(f"{user_id}/{rel}", p):
                    n += 1
        except Exception:
            pass
    return n
