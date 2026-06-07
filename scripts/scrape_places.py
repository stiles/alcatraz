"""
Fetch Alcatraz place data from the NPS Developer API.

Source: https://developer.nps.gov/api/v1/places?parkCode=alca
Output:
  data/places.json    - full API records
  data/places.csv     - flat version (coordinates, title, description, tags)
  data/places.geojson - GeoJSON FeatureCollection for mapping

A free API key from https://www.nps.gov/subjects/developer/get-started.htm
unlocks higher rate limits. Falls back to DEMO_KEY if NPS_API_KEY is not set.
"""

import csv
import json
import os
from pathlib import Path

import requests

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"

NPS_API_BASE = "https://developer.nps.gov/api/v1"
PARK_CODE = "alca"
API_KEY = os.environ.get("NPS_API_KEY", "DEMO_KEY")
HEADERS = {"User-Agent": "AlcatrazResearch/1.0 (educational)"}


def fetch_places() -> list[dict]:
    """Paginate through all Alcatraz places from the NPS API."""
    all_places = []
    start = 0
    limit = 50

    while True:
        resp = requests.get(
            f"{NPS_API_BASE}/places",
            params={"parkCode": PARK_CODE, "api_key": API_KEY, "limit": limit, "start": start},
            headers=HEADERS,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        total = int(data["total"])
        all_places.extend(data["data"])
        print(f"  fetched {len(all_places)}/{total}")
        if len(all_places) >= total:
            break
        start += limit

    return all_places


def to_geojson(places: list[dict]) -> dict:
    """Convert place records to a GeoJSON FeatureCollection."""
    features = []
    for p in places:
        try:
            lon = float(p["longitude"])
            lat = float(p["latitude"])
        except (ValueError, KeyError):
            continue

        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {
                    "id": p.get("id"),
                    "title": p.get("title"),
                    "description": p.get("listingDescription"),
                    "tags": p.get("tags", []),
                    "url": p.get("url"),
                    "is_open_to_public": p.get("isOpenToPublic"),
                    "is_passport_stamp": p.get("isPassportStampLocation"),
                    "nps_map_id": p.get("npmapId"),
                },
            }
        )

    return {"type": "FeatureCollection", "features": features}


def main() -> None:
    print("Fetching Alcatraz places from NPS Developer API...")
    if API_KEY == "DEMO_KEY":
        print("  (using DEMO_KEY — set NPS_API_KEY env var for higher rate limits)")

    places = fetch_places()
    print(f"Total: {len(places)} places")

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Full JSON
    json_file = DATA_DIR / "places.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(places, f, indent=2, ensure_ascii=False)
    print(f"Saved to {json_file.relative_to(ROOT)}")

    # GeoJSON
    geojson_file = DATA_DIR / "places.geojson"
    with open(geojson_file, "w", encoding="utf-8") as f:
        json.dump(to_geojson(places), f, indent=2, ensure_ascii=False)
    print(f"Saved to {geojson_file.relative_to(ROOT)}")

    # Flat CSV
    csv_file = DATA_DIR / "places.csv"
    flat_fields = ["id", "title", "latitude", "longitude", "listing_description",
                   "tags", "url", "is_open_to_public", "is_passport_stamp", "nps_map_id"]
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=flat_fields)
        writer.writeheader()
        for p in places:
            writer.writerow({
                "id": p.get("id"),
                "title": p.get("title"),
                "latitude": p.get("latitude"),
                "longitude": p.get("longitude"),
                "listing_description": p.get("listingDescription"),
                "tags": "|".join(p.get("tags", [])),
                "url": p.get("url"),
                "is_open_to_public": p.get("isOpenToPublic"),
                "is_passport_stamp": p.get("isPassportStampLocation"),
                "nps_map_id": p.get("npmapId"),
            })
    print(f"Saved to {csv_file.relative_to(ROOT)}")

    # Preview
    print()
    for p in sorted(places, key=lambda x: x.get("title", "")):
        lat = p.get("latitude", "")
        lon = p.get("longitude", "")
        print(f"  {p.get('title', '?'):45}  {lat}, {lon}")


if __name__ == "__main__":
    main()
