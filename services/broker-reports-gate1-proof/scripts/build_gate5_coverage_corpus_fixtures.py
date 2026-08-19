#!/usr/bin/env python3
"""Build deterministic binary fixtures for the G5.37 coverage corpus."""

from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZIP_STORED, ZipFile, ZipInfo


SERVICE_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = SERVICE_ROOT / "tests/fixtures/g537_multisheet_disposal.xlsx"


def _zip_entry(name: str, content: str) -> tuple[ZipInfo, bytes]:
    info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = ZIP_STORED
    info.create_system = 0
    info.external_attr = 0
    return info, content.encode("utf-8")


def _shared_cell(ref: str, index: int) -> str:
    return f'<c r="{ref}" t="s"><v>{index}</v></c>'


def _number_cell(ref: str, value: str) -> str:
    return f'<c r="{ref}"><v>{escape(value)}</v></c>'


def build() -> bytes:
    shared = [
        "Отчет по сделкам и операциям",
        "Период",
        "2025",
        "Вид операции",
        "Дата сделки",
        "Инструмент",
        "Количество",
        "Цена за единицу",
        "Сумма сделки",
        "Валюта",
        "Продажа",
        "2025-02-11",
        "ASSET-G536",
        "RUB",
        "Сводные данные",
        "Показатель",
        "Значение",
        "Количество сделок",
    ]
    shared_xml = "".join(f"<si><t>{escape(value)}</t></si>" for value in shared)
    files = {
        "[Content_Types].xml": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>
""",
        "_rels/.rels": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>
""",
        "xl/workbook.xml": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="Сделки" sheetId="1" r:id="rId1"/>
    <sheet name="Итоги" sheetId="2" r:id="rId2"/>
  </sheets>
</workbook>
""",
        "xl/_rels/workbook.xml.rels": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>
  <Relationship Id="rId4" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>
""",
        "xl/sharedStrings.xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            f'count="{len(shared)}" uniqueCount="{len(shared)}">{shared_xml}</sst>\n'
        ),
        "xl/styles.xml": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>
  <fills count="1"><fill><patternFill patternType="none"/></fill></fills>
  <borders count="1"><border/></borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
  <cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs>
</styleSheet>
""",
        "xl/worksheets/sheet1.xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
            f'<row r="1">{_shared_cell("A1", 0)}</row>'
            f'<row r="2">{_shared_cell("A2", 1)}{_shared_cell("B2", 2)}</row>'
            '<row r="4">'
            + "".join(
                _shared_cell(f"{column}4", index)
                for column, index in zip("ABCDEFG", range(3, 10), strict=True)
            )
            + '</row><row r="5">'
            + _shared_cell("A5", 10)
            + _shared_cell("B5", 11)
            + _shared_cell("C5", 12)
            + _number_cell("D5", "1")
            + _number_cell("E5", "100.00")
            + _number_cell("F5", "100.00")
            + _shared_cell("G5", 13)
            + "</row></sheetData></worksheet>\n"
        ),
        "xl/worksheets/sheet2.xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
            f'<row r="1">{_shared_cell("A1", 14)}</row>'
            f'<row r="3">{_shared_cell("A3", 15)}{_shared_cell("B3", 16)}</row>'
            f'<row r="4">{_shared_cell("A4", 17)}{_number_cell("B4", "1")}</row>'
            "</sheetData></worksheet>\n"
        ),
    }
    from io import BytesIO

    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        for name in sorted(files):
            info, content = _zip_entry(name, files[name])
            archive.writestr(info, content)
    return buffer.getvalue()


def main() -> int:
    OUTPUT.write_bytes(build())
    print(OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
