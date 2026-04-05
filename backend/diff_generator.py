"""
Diff generator: creates unified diffs from original vs. fixed file contents.
"""
import difflib
import logging
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)


def generate_unified_diff(
    original_content: str,
    fixed_content: str,
    filename: str,
    context_lines: int = 5,
) -> str:
    """
    Generate a unified diff between two versions of a file.
    Returns the diff as a string.
    """
    original_lines = original_content.splitlines(keepends=True)
    fixed_lines = fixed_content.splitlines(keepends=True)

    diff = difflib.unified_diff(
        original_lines,
        fixed_lines,
        fromfile=f"a/{filename}",
        tofile=f"b/{filename}",
        n=context_lines,
    )
    return "".join(diff)


def generate_all_diffs(
    original_files: Dict[str, str],
    fixed_files: Dict[str, str],
) -> Dict[str, str]:
    """
    Generate unified diffs for all changed files.
    Returns {filepath: diff_string}.
    Only includes files that actually changed.
    """
    diffs = {}

    for filepath, fixed_content in fixed_files.items():
        original = original_files.get(filepath, "")

        # Normalize line endings for comparison
        orig_normalized = original.replace("\r\n", "\n").strip()
        fixed_normalized = fixed_content.replace("\r\n", "\n").strip()

        if orig_normalized == fixed_normalized:
            logger.info("No changes in %s — skipping diff", filepath)
            continue

        diff = generate_unified_diff(
            original,
            fixed_content,
            filepath,
        )

        if diff.strip():
            diffs[filepath] = diff
            changed_lines = _count_changed_lines(diff)
            logger.info(
                "Generated diff for %s: +%d -%d lines",
                filepath, changed_lines[0], changed_lines[1],
            )

    return diffs


def _count_changed_lines(diff: str) -> Tuple[int, int]:
    """Count added and removed lines in a unified diff."""
    added = sum(1 for line in diff.splitlines() if line.startswith("+") and not line.startswith("+++"))
    removed = sum(1 for line in diff.splitlines() if line.startswith("-") and not line.startswith("---"))
    return added, removed


def format_diff_for_display(diffs: Dict[str, str]) -> str:
    """
    Format all diffs into a single markdown code block for display.
    """
    if not diffs:
        return "No changes generated."

    parts = []
    for filepath, diff in diffs.items():
        added, removed = _count_changed_lines(diff)
        parts.append(
            f"### `{filepath}` (+{added} / -{removed} lines)\n"
            f"```diff\n{diff}\n```"
        )

    return "\n\n".join(parts)


def parse_fixed_files_from_llm_response(
    response: str,
    suspect_files: List[str],
) -> Dict[str, str]:
    """
    Parse the LLM's fix generation response to extract {filepath: content}.
    
    The LLM is asked to output:
      ### Fix for `path/to/file.py`
      ```python
      <full file content>
      ```
    
    This function extracts those code blocks.
    """
    import re

    fixed_files = {}

    # Pattern: ### Fix for `filepath` ... ```lang\n<content>\n```
    pattern = re.compile(
        r"Fix for `([^`]+)`.*?```(?:\w+)?\n(.*?)```",
        re.DOTALL | re.IGNORECASE,
    )

    for match in pattern.finditer(response):
        filepath = match.group(1).strip()
        content = match.group(2)

        # Clean up the content
        content = content.rstrip()

        # Verify the filepath looks reasonable
        if "/" in filepath or "." in filepath:
            fixed_files[filepath] = content
            logger.info("Parsed fixed content for: %s (%d chars)", filepath, len(content))

    # Fallback: try to match any filepath from suspect_files
    if not fixed_files:
        logger.warning("Could not parse fix blocks from LLM response — trying fallback")
        for fp in suspect_files:
            # Look for content near the filename mention
            escaped = re.escape(fp)
            m = re.search(
                escaped + r".*?```(?:\w+)?\n(.*?)```",
                response,
                re.DOTALL,
            )
            if m:
                fixed_files[fp] = m.group(1).rstrip()

    return fixed_files


def get_diff_stats(diffs: Dict[str, str]) -> Dict:
    """Return aggregate stats about the diffs."""
    total_added = 0
    total_removed = 0
    for diff in diffs.values():
        a, r = _count_changed_lines(diff)
        total_added += a
        total_removed += r

    return {
        "files_changed": len(diffs),
        "lines_added": total_added,
        "lines_removed": total_removed,
    }
