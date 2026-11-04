"""Normalized finding model shared by every importer, the policy engine and the agent."""

from __future__ import annotations

import hashlib
import json
import re
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")


class Severity(str, Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"
    info = "info"

    @property
    def rank(self) -> int:
        return ["info", "low", "medium", "high", "critical"].index(self.value)


class Category(str, Enum):
    sast = "sast"  # first-party code
    sca = "sca"  # vulnerable dependency
    secrets = "secrets"
    iac = "iac"
    container = "container"
    other = "other"


class Location(BaseModel):
    path: str
    start_line: int | None = None
    end_line: int | None = None
    snippet: str | None = None


class Package(BaseModel):
    name: str
    version: str | None = None
    ecosystem: str | None = None  # npm, pypi, go, maven, ...
    fixed_versions: list[str] = Field(default_factory=list)
    manifest: str | None = None  # e.g. package.json


class Finding(BaseModel):
    """One security result, independent of the tool that produced it.

    Everything here except ``id`` is copied from scanner output and must be
    treated as untrusted data when it is shown to a model.
    """

    id: str = ""
    tool: str
    rule_id: str
    title: str
    message: str = ""
    severity: Severity = Severity.medium
    category: Category = Category.sast
    cwe: list[str] = Field(default_factory=list)
    advisories: list[str] = Field(default_factory=list)  # CVE / GHSA / tool ids
    location: Location | None = None
    package: Package | None = None
    help_uri: str | None = None
    source_format: str = "unknown"
    raw: dict[str, Any] = Field(default_factory=dict, repr=False)

    def model_post_init(self, __context: Any) -> None:
        # Ids become directory and branch names, and reports are untrusted: only allow a safe charset.
        if not self.id or not SAFE_ID.fullmatch(self.id):
            self.id = self.fingerprint()

    def fingerprint(self) -> str:
        """Stable id: same tool + rule + place (or package) -> same id across runs."""
        place: Any
        if self.package:
            place = [self.package.name, self.package.version, sorted(self.advisories)]
        elif self.location:
            place = [self.location.path, self.location.start_line]
        else:
            place = [self.title]
        blob = json.dumps([self.tool.lower(), self.rule_id, place], sort_keys=True)
        return "of-" + hashlib.sha256(blob.encode()).hexdigest()[:12]

    def short(self) -> str:
        where = ""
        if self.location:
            where = self.location.path + (f":{self.location.start_line}" if self.location.start_line else "")
        elif self.package:
            where = f"{self.package.name}@{self.package.version or '?'}"
        return f"[{self.severity.value}] {self.rule_id} {where}".strip()


SEVERITY_WORDS = {
    "critical": Severity.critical,
    "high": Severity.high,
    "error": Severity.high,
    "medium": Severity.medium,
    "moderate": Severity.medium,
    "warning": Severity.medium,
    "low": Severity.low,
    "note": Severity.low,
    "info": Severity.info,
    "informational": Severity.info,
    "none": Severity.info,
    "unknown": Severity.medium,
}


def severity_from(value: Any = None, score: Any = None) -> Severity:
    """Map a CVSS-like score or a tool's severity word onto Severity."""
    if score not in (None, ""):
        try:
            s = float(score)
        except (TypeError, ValueError):
            s = -1
        if s >= 9:
            return Severity.critical
        if s >= 7:
            return Severity.high
        if s >= 4:
            return Severity.medium
        if s > 0:
            return Severity.low
        if s == 0:
            return Severity.info
    return SEVERITY_WORDS.get(str(value or "unknown").strip().lower(), Severity.medium)
