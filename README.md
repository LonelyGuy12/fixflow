# 🔧 FixFlow — Autonomous Bug Resolution Agent

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.30+-FF4B4B?style=flat-square&logo=streamlit&logoColor=white)](https://streamlit.io)
[![GLM 5.1](https://img.shields.io/badge/Powered%20by-GLM%205.1%20by%20Z.ai-6c63ff?style=flat-square)](https://open.bigmodel.cn)
[![License](https://img.shields.io/badge/License-MIT-10b981?style=flat-square)](LICENSE)

**Give FixFlow a GitHub issue. Get back a root cause analysis + a PR-ready fix.**

*Built with GLM 5.1 by Z.ai ⚡*

</div>

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🐛 **Smart Issue Parsing** | Extracts error messages, reproduction steps, and technical clues from any GitHub issue |
| 🗺️ **Codebase Mapping** | Identifies the top 5-10 most suspect files from the entire repo tree |
| 🧠 **Chain-of-Thought Reasoning** | Traces execution flow step-by-step, citing file names, functions, and line numbers |
| 🔬 **Root Cause Analysis** | Pinpoints the exact bug location with high-confidence reasoning |
| 🔧 **Fix Generation** | Generates minimal, precise code changes as unified diffs |
| 📝 **PR Description** | Writes a complete, reviewer-friendly pull request description |
| 🎯 **Confidence Score** | Optional self-evaluation step where GLM rates its own certainty |
| 📤 **Export** | Download the full analysis report as Markdown or the patch as `.diff` |

---

## 🚀 Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/your-username/fixflow.git
cd fixflow

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure API Keys

```bash
cp .env.example .env
```

Edit `.env`:

```env
GLM_API_KEY=your_glm_api_key_here        # Get from https://open.bigmodel.cn/
GITHUB_TOKEN=ghp_your_token_here          # Optional, but recommended
GLM_MODEL=glm-5-plus
```

### 3. Run

```bash
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501) 🎉

---

## 🔄 How It Works

```
GitHub Issue URL
      │
      ▼
┌─────────────────┐
│ 1. Parse Issue  │ ─── Extract: error, repro steps, affected components
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 2. Map Codebase │ ─── Scan repo tree → Rank top 5-10 suspect files
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 3. Analyze Code │ ─── Read files → Chain-of-thought root cause tracing
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 4. Generate Fix │ ─── Produce corrected file versions (minimal changes)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 5. Write PR     │ ─── Unified diff + human-readable PR description
└─────────────────┘
         │
         ▼
  📄 Full Report + 📦 Patch File
```

---

## 🧪 Example Output

See [`demo/example_output.md`](demo/example_output.md) for a full sample analysis on a real FastAPI issue.

Quick preview:

```
🔬 Root Cause:
In fastapi/_compat.py ~line 215, _get_value() calls model_dump()
without passing `include=include` in the Pydantic v2 branch.
The fix: add include=include, exclude=exclude to model_dump().
```

---

## 📁 Project Structure

```
fixflow/
├── app.py                    # Streamlit frontend (dark UI, streaming output)
├── backend/
│   ├── __init__.py
│   ├── config.py             # API keys, model config, constants
│   ├── github_client.py      # Fetch issues, repo trees, file contents
│   ├── code_indexer.py       # Parse repo structure, format for LLM
│   ├── agent.py              # Core 5-step reasoning agent orchestrator
│   ├── prompts.py            # All LLM prompt templates
│   ├── diff_generator.py     # Generate unified diffs from proposed changes
│   └── llm_client.py        # GLM 5.1 API wrapper (sync + streaming)
├── requirements.txt
├── .env.example
├── README.md
└── demo/
    └── example_output.md     # Sample output for showcase
```

---

## ⚙️ Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `GLM_API_KEY` | — | Your Z.ai API key (required) |
| `GITHUB_TOKEN` | — | GitHub PAT (optional, recommended) |
| `GLM_MODEL` | `glm-5-plus` | GLM model to use |
| `GLM_BASE_URL` | `https://open.bigmodel.cn/api/paas/v4` | API endpoint |
| `MAX_FILES_TO_SCAN` | `100` | Max files to include in repo scan |
| `MAX_FILE_SIZE_BYTES` | `51200` | Max file size to read (50 KB) |

---

## 🛠️ Tech Stack

- **Frontend:** Streamlit with custom dark CSS (glassmorphism design)
- **Backend:** Python 3.11+, FastAPI-compatible architecture
- **LLM:** GLM 5.1 via Z.ai API (OpenAI-compatible endpoint)
- **GitHub:** PyGithub + GitHub REST API
- **Diffs:** Python `difflib` (unified diff format)

---

## 📝 License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">
Built with ❤️ for the Z.ai GLM 5.1 Hackathon<br>
<b>Powered by GLM 5.1 by Z.ai ⚡</b>
</div>
