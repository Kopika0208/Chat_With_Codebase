"""Contribution analytics endpoint with fuzzy author merging."""

import re
import os
from fastapi import APIRouter, HTTPException
from backend.deps import list_repos, load_contributions

router = APIRouter(prefix="/api/repos/{repo_name}", tags=["contributions"])


# ── Author merging (same logic as contributions_viz.py) ──

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


@router.get("/contributions")
def get_contributions(repo_name: str):
    """Get contribution analytics with merged authors."""
    if repo_name not in list_repos():
        raise HTTPException(status_code=404, detail=f"Repository '{repo_name}' not found")

    raw = load_contributions(repo_name)
    if not raw or not raw.get("authors"):
        return {"authors": [], "total_commits": 0, "total_authors": 0, "analysis_scope": {}}

    # Check if data is already merged (has 'emails' field indicating merged authors)
    authors_dict = raw.get("authors", {})
    is_already_merged = any(isinstance(data, dict) and "emails" in data for data in authors_dict.values())

    if is_already_merged:
        # Data is already merged, convert to expected format
        merged = []
        for email, data in authors_dict.items():
            merged.append({
                "name": data.get("name", email),
                "commits": data.get("commits", 0),
                "files_changed": data.get("files_changed", 0),
                "lines_added": data.get("lines_added", 0),
                "lines_deleted": data.get("lines_deleted", 0),
                "net_lines": data.get("net_lines", 0),
                "first_commit": data.get("first_commit"),
                "last_commit": data.get("last_commit"),
                "recent_commits": data.get("recent_commits", []),
                "emails": data.get("emails", [email]),
            })
    else:
        # Apply merging to raw data
        merged = _merge_authors(authors_dict)

    return {
        "authors": merged,
        "total_commits": raw.get("total_commits", sum(a["commits"] for a in merged)),
        "total_authors": len(merged),
        "analysis_scope": raw.get("analysis_scope", {}),
    }
