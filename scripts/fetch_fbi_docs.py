"""
Scrape and download FBI vault documents for the Alcatraz Escape case.

Source: https://vault.fbi.gov/Alcatraz%20Escape/
Output:
  data/fbi_docs.json   - index of all documents with view and download URLs
  documents/*.pdf      - downloaded PDF files (skips existing)
"""

import json
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
DOCS_DIR = ROOT / "documents"

BASE_URL = "https://vault.fbi.gov"
INDEX_URL = f"{BASE_URL}/Alcatraz%20Escape/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def scrape_index() -> list[dict]:
    """Return a list of dicts with title, view_url, and download_url for each document."""
    resp = requests.get(INDEX_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    docs = []

    for a in soup.select("a.pdf-grid-link"):
        href = a["href"].strip()
        title_el = a.select_one(".pdf-grid-title")
        title = title_el.get_text(strip=True) if title_el else href

        view_url = BASE_URL + href if href.startswith("/") else href
        download_url = view_url.replace("/view", "/at_download/file")

        docs.append({"title": title, "view_url": view_url, "download_url": download_url})

    return docs


def download_docs(docs: list[dict], delay: float = 1.5) -> None:
    """Download each document PDF. Skips files that already exist."""
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    for doc in docs:
        filename = doc["title"].replace(" ", "_") + ".pdf"
        path = DOCS_DIR / filename

        if path.exists():
            print(f"  skip  {filename}")
            continue

        print(f"  fetch {filename} ...")
        resp = requests.get(doc["download_url"], headers=HEADERS, stream=True, timeout=60)
        resp.raise_for_status()

        with open(path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

        print(f"        {path.stat().st_size // 1024} KB")
        time.sleep(delay)


def main() -> None:
    print("Scraping FBI vault index...")
    docs = scrape_index()
    print(f"Found {len(docs)} documents")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    index_file = DATA_DIR / "fbi_docs.json"
    with open(index_file, "w") as f:
        json.dump(docs, f, indent=2)
    print(f"Index saved to {index_file.relative_to(ROOT)}")

    print("\nDownloading PDFs...")
    download_docs(docs)
    print("\nDone.")


if __name__ == "__main__":
    main()
