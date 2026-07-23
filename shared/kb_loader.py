"""
Knowledge base loader.

All agents use this module to read KB content. Centralizing it gives us:
    - Caching (read each file once per process)
    - Consistent path resolution
    - One place to add features (e.g. metadata filtering, status checks)
    - Easy mocking in tests

The KB lives in markdown files under a root directory (default: ./kb).
Files have YAML frontmatter with metadata; this loader exposes both the
raw content and the parsed metadata.

kb/01_Live/ is special: its files are generated from a Google Sheet by
shared/kb_sync.py and always reflect current schedules/events. Use
load_live_context() to include them.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# ============================================================================
# Paths
# ============================================================================

DEFAULT_KB_PATH = Path(os.environ.get("HSO_KB_PATH", "./kb"))


def get_kb_root() -> Path:
    """Resolve the KB root path. Override via HSO_KB_PATH env var."""
    return Path(os.environ.get("HSO_KB_PATH", str(DEFAULT_KB_PATH)))


# ============================================================================
# Data types
# ============================================================================

@dataclass
class KBDocument:
    """A parsed KB document — frontmatter + body."""
    relative_path: str
    metadata: dict = field(default_factory=dict)
    body: str = ""
    raw: str = ""  # full original content including frontmatter

    @property
    def status(self) -> str:
        return self.metadata.get("status", "draft")

    @property
    def is_approved(self) -> bool:
        return self.status == "approved"

    @property
    def title(self) -> str:
        return self.metadata.get("title", self.relative_path)


# ============================================================================
# Frontmatter parsing
# ============================================================================

_FRONTMATTER_RE = re.compile(
    r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL
)


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """
    Extract YAML frontmatter from a markdown document.

    We do a light hand-rolled parse to avoid a YAML dependency for the simple
    flat metadata we use. Only handles `key: value` pairs and `key: [a, b]`
    lists. If you need full YAML, swap in pyyaml here.
    """
    match = _FRONTMATTER_RE.match(content)
    if not match:
        return {}, content

    fm_text, body = match.group(1), match.group(2)
    metadata: dict = {}
    for line in fm_text.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        # Lists: [a, b, c]
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1]
            metadata[key] = [item.strip() for item in inner.split(",") if item.strip()]
        else:
            metadata[key] = value
    return metadata, body.lstrip("\n")


# ============================================================================
# Caching
# ============================================================================

_cache: dict[str, KBDocument] = {}


def clear_cache() -> None:
    """Reset the in-memory KB cache. Use after KB updates."""
    _cache.clear()


# ============================================================================
# Loading
# ============================================================================

def load_document(
    relative_path: str,
    *,
    require_approved: bool = False,
    use_cache: bool = True,
) -> Optional[KBDocument]:
    """
    Load a single KB document by path relative to the KB root.

    Returns None if the file doesn't exist. Raises ValueError if
    require_approved is True and the document's status is not "approved".
    """
    if use_cache and relative_path in _cache:
        doc = _cache[relative_path]
    else:
        full_path = get_kb_root() / relative_path
        if not full_path.exists():
            logger.warning("KB file not found: %s", full_path)
            return None
        raw = full_path.read_text(encoding="utf-8")
        metadata, body = parse_frontmatter(raw)
        doc = KBDocument(
            relative_path=relative_path,
            metadata=metadata,
            body=body,
            raw=raw,
        )
        if use_cache:
            _cache[relative_path] = doc

    if require_approved and not doc.is_approved:
        raise ValueError(
            f"KB document {relative_path} has status={doc.status!r} "
            f"but require_approved=True"
        )
    return doc


def load_many(
    relative_paths: list[str],
    *,
    require_approved: bool = False,
    skip_missing: bool = True,
) -> list[KBDocument]:
    """Load several KB documents. Missing files are skipped by default."""
    docs = []
    for path in relative_paths:
        try:
            doc = load_document(path, require_approved=require_approved)
        except ValueError:
            logger.warning("Skipping non-approved KB document: %s", path)
            continue
        if doc:
            docs.append(doc)
        elif not skip_missing:
            raise FileNotFoundError(path)
    return docs


def assemble_context(
    docs: list[KBDocument],
    *,
    include_headers: bool = True,
) -> str:
    """
    Concatenate documents into a single context string for an LLM prompt.

    Each document is preceded by a header showing its path so the model
    knows which document a given chunk came from.
    """
    sections = []
    for doc in docs:
        if include_headers:
            sections.append(f"# === {doc.relative_path} ===\n\n{doc.body}")
        else:
            sections.append(doc.body)
    return "\n\n".join(sections)


# ============================================================================
# Convenience: load core docs (always-loaded for every agent)
# ============================================================================

CORE_DOCS = [
    "00_Core/voice-and-tone.md",
    "00_Core/about-hopespot.md",
    "00_Core/escalation-rules.md",
    "00_Core/do-not-say.md",
]


def load_core_context(*, require_approved: bool = False) -> str:
    """Load the four foundational documents and return as a single string."""
    docs = load_many(CORE_DOCS, require_approved=require_approved)
    return assemble_context(docs)


def load_category_context(
    category: str,
    category_to_files: dict,
    *,
    require_approved: bool = False,
) -> str:
    """
    Load the documents specified for a given category.

    `category_to_files` is a dict mapping category names to lists of paths,
    typically defined per-agent.
    """
    paths = category_to_files.get(category, [])
    docs = load_many(paths, require_approved=require_approved)
    return assemble_context(docs)


# ============================================================================
# Live KB — sheet-synced current schedules/events (see shared/kb_sync.py)
# ============================================================================

LIVE_SUBDIR = "01_Live"


def load_live_context(subdir: str = LIVE_SUBDIR) -> str:
    """Load every document in kb/01_Live/ (sheet-synced current info).
    Returns "" if the folder doesn't exist or is empty."""
    live_dir = get_kb_root() / subdir
    if not live_dir.exists():
        return ""
    docs = []
    for path in sorted(live_dir.glob("*.md")):
        doc = load_document(f"{subdir}/{path.name}")
        if doc:
            docs.append(doc)
    return assemble_context(docs)
