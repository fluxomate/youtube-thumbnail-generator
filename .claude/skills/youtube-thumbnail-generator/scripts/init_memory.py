"""Create the local memory tree for the thumbnail generator (idempotent).

Run once on first use, or any time to repair missing folders. It never
overwrites existing files, so your saved photos, likes, and notes are safe.
"""

import pathlib
import sys

# memory/ lives next to the skill root (one level up from scripts/)
SKILL_ROOT = pathlib.Path(__file__).resolve().parents[1]
MEM = SKILL_ROOT / "memory"

TEMPLATES = {
    "README.md": """# Thumbnail generator memory

Everything the skill knows about you and your taste lives here. It is all local.

- `profile/face/`  — reference photos of you (the more angles/lighting, the better)
- `profile/style-profile.md` — your channel, niche, recurring style, do's & don'ts
- `preferences/likes/`    — thumbnails you liked (+ INDEX.md saying *why*)
- `preferences/dislikes/` — thumbnails you disliked (+ INDEX.md saying *why*)
- `inspiration/`   — other creators' thumbnails worth borrowing techniques from
- `projects/`      — one folder per video: brief, concepts, generated images
""",
    "profile/style-profile.md": """# Style profile

_The skill reads this before generating every concept and image. Keep it current._

## Channel / niche
(What is the channel about? Who is the audience?)

## Persona on camera
(How do you usually appear? Expressions, energy, wardrobe, glasses/beard, etc.)

## Visual signature
- Colors:
- Fonts / text style:
- Composition habits (face left/right, where text sits):
- Background style:

## Do's
-

## Don'ts
-
""",
    "profile/face/INDEX.md": """# Face reference photos

Drop clear photos of yourself in this folder, then note each below.
Good refs: front-on + 3/4 angle, neutral + expressive, even lighting, high res.

| file | angle | expression | notes |
|------|-------|------------|-------|
| example.jpg | front | neutral | (delete this row) |
""",
    "preferences/likes/INDEX.md": """# Liked thumbnails

Save images you like here and log *why* — the reason matters more than the image.

| file | source/creator | why it works |
|------|----------------|--------------|
""",
    "preferences/dislikes/INDEX.md": """# Disliked thumbnails

Save misses here and log *why* you'd avoid them.

| file | source | why to avoid |
|------|--------|--------------|
""",
    "inspiration/INDEX.md": """# Inspiration library

Save thumbnails from other creators here. Capture the *technique* to reuse, not
just the picture. Group related images in subfolders by creator or theme.

| file | creator | technique to borrow |
|------|---------|---------------------|
""",
    "projects/README.md": """# Projects

One folder per video. The skill creates these for you. Layout:

```
<video-slug>/
  brief.md            transcript + context + audience + angle
  concepts.md         generated concepts, each with an ID + approval status
  generated/<id>/     image variations (v1, v2, v3) + .json sidecars
  final/              chosen + upscaled thumbnail(s)
```
""",
}

FOLDERS = [
    "profile/face",
    "preferences/likes",
    "preferences/dislikes",
    "inspiration",
    "projects",
]


def main():
    created = []
    for folder in FOLDERS:
        (MEM / folder).mkdir(parents=True, exist_ok=True)
    for rel, body in TEMPLATES.items():
        path = MEM / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text(body, encoding="utf-8")
            created.append(rel)

    print(f"Memory tree ready at: {MEM}")
    if created:
        print("Created:")
        for c in created:
            print(f"  + {c}")
    else:
        print("Nothing new — everything already in place.")


if __name__ == "__main__":
    main()
