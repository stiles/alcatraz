"""
Scrape the 14 Alcatraz escape attempts from the Bureau of Prisons history page.

Source: https://www.bop.gov/about/history/alcatraz.jsp
Requires: data/inmates.csv (run scrape_inmates.py first)

Output:
  data/escape_attempts.json  - structured attempt records with participant matches
  data/escape_attempts.csv   - flat version (one row per attempt)
"""

import csv
import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"

SOURCE_URL = "https://www.bop.gov/about/history/alcatraz.jsp"
HEADERS = {"User-Agent": "AlcatrazResearch/1.0 (educational)"}

# Words that look like names but aren't prisoner last names.
FALSE_POSITIVE_LAST_NAMES = {
    "SAN", "BAY", "ISLAND", "FRANCISCO", "ANGEL", "ALCATRAZ", "GOLDEN",
    "GATE", "MARINES", "NAVY", "ARMY", "FORT", "POINT",
    "PACIFIC", "CORRECTIONAL", "FEDERAL", "AFTER", "OVER",
}


# ── Date parsing ──────────────────────────────────────────────────────────────

def parse_date(raw: str) -> tuple[str, str]:
    """
    Return (date_start, date_end) as ISO strings.
    Handles single dates ('April 27, 1936') and ranges ('May 2-4, 1946').
    """
    raw = raw.strip()
    range_match = re.match(r"^(\w+)\s+(\d+)-(\d+),\s*(\d{4})$", raw)
    if range_match:
        month, d1, d2, year = range_match.groups()
        start = datetime.strptime(f"{month} {d1}, {year}", "%B %d, %Y").date().isoformat()
        end = datetime.strptime(f"{month} {d2}, {year}", "%B %d, %Y").date().isoformat()
        return start, end
    d = datetime.strptime(raw, "%B %d, %Y").date().isoformat()
    return d, d


# ── Participant extraction ────────────────────────────────────────────────────

def build_last_name_index(inmates: list[dict]) -> dict[str, list[dict]]:
    index = defaultdict(list)
    for row in inmates:
        index[row["name_last"].upper()].append(row)
    return index


def _match_name(first_word: str, last_word: str, index: dict) -> list[dict]:
    """
    Return archive rows for a (first, last) name pair.

    Tries 3-char prefix → 1-char prefix → nickname substring, in that order.
    Returns empty list if no plausible match is found.
    """
    if last_word.upper() in FALSE_POSITIVE_LAST_NAMES:
        return []
    candidates = index.get(last_word.upper(), [])
    if not candidates:
        return []

    first_upper = first_word.upper()

    by_3 = [c for c in candidates if c["name_given"].upper().startswith(first_upper[:3])]
    if by_3:
        return by_3

    by_1 = [c for c in candidates if c["name_given"].upper().startswith(first_upper[0])]
    if by_1:
        return by_1

    by_nick = [c for c in candidates if first_upper in c["name_raw"].upper()]
    if by_nick:
        return by_nick

    return []


def find_participants(narrative: str, index: dict[str, list[dict]]) -> list[dict]:
    """
    Extract prisoner names from free text and match against the archive.

    Handles:
    - 'First Last' and 'First "Nick" Last' pairs
    - Mixed-case last names like McCain, McPherson
    - 'First Middle Last' three-word names (e.g. 'John Paul Scott')
    - 'FirstA and FirstB LastName' constructs (e.g. 'John and Clarence Anglin')
    """
    found: dict[str, dict] = {}

    def add_matches(first_word: str, last_word: str, mention: str) -> None:
        for inmate in _match_name(first_word, last_word, index):
            reg = inmate["register_number"]
            if reg not in found:
                found[reg] = {
                    "register_number": int(reg),
                    "name_as_mentioned": mention,
                    "name_raw": inmate["name_raw"],
                    "name_full": inmate["name_full"],
                }

    name_word = r'[A-Z][a-zA-Z\'-]+'

    # Pattern 1: 'First ["Nick"] Last'
    for m in re.finditer(rf'\b({name_word})(?:\s+"[^"]*")?\s+({name_word})\b', narrative):
        add_matches(m.group(1), m.group(2), m.group(0))

    # Pattern 2: 'First Middle Last' — use first and last, skip middle.
    for m in re.finditer(rf'\b({name_word})\s+{name_word}\s+({name_word})\b', narrative):
        add_matches(m.group(1), m.group(2), f"{m.group(1)} {m.group(2)}")

    # Pattern 3: 'FirstA and FirstB LastName'
    # Guard: skip first_a if it's itself a known archive last name.
    for m in re.finditer(rf'\b({name_word})\s+and\s+({name_word})\s+({name_word})\b', narrative):
        first_a, first_b, last = m.group(1), m.group(2), m.group(3)
        if first_a.upper() not in index:
            add_matches(first_a, last, f"{first_a} {last}")
        add_matches(first_b, last, f"{first_b} {last}")

    return sorted(found.values(), key=lambda r: r["register_number"])


# ── Scraping ──────────────────────────────────────────────────────────────────

def scrape_escape_attempts(inmates: list[dict]) -> list[dict]:
    resp = requests.get(SOURCE_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    accordion = soup.find(id="escape_attempts_accordion")

    index = build_last_name_index(inmates)
    attempts = []

    for i, h4 in enumerate(accordion.find_all("h4"), start=1):
        header_text = h4.get_text(separator=" ", strip=True)
        header_clean = re.sub(r"^\s*\S+\s+", "", header_text).strip()
        year_match = re.match(r"^(\d{4})\s*-\s*(.+)$", header_clean)
        year = int(year_match.group(1)) if year_match else None
        nickname = year_match.group(2).strip() if year_match else header_clean

        p = h4.find_next_sibling("p")
        date_tag = p.find("i")
        date_raw = date_tag.get_text(strip=True) if date_tag else ""

        full_text = re.sub(r"\s+", " ", p.get_text(separator=" ")).strip()
        description = re.sub(r"^[^-–]+-+\s*", "", full_text).strip()

        date_start, date_end = parse_date(date_raw) if date_raw else ("", "")

        attempts.append(
            {
                "attempt_number": i,
                "year": year,
                "nickname": nickname,
                "date_raw": date_raw,
                "date_start": date_start,
                "date_end": date_end,
                "description": description,
                "participants": find_participants(full_text, index),
            }
        )

    return attempts


def main() -> None:
    inmates_csv = DATA_DIR / "inmates.csv"
    with open(inmates_csv, newline="", encoding="utf-8") as f:
        inmates = list(csv.DictReader(f))

    print("Scraping BOP escape attempts...")
    attempts = scrape_escape_attempts(inmates)
    print(f"Found {len(attempts)} attempts")

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    json_file = DATA_DIR / "escape_attempts.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(attempts, f, indent=2, ensure_ascii=False)
    print(f"Saved to {json_file.relative_to(ROOT)}")

    csv_file = DATA_DIR / "escape_attempts.csv"
    flat_fieldnames = [
        "attempt_number", "year", "nickname", "date_raw",
        "date_start", "date_end", "description", "participant_registers",
    ]
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=flat_fieldnames)
        writer.writeheader()
        for attempt in attempts:
            row = {k: attempt[k] for k in flat_fieldnames if k != "participant_registers"}
            row["participant_registers"] = "|".join(
                str(p["register_number"]) for p in attempt["participants"]
            )
            writer.writerow(row)
    print(f"Saved to {csv_file.relative_to(ROOT)}")

    print()
    for a in attempts:
        regs = ", ".join(str(p["register_number"]) for p in a["participants"]) or "—"
        print(f"  #{a['attempt_number']:2d}  {a['date_start']}  {a['nickname']}")
        print(f"       participants: {regs}")


if __name__ == "__main__":
    main()
