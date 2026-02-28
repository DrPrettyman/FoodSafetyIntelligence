"""
Download EU food safety regulations from the Cellar REST API.

Uses HTTP content negotiation against the Cellar endpoint, which requires
no authentication and returns XHTML (newer docs) or HTML (older docs).
The EUR-Lex website itself is behind AWS WAF bot protection, so we use
the publications.europa.eu Cellar endpoint instead.

Supports downloading consolidated (as-amended) text when available.
Consolidated texts use CELEX format 0YYYYTNNNN-YYYYMMDD and are in CLG HTML format.
"""

import logging
import time
import urllib.request
from pathlib import Path

from src.ingestion.corpus import CORPUS, get_consolidated_celex

logger = logging.getLogger(__name__)

CELLAR_BASE = "http://publications.europa.eu/resource/celex/"

# Content negotiation headers — must accept both text/html (older docs)
# and application/xhtml+xml (newer docs) or older regulations return 404.
REQUEST_HEADERS = {
    "Accept": "text/html, application/xhtml+xml;q=0.9",
    "Accept-Language": "eng",
}

DELAY_BETWEEN_REQUESTS = 1.0  # seconds, be polite to the API
MAX_RETRIES = 3


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

    for attempt in range(MAX_RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                content = resp.read()
                content_type = resp.headers.get("Content-Type", "")
            break
        except urllib.error.HTTPError as e:
            if e.code in (502, 503) and attempt < MAX_RETRIES - 1:
                wait = (attempt + 1) * 5
                logger.warning(f"HTTP {e.code} for {celex_id}, retrying in {wait}s...")
                time.sleep(wait)
                continue
            logger.error(f"HTTP {e.code} for {celex_id}: {e.reason}")
            return {"celex": celex_id, "error": f"HTTP {e.code}: {e.reason}"}
        except (urllib.error.URLError, ConnectionResetError, TimeoutError) as e:
            if attempt < MAX_RETRIES - 1:
                wait = (attempt + 1) * 5
                logger.warning(f"Connection error for {celex_id}, retrying in {wait}s...")
                time.sleep(wait)
                continue
            logger.error(f"Connection error for {celex_id}: {e}")
            return {"celex": celex_id, "error": str(e)}

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
    prefer_consolidated: bool = True,
) -> list[dict]:
    """Download all regulations in the corpus (or a subset).

    Args:
        output_dir: Directory to save HTML files.
        celex_ids: Optional subset of CELEX IDs. If None, downloads the full corpus.
        prefer_consolidated: If True, download consolidated (as-amended) text
            when available. Falls back to original if no consolidated version exists.

    Returns:
        List of download result dicts.
    """
    output_dir = Path(output_dir)
    ids = celex_ids or list(CORPUS.keys())
    consolidated = get_consolidated_celex() if prefer_consolidated else {}

    logger.info(
        f"Downloading {len(ids)} regulations to {output_dir}"
        f" (consolidated={prefer_consolidated}, {len(consolidated)} available)"
    )
    results = []

    for i, celex_id in enumerate(ids):
        # Use consolidated CELEX if available, otherwise original
        download_id = consolidated.get(celex_id, celex_id) if prefer_consolidated else celex_id
        result = download_regulation(download_id, output_dir)

        # Fall back to original if consolidated download failed
        if result.get("error") and download_id != celex_id:
            logger.info(f"Consolidated {download_id} failed, falling back to original {celex_id}")
            result = download_regulation(celex_id, output_dir)
            download_id = celex_id

        # Tag the result with the base CELEX for tracking
        result["base_celex"] = celex_id
        result["is_consolidated"] = download_id != celex_id
        results.append(result)

        # Only delay if we actually downloaded (not skipped/errored)
        if not result.get("skipped") and not result.get("error"):
            if i < len(ids) - 1:
                time.sleep(DELAY_BETWEEN_REQUESTS)

    downloaded = sum(1 for r in results if not r.get("skipped") and not r.get("error"))
    skipped = sum(1 for r in results if r.get("skipped"))
    errors = sum(1 for r in results if r.get("error"))
    n_consolidated = sum(1 for r in results if r.get("is_consolidated") and not r.get("error"))
    logger.info(
        f"Done: {downloaded} downloaded ({n_consolidated} consolidated), "
        f"{skipped} skipped, {errors} errors"
    )

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Download EU food safety regulations")
    parser.add_argument("--original", action="store_true", help="Download original text (not consolidated)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    results = download_corpus(prefer_consolidated=not args.original)

    print(f"\n{'='*70}")
    print(f"{'Base CELEX':<15} {'Download CELEX':<30} {'Size':>10} {'Status'}")
    print(f"{'='*70}")
    for r in results:
        base = r.get("base_celex", r["celex"])
        dl = r["celex"]
        if r.get("error"):
            print(f"{base:<15} {dl:<30} {'':>10} ERROR: {r['error']}")
        else:
            status = "skipped" if r.get("skipped") else "ok"
            consol = " (C)" if r.get("is_consolidated") else ""
            print(f"{base:<15} {dl:<30} {r['size']:>10,} {status}{consol}")
