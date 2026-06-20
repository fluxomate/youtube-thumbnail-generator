"""Upscale a chosen thumbnail with fal.ai clarity-upscaler.

YouTube thumbnails display at 1280x720. nano-banana output is already usable,
but upscaling sharpens detail and is handy before final export or for reuse as
a high-res asset.

Usage
-----
python upscale.py --image "memory/projects/lost-40k/generated/concept-01/v2.jpg" \
    --factor 2 \
    --out "memory/projects/lost-40k/final"
"""

import argparse
import pathlib
import sys

import lib


def main():
    ap = argparse.ArgumentParser(description="Upscale a thumbnail via fal clarity-upscaler")
    ap.add_argument("--image", required=True, help="Local image to upscale")
    ap.add_argument("--factor", type=float, default=2.0, help="Upscale factor (default 2)")
    ap.add_argument("--prompt", default="masterpiece, best quality, highres, sharp, vibrant",
                    help="Guidance prompt for the upscaler")
    ap.add_argument("--creativity", type=float, default=0.2,
                    help="Denoise strength 0-1; keep low (0.2) so the face/text don't drift")
    ap.add_argument("--resemblance", type=float, default=0.8,
                    help="Fidelity to the original 0-1; high keeps it faithful")
    ap.add_argument("--out", required=True, help="Output directory")
    args = ap.parse_args()

    src = pathlib.Path(args.image)
    if not src.exists():
        sys.exit(f"Image not found: {src}")

    out_dir = pathlib.Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    image_url = lib.upload_refs([str(src)])[0]
    result = lib.run_model("fal-ai/clarity-upscaler", {
        "image_url": image_url,
        "upscale_factor": args.factor,
        "prompt": args.prompt,
        "creativity": args.creativity,
        "resemblance": args.resemblance,
    })

    img = result.get("image")
    if not img or not img.get("url"):
        sys.exit(f"No upscaled image returned. Raw result: {result}")

    dest = out_dir / f"{src.stem}-upscaled-{int(args.factor)}x.png"
    lib.download(img["url"], dest)
    lib.write_sidecar(dest, {
        "endpoint": "fal-ai/clarity-upscaler",
        "source_image": str(src),
        "upscale_factor": args.factor,
        "source_url": img["url"],
        "width": img.get("width"),
        "height": img.get("height"),
    })
    print(f"saved: {dest}")
    if img.get("width"):
        print(f"dimensions: {img.get('width')}x{img.get('height')}")


if __name__ == "__main__":
    main()
