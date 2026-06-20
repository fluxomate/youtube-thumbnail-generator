# 🎯 YouTube Thumbnail Generator — Skill + Studio

An AI thumbnail system that makes **YouTube thumbnails with your real face and your taste** —
not generic AI images. It learns what you look like, the styles that work for your channel,
and which reference thumbnails to copy, then turns a video transcript into approved concepts
and finished thumbnails using [fal.ai](https://fal.ai) (nano‑banana) for images.

There are **two ways to use it**, and this repo contains both:

| | What it is | Best for |
|---|---|---|
| **1. The Skill** | A [Claude Code](https://claude.com/claude-code) skill you talk to in your terminal | People who live in Claude Code and want it in their workflow |
| **2. The Studio** | A local web app (point‑and‑click UI) wrapping the same engine | People who want a clean visual tool — paste transcript → concepts → thumbnails |

> 🔑 **No API keys are included in this repo.** You bring your own
> [fal.ai key](https://fal.ai/dashboard/keys) (and an
> [Anthropic key](https://console.anthropic.com) for the app). Everything runs locally;
> the only outbound calls are to fal.ai (images) and Anthropic (concept writing).

---

# 1. The Skill

A local, memory‑backed thumbnail studio for Claude Code. It remembers what you look like,
the thumbnails you like/dislike, and inspiration from other creators, then turns a video's
transcript + context into approved concepts and real images via fal.ai. Everything is stored
locally in `memory/`.

**The core idea:** the best results come from **copying a proven reference thumbnail** —
your face + brand are kept, while the model recreates a winning layout/lighting/text style.

### 📦 What's inside the skill (`.claude/skills/youtube-thumbnail-generator/`)
```
SKILL.md                     how the skill thinks + the workflow
references/                  the craft guides (principles, prompting, fal params,
                             reverse‑engineered examples + an element library)
scripts/                     generate.py, upscale.py, init_memory.py, lib.py
memory/                      YOUR data: faces, style, likes/dislikes, inspiration, projects
```

### 🚀 Step‑by‑step: use it for your own channel

**1. Prerequisites**
- [Claude Code](https://claude.com/claude-code) installed
- Python 3.10+ and `pip install fal-client`
- A free [fal.ai API key](https://fal.ai/dashboard/keys)

**2. Install the skill**
- Copy `.claude/skills/youtube-thumbnail-generator/` into your project's `.claude/skills/`
  folder (or your user‑level skills folder).
- Set your key:
  - PowerShell (this session): `$env:FAL_KEY = "your-key"`
  - Permanent (Windows): `setx FAL_KEY "your-key"` then restart the terminal
  - macOS/Linux: `export FAL_KEY="your-key"`

**3. Make it *yours* (one‑time setup — this is what makes it not generic)**
- Scaffold the memory tree: `python scripts/init_memory.py`
- **Add your face:** drop 3–5 clear photos of yourself (front + 3/4 angle, varied
  expressions) into `memory/profile/face/`. More good refs = better likeness.
- **Fill your style:** edit `memory/profile/style-profile.md` — your niche, audience,
  on‑camera persona, signature colours and fonts.
- **(Optional) Add reference thumbnails to copy:** save a few high‑performing thumbnails you
  admire into `memory/inspiration/reference-thumbnails/` — these become the "copy this look"
  anchors. Cross‑niche references work best.

**4. Make thumbnails (just talk to Claude Code)**
- Paste your **video transcript or idea** and say *"give me thumbnail concepts."*
- It reads your memory and writes ~5 distinct concepts. **Approve** the ones you like.
- It generates each approved concept with **your face + a copied reference style**, 16:9, a
  few variations.
- Iterate: *"more like v2"*, *"make it like THIS thumbnail"* (paste one), *"punchier text"*,
  or **upscale** the winner.

**5. Teach it your taste (so it gets sharper over time)**
- *"Save this as a like / dislike"* → it stores the image + **why**.
- *"Add this creator's thumbnail as inspiration"* → it logs the technique to borrow.
- Patterns get folded into your `style-profile.md`, so future concepts start better.

See [`SKILL.md`](.claude/skills/youtube-thumbnail-generator/SKILL.md) for the full method and
[`references/`](.claude/skills/youtube-thumbnail-generator/references) for the craft guides.

---

# 2. The Studio (web app)

A local web app — the same engine with a beautiful point‑and‑click UI. Paste a transcript,
get concepts in your style, turn them into thumbnails, upscale and download. It reads and
writes the **same `memory/` folder** as the skill, so the two stay in sync.

### ✨ The flow
1. **Intake** — choose **From scratch** (concepts from your memory) or **From inspiration**
   (recreate one reference thumbnail). Paste your transcript / context, and drop or **paste
   (Ctrl+V) inspiration images** — the model actually looks at them.
2. **Concepts** — Claude writes distinct concepts in your validated styles. Approve, edit,
   decline, or generate more.
3. **Thumbnails** — selected concepts generate variations via fal. View, **upscale 2×**,
   **more like this**, and download.
- **Memory** tab — edit your style profile and manage faces / likes / dislikes / inspiration.
- **Settings** — paste your own keys (stored locally, never committed).

### ▶️ Run it locally
```bash
# from the repo root
pip install flask anthropic fal-client      # one‑time
python studio/server.py                      # then open http://127.0.0.1:5005
```
On Windows you can also double‑click `studio/Start Thumbnail Studio.bat`.

Then open **Settings** and paste your **fal.ai** key (images) and **Anthropic** key (concepts).
Keys are saved to `studio/config.json`, which is **git‑ignored** and never leaves your machine.

See [`studio/README.md`](studio/README.md) for details on how the app connects to the skill.

---

## 🔒 Privacy & keys
- All your data (faces, style, projects, generated images) stays **local** in `memory/`.
- API keys live in `studio/config.json` or environment variables — both **git‑ignored**.
- The only network calls are to **fal.ai** (image generation) and **Anthropic** (writing
  concepts), using **your** keys.

## License
MIT — do what you like, no warranty. Make great thumbnails. 🧡
