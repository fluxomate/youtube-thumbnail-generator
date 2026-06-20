"""Generate thumbnail image variations with fal.ai nano-banana.

If reference images are supplied (your face photos, inspiration, a previous
thumbnail) it uses `fal-ai/nano-banana/edit`, which keeps your identity and the
visual cues consistent. With no references it falls back to plain text-to-image
(`fal-ai/nano-banana`).

Usage examples
--------------
# 3 variations from a prompt, using your face refs, 16:9, saved to a concept dir
python generate.py \
    --prompt "Wide-eyed shocked founder pointing at a glowing red 'BANKRUPT' chart, dark studio bg, bold 3D yellow text 'I LOST $40K'" \
    --refs "memory/profile/face/face1.jpg,memory/profile/face/face2.jpg" \
    --num 3 \
    --out "memory/projects/lost-40k/generated/concept-01"

# Pure text-to-image, no refs
python generate.py --prompt "..." --num 2 --out ./out
"""

import argparse
import pathlib
import sys

import lib


def main():
    ap = argparse.ArgumentParser(description="Generate thumbnail variations via fal nano-banana")
    ap.add_argument("--prompt", help="Full image prompt (see references/prompting.md)")
    ap.add_argument("--prompt-file", dest="prompt_file",
                    help="Path to a UTF-8 text file containing the prompt (avoids shell-escaping "
                         "long prompts with quotes/# characters). Use this OR --prompt.")
    ap.add_argument("--refs", default="", help="Comma-separated local image paths (face refs)")
    ap.add_argument("--style-ref", dest="style_ref", default=None,
                    help="Path to a thumbnail to COPY the style of (the core method — see "
                         "memory/winning-style.md). Uploaded last and auto-flagged as style-only: "
                         "the model recreates its look while keeping the face from --refs.")
    ap.add_argument("--num", type=int, default=3, help="Number of variations (default 3)")
    ap.add_argument("--aspect", default="16:9", help="Aspect ratio (default 16:9 for YouTube)")
    ap.add_argument("--format", default="jpeg", choices=["jpeg", "png", "webp"], help="Output format")
    ap.add_argument("--model", default="nano-banana-2",
                    choices=["nano-banana-2", "nano-banana-pro", "nano-banana"],
                    help="fal model family. nano-banana-2 (default, newest), nano-banana-pro "
                         "(Google flagship, highest quality/cost), nano-banana (v1, cheapest).")
    ap.add_argument("--resolution", default="2K", choices=["0.5K", "1K", "2K", "4K"],
                    help="Output resolution for nano-banana-2/pro (default 2K for crisp "
                         "thumbnails). Ignored by v1 nano-banana.")
    ap.add_argument("--seed", type=int, default=None, help="Optional seed for reproducibility")
    ap.add_argument("--out", required=True, help="Output directory for the variations")
    ap.add_argument("--name", default="v", help="Filename prefix (default 'v')")
    args = ap.parse_args()

    if args.prompt_file:
        args.prompt = pathlib.Path(args.prompt_file).read_text(encoding="utf-8").strip()
    if not args.prompt:
        sys.exit("Provide a prompt via --prompt or --prompt-file.")

    ref_paths = [r.strip() for r in args.refs.split(",") if r.strip()]
    # A style reference — "copy this thumbnail" — is the heart of how this skill gets its best
    # results. It's uploaded LAST and auto-flagged as style-only so the model recreates the look
    # while keeping the creator's face from the earlier refs.
    if args.style_ref:
        ref_paths.append(args.style_ref.strip())
        args.prompt += (
            "\n\nIMPORTANT: The FINAL reference image is a STYLE / LAYOUT reference only. "
            "Recreate its visual style, composition, lighting, colour treatment, text styling and "
            "graphic-element treatment as closely as possible — but use the PERSON from the earlier "
            "face reference photos (keep his exact identity and the orange-hoodie brand) and follow "
            "the scene and text described above. Do NOT copy the style reference's person or its words."
        )
    out_dir = pathlib.Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    base = f"fal-ai/{args.model}"
    arguments = {
        "prompt": args.prompt,
        "num_images": args.num,
        "aspect_ratio": args.aspect,
        "output_format": args.format,
    }
    # nano-banana-2 / pro support a native resolution param; v1 does not.
    if args.model in ("nano-banana-2", "nano-banana-pro"):
        arguments["resolution"] = args.resolution

    if ref_paths:
        endpoint = f"{base}/edit"
        arguments["image_urls"] = lib.upload_refs(ref_paths)
    else:
        endpoint = base
    if args.seed is not None:
        arguments["seed"] = args.seed

    result = lib.run_model(endpoint, arguments)

    images = result.get("images") or []
    if not images:
        sys.exit(f"No images returned. Raw result: {result}")

    ext = "jpg" if args.format == "jpeg" else args.format
    saved = []
    for i, img in enumerate(images, start=1):
        url = img.get("url")
        if not url:
            continue
        dest = out_dir / f"{args.name}{i}.{ext}"
        lib.download(url, dest)
        lib.write_sidecar(dest, {
            "endpoint": endpoint,
            "prompt": args.prompt,
            "refs": ref_paths,
            "style_ref": args.style_ref,
            "aspect_ratio": args.aspect,
            "resolution": arguments.get("resolution"),
            "seed": arguments.get("seed"),
            "source_url": url,
            "model_description": result.get("description"),
        })
        saved.append(str(dest))
        print(f"saved: {dest}")

    print(f"\nDone. {len(saved)} image(s) in {out_dir}")
    if result.get("description"):
        print(f"Model note: {result['description']}")


if __name__ == "__main__":
    main()
