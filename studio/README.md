# Thumbnail Studio

A local web app for generating YouTube thumbnails — the UI on top of the
`youtube-thumbnail-generator` skill. Same memory, same fal models, now with a
point-and-click flow: **paste transcript → concepts → approve → thumbnails → upscale / download.**

## Run it

Double-click **`Start Thumbnail Studio.bat`** (Windows), or from a terminal:

```bash
python server.py
```

Then open <http://127.0.0.1:5005>. Everything runs on your machine; the only
outbound calls are to Anthropic (writing concepts) and fal.ai (images).

## First-time setup

Open **Settings** in the app and paste:

- **Anthropic API key** — writes the concepts ([console.anthropic.com](https://console.anthropic.com))
- **fal.ai key** — generates & upscales images ([fal.ai/dashboard/keys](https://fal.ai/dashboard/keys))

Keys are saved locally to `studio/config.json` (git-ignored). If `FAL_KEY` /
`ANTHROPIC_API_KEY` are already in your environment, it uses those automatically.

## The flow

1. **Studio → Intake.** Title (optional), paste the transcript, add context, and
   drop/paste **inspiration images** (screenshots, other creators' thumbnails) —
   Claude actually looks at them when writing concepts. Choose how many concepts.
2. **Concepts.** Claude writes distinct concepts using your saved taste. Approve
   (click to select), **Edit** any concept (including the raw image prompt),
   **Decline**, or **+ More concepts**.
3. **Thumbnails.** Selected concepts generate 3 variations each via fal. Per image:
   **View**, **Upscale 2×**, **More like this**, **Save**.

Every video becomes a project in the left rail — reopen any time.

## Memory

The **Memory** tab is a live view of the skill's `memory/` folder:

- **Style profile** — edit and save the text the concept-writer reads every time.
- **Face / Likes / Dislikes / Inspiration** — add images (with a note), delete,
  preview. New uploads land in the same files the skill uses.

## How it connects to the skill

The studio is a thin shell over the skill — it does **not** keep a private copy of the
generation logic or the style guidance, so it tracks the skill as the skill evolves:

- **Generation** shells out to the skill's own `scripts/generate.py` (currently
  `nano-banana-2 @ 2K` + the **style-ref "copy this thumbnail"** technique). Whatever the
  skill script does, the app does.
- **Concept brain** feeds Claude the skill's live guidance every time: `winning-style.md`
  (cinematic-default + style menu), `references/thumbnail-principles.md`,
  `references/reverse-engineered-examples.md`, the style profile, likes/dislikes, and the
  list of reference thumbnails it can copy.
- **Styles** = the validated menu: cinematic-dark (default), income-proof, storyboard,
  shocked-laptop, plus secondary graphic-dark/-light. Each concept can name a reference
  thumbnail from `memory/inspiration/reference-thumbnails/` to copy; the app passes it as
  `--style-ref`. Pasted inspiration (or "more like this") overrides it.
- Memory: `../.claude/skills/youtube-thumbnail-generator/memory/`; upscaling reuses
  `scripts/lib.py`. Projects/concepts/images write into `memory/projects/<slug>/` so the
  skill and UI stay in sync.

## Files

- `server.py` — Flask backend (config, memory, concepts via Claude, fal jobs)
- `static/` — the single-page UI (`index.html`, `styles.css`, `app.js`)
- `config.json` — your local keys (created on save; git-ignored)
