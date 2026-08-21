"""S3.1 report framework (ticket #23): PDF export.

`GET /api/v1/reports/{code}/export?format=pdf[&paper=A5]` produces a real
PDF built by fpdf2 with the bundled OFL IBM Plex Sans Arabic font and
HarfBuzz text shaping — Arabic titles/headers render shaped, not as boxes
(the legacy ModPrint PDF path). `paper` drives the page size exactly like
the HTML print page (A4 default, A5 selectable).
"""
from tests.reports_test_utils import _login_token

A4_WIDTH_PT = 595.28
A5_WIDTH_PT = 419.53


def _mediabox(content: bytes) -> list[float]:
    """Parse the (uncompressed) /MediaBox numbers from the PDF."""
    marker = b"/MediaBox ["
    start = content.index(marker) + len(marker)
    end = content.index(b"]", start)
    return [float(x) for x in content[start:end].split()]


async def test_pdf_export_is_a_real_pdf_with_embedded_arabic_font(client):
    token = await _login_token(client)
    r = await client.get(
        "/api/v1/reports/day_profit/export",
        params={"format": "pdf"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF-")
    # the Arabic font is embedded (subset) — no unshaped tofu output
    assert b"/FontFile2" in r.content


async def test_pdf_paper_selects_the_page_size(client):
    token = await _login_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    a4 = await client.get(
        "/api/v1/reports/day_profit/export",
        params={"format": "pdf"},
        headers=headers,
    )
    a5 = await client.get(
        "/api/v1/reports/day_profit/export",
        params={"format": "pdf", "paper": "A5"},
        headers=headers,
    )
    assert a4.status_code == a5.status_code == 200
    box_a4 = _mediabox(a4.content)
    box_a5 = _mediabox(a5.content)
    assert abs(box_a4[2] - A4_WIDTH_PT) < 1
    assert abs(box_a5[2] - A5_WIDTH_PT) < 1


async def test_pdf_rejects_bad_paper_and_unknown_code(client):
    token = await _login_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    bad_paper = await client.get(
        "/api/v1/reports/day_profit/export",
        params={"format": "pdf", "paper": "Letter"},
        headers=headers,
    )
    assert bad_paper.status_code == 400
    missing = await client.get(
        "/api/v1/reports/nope/export",
        params={"format": "pdf"},
        headers=headers,
    )
    assert missing.status_code == 404
