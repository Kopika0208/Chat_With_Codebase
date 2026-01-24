# utils.py - Helper functions for repository ingestion

import os
from datetime import timezone
from git import Repo


def clone_or_open_repo(repo_url: str, target_dir: str) -> str:
    """Clone a repository from a URL or open an existing local repo."""
    if repo_url.startswith("http"):
        if os.path.exists(target_dir):
            print("♻️ Repo exists — removing for fresh clone.")
            import shutil
            shutil.rmtree(target_dir, ignore_errors=True)
        print(f"📥 Cloning {repo_url} → {target_dir}")
        os.makedirs(os.path.dirname(target_dir), exist_ok=True)
        Repo.clone_from(repo_url, target_dir)
    else:
        # Local path - ensure it exists
        if not os.path.exists(repo_url):
            raise ValueError(f"Local repository path does not exist: {repo_url}")
        target_dir = repo_url
    return os.path.abspath(target_dir)


def list_repo_files(repo_path: str, extensions: tuple):
    """Iterate over files in repository matching specified extensions."""
    for root, _, files in os.walk(repo_path):
        if any(ignored in root for ignored in [".git", "venv", "node_modules", "__pycache__"]):
            continue
        for f in files:
            if f.endswith(extensions):
                yield os.path.join(root, f)


def get_commit_info(repo_path: str, file_path: str):
    """Get commit SHA, message, and date for a file."""
    try:
        repo = Repo(repo_path)
        rel = os.path.relpath(file_path, repo_path)
        commit = next(repo.iter_commits(paths=rel, max_count=1))
        try:
            dt = commit.committed_datetime.astimezone(timezone.utc).isoformat()
        except Exception:
            dt = None
        return commit.hexsha[:7], commit.message.strip().split("\n")[0], dt
    except Exception:
        return "unknown", "No commit message found", None
