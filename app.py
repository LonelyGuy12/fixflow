"""
FixFlow — Streamlit Frontend
Autonomous Bug Resolution Agent powered by GLM 5.1 (Z.ai)
"""
import time
import logging
import threading
from typing import Optional

import streamlit as st

from backend.agent import AgentResult, FixFlowAgent, generate_full_report
from backend.config import GLM_MODEL, GLM_BASE_URL
from backend.github_client import GitHubClient
from backend.llm_client import GLMClient

# ── Logging Setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("fixflow.app")


# ── Page Config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="FixFlow — Autonomous Bug Resolution Agent",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

/* ── Root & Base ─────────── */
:root {
    --bg-primary: #0a0b0f;
    --bg-secondary: #12141a;
    --bg-card: #1a1c24;
    --bg-card-hover: #1e2028;
    --accent-primary: #6c63ff;
    --accent-secondary: #a78bfa;
    --accent-green: #10b981;
    --accent-red: #ef4444;
    --accent-yellow: #f59e0b;
    --accent-blue: #3b82f6;
    --text-primary: #f0f0ff;
    --text-secondary: #9ca3af;
    --text-muted: #6b7280;
    --border: #2a2c36;
    --border-bright: #3a3c48;
    --shadow-glow: 0 0 40px rgba(108, 99, 255, 0.15);
    --radius: 12px;
    --radius-sm: 8px;
}

/* Global font */
html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    color: var(--text-primary);
}

/* Dark background */
.stApp {
    background: var(--bg-primary);
    background-image: radial-gradient(ellipse at 20% 10%, rgba(108, 99, 255, 0.08) 0%, transparent 60%),
                      radial-gradient(ellipse at 80% 90%, rgba(167, 139, 250, 0.05) 0%, transparent 60%);
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background: var(--bg-secondary) !important;
    border-right: 1px solid var(--border) !important;
}

section[data-testid="stSidebar"] > div {
    padding: 1.5rem 1.2rem;
}

/* ── Logo / Header ───────── */
.fixflow-header {
    text-align: center;
    padding: 2rem 1rem 1rem;
    margin-bottom: 1.5rem;
}

.fixflow-logo {
    font-size: 3.5rem;
    margin-bottom: 0.5rem;
    display: block;
    filter: drop-shadow(0 0 20px rgba(108, 99, 255, 0.5));
}

.fixflow-title {
    font-size: 2.2rem;
    font-weight: 800;
    background: linear-gradient(135deg, #6c63ff 0%, #a78bfa 50%, #60a5fa 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    letter-spacing: -0.02em;
    line-height: 1.2;
    margin-bottom: 0.4rem;
}

.fixflow-subtitle {
    color: var(--text-secondary);
    font-size: 1rem;
    font-weight: 400;
    margin-bottom: 1rem;
}

.powered-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    background: linear-gradient(135deg, rgba(108, 99, 255, 0.15), rgba(167, 139, 250, 0.1));
    border: 1px solid rgba(108, 99, 255, 0.3);
    border-radius: 100px;
    padding: 0.3rem 0.9rem;
    font-size: 0.78rem;
    font-weight: 600;
    color: var(--accent-secondary);
    letter-spacing: 0.04em;
    text-transform: uppercase;
}

/* ── Cards ───────────────── */
.pipeline-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 1.5rem;
    margin-bottom: 1rem;
    transition: border-color 0.3s ease, box-shadow 0.3s ease;
    position: relative;
    overflow: hidden;
}

.pipeline-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg, var(--accent-primary), var(--accent-secondary));
    opacity: 0;
    transition: opacity 0.3s ease;
}

.pipeline-card:hover::before { opacity: 1; }
.pipeline-card:hover {
    border-color: var(--border-bright);
    box-shadow: var(--shadow-glow);
}

/* ── Step Status Indicators ─ */
.step-indicator {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.8rem 1rem;
    border-radius: var(--radius-sm);
    margin-bottom: 0.5rem;
    font-size: 0.9rem;
    font-weight: 500;
    border: 1px solid transparent;
    transition: all 0.3s ease;
}

.step-idle {
    background: rgba(107, 114, 128, 0.08);
    border-color: rgba(107, 114, 128, 0.15);
    color: var(--text-muted);
}

.step-running {
    background: rgba(59, 130, 246, 0.1);
    border-color: rgba(59, 130, 246, 0.3);
    color: #60a5fa;
    animation: pulse-blue 2s infinite;
}

.step-complete {
    background: rgba(16, 185, 129, 0.08);
    border-color: rgba(16, 185, 129, 0.25);
    color: var(--accent-green);
}

.step-error {
    background: rgba(239, 68, 68, 0.08);
    border-color: rgba(239, 68, 68, 0.25);
    color: var(--accent-red);
}

@keyframes pulse-blue {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.7; }
}

.step-icon { font-size: 1.1rem; }
.step-time { margin-left: auto; font-size: 0.75rem; color: var(--text-muted); font-family: 'JetBrains Mono', monospace; }

/* ── Input Fields ────────── */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius-sm) !important;
    color: var(--text-primary) !important;
    font-family: 'Inter', sans-serif !important;
    transition: border-color 0.2s !important;
}

.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-color: var(--accent-primary) !important;
    box-shadow: 0 0 0 3px rgba(108, 99, 255, 0.12) !important;
}

/* ── Analyze Button ──────── */
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #6c63ff, #a78bfa) !important;
    border: none !important;
    border-radius: 10px !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 700 !important;
    font-size: 1rem !important;
    padding: 0.7rem 2rem !important;
    letter-spacing: 0.02em !important;
    transition: all 0.3s ease !important;
    box-shadow: 0 4px 24px rgba(108, 99, 255, 0.35) !important;
    color: white !important;
}

.stButton > button[kind="primary"]:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 32px rgba(108, 99, 255, 0.5) !important;
}

.stButton > button[kind="primary"]:active {
    transform: translateY(0) !important;
}

/* Secondary buttons */
.stButton > button[kind="secondary"] {
    background: var(--bg-card) !important;
    border: 1px solid var(--border-bright) !important;
    border-radius: var(--radius-sm) !important;
    color: var(--text-secondary) !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 500 !important;
}

/* ── Expander ────────────── */
.streamlit-expanderHeader {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius-sm) !important;
    color: var(--text-primary) !important;
    font-weight: 600 !important;
    transition: border-color 0.2s !important;
}

.streamlit-expanderHeader:hover {
    border-color: var(--accent-primary) !important;
}

.streamlit-expanderContent {
    background: var(--bg-secondary) !important;
    border: 1px solid var(--border) !important;
    border-top: none !important;
    border-radius: 0 0 var(--radius-sm) var(--radius-sm) !important;
}

/* Code blocks */
.stCodeBlock pre, code {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.85rem !important;
}

/* ── Metrics ─────────────── */
.stat-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    padding: 1rem;
    text-align: center;
}

.stat-value {
    font-size: 1.8rem;
    font-weight: 800;
    background: linear-gradient(135deg, #6c63ff, #a78bfa);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    line-height: 1;
}

.stat-label {
    font-size: 0.75rem;
    color: var(--text-muted);
    margin-top: 0.3rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
}

/* ── Dividers ────────────── */
hr {
    border: none !important;
    border-top: 1px solid var(--border) !important;
    margin: 1.5rem 0 !important;
}

/* ── Sidebar specific ────── */
.sidebar-section-title {
    font-size: 0.7rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--text-muted);
    margin: 1.2rem 0 0.5rem;
}

.sidebar-logo {
    font-size: 1.5rem;
    font-weight: 800;
    background: linear-gradient(135deg, #6c63ff, #a78bfa);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin-bottom: 0.2rem;
}

/* ── Stream output box ───── */
.stream-box {
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    padding: 1rem;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.82rem;
    line-height: 1.6;
    color: #d1fae5;
    max-height: 300px;
    overflow-y: auto;
    white-space: pre-wrap;
    word-break: break-word;
}

/* ── Alerts ──────────────── */
.stAlert {
    border-radius: var(--radius-sm) !important;
}

/* Toggle/checkbox */
.stCheckbox > label {
    color: var(--text-secondary) !important;
    font-size: 0.9rem !important;
}

/* Scrollbar */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: var(--bg-secondary); }
::-webkit-scrollbar-thumb { background: var(--border-bright); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--accent-primary); }

/* Selectbox */
.stSelectbox > div > div {
    background: var(--bg-card) !important;
    border-color: var(--border) !important;
    color: var(--text-primary) !important;
}
</style>
""", unsafe_allow_html=True)


# ── Session State Init ────────────────────────────────────────────────────────
def init_session():
    defaults = {
        "result": None,
        "running": False,
        "step_statuses": {},
        "step_messages": {},
        "stream_buffer": "",
        "error": None,
        "glm_api_key": "",
        "github_token": "",
        "model": GLM_MODEL,
        "run_confidence": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_session()


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div class="sidebar-logo">🔧 FixFlow</div>', unsafe_allow_html=True)
    st.markdown('<div style="color: #6b7280; font-size: 0.8rem; margin-bottom: 1.5rem;">Autonomous Bug Resolution Agent</div>', unsafe_allow_html=True)

    st.markdown('<div class="sidebar-section-title">🔑 API Configuration</div>', unsafe_allow_html=True)

    glm_key = st.text_input(
        "GLM API Key (Z.ai)",
        value=st.session_state.glm_api_key,
        type="password",
        placeholder="Enter your Z.ai GLM API key...",
        help="Get your key at https://open.bigmodel.cn/",
        key="glm_key_input",
    )
    if glm_key:
        st.session_state.glm_api_key = glm_key

    github_token = st.text_input(
        "GitHub Token (optional)",
        value=st.session_state.github_token,
        type="password",
        placeholder="ghp_... (for private repos / higher limits)",
        help="Needed for private repos. Also increases rate limit from 60 to 5000 req/hr.",
        key="github_token_input",
    )
    if github_token:
        st.session_state.github_token = github_token

    st.markdown('<div class="sidebar-section-title">⚙️ Model Settings</div>', unsafe_allow_html=True)

    model_choice = st.selectbox(
        "GLM Model",
        options=["glm-5-plus", "glm-4-plus", "glm-4"],
        index=0,
        key="model_select",
    )
    st.session_state.model = model_choice

    st.markdown('<div class="sidebar-section-title">🧪 Options</div>', unsafe_allow_html=True)

    run_confidence = st.checkbox(
        "Run confidence self-evaluation",
        value=st.session_state.run_confidence,
        help="Ask GLM to rate confidence in its own analysis (adds ~10-15s)",
        key="confidence_check",
    )
    st.session_state.run_confidence = run_confidence

    # Rate limit info
    if st.session_state.github_token:
        st.markdown('<div class="sidebar-section-title">📊 GitHub Status</div>', unsafe_allow_html=True)
        try:
            gh_temp = GitHubClient(token=st.session_state.github_token)
            rl = gh_temp.get_rate_limit_info()
            if rl:
                remaining = rl.get("core_remaining", "?")
                limit = rl.get("core_limit", "?")
                pct = int(remaining / limit * 100) if isinstance(remaining, int) and isinstance(limit, int) else 0
                color = "#10b981" if pct > 50 else "#f59e0b" if pct > 20 else "#ef4444"
                st.markdown(
                    f'<div style="font-size:0.8rem; color: {color};">API: {remaining}/{limit} requests remaining</div>',
                    unsafe_allow_html=True
                )
        except Exception:
            pass

    st.markdown("---")
    st.markdown(
        '<div style="font-size: 0.72rem; color: #4b5563; line-height: 1.6;">'
        '🔒 Your API keys are never stored or transmitted beyond direct API calls.<br><br>'
        '⚡ Powered by <b style="color: #a78bfa;">GLM 5.1 by Z.ai</b>'
        '</div>',
        unsafe_allow_html=True
    )


# ── Main Content ──────────────────────────────────────────────────────────────

# Header
st.markdown("""
<div class="fixflow-header">
    <span class="fixflow-logo">🔧</span>
    <div class="fixflow-title">FixFlow</div>
    <div class="fixflow-subtitle">Autonomous Bug Resolution Agent</div>
    <span class="powered-badge">⚡ GLM 5.1 by Z.ai</span>
</div>
""", unsafe_allow_html=True)


# ── Input Section ─────────────────────────────────────────────────────────────
st.markdown('<div class="pipeline-card">', unsafe_allow_html=True)
st.markdown("### 🎯 Analyze a GitHub Issue")
st.markdown('<div style="color: #9ca3af; font-size: 0.9rem; margin-bottom: 1rem;">Paste a GitHub issue URL and the repository to analyze. FixFlow will autonomously trace the root cause and generate a fix.</div>', unsafe_allow_html=True)

col1, col2 = st.columns(2)
with col1:
    issue_url = st.text_input(
        "GitHub Issue URL",
        placeholder="https://github.com/owner/repo/issues/123",
        help="Full URL to the GitHub issue you want to fix",
        key="issue_url_input",
    )
with col2:
    repo_url = st.text_input(
        "Repository URL",
        placeholder="https://github.com/owner/repo",
        help="The repository containing the buggy code",
        key="repo_url_input",
    )

# Auto-fill repo from issue URL
if issue_url and not repo_url:
    # Try to extract repo from issue URL
    import re
    m = re.match(r"(https://github\.com/[^/]+/[^/]+)/issues/\d+", issue_url.strip())
    if m:
        st.session_state["repo_url_input"] = m.group(1)
        repo_url = m.group(1)

# Example buttons
st.markdown('<div style="margin-top: 0.5rem; color: #6b7280; font-size: 0.8rem;">💡 Try with an example:</div>', unsafe_allow_html=True)
ex_col1, ex_col2, ex_col3 = st.columns(3)
with ex_col1:
    if st.button("FastAPI #1234 example", key="ex1", help="Example issue"):
        st.info("Set issue URL to a real FastAPI issue, e.g.: https://github.com/tiangolo/fastapi/issues/10876")
with ex_col2:
    if st.button("Requests #6710 example", key="ex2", help="Example issue"):
        st.info("Set issue URL to: https://github.com/psf/requests/issues/6710")
with ex_col3:
    if st.button("Flask #5742 example", key="ex3", help="Example issue"):
        st.info("Set issue URL to: https://github.com/pallets/flask/issues/5742")

st.markdown('</div>', unsafe_allow_html=True)

# ── Analyze Button ────────────────────────────────────────────────────────────
st.markdown("<br>", unsafe_allow_html=True)
btn_col, info_col = st.columns([1, 3])

with btn_col:
    analyze_clicked = st.button(
        "🚀 Analyze & Fix",
        key="analyze_btn",
        type="primary",
        disabled=st.session_state.running,
        use_container_width=True,
    )

with info_col:
    if st.session_state.running:
        st.markdown(
            '<div style="padding: 0.6rem; color: #60a5fa; font-size: 0.9rem; display: flex; align-items: center; gap: 0.5rem;">'
            '⏳ Analysis in progress... This may take 1-3 minutes depending on repo size.'
            '</div>',
            unsafe_allow_html=True
        )
    elif st.session_state.result:
        total_time = sum(st.session_state.result.step_timings.values())
        st.markdown(
            f'<div style="padding: 0.6rem; color: #10b981; font-size: 0.9rem;">'
            f'✅ Last analysis completed in {total_time:.1f}s</div>',
            unsafe_allow_html=True
        )


# ── Pipeline Execution ────────────────────────────────────────────────────────
STEP_LABELS = {
    "0_fetch":      ("📡", "Fetching GitHub Data"),
    "1_issue":      ("📋", "Analyzing Bug Report"),
    "2_mapping":    ("🗺️", "Mapping Codebase"),
    "3_analysis":   ("🔬", "Root Cause Analysis"),
    "4_fix":        ("🔧", "Generating Fix"),
    "5_diff":       ("📝", "Creating PR Description"),
    "6_confidence": ("🎯", "Confidence Evaluation"),
}


def run_agent():
    """Execute the FixFlow agent pipeline (runs in main thread for Streamlit)."""
    st.session_state.running = True
    st.session_state.result = None
    st.session_state.error = None
    st.session_state.step_statuses = {}
    st.session_state.step_messages = {}
    st.session_state.stream_buffer = ""

    def on_status(step: str, status: str, message: str):
        st.session_state.step_statuses[step] = status
        st.session_state.step_messages[step] = message

    def on_stream(chunk: str):
        st.session_state.stream_buffer += chunk

    try:
        llm = GLMClient(
            api_key=st.session_state.glm_api_key,
            base_url=GLM_BASE_URL,
            model=st.session_state.model,
        )
        gh = GitHubClient(token=st.session_state.github_token or None)
        agent = FixFlowAgent(llm_client=llm, github_client=gh)

        result = agent.run(
            issue_url=issue_url.strip(),
            repo_url=repo_url.strip(),
            on_status=on_status,
            stream_callback=on_stream,
            run_confidence_eval=st.session_state.run_confidence,
        )
        st.session_state.result = result

    except Exception as e:
        st.session_state.error = str(e)
        logger.exception("Agent pipeline error")
    finally:
        st.session_state.running = False


# Trigger on button click
if analyze_clicked:
    if not st.session_state.glm_api_key:
        st.error("⚠️ Please enter your GLM API key in the sidebar.")
    elif not issue_url:
        st.error("⚠️ Please enter a GitHub Issue URL.")
    elif not repo_url:
        st.error("⚠️ Please enter the Repository URL.")
    else:
        run_agent()
        st.rerun()


# ── Error Display ─────────────────────────────────────────────────────────────
if st.session_state.error:
    st.error(f"❌ **Error:** {st.session_state.error}")
    with st.expander("🐛 Debug Information"):
        st.code(st.session_state.error)


# ── Pipeline Progress ─────────────────────────────────────────────────────────
if st.session_state.step_statuses or st.session_state.result:
    st.markdown("---")
    st.markdown("### ⚡ Pipeline Progress")

    statuses = st.session_state.step_statuses
    result: Optional[AgentResult] = st.session_state.result
    timings = result.step_timings if result else {}

    status_icons = {
        "running": "⏳",
        "complete": "✅",
        "error": "❌",
        "info": "ℹ️",
    }

    progress_cols = st.columns(min(len(STEP_LABELS), 4))
    step_items = list(STEP_LABELS.items())

    for i, (step_id, (icon, label)) in enumerate(step_items):
        status = statuses.get(step_id, "idle")
        timing = timings.get(step_id)

        css_class = f"step-{status}" if status != "idle" else "step-idle"
        status_icon = status_icons.get(status, "⬜")
        time_str = f"{timing:.1f}s" if timing else ""

        st.markdown(
            f'<div class="step-indicator {css_class}">'
            f'<span class="step-icon">{status_icon}</span>'
            f'<span>{icon} {label}</span>'
            f'<span class="step-time">{time_str}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )


# ── Results ───────────────────────────────────────────────────────────────────
if st.session_state.result:
    result: AgentResult = st.session_state.result
    st.markdown("---")

    # ── Summary Stats ─────────────────────────────────────────────────────────
    total_time = sum(result.step_timings.values())
    stats = result.diff_stats

    st.markdown("### 📊 Analysis Summary")
    m1, m2, m3, m4 = st.columns(4)

    with m1:
        st.markdown(
            f'<div class="stat-card">'
            f'<div class="stat-value">{len(result.suspect_file_paths)}</div>'
            f'<div class="stat-label">Files Analyzed</div>'
            f'</div>',
            unsafe_allow_html=True
        )
    with m2:
        st.markdown(
            f'<div class="stat-card">'
            f'<div class="stat-value">{stats.get("files_changed", 0)}</div>'
            f'<div class="stat-label">Files Changed</div>'
            f'</div>',
            unsafe_allow_html=True
        )
    with m3:
        st.markdown(
            f'<div class="stat-card">'
            f'<div class="stat-value">+{stats.get("lines_added", 0)}</div>'
            f'<div class="stat-label">Lines Added</div>'
            f'</div>',
            unsafe_allow_html=True
        )
    with m4:
        st.markdown(
            f'<div class="stat-card">'
            f'<div class="stat-value">{total_time:.0f}s</div>'
            f'<div class="stat-label">Total Time</div>'
            f'</div>',
            unsafe_allow_html=True
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Step 1: Bug Summary ───────────────────────────────────────────────────
    with st.expander("📋 Step 1: Bug Summary", expanded=True):
        st.markdown(
            f'<div style="color: #9ca3af; font-size: 0.82rem; margin-bottom: 1rem;">'
            f'⏱️ Completed in {result.step_timings.get("1_issue", 0):.1f}s'
            f'</div>',
            unsafe_allow_html=True
        )
        st.markdown(result.bug_summary)

    # ── Step 2: Relevant Files ────────────────────────────────────────────────
    with st.expander("🔍 Step 2: Relevant Files & Codebase Mapping", expanded=False):
        st.markdown(
            f'<div style="color: #9ca3af; font-size: 0.82rem; margin-bottom: 0.5rem;">'
            f'⏱️ Completed in {result.step_timings.get("2_mapping", 0):.1f}s | '
            f'Selected {len(result.suspect_file_paths)} files for deep analysis'
            f'</div>',
            unsafe_allow_html=True
        )

        if result.suspect_file_paths:
            st.markdown("**🎯 Files Selected for Analysis:**")
            for i, fp in enumerate(result.suspect_file_paths, 1):
                st.markdown(f"`{i}.` `{fp}`")

        st.markdown("---")
        st.markdown(result.relevant_files_analysis)

    # ── Step 3: Root Cause Analysis ───────────────────────────────────────────
    with st.expander("🔬 Step 3: Root Cause Analysis (Chain-of-Thought)", expanded=True):
        st.markdown(
            f'<div style="color: #9ca3af; font-size: 0.82rem; margin-bottom: 1rem;">'
            f'⏱️ Completed in {result.step_timings.get("3_analysis", 0):.1f}s | '
            f'This is the core reasoning chain — read carefully!'
            f'</div>',
            unsafe_allow_html=True
        )
        st.markdown(result.root_cause_analysis)

    # ── Step 4: Proposed Fix (Diff) ───────────────────────────────────────────
    with st.expander("🔧 Step 4: Proposed Fix", expanded=True):
        st.markdown(
            f'<div style="color: #9ca3af; font-size: 0.82rem; margin-bottom: 1rem;">'
            f'⏱️ Completed in {result.step_timings.get("4_fix", 0):.1f}s | '
            f'{stats.get("files_changed", 0)} file(s) modified, '
            f'+{stats.get("lines_added", 0)} / -{stats.get("lines_removed", 0)} lines'
            f'</div>',
            unsafe_allow_html=True
        )

        if result.diffs:
            # Syntax-highlighted diff
            for filepath, diff_content in result.diffs.items():
                st.markdown(f"**`{filepath}`**")
                st.code(diff_content, language="diff")
        else:
            st.warning("⚠️ No diffs generated. The LLM may not have proposed direct file changes.")
            if result.fix_generation_raw:
                st.markdown("**Raw fix proposal from GLM:**")
                st.markdown(result.fix_generation_raw)

        # Copy button for full diff
        if result.diff_formatted and result.diffs:
            st.markdown("---")
            copy_col, _ = st.columns([1, 3])
            with copy_col:
                st.download_button(
                    "📋 Copy Full Diff",
                    data=result.diff_formatted,
                    file_name="fixflow.diff",
                    mime="text/plain",
                    use_container_width=True,
                )

    # ── Step 5: Fix Explanation ───────────────────────────────────────────────
    with st.expander("📝 Step 5: PR Description & Fix Explanation", expanded=True):
        st.markdown(
            f'<div style="color: #9ca3af; font-size: 0.82rem; margin-bottom: 1rem;">'
            f'⏱️ Completed in {result.step_timings.get("5_diff", 0):.1f}s'
            f'</div>',
            unsafe_allow_html=True
        )
        st.markdown(result.fix_explanation)

    # ── Confidence Eval (optional) ────────────────────────────────────────────
    if result.confidence_eval:
        with st.expander("🎯 Confidence Self-Evaluation", expanded=False):
            st.markdown(result.confidence_eval)

    # ── Export Full Report ────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 📤 Export Report")
    exp_col1, exp_col2, _ = st.columns([1, 1, 2])

    full_report = generate_full_report(result)
    issue_num = result.issue_data.get("number", "0")
    repo_slug = repo_url.strip().rstrip("/").split("/")[-1] if repo_url else "repo"

    with exp_col1:
        st.download_button(
            "📄 Download Full Report (.md)",
            data=full_report,
            file_name=f"fixflow_{repo_slug}_issue_{issue_num}.md",
            mime="text/markdown",
            use_container_width=True,
        )

    with exp_col2:
        if result.diff_formatted and result.diffs:
            st.download_button(
                "📦 Download Patch (.diff)",
                data=result.diff_formatted,
                file_name=f"fixflow_{repo_slug}_issue_{issue_num}.diff",
                mime="text/plain",
                use_container_width=True,
            )

    st.markdown("---")
    st.markdown(
        '<div style="text-align: center; color: #4b5563; font-size: 0.8rem; padding: 1rem 0;">'
        '🔧 <b style="color: #6c63ff;">FixFlow</b> — Autonomous Bug Resolution · Powered by '
        '<b style="color: #a78bfa;">GLM 5.1 by Z.ai</b>'
        '</div>',
        unsafe_allow_html=True
    )


# ── Empty State ───────────────────────────────────────────────────────────────
elif not st.session_state.running and not st.session_state.error:
    st.markdown("<br>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)

    cards = [
        ("🐛", "Bug Report Parsing", "Automatically extracts error messages, reproduction steps, affected components, and technical clues from any GitHub issue."),
        ("🧠", "Chain-of-Thought Reasoning", "Traces the execution flow step-by-step, citing specific file names, functions, and line numbers to pinpoint the root cause."),
        ("🔧", "PR-Ready Fixes", "Generates minimal, precise code fixes with unified diffs and a complete pull request description you can copy directly."),
    ]

    for col, (icon, title, desc) in zip([col1, col2, col3], cards):
        with col:
            st.markdown(
                f'<div class="pipeline-card" style="text-align: center; padding: 2rem 1.5rem;">'
                f'<div style="font-size: 2.5rem; margin-bottom: 0.75rem;">{icon}</div>'
                f'<div style="font-weight: 700; font-size: 1rem; color: #f0f0ff; margin-bottom: 0.5rem;">{title}</div>'
                f'<div style="font-size: 0.85rem; color: #6b7280; line-height: 1.6;">{desc}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    st.markdown("<br>", unsafe_allow_html=True)

    # How it works
    st.markdown("### 🔄 How It Works")
    steps_html = """
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 0.75rem; margin-top: 1rem;">
    """
    how_steps = [
        ("1", "📡", "Fetch Issue", "Pulls the full GitHub issue: title, body, comments, labels"),
        ("2", "🗺️", "Map Codebase", "Identifies top 5-10 suspect files from the repo tree"),
        ("3", "🔬", "Analyze Code", "Deep code reading with chain-of-thought root cause tracing"),
        ("4", "🔧", "Generate Fix", "Creates corrected file versions with minimal changes"),
        ("5", "📝", "Write PR", "Produces unified diff + human-readable PR description"),
    ]
    for num, icon, title, desc in how_steps:
        steps_html += f"""
        <div style="background: #12141a; border: 1px solid #2a2c36; border-radius: 10px; padding: 1rem; position: relative;">
            <div style="position: absolute; top: -10px; left: 12px; background: linear-gradient(135deg, #6c63ff, #a78bfa); border-radius: 50%; width: 22px; height: 22px; display: flex; align-items: center; justify-content: center; font-size: 0.7rem; font-weight: 800; color: white;">{num}</div>
            <div style="font-size: 1.4rem; margin-bottom: 0.4rem; margin-top: 0.3rem;">{icon}</div>
            <div style="font-weight: 700; font-size: 0.9rem; color: #f0f0ff; margin-bottom: 0.3rem;">{title}</div>
            <div style="font-size: 0.78rem; color: #6b7280; line-height: 1.5;">{desc}</div>
        </div>
        """
    steps_html += "</div>"
    st.markdown(steps_html, unsafe_allow_html=True)
