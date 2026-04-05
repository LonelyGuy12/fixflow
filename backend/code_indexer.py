"""
Code indexer: parses repo structure and helps identify the most
relevant files for a given bug. No vector DB — pure in-memory.
"""
import logging
import re
from typing import List, Dict, Optional

from backend.config import CODE_EXTENSIONS, MAX_FILES_TO_ANALYZE

logger = logging.getLogger(__name__)


def build_file_tree_string(files: List[Dict], max_lines: int = 300) -> str:
    """
    Convert a flat list of file dicts into an indented tree string
    suitable for LLM context.
    """
    paths = sorted(f["path"] for f in files)

    lines = []
    prev_parts: List[str] = []

    for path in paths:
        parts = path.split("/")
        # Find the common prefix depth
        common = 0
        for i, (a, b) in enumerate(zip(prev_parts, parts[:-1])):
            if a == b:
                common = i + 1
            else:
                break

        # Print changed directory levels
        for depth in range(common, len(parts) - 1):
            indent = "  " * depth
            lines.append(f"{indent}📁 {parts[depth]}/")

        indent = "  " * (len(parts) - 1)
        lines.append(f"{indent}📄 {parts[-1]}")
        prev_parts = parts[:-1]

        if len(lines) >= max_lines:
            lines.append(f"... and more files ({len(paths) - paths.index(path) - 1} remaining)")
            break

    return "\n".join(lines)


def format_file_contents_for_prompt(
    file_contents: Dict[str, str],
    max_chars_per_file: int = 3000,
    max_total_chars: int = 20000,
) -> str:
    """
    Format multiple file contents into a single block for LLM context.
    Truncates long files and respects a total character budget.
    """
    sections = []
    total_chars = 0

    for path, content in file_contents.items():
        if total_chars >= max_total_chars:
            sections.append(f"[Remaining files omitted due to context limit]")
            break

        # Add line numbers for reference
        lines = content.splitlines()
        numbered = "\n".join(
            f"{i+1:4d} | {line}" for i, line in enumerate(lines)
        )

        if len(numbered) > max_chars_per_file:
            truncated = numbered[:max_chars_per_file]
            # Find a clean line boundary
            last_newline = truncated.rfind("\n")
            if last_newline > 0:
                truncated = truncated[:last_newline]
            numbered = truncated + f"\n\n... [TRUNCATED — {len(lines)} total lines, showing first {truncated.count(chr(10))} lines]"

        section = f"### File: `{path}`\n```\n{numbered}\n```"
        sections.append(section)
        total_chars += len(section)

    return "\n\n".join(sections)


def extract_file_paths_from_llm_response(response: str) -> List[str]:
    """
    Parse file paths from the LLM's relevance ranking response.
    Looks for backtick-quoted paths like `path/to/file.py` or **`path/to/file.py`**.
    """
    # Match paths in backticks
    patterns = [
        r"`([a-zA-Z0-9_\-./]+\.[a-zA-Z]+)`",   # `path/to/file.ext`
        r"\*\*`([a-zA-Z0-9_\-./]+\.[a-zA-Z]+)`\*\*",  # **`path`**
    ]
    paths = []
    for pattern in patterns:
        found = re.findall(pattern, response)
        for p in found:
            if p not in paths and "/" in p or "." in p:
                paths.append(p)

    return paths[:MAX_FILES_TO_ANALYZE]


def rank_files_by_keyword_match(
    files: List[Dict],
    keywords: List[str],
) -> List[Dict]:
    """
    Quick keyword-based pre-filter before sending the full list to the LLM.
    Returns files sorted by keyword match count (descending).
    """
    scored = []
    lc_keywords = [kw.lower() for kw in keywords]

    for f in files:
        path_lower = f["path"].lower()
        score = sum(kw in path_lower for kw in lc_keywords)
        scored.append((score, f))

    scored.sort(key=lambda x: -x[0])
    return [f for _, f in scored]


def extract_keywords_from_issue(issue_data: Dict) -> List[str]:
    """
    Extract potential code-relevant keywords from an issue dict.
    Used for pre-filtering before sending to LLM.
    """
    text = " ".join([
        issue_data.get("title", ""),
        issue_data.get("body", ""),
    ]).lower()

    # Extract likely identifiers: CamelCase, snake_case, module names
    words = re.findall(r"\b[a-zA-Z][a-zA-Z0-9_]{2,}\b", text)
    # Deduplicate while preserving order
    seen = set()
    keywords = []
    for w in words:
        lw = w.lower()
        if lw not in seen and len(lw) > 3:
            seen.add(lw)
            keywords.append(lw)

    return keywords[:30]


def get_file_summary(path: str, content: str, max_chars: int = 500) -> str:
    """
    Generate a quick summary of a file (first N chars of meaningful content).
    Skips blank lines and comment-only lines at the top.
    """
    lines = content.splitlines()
    meaningful = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and not stripped.startswith("//"):
            meaningful.append(line)
        if len("\n".join(meaningful)) > max_chars:
            break
    preview = "\n".join(meaningful)[:max_chars]
    return preview
