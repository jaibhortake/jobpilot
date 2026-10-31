import csv
import io
import re
from dataclasses import dataclass, field

from openpyxl import load_workbook

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_URL_SPLIT = re.compile(r"[\s,]+")


@dataclass
class SheetRow:
    company: str
    urls: list[str]
    emails: list[str]


@dataclass
class SheetParse:
    rows: list[SheetRow] = field(default_factory=list)
    skipped_blank: int = 0


class BadUpload(ValueError):
    pass


def _cells(data: bytes, filename: str) -> list[list[str]]:
    name = filename.lower()
    if name.endswith(".xlsx"):
        ws = load_workbook(io.BytesIO(data), read_only=True, data_only=True).worksheets[0]
        return [
            ["" if c is None else str(c) for c in row] for row in ws.iter_rows(values_only=True)
        ]
    if name.endswith(".csv"):
        return list(csv.reader(io.StringIO(data.decode("utf-8-sig"))))
    raise BadUpload("only .xlsx or .csv files are accepted")


def parse_sheet(data: bytes, filename: str) -> SheetParse:
    table = _cells(data, filename)
    if not table:
        raise BadUpload("empty file")
    header = [h.strip().lower() for h in table[0]]
    try:
        c_name = header.index("company")
    except ValueError as exc:
        raise BadUpload("missing 'Company' column") from exc
    c_url = header.index("website") if "website" in header else None
    c_hr = next((i for i, h in enumerate(header) if h.startswith("hr")), None)

    out = SheetParse()
    for row in table[1:]:
        def cell(i: int | None, row: list[str] = row) -> str:
            return row[i].strip() if i is not None and i < len(row) else ""

        name = cell(c_name)
        if not name:
            out.skipped_blank += 1
            continue
        urls = [u for u in _URL_SPLIT.split(cell(c_url)) if u]
        out.rows.append(SheetRow(name, urls, EMAIL_RE.findall(cell(c_hr))))
    return out
