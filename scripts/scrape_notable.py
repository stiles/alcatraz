"""
Scrape Wikipedia's list of notable Alcatraz inmates and join with inmates.csv.

Source: https://en.wikipedia.org/wiki/List_of_inmates_of_Alcatraz_Federal_Penitentiary
Requires: data/inmates.csv (run scrape_inmates.py first)

Output:
  data/notable_inmates.json  - scraped list with register matches
  data/inmates_enriched.json - full inmate list enriched with notable/wikipedia_url
  data/inmates_enriched.csv  - same data as CSV
"""

import csv
import json
import re
from collections import defaultdict
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"

WIKI_ARTICLE_URL = "https://en.wikipedia.org/wiki/List_of_inmates_of_Alcatraz_Federal_Penitentiary"
WIKI_BASE = "https://en.wikipedia.org"

HEADERS = {"User-Agent": "AlcatrazResearch/1.0 (educational)"}

# One bullet covers multiple people; expand before matching.
MULTI_PERSON_EXPANSIONS = {
    "Anglin Brothers and Frank Morris": [
        {"name": "Clarence Anglin", "url": "/wiki/June_1962_Alcatraz_escape"},
        {"name": "John Anglin", "url": "/wiki/June_1962_Alcatraz_escape"},
        {"name": "Frank Morris", "url": "/wiki/June_1962_Alcatraz_escape"},
    ],
}

# Wikipedia last name → Archives last name (spelling discrepancies / aliases).
LAST_NAME_OVERRIDES = {
    "Barnes": "Kelly",  # George Kelly Barnes → KELLY, GEORGE R. "MACHINE GUN"
    "Rapp": "Raap",     # Verrill Rapp → RAAP, VERRILL HERSEY (Wikipedia typo)
}


def scrape_notable_list() -> list[dict]:
    """Return raw list of {name, url} dicts from the Wikipedia bullet list."""
    resp = requests.get(WIKI_ARTICLE_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    entries = []
    for h2 in soup.find_all("h2"):
        if "notable" in h2.get_text().lower():
            ul = h2.find_next("ul")
            for li in ul.find_all("li"):
                a = li.find("a")
                href = a["href"] if a else None
                wiki_href = href if (href and href.startswith("/wiki/")) else None
                entries.append({"name": li.get_text(strip=True), "raw_href": wiki_href})
            break

    expanded = []
    for entry in entries:
        if entry["name"] in MULTI_PERSON_EXPANSIONS:
            expanded.extend(MULTI_PERSON_EXPANSIONS[entry["name"]])
        else:
            expanded.append({"name": entry["name"], "url": entry["raw_href"]})

    return expanded


def clean_display_name(raw: str) -> str:
    return re.sub(r"\[\d+\]", "", raw).strip()


def extract_last_and_first(display_name: str) -> tuple[str, str]:
    """
    Pull the most likely last name and first name from a Wikipedia display name.

    Strips quoted nicknames so 'Waxey Gordon' etc. don't confuse the last-word heuristic.
    """
    name = re.sub(r'"[^"]*"', "", display_name)
    name = re.sub(r"\s+", " ", name).strip()
    words = name.split()
    return (words[-1] if words else ""), (words[0] if words else "")


def build_archive_index(rows: list[dict]) -> dict[str, list[dict]]:
    index = defaultdict(list)
    for row in rows:
        index[row["name_last"].upper()].append(row)
    return index


def find_matches(display_name: str, index: dict) -> list[dict]:
    display_name = clean_display_name(display_name)
    last, first = extract_last_and_first(display_name)

    lookup_last = LAST_NAME_OVERRIDES.get(last, last).upper()
    candidates = index.get(lookup_last, [])

    if not candidates:
        return []

    if first:
        first_letter = first[0].upper()
        by_letter = [c for c in candidates if c["name_given"].upper().startswith(first_letter)]
        if by_letter:
            candidates = by_letter
        elif len(candidates) == 1:
            # One candidate, first-letter mismatch — allow only if first name is a nickname.
            if first.upper() not in candidates[0]["name_raw"].upper():
                return []

    if len(candidates) <= 1:
        return candidates

    # Further narrow by 3-char prefix (Henri/Henry, Eddie/Edward, etc.).
    if first:
        narrowed = [c for c in candidates if c["name_given"].upper().startswith(first[:3].upper())]
        if narrowed:
            return narrowed

    return candidates


def main() -> None:
    inmates_csv = DATA_DIR / "inmates.csv"
    with open(inmates_csv, newline="", encoding="utf-8") as f:
        inmates = list(csv.DictReader(f))

    archive_index = build_archive_index(inmates)

    print("Scraping Wikipedia notable prisoner list...")
    raw_entries = scrape_notable_list()
    print(f"Found {len(raw_entries)} entries (after expanding multi-person bullets)")

    notable_records = []
    unmatched = []

    for entry in raw_entries:
        display = clean_display_name(entry["name"])
        wiki_url = (WIKI_BASE + entry["url"]) if entry.get("url") else None
        matches = find_matches(display, archive_index)
        register_numbers = [int(m["register_number"]) for m in matches]

        notable_records.append(
            {
                "wikipedia_name": display,
                "wikipedia_url": wiki_url,
                "matched_registers": register_numbers,
                "match_count": len(register_numbers),
            }
        )
        if not register_numbers:
            unmatched.append(display)

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    notable_json = DATA_DIR / "notable_inmates.json"
    with open(notable_json, "w", encoding="utf-8") as f:
        json.dump(notable_records, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(notable_records)} notable entries to {notable_json.relative_to(ROOT)}")

    if unmatched:
        print(f"\nUnmatched ({len(unmatched)}) — not found in Archives list:")
        for name in unmatched:
            print(f"  {name}")

    # Build register → notable info lookup.
    register_to_notable: dict[int, dict] = {}
    for record in notable_records:
        for reg in record["matched_registers"]:
            if reg not in register_to_notable or (
                record["wikipedia_url"] and not register_to_notable[reg]["wikipedia_url"]
            ):
                register_to_notable[reg] = record

    # Enrich the inmate list.
    enriched = []
    for row in inmates:
        reg = int(row["register_number"])
        info = register_to_notable.get(reg)
        enriched_row = dict(row)
        enriched_row["notable"] = info is not None
        enriched_row["wikipedia_name"] = info["wikipedia_name"] if info else ""
        enriched_row["wikipedia_url"] = (info["wikipedia_url"] or "") if info else ""
        enriched.append(enriched_row)

    enriched_json = DATA_DIR / "inmates_enriched.json"
    with open(enriched_json, "w", encoding="utf-8") as f:
        json.dump(enriched, f, indent=2, ensure_ascii=False)
    print(f"Enriched JSON saved to {enriched_json.relative_to(ROOT)}")

    enriched_csv = DATA_DIR / "inmates_enriched.csv"
    fieldnames = list(inmates[0].keys()) + ["notable", "wikipedia_name", "wikipedia_url"]
    with open(enriched_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(enriched)

    notable_count = sum(1 for r in enriched if r["notable"])
    print(f"{notable_count} archive records flagged as notable")
    print(f"Enriched CSV saved to {enriched_csv.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
