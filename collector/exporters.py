"""Write collected rows to CSV, JSON or Excel (Excel includes a Summary sheet with live formulas)."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Optional, Sequence

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

FONT = "Arial"
HEADER_FONT = Font(name=FONT, size=10, bold=True, color="FFFFFF")
HEADER_FILL = PatternFill("solid", start_color="1F3864")
BASE_FONT = Font(name=FONT, size=10)

# A summary line: (label, formula template, number format). Templates use {column_key} placeholders,
# which are replaced by the matching range on the Data sheet, e.g. =SUM({stars}).
SummaryLine = tuple[str, str, str]


def export_csv(rows: Sequence[dict[str, Any]], path: Path, columns: Sequence[str]) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as handle:  # utf-8-sig: Excel opens accents correctly
        writer = csv.DictWriter(handle, fieldnames=list(columns), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def export_json(rows: Sequence[dict[str, Any]], path: Path, columns: Sequence[str]) -> None:
    clean = [{key: row.get(key) for key in columns} for row in rows]
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(clean, handle, ensure_ascii=False, indent=2)


def export_xlsx(
    rows: Sequence[dict[str, Any]],
    path: Path,
    columns: Sequence[str],
    summary: Optional[Sequence[SummaryLine]] = None,
    title: str = "Collected data",
) -> None:
    if not rows:
        raise ValueError("No rows to export")
    wb = Workbook()
    summary_ws = wb.active
    summary_ws.title = "Summary"
    data_ws = wb.create_sheet("Data")

    data_ws.append(list(columns))
    for col in range(1, len(columns) + 1):
        cell = data_ws.cell(row=1, column=col)
        cell.font, cell.fill = HEADER_FONT, HEADER_FILL
        cell.alignment = Alignment(horizontal="center")
    for row in rows:
        data_ws.append([row.get(key) for key in columns])
    last_row = len(rows) + 1
    for data_row in data_ws.iter_rows(min_row=2, max_row=last_row):
        for cell in data_row:
            cell.font = BASE_FONT
    for index, key in enumerate(columns, start=1):
        longest = max(len(str(key)), *(len(str(row.get(key, ""))) for row in rows))
        data_ws.column_dimensions[get_column_letter(index)].width = min(max(longest + 2, 10), 60)
    data_ws.freeze_panes = "A2"
    data_ws.auto_filter.ref = f"A1:{get_column_letter(len(columns))}{last_row}"

    ranges = {
        key: f"Data!${get_column_letter(i)}$2:${get_column_letter(i)}${last_row}"
        for i, key in enumerate(columns, start=1)
    }
    summary_ws["A1"] = title
    summary_ws["A1"].font = Font(name=FONT, size=16, bold=True)
    summary_ws["A2"] = "Figures below are formulas based on the Data sheet."
    summary_ws["A2"].font = Font(name=FONT, size=9, italic=True, color="595959")
    for offset, (label, template, number_format) in enumerate(summary or [], start=4):
        summary_ws[f"A{offset}"] = label
        summary_ws[f"A{offset}"].font = Font(name=FONT, size=10, bold=True)
        summary_ws[f"B{offset}"] = template.format(**ranges)
        summary_ws[f"B{offset}"].font = BASE_FONT
        summary_ws[f"B{offset}"].number_format = number_format
        summary_ws[f"B{offset}"].alignment = Alignment(horizontal="right")
    summary_ws.column_dimensions["A"].width = 28
    summary_ws.column_dimensions["B"].width = 30
    wb.save(path)


def export(
    rows: Sequence[dict[str, Any]],
    path: Path,
    columns: Sequence[str],
    summary: Optional[Sequence[SummaryLine]] = None,
    title: str = "Collected data",
) -> None:
    """Choose the format from the file extension (.xlsx, .csv or .json)."""
    path = Path(path)
    if path.parent and not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
    suffix = path.suffix.lower()
    if suffix == ".xlsx":
        export_xlsx(rows, path, columns, summary, title)
    elif suffix == ".csv":
        export_csv(rows, path, columns)
    elif suffix == ".json":
        export_json(rows, path, columns)
    else:
        raise ValueError(f"Unsupported output format '{suffix}'. Use .xlsx, .csv or .json")
