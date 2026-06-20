# Winning style — CINEMATIC FILM-STILL (the PREFERRED default)

These prompts produced thumbnails Leo **actually used on the channel**. This cinematic,
editorial-photography style is now the **preferred default** — it beats the earlier graphic /
icon / chart / dashboard look. Lead here unless a specific video clearly calls for the graphic
style. Read this before drafting concepts.

## ⚠️ CALIBRATION (most important) — cinematic SUBJECT, designed THUMBNAIL
The win is **cinematic-quality subject + a designed thumbnail**, NOT a full cinematic scene.
- **Keep:** the crisp, dramatically-lit, high-quality look of the *person* (strong rim/side
  light, premium skin/detail, 4K, slight vignette, punchy highlights).
- **Drop:** full photographic *environments/scenes* (empty boardroom, night street, window) —
  those lean too "movie still," not "thumbnail."
- **Instead:** studio-light the subject and composite them onto a **clean DESIGNED background**
  (solid dark charcoal/black, or a bold brand-orange gradient/radial glow — pick per scene),
  with **bold graphic text** and **one simple clean graphic element** (a traffic-light icon, a
  green/red arrow, a clean client card, a big number). Reference the agency thumbnails Leo
  gave: **Alex Hormozi, Jeremy Haines, Bing** — person + bold text + one clean graphic on a
  designed background. Crisp, premium, uncluttered.
- **Resolution:** generate finals at **4K** (`--resolution 4K`) for crisp highlights/detail.

## ✅ Refined rules from the Round-5 review (benchmark = concept 23 v1)
Build on **23 v1** (saved in likes). Apply ALL of these:
- **Background = solid deep BLACK / charcoal-black.** NOT dark blue, NOT a weak orange blur.
- **Glow behind the subject = warm ORANGE→RED radial glow** (brand). **Never a white glow.**
- **No white cut-out / sticker outline around the subject.** Blend them into the dark with the
  orange/red glow + rim light. White sticker edges look cheap.
- **Any people in graphic elements (client cards) = REAL photographic headshots**, never cartoon/
  illustrated avatars (those look trash).
- **No coloured light on the face without a visible in-scene source** (the red/green-on-face with
  no source looked weird in 22).
- **Don't over-focus on the face** when there's a graphic — balance subject vs graphic element.
- **Premium typography** — clean bold condensed sans, not a generic/wrong font.
- **$10k-designer quality bar:** rich, polished, depth and gloss on graphic elements. If it looks
  like something makeable on camera in 5 minutes, it's not good enough. Ultra high quality only.

## 🎯 Style-matching a specific reference thumbnail (powerful technique)
To closely mimic a specific reference thumbnail's look, **pass that thumbnail as an extra `--refs`
image (last in the list), alongside Leo's face refs**, and in the prompt assign roles explicitly:
"the person is the man from the face reference photos (use his exact face); use the LAST reference
image ONLY as a style/layout guide — do not copy its person or its text." This made nano-banana-2
reproduce a target style almost exactly (bright bg, floating glossy app icons, income chart +
callout) while keeping Leo's identity. Use it whenever Leo says "make it like THIS thumbnail."

## Validated alt style — "income-proof / faceless" (bright)
A proven clean BRIGHT variant (vs the dark default): off-white background, Leo on the left with a big
genuine smile, **bold black extra-condensed headline + a red YouTube play logo**, **two floating
glossy 3D app icons** (orange starburst + green/yellow squiggle = the tool stack), and a **rising
income line chart with a white callout card** showing a date + exact $ (e.g. "+$18,000/MO"). Great for
result/proof/"how I…" videos. Pair with the style-ref technique above using
`inspiration/reference-thumbnails/A5-faceless-channel-income-chart.png`.

## Validated alt style — "hand-drawn storyboard / whiteboard" (warm editorial)
A proven, premium "explainer" look Leo loves: the topic drawn out as **pencil/marker sketches on a
warm whiteboard** behind Leo (orange hoodie) who points at them; a **handwritten red marker title +
red underline + red curved arrow**; often a **caricature of Leo** on the board. Great for system /
breakdown / "how it works" videos. The big title + key numbers render clean; small background notes
may garble (fine — reads as handwriting, or tidy in Canva). Use the style-ref technique with
`inspiration/reference-thumbnails/A1-ai-animation-storyboard.png`.

## Style menu (pick per video; all use the style-ref technique)
1. **Dark premium** (default) — black/charcoal, orange/red glow, bold headline, one clean graphic.
2. **Bright income-proof** (A5) — off-white, smile, app icons, income chart + $ callout, YT logo.
3. **Hand-drawn storyboard** (A1) — whiteboard sketches, red marker title + arrow, pointing.
4. **Shocked-over-laptop** (A2) — dark studio, extreme shock leaning over a glowing laptop, floating
   client/result cards + glossy app icons, big bold white bottom text with thick dark outline. High
   energy; great for "how much X / I did Y" hooks. Ref: `reference-thumbnails/A2-100-ads-in-5-min-shocked-laptop.png`.
Always pass Leo's face refs + the chosen reference thumbnail as the LAST ref.

## The recipe
Open every prompt with: **"Cinematic landscape YouTube thumbnail, film-still quality."**
- **Subject:** Leo BIG — a close-up portrait, OR a cinematic scene built around a **visual
  metaphor**. Always a strong, genuine emotion: shocked disbelief (mouth slightly open, eyebrows
  raised), concern, contemplation. Real, not posed-stock.
- **Lighting:** strong cinematic **side-lighting**, deep shadows on one side of the face,
  **rim/back light**. Warm–cool colour contrast. Moody.
- **Camera:** **shallow depth of field**, dark out-of-focus background; sometimes a low angle.
- **Text:** bold **extra-condensed** sans-serif, integrated **"like a film title,"** top-left,
  subtle shadow. One key word tinted bright orange (`#FF7300`) or red; the rest white.
- **Grade:** premium editorial photography, **cinematic colour grade**, slight vignette, high contrast.
- **Concept:** prefer a **VISUAL METAPHOR that tells the story** over literal charts/icons/
  dashboards (empty chair = client left; standing alone at a night window = lost client). "Way
  more cinematic than charts or icons."

## Why it wins
Feels like a still from a film / corporate drama, not a designed YouTube graphic. Emotion +
metaphor + film-title text create intrigue and a premium feel. This is the look that performed.

## Relationship to the older "graphic" style
The icon-grid / dashboard / chart-heavy / big-text-block style (earlier Modes A/B) is now
**secondary** — keep it only for the occasional pure data/announcement video. **Avoid icon
grids, dashboard mockups, and chart-heavy layouts by default.** Default to cinematic.

## Proven prompts (match this phrasing)

**Portrait — shocked close-up:**
> Cinematic landscape YouTube thumbnail, film-still quality. A young man with short dark hair and
> short beard wearing a bright orange hoodie, shot in close-up portrait style, mouth slightly open,
> eyebrows raised in genuine shocked disbelief like he just read something unbelievable. Strong
> cinematic side-lighting with deep shadows on one side of his face, rim light from behind. Shallow
> depth of field, dark moody out-of-focus background. Top-left, bold extra-condensed sans-serif
> "WORST AGENCY EVER" in white, "WORST" in bright orange (#FF7300), integrated like a film title.
> Premium editorial photography. High contrast, premium feel, slight cinematic vignette.

**Scene + metaphor — empty chair:**
> Cinematic landscape YouTube thumbnail, film-still quality. A dimly lit modern office boardroom,
> shot from a low angle. Centre frame: an empty office chair pulled out from a dark wooden
> conference table, slightly turned as if someone just stood and walked away, lit by a warm
> overhead spotlight. To the right, partially in shadow, a young man with short dark hair and short
> beard in a bright orange hoodie looks down at the empty chair with a concerned, contemplative
> expression. Strong cinematic lighting, deep shadows, warm-cool colour contrast, shallow depth of
> field. Top-left, bold extra-condensed sans-serif "THIS IS WHY THEY LEAVE" in white, "LEAVE"
> tinted bright red, integrated like a film title with subtle shadow. Premium editorial photography,
> moody atmosphere, cinematic colour grade.

**Alternative metaphor — alone at the night window:**
> ...a young man (Leo) alone in a dark modern office at night, hands in hoodie pockets, looking out
> a floor-to-ceiling window at city lights, the city reflected on the glass, pensive expression like
> an agency owner who just lost a client. Same cinematic lighting / shallow DOF / film-title text.
