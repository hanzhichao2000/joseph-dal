"""Revision record in the #893 shape: capability, version, source, revision id, content digest,
receipt plus an immutable ordered file list with per-file digests. JSON round-trips byte-identically."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import PurePosixPath
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RevisionFile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    path: str
    digest: str
    size: int = Field(ge=0)

    @field_validator("path")
    @classmethod
    def _relative(cls, v: str) -> str:
        p = PurePosixPath(v)
        if p.is_absolute() or ".." in p.parts or v.startswith("~"):
            raise ValueError(f"revision file path must be relative and contained: {v!r}")
        return p.as_posix()


class RevisionWindow(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    start: date
    end: date


class RevisionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    capability_id: str
    schema_version: str
    source: str
    revision_id: str
    content_digest: str
    files: tuple[RevisionFile, ...]
    window: RevisionWindow | None = None

    @staticmethod
    def compute_content_digest(
        capability_id: str,
        schema_version: str,
        source: str,
        files: tuple[RevisionFile, ...] | list[RevisionFile],
    ) -> str:
        payload = json.dumps(
            {
                "capability_id": capability_id,
                "schema_version": schema_version,
                "source": source,
                "files": [{"path": f.path, "digest": f.digest, "size": f.size} for f in files],
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def to_json(self) -> str:
        return json.dumps(
            self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )

    @classmethod
    def from_json(cls, raw: str) -> RevisionRecord:
        data: Any = json.loads(raw)
        return cls.model_validate(data)
