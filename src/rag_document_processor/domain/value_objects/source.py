from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class FileSource:
    kind: Literal["file"] = "file"
    blob_key: str = ""
    content_type: str | None = None
    original_filename: str | None = None


@dataclass(frozen=True, slots=True)
class UrlSource:
    kind: Literal["url"] = "url"
    url: str = ""


@dataclass(frozen=True, slots=True)
class TextSource:
    kind: Literal["text"] = "text"
    texts: tuple[str, ...] = ()


IngestionSource = FileSource | UrlSource | TextSource


def joined_text_from_source(source: IngestionSource) -> str | None:
    if isinstance(source, TextSource):
        return "\n\n".join(t for t in source.texts if t)
    return None
