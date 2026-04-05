"""
FixFlow Core Agent — Multi-step autonomous bug resolution pipeline.

Pipeline:
  Step 1: Issue Understanding     → Structured bug summary
  Step 2: Codebase Mapping        → Ranked list of suspect files
  Step 3: Deep Code Analysis      → Root cause analysis + reasoning chain
  Step 4: Fix Generation          → Corrected file contents
  Step 5: Diff & Explanation      → PR-ready diff + human explanation
"""
import logging
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterator, List, Optional

from backend.config import MAX_FILES_TO_ANALYZE
from backend.llm_client import GLMClient
from backend.github_client import GitHubClient
from backend.code_indexer import (
    build_file_tree_string,
    extract_file_paths_from_llm_response,
    extract_keywords_from_issue,
    format_file_contents_for_prompt,
    rank_files_by_keyword_match,
)
from backend.diff_generator import (
    format_diff_for_display,
    generate_all_diffs,
    get_diff_stats,
    parse_fixed_files_from_llm_response,
)
from backend.prompts import (
    SYSTEM_MESSAGE,
    ISSUE_ANALYSIS_PROMPT,
    FILE_RELEVANCE_PROMPT,
    ROOT_CAUSE_PROMPT,
    FIX_GENERATION_PROMPT,
    FIX_EXPLANATION_PROMPT,
    CONFIDENCE_EVAL_PROMPT,
)

logger = logging.getLogger(__name__)


# ── Result Dataclass ──────────────────────────────────────────────────────────

@dataclass
class AgentResult:
    """Holds all outputs from the FixFlow pipeline."""
    # Inputs
    issue_url: str = ""
    repo_url: str = ""
    issue_data: Dict = field(default_factory=dict)

    # Step outputs
    bug_summary: str = ""
    relevant_files_analysis: str = ""
    suspect_file_paths: List[str] = field(default_factory=list)
    root_cause_analysis: str = ""
    fix_generation_raw: str = ""
    fixed_files: Dict[str, str] = field(default_factory=dict)
    diffs: Dict[str, str] = field(default_factory=dict)
    diff_formatted: str = ""
    fix_explanation: str = ""
    confidence_eval: str = ""

    # Metadata
    step_timings: Dict[str, float] = field(default_factory=dict)
    step_errors: Dict[str, str] = field(default_factory=dict)
    diff_stats: Dict = field(default_factory=dict)
    file_tree: List[Dict] = field(default_factory=list)
    original_file_contents: Dict[str, str] = field(default_factory=dict)


# Status callback type
StatusCallback = Optional[Callable[[str, str, str], None]]
# Args: (step_name, status, message)
# status: "running" | "complete" | "error" | "info"


# ── FixFlow Agent ─────────────────────────────────────────────────────────────

class FixFlowAgent:
    """
    Orchestrates the full bug-resolution pipeline.

    Usage:
        agent = FixFlowAgent(glm_client, github_client)
        result = agent.run(issue_url, repo_url, on_status=callback)
    """

    def __init__(
        self,
        llm_client: GLMClient,
        github_client: GitHubClient,
    ):
        self.llm = llm_client
        self.gh = github_client

    # ── Public entry point ────────────────────────────────────────────────────

    def run(
        self,
        issue_url: str,
        repo_url: str,
        on_status: StatusCallback = None,
        stream_callback: Optional[Callable[[str], None]] = None,
        run_confidence_eval: bool = False,
    ) -> AgentResult:
        """
        Execute the full FixFlow pipeline. Returns an AgentResult.
        
        Args:
            issue_url: Full GitHub issue URL
            repo_url: Full GitHub repo URL
            on_status: Optional callback(step, status, message) for UI updates
            stream_callback: Optional callback(chunk) for streaming LLM output
            run_confidence_eval: Whether to run the optional confidence self-eval
        """
        result = AgentResult(issue_url=issue_url, repo_url=repo_url)
        self._status = on_status or (lambda *a: None)

        try:
            # ── Step 0: Fetch GitHub data ─────────────────────────────────
            self._emit("0_fetch", "running", "Fetching GitHub issue and repository data...")
            t0 = time.time()

            result.issue_data = self._fetch_issue(issue_url)
            result.file_tree = self._fetch_repo_tree(repo_url)
            result.step_timings["0_fetch"] = time.time() - t0
            self._emit("0_fetch", "complete",
                       f"Fetched issue #{result.issue_data['number']} + "
                       f"{len(result.file_tree)} repo files in "
                       f"{result.step_timings['0_fetch']:.1f}s")

            # ── Step 1: Issue Understanding ───────────────────────────────
            self._emit("1_issue", "running", "Analyzing bug report with GLM...")
            t1 = time.time()

            result.bug_summary = self._step1_issue_understanding(
                result.issue_data, stream_callback
            )
            result.step_timings["1_issue"] = time.time() - t1
            self._emit("1_issue", "complete",
                       f"Bug analysis complete in {result.step_timings['1_issue']:.1f}s")

            # ── Step 2: Codebase Mapping ──────────────────────────────────
            self._emit("2_mapping", "running", "Scanning codebase to identify suspect files...")
            t2 = time.time()

            result.relevant_files_analysis, result.suspect_file_paths = \
                self._step2_codebase_mapping(
                    result.bug_summary,
                    result.file_tree,
                    result.issue_data,
                    stream_callback,
                    repo_url=repo_url,
                )
            result.step_timings["2_mapping"] = time.time() - t2
            self._emit("2_mapping", "complete",
                       f"Identified {len(result.suspect_file_paths)} suspect files in "
                       f"{result.step_timings['2_mapping']:.1f}s")

            # ── Step 3: Deep Code Analysis ────────────────────────────────
            self._emit("3_analysis", "running",
                       f"Reading {len(result.suspect_file_paths)} files + performing root cause analysis...")
            t3 = time.time()

            result.original_file_contents = self.gh.fetch_multiple_files(
                repo_url, result.suspect_file_paths
            )
            result.root_cause_analysis = self._step3_deep_analysis(
                result.bug_summary,
                result.original_file_contents,
                stream_callback,
            )
            result.step_timings["3_analysis"] = time.time() - t3
            self._emit("3_analysis", "complete",
                       f"Root cause identified in {result.step_timings['3_analysis']:.1f}s")

            # ── Step 4: Fix Generation ────────────────────────────────────
            self._emit("4_fix", "running", "Generating corrected file contents...")
            t4 = time.time()

            result.fix_generation_raw = self._step4_fix_generation(
                result.root_cause_analysis,
                result.original_file_contents,
                stream_callback,
            )
            result.fixed_files = parse_fixed_files_from_llm_response(
                result.fix_generation_raw,
                result.suspect_file_paths,
            )
            result.step_timings["4_fix"] = time.time() - t4
            self._emit("4_fix", "complete",
                       f"Generated fixes for {len(result.fixed_files)} file(s) in "
                       f"{result.step_timings['4_fix']:.1f}s")

            # ── Step 5: Diff & Explanation ────────────────────────────────
            self._emit("5_diff", "running", "Generating diff and PR explanation...")
            t5 = time.time()

            result.diffs = generate_all_diffs(
                result.original_file_contents, result.fixed_files
            )
            result.diff_formatted = format_diff_for_display(result.diffs)
            result.diff_stats = get_diff_stats(result.diffs)

            result.fix_explanation = self._step5_explanation(
                result.bug_summary,
                result.root_cause_analysis,
                result.diff_formatted,
                stream_callback,
            )
            result.step_timings["5_diff"] = time.time() - t5
            self._emit("5_diff", "complete",
                       f"PR explanation ready in {result.step_timings['5_diff']:.1f}s")

            # ── Optional: Confidence Evaluation ───────────────────────────
            if run_confidence_eval:
                self._emit("6_confidence", "running", "Running self-evaluation...")
                t6 = time.time()
                combined = (
                    f"# Bug Summary\n{result.bug_summary}\n\n"
                    f"# Root Cause\n{result.root_cause_analysis}\n\n"
                    f"# Fix Explanation\n{result.fix_explanation}"
                )
                result.confidence_eval = self._run_confidence_eval(combined)
                result.step_timings["6_confidence"] = time.time() - t6
                self._emit("6_confidence", "complete",
                           f"Confidence eval done in {result.step_timings['6_confidence']:.1f}s")

        except Exception as e:
            logger.exception("FixFlow pipeline failed")
            step = self._current_step or "unknown"
            result.step_errors[step] = str(e)
            self._emit(step, "error", f"❌ Pipeline failed: {e}")
            raise

        return result

    # ── Pipeline Steps ────────────────────────────────────────────────────────

    def _step1_issue_understanding(
        self,
        issue_data: Dict,
        stream_cb: Optional[Callable] = None,
    ) -> str:
        self._current_step = "1_issue"

        comments_text = ""
        for c in issue_data.get("comments", [])[:5]:
            comments_text += f"**@{c['author']}:** {c['body'][:500]}\n\n"
        if not comments_text:
            comments_text = "No comments."

        prompt = ISSUE_ANALYSIS_PROMPT.format(
            title=issue_data.get("title", ""),
            body=issue_data.get("body", ""),
            labels=", ".join(issue_data.get("labels", [])) or "none",
            comments=comments_text,
        )

        messages = [
            {"role": "system", "content": SYSTEM_MESSAGE},
            {"role": "user", "content": prompt},
        ]
        return self._llm_call(messages, stream_cb, temperature=0.2)

    def _step2_codebase_mapping(
        self,
        bug_summary: str,
        file_tree: List[Dict],
        issue_data: Dict,
        stream_cb: Optional[Callable] = None,
        repo_url: str = "",
    ):
        self._current_step = "2_mapping"

        # Pre-filter files by keyword match for large repos
        keywords = extract_keywords_from_issue(issue_data)
        ranked_files = rank_files_by_keyword_match(file_tree, keywords)

        tree_string = build_file_tree_string(ranked_files, max_lines=200)
        repo_name = repo_url.rstrip("/").split("/")[-2:]
        repo_display = "/".join(repo_name) if len(repo_name) == 2 else repo_url

        prompt = FILE_RELEVANCE_PROMPT.format(
            bug_summary=bug_summary,
            file_tree=tree_string,
            repo_name=repo_display,
        )

        messages = [
            {"role": "system", "content": SYSTEM_MESSAGE},
            {"role": "user", "content": prompt},
        ]
        analysis = self._llm_call(messages, stream_cb, temperature=0.2)

        # Extract actual file paths from the response
        paths = extract_file_paths_from_llm_response(analysis)

        # Validate against actual tree (only keep paths that exist)
        known_paths = {f["path"] for f in file_tree}
        valid_paths = [p for p in paths if p in known_paths]

        # If LLM hallucinated paths, fall back to keyword-ranked files
        if not valid_paths:
            logger.warning("LLM returned no valid paths — falling back to keyword ranking")
            valid_paths = [f["path"] for f in ranked_files[:MAX_FILES_TO_ANALYZE]]

        return analysis, valid_paths[:MAX_FILES_TO_ANALYZE]

    def _step3_deep_analysis(
        self,
        bug_summary: str,
        file_contents: Dict[str, str],
        stream_cb: Optional[Callable] = None,
    ) -> str:
        self._current_step = "3_analysis"

        formatted = format_file_contents_for_prompt(file_contents)

        prompt = ROOT_CAUSE_PROMPT.format(
            bug_summary=bug_summary,
            file_contents=formatted,
        )

        messages = [
            {"role": "system", "content": SYSTEM_MESSAGE},
            {"role": "user", "content": prompt},
        ]
        return self._llm_call(messages, stream_cb, temperature=0.15, max_tokens=6000)

    def _step4_fix_generation(
        self,
        root_cause: str,
        file_contents: Dict[str, str],
        stream_cb: Optional[Callable] = None,
    ) -> str:
        self._current_step = "4_fix"

        formatted = format_file_contents_for_prompt(file_contents)

        # Build list of filepaths for the placeholder
        filepaths = ", ".join(file_contents.keys()) or "affected_file.py"

        prompt = FIX_GENERATION_PROMPT.format(
            root_cause=root_cause,
            file_contents=formatted,
            filepath_placeholder=filepaths,
        )

        messages = [
            {"role": "system", "content": SYSTEM_MESSAGE},
            {"role": "user", "content": prompt},
        ]
        return self._llm_call(messages, stream_cb, temperature=0.1, max_tokens=8000)

    def _step5_explanation(
        self,
        bug_summary: str,
        root_cause: str,
        diff_formatted: str,
        stream_cb: Optional[Callable] = None,
    ) -> str:
        self._current_step = "5_diff"

        # Shorten root cause for context
        root_cause_summary = root_cause[:2000] + ("..." if len(root_cause) > 2000 else "")

        prompt = FIX_EXPLANATION_PROMPT.format(
            bug_summary=bug_summary,
            root_cause_summary=root_cause_summary,
            unified_diff=diff_formatted[:3000],
        )

        messages = [
            {"role": "system", "content": SYSTEM_MESSAGE},
            {"role": "user", "content": prompt},
        ]
        return self._llm_call(messages, stream_cb, temperature=0.3)

    def _run_confidence_eval(self, analysis: str) -> str:
        self._current_step = "6_confidence"
        prompt = CONFIDENCE_EVAL_PROMPT.format(analysis=analysis[:4000])
        messages = [
            {"role": "system", "content": SYSTEM_MESSAGE},
            {"role": "user", "content": prompt},
        ]
        return self._llm_call(messages, None, temperature=0.2)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _llm_call(
        self,
        messages: List[Dict],
        stream_cb: Optional[Callable],
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> str:
        """
        Route to streaming or sync call depending on whether a stream callback is provided.
        """
        if stream_cb:
            full_response = ""
            for chunk in self.llm.chat_stream(messages, temperature, max_tokens):
                stream_cb(chunk)
                full_response += chunk
            return full_response
        else:
            return self.llm.chat(messages, temperature, max_tokens)

    def _fetch_issue(self, issue_url: str) -> Dict:
        return self.gh.fetch_issue(issue_url)

    def _fetch_repo_tree(self, repo_url: str) -> List[Dict]:
        return self.gh.fetch_repo_tree(repo_url)

    def _emit(self, step: str, status: str, message: str) -> None:
        self._status(step, status, message)
        logger.info("[%s] %s: %s", step, status.upper(), message)

    _current_step: str = "init"


# ── Wrapper for full report generation ───────────────────────────────────────

def generate_full_report(result: AgentResult) -> str:
    """
    Generate a complete markdown report from an AgentResult.
    Suitable for download/export.
    """
    total_time = sum(result.step_timings.values())
    stats = result.diff_stats

    report = f"""# 🔧 FixFlow Autonomous Bug Resolution Report

**Issue:** [{result.issue_data.get('title', 'Unknown')}]({result.issue_url})  
**Repository:** {result.repo_url}  
**Analysis Date:** {time.strftime('%Y-%m-%d %H:%M UTC')}  
**Total Analysis Time:** {total_time:.1f}s  

---

## 📋 Step 1: Bug Summary

{result.bug_summary}

---

## 🔍 Step 2: Relevant Files Analysis

{result.relevant_files_analysis}

**Files Selected for Analysis:**
{chr(10).join(f'- `{p}`' for p in result.suspect_file_paths)}

---

## 🔬 Step 3: Root Cause Analysis

{result.root_cause_analysis}

---

## 🔧 Step 4: Proposed Fix

**Diff Statistics:**
- Files changed: {stats.get('files_changed', 0)}
- Lines added: +{stats.get('lines_added', 0)}
- Lines removed: -{stats.get('lines_removed', 0)}

{result.diff_formatted}

---

## 📝 Step 5: Fix Explanation (PR Description)

{result.fix_explanation}

---

{f"## 🎯 Confidence Evaluation{chr(10)}{result.confidence_eval}{chr(10)}{chr(10)}---{chr(10)}" if result.confidence_eval else ""}

## ⏱️ Timing Breakdown

| Step | Duration |
|------|----------|
{"".join(f"| {k} | {v:.1f}s |{chr(10)}" for k, v in result.step_timings.items())}

---
*Generated by FixFlow — Autonomous Bug Resolution Agent powered by GLM 5.1*
"""
    return report
