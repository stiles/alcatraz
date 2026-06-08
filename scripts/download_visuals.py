"""
Download curated Street View images from visuals/manifest.json.

Uses streetview-dl to fetch high-resolution panoramas. Requires a Google Maps
API key with Map Tiles API enabled — set GOOGLE_MAPS_API_KEY or run
`streetview-dl --configure`.

Output:
  visuals/<filename>           - downloaded image (skipped if already present)
  visuals/metadata/<id>.json   - panorama metadata from streetview-dl

Usage:
  uv run python scripts/download_visuals.py           # download all missing
  uv run python scripts/download_visuals.py --force   # re-download everything
  uv run python scripts/download_visuals.py --id b_block
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
VISUALS_DIR = ROOT / "visuals"
MANIFEST_PATH = VISUALS_DIR / "manifest.json"
METADATA_DIR = VISUALS_DIR / "metadata"


def load_manifest() -> list[dict]:
    with open(MANIFEST_PATH) as f:
        return json.load(f)["images"]


def download_image(entry: dict, force: bool = False) -> bool:
    """Download a single manifest entry. Returns True if downloaded or skipped cleanly."""
    output_path = VISUALS_DIR / entry["filename"]
    metadata_path = METADATA_DIR / f"{entry['id']}.json"

    if output_path.exists() and not force:
        print(f"  skip {entry['filename']} (exists)")
        return True

    cmd = [
        "streetview-dl",
        "--output", str(output_path),
        "--metadata",
        "--format", "png",
    ]

    if entry.get("crop_bottom") is not None:
        cmd.extend(["--crop-bottom", str(entry["crop_bottom"])])
    if entry.get("fov"):
        cmd.extend(["--fov", str(entry["fov"])])
    if entry.get("quality"):
        cmd.extend(["--quality", entry["quality"]])

    cmd.append(entry["url"])

    print(f"  download {entry['filename']} …")
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        print(f"  error: {e.stderr or e.stdout}", file=sys.stderr)
        return False

    # streetview-dl writes metadata next to the image; move it to metadata/
    sidecar = output_path.with_suffix(".json")
    if sidecar.exists():
        METADATA_DIR.mkdir(parents=True, exist_ok=True)
        sidecar.rename(metadata_path)

    print(f"  saved {output_path.name}")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Download Street View visuals from manifest")
    parser.add_argument("--force", action="store_true", help="Re-download even if file exists")
    parser.add_argument("--id", help="Download only this manifest entry id")
    args = parser.parse_args()

    if not MANIFEST_PATH.exists():
        print(f"Manifest not found: {MANIFEST_PATH}", file=sys.stderr)
        sys.exit(1)

    entries = load_manifest()
    if args.id:
        entries = [e for e in entries if e["id"] == args.id]
        if not entries:
            print(f"No manifest entry with id={args.id!r}", file=sys.stderr)
            sys.exit(1)

    VISUALS_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Downloading {len(entries)} image(s) from manifest …")
    failed = [e["id"] for e in entries if not download_image(e, force=args.force)]

    if failed:
        print(f"\nFailed: {', '.join(failed)}", file=sys.stderr)
        sys.exit(1)

    print("\nDone.")


if __name__ == "__main__":
    main()
