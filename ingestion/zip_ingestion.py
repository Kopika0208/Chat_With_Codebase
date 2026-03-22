# zip_ingestion.py - ZIP-based repository ingestion for large repos

import io
import os
import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Optional, Tuple

import requests

from .utils import SKIP_DIR_NAMES, should_skip


GITHUB_API_BASE = "https://api.github.com"
MAX_RETRIES = 4
DEFAULT_TIMEOUT = 30
MAX_FILE_BYTES = 1_500_000


def _get_zip_download_url(owner: str, repo: str, branch: str = "main") -> str:
    """Construct the ZIP download URL for GitHub."""
    return f"{GITHUB_API_BASE}/repos/{owner}/{repo}/zipball/{branch}"


def _download_zipball(owner: str, repo: str, branch: str, token: Optional[str], dest_path: str) -> None:
    """Download repository zipball from GitHub API with retry logic and rate limit handling."""
    url = _get_zip_download_url(owner, repo, branch)
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    headers.update({
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "CodebaseChat/1.0",
    })

    backoff = 1.0
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(url, headers=headers, timeout=DEFAULT_TIMEOUT, stream=True)

            # Check rate limit headers
            remaining = response.headers.get("X-RateLimit-Remaining")
            reset_at = response.headers.get("X-RateLimit-Reset")
            if remaining:
                print(f"GitHub API rate limit: {remaining} requests remaining")
                if remaining == "0" and reset_at:
                    wait_seconds = max(1, int(reset_at) - int(datetime.now(timezone.utc).timestamp()))
                    print(f"Rate limit reached. Waiting {wait_seconds} seconds...")
                    import time
                    time.sleep(min(wait_seconds, 60))

            if response.status_code == 200:
                # Stream download to avoid memory overload
                with open(dest_path, "wb") as handle:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            handle.write(chunk)
                print(f"Downloaded {owner}/{repo} ({branch}) to {dest_path}")
                return

            if response.status_code in (403, 429):
                # Rate limited or forbidden
                if attempt < MAX_RETRIES - 1:
                    wait_time = min(int(backoff), 15)
                    print(f"Rate limit or authentication error ({response.status_code}). Retrying in {wait_time}s...")
                    import time
                    time.sleep(wait_time)
                    backoff *= 2
                    continue

            if response.status_code in (500, 502, 503, 504):
                # Server error
                if attempt < MAX_RETRIES - 1:
                    wait_time = min(int(backoff), 15)
                    print(f"Server error ({response.status_code}). Retrying in {wait_time}s...")
                    import time
                    time.sleep(wait_time)
                    backoff *= 2
                    continue

            raise RuntimeError(
                f"Failed to download zipball ({response.status_code}): {response.text[:300]}"
            )

        except requests.RequestException as e:
            if attempt < MAX_RETRIES - 1:
                wait_time = min(int(backoff), 15)
                print(f"Network error during download: {e}. Retrying in {wait_time}s...")
                import time
                time.sleep(wait_time)
                backoff *= 2
            else:
                raise RuntimeError(f"Failed to download zipball after {MAX_RETRIES} retries: {e}") from e

    raise RuntimeError(f"Failed to download zipball: exhausted retries")


def _extract_zipball(zip_path: str, extract_dir: str) -> str:
    """Extract ZIP file and return the actual repository root directory."""
    import zipfile

    print(f"Extracting ZIP to {extract_dir}...")
    
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_dir)
    except Exception as e:
        raise RuntimeError(f"Failed to extract zipball: {e}") from e

    # GitHub zipballs have a single root directory like "owner-repo-sha/"
    # We need to find and return that directory
    entries = os.listdir(extract_dir)
    if len(entries) == 1:
        repo_root = os.path.join(extract_dir, entries[0])
        if os.path.isdir(repo_root):
            return repo_root
    
    # If no single root, return the extract directory itself
    return extract_dir


def download_and_extract_repo(
    owner: str,
    repo: str,
    branch: str = "main",
    token: Optional[str] = None,
) -> Tuple[str, str, str]:
    """
    Download and extract a GitHub repository as ZIP.
    
    Returns:
        Tuple of (extracted_repo_path, temp_zip_path, cleanup_root)
        - extracted_repo_path: Path to the extracted repository
        - temp_zip_path: Path to the ZIP file (for cleanup)
        - cleanup_root: Root temp directory (for cleanup)
    """
    # Create temp directory
    cleanup_root = tempfile.mkdtemp(prefix=f"{repo}_")
    zip_path = os.path.join(cleanup_root, f"{repo}.zip")
    extract_dir = os.path.join(cleanup_root, "extracted")
    
    try:
        # Download ZIP
        print(f"Downloading {owner}/{repo} ({branch}) via ZIP...")
        _download_zipball(owner, repo, branch, token, zip_path)
        
        # Extract ZIP
        repo_path = _extract_zipball(zip_path, extract_dir)
        
        print(f"Repository ready at: {repo_path}")
        return repo_path, zip_path, cleanup_root
        
    except Exception as e:
        # Cleanup on failure
        if os.path.exists(cleanup_root):
            shutil.rmtree(cleanup_root, ignore_errors=True)
        raise RuntimeError(f"Failed to download and extract repository: {e}") from e


def list_files_from_zip(repo_path: str, extensions: tuple):
    """
    Stream files from an extracted ZIP repository.
    
    Similar to utils.list_repo_files but for ZIP-extracted repos.
    This is memory-safe and doesn't load all files at once.
    """
    normalized_exts = tuple(ext.lower() for ext in extensions)
    
    for root, dirs, files in os.walk(repo_path):
        # Prune directories to skip
        dirs[:] = [d for d in dirs if d.lower() not in SKIP_DIR_NAMES]
        
        for file_name in files:
            file_path = os.path.join(root, file_name)
            
            # Check extension
            if not file_path.lower().endswith(normalized_exts):
                continue
            
            # Check if should skip
            if should_skip(file_path, repo_path, max_file_bytes=MAX_FILE_BYTES):
                continue
            
            yield file_path


def cleanup_zip_extraction(zip_path: str, cleanup_root: str) -> None:
    """Clean up temporary ZIP and extraction directories."""
    try:
        if os.path.exists(zip_path):
            os.remove(zip_path)
            print(f"Deleted ZIP file: {zip_path}")
    except Exception as e:
        print(f"Warning: Failed to delete ZIP file {zip_path}: {e}")
    
    try:
        if os.path.exists(cleanup_root):
            shutil.rmtree(cleanup_root, ignore_errors=True)
            print(f"Deleted temporary directory: {cleanup_root}")
    except Exception as e:
        print(f"Warning: Failed to delete temporary directory {cleanup_root}: {e}")


def get_repo_size_estimation(owner: str, repo: str, token: Optional[str]) -> int:
    """
    Get repository size in KB from GitHub API metadata.
    
    Returns:
        Size in kilobytes (0 if unable to fetch)
    """
    try:
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        
        headers.update({
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        })
        
        response = requests.get(
            f"{GITHUB_API_BASE}/repos/{owner}/{repo}",
            headers=headers,
            timeout=DEFAULT_TIMEOUT
        )
        
        if response.status_code == 200:
            data = response.json()
            size_kb = data.get("size", 0)  # Size is in KB
            return size_kb
        
        print(f"Warning: Could not fetch repo metadata ({response.status_code})")
        return 0
        
    except Exception as e:
        print(f"Warning: Failed to fetch repo size: {e}")
        return 0
