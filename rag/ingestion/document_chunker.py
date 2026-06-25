from __future__ import annotations

import hashlib
import re
from typing import Any


class DocumentChunker:
    def chunk_document(
        self,
        *,
        document: dict[str, Any],
        content: str,
        max_chunk_chars: int = 900,
        min_chunk_chars: int = 120,
    ) -> list[dict[str, Any]]:
        normalized = re.sub(r"\r", "\n", content or "")
        normalized = re.sub(r"\n{3,}", "\n\n", normalized).strip()
        if not normalized:
            return []

        paragraphs = [block.strip() for block in re.split(r"\n\s*\n", normalized) if block.strip()]
        raw_chunks: list[str] = []
        current = ""

        for paragraph in paragraphs or [normalized]:
            if not current:
                current = paragraph
                continue

            if len(current) + 2 + len(paragraph) <= max_chunk_chars:
                current = f"{current}\n\n{paragraph}"
                continue

            raw_chunks.extend(self._split_long_chunk(current, max_chunk_chars=max_chunk_chars))
            current = paragraph

        if current:
            raw_chunks.extend(self._split_long_chunk(current, max_chunk_chars=max_chunk_chars))

        chunks: list[dict[str, Any]] = []
        page_number = document.get("page_number")
        section_title = document.get("section_title")
        citation_text = document.get("citation_text")
        canonical_content = re.sub(r"\s+", " ", normalized).strip()
        search_start = 0
        for index, chunk_text in enumerate(raw_chunks, start=1):
            compact = re.sub(r"\s+", " ", chunk_text).strip()
            if compact:
                found_at = canonical_content.find(compact, search_start)
                if found_at == -1:
                    found_at = search_start
                start_offset = found_at
                end_offset = found_at + len(compact)
                search_start = end_offset
            else:
                start_offset = search_start
                end_offset = search_start
            if len(compact) < min_chunk_chars and chunks:
                chunks[-1]["content"] = f"{chunks[-1]['content']}\n\n{compact}".strip()
                chunks[-1]["content_snippet"] = self._build_snippet(chunks[-1]["content"])
                chunks[-1]["citation_text"] = chunks[-1].get("citation_text") or chunks[-1]["content_snippet"]
                chunks[-1]["anchor_text"] = chunks[-1].get("anchor_text") or chunks[-1]["citation_text"]
                chunks[-1]["start_offset"] = chunks[-1].get("start_offset", start_offset)
                chunks[-1]["end_offset"] = end_offset
                chunks[-1]["content_hash"] = self._content_hash(chunks[-1]["content"])
                continue

            chunks.append(
                {
                    "document_id": document.get("document_id"),
                    "chunk_id": f"{document.get('document_id', 'doc')}-chunk-{index:03d}",
                    "chunk_index": index,
                    "page_number": page_number,
                    "section_title": section_title,
                    "citation_text": citation_text or self._build_snippet(compact),
                    "anchor_text": self._build_snippet(compact),
                    "start_offset": start_offset,
                    "end_offset": end_offset,
                    "content_hash": self._content_hash(compact),
                    "document_type": document.get("document_type"),
                    "document_category": document.get("document_category"),
                    "related_vendor_id": document.get("related_vendor_id"),
                    "related_employee_id": document.get("related_employee_id"),
                    "related_transaction_id": document.get("related_transaction_id"),
                    "related_contract_id": document.get("related_contract_id"),
                    "related_investigation_id": document.get("related_investigation_id"),
                    "creation_date": document.get("creation_date"),
                    "file_name": document.get("file_name"),
                    "file_path": document.get("file_path"),
                    "source_metadata_file": document.get("source_metadata_file"),
                    "content": compact,
                    "content_snippet": self._build_snippet(compact),
                }
            )

        return chunks

    def _split_long_chunk(self, chunk: str, *, max_chunk_chars: int) -> list[str]:
        compact = re.sub(r"\s+", " ", chunk).strip()
        if len(compact) <= max_chunk_chars:
            return [compact]

        pieces: list[str] = []
        start = 0
        while start < len(compact):
            end = min(start + max_chunk_chars, len(compact))
            piece = compact[start:end].strip()
            if piece:
                pieces.append(piece)
            start = end
        return pieces

    def _build_snippet(self, content: str, limit: int = 260) -> str:
        compact = re.sub(r"\s+", " ", content or "").strip()
        if not compact:
            return ""
        snippet = compact[:limit]
        if len(compact) > limit and " " in snippet:
            snippet = snippet.rsplit(" ", 1)[0].strip()
        return f"{snippet}..." if len(compact) > len(snippet) else snippet

    def _content_hash(self, content: str) -> str:
        normalized = re.sub(r"\s+", " ", content or "").strip().encode("utf-8", errors="ignore")
        return hashlib.sha256(normalized).hexdigest()
