"""
Fetch the Alcatraz Island boundary polygon from OpenStreetMap via Overpass API.

Source: OSM relation 20197830 (NPS protected area, wikidata Q131354)
Output:
  data/boundary.geojson - GeoJSON Polygon of the island boundary
"""

import json
from pathlib import Path

import requests

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OSM_RELATION_ID = 20197830
HEADERS = {"User-Agent": "AlcatrazResearch/1.0 (educational)"}

QUERY = f"""
[out:json][timeout:25];
relation({OSM_RELATION_ID});
out geom;
"""


def fetch_boundary() -> dict:
    resp = requests.post(OVERPASS_URL, data={"data": QUERY}, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    rel = data["elements"][0]
    tags = rel["tags"]

    # Collect outer rings (skip node members like highest_point)
    rings = []
    for member in rel.get("members", []):
        if member["type"] != "way" or member["role"] != "outer":
            continue
        coords = [[pt["lon"], pt["lat"]] for pt in member["geometry"]]
        # Close the ring if not already closed
        if coords and coords[0] != coords[-1]:
            coords.append(coords[0])
        rings.append(coords)

    if len(rings) == 1:
        geometry = {"type": "Polygon", "coordinates": rings}
    else:
        geometry = {"type": "MultiPolygon", "coordinates": [[r] for r in rings]}

    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": geometry,
                "properties": {
                    "name": tags.get("name"),
                    "short_name": tags.get("short_name"),
                    "osm_relation_id": OSM_RELATION_ID,
                    "osm_type": tags.get("type"),
                    "wikidata": tags.get("wikidata"),
                    "wikipedia": tags.get("wikipedia"),
                    "website": tags.get("website"),
                    "gnis_feature_id": tags.get("gnis:feature_id"),
                    "ele_m": tags.get("ele"),
                    "boundary": tags.get("boundary"),
                    "protect_class": tags.get("protect_class"),
                },
            }
        ],
    }


def main() -> None:
    print(f"Fetching Alcatraz boundary from OSM (relation {OSM_RELATION_ID})...")
    geojson = fetch_boundary()

    feature = geojson["features"][0]
    geom = feature["geometry"]
    ring = geom["coordinates"][0] if geom["type"] == "Polygon" else geom["coordinates"][0][0]
    print(f"  geometry type: {geom['type']}")
    print(f"  coordinate count: {len(ring)}")
    print(f"  name: {feature['properties']['name']}")
    print(f"  wikidata: {feature['properties']['wikidata']}")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out = DATA_DIR / "boundary.geojson"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(geojson, f, indent=2)
    print(f"Saved to {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
