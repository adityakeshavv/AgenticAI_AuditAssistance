from __future__ import annotations

import base64
import email
import re
import zlib
from collections.abc import Iterable
from email import policy
from pathlib import Path
from typing import Any
from zipfile import ZipFile
from xml.etree import ElementTree as ET

from app.services.document_intelligence_service import DocumentIntelligenceService


class DocumentProcessingService:
    def __init__(self) -> None:
        self.document_intelligence_service = DocumentIntelligenceService()

    def process_document(
        self,
        *,
        file_path: str,
        file_name: str,
        document_type: str,
        document_category: str,
    ) -> dict[str, Any]:
        path = Path(file_path)
        raw_text = self._extract_text(path)
        content_snippet = self._first_meaningful_snippet(raw_text)
        document_payload = {
            "document_type": document_type,
            "document_category": document_category,
            "file_name": file_name,
            "file_path": file_path,
            "content_snippet": content_snippet,
            "reason_selected": f"Uploaded document processed from {file_name}.",
        }
        intelligence = self.document_intelligence_service.classify(document_payload)
        signals = list(intelligence.get("signals", []))
        risk_contribution = list(intelligence.get("risk_contribution", []))

        processing_summary = self._build_processing_summary(
            file_name=file_name,
            document_type=document_type,
            document_category=document_category,
            content_snippet=content_snippet,
            signals=signals,
        )

        return {
            "supported": path.exists() and path.is_file(),
            "file_type": path.suffix.lower().lstrip(".") or document_type,
            "content_snippet": content_snippet,
            "content_length": len(raw_text),
            "document_intelligence": intelligence,
            "processing_summary": processing_summary,
            "signals": signals,
            "risk_contribution": risk_contribution,
        }

    def _extract_text(self, path: Path) -> str:
        if not path.exists() or not path.is_file():
            return ""

        suffix = path.suffix.lower()
        try:
            if suffix in {".txt", ".md", ".log", ".csv"}:
                return path.read_text(encoding="utf-8", errors="ignore")
            if suffix == ".eml":
                return self._read_eml(path)
            if suffix == ".docx":
                return self._read_docx(path)
            if suffix == ".pdf":
                return self._read_pdf(path)
        except Exception:
            return ""
        return ""

    def _read_eml(self, path: Path) -> str:
        with path.open("rb") as handle:
            message = email.message_from_binary_file(handle, policy=policy.default)

        fragments: list[str] = []
        if message.is_multipart():
            for part in message.walk():
                if part.get_content_type() == "text/plain":
                    payload = part.get_content()
                    if isinstance(payload, str):
                        fragments.append(payload)
        else:
            payload = message.get_content()
            if isinstance(payload, str):
                fragments.append(payload)
        return "\n".join(fragments)

    def _read_docx(self, path: Path) -> str:
        namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        with ZipFile(path) as archive:
            with archive.open("word/document.xml") as document_xml:
                tree = ET.parse(document_xml)

        paragraphs: list[str] = []
        for paragraph in tree.findall(".//w:p", namespace):
            texts = [node.text or "" for node in paragraph.findall(".//w:t", namespace)]
            text = "".join(texts).strip()
            if text:
                paragraphs.append(text)
        return "\n".join(paragraphs)

    def _read_pdf(self, path: Path) -> str:
        try:
            data = path.read_bytes()
        except Exception:
            return ""

        offset = 0
        while True:
            stream_start = data.find(b"stream", offset)
            if stream_start == -1:
                break

            content_start = data.find(b"\n", stream_start)
            if content_start == -1:
                break
            content_start += 1
            endstream = data.find(b"endstream", content_start)
            if endstream == -1:
                break

            chunk = data[content_start:endstream].strip(b"\r\n")
            decoded = self._decode_pdf_stream(chunk)
            if decoded:
                text = self._extract_text_from_pdf_stream(decoded)
                paragraph = self._first_meaningful_paragraph(text)
                if paragraph:
                    return paragraph

            offset = endstream + len(b"endstream")

        fallback_text = self._extract_text_from_pdf_bytes(data)
        return self._first_meaningful_paragraph(fallback_text)

    def _decode_pdf_stream(self, chunk: bytes) -> bytes:
        candidates = [chunk, chunk.strip(b"\r\n")]
        for candidate in candidates:
            try:
                return zlib.decompress(candidate)
            except Exception:
                pass
            try:
                ascii85_decoded = base64.a85decode(candidate, adobe=True)
                return zlib.decompress(ascii85_decoded)
            except Exception:
                pass
        return chunk

    def _extract_text_from_pdf_stream(self, stream_data: bytes) -> str:
        try:
            text = stream_data.decode("latin-1", errors="ignore")
        except Exception:
            return ""

        fragments: list[str] = []
        fragments.extend(self._extract_pdf_literal_strings(text))
        fragments.extend(self._extract_pdf_hex_strings(text))
        if fragments:
            return "\n".join(fragments)
        return self._extract_text_from_pdf_bytes(stream_data)

    def _extract_text_from_pdf_bytes(self, data: bytes) -> str:
        try:
            text = data.decode("latin-1", errors="ignore")
        except Exception:
            return ""

        fragments: list[str] = []
        fragments.extend(self._extract_pdf_literal_strings(text))
        fragments.extend(self._extract_pdf_hex_strings(text))
        return "\n".join(fragments)

    def _extract_pdf_literal_strings(self, text: str) -> list[str]:
        strings = re.findall(r"\((.*?)\)\s*T[Jj]", text, flags=re.DOTALL)
        cleaned: list[str] = []
        for value in strings:
            candidate = re.sub(r"\\([nrtbf()\\])", " ", value)
            candidate = re.sub(r"\\[0-7]{1,3}", " ", candidate)
            candidate = re.sub(r"\s+", " ", candidate).strip()
            if candidate:
                cleaned.append(candidate)

        array_strings = re.findall(r"\[(.*?)\]\s*TJ", text, flags=re.DOTALL)
        for array in array_strings:
            cleaned.extend(self._extract_pdf_literal_strings(array))
            cleaned.extend(self._extract_pdf_hex_strings(array))
        return cleaned

    def _extract_pdf_hex_strings(self, text: str) -> list[str]:
        hex_values = re.findall(r"<([0-9A-Fa-f\s]+)>\s*T[Jj]", text, flags=re.DOTALL)
        cleaned: list[str] = []
        for value in hex_values:
            compact = re.sub(r"\s+", "", value)
            if not compact:
                continue
            try:
                if len(compact) % 2 == 1:
                    compact = compact[:-1]
                decoded = bytes.fromhex(compact).decode("utf-16-be", errors="ignore").strip()
                if not decoded:
                    decoded = bytes.fromhex(compact).decode("latin-1", errors="ignore").strip()
            except Exception:
                decoded = ""
            if decoded:
                cleaned.append(decoded)
        return cleaned

    def _first_meaningful_paragraph(self, content: str) -> str:
        normalized = re.sub(r"\r", "\n", content)
        normalized = re.sub(r"\n{3,}", "\n\n", normalized)
        blocks = [block.strip() for block in re.split(r"\n\s*\n", normalized) if block.strip()]
        for block in blocks:
            compact = re.sub(r"\s+", " ", block).strip()
            if len(compact) >= 40:
                return compact[:300]
        compact = re.sub(r"\s+", " ", normalized).strip()
        return compact[:300]

    def _first_meaningful_snippet(self, content: str) -> str:
        compact = re.sub(r"\s+", " ", content).strip()
        if not compact:
            return ""
        return compact[:240] + ("..." if len(compact) > 240 else "")

    def _build_processing_summary(
        self,
        *,
        file_name: str,
        document_type: str,
        document_category: str,
        content_snippet: str,
        signals: Iterable[str],
    ) -> str:
        signal_text = ", ".join(list(signals)[:3]) if signals else "no risk signals detected"
        snippet_text = content_snippet or "no readable snippet extracted"
        return (
            f"Processed {file_name} as {document_type.upper()} in category {document_category}. "
            f"Document intelligence identified {signal_text}. "
            f"Snippet: {snippet_text}"
        )
