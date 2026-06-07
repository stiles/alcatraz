"""
Scrape and normalize the Alcatraz prisoner list from the National Archives.

Source: https://www.archives.gov/san-francisco/finding-aids/alcatraz-alpha
All five alphabetical sections (A-G, H-L, M-Q, R-T, U-Z) live on one page.

Output:
  data/inmates.json  - full record list
  data/inmates.csv   - same data as CSV
Columns: register_number, name_raw, name_last, name_given, name_suffix, name_full
"""

import csv
import json
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"

SOURCE_URL = "https://www.archives.gov/san-francisco/finding-aids/alcatraz-alpha"

# Honorific/generational suffixes that appear after a trailing comma.
SUFFIX_RE = re.compile(r"^(Jr\.|Sr\.|II|III|IV|2nd|3rd)$", re.IGNORECASE)


def normalize_name(raw: str) -> tuple[str, str, str, str]:
    """
    Parse 'LAST, FIRST MIDDLE[, SUFFIX]' into components.

    Returns (name_last, name_given, name_suffix, name_full) all in title case.
    """
    raw = raw.strip()

    first_comma = raw.find(",")
    if first_comma == -1:
        tc = raw.title()
        return tc, "", "", tc

    last_raw = raw[:first_comma].strip()
    rest_raw = raw[first_comma + 1 :].strip()

    # Detect a trailing generational suffix after the last comma in rest.
    suffix_raw = ""
    last_comma = rest_raw.rfind(",")
    if last_comma != -1:
        candidate = rest_raw[last_comma + 1 :].strip()
        if SUFFIX_RE.match(candidate):
            suffix_raw = candidate
            rest_raw = rest_raw[:last_comma].strip()

    name_last = last_raw.title()
    name_given = rest_raw.title()
    name_suffix = suffix_raw.title() if suffix_raw else ""

    # Fix edge cases where .title() mangles Roman numerals.
    name_suffix = re.sub(r"^Ii$", "II", name_suffix)
    name_suffix = re.sub(r"^Iii$", "III", name_suffix)
    name_suffix = re.sub(r"^Iv$", "IV", name_suffix)

    parts = [name_given, name_last]
    if name_suffix:
        parts.append(name_suffix)
    name_full = " ".join(p for p in parts if p)

    return name_last, name_given, name_suffix, name_full


def scrape_inmates() -> list[dict]:
    resp = requests.get(SOURCE_URL, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    rows = []

    for tr in soup.select("table tr"):
        cells = tr.find_all("td")
        if len(cells) < 2:
            continue

        name_raw = cells[0].get_text(strip=True)
        register = cells[1].get_text(strip=True)

        if not name_raw or not register.isdigit():
            continue

        name_last, name_given, name_suffix, name_full = normalize_name(name_raw)

        rows.append(
            {
                "register_number": int(register),
                "name_raw": name_raw,
                "name_last": name_last,
                "name_given": name_given,
                "name_suffix": name_suffix,
                "name_full": name_full,
            }
        )

    return rows


def main() -> None:
    print("Scraping National Archives prisoner list...")
    inmates = scrape_inmates()
    print(f"Found {len(inmates)} records")

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    json_file = DATA_DIR / "inmates.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(inmates, f, indent=2, ensure_ascii=False)
    print(f"Saved to {json_file.relative_to(ROOT)}")

    csv_file = DATA_DIR / "inmates.csv"
    fieldnames = ["register_number", "name_raw", "name_last", "name_given", "name_suffix", "name_full"]
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(inmates)
    print(f"Saved to {csv_file.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
