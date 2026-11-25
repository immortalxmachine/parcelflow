"""Load named SQL statements from .sql files.

Statements are separated by ``-- name: <id>`` marker comments. This keeps SQL
in real .sql files (easy to read, lint and reuse) while letting Python fetch a
specific statement by name.
"""

from __future__ import annotations

import re
from pathlib import Path

from ..config import PROJECT_ROOT

SQL_DIR = PROJECT_ROOT / "sql"
_NAME_RE = re.compile(r"^--\s*name:\s*(\w+)\s*$", re.MULTILINE)
_COMMENT_RE = re.compile(r"--.*$", re.MULTILINE)


def _strip_comments(sql: str) -> str:
    """Remove ``--`` line comments.

    Bind parameters use the ``:name`` syntax, so a colon inside a descriptive
    comment (e.g. ``-- forecast for (:hub_code)``) would otherwise be parsed as
    a second parameter. Stripping comments avoids that. Safe here because none
    of our SQL contains ``--`` inside a string literal.
    """
    return _COMMENT_RE.sub("", sql)


def load_named_queries(filename: str) -> dict[str, str]:
    """Return ``{name: sql}`` for every ``-- name:`` block in ``sql/<filename>``."""
    text = (SQL_DIR / filename).read_text(encoding="utf-8")
    matches = list(_NAME_RE.finditer(text))
    queries: dict[str, str] = {}
    for i, m in enumerate(matches):
        name = m.group(1)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = _strip_comments(text[start:end]).strip()
        if body:
            queries[name] = body
    return queries


def get_query(filename: str, name: str) -> str:
    """Return a single named query, raising if it is missing."""
    queries = load_named_queries(filename)
    if name not in queries:
        raise KeyError(f"Query {name!r} not found in sql/{filename}")
    return queries[name]
