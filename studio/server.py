"""Thumbnail Studio — local web UI for the YouTube thumbnail generator skill.

A single-file Flask backend that wraps the existing skill:
  - reads/writes the skill's `memory/` tree (style, faces, likes, inspiration)
  - writes concepts with Claude (Anthropic API) using the creator's saved taste
  - generates + upscales images with fal.ai (reuses the skill's lib.py)

Run:  python studio/server.py   then open  http://127.0.0.1:5005

Everything is local. The only outbound calls are to Anthropic (concepts) and
fal.ai (images). Keys come from the environment or studio/config.json.
"""

import io
import os
import sys
import json
import time
import threading
import pathlib
import mimetypes
import subprocess
import traceback

from flask import Flask, request, jsonify, send_file, Response, abort, g

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
STUDIO_DIR = pathlib.Path(__file__).resolve().parent
PROJECT_ROOT = STUDIO_DIR.parent
SKILL_DIR = PROJECT_ROOT / ".claude" / "skills" / "youtube-thumbnail-generator"
SKILL_MEMORY = SKILL_DIR / "memory"
_MEM_OVERRIDE = os.environ.get("STUDIO_MEMORY")
_DEFAULT_MEMORY = pathlib.Path(_MEM_OVERRIDE).resolve() if _MEM_OVERRIDE else SKILL_MEMORY

import contextvars as _ctxv
_cur_mem = _ctxv.ContextVar("cur_mem", default=None)


class _MemoryProxy:
    """Resolves to the current request's per-user memory dir, or the default."""
    def _b(self):
        v = _cur_mem.get()
        return v if v is not None else _DEFAULT_MEMORY
    def __truediv__(self, o):
        return self._b() / o
    def resolve(self):
        return self._b().resolve()
    def mkdir(self, *a, **k):
        return self._b().mkdir(*a, **k)
    def exists(self):
        return self._b().exists()
    def __fspath__(self):
        return str(self._b())
    def __str__(self):
        return str(self._b())
    def __repr__(self):
        return "MEMORY(%s)" % self._b()


MEMORY = _MemoryProxy()

_BLANK_STYLE_TEMPLATE = """# Style profile

_The studio reads this before generating every concept. Fill it in during onboarding._

## Channel / niche
(What is your channel about? Who is the audience?)

## Persona on camera
(How do you usually appear? Expressions, energy, wardrobe.)

## Visual signature
- Colors:
- Fonts / text style:
- Composition habits:
- Background style:

## Do's
-

## Don'ts
-
"""


def _seed_blank_memory():
    """Fresh workspace (STUDIO_MEMORY set): copy SHARED methodology + reference
    thumbnails, but leave faces + style blank so the user gets onboarding. Never
    copies the owner's personal face photos / style / likes."""
    if not _MEM_OVERRIDE:
        return
    marker = MEMORY / ".seeded"
    if marker.exists():
        return
    import shutil
    src = SKILL_MEMORY
    MEMORY.mkdir(parents=True, exist_ok=True)
    for rel in ("winning-style.md", "example-concepts.md", "README.md"):
        sp = src / rel
        if sp.exists():
            shutil.copy2(sp, MEMORY / rel)
    rt = src / "inspiration" / "reference-thumbnails"
    if rt.exists():
        shutil.copytree(rt, MEMORY / "inspiration" / "reference-thumbnails", dirs_exist_ok=True)
    for d in ("profile/face", "preferences/likes", "preferences/dislikes", "inspiration", "projects"):
        (MEMORY / d).mkdir(parents=True, exist_ok=True)

    def _w(rel, text):
        f = MEMORY / rel
        if not f.exists():
            f.write_text(text, encoding="utf-8")

    _w("profile/style-profile.md", _BLANK_STYLE_TEMPLATE)
    _w("profile/face/INDEX.md",
       "# Face reference photos\n\n| file | angle | expression | notes |\n|------|-------|------------|-------|\n")
    _w("preferences/likes/INDEX.md",
       "# Liked thumbnails\n\n| file | source | why it works |\n|------|--------|--------------|\n")
    _w("preferences/dislikes/INDEX.md",
       "# Disliked thumbnails\n\n| file | source | why to avoid |\n|------|--------|--------------|\n")
    _w("inspiration/INDEX.md",
       "# Inspiration library\n\n| file | creator | technique to borrow |\n|------|---------|---------------------|\n")
    marker.write_text("seeded", encoding="utf-8")


_seed_blank_memory()
SCRIPTS = SKILL_DIR / "scripts"
CONFIG_PATH = STUDIO_DIR / "config.json"
STATIC_DIR = STUDIO_DIR / "static"

# Make the skill's shared fal helpers importable (lib.run_model, upload_refs...).
import sys
sys.path.insert(0, str(SCRIPTS))


# ---------------------------------------------------------------------------
# Multi-user (Supabase auth). Active only when SUPABASE_URL + anon key are set;
# otherwise the app stays single-tenant exactly as before.
# ---------------------------------------------------------------------------
import urllib.request as _urlreq
import hashlib as _hashlib
import time as _time
import shutil as _shutil
import sbstorage

SUPABASE_URL = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY") or ""
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or ""
WORKSPACES = pathlib.Path(os.environ.get("STUDIO_WORKSPACES") or (STUDIO_DIR / "_workspaces"))
MULTIUSER = bool(SUPABASE_URL and SUPABASE_ANON_KEY)

_tok_cache = {}


def verify_supabase_token(token):
    """Return the Supabase user id for a valid access token, else None (cached 60s)."""
    if not token or not MULTIUSER:
        return None
    h = _hashlib.sha256(token.encode()).hexdigest()
    now = _time.time()
    c = _tok_cache.get(h)
    if c and c[1] > now:
        return c[0]
    try:
        req = _urlreq.Request(SUPABASE_URL + "/auth/v1/user",
                              headers={"Authorization": "Bearer " + token, "apikey": SUPABASE_ANON_KEY})
        with _urlreq.urlopen(req, timeout=8) as r:
            d = json.loads(r.read().decode("utf-8"))
        uid = d.get("id")
        if uid:
            _tok_cache[h] = (uid, now + 60)
            return uid
    except Exception:
        return None
    return None


def seed_workspace(base):
    """Seed a fresh per-user workspace with shared methodology + reference thumbnails,
    blank faces/style (so the user gets onboarding). No owner data."""
    base = pathlib.Path(base)
    marker = base / ".seeded"
    if marker.exists():
        return
    src = SKILL_MEMORY
    base.mkdir(parents=True, exist_ok=True)
    for rel in ("winning-style.md", "example-concepts.md", "README.md"):
        sp = src / rel
        if sp.exists():
            _shutil.copy2(sp, base / rel)
    rt = src / "inspiration" / "reference-thumbnails"
    if rt.exists():
        _shutil.copytree(rt, base / "inspiration" / "reference-thumbnails", dirs_exist_ok=True)
    for d in ("profile/face", "preferences/likes", "preferences/dislikes", "inspiration", "projects"):
        (base / d).mkdir(parents=True, exist_ok=True)

    def _w(rel, text):
        f = base / rel
        if not f.exists():
            f.write_text(text, encoding="utf-8")

    _w("profile/style-profile.md", _BLANK_STYLE_TEMPLATE)
    _w("profile/face/INDEX.md", """# Face reference photos

| file | angle | expression | notes |
|------|-------|------------|-------|
""")
    _w("preferences/likes/INDEX.md", """# Liked thumbnails

| file | source | why it works |
|------|--------|--------------|
""")
    _w("preferences/dislikes/INDEX.md", """# Disliked thumbnails

| file | source | why to avoid |
|------|--------|--------------|
""")
    _w("inspiration/INDEX.md", """# Inspiration library

| file | creator | technique to borrow |
|------|---------|---------------------|
""")
    marker.write_text("seeded", encoding="utf-8")


def set_workspace(user_id):
    base = (WORKSPACES / user_id / "memory")
    if not base.exists() and sbstorage.enabled():
        try:
            sbstorage.download_all(user_id, base)   # restore from Supabase on a fresh container/volume
        except Exception:
            pass
    seed_workspace(base)   # no-op if already seeded/restored
    _cur_mem.set(base)
    return base


# ---------------------------------------------------------------------------
# Config / keys  — env first, then studio/config.json (written by Settings UI)
# ---------------------------------------------------------------------------
def _config_path():
    v = _cur_mem.get()
    if v is not None:
        return pathlib.Path(v).parent / "config.json"
    return CONFIG_PATH


def load_config() -> dict:
    cp = _config_path()
    if cp.exists():
        try:
            return json.loads(cp.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_config(cfg: dict) -> None:
    cp = _config_path()
    cp.parent.mkdir(parents=True, exist_ok=True)
    cp.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def apply_config_to_env() -> None:
    """Push saved keys into the process env so fal_client / anthropic pick them up."""
    cfg = load_config()
    if cfg.get("FAL_KEY") and not os.environ.get("FAL_KEY"):
        os.environ["FAL_KEY"] = cfg["FAL_KEY"]
    if cfg.get("ANTHROPIC_API_KEY") and not os.environ.get("ANTHROPIC_API_KEY"):
        os.environ["ANTHROPIC_API_KEY"] = cfg["ANTHROPIC_API_KEY"]


def _has_request() -> bool:
    try:
        from flask import has_request_context
        return has_request_context()
    except Exception:
        return False


def concept_model() -> str:
    if _has_request():
        h = request.headers.get("X-Model")
        if h:
            return h.strip()
    return load_config().get("model") or os.environ.get("THUMB_MODEL") or "claude-sonnet-4-6"


def req_fal_key():
    """fal key for this request. In multi-user mode it is ONLY the user's own key
    (header or their workspace config) -- never a shared/global key."""
    if _has_request():
        h = request.headers.get("X-Fal-Key")
        if h:
            return h.strip()
    k = load_config().get("FAL_KEY")
    if k:
        return k
    return None if MULTIUSER else os.environ.get("FAL_KEY")


def req_anthropic_key():
    if _has_request():
        h = request.headers.get("X-Anthropic-Key")
        if h:
            return h.strip()
    k = load_config().get("ANTHROPIC_API_KEY")
    if k:
        return k
    return None if MULTIUSER else os.environ.get("ANTHROPIC_API_KEY")


def clean_slug(slug: str) -> str:
    """Reject path-traversal in a client-supplied project slug."""
    s = (slug or "").strip().strip("/\\")
    if not s or ".." in s or "/" in s or "\\" in s or s.startswith("."):
        from flask import abort
        abort(400, "invalid project id")
    return s


apply_config_to_env()


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def slugify(text: str, maxlen: int = 48) -> str:
    keep = []
    for ch in (text or "").lower().strip():
        if ch.isalnum():
            keep.append(ch)
        elif ch in " -_":
            keep.append("-")
    slug = "".join(keep)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-")[:maxlen] or "untitled"


def read_text(path: pathlib.Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def safe_under(base: pathlib.Path, candidate: pathlib.Path) -> pathlib.Path:
    """Resolve candidate and ensure it stays within base (path-traversal guard)."""
    base = base.resolve()
    p = candidate.resolve()
    if base != p and base not in p.parents:
        abort(403, "path outside allowed directory")
    return p


def face_refs() -> list:
    """All face reference images currently in memory, as absolute path strings."""
    face_dir = MEMORY / "profile" / "face"
    if not face_dir.exists():
        return []
    exts = {".jpg", ".jpeg", ".png", ".webp"}
    return sorted(str(p) for p in face_dir.iterdir()
                  if p.suffix.lower() in exts and p.is_file())


def list_images(folder: pathlib.Path) -> list:
    exts = {".jpg", ".jpeg", ".png", ".webp"}
    if not folder.exists():
        return []
    return sorted(p for p in folder.iterdir()
                  if p.is_file() and p.suffix.lower() in exts)


def rel_to_memory(p: pathlib.Path) -> str:
    return str(p.resolve().relative_to(MEMORY.resolve())).replace("\\", "/")


# ---------------------------------------------------------------------------
# Jobs — background work (fal calls) with pollable progress
# ---------------------------------------------------------------------------
JOBS = {}
JOBS_LOCK = threading.Lock()
_JOB_SEQ = [0]


def new_job(kind: str) -> str:
    with JOBS_LOCK:
        _JOB_SEQ[0] += 1
        jid = f"job-{_JOB_SEQ[0]}"
        JOBS[jid] = {
            "id": jid, "kind": kind, "status": "running",
            "progress": [], "results": [], "error": None, "pct": 0,
        }
    return jid


def job_log(jid: str, msg: str, pct=None):
    with JOBS_LOCK:
        j = JOBS.get(jid)
        if not j:
            return
        j["progress"].append(msg)
        if pct is not None:
            j["pct"] = pct


def job_add_result(jid: str, result: dict):
    with JOBS_LOCK:
        if jid in JOBS:
            JOBS[jid]["results"].append(result)


def job_done(jid: str, error=None):
    with JOBS_LOCK:
        if jid in JOBS:
            JOBS[jid]["status"] = "error" if error else "done"
            JOBS[jid]["error"] = error
            JOBS[jid]["pct"] = 100


# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------
app = Flask(__name__, static_folder=None)


@app.before_request
def _auth_gate():
    """Multi-user mode (SUPABASE configured): require a valid Supabase session and
    scope the request to that user's workspace. Otherwise: optional shared password."""
    if MULTIUSER:
        p = request.path
        if p == "/" or p.startswith("/static/") or p == "/api/auth-config" or p == "/favicon.ico":
            return
        token = None
        ah = request.headers.get("Authorization", "")
        if ah.startswith("Bearer "):
            token = ah[7:]
        if not token:
            token = request.args.get("token")  # img/download tags can't set headers
        uid = verify_supabase_token(token)
        if not uid:
            return jsonify({"error": "Please sign in."}), 401
        g.user_id = uid
        g._req_start = _time.time()
        set_workspace(uid)
        return
    pw = os.environ.get("APP_PASSWORD")
    if not pw:
        return
    auth = request.authorization
    if not auth or not auth.password or auth.password != pw:
        return Response("Authentication required.", 401,
                        {"WWW-Authenticate": 'Basic realm="Thumbnail Studio"'})


@app.get("/api/auth-config")
def api_auth_config():
    return jsonify({"multiuser": MULTIUSER,
                    "supabase_url": SUPABASE_URL or None,
                    "anon_key": SUPABASE_ANON_KEY or None})


@app.after_request
def no_cache(resp):
    resp.headers["Cache-Control"] = "no-store"
    try:
        if MULTIUSER and sbstorage.enabled() and request.method in ("POST", "PUT", "DELETE") and getattr(g, "user_id", None):
            base = _cur_mem.get()
            if base is not None:
                sbstorage.sync_up_changed(base, g.user_id, getattr(g, "_req_start", 0))
    except Exception:
        pass
    return resp


# ---- static frontend --------------------------------------------------------
@app.get("/")
def index():
    return send_file(STATIC_DIR / "index.html")


@app.get("/static/<path:fname>")
def static_files(fname):
    p = safe_under(STATIC_DIR, STATIC_DIR / fname)
    if not p.exists():
        abort(404)
    return send_file(p)


# ---- serve memory images ----------------------------------------------------
@app.get("/api/file")
def api_file():
    rel = request.args.get("path", "")
    p = safe_under(MEMORY, MEMORY / rel)
    if not p.exists() or not p.is_file():
        abort(404)
    mime = mimetypes.guess_type(str(p))[0] or "application/octet-stream"
    as_download = request.args.get("download")
    return send_file(p, mimetype=mime, as_attachment=bool(as_download),
                     download_name=p.name if as_download else None)


# ---- status / settings ------------------------------------------------------
@app.get("/api/status")
def api_status():
    cfg = load_config()
    return jsonify({
        "fal_key": bool(req_fal_key()),
        "anthropic_key": bool(req_anthropic_key()),
        "model": concept_model(),
        "memory_path": str(MEMORY),
        "faces": len(face_refs()),
        "needs_onboarding": len(face_refs()) == 0,
        "multiuser": MULTIUSER,
    })


@app.post("/api/settings")
def api_settings():
    data = request.get_json(force=True)
    cfg = load_config()
    for k in ("FAL_KEY", "ANTHROPIC_API_KEY", "model"):
        v = (data.get(k) or "").strip()
        if v:
            cfg[k] = v
        elif k in data and data.get(k) == "":
            cfg.pop(k, None)
    save_config(cfg)
    apply_config_to_env()
    if cfg.get("FAL_KEY"):
        os.environ["FAL_KEY"] = cfg["FAL_KEY"]
    if cfg.get("ANTHROPIC_API_KEY"):
        os.environ["ANTHROPIC_API_KEY"] = cfg["ANTHROPIC_API_KEY"]
    return jsonify({"ok": True})


# ---- memory: read everything ------------------------------------------------
def parse_index_rows(md: str) -> list:
    """Parse a simple markdown table (skip header + separator) into row dicts."""
    rows = []
    for line in md.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if not cells:
            continue
        joined = "".join(cells).replace("-", "").replace(" ", "")
        if joined == "":  # separator row
            continue
        if cells[0].lower() in ("file", "name"):  # header
            continue
        rows.append(cells)
    return rows


@app.get("/api/memory")
def api_memory():
    def collection(folder_rel, index_rel):
        folder = MEMORY / folder_rel
        rows = parse_index_rows(read_text(MEMORY / index_rel))
        notes = {}
        for cells in rows:
            fname = cells[0]
            notes[fname] = cells[1:]
        items = []
        for img in list_images(folder):
            items.append({
                "file": img.name,
                "path": rel_to_memory(img),
                "meta": notes.get(img.name, []),
            })
        # also surface index notes that have no matching image (text-only entries)
        return {"items": items, "rows": rows}

    return jsonify({
        "style_profile": read_text(MEMORY / "profile" / "style-profile.md"),
        "example_concepts": read_text(MEMORY / "example-concepts.md"),
        "faces": collection("profile/face", "profile/face/INDEX.md"),
        "likes": collection("preferences/likes", "preferences/likes/INDEX.md"),
        "dislikes": collection("preferences/dislikes", "preferences/dislikes/INDEX.md"),
        "inspiration": _inspiration_tree(),
    })


def _inspiration_tree():
    base = MEMORY / "inspiration"
    rows = parse_index_rows(read_text(base / "INDEX.md"))
    items = []
    if base.exists():
        for img in base.rglob("*"):
            if img.is_file() and img.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
                items.append({"file": img.name, "path": rel_to_memory(img)})
    return {"items": items, "rows": rows}


@app.post("/api/memory/style")
def api_memory_style():
    data = request.get_json(force=True)
    text = data.get("text", "")
    (MEMORY / "profile" / "style-profile.md").write_text(text, encoding="utf-8")
    return jsonify({"ok": True})


@app.post("/api/memory/upload")
def api_memory_upload():
    """Upload an image into a memory collection and append a note to its INDEX."""
    kind = request.form.get("kind", "")  # faces | likes | dislikes | inspiration
    note = request.form.get("note", "").strip()
    source = request.form.get("source", "").strip()
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "no file"}), 400

    targets = {
        "faces": ("profile/face", "profile/face/INDEX.md"),
        "likes": ("preferences/likes", "preferences/likes/INDEX.md"),
        "dislikes": ("preferences/dislikes", "preferences/dislikes/INDEX.md"),
        "inspiration": ("inspiration", "inspiration/INDEX.md"),
    }
    if kind not in targets:
        return jsonify({"error": "bad kind"}), 400
    folder_rel, index_rel = targets[kind]
    folder = MEMORY / folder_rel
    folder.mkdir(parents=True, exist_ok=True)

    safe_name = slugify(pathlib.Path(file.filename).stem) + pathlib.Path(file.filename).suffix.lower()
    dest = folder / safe_name
    n = 1
    while dest.exists():
        dest = folder / f"{pathlib.Path(safe_name).stem}-{n}{pathlib.Path(safe_name).suffix}"
        n += 1
    file.save(str(dest))

    # append a row to INDEX.md
    index_path = MEMORY / index_rel
    row = {
        "faces": f"| {dest.name} | {source or '—'} | {note or '—'} |\n",
        "likes": f"| {dest.name} | {source or '—'} | {note or '—'} |\n",
        "dislikes": f"| {dest.name} | {source or '—'} | {note or '—'} |\n",
        "inspiration": f"| {dest.name} | {source or '—'} | {note or '—'} |\n",
    }[kind]
    with open(index_path, "a", encoding="utf-8") as f:
        f.write(row)

    return jsonify({"ok": True, "path": rel_to_memory(dest)})


@app.post("/api/memory/delete")
def api_memory_delete():
    data = request.get_json(force=True)
    rel = data.get("path", "")
    p = safe_under(MEMORY, MEMORY / rel)
    if p.exists() and p.is_file():
        p.unlink()
        side = p.with_suffix(p.suffix + ".json")
        if side.exists():
            side.unlink()
    if MULTIUSER and sbstorage.enabled() and getattr(g, "user_id", None):
        try:
            sbstorage.delete_prefix(g.user_id + "/" + rel)
        except Exception:
            pass
    return jsonify({"ok": True})


# ---- projects ---------------------------------------------------------------
def project_dir(slug: str) -> pathlib.Path:
    s = (slug or "").strip().strip("/\\")
    if not s or s.startswith(".") or ".." in s or "/" in s or "\\" in s:
        from flask import abort
        abort(400, "invalid project id")
    return MEMORY / "projects" / s


def load_project(slug: str) -> dict:
    pd = project_dir(slug)
    brief = {}
    if (pd / "brief.json").exists():
        brief = json.loads(read_text(pd / "brief.json") or "{}")
    concepts = []
    if (pd / "concepts.json").exists():
        concepts = json.loads(read_text(pd / "concepts.json") or "[]")
    # attach generated images per concept
    for c in concepts:
        gen = pd / "generated" / c["id"]
        c["images"] = [{"path": rel_to_memory(p), "file": p.name}
                       for p in list_images(gen)]
    finals = [{"path": rel_to_memory(p), "file": p.name}
              for p in list_images(pd / "final")]
    feedback = {}
    if (pd / "feedback.json").exists():
        feedback = json.loads(read_text(pd / "feedback.json") or "{}")
    return {"slug": slug, "brief": brief, "concepts": concepts,
            "finals": finals, "feedback": feedback}


@app.get("/api/projects")
def api_projects():
    base = MEMORY / "projects"
    out = []
    if base.exists():
        for d in sorted(base.iterdir()):
            if d.is_dir() and (d / "brief.json").exists():
                brief = json.loads(read_text(d / "brief.json") or "{}")
                n_imgs = sum(1 for _ in (d / "generated").rglob("*")
                             if _.is_file() and _.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}) \
                    if (d / "generated").exists() else 0
                out.append({
                    "slug": d.name,
                    "title": brief.get("title") or d.name,
                    "n_concepts": len(json.loads(read_text(d / "concepts.json") or "[]")),
                    "n_images": n_imgs,
                })
    return jsonify({"projects": out})


@app.get("/api/project/<slug>")
def api_project(slug):
    return jsonify(load_project(slug))


@app.post("/api/project/delete")
def api_project_delete():
    data = request.get_json(force=True)
    slug = data.get("slug", "")
    pd = safe_under(MEMORY / "projects", project_dir(slug))
    if pd.exists():
        import shutil
        shutil.rmtree(pd)
    if MULTIUSER and sbstorage.enabled() and getattr(g, "user_id", None):
        try:
            sbstorage.delete_prefix(g.user_id + "/projects/" + slug)
        except Exception:
            pass
    return jsonify({"ok": True})


# ---- feedback on final generations (like / dislike → memory) ----------------
PREF_TARGETS = {
    "like": ("preferences/likes", "preferences/likes/INDEX.md"),
    "dislike": ("preferences/dislikes", "preferences/dislikes/INDEX.md"),
}


def _remove_index_row(index_path: pathlib.Path, filename: str) -> None:
    """Drop any INDEX.md table row whose first cell is exactly `filename`."""
    if not index_path.exists():
        return
    kept = []
    for line in index_path.read_text(encoding="utf-8").splitlines(keepends=True):
        s = line.strip()
        if s.startswith("|"):
            first = s.strip("|").split("|")[0].strip()
            if first == filename:
                continue
        kept.append(line)
    index_path.write_text("".join(kept), encoding="utf-8")


def _save_pref(verdict: str, src: pathlib.Path, source: str, note: str) -> str:
    """Copy a generated image into the likes/dislikes collection + log a row.

    Returns the new file's memory-relative path.
    """
    import shutil
    folder_rel, index_rel = PREF_TARGETS[verdict]
    folder = MEMORY / folder_rel
    folder.mkdir(parents=True, exist_ok=True)
    safe_name = slugify(src.stem) + src.suffix.lower()
    dest = folder / safe_name
    n = 1
    while dest.exists():
        dest = folder / f"{pathlib.Path(safe_name).stem}-{n}{src.suffix.lower()}"
        n += 1
    shutil.copy2(src, dest)
    with open(MEMORY / index_rel, "a", encoding="utf-8") as f:
        f.write(f"| {dest.name} | {source or '—'} | {note or '—'} |\n")
    return rel_to_memory(dest)


def _remove_pref(saved_rel: str, verdict: str) -> None:
    """Delete a previously-saved like/dislike image + its INDEX row."""
    if not saved_rel:
        return
    p = (MEMORY / saved_rel).resolve()
    try:
        safe_under(MEMORY, p)
    except Exception:
        return
    if p.exists() and p.is_file():
        p.unlink()
    _, index_rel = PREF_TARGETS[verdict]
    _remove_index_row(MEMORY / index_rel, p.name)


@app.post("/api/feedback")
def api_feedback():
    """Like / dislike a final generated thumbnail.

    Body: {slug, path (memory-relative image), verdict: like|dislike, note?}
    Sending the verdict that's already set toggles it off (clears the memory copy).
    Stores per-project state in feedback.json so the UI can show it after reload.
    """
    data = request.get_json(force=True)
    slug = data.get("slug", "")
    rel = data.get("path", "")
    verdict = data.get("verdict", "")
    note = (data.get("note") or "").strip()
    if verdict not in ("like", "dislike"):
        return jsonify({"error": "verdict must be like or dislike"}), 400

    src = safe_under(MEMORY, MEMORY / rel)
    if not src.exists() or not src.is_file():
        abort(404)
    pd = project_dir(slug)
    if not pd.exists():
        return jsonify({"error": "unknown project"}), 404

    brief = json.loads(read_text(pd / "brief.json") or "{}")
    source = f"studio gen — {brief.get('title') or slug}"

    fb_path = pd / "feedback.json"
    fb = json.loads(read_text(fb_path) or "{}")
    prev = fb.get(rel)

    # Clear any prior saved copy for this image before re-classifying.
    if prev and prev.get("saved_rel"):
        _remove_pref(prev["saved_rel"], prev["verdict"])

    toggled_off = bool(prev and prev.get("verdict") == verdict and not note)
    if toggled_off:
        fb.pop(rel, None)
        result = {"verdict": None}
    else:
        saved_rel = _save_pref(verdict, src, source, note)
        fb[rel] = {"verdict": verdict, "note": note, "saved_rel": saved_rel}
        result = {"verdict": verdict, "note": note, "saved_rel": saved_rel}

    fb_path.write_text(json.dumps(fb, indent=2), encoding="utf-8")
    return jsonify({"ok": True, **result})


# ---- concepts (Claude) ------------------------------------------------------
CONCEPT_TOOL = {
    "name": "emit_concepts",
    "description": "Return the list of distinct YouTube thumbnail concepts.",
    "input_schema": {
        "type": "object",
        "properties": {
            "concepts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Short hook name"},
                        "style": {"type": "string",
                                  "enum": ["cinematic-dark", "income-proof", "storyboard",
                                           "shocked-laptop", "graphic-dark", "graphic-light"],
                                  "description": "Validated style this concept uses. Default cinematic-dark."},
                        "style_ref": {"type": "string",
                                      "description": "Filename of a reference thumbnail from the provided "
                                                     "library to copy (e.g. A5-faceless-channel-income-chart.png), "
                                                     "or empty to use the style's default reference."},
                        "big_text": {"type": "string", "description": "The main hook text, 2-4 words (blank is OK)"},
                        "secondary_text": {"type": "string", "description": "Optional smaller supporting text"},
                        "emotion": {"type": "string", "description": "Leo's expression/pose"},
                        "scene": {"type": "string", "description": "Background + the ONE clean graphic element / metaphor"},
                        "composition": {"type": "string", "description": "Rule-of-thirds layout (face one third, hook another)"},
                        "why": {"type": "string", "description": "Why it works / which 2-3 types it combines / what it pulls from memory"},
                        "finishing": {"type": "string", "description": "Post-gen finishing (darken behind text, blur bg, composite real screenshot)"},
                        "image_prompt": {"type": "string",
                                         "description": "Full literal cinematic fal image prompt, ready to send"},
                    },
                    "required": ["name", "style", "big_text", "emotion", "scene",
                                 "composition", "why", "image_prompt"],
                },
            }
        },
        "required": ["concepts"],
    },
}


def reference_library() -> list:
    """Reference thumbnails available to copy (the style-ref technique)."""
    rt = MEMORY / "inspiration" / "reference-thumbnails"
    return [p.name for p in list_images(rt)] if rt.exists() else []


def build_concept_context() -> str:
    parts = []
    # winning-style.md is the current PREFERRED guidance — lead with it.
    parts.append("## WINNING STYLE — read first (the preferred cinematic default + style-ref technique)\n"
                 + read_text(MEMORY / "winning-style.md"))
    parts.append("## STYLE PROFILE\n" + read_text(MEMORY / "profile" / "style-profile.md"))
    parts.append("## THUMBNAIL PRINCIPLES (craft field guide)\n"
                 + read_text(SKILL_DIR / "references" / "thumbnail-principles.md"))
    parts.append("## REVERSE-ENGINEERED EXAMPLES + ELEMENT LIBRARY\n"
                 + read_text(SKILL_DIR / "references" / "reverse-engineered-examples.md"))
    parts.append("## EXAMPLE CONCEPTS (the creator's own layout vocabulary — secondary to cinematic)\n"
                 + read_text(MEMORY / "example-concepts.md"))
    parts.append("## LIKES (what works)\n" + read_text(MEMORY / "preferences" / "likes" / "INDEX.md"))
    parts.append("## DISLIKES (avoid)\n" + read_text(MEMORY / "preferences" / "dislikes" / "INDEX.md"))
    parts.append("## INSPIRATION (techniques to borrow)\n" + read_text(MEMORY / "inspiration" / "INDEX.md"))
    refs = reference_library()
    if refs:
        parts.append("## REFERENCE THUMBNAILS available to copy (use one as the style anchor)\n- "
                     + "\n- ".join(refs))
    return "\n\n".join(parts)


CONCEPT_SYSTEM = """You are the thumbnail concept director for a specific YouTube creator (Leo,
channel Fluxomate — AI/automation for agencies). You write thumbnail concepts that match THIS
creator's validated, saved taste — never generic AI thumbnails. You are given his full memory
(WINNING STYLE, style profile, principles, an element library + reverse-engineered references,
example concepts, likes, dislikes) then a new video's transcript/context.

CORE METHOD — copy a reference (the single biggest quality lever):
- Each generation works best when ANCHORED to a specific reference thumbnail it recreates. For
  every concept, pick which validated style it uses and (when relevant) which reference thumbnail
  from the provided library to copy. The app will pass that reference to the image model as a
  style anchor; you just choose it and design the scene/hook to fit it.

STYLE — default to CINEMATIC (this is what performed):
- Prefer the cinematic film-still look: Leo studio-lit with strong side/rim light, deep shadows,
  shallow depth of field, premium editorial grade, slight vignette — composited on a CLEAN
  DESIGNED background (solid deep black/charcoal, or a brand orange→red radial glow), with ONE
  clean graphic element and a bold film-title headline. Prefer a VISUAL METAPHOR that tells the
  story over literal charts/dashboards/icon-grids.
- The validated style menu (pick per concept): cinematic-dark (default), income-proof (bright,
  off-white, smile, app icons + rising income chart with $ callout), storyboard (hand-drawn
  whiteboard + red marker title/arrow), shocked-laptop (extreme shock over a glowing laptop +
  floating result cards). The older graphic/icon-grid/dashboard look is SECONDARY — use it only
  for an occasional pure data/announcement video (graphic-dark / graphic-light).

CALIBRATION RULES (must follow):
- Leo is from the face refs: describe him as "a young man with short dark hair and short beard in
  a bright orange hoodie (use his exact face from the reference photos)". Never invent his face.
- Background = solid deep black/charcoal OR brand orange→red radial glow. Glow behind him is warm
  orange/red, NEVER white. No white cut-out / sticker outline around him.
- Any people inside graphic elements = REAL photographic headshots, never cartoon avatars.
- Premium bold EXTRA-CONDENSED sans headline integrated like a film title, top-left; one key word
  tinted orange (#FF7300) or red, the rest white. Text ≤4 words ("blank is fine").
- Compose on the rule of thirds (face one third, hook another). Combine 2-3 of the thumbnail
  TYPES and it should read clearly at phone size. $10k-designer polish — gloss + depth, never
  "makeable in 5 minutes".
- Honour the palette (orange main); vary only the highlight colour per video.

OUTPUT per concept via emit_concepts:
- style + (optional) style_ref filename from the library to copy.
- A complete literal image_prompt ready for the model: open cinematic ones with "Cinematic
  landscape YouTube thumbnail, film-still quality." then subject + expression, lighting, the clean
  background, the ONE graphic element, and the exact quoted headline with its colours. Do NOT add
  any "use the last reference as style only" wording — the app appends that automatically.
- finishing notes (darken behind text / blur bg / composite a real screenshot) when relevant.
Produce genuinely distinct angles unless told to adapt one reference. Return ONLY via emit_concepts."""


RESEARCH_TOOL = {
    "name": "emit_profile",
    "description": "Return the researched channel profile used to seed thumbnail style.",
    "input_schema": {
        "type": "object",
        "properties": {
            "channel_name": {"type": "string"},
            "niche": {"type": "string", "description": "niche + target audience, one concise line"},
            "persona": {"type": "string", "description": "the creator's on-camera appearance & persona for thumbnails"},
            "brand_color": {"type": "string", "description": "hex like #FF7300"},
            "style_notes": {"type": "string", "description": "2-4 short notes on their thumbnail style/devices"},
        },
        "required": ["niche", "persona"],
    },
}


@app.post("/api/onboard/research")
def api_onboard_research():
    """Research a creator's channel (web search via Claude) and return a profile to
    auto-fill onboarding. Uses the user's Anthropic key (header or saved)."""
    key = req_anthropic_key()
    if not key:
        return jsonify({"error": "Add your Anthropic key first."}), 400
    data = request.get_json(force=True)
    channel = (data.get("channel") or "").strip()
    if not channel:
        return jsonify({"error": "Enter your channel URL or @handle."}), 400
    try:
        import anthropic
    except ImportError:
        return jsonify({"error": "The anthropic package isn't installed."}), 500

    client = anthropic.Anthropic(api_key=key)
    prompt = (
        "Research this YouTube channel: " + channel + "\n\n"
        "Find what the channel is about, the creator's on-camera appearance and persona, their niche "
        "and target audience, and the brand/accent colours used in their thumbnails. Use web search to "
        "look them up. Then call emit_profile with your findings. If you cannot find the channel, infer "
        "sensible values from the handle/name."
    )

    def run(use_web):
        kw = {"model": concept_model(), "max_tokens": 2500, "tools": [RESEARCH_TOOL],
              "messages": [{"role": "user", "content": prompt}]}
        if use_web:
            kw["tools"] = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 5}, RESEARCH_TOOL]
        else:
            kw["tool_choice"] = {"type": "tool", "name": "emit_profile"}
        return client.messages.create(**kw)

    def extract(msg):
        for b in msg.content:
            if getattr(b, "type", None) == "tool_use" and getattr(b, "name", None) == "emit_profile":
                return b.input
        return None

    prof = None
    try:
        prof = extract(run(True))          # with web search
    except Exception:
        prof = None
    if not prof:
        try:
            prof = extract(run(False))     # fallback: knowledge-only, forced emit
        except Exception as e:
            return jsonify({"error": "Research failed: " + str(e)}), 500
    if not prof:
        return jsonify({"error": "Couldn't research that channel — fill it in manually."}), 200
    return jsonify({"profile": prof})


@app.post("/api/concepts")
def api_concepts():
    data = request.get_json(force=True)
    title = (data.get("title") or "").strip()
    transcript = (data.get("transcript") or "").strip()
    context = (data.get("context") or "").strip()
    extra_inspo = (data.get("inspiration") or "").strip()
    inspo_images = data.get("inspiration_images") or []  # [{name, media_type, data(base64)}]
    mode = (data.get("mode") or "scratch").strip()        # 'scratch' | 'inspiration'
    n = int(data.get("n") or 5)
    avoid = data.get("avoid") or []  # names of existing concepts to not repeat

    if mode != "inspiration" and not (transcript or context):
        return jsonify({"error": "Paste a transcript or some video context first."}), 400
    if mode == "inspiration" and not inspo_images:
        return jsonify({"error": "Add the reference image you want to base concepts on."}), 400

    try:
        import anthropic
    except ImportError:
        return jsonify({"error": "The 'anthropic' package isn't installed. Run: pip install anthropic"}), 500

    key = os.environ.get("ANTHROPIC_API_KEY") or load_config().get("ANTHROPIC_API_KEY")
    if not key:
        return jsonify({"error": "No Anthropic API key. Add it in Settings (or set ANTHROPIC_API_KEY)."}), 400

    user_parts = [build_concept_context(), "\n\n---\n\n## NEW VIDEO"]
    if title:
        user_parts.append(f"Title: {title}")
    if context:
        user_parts.append(f"Context / hook / vibe:\n{context}")
    if transcript:
        user_parts.append(f"Transcript:\n{transcript[:14000]}")
    if extra_inspo:
        user_parts.append(f"Extra inspiration the creator dropped in for THIS video:\n{extra_inspo}")
    if avoid:
        user_parts.append("Do NOT repeat these existing concept angles: " + "; ".join(avoid))

    # Build the message content: text, then any pasted/uploaded inspiration images
    # as visual references Claude can actually see and borrow technique from.
    allowed_media = {"image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif"}
    image_blocks = []
    for img in inspo_images:
        mt = (img.get("media_type") or "").lower()
        if mt == "image/jpg":
            mt = "image/jpeg"
        b64 = img.get("data") or ""
        if mt in allowed_media and b64:
            image_blocks.append({
                "type": "image",
                "source": {"type": "base64", "media_type": mt, "data": b64},
            })
    if mode == "inspiration":
        # Anchor the whole batch to the attached reference(s): recreate, don't diverge.
        user_parts.append(
            f"## TASK — RECREATE FROM INSPIRATION\n"
            f"The {len(image_blocks)} image(s) below are the SPECIFIC reference this batch is based on. "
            f"Study the reference closely — its layout, composition by thirds, the text placement and "
            f"weight, the color story, the background device, the subject's pose/expression and crop. "
            f"Produce {n} concepts that all RECREATE this reference's structure and technique, but rebuilt "
            f"as THIS creator's thumbnail: his face (from his face refs, in the orange wardrobe), his brand "
            f"orange (#FF7300) accent, and the hook/number for THIS video. Keep the reference's winning "
            f"layout; vary only secondary details across the {n} versions (exact hook wording, expression, "
            f"color emphasis, which element is circled). Each image_prompt must read as a faithful adaptation "
            f"of the reference, not a different idea. Do NOT copy any text or faces from the reference itself."
        )
    elif image_blocks:
        user_parts.append(
            f"The creator also attached {len(image_blocks)} reference image(s) below as visual "
            "inspiration for THIS thumbnail — study their composition, text treatment, color and "
            "framing and borrow the technique (do NOT copy them literally; they are not the creator's face)."
        )

    if mode == "inspiration":
        user_parts.append(f"\nWrite {n} faithful adaptations of the reference now via emit_concepts.")
    else:
        user_parts.append(f"\nWrite {n} distinct concepts now via emit_concepts.")

    text_block = {"type": "text", "text": "\n\n".join(user_parts)}
    client = anthropic.Anthropic(api_key=key)

    def _call(content):
        return client.messages.create(
            model=concept_model(),
            max_tokens=6000,
            system=CONCEPT_SYSTEM,
            tools=[CONCEPT_TOOL],
            tool_choice={"type": "tool", "name": "emit_concepts"},
            messages=[{"role": "user", "content": content}],
        )

    warning = None
    try:
        msg = _call([text_block] + image_blocks)
    except Exception as e:
        # An unreadable inspiration image shouldn't sink the whole request — retry text-only.
        if image_blocks:
            try:
                msg = _call([text_block])
                warning = "One or more inspiration images couldn't be read, so concepts were written from the text only."
                image_blocks = []  # don't save the bad images either
            except Exception as e2:
                return jsonify({"error": f"Anthropic call failed: {e2}"}), 500
        else:
            return jsonify({"error": f"Anthropic call failed: {e}"}), 500

    concepts = []
    for block in msg.content:
        if block.type == "tool_use" and block.name == "emit_concepts":
            concepts = block.input.get("concepts", [])
    if not concepts:
        return jsonify({"error": "Claude returned no concepts. Try again."}), 500

    # assign ids and pending status, continuing numbering if avoiding existing
    start = int(data.get("start_index") or 1)
    for i, c in enumerate(concepts, start=start):
        c["id"] = f"concept-{i:02d}"
        c["status"] = "pending"

    # persist project
    slug = data.get("slug")
    if not slug:
        base = slugify(title or context[:40] or "")
        if not base:
            base = "inspiration-" + time.strftime("%m%d-%H%M%S") if mode == "inspiration" \
                else "untitled-" + time.strftime("%m%d-%H%M%S")
        slug = base
    pd = project_dir(slug)
    pd.mkdir(parents=True, exist_ok=True)
    brief = {"title": title, "context": context, "mode": mode,
             "transcript_excerpt": transcript[:2000], "slug": slug}
    (pd / "brief.json").write_text(json.dumps(brief, indent=2), encoding="utf-8")

    # keep any attached inspiration images with the project
    if image_blocks:
        import base64 as _b64
        insp_dir = pd / "inspiration"
        insp_dir.mkdir(parents=True, exist_ok=True)
        ext_map = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp", "image/gif": "gif"}
        existing_n = len(list_images(insp_dir))
        for k, blk in enumerate(image_blocks, start=existing_n + 1):
            mt = blk["source"]["media_type"]
            try:
                raw = _b64.b64decode(blk["source"]["data"])
                (insp_dir / f"inspo-{k:02d}.{ext_map.get(mt, 'png')}").write_bytes(raw)
            except Exception:
                pass

    # merge with existing concepts (when "generate more")
    existing = []
    if (pd / "concepts.json").exists() and data.get("append"):
        existing = json.loads(read_text(pd / "concepts.json") or "[]")
    all_concepts = existing + concepts
    (pd / "concepts.json").write_text(json.dumps(all_concepts, indent=2), encoding="utf-8")
    _write_concepts_md(pd, brief, all_concepts)

    return jsonify({"slug": slug, "concepts": concepts, "all": all_concepts, "warning": warning})


def _write_concepts_md(pd, brief, concepts):
    """Human-readable mirror so the skill can still read the project."""
    lines = [f"# Concepts — {brief.get('title') or pd.name}\n"]
    for c in concepts:
        lines.append(f"## [{'x' if c.get('status')=='generated' else ' '}] {c['id']} — {c.get('name','')}")
        lines.append(f"- **Style:** {c.get('style', c.get('mode',''))}"
                     + (f"  (ref: {c['style_ref']})" if c.get('style_ref') else ''))
        lines.append(f"- **Big text:** \"{c.get('big_text','')}\"")
        if c.get("secondary_text"):
            lines.append(f"- **Secondary:** \"{c['secondary_text']}\"")
        lines.append(f"- **Emotion:** {c.get('emotion','')}")
        lines.append(f"- **Scene:** {c.get('scene','')}")
        lines.append(f"- **Composition:** {c.get('composition','')}")
        lines.append(f"- **Why:** {c.get('why','')}")
        if c.get("finishing"):
            lines.append(f"- **Finishing:** {c['finishing']}")
        lines.append(f"- **Prompt:** {c.get('image_prompt','')}\n")
    (pd / "concepts.md").write_text("\n".join(lines), encoding="utf-8")


@app.post("/api/concept/update")
def api_concept_update():
    """Edit or set status of a single concept (approve/decline/edit)."""
    data = request.get_json(force=True)
    slug = data["slug"]
    cid = data["id"]
    pd = project_dir(slug)
    concepts = json.loads(read_text(pd / "concepts.json") or "[]")
    for c in concepts:
        if c["id"] == cid:
            for k in ("name", "style", "style_ref", "mode", "big_text", "secondary_text",
                      "emotion", "scene", "composition", "why", "finishing", "image_prompt", "status"):
                if k in data:
                    c[k] = data[k]
    (pd / "concepts.json").write_text(json.dumps(concepts, indent=2), encoding="utf-8")
    brief = json.loads(read_text(pd / "brief.json") or "{}")
    _write_concepts_md(pd, brief, concepts)
    return jsonify({"ok": True})


# ---- generation (fal) -------------------------------------------------------
# Default reference thumbnail each validated style copies (the style-ref technique).
STYLE_DEFAULT_REF = {
    "income-proof": "inspiration/reference-thumbnails/A5-faceless-channel-income-chart.png",
    "storyboard": "inspiration/reference-thumbnails/A1-ai-animation-storyboard.png",
    "shocked-laptop": "inspiration/reference-thumbnails/A2-100-ads-in-5-min-shocked-laptop.png",
    "cinematic-dark": "preferences/likes/23v1-why-they-leave-BEST.jpg",
}

GENERATE_PY = SCRIPTS / "generate.py"


def _resolve_style_ref(c, extra_ref, pd):
    """Choose the thumbnail to copy for this concept, in priority order.

    1. an explicit image (e.g. 'more like this one'),
    2. the project's pasted inspiration anchor (inspiration mode),
    3. the concept's chosen library reference,
    4. the default reference for the concept's validated style.
    Returns an absolute path string or None.
    """
    # 1. explicit ref (memory-relative)
    if extra_ref:
        base = MEMORY.resolve()
        p = (MEMORY / extra_ref).resolve()
        if (p == base or str(p).startswith(str(base) + os.sep)) and p.exists():
            return str(p)
    # 2. pasted inspiration anchor
    insp = list_images(pd / "inspiration")
    if insp:
        return str(insp[0].resolve())
    # 3. concept-named library reference
    sref = (c.get("style_ref") or "").strip()
    if sref:
        cand = (MEMORY / "inspiration" / "reference-thumbnails" / pathlib.Path(sref).name).resolve()
        if cand.exists():
            return str(cand)
    # 4. style default
    default_rel = STYLE_DEFAULT_REF.get(c.get("style") or "cinematic-dark")
    if default_rel:
        cand = (MEMORY / default_rel).resolve()
        if cand.exists():
            return str(cand)
    return None


def _sb_sync_worker(base, since):
    try:
        if MULTIUSER and sbstorage.enabled() and base is not None:
            sbstorage.sync_up_changed(base, pathlib.Path(base).parent.name, since)
    except Exception:
        pass


def _gen_worker(jid, slug, concept_ids, num, extra_ref=None, name_prefix="v",
                edit_instruction=None):
    """Generate by driving the skill's own generate.py (nano-banana-2 + style-ref).

    Shelling out to the skill script means the studio always uses the skill's
    current generation logic instead of a private copy.
    """
    _w_start = _time.time()
    _w_base = _cur_mem.get()
    try:
        pd = project_dir(slug)
        concepts = json.loads(read_text(pd / "concepts.json") or "[]")
        by_id = {c["id"]: c for c in concepts}
        faces = face_refs()
        total = len(concept_ids)
        any_ok = False
        errors = []

        for idx, cid in enumerate(concept_ids, start=1):
            c = by_id.get(cid)
            if not c:
                continue
            job_log(jid, f"Concept {idx}/{total}: {c.get('name','')} — preparing", pct=int((idx - 1) / total * 100))

            out_dir = pd / "generated" / cid
            out_dir.mkdir(parents=True, exist_ok=True)
            # write the prompt to a file so long prompts don't need shell escaping
            cdir = pd / "concepts"
            cdir.mkdir(parents=True, exist_ok=True)
            prompt_text = c.get("image_prompt", "")
            if edit_instruction:
                prompt_text += (
                    "\n\nEDIT REQUESTED — start from the FINAL reference image (the creator's own "
                    "previously generated thumbnail) and keep everything about it the same: the exact "
                    "composition, the subject's pose and identity, the background, lighting and text. "
                    f"Change ONLY this: {edit_instruction}"
                )
            prompt_file = cdir / f"{cid}.txt"
            prompt_file.write_text(prompt_text, encoding="utf-8")

            style_ref = _resolve_style_ref(c, extra_ref, pd)
            before = {p.name for p in list_images(out_dir)}
            batch_prefix = f"{name_prefix}{len(before) + 1}_"  # unique per batch so 'more' appends

            cmd = [sys.executable, str(GENERATE_PY),
                   "--prompt-file", str(prompt_file),
                   "--refs", ",".join(faces),
                   "--model", "nano-banana-2", "--resolution", "2K",
                   "--num", str(num), "--aspect", "16:9", "--format", "jpeg",
                   "--out", str(out_dir), "--name", batch_prefix]
            if style_ref:
                cmd += ["--style-ref", style_ref]
                job_log(jid, f"Concept {idx}/{total}: copying style of {pathlib.Path(style_ref).name}")

            job_log(jid, f"Concept {idx}/{total}: generating {num} variation(s)…")
            _env = os.environ.copy()
            if MULTIUSER:
                _env.pop("FAL_KEY", None)
            _fk = req_fal_key()
            if _fk:
                _env["FAL_KEY"] = _fk
            proc = subprocess.Popen(cmd, cwd=str(SKILL_DIR), env=_env,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, encoding="utf-8", errors="replace", bufsize=1)
            tail = []
            for line in proc.stdout:
                line = line.rstrip()
                if not line:
                    continue
                tail.append(line)
                tail[:] = tail[-12:]
                if line.startswith("  ·") or "uploading" in line or "calling" in line or line.startswith("saved"):
                    job_log(jid, "    " + line.strip())
            proc.wait()

            new_imgs = sorted(p for p in list_images(out_dir) if p.name not in before)
            if proc.returncode == 0 and new_imgs:
                any_ok = True
                saved = [{"path": rel_to_memory(p), "file": p.name} for p in new_imgs]
                job_add_result(jid, {"concept_id": cid, "images": saved})
                job_log(jid, f"Concept {idx}/{total}: done — {len(saved)} image(s)", pct=int(idx / total * 100))
                c["status"] = "generated"
            else:
                msg = "\n".join(tail[-4:]) or "generation failed"
                errors.append(f"{cid}: {msg}")
                job_log(jid, f"Concept {idx}/{total}: failed — {msg}")

        (pd / "concepts.json").write_text(json.dumps(concepts, indent=2), encoding="utf-8")
        brief = json.loads(read_text(pd / "brief.json") or "{}")
        _write_concepts_md(pd, brief, concepts)
        _sb_sync_worker(_w_base, _w_start)
        if any_ok:
            job_done(jid)
        else:
            job_done(jid, error="; ".join(errors) or "No images were generated.")
    except Exception as e:
        job_done(jid, error=f"{e}\n{traceback.format_exc()}")


def _spawn(target, *args):
    """Start a worker thread that inherits the current request's per-user workspace."""
    base = _cur_mem.get()

    def _run():
        if base is not None:
            _cur_mem.set(base)
        target(*args)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return t


@app.post("/api/generate")
def api_generate():
    if not req_fal_key():
        return jsonify({"error": "Add your fal.ai key in Settings/onboarding first."}), 400
    data = request.get_json(force=True)
    slug = data["slug"]
    concept_ids = data["concept_ids"]
    num = int(data.get("num") or 3)
    extra_ref = data.get("extra_ref")  # memory-relative path of an image to use as a ref
    jid = new_job("generate")
    t = _spawn(_gen_worker, jid, slug, concept_ids, num, extra_ref)
    return jsonify({"job_id": jid})


@app.post("/api/edit")
def api_edit():
    """Apply an edit comment to ONE final thumbnail and regenerate variations.

    Body: {slug, concept_id, path (the image to edit), instruction, num?}
    The source image is used as the style/layout anchor so the edit keeps that
    exact thumbnail and changes only what the instruction asks.
    """
    if not req_fal_key():
        return jsonify({"error": "Add your fal.ai key in Settings/onboarding first."}), 400
    data = request.get_json(force=True)
    slug = data["slug"]
    cid = data["concept_id"]
    rel = data["path"]
    instruction = (data.get("instruction") or "").strip()
    if not instruction:
        return jsonify({"error": "Describe the edit you want."}), 400
    num = int(data.get("num") or 2)
    jid = new_job("edit")
    t = _spawn(_gen_worker, jid, slug, [cid], num, rel, "edit", instruction)
    return jsonify({"job_id": jid})


def _upscale_worker(jid, rel_path, factor):
    _w_start = _time.time()
    _w_base = _cur_mem.get()
    try:
        import lib
        _fk = req_fal_key()
        if _fk:
            os.environ["FAL_KEY"] = _fk
        src = safe_under(MEMORY, MEMORY / rel_path)
        # final dir = project's final folder
        # rel like projects/<slug>/generated/<cid>/v2.jpg
        parts = pathlib.Path(rel_path).parts
        if "projects" in parts:
            slug = parts[parts.index("projects") + 1]
            out_dir = project_dir(slug) / "final"
        else:
            out_dir = src.parent / "final"
        out_dir.mkdir(parents=True, exist_ok=True)

        job_log(jid, "Uploading image…", pct=20)
        image_url = lib.upload_refs([str(src)])[0]
        job_log(jid, f"Upscaling {factor}×…", pct=40)
        result = lib.run_model("fal-ai/clarity-upscaler", {
            "image_url": image_url, "upscale_factor": factor,
            "prompt": "masterpiece, best quality, highres, sharp, vibrant",
            "creativity": 0.2, "resemblance": 0.8,
        })
        img = result.get("image")
        if not img or not img.get("url"):
            job_done(jid, error="No upscaled image returned.")
            return
        dest = out_dir / f"{src.stem}-upscaled-{int(factor)}x.png"
        lib.download(img["url"], dest)
        job_add_result(jid, {"path": rel_to_memory(dest), "file": dest.name,
                             "width": img.get("width"), "height": img.get("height")})
        job_log(jid, "Done.", pct=100)
        _sb_sync_worker(_w_base, _w_start)
        job_done(jid)
    except SystemExit as e:
        job_done(jid, error=str(e))
    except Exception as e:
        job_done(jid, error=f"{e}\n{traceback.format_exc()}")


@app.post("/api/upscale")
def api_upscale():
    if not req_fal_key():
        return jsonify({"error": "Add your fal.ai key in Settings/onboarding first."}), 400
    data = request.get_json(force=True)
    rel_path = data["path"]
    factor = float(data.get("factor") or 2)
    jid = new_job("upscale")
    t = _spawn(_upscale_worker, jid, rel_path, factor)
    return jsonify({"job_id": jid})


@app.get("/api/job/<jid>")
def api_job(jid):
    with JOBS_LOCK:
        j = JOBS.get(jid)
        if not j:
            abort(404)
        return jsonify(dict(j))


if __name__ == "__main__":
    print("\n  Thumbnail Studio")
    print("  ----------------")
    print(f"  memory : {MEMORY}")
    print(f"  open   : http://127.0.0.1:5005\n")
    app.run(host="127.0.0.1", port=5005, threaded=True, debug=False)
