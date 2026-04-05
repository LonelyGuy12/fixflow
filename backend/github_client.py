"""
GitHub client for fetching issues, repo trees, and file contents.
Supports both public repos (no auth) and private repos (with token).
"""
import re
import logging
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests
from github import Github, GithubException, Auth

from backend.config import (
    GITHUB_TOKEN,
    IGNORE_EXTENSIONS,
    IGNORE_DIRS,
    CODE_EXTENSIONS,
    MAX_FILE_SIZE_BYTES,
    MAX_REPO_FILES,
)

logger = logging.getLogger(__name__)


# ── URL Parsing Helpers ───────────────────────────────────────────────────────

def parse_issue_url(issue_url: str) -> Tuple[str, str, int]:
    """
    Parse a GitHub issue URL into (owner, repo, issue_number).
    Supports:
      https://github.com/owner/repo/issues/123
    """
    issue_url = issue_url.strip().rstrip("/")
    pattern = r"github\.com/([^/]+)/([^/]+)/issues/(\d+)"
    match = re.search(pattern, issue_url)
    if not match:
        raise ValueError(
            f"Could not parse GitHub issue URL: {issue_url!r}\n"
            "Expected format: https://github.com/owner/repo/issues/123"
        )
    owner, repo, issue_num = match.groups()
    return owner, repo, int(issue_num)


def parse_repo_url(repo_url: str) -> Tuple[str, str]:
    """
    Parse a GitHub repo URL into (owner, repo).
    Supports:
      https://github.com/owner/repo
      https://github.com/owner/repo.git
    """
    repo_url = repo_url.strip().rstrip("/").removesuffix(".git")
    pattern = r"github\.com/([^/]+)/([^/]+)"
    match = re.search(pattern, repo_url)
    if not match:
        raise ValueError(
            f"Could not parse GitHub repo URL: {repo_url!r}\n"
            "Expected format: https://github.com/owner/repo"
        )
    owner, repo = match.groups()
    return owner, repo


# ── GitHub Client ─────────────────────────────────────────────────────────────

class GitHubClient:
    """Wraps PyGithub for FixFlow's use cases."""

    def __init__(self, token: Optional[str] = None):
        tok = token or GITHUB_TOKEN
        if tok:
            auth = Auth.Token(tok)
            self._gh = Github(auth=auth)
        else:
            self._gh = Github()  # unauthenticated (60 req/hr)
        self._rate_limit_warned = False

    # ── Issue Fetching ────────────────────────────────────────────────────────

    def fetch_issue(self, issue_url: str) -> Dict:
        """
        Fetch a GitHub issue and return a structured dict:
        {title, body, labels, state, author, comments, url}
        """
        owner, repo_name, issue_num = parse_issue_url(issue_url)
        logger.info("Fetching issue #%d from %s/%s", issue_num, owner, repo_name)

        try:
            repo = self._gh.get_repo(f"{owner}/{repo_name}")
            issue = repo.get_issue(number=issue_num)
        except GithubException as e:
            raise RuntimeError(
                f"Failed to fetch issue from GitHub: {e.data.get('message', str(e))}"
            ) from e

        # Collect top comments (up to 10)
        comments = []
        try:
            for comment in issue.get_comments():
                comments.append({
                    "author": comment.user.login if comment.user else "unknown",
                    "body": comment.body or "",
                    "created_at": str(comment.created_at),
                })
                if len(comments) >= 10:
                    break
        except GithubException:
            pass

        return {
            "title": issue.title or "",
            "body": issue.body or "",
            "labels": [lbl.name for lbl in issue.labels],
            "state": issue.state,
            "author": issue.user.login if issue.user else "unknown",
            "url": issue.html_url,
            "number": issue_num,
            "comments": comments,
            "repo_owner": owner,
            "repo_name": repo_name,
        }

    def list_open_issues(self, repo_url: str, limit: int = 20) -> List[Dict]:
        """
        List open issues for a repository.
        Returns a list of structured dicts: {title, number, url, author, created_at, body_snippet}
        """
        owner, repo_name = parse_repo_url(repo_url)
        logger.info("Listing open issues for %s/%s", owner, repo_name)

        try:
            repo = self._gh.get_repo(f"{owner}/{repo_name}")
            # state='open' by default
            issues = repo.get_issues(state='open', sort='updated', direction='desc')
            
            result = []
            for issue in issues:
                # Skip Pull Requests (PyGithub get_issues() returns both)
                if issue.pull_request:
                    continue
                
                result.append({
                    "title": issue.title,
                    "number": issue.number,
                    "url": issue.html_url,
                    "author": issue.user.login if issue.user else "unknown",
                    "created_at": str(issue.created_at),
                    "body_snippet": (issue.body[:200] + "...") if issue.body else "",
                })
                if len(result) >= limit:
                    break
            return result
        except GithubException as e:
            raise RuntimeError(
                f"Failed to list issues: {e.data.get('message', str(e))}"
            ) from e

    # ── Repo Tree ─────────────────────────────────────────────────────────────

    def fetch_repo_tree(
        self,
        repo_url: str,
        token: Optional[str] = None,
    ) -> List[Dict]:
        """
        Return a flat list of code files in the repo.
        Each entry: {path, size, type}
        Filters out binary files, ignored dirs, etc.
        """
        owner, repo_name = parse_repo_url(repo_url)
        logger.info("Fetching repo tree for %s/%s", owner, repo_name)

        # Refresh client if a token was provided on this call
        if token and not GITHUB_TOKEN:
            auth = Auth.Token(token)
            self._gh = Github(auth=auth)

        try:
            repo = self._gh.get_repo(f"{owner}/{repo_name}")
            # Use recursive git tree for efficiency
            tree = repo.get_git_tree("HEAD", recursive=True)
        except GithubException as e:
            raise RuntimeError(
                f"Failed to fetch repo tree: {e.data.get('message', str(e))}"
            ) from e

        files = []
        for item in tree.tree:
            if item.type != "blob":
                continue
            path = item.path

            # Skip ignored directories
            parts = path.split("/")
            if any(p in IGNORE_DIRS for p in parts[:-1]):
                continue

            # Skip ignored/non-code extensions
            ext = "." + path.rsplit(".", 1)[-1].lower() if "." in path else ""
            if ext in IGNORE_EXTENSIONS:
                continue
            if ext not in CODE_EXTENSIONS and ext:
                continue

            # Skip overly large files
            size = item.size or 0
            if size > MAX_FILE_SIZE_BYTES:
                logger.debug("Skipping large file (%d bytes): %s", size, path)
                continue

            files.append({"path": path, "size": size, "type": item.type})
            if len(files) >= MAX_REPO_FILES:
                logger.warning("Hit MAX_REPO_FILES limit (%d)", MAX_REPO_FILES)
                break

        logger.info("Found %d code files in %s/%s", len(files), owner, repo_name)
        return files

    # ── File Content ──────────────────────────────────────────────────────────

    def fetch_file_content(
        self,
        repo_url: str,
        file_path: str,
    ) -> str:
        """
        Fetch the raw text content of a single file from the repo.
        Returns empty string on failure (binary, too large, etc).
        """
        owner, repo_name = parse_repo_url(repo_url)
        try:
            repo = self._gh.get_repo(f"{owner}/{repo_name}")
            content_obj = repo.get_contents(file_path)
            # Handle list (shouldn't happen for blobs, but defensive)
            if isinstance(content_obj, list):
                content_obj = content_obj[0]
            if content_obj.size > MAX_FILE_SIZE_BYTES:
                return f"[File too large to display: {content_obj.size} bytes]"
            decoded = content_obj.decoded_content
            return decoded.decode("utf-8", errors="replace")
        except GithubException as e:
            logger.warning("Could not fetch %s: %s", file_path, e)
            return ""
        except Exception as e:
            logger.warning("Error decoding %s: %s", file_path, e)
            return ""

    def fetch_multiple_files(
        self,
        repo_url: str,
        file_paths: List[str],
    ) -> Dict[str, str]:
        """
        Fetch contents of multiple files. Returns {path: content} dict.
        """
        result = {}
        owner, repo_name = parse_repo_url(repo_url)
        logger.info("Fetching %d files from %s/%s", len(file_paths), owner, repo_name)

        for path in file_paths:
            content = self.fetch_file_content(repo_url, path)
            if content:
                result[path] = content
        return result

    # ── Pull Request Creation ─────────────────────────────────────────────────

    def create_pull_request(
        self,
        repo_url: str,
        branch_name: str,
        files_content: Dict[str, str],
        title: str,
        body: str,
    ) -> str:
        """
        Creates a new branch and commits all changed files, then opens a pull request.
        Requires a GitHub token with write access to the repository.
        Returns the HTML URL of the created PR.
        """
        if not self._gh.get_user():
            raise RuntimeError("A valid GitHub Token with write access is required to create a PR.")
            
        owner, repo_name = parse_repo_url(repo_url)
        logger.info("Creating PR on %s/%s branch %s", owner, repo_name, branch_name)
        
        try:
            repo = self._gh.get_repo(f"{owner}/{repo_name}")
            from github import InputGitTreeElement
            
            base_branch = repo.default_branch
            base_ref = repo.get_git_ref(f"heads/{base_branch}")
            
            # Create new branch off base branch
            try:
                repo.create_git_ref(ref=f"refs/heads/{branch_name}", sha=base_ref.object.sha)
            except GithubException:
                logger.warning(f"Branch {branch_name} may already exist, proceeding to update it.")
            
            base_tree = repo.get_git_tree(base_ref.object.sha)
            
            # Create a blob for each changed file
            elements = []
            for filepath, content in files_content.items():
                blob = repo.create_git_blob(content, "utf-8")
                elements.append(
                    InputGitTreeElement(path=filepath, mode='100644', type='blob', sha=blob.sha)
                )
                
            # Create new tree with all blob changes batched together
            new_tree = repo.create_git_tree(elements, base_tree)
            parent = repo.get_git_commit(base_ref.object.sha)
            commit = repo.create_git_commit(message=title, tree=new_tree, parents=[parent])
            
            # Update the branch reference to point to the new commit
            ref = repo.get_git_ref(f"heads/{branch_name}")
            ref.edit(commit.sha)
            
            # Create the actual PR
            pr = repo.create_pull(title=title, body=body, head=branch_name, base=base_branch)
            return pr.html_url
            
        except GithubException as e:
            raise RuntimeError(
                f"Failed to create PR. Ensure your GitHub token has write access to {owner}/{repo_name}. Detail: {e.data.get('message', str(e))}"
            ) from e

    # ── Rate Limit Info ───────────────────────────────────────────────────────

    def get_rate_limit_info(self) -> Dict:
        """Return current GitHub API rate limit information."""
        try:
            rl = self._gh.get_rate_limit()
            return {
                "core_remaining": rl.core.remaining,
                "core_limit": rl.core.limit,
                "reset_at": str(rl.core.reset),
            }
        except Exception:
            return {}
