import urllib.request
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.ingestion.eurlex_downloader import (
    CELLAR_BASE,
    REQUEST_HEADERS,
    download_corpus,
    download_regulation,
)


def test_cellar_base_url():
    assert CELLAR_BASE == "http://publications.europa.eu/resource/celex/"


def test_headers_accept_both_formats():
    """Must accept both text/html and application/xhtml+xml to handle old and new docs."""
    accept = REQUEST_HEADERS["Accept"]
    assert "text/html" in accept
    assert "application/xhtml+xml" in accept


def test_headers_request_english():
    assert REQUEST_HEADERS["Accept-Language"] == "eng"


def test_download_skips_existing_file(tmp_path):
    """If the file already exists, download should skip it."""
    existing = tmp_path / "32015R2283.html"
    existing.write_text("<html>already here</html>")

    result = download_regulation("32015R2283", tmp_path)

    assert result["skipped"] is True
    assert result["celex"] == "32015R2283"
    assert result["size"] > 0


def test_download_handles_http_error(tmp_path):
    """HTTP errors should return an error dict, not raise."""
    with patch("src.ingestion.eurlex_downloader.urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="http://example.com", code=404, msg="Not Found", hdrs={}, fp=None
        )
        result = download_regulation("INVALID_CELEX", tmp_path)

    assert "error" in result
    assert "404" in result["error"]


def test_download_writes_file(tmp_path):
    """Successful download should write the file and return metadata."""
    fake_content = b"<html><body>regulation text</body></html>"
    mock_response = MagicMock()
    mock_response.read.return_value = fake_content
    mock_response.headers = {"Content-Type": "application/xhtml+xml;charset=UTF-8"}
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)

    with patch("src.ingestion.eurlex_downloader.urllib.request.urlopen", return_value=mock_response):
        result = download_regulation("32015R2283", tmp_path)

    assert result["celex"] == "32015R2283"
    assert result["size"] == len(fake_content)
    assert result["format"] == "xhtml"
    assert not result.get("skipped")
    assert (tmp_path / "32015R2283.html").exists()
    assert (tmp_path / "32015R2283.html").read_bytes() == fake_content


def test_download_detects_html_format(tmp_path):
    """Older documents served as text/html should be detected correctly."""
    fake_content = b"<html><body>old regulation</body></html>"
    mock_response = MagicMock()
    mock_response.read.return_value = fake_content
    mock_response.headers = {"Content-Type": "text/html;charset=UTF-8"}
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)

    with patch("src.ingestion.eurlex_downloader.urllib.request.urlopen", return_value=mock_response):
        result = download_regulation("32002R0178", tmp_path)

    assert result["format"] == "html"


def test_download_retries_on_502(tmp_path):
    """502 errors should trigger retry, not immediately fail."""
    fake_content = b"<html><body>regulation</body></html>"
    mock_response = MagicMock()
    mock_response.read.return_value = fake_content
    mock_response.headers = {"Content-Type": "text/html"}
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)

    with patch("src.ingestion.eurlex_downloader.urllib.request.urlopen") as mock_urlopen, \
         patch("src.ingestion.eurlex_downloader.time.sleep"):
        # First call raises 502, second succeeds
        mock_urlopen.side_effect = [
            urllib.error.HTTPError(
                url="http://example.com", code=502, msg="Bad Gateway", hdrs={}, fp=None
            ),
            mock_response,
        ]
        result = download_regulation("32015R2283", tmp_path)

    assert "error" not in result
    assert result["size"] == len(fake_content)


def test_download_retries_on_connection_reset(tmp_path):
    """ConnectionResetError should trigger retry."""
    fake_content = b"<html><body>regulation</body></html>"
    mock_response = MagicMock()
    mock_response.read.return_value = fake_content
    mock_response.headers = {"Content-Type": "text/html"}
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)

    with patch("src.ingestion.eurlex_downloader.urllib.request.urlopen") as mock_urlopen, \
         patch("src.ingestion.eurlex_downloader.time.sleep"):
        mock_urlopen.side_effect = [
            ConnectionResetError("Connection reset by peer"),
            mock_response,
        ]
        result = download_regulation("32002R0178", tmp_path)

    assert "error" not in result
    assert result["size"] == len(fake_content)


def test_download_corpus_consolidated(tmp_path):
    """download_corpus with prefer_consolidated uses consolidated CELEX IDs."""
    fake_content = b"<html><body>consolidated</body></html>"
    mock_response = MagicMock()
    mock_response.read.return_value = fake_content
    mock_response.headers = {"Content-Type": "text/html"}
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)

    with patch("src.ingestion.eurlex_downloader.urllib.request.urlopen", return_value=mock_response), \
         patch("src.ingestion.eurlex_downloader.time.sleep"), \
         patch("src.ingestion.eurlex_downloader.CORPUS", {"32002R0178": {"category": "general_food_law", "title": "Test"}}), \
         patch("src.ingestion.eurlex_downloader.get_consolidated_celex", return_value={"32002R0178": "02002R0178-20260101"}):
        results = download_corpus(output_dir=tmp_path, prefer_consolidated=True)

    assert len(results) == 1
    assert results[0]["celex"] == "02002R0178-20260101"
    assert results[0]["base_celex"] == "32002R0178"
    assert results[0]["is_consolidated"] is True


def test_download_corpus_original(tmp_path):
    """download_corpus with prefer_consolidated=False uses base CELEX IDs."""
    fake_content = b"<html><body>original</body></html>"
    mock_response = MagicMock()
    mock_response.read.return_value = fake_content
    mock_response.headers = {"Content-Type": "text/html"}
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)

    with patch("src.ingestion.eurlex_downloader.urllib.request.urlopen", return_value=mock_response), \
         patch("src.ingestion.eurlex_downloader.time.sleep"), \
         patch("src.ingestion.eurlex_downloader.CORPUS", {"32002R0178": {"category": "general_food_law", "title": "Test"}}), \
         patch("src.ingestion.eurlex_downloader.get_consolidated_celex", return_value={"32002R0178": "02002R0178-20260101"}):
        results = download_corpus(output_dir=tmp_path, prefer_consolidated=False)

    assert len(results) == 1
    assert results[0]["celex"] == "32002R0178"
    assert results[0]["is_consolidated"] is False


def test_download_corpus_fallback_on_consolidated_error(tmp_path):
    """When consolidated download fails (404), should fall back to original CELEX."""
    fake_content = b"<html><body>original text</body></html>"
    mock_response = MagicMock()
    mock_response.read.return_value = fake_content
    mock_response.headers = {"Content-Type": "text/html"}
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)

    call_count = 0

    def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # First call (consolidated) fails with 404
            raise urllib.error.HTTPError(
                url="http://example.com", code=404, msg="Not Found", hdrs={}, fp=None
            )
        # Second call (original) succeeds
        return mock_response

    with patch("src.ingestion.eurlex_downloader.urllib.request.urlopen", side_effect=side_effect), \
         patch("src.ingestion.eurlex_downloader.time.sleep"), \
         patch("src.ingestion.eurlex_downloader.CORPUS", {"32002R0178": {"category": "general_food_law", "title": "Test"}}), \
         patch("src.ingestion.eurlex_downloader.get_consolidated_celex", return_value={"32002R0178": "02002R0178-20260101"}):
        results = download_corpus(output_dir=tmp_path, prefer_consolidated=True)

    assert len(results) == 1
    assert results[0]["celex"] == "32002R0178"  # Fell back to original
    assert results[0]["is_consolidated"] is False
    assert "error" not in results[0]
