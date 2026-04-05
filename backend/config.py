"""
FixFlow Configuration
All API keys, model config, and constants loaded from environment variables.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ── LLM Config ──────────────────────────────────────────────────────────────
GLM_API_KEY: str = os.getenv("GLM_API_KEY", "")
GLM_BASE_URL: str = os.getenv("GLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")
GLM_MODEL: str = os.getenv("GLM_MODEL", "glm-5")

# ── GitHub Config ────────────────────────────────────────────────────────────
GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")
if GITHUB_TOKEN == "your_github_token_here":
    GITHUB_TOKEN = ""

# ── Agent Limits ─────────────────────────────────────────────────────────────
MAX_FILES_TO_SCAN: int = int(os.getenv("MAX_FILES_TO_SCAN", "100"))
MAX_FILE_SIZE_BYTES: int = int(os.getenv("MAX_FILE_SIZE_BYTES", "51200"))  # 50 KB
MAX_FILES_TO_ANALYZE: int = 10      # Top N files sent to deep analysis
MAX_REPO_FILES: int = 500           # Hard cap on tree traversal

# ── File Filters (skip these in code analysis) ───────────────────────────────
IGNORE_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp",
    ".mp4", ".mp3", ".wav", ".pdf", ".zip", ".tar", ".gz",
    ".woff", ".woff2", ".ttf", ".eot",
    ".lock", ".sum", ".mod",
    ".pyc", ".pyo", ".pyd",
    ".class", ".jar",
    ".DS_Store",
}

IGNORE_DIRS = {
    "node_modules", ".git", ".github", "__pycache__", ".venv", "venv",
    "env", "dist", "build", ".next", ".nuxt", "coverage", ".pytest_cache",
    "vendor", "third_party", "external", "site-packages",
}

CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rb", ".rs",
    ".cpp", ".c", ".h", ".hpp", ".cs", ".php", ".swift", ".kt", ".scala",
    ".sh", ".bash", ".yaml", ".yml", ".toml", ".cfg", ".ini", ".env",
    ".json", ".xml", ".html", ".css", ".scss", ".sql", ".md",
}

# ── Timing & Logging ─────────────────────────────────────────────────────────
LOG_LLM_CALLS: bool = os.getenv("LOG_LLM_CALLS", "true").lower() == "true"
