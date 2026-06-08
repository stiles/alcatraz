"""
Discover Street View panorama coverage on Alcatraz Island.

Adapted from streetview-dl/examples/alcatraz_example.py. Queries Google's
Street View API for all panoramas within a radius of the island center, then
saves results for browsing and adding to visuals/manifest.json.

Requires GOOGLE_MAPS_API_KEY (Map Tiles API enabled).

Output:
  data/streetview_coverage.json  - full query results
  data/streetview_urls.txt       - one Google Maps URL per panorama
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"

ALCATRAZ_LAT = 37.8267028
ALCATRAZ_LNG = -122.4242763
SEARCH_RADIUS = 100
MAX_RESULTS = 150
SEARCH_DEPTH = 5
MAX_PANOS = 1000


def query_panoramas() -> dict:
    result = subprocess.run(
        [
            "streetview-dl", "query",
            "--lat", str(ALCATRAZ_LAT),
            "--lng", str(ALCATRAZ_LNG),
            "--radius", str(SEARCH_RADIUS),
            "--max-results", str(MAX_RESULTS),
            "--depth", str(SEARCH_DEPTH),
            "--max-panos", str(MAX_PANOS),
            "--json",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def build_maps_url(pano: dict) -> str:
    lat, lng = pano["lat"], pano["lng"]
    pano_id = pano["pano_id"]
    heading = pano.get("heading", 0)
    return (
        f"https://www.google.com/maps/@{lat},{lng},"
        f"3a,75y,{heading:.0f}h,90t/data=!3m7!1e1!3m5!1s{pano_id}!"
    )


def main() -> None:
    print("Querying Street View coverage on Alcatraz Island …")
    try:
        data = query_panoramas()
    except subprocess.CalledProcessError as e:
        print(f"Query failed: {e.stderr}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Invalid JSON from query: {e}", file=sys.stderr)
        sys.exit(1)

    panoramas = data["panoramas"]
    print(f"Found {len(panoramas)} panorama(s)\n")

    by_date: dict[str, list] = {}
    for pano in panoramas:
        by_date.setdefault(pano.get("date", "unknown"), []).append(pano)

    for date in sorted(by_date, reverse=True):
        panos = by_date[date]
        print(f"  {date}: {len(panos)} panorama(s)")

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    coverage_path = DATA_DIR / "streetview_coverage.json"
    with open(coverage_path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"\nSaved {coverage_path}")

    urls_path = DATA_DIR / "streetview_urls.txt"
    with open(urls_path, "w") as f:
        for pano in panoramas:
            f.write(build_maps_url(pano) + "\n")
    print(f"Saved {urls_path} ({len(panoramas)} URLs)")

    print("\nTo add a view to the image library:")
    print("  1. Open a URL from streetview_urls.txt in Google Maps")
    print("  2. Adjust heading/pitch, copy the share URL")
    print("  3. Add an entry to visuals/manifest.json")
    print("  4. Run: uv run python scripts/download_visuals.py")


if __name__ == "__main__":
    main()
