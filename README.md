# Alcatraz research

Replicable data collection for the 1962 Alcatraz escape and related history.

## Setup

```bash
uv sync
```

## Scripts

| Script | Source | Output |
|--------|--------|--------|
| `scripts/scrape_inmates.py` | [National Archives – Former Alcatraz Inmates](https://www.archives.gov/san-francisco/finding-aids/alcatraz-alpha) | `data/inmates.json`, `data/inmates.csv` |
| `scripts/scrape_notable.py` | [Wikipedia – List of inmates](https://en.wikipedia.org/wiki/List_of_inmates_of_Alcatraz_Federal_Penitentiary) | `data/notable_inmates.json`, `data/inmates_enriched.json`, `data/inmates_enriched.csv` |
| `scripts/scrape_escapes.py` | [BOP – Alcatraz History](https://www.bop.gov/about/history/alcatraz.jsp) | `data/escape_attempts.json`, `data/escape_attempts.csv` |
| `scripts/scrape_places.py` | [NPS Developer API – Places](https://developer.nps.gov/api/v1/places?parkCode=alca) | `data/places.json`, `data/places.csv`, `data/places.geojson` |
| `scripts/scrape_boundary.py` | [OpenStreetMap – relation 20197830](https://www.openstreetmap.org/relation/20197830) | `data/boundary.geojson` |
| `scripts/fetch_fbi_docs.py` | [FBI Vault – Alcatraz Escape](https://vault.fbi.gov/Alcatraz%20Escape/) | `data/fbi_docs.json`, `documents/*.pdf` |
| `scripts/discover_streetview.py` | Google Street View (via [streetview-dl](https://github.com/mstiles/streetview-dl)) | `data/streetview_coverage.json`, `data/streetview_urls.txt` |
| `scripts/download_visuals.py` | `visuals/manifest.json` | `visuals/*.png`, `visuals/metadata/*.json` |

Run scripts in order — `scrape_notable.py` and `scrape_escapes.py` both read from `data/inmates.csv`:

```bash
uv run python scripts/scrape_inmates.py
uv run python scripts/scrape_notable.py
uv run python scripts/scrape_escapes.py
uv run python scripts/scrape_places.py
uv run python scripts/scrape_boundary.py
uv run python scripts/fetch_fbi_docs.py   # large download, ~600 MB
uv run python scripts/discover_streetview.py   # requires GOOGLE_MAPS_API_KEY
uv run python scripts/download_visuals.py
```

## Visuals

Street View panoramas from inside and around Alcatraz, downloaded with [streetview-dl](https://github.com/mstiles/streetview-dl). Requires a Google Maps API key with Map Tiles API enabled:

```bash
export GOOGLE_MAPS_API_KEY="your_key"
uv run python scripts/discover_streetview.py   # find all panos on the island
uv run python scripts/download_visuals.py      # download curated views from manifest
```

Curated images are listed in `visuals/manifest.json`. To add a new view:

1. Open a URL from `data/streetview_urls.txt` in Google Maps (or browse inside the cellhouse)
2. Adjust heading and pitch, then copy the share URL
3. Add an entry to `visuals/manifest.json` with `id`, `title`, `url`, `filename`, and optional `crop_bottom`
4. Run `uv run python scripts/download_visuals.py`

| File | Description |
|------|-------------|
| `visuals/b_block_alcatraz.png` | B Block cell block interior — Morris and the Anglin brothers' housing block |
| `visuals/manifest.json` | Curated image catalog with URLs and download settings |
| `visuals/metadata/*.json` | Panorama metadata (capture date, coordinates, pano ID) |

## Data

### `data/inmates.json` / `data/inmates.csv`

1,576 prisoner records from the National Archives alphabetical index.

| Column | Description |
|--------|-------------|
| `register_number` | Bureau of Prisons register number |
| `name_raw` | Original all-caps string from source (`LAST, FIRST MIDDLE`) |
| `name_last` | Last name in title case |
| `name_given` | Given name(s) in title case |
| `name_suffix` | Generational suffix (Jr., Sr., II, III, IV) if present |
| `name_full` | Reconstructed full name: `First Middle Last [Suffix]` |

Some names include alternate surnames in brackets (e.g. `Best [Besmanoff]`) or nicknames in quotes — these are preserved from the source.

### `data/inmates_enriched.json` / `data/inmates_enriched.csv`

All 1,576 records with three columns added by `scrape_notable.py`:

| Column | Description |
|--------|-------------|
| `notable` | `true` if the prisoner appears on Wikipedia's notable inmates list |
| `wikipedia_name` | Display name as it appears on Wikipedia |
| `wikipedia_url` | Link to Wikipedia article, if one exists |

Three Wikipedia entries are unmatched in the Archives list: Wilhelm von Brincken (pre-1934 military era), Robert Simmons, and Irving "Waxey Gordon" Wexler.

### `data/escape_attempts.json` / `data/escape_attempts.csv`

14 escape attempts from the BOP history page. The JSON version includes a full `participants` array with register numbers, matched names, and how each name appears in the BOP narrative. The CSV flattens participants to a pipe-delimited `participant_registers` column.

| Column | Description |
|--------|-------------|
| `attempt_number` | 1–14 in chronological order |
| `year` | Year of the attempt |
| `nickname` | BOP's informal label (e.g. "Hollywood", "Battle of Alcatraz") |
| `date_start` / `date_end` | ISO dates (equal for single-day events) |
| `description` | Narrative text from BOP |
| `participant_registers` | Pipe-delimited register numbers of matched prisoners (CSV only) |

Known matching gaps: Thomas Limerick (#3, 1938) is called "James Limerick" in the BOP text but "Thomas Robert" in the Archives; two William Martins (registers 370 and 1308) can't be disambiguated from text alone.

### `data/places.json` / `data/places.csv` / `data/places.geojson`

65 named locations on Alcatraz Island from the NPS Developer API, including coordinates, descriptions, tags, and amenities. The GeoJSON file is ready to drop into any mapping tool.

`scrape_places.py` uses `DEMO_KEY` by default. For higher rate limits, set `NPS_API_KEY` to a [free key from the NPS developer portal](https://www.nps.gov/subjects/developer/get-started.htm).

| Column | Description |
|--------|-------------|
| `id` | NPS UUID for the place |
| `title` | Location name |
| `latitude` / `longitude` | WGS84 coordinates |
| `listing_description` | Short description |
| `tags` | Pipe-delimited tags (e.g. tour stops, wayside exhibits) |
| `url` | NPS.gov page for the location |
| `is_open_to_public` | Whether publicly accessible |
| `is_passport_stamp` | Whether a National Parks Passport stamp location |
| `nps_map_id` | Internal NPS map pin ID |

### `data/boundary.geojson`

Island boundary polygon from the OpenStreetMap `natural=coastline` way ([relation 20197830](https://www.openstreetmap.org/relation/20197830)) — 135 coordinate points, roughly one vertex every 4 metres around the ~500 m perimeter. This is the highest-resolution island outline available from a free public API. Properties include `wikidata`, `wikipedia`, `gnis_feature_id`, and the OSM way id. Drop it alongside `places.geojson` for a complete map layer stack.

### `data/fbi_docs.json`

Index of the 17 FBI vault PDFs with `title`, `view_url`, and `download_url`.

## Notes

- All scripts can be re-run safely; `fetch_fbi_docs.py` skips PDFs that already exist in `documents/`.
- The FBI vault requires a browser-like User-Agent header; the script sets one automatically.
- The Archives prisoner list has no real pagination — all five alphabetical sections are on a single page.
