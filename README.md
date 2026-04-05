---
title: Fixflow
emoji: 🔧
colorFrom: pink
colorTo: red
sdk: docker
app_port: 7860
pinned: false
---

<div align="center">
  <h1>🔧 FixFlow</h1>
  <p><b>Autonomous AI Agent for Automated Technical Due Diligence and Bug Resolution</b></p>
  
  <p align="center">
    <a href="#about">About</a> •
    <a href="#features">Features</a> •
    <a href="#architecture">Architecture</a> •
    <a href="#how-it-works">How it Works</a> •
    <a href="#quick-start">Quick Start</a> •
    <a href="#deployment">Deployment</a>
  </p>
</div>

---

## ⚡️ About FixFlow

FixFlow is a state-of-the-art **autonomous bug resolution agent** built for modern development workflows. Give FixFlow a GitHub repository URL and an Issue link, and it will handle the rest—from cloning the repository and deeply analyzing the architecture, to finding the root cause of the bug, generating the fixed code, and automatically opening a Pull Request.

Built using **Next.js**, **FastAPI**, and propelled by the intelligent reasoning capabilities of **GLM-4-Air** (Z.ai), FixFlow turns hours of debugging into a highly optimized, fully automated 3-minute process.

---

## ✨ Core Features

*   🌍 **Full-Viewport IDE Dashboard:** A beautiful, responsive 3-pane IDE layout featuring a live File Explorer, interactive Code Editor, and automated Issue Tracking.
*   🧠 **Deep Contextual Understanding:** FixFlow doesn't just read the issue; it navigates the repository file tree, fetching the exact files that define the bug's context.
*   ⚡ **Lightning Fast:** Generates production-ready, peer-reviewed fixes in an average of 2-3 minutes.
*   📹 **Live SSE Streaming:** See the LLM's thought process and generated syntax mapped into the editor UI live, block-by-block.
*   🤖 **Autonomous PR Creation:** One click publishes the fix directly to your GitHub repository with a detailed changelog and explanation.
*   🔒 **Intelligent Rate Limiting:** Built-in semantic retry logic with exponential backoff and jitter designed specifically for autonomous API agents.

---

## 🏛 Architecture

FixFlow is split into a highly responsive client-side interface and a powerful Python-based agentic pipeline.

*   **Frontend (Next.js 15, React, Vanilla CSS):** Handles the IDE state machine (LOADING, REPO_DASHBOARD, DONE), renders the file explorer, and streams Server-Sent Events (SSE) representing intermediate agent log steps.
*   **Backend (FastAPI, Python 3.11):** Contains the orchestrator logic to traverse the repository, interface with the GitHub REST API, and communicate with the GLM API endpoints.
*   **LLM Engine (GLM-4-Air):** The foundation of the logical reasoning. The agent forces the LLM to provide multi-step reasoning outputs ensuring accuracy across thousands of files.

---

## ⚙️ How the Agent Pipeline Works

FixFlow operates in a rigid, deterministic 5-step autonomous loop:

1.  **[1_ISSUE] Issue Understanding:** Fetches the open GitHub issue to decode the exact bug details, user complaints, and relevant environment variables.
2.  **[2_MAPPING] Repository Mapping:** Clones the repository file-tree. Leverages intelligent filtering to skip assets (e.g. `.png`) and dependencies (e.g. `node_modules`), zeroing in exclusively on source code logic.
3.  **[3_ANALYSIS] Root Cause Analysis:** Scans top suspected files and cross-references them against the issue, discovering precisely where the logic flaw or crash originated.
4.  **[4_FIX] Automated Generation:** Streams a live diff sequence overriding the broken logic with best-practice solutions.
5.  **[5_EXPLANATION] Documentation:** Outputs developer-friendly Markdown describing exactly *what* changed and *why*, generating a PR template.

---

## 🚀 Quick Start (Local Development)

### 1. Prerequisites
- Node.js v20+
- Python 3.11+
- A valid **GitHub Personal Access Token (PAT)**
- A valid **Z.ai API Key (`GLM_API_KEY`)**

### 2. Environment Setup
Create a `.env` file in the root directory:
```env
GLM_API_KEY=your_zai_api_key_here
GITHUB_TOKEN=your_github_pat_here
GLM_MODEL=glm-4-air
```

### 3. Run the Backend (FastAPI)
```bash
# Optional: Create a virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Boot the API server
uvicorn backend.api:app --host 127.0.0.1 --port 8000
```

### 4. Run the Frontend (Next.js)
```bash
# In a new terminal
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000` in your browser.

---

## 🐳 Deployment (Docker & Hugging Face Spaces)

FixFlow is fully configured for deployment on **Hugging Face Spaces (Docker SDK)**. 

### Running via unified Docker Container
The provided `Dockerfile` bundles the Python API and the Next.js React app, serving them via a `start.sh` job-control script. Next.js automatically rewrites `/api/*` traffic to the internal Python backend.

```bash
docker build -t fixflow .
docker run -p 7860:7860 --env-file .env fixflow
```

### Deploying to Hugging Face
If deploying remotely to an empty HF Space:

1. Create a dynamic HF Space with the **Docker** runtime.
2. Ensure you have a Hugging Face Access Token with **Write** permissions.
3. Configure `GLM_API_KEY` and `GITHUB_TOKEN` under your Space's *Variables & Secrets*.
4. Push your codebase to the space:
```bash
git remote add hf https://huggingface.co/spaces/<username>/<space-name>
git push https://<username>:<HF_TOKEN>@huggingface.co/spaces/<username>/<space-name> main --force
```

---
<div align="center">
  <p><i>Autonomous bug fixing for the modern developer. Built during Hackathon.</i></p>
</div>
