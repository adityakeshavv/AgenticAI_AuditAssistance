from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any
from zipfile import ZipFile
from xml.etree import ElementTree as ET


class TabularTextService:
    """Extract readable text from CSV and spreadsheet files for semantic search."""

    SPREADSHEET_SUFFIXES = {".xlsx", ".xlsm", ".xltx", ".xltm"}

    def supports(self, path: Path) -> bool:
        return path.suffix.lower() in self.SPREADSHEET_SUFFIXES or path.suffix.lower() == ".csv"

    def extract_text(self, path: Path) -> str:
        units = self.extract_units(path)
        if not units:
            return ""
        return "\n\n".join(str(unit.get("content") or "") for unit in units if str(unit.get("content") or "").strip())

    def extract_units(self, path: Path) -> list[dict[str, Any]]:
        suffix = path.suffix.lower()
        if suffix == ".csv":
            return self._extract_csv_units(path)
        if suffix in self.SPREADSHEET_SUFFIXES:
            return self._extract_xlsx_units(path)
        return []

    def _extract_csv_units(self, path: Path) -> list[dict[str, Any]]:
        try:
            raw_text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return []

        try:
            rows = list(csv.reader(raw_text.splitlines()))
        except Exception:
            rows = [[line.strip()] for line in raw_text.splitlines() if line.strip()]

        if not rows:
            return []

        header = rows[0] if rows else []
        has_header = self._looks_like_header(header)
        units: list[dict[str, Any]] = []
        content_lines: list[str] = []

        for row_index, row in enumerate(rows, start=1):
            cells = [str(cell).strip() for cell in row if str(cell).strip()]
            if not cells:
                continue

            if has_header and row_index > 1 and header:
                pairs = []
                for idx, cell in enumerate(row):
                    cell_value = str(cell).strip()
                    if not cell_value:
                        continue
                    label = str(header[idx]).strip() if idx < len(header) and str(header[idx]).strip() else f"Column {idx + 1}"
                    pairs.append(f"{label}={cell_value}")
                row_text = " | ".join(pairs) if pairs else " | ".join(cells)
            else:
                row_text = " | ".join(cells)

            content_lines.append(f"Row {row_index}: {row_text}")

        if not content_lines:
            return []

        content = "\n".join(content_lines)
        units.append(
            {
                "page_number": 1,
                "section_title": path.stem,
                "citation_text": self._snippet(content),
                "content": content,
                "source_type": "tabular",
            }
        )
        return units

    def _extract_xlsx_units(self, path: Path) -> list[dict[str, Any]]:
        try:
            with ZipFile(path) as archive:
                shared_strings = self._read_shared_strings(archive)
                sheet_map = self._read_sheet_map(archive)
                units: list[dict[str, Any]] = []
                for sheet_index, sheet_info in enumerate(sheet_map, start=1):
                    sheet_path = sheet_info.get("path")
                    sheet_name = sheet_info.get("name") or f"Sheet {sheet_index}"
                    if not sheet_path:
                        continue
                    rows = self._read_sheet_rows(archive, sheet_path, shared_strings)
                    if not rows:
                        continue
                    content = "\n".join(rows)
                    units.append(
                        {
                            "page_number": sheet_index,
                            "section_title": sheet_name,
                            "citation_text": self._snippet(content),
                            "content": content,
                            "source_type": "spreadsheet",
                        }
                    )
                return units
        except Exception:
            return []

    def _read_shared_strings(self, archive: ZipFile) -> list[str]:
        try:
            with archive.open("xl/sharedStrings.xml") as handle:
                tree = ET.parse(handle)
        except Exception:
            return []

        namespace = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        values: list[str] = []
        for node in tree.findall(".//a:si", namespace):
            texts = [part.text or "" for part in node.findall(".//a:t", namespace)]
            values.append("".join(texts))
        return values

    def _read_sheet_map(self, archive: ZipFile) -> list[dict[str, str]]:
        workbook_ns = {
            "a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
            "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
        }
        rel_ns = {"rel": "http://schemas.openxmlformats.org/package/2006/relationships"}

        try:
            with archive.open("xl/workbook.xml") as handle:
                workbook_tree = ET.parse(handle)
            with archive.open("xl/_rels/workbook.xml.rels") as handle:
                rel_tree = ET.parse(handle)
        except Exception:
            return []

        rel_targets: dict[str, str] = {}
        for rel in rel_tree.findall(".//rel:Relationship", rel_ns):
            rel_id = rel.attrib.get("Id")
            target = rel.attrib.get("Target")
            if rel_id and target:
                rel_targets[rel_id] = target

        sheets: list[dict[str, str]] = []
        for sheet in workbook_tree.findall(".//a:sheets/a:sheet", workbook_ns):
            name = sheet.attrib.get("name") or ""
            rel_id = sheet.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
            target = rel_targets.get(rel_id or "")
            if not target:
                continue
            sheets.append(
                {
                    "name": name,
                    "path": f"xl/{target.lstrip('/')}",
                }
            )
        return sheets

    def _read_sheet_rows(self, archive: ZipFile, sheet_path: str, shared_strings: list[str]) -> list[str]:
        namespace = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        try:
            with archive.open(sheet_path) as handle:
                tree = ET.parse(handle)
        except Exception:
            return []

        rows: list[str] = []
        for row in tree.findall(".//a:sheetData/a:row", namespace):
            row_number = row.attrib.get("r") or ""
            cells: list[str] = []
            for cell in row.findall("a:c", namespace):
                ref = cell.attrib.get("r") or ""
                value = self._read_cell_value(cell, namespace, shared_strings)
                if value:
                    cells.append(f"{ref}={value}" if ref else value)
            if cells:
                prefix = f"Row {row_number}:" if row_number else "Row:"
                rows.append(f"{prefix} {' | '.join(cells)}")
        return rows

    def _read_cell_value(self, cell: ET.Element, namespace: dict[str, str], shared_strings: list[str]) -> str:
        cell_type = cell.attrib.get("t")
        value_node = cell.find("a:v", namespace)
        inline_node = cell.find(".//a:t", namespace)

        if cell_type == "s" and value_node is not None and value_node.text:
            try:
                index = int(value_node.text)
                return shared_strings[index] if 0 <= index < len(shared_strings) else value_node.text
            except Exception:
                return value_node.text.strip()

        if cell_type == "inlineStr" and inline_node is not None and inline_node.text:
            return inline_node.text.strip()

        if value_node is not None and value_node.text:
            return value_node.text.strip()

        if inline_node is not None and inline_node.text:
            return inline_node.text.strip()

        return ""

    def _looks_like_header(self, row: list[str]) -> bool:
        if not row:
            return False
        header_like = 0
        for cell in row:
            compact = re.sub(r"\s+", " ", str(cell)).strip()
            if not compact:
                continue
            if compact.isalpha() or compact.replace("_", "").replace(" ", "").isalpha():
                header_like += 1
        return header_like >= max(1, len(row) // 2)

    def _snippet(self, content: str, limit: int = 260) -> str:
        compact = re.sub(r"\s+", " ", content or "").strip()
        if not compact:
            return ""
        snippet = compact[:limit]
        if len(compact) > limit and " " in snippet:
            snippet = snippet.rsplit(" ", 1)[0].strip()
        return f"{snippet}..." if len(compact) > len(snippet) else snippet
