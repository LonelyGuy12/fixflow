import asyncio
import json
import logging
import time
import uuid
from threading import Thread
from typing import Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from backend.agent import FixFlowAgent
from backend.config import GLM_MODEL, GLM_BASE_URL, GLM_API_KEY, GITHUB_TOKEN
from backend.github_client import GitHubClient
from backend.llm_client import GLMClient

logger = logging.getLogger(__name__)

app = FastAPI(title="FixFlow API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SESSION_CACHE: Dict[str, Any] = {}

class AnalyzeRequest(BaseModel):
    issue_url: str
    repo_url: str
    run_confidence: bool = True

@app.get("/api/analyze")
async def analyze_endpoint(issue_url: str, repo_url: str, run_confidence: bool = True):
    if not GLM_API_KEY:
        raise HTTPException(status_code=400, detail="Missing GLM API key in backend config")

    session_id = str(uuid.uuid4())
    queue = asyncio.Queue()

    def sync_runner():
        llm = GLMClient(
            api_key=GLM_API_KEY,
            base_url=GLM_BASE_URL,
            model=GLM_MODEL,
        )
        gh = GitHubClient(token=GITHUB_TOKEN)
        agent = FixFlowAgent(llm_client=llm, github_client=gh)

        def on_status(step: str, status: str, message: str):
            asyncio.run_coroutine_threadsafe(
                queue.put({"type": "status", "data": {"step": step, "status": status, "message": message}}),
                loop
            )

        def on_stream(chunk: str):
            asyncio.run_coroutine_threadsafe(
                queue.put({"type": "stream", "data": {"chunk": chunk}}),
                loop
            )

        try:
            result = agent.run(
                issue_url=issue_url,
                repo_url=repo_url,
                on_status=on_status,
                stream_callback=on_stream,
                run_confidence_eval=run_confidence,
            )
            
            payload = {
                "bug_summary": result.bug_summary,
                "relevant_files_analysis": result.relevant_files_analysis,
                "suspect_file_paths": result.suspect_file_paths,
                "root_cause_analysis": result.root_cause_analysis,
                "diff_formatted": result.diff_formatted,
                "fix_explanation": result.fix_explanation,
                "diff_stats": result.diff_stats,
                "step_timings": result.step_timings,
                "fixed_files": result.fixed_files,
                "issue_title": result.issue_data.get("title", "Bug fix")
            }
            SESSION_CACHE[session_id] = result
            asyncio.run_coroutine_threadsafe(
                queue.put({"type": "done", "data": {"result": payload, "session_id": session_id}}),
                loop
            )
        except Exception as e:
            logger.exception("Agent run failed")
            asyncio.run_coroutine_threadsafe(
                queue.put({"type": "error", "data": {"error": str(e)}}),
                loop
            )
        finally:
            asyncio.run_coroutine_threadsafe(
                queue.put({"type": "eof"}),
                loop
            )

    loop = asyncio.get_running_loop()
    thread = Thread(target=sync_runner)
    thread.start()

    async def event_generator():
        while True:
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=15.0)
                if msg["type"] == "eof":
                    yield {"event": "eof", "data": json.dumps({"done": True})}
                    break
                yield {
                    "event": msg["type"],
                    "data": json.dumps(msg["data"])
                }
            except asyncio.TimeoutError:
                yield {"event": "heartbeat", "data": json.dumps({"alive": True})}

    return EventSourceResponse(event_generator())


class PRRequest(BaseModel):
    repo_url: str
    title: str
    body: str
    fixed_files: Dict[str, str]

@app.post("/api/pr")
def create_pr(req: PRRequest):
    if not GITHUB_TOKEN:
        raise HTTPException(status_code=400, detail="Missing GITHUB_TOKEN in backend config for PR creation")
        
    gh = GitHubClient(token=GITHUB_TOKEN)
    branch_name = f"fixflow-patch-{int(time.time())}"
    try:
        url = gh.create_pull_request(
            repo_url=req.repo_url,
            branch_name=branch_name,
            files_content=req.fixed_files,
            title=req.title,
            body=req.body
        )
        return {"url": url}
    except Exception as e:
        logger.exception("PR creation failed")
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/repo_info")
def get_repo_info(repo_url: str):
    """
    Fetch repository file tree and list open issues.
    """
    try:
        gh = GitHubClient(token=GITHUB_TOKEN)
        # Fetch repo tree (flat list)
        tree = gh.fetch_repo_tree(repo_url)
        # Fetch top 10 open issues
        issues = gh.list_open_issues(repo_url, limit=10)
        
        return {
            "tree": tree,
            "issues": issues,
            "repo_url": repo_url
        }
    except Exception as e:
        logger.exception("Repo info fetch failed")
        raise HTTPException(status_code=400, detail=str(e))

        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/file_content")
def get_file_content(repo_url: str, file_path: str):
    """
    Fetch the raw content of a specific file in the repository.
    """
    try:
        gh = GitHubClient(token=GITHUB_TOKEN)
        content = gh.fetch_file_content(repo_url, file_path)
        return {"content": content, "path": file_path}
    except Exception as e:
        logger.exception("File content fetch failed")
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/refine")
async def refine_endpoint(session_id: str, feedback: str):
    if not GLM_API_KEY:
        raise HTTPException(status_code=400, detail="Missing GLM API key in backend config")
        
    if session_id not in SESSION_CACHE:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    queue = asyncio.Queue()

    def sync_runner():
        llm = GLMClient(
            api_key=GLM_API_KEY,
            base_url=GLM_BASE_URL,
            model=GLM_MODEL,
        )
        gh = GitHubClient(token=GITHUB_TOKEN)
        agent = FixFlowAgent(llm_client=llm, github_client=gh)
        previous_result = SESSION_CACHE[session_id]

        def on_status(step: str, status: str, message: str):
            asyncio.run_coroutine_threadsafe(
                queue.put({"type": "status", "data": {"step": step, "status": status, "message": message}}),
                loop
            )

        def on_stream(chunk: str):
            asyncio.run_coroutine_threadsafe(
                queue.put({"type": "stream", "data": {"chunk": chunk}}),
                loop
            )

        try:
            result = agent.refine_fix(
                feedback=feedback,
                result=previous_result,
                on_status=on_status,
                stream_callback=on_stream,
            )
            
            payload = {
                "bug_summary": result.bug_summary,
                "relevant_files_analysis": result.relevant_files_analysis,
                "suspect_file_paths": result.suspect_file_paths,
                "root_cause_analysis": result.root_cause_analysis,
                "diff_formatted": result.diff_formatted,
                "fix_explanation": result.fix_explanation,
                "diff_stats": result.diff_stats,
                "step_timings": result.step_timings,
                "fixed_files": result.fixed_files,
                "issue_title": result.issue_data.get("title", "Bug fix")
            }
            SESSION_CACHE[session_id] = result
            asyncio.run_coroutine_threadsafe(
                queue.put({"type": "done", "data": {"result": payload, "session_id": session_id}}),
                loop
            )
        except Exception as e:
            logger.exception("Agent run failed")
            asyncio.run_coroutine_threadsafe(
                queue.put({"type": "error", "data": {"error": str(e)}}),
                loop
            )
        finally:
            asyncio.run_coroutine_threadsafe(
                queue.put({"type": "eof"}),
                loop
            )

    loop = asyncio.get_running_loop()
    thread = Thread(target=sync_runner)
    thread.start()

    async def event_generator():
        while True:
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=15.0)
                if msg["type"] == "eof":
                    yield {"event": "eof", "data": json.dumps({"done": True})}
                    break
                yield {
                    "event": msg["type"],
                    "data": json.dumps(msg["data"])
                }
            except asyncio.TimeoutError:
                yield {"event": "heartbeat", "data": json.dumps({"alive": True})}

    return EventSourceResponse(event_generator())
