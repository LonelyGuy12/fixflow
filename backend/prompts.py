"""
All LLM prompt templates for the FixFlow agent pipeline.
Each prompt includes a system message + user message pair.
"""

# ── Shared system message ─────────────────────────────────────────────────────
SYSTEM_MESSAGE = (
    "You are FixFlow, an expert senior debugging engineer with 20+ years of "
    "experience in software debugging, code review, and root cause analysis. "
    "You systematically analyze bug reports and codebases to identify root causes "
    "and generate precise, minimal fixes. You ALWAYS show your reasoning step-by-step. "
    "You reference specific files, functions, and line numbers. "
    "Your analysis is thorough, your explanations are clear, and your fixes are "
    "safe and well-reasoned. You never make assumptions without stating them."
)


# ── Step 1: Issue Understanding ───────────────────────────────────────────────
ISSUE_ANALYSIS_PROMPT = """You have been given a GitHub issue to analyze. Your task is to extract a structured bug summary.

## GitHub Issue Details

**Title:** {title}

**Body:**
{body}

**Labels:** {labels}

**Comments (most relevant):**
{comments}

---

## Your Task

Carefully read the issue and extract the following information. Be precise and include exact quotes where relevant.

Respond with a structured markdown document using EXACTLY this format:

### 🐛 Error Message
(The exact error message, exception, or failure description. Quote directly if possible.)

### ✅ Expected Behavior
(What the user/reporter expected to happen)

### ❌ Actual Behavior
(What actually happened — the bug behavior)

### 🔁 Reproduction Steps
(Numbered list of steps to reproduce, if provided)

### 🎯 Affected Components
(Your best guess at which modules, files, functions, or subsystems are affected based on the issue text. List as bullet points.)

### 🔍 Key Technical Clues
(Specific technical details: version numbers, stack traces, config values, edge cases — anything that will help locate the bug)

### 💡 Hypothesis
(Your initial hypothesis about the root cause, stated clearly with reasoning)

Be thorough but concise. If information is not available, write "Not specified" rather than guessing.
"""


# ── Step 2: Codebase Mapping ──────────────────────────────────────────────────
FILE_RELEVANCE_PROMPT = """You are analyzing a codebase to find files relevant to a bug report.

## Bug Summary
{bug_summary}

## Repository File Tree
```
{file_tree}
```

## Repository: {repo_name}

---

## Your Task

Identify the TOP 5-10 most relevant files that are likely related to this bug. 

Think step-by-step:
1. First, consider what the error message tells you about the code path
2. Then look at affected components mentioned in the bug
3. Consider entry points, utilities, and configuration files
4. Look for files matching the error traceback if one was provided

Respond with EXACTLY this format:

### 🗺️ Codebase Analysis

**Repository structure overview:** (2-3 sentences about what kind of codebase this is)

### 📁 Relevant Files (Ranked by Suspicion)

For each file, provide:

**[Rank]. `path/to/file.py`**
- **Relevance score:** X/10
- **Why relevant:** (specific reasoning — what in this file could cause the bug)
- **What to look for:** (specific functions, classes, or patterns to inspect)

---

(Repeat for each file, ranked from most to least suspicious)

### 🔎 Files to Skip
(Brief note on any obviously irrelevant areas of the codebase)
"""


# ── Step 3: Deep Code Analysis ────────────────────────────────────────────────
ROOT_CAUSE_PROMPT = """You are performing a deep code analysis to identify the root cause of a bug.

## Bug Summary
{bug_summary}

## Suspect Files and Content

{file_contents}

---

## Your Task

Trace the execution flow and identify the EXACT root cause of the bug. 

**You MUST:**
- Reference specific file names, function names, and line numbers
- Show your chain-of-thought reasoning
- Trace the call chain from entry point to failure
- Identify the exact line(s) where the bug originates

Respond with EXACTLY this format:

### 🔬 Root Cause Analysis

#### Executive Summary
(1-2 sentences: what is the root cause in plain English)

#### 🧠 Chain-of-Thought Reasoning

**Step 1: Entry Point**
(Where does execution start for this bug? What triggers it?)

**Step 2: Execution Trace**
(Follow the code path step by step. For each step, cite: `filename.py:function_name()` or `filename.py:LineN`)

**Step 3: The Bug**
(The exact location and nature of the bug. Be precise: "In `file.py`, line N, function `foo()` does X when it should do Y because...")

**Step 4: Why This Causes the Reported Behavior**
(Connect the bug to the symptoms described in the issue)

#### 📍 Bug Location
- **File:** `path/to/file.py`
- **Function/Class:** `function_name()` / `ClassName`
- **Line(s):** ~N (approximate)
- **Type:** (e.g., off-by-one error, null check missing, race condition, type mismatch, etc.)

#### ⚠️ Contributing Factors
(Any secondary issues, missed validations, or design problems that make this worse)

#### 🎯 Confidence Level
(High/Medium/Low) — and why

Be thorough. Show your work. Reference specific code.
"""


# ── Step 4: Fix Generation ────────────────────────────────────────────────────
FIX_GENERATION_PROMPT = """You are generating a precise, minimal fix for a confirmed bug.

## Root Cause Analysis
{root_cause}

## Files to Fix

{file_contents}

---

## Your Task

Generate corrected versions of the affected files. 

**Rules for the fix:**
1. Make the MINIMAL change needed — don't refactor unrelated code
2. The fix must directly address the root cause identified above
3. Add a comment explaining WHY the change was made (not just what)
4. Preserve existing code style, formatting, and conventions
5. Consider edge cases your fix must handle

For EACH file that needs changes, provide:

---

### Fix for `{filepath_placeholder}`

**What changed and why:**
(Brief explanation of the change)

**Fixed code:**
```python
(FULL content of the fixed file — complete, not just the changed section)
```

---

If multiple files need changes, repeat the above section for each file.

After all fixes, add:

### ✅ Fix Summary
- Files changed: N
- Nature of fix: (one-liner)
- Risk level: Low/Medium/High (and why)
- Edge cases handled: (bullet list)
"""


# ── Step 5: Fix Explanation ───────────────────────────────────────────────────
FIX_EXPLANATION_PROMPT = """You are writing a human-readable explanation of a code fix for a pull request.

## Original Bug
{bug_summary}

## Root Cause
{root_cause_summary}

## Changes Made (Unified Diff)
```diff
{unified_diff}
```

---

## Your Task

Write a clear, friendly, professional pull request description that a human reviewer can read to quickly understand and verify this fix.

Respond with EXACTLY this format:

### 📝 Pull Request: Fix for [bug title]

#### 🐛 Problem
(What was the bug? 2-3 sentences, non-technical enough for a manager to understand)

#### 🔍 Root Cause
(Technical explanation of WHY this bug existed — 3-5 sentences)

#### 🔧 Solution
(What was changed and how it fixes the problem — reference specific lines/functions)

#### 📋 Changes
(For each changed file, one bullet: "`filename.py` — what changed and why")

#### 🧪 Testing Recommendations
(How a reviewer should verify this fix works — what to test, what edge cases to check)

#### ⚠️ Potential Side Effects
(Any risks or areas that could be affected by this change. If none, say "None identified.")

#### 📚 Related Issues / References
(Any related issues, docs, or context that helps understand this fix)

Write this as if you're a careful, experienced engineer who wants the reviewer to feel confident merging this PR.
"""


# ── Confidence Self-Evaluation (Stretch feature) ──────────────────────────────
CONFIDENCE_EVAL_PROMPT = """Review your own analysis and rate your confidence.

## Analysis Summary
{analysis}

## Self-Evaluation

Rate the following on a scale of 1-10 and explain:

1. **Root Cause Confidence** (1-10): How certain are you the identified root cause is correct?
2. **Fix Correctness** (1-10): How confident are you the proposed fix will resolve the issue?
3. **Fix Safety** (1-10): How safe is the fix (no regressions, no side effects)?
4. **Completeness** (1-10): How complete is your analysis (nothing important missed)?

**Overall Score:** X/10

**Uncertainty Factors:** (What would change your diagnosis?)

**Recommended Next Steps:** (What additional verification would increase confidence?)
"""
