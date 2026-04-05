import json
import os
import time
from collections import defaultdict
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import re

import requests

from .github_loader import GITHUB_API_BASE, GitHubAPIError, _build_headers
from .ingest import _get_repo_paths
from redis_storage import save_json


MAX_COMMITS = 500
MAX_DETAIL_COMMITS = 50
MAX_RAW_CONTRIBUTORS = 20  # Fetch more raw authors initially for merging
MAX_FINAL_CONTRIBUTORS = 10  # Final limit after fuzzy merging
MAX_WORKERS = 5
TIMEOUT_SECONDS = 30
COMMITS_PAGE_SIZE = 100
DETAIL_DELAY_SECONDS = 0.15
MIN_COMMITS_PER_CONTRIBUTOR = 2
RATE_LIMIT_THRESHOLD = 25

# ======================================================
# Author merging functions (moved from backend router)
# ======================================================

def _normalize_name(name: str) -> str:
    return re.sub(r'[^a-z0-9]', '', name.lower().strip())


def _extract_name_parts(name: str) -> set:
    tokens = re.split(r'[\s._\-@+]+', name.lower().strip())
    parts = set()
    for t in tokens:
        if len(t) < 2 or t.isdigit():
            continue
        parts.add(t)
        stripped = re.sub(r'\d+$', '', t)
        if stripped and len(stripped) >= 2:
            parts.add(stripped)
    return parts


def _names_match(a: str, b: str) -> bool:
    na, nb = _normalize_name(a), _normalize_name(b)
    if na == nb:
        return True
    if len(na) >= 3 and len(nb) >= 3 and (na in nb or nb in na):
        return True
    pa, pb = _extract_name_parts(a), _extract_name_parts(b)
    if pa and pb and {t for t in (pa & pb) if len(t) >= 3}:
        return True
    return False


def _get_display_name(data: dict, email: str) -> str:
    for c in data.get("recent_commits", []):
        n = c.get("author_name", "")
        if n and " " in n:
            return n
    if data.get("recent_commits"):
        return data["recent_commits"][0].get("author_name", email)
    return email


def _merge_authors(authors_raw: dict) -> list:
    """Merge authors and return sorted list of {name, data} dicts."""
    if not authors_raw:
        return []

    entries = []
    for email, data in authors_raw.items():
        display = _get_display_name(data, email)
        all_names = {email, display}
        for c in data.get("recent_commits", []):
            n = c.get("author_name", "")
            if n:
                all_names.add(n)
        entries.append((email, data, display, all_names))

    groups, assigned = [], set()
    for i, (_, _, _, names_i) in enumerate(entries):
        if i in assigned:
            continue
        group = [i]
        assigned.add(i)
        for j, (_, _, _, names_j) in enumerate(entries):
            if j in assigned:
                continue
            if any(_names_match(a, b) for a in names_i for b in names_j):
                group.append(j)
                assigned.add(j)
        groups.append(group)

    result = []
    for group in groups:
        merged = {
            "commits": 0, "files_changed": 0,
            "lines_added": 0, "lines_deleted": 0, "net_lines": 0,
            "first_commit": None, "last_commit": None,
            "recent_commits": [], "emails": [],
        }
        for idx in group:
            email, data, _, _ = entries[idx]
            merged["commits"] += data.get("commits", 0)
            merged["files_changed"] += data.get("files_changed", 0)
            merged["lines_added"] += data.get("lines_added", 0)
            merged["lines_deleted"] += data.get("lines_deleted", 0)
            merged["net_lines"] += data.get("net_lines", 0)
            merged["emails"].append(email)
            fc, lc = data.get("first_commit"), data.get("last_commit")
            if fc and (not merged["first_commit"] or str(fc) < str(merged["first_commit"])):
                merged["first_commit"] = fc
            if lc and (not merged["last_commit"] or str(lc) > str(merged["last_commit"])):
                merged["last_commit"] = lc
            merged["recent_commits"].extend(data.get("recent_commits", []))

        merged["recent_commits"] = sorted(
            merged["recent_commits"], key=lambda c: c.get("date", ""), reverse=True
        )[:5]

        best_name = None
        for idx in group:
            if " " in entries[idx][2]:
                best_name = entries[idx][2]
                break
        if not best_name:
            best_name = entries[group[0]][2]

        result.append({"name": best_name, **merged})

    result.sort(key=lambda x: -x["commits"])
    return result


MAX_COMMITS = 500
MAX_DETAIL_COMMITS = 50
MAX_RAW_CONTRIBUTORS = 20  # Fetch more raw authors initially for merging
MAX_FINAL_CONTRIBUTORS = 10  # Final limit after fuzzy merging
MAX_WORKERS = 5
TIMEOUT_SECONDS = 30
COMMITS_PAGE_SIZE = 100
DETAIL_DELAY_SECONDS = 0.15
MIN_COMMITS_PER_CONTRIBUTOR = 2
RATE_LIMIT_THRESHOLD = 25

# ======================================================
# File filtering — only count lines from meaningful code files
# Mirrors the ingestion pipeline's EXTENSIONS and SKIP rules
# ======================================================
CODE_EXTENSIONS = {
    ".py", ".js", ".java", ".ts", ".tsx", ".jsx",
    ".go", ".cpp", ".c", ".h", ".hpp", ".rs",
    ".md", ".txt", ".css", ".scss", ".html",
    ".rb", ".php", ".swift", ".kt", ".scala",
    ".sh", ".bash", ".sql", ".yaml", ".yml",
}

SKIP_DIR_PARTS = {
    "node_modules", ".git", ".github", "__pycache__", ".venv", "venv",
    "dist", "build", ".next", "coverage", "vendor", "third_party",
    "target", "out", ".turbo", ".gradle", ".idea", ".pytest_cache",
}

SKIP_FILE_NAMES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "poetry.lock", "cargo.lock", "composer.lock",
}

SKIP_SUFFIXES = (
    ".min.js", ".min.css", ".bundle.js",
    ".generated.js", ".generated.ts", ".generated.tsx",
    ".g.dart", ".pb.go", ".designer.cs",
)


def _is_code_file(filename: str) -> bool:
    """Check if a file is a meaningful code file worth counting in contributions."""
    if not filename:
        return False

    lower = filename.lower()
    base = lower.rsplit("/", 1)[-1] if "/" in lower else lower

    # Skip known non-code files
    if base in SKIP_FILE_NAMES:
        return False

    # Skip generated/minified files
    if any(lower.endswith(s) for s in SKIP_SUFFIXES):
        return False

    # Skip files inside non-code directories
    parts = set(lower.replace("\\", "/").split("/"))
    if parts & SKIP_DIR_PARTS:
        return False

    # Check extension
    _, ext = os.path.splitext(lower)
    return ext in CODE_EXTENSIONS


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_author(commit_item: Dict[str, Any]) -> Dict[str, str]:
    author_meta = commit_item.get("author") or {}
    commit_author = (commit_item.get("commit") or {}).get("author") or {}

    raw_name = (
        commit_author.get("name")
        or author_meta.get("login")
        or commit_author.get("email")
        or "unknown"
    )
    raw_email = (
        commit_author.get("email")
        or author_meta.get("email")
        or (f"{author_meta.get('login')}@users.noreply.github.com" if author_meta.get("login") else None)
        or f"{raw_name}@local"
    )

    return {
        "name": str(raw_name).strip() or "unknown",
        "email": str(raw_email).strip().lower() or "unknown@local",
    }


def _is_bot(author_name: str, author_email: str) -> bool:
    lowered_name = author_name.lower()
    lowered_email = author_email.lower()
    return "[bot]" in lowered_name or "[bot]" in lowered_email or lowered_email.endswith("bot@users.noreply.github.com")


def _sleep_if_rate_limited(headers: Dict[str, Any]) -> None:
    remaining = headers.get("X-RateLimit-Remaining")
    reset_at = headers.get("X-RateLimit-Reset")
    try:
        remaining_int = int(remaining) if remaining is not None else None
    except (TypeError, ValueError):
        remaining_int = None

    if remaining_int is None or remaining_int >= RATE_LIMIT_THRESHOLD or not reset_at:
        return

    try:
        reset_seconds = int(reset_at) - int(time.time())
    except (TypeError, ValueError):
        reset_seconds = 1

    time.sleep(max(1, min(reset_seconds, 60)))


def _request_json_with_headers(
    path: str,
    token: Optional[str],
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    url = f"{GITHUB_API_BASE}{path}"
    backoff = 1.0

    for attempt in range(4):
        response = requests.get(url, headers=_build_headers(token), params=params, timeout=TIMEOUT_SECONDS)
        _sleep_if_rate_limited(response.headers)

        if response.status_code == 200:
            return response.json()

        if response.status_code == 403 and attempt < 3:
            time.sleep(min(backoff, 15))
            backoff *= 2
            continue

        if response.status_code in (500, 502, 503, 504) and attempt < 3:
            time.sleep(min(backoff, 15))
            backoff *= 2
            continue

        raise GitHubAPIError(
            f"GitHub API request failed ({response.status_code}) for {path}: {response.text[:300]}"
        )

    raise GitHubAPIError(f"GitHub API request exceeded retries for {path}")


def fetch_commits(
    owner: str,
    repo: str,
    token: Optional[str],
    max_commits: int = MAX_COMMITS,
    branch: Optional[str] = None,
    stop_sha: Optional[str] = None,
    start_time: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """Fetch recent commits using pagination, bounded for large repositories."""
    commits: List[Dict[str, Any]] = []
    page = 1

    while len(commits) < max_commits:
        if start_time and (time.time() - start_time) >= TIMEOUT_SECONDS:
            break

        params: Dict[str, Any] = {
            "per_page": min(COMMITS_PAGE_SIZE, max_commits - len(commits)),
            "page": page,
        }
        if branch:
            params["sha"] = branch

        try:
            payload = _request_json_with_headers(f"/repos/{owner}/{repo}/commits", token=token, params=params)
        except Exception as exc:
            print(f"Failed to fetch commit page {page} for {owner}/{repo}: {exc}")
            break

        page_items = payload if isinstance(payload, list) else []
        if not page_items:
            break

        for item in page_items:
            full_sha = item.get("sha") or ""
            if stop_sha and full_sha == stop_sha:
                return commits

            identity = _normalize_author(item)
            commit = item.get("commit") or {}
            author = commit.get("author") or {}
            commits.append(
                {
                    "sha": full_sha[:7],
                    "full_sha": full_sha,
                    "author_name": identity["name"],
                    "author_email": identity["email"],
                    "date": author.get("date"),
                    "message": (commit.get("message") or "").strip().split("\n")[0],
                }
            )
            if len(commits) >= max_commits:
                break

        if len(page_items) < COMMITS_PAGE_SIZE:
            break
        page += 1

    return commits


def fetch_commit_details(
    owner: str,
    repo: str,
    sha: str,
    token: Optional[str],
) -> Dict[str, Any]:
    """Fetch detailed stats for a single commit, counting only meaningful code files."""
    try:
        payload = _request_json_with_headers(f"/repos/{owner}/{repo}/commits/{sha}", token=token)
    except Exception as exc:
        raise GitHubAPIError(f"Failed to fetch commit details for {sha}: {exc}") from exc

    files = payload.get("files", []) or []

    # Filter to code files only and sum their per-file stats
    filtered_additions = 0
    filtered_deletions = 0
    filtered_files = []

    for entry in files:
        filename = entry.get("filename", "")
        if _is_code_file(filename):
            filtered_additions += int(entry.get("additions", 0) or 0)
            filtered_deletions += int(entry.get("deletions", 0) or 0)
            filtered_files.append(filename)

    return {
        "sha": payload.get("sha", sha),
        "additions": filtered_additions,
        "deletions": filtered_deletions,
        "files_changed": filtered_files,
    }


def _empty_payload() -> Dict[str, Any]:
    return {
        "contributors": [],
        "total_commits": 0,
        "last_updated": _utc_now(),
        "total_authors": 0,
        "authors": {},
        "analysis_scope": {
            "commit_sample_size": 0,
            "detail_commit_sample_size": 0,
            "head_commit_sha": None,
            "last_processed_commit_sha": None,
            "fallback_mode": True,
            "timed_out": False,
        },
    }


def _load_previous_authors(existing_data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not existing_data:
        return {}
    authors = existing_data.get("authors", {})
    return authors if isinstance(authors, dict) else {}


def _merge_recent_commits(existing: List[Dict[str, Any]], new: List[Dict[str, Any]], limit: int = 5) -> List[Dict[str, Any]]:
    merged: Dict[str, Dict[str, Any]] = {}
    for commit in existing + new:
        sha = commit.get("sha")
        if sha and sha not in merged:
            merged[sha] = commit
    ordered = sorted(merged.values(), key=lambda item: item.get("date") or "", reverse=True)
    return ordered[:limit]


def _build_commit_only_author_state(existing_data: Optional[Dict[str, Any]] = None) -> Dict[str, Dict[str, Any]]:
    author_state: Dict[str, Dict[str, Any]] = {}
    for email, author in _load_previous_authors(existing_data).items():
        author_state[email] = {
            "name": author.get("recent_commits", [{}])[0].get("author_name", email),
            "commits": int(author.get("commits", 0) or 0),
            "lines_added": int(author.get("lines_added", 0) or 0),
            "lines_deleted": int(author.get("lines_deleted", 0) or 0),
            "files_changed": set(),
            "first_commit": author.get("first_commit"),
            "last_commit": author.get("last_commit"),
            "recent_commits": list(author.get("recent_commits", [])),
        }
    return author_state


def _update_author_state(author_state: Dict[str, Dict[str, Any]], commits: List[Dict[str, Any]]) -> None:
    for commit in commits:
        email = commit["author_email"]
        state = author_state.setdefault(
            email,
            {
                "name": commit["author_name"],
                "commits": 0,
                "lines_added": 0,
                "lines_deleted": 0,
                "files_changed": set(),
                "first_commit": None,
                "last_commit": None,
                "recent_commits": [],
            },
        )
        state["name"] = state.get("name") or commit["author_name"]
        state["commits"] += 1

        commit_date = commit.get("date")
        if commit_date:
            if state["first_commit"] is None or commit_date < state["first_commit"]:
                state["first_commit"] = commit_date
            if state["last_commit"] is None or commit_date > state["last_commit"]:
                state["last_commit"] = commit_date

        state["recent_commits"] = _merge_recent_commits(
            state.get("recent_commits", []),
            [
                {
                    "sha": commit.get("sha", ""),
                    "message": commit.get("message", ""),
                    "date": commit.get("date"),
                    "author_name": commit.get("author_name", "Unknown"),
                    "author_email": email,
                }
            ],
        )


def _filter_and_rank_authors(author_state: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    ranked: List[Dict[str, Any]] = []
    for email, state in author_state.items():
        if _is_bot(state.get("name", ""), email):
            continue
        if int(state.get("commits", 0) or 0) < MIN_COMMITS_PER_CONTRIBUTOR:
            continue
        ranked.append(
            {
                "email": email,
                "name": state.get("name", email),
                "commits": int(state.get("commits", 0) or 0),
                "lines_added": int(state.get("lines_added", 0) or 0),
                "lines_deleted": int(state.get("lines_deleted", 0) or 0),
                "files_changed_set": state.get("files_changed", set()),
                "first_commit": state.get("first_commit"),
                "last_commit": state.get("last_commit"),
                "recent_commits": list(state.get("recent_commits", [])),
            }
        )

    ranked.sort(key=lambda item: (-item["commits"], item["name"].lower(), item["email"]))
    return ranked[:MAX_RAW_CONTRIBUTORS]


def _fetch_detail_stats_parallel(
    owner: str,
    repo: str,
    commits: List[Dict[str, Any]],
    token: Optional[str],
    start_time: float,
) -> Dict[str, Dict[str, Any]]:
    detail_stats: Dict[str, Dict[str, Any]] = {}
    if not commits:
        return detail_stats

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {}
        commit_iter = iter(commits[:MAX_DETAIL_COMMITS])

        def submit_more() -> None:
            while len(futures) < MAX_WORKERS:
                try:
                    commit = next(commit_iter)
                except StopIteration:
                    break
                full_sha = commit.get("full_sha") or ""
                if not full_sha:
                    continue
                futures[executor.submit(fetch_commit_details, owner, repo, full_sha, token)] = full_sha
                time.sleep(DETAIL_DELAY_SECONDS)

        submit_more()
        while futures:
            remaining = TIMEOUT_SECONDS - (time.time() - start_time)
            if remaining <= 0:
                break
            done, _ = wait(list(futures.keys()), timeout=min(remaining, 5), return_when=FIRST_COMPLETED)
            if not done:
                break
            for future in done:
                full_sha = futures.pop(future)
                try:
                    detail_stats[full_sha] = future.result()
                except Exception as exc:
                    print(f"Skipping detail stats for {full_sha[:7]}: {exc}")
                submit_more()

    return detail_stats


def _apply_detail_stats(
    author_state: Dict[str, Dict[str, Any]],
    commits: List[Dict[str, Any]],
    detail_stats: Dict[str, Dict[str, Any]],
) -> None:
    for commit in commits[:MAX_DETAIL_COMMITS]:
        full_sha = commit.get("full_sha") or ""
        details = detail_stats.get(full_sha)
        if not details:
            continue
        email = commit["author_email"]
        state = author_state.get(email)
        if not state:
            continue
        state["lines_added"] += details.get("additions", 0)
        state["lines_deleted"] += details.get("deletions", 0)
        state["files_changed"].update(details.get("files_changed", []))


def _serialize_payload(
    author_state: Dict[str, Dict[str, Any]],
    commits: List[Dict[str, Any]],
    head_commit_sha: Optional[str],
    detail_count: int,
    fallback_mode: bool,
    timed_out: bool,
) -> Dict[str, Any]:
    ranked = _filter_and_rank_authors(author_state)

    # Convert ranked list to dict format for merging
    authors_dict = {}
    for item in ranked:
        authors_dict[item["email"]] = {
            "commits": item["commits"],
            "files_changed": len(item["files_changed_set"]),
            "lines_added": item["lines_added"],
            "lines_deleted": item["lines_deleted"],
            "net_lines": item["lines_added"] - item["lines_deleted"],
            "first_commit": item["first_commit"],
            "last_commit": item["last_commit"],
            "recent_commits": item["recent_commits"],
        }

    # Apply fuzzy merging
    merged_authors = _merge_authors(authors_dict)

    # Limit to final number of contributors
    merged_authors = merged_authors[:MAX_FINAL_CONTRIBUTORS]

    # Convert merged authors back to dict format for storage
    authors_payload: Dict[str, Any] = {}
    contributors: List[Dict[str, Any]] = []
    for author in merged_authors:
        # Use the first email as the key for the merged author
        primary_email = author["emails"][0] if author.get("emails") else f"{author['name'].lower().replace(' ', '.')}@merged"
        authors_payload[primary_email] = {
            "name": author["name"],
            "commits": author["commits"],
            "files_changed": author["files_changed"],
            "lines_added": author["lines_added"],
            "lines_deleted": author["lines_deleted"],
            "net_lines": author["net_lines"],
            "first_commit": author["first_commit"],
            "last_commit": author["last_commit"],
            "recent_commits": author["recent_commits"],
            "emails": author["emails"],  # Mark as merged
        }
        contributors.append(
            {
                "name": author["name"],
                "email": primary_email,
                "commits": author["commits"],
                "lines_added": author["lines_added"],
                "lines_deleted": author["lines_deleted"],
                "files_changed": author["files_changed"],
                "first_commit": author["first_commit"],
                "last_commit": author["last_commit"],
            }
        )

    return {
        "contributors": contributors,
        "total_commits": len(commits),
        "last_updated": _utc_now(),
        "last_processed_commit_sha": head_commit_sha,
        "total_authors": len(authors_payload),
        "authors": authors_payload,
        "analysis_scope": {
            "commit_sample_size": len(commits),
            "detail_commit_sample_size": detail_count,
            "head_commit_sha": head_commit_sha,
            "last_processed_commit_sha": head_commit_sha,
            "fallback_mode": fallback_mode,
            "timed_out": timed_out,
        },
    }


def extract_contributions_via_api(
    owner: str,
    repo: str,
    token: Optional[str],
    branch: Optional[str] = None,
    max_commits: int = MAX_COMMITS,
    detail_commit_limit: int = MAX_DETAIL_COMMITS,
    existing_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Compute contributor statistics with strict time and API-use bounds."""
    start_time = time.time()
    max_commits = min(max_commits, MAX_COMMITS)
    detail_commit_limit = min(detail_commit_limit, MAX_DETAIL_COMMITS)

    previous_head_sha = (
        existing_data.get("analysis_scope", {}).get("last_processed_commit_sha")
        if existing_data
        else None
    )

    try:
        commits = fetch_commits(
            owner,
            repo,
            token,
            max_commits=max_commits,
            branch=branch,
            start_time=start_time,
        )
    except Exception as exc:
        print(f"Failed to fetch commits for {owner}/{repo}: {exc}")
        return existing_data or _empty_payload()

    if not commits:
        return existing_data or _empty_payload()

    head_commit_sha = commits[0].get("full_sha")
    if existing_data and previous_head_sha == head_commit_sha:
        return existing_data

    timed_out = (time.time() - start_time) >= TIMEOUT_SECONDS
    incremental_commits = []
    if previous_head_sha:
        incremental_commits = fetch_commits(
            owner,
            repo,
            token,
            max_commits=max_commits,
            branch=branch,
            stop_sha=previous_head_sha,
            start_time=start_time,
        )

    author_state = _build_commit_only_author_state(existing_data if incremental_commits else None)
    _update_author_state(author_state, incremental_commits or commits)

    fallback_mode = False
    detail_stats: Dict[str, Dict[str, Any]] = {}
    detail_source_commits = commits[:detail_commit_limit]
    if not timed_out:
        try:
            detail_stats = _fetch_detail_stats_parallel(
                owner,
                repo,
                detail_source_commits,
                token,
                start_time,
            )
        except Exception as exc:
            print(f"Falling back to commit-only contribution stats for {owner}/{repo}: {exc}")
            fallback_mode = True
    else:
        fallback_mode = True

    if (time.time() - start_time) >= TIMEOUT_SECONDS:
        timed_out = True
        fallback_mode = True

    if detail_stats:
        for state in author_state.values():
            state["lines_added"] = 0
            state["lines_deleted"] = 0
            state["files_changed"] = set()
        _apply_detail_stats(author_state, detail_source_commits, detail_stats)
    else:
        for state in author_state.values():
            state["lines_added"] = 0
            state["lines_deleted"] = 0
            state["files_changed"] = set()

    payload = _serialize_payload(
        author_state,
        commits,
        head_commit_sha,
        detail_count=len(detail_stats),
        fallback_mode=fallback_mode,
        timed_out=timed_out,
    )
    return payload


def save_contributions(repo_name: str, data: Dict[str, Any]) -> str:
    """Save contributions data to Redis."""
    return save_json(repo_name, "contributions", data)