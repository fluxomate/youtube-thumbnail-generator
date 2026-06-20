# fal.ai API reference (for this skill)

The key is read from the `FAL_KEY` environment variable. `fal_client` picks it
up automatically — never hardcode it. All scripts use `fal_client.subscribe()`
so long jobs stream progress instead of timing out.

## Models used

`generate.py` selects the model with `--model` (default **`nano-banana-2`**):
- `nano-banana-2` — newest (Google Gemini 3 image). DEFAULT. Best quality/legibility,
  supports `resolution` up to 4K and up to 14 refs.
- `nano-banana-pro` — Google flagship Pro tier. Highest quality, highest cost.
- `nano-banana` — v1 (Gemini Flash Image). Cheapest, no `resolution` param.

With `--refs`, the `/edit` endpoint is used (reference-driven, keeps identity); without
refs, the base endpoint is text-to-image.

### `fal-ai/nano-banana-2/edit` (and `/nano-banana-pro/edit`) — DEFAULT for faces
| input | type | default | notes |
|-------|------|---------|-------|
| `prompt` | string | — | required |
| `image_urls` | list[str] | — | your uploaded face/inspiration refs (up to 14) |
| `num_images` | int | 1 | variations per call (1–4) |
| `aspect_ratio` | enum | auto | use `16:9` for thumbnails. Options incl: 21:9,16:9,3:2,4:3,5:4,1:1,9:16 |
| `resolution` | enum | 1K | `0.5K`/`1K`/`2K`/`4K`. Skill defaults to **2K** for crisp thumbnails. |
| `output_format` | enum | png | `jpeg`/`png`/`webp` |
| `seed` | int | — | reuse to reproduce a result |

Output: `{ "images": [ {url, width, height, content_type, file_name, file_size} ], "description": str }`

Text-to-image (no refs): same params minus `image_urls`, endpoint `fal-ai/nano-banana-2`.

### `fal-ai/nano-banana/edit` + `fal-ai/nano-banana` — v1 (legacy)
Older/cheaper. No `resolution` param. Use via `--model nano-banana`.

### `fal-ai/clarity-upscaler` — upscaling
Used by `upscale.py`.

| input | type | default | notes |
|-------|------|---------|-------|
| `image_url` | string | — | required |
| `upscale_factor` | float | 2 | |
| `prompt` | string | masterpiece... | guidance |
| `creativity` | float | 0.35 | denoise; keep **low (~0.2)** so face/text don't drift |
| `resemblance` | float | 0.6 | fidelity; keep **high (~0.8)** for thumbnails |

Output: `{ "image": {url, width, height, ...}, "seed": int }`

## Cost awareness
Each `generate.py` call bills per image (`num_images`). Default is 3 variations
per concept. Confirm with the user before large batches (e.g. 5 concepts x 3 = 15).

## Adding more models later
To swap/add a model (e.g. a different upscaler or a FLUX fallback), add an
endpoint string + argument dict and call `lib.run_model(endpoint, arguments)`.
The result-parsing assumes an `images` array (generation) or `image` object
(upscale) — match whichever the new endpoint returns.
