"""
Download EU food safety regulations from the Cellar REST API.

Uses HTTP content negotiation against the Cellar endpoint, which requires
no authentication and returns XHTML (newer docs) or HTML (older docs).
The EUR-Lex website itself is behind AWS WAF bot protection, so we use
the publications.europa.eu Cellar endpoint instead.
"""

import logging
import time
import urllib.request
from pathlib import Path

from src.ingestion.corpus import CORPUS

logger = logging.getLogger(__name__)

CELLAR_BASE = "http://publications.europa.eu/resource/celex/"

# Content negotiation headers — must accept both text/html (older docs)
# and application/xhtml+xml (newer docs) or older regulations return 404.
REQUEST_HEADERS = {
    "Accept": "text/html, application/xhtml+xml;q=0.9",
    "Accept-Language": "eng",
}

DELAY_BETWEEN_REQUESTS = 1.0  # seconds, be polite to the API


def download_regulation(celex_id: str, output_dir: Path) -> dict:
    """Download a single regulation by CELEX number.

    Returns a dict with download metadata (celex, size, format, path).
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{celex_id}.html"

    if output_path.exists():
        size = output_path.stat().st_size
        logger.info(f"Already downloaded: {celex_id} ({size:,} bytes)")
        return {
            "celex": celex_id,
            "size": size,
            "path": str(output_path),
            "skipped": True,
        }

    url = f"{CELLAR_BASE}{celex_id}"
    req = urllib.request.Request(url, headers=REQUEST_HEADERS)

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = resp.read()
            content_type = resp.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        logger.error(f"HTTP {e.code} for {celex_id}: {e.reason}")
        return {"celex": celex_id, "error": f"HTTP {e.code}: {e.reason}"}
    except urllib.error.URLError as e:
        logger.error(f"URL error for {celex_id}: {e.reason}")
        return {"celex": celex_id, "error": str(e.reason)}

    output_path.write_bytes(content)

    fmt = "xhtml" if "xhtml" in content_type else "html"
    logger.info(f"Downloaded {celex_id}: {len(content):,} bytes ({fmt})")

    return {
        "celex": celex_id,
        "size": len(content),
        "format": fmt,
        "path": str(output_path),
        "skipped": False,
    }


def download_corpus(
    output_dir: Path | str = "data/raw/html",
    celex_ids: list[str] | None = None,
) -> list[dict]:
    """Download all regulations in the corpus (or a subset).

    Args:
        output_dir: Directory to save HTML files.
        celex_ids: Optional subset of CELEX IDs. If None, downloads the full corpus.

    Returns:
        List of download result dicts.
    """
    output_dir = Path(output_dir)
    ids = celex_ids or list(CORPUS.keys())

    logger.info(f"Downloading {len(ids)} regulations to {output_dir}")
    results = []

    for i, celex_id in enumerate(ids):
        result = download_regulation(celex_id, output_dir)
        results.append(result)

        # Only delay if we actually downloaded (not skipped/errored)
        if not result.get("skipped") and not result.get("error"):
            if i < len(ids) - 1:
                time.sleep(DELAY_BETWEEN_REQUESTS)

    downloaded = sum(1 for r in results if not r.get("skipped") and not r.get("error"))
    skipped = sum(1 for r in results if r.get("skipped"))
    errors = sum(1 for r in results if r.get("error"))
    logger.info(f"Done: {downloaded} downloaded, {skipped} skipped, {errors} errors")

    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    results = download_corpus()

    print(f"\n{'='*60}")
    print(f"{'CELEX':<20} {'Size':>10} {'Status'}")
    print(f"{'='*60}")
    for r in results:
        if r.get("error"):
            print(f"{r['celex']:<20} {'':>10} ERROR: {r['error']}")
        else:
            status = "skipped" if r.get("skipped") else "ok"
            print(f"{r['celex']:<20} {r['size']:>10,} {status}")
