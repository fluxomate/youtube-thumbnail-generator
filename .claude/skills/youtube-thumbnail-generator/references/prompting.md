# Thumbnail concept + prompt craft

This is the creative core. Two different jobs: (1) writing **concepts** the user
approves, and (2) turning an approved concept into an **image prompt** for fal.

## What makes a YouTube thumbnail work
- **One idea, readable in 0.5s** at phone size. If it needs a second look, it's too busy.
- **A face with a clear emotion** is the strongest hook (shock, joy, curiosity, tension).
  This is why we keep face refs — the subject should look like *you*.
- **Big bold text, 3–5 words max.** It should add information the title doesn't.
- **High contrast + focal point.** Eyes go to the brightest/most saturated region.
- **Curiosity gap or stakes.** Show the result, the conflict, or the surprising thing.

## Concept format (present these to the user for approval)
Generate ~5 distinct concepts. Make them genuinely different angles, not variations
of one idea. For each:

```
### Concept 01 — <short hook name>
- **Big text:** "I LOST $40K" (3–5 words)
- **Emotion/expression:** wide-eyed shock, hand on head
- **Scene:** dark studio, glowing red downward stock chart behind
- **Composition:** face right third, text left, chart filling background
- **Why it works:** stakes + curiosity gap, raw emotion reads instantly
- **Pulls from memory:** likes/red-arrow-tension.jpg technique; your usual yellow text
```

Mark each as `[ ]` pending until the user approves. Track approval in `concepts.md`.

## Turning a concept into an image prompt
nano-banana follows natural-language descriptions well. Build the prompt in this order:

1. **Subject + expression** (this is you — refs handle likeness): "a man with [your
   features] looking shocked, eyes wide, mouth open, hand on forehead"
2. **Wardrobe/persona** from style-profile if relevant.
3. **Scene + background**, with lighting and mood.
4. **The text**, quoted and styled: `bold 3D yellow text reading "I LOST $40K", heavy
   outline, top-left`. Keep it short — image models garble long text.
5. **Composition + format**: "YouTube thumbnail composition, 16:9, subject on the
   right third, strong rim lighting, high contrast, vibrant, sharp focus".
6. **Borrowed technique** from a like/inspiration, described in words (not "copy X").

### Text rendering tips
- Fewer words render cleaner. If text garbles, reduce to 2–3 words or generate the
  scene without text and note that text can be added in an editor.
- Always quote the exact words you want.

### Keeping it *you*
- Always pass face refs via `--refs` for face-driven concepts.
- If a generation drifts from your likeness, add more/better face refs, or feed a
  previously-good thumbnail of you as an extra ref.

## Example: concept -> prompt
Concept: shocked founder + bankrupt chart, text "I LOST $40K".

Prompt:
> A man (see reference) with a shocked expression, eyes wide and mouth open, one hand
> on his forehead, wearing a dark hoodie. Behind him a large glowing red stock chart
> crashing downward, dark moody studio lighting with red rim light. Bold 3D yellow
> text with a thick black outline reading "I LOST $40K" in the upper-left. YouTube
> thumbnail composition, 16:9, subject on the right third, extreme high contrast,
> vibrant, ultra sharp, dramatic.

## Iteration vocabulary (when the user asks for "more like that")
- Reuse the winning image as an extra ref to lock the look, then vary one axis
  (expression, background, text, color) per batch so variations stay distinct.
- "Generate more like v2" → feed v2 as a ref + keep prompt, bump `--seed` off.
- "Punchier" → increase contrast/saturation words, simplify the scene, enlarge text.
