---
title: Fixflow
emoji: 🔧
colorFrom: pink
colorTo: red
sdk: docker
app_port: 7860
pinned: false
---

# FixFlow - Autonomous Repository Agent

FixFlow analyzes your repository, understands issues deeply, and generates production-ready fixes with pull requests—all automatically.

## Running Locally

1. Create a `.env` file with `GLM_API_KEY` and `GITHUB_TOKEN`.
2. Start the FastAPI backend:
   ```bash
   uvicorn backend.api:app --host 127.0.0.1 --port 8000
   ```
3. Start the Next.js frontend:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

## Deploying

This project is configured to run fully containerized on Hugging Face Spaces using the provided `Dockerfile` and `start.sh`.
