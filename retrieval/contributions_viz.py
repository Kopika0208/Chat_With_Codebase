"""
Contribution analytics visualization for Streamlit.
Displays code contribution metrics, commit history, and author statistics.
Includes fuzzy author merging for users with multiple emails/usernames.
"""

import streamlit as st
import json
import os
import re
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from collections import defaultdict


def load_contributions_data(repo_name: str) -> Optional[Dict]:
    """Load contributions data from the data directory."""
    try:
        contributions_path = os.path.join("data", repo_name, "contributions.json")
        if os.path.exists(contributions_path):
            with open(contributions_path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"⚠️ Error loading contributions data: {e}")
    return None


# ======================================================
# 🔀 AUTHOR MERGING
# ======================================================

def _normalize_name(name: str) -> str:
    """Normalize a name for comparison: lowercase, strip whitespace/punctuation."""
    return re.sub(r'[^a-z0-9]', '', name.lower().strip())


def _extract_name_parts(name: str) -> set:
    """Extract meaningful tokens from a name or username."""
    # Split on common separators
    tokens = re.split(r'[\s._\-@+]+', name.lower().strip())
    parts = set()
    for t in tokens:
        if len(t) < 2:
            continue
        if t.isdigit():
            continue
        parts.add(t)
        # Also add version with trailing digits stripped (e.g. "kopika0208" -> "kopika")
        stripped = re.sub(r'\d+$', '', t)
        if stripped and len(stripped) >= 2:
            parts.add(stripped)
    return parts


def _names_match(name_a: str, name_b: str) -> bool:
    """
    Check if two author identifiers likely refer to the same person.
    
    Matches:
      - "Kopika Muralidharan" vs "Kopika0208" (shared token "kopika")
      - "john.doe@gmail.com" vs "johndoe@company.com" (shared tokens)
      - "JDoe" vs "John Doe" (first token overlap)
    """
    norm_a = _normalize_name(name_a)
    norm_b = _normalize_name(name_b)
    
    # Exact normalized match
    if norm_a == norm_b:
        return True
    
    # One contains the other
    if len(norm_a) >= 3 and len(norm_b) >= 3:
        if norm_a in norm_b or norm_b in norm_a:
            return True
    
    # Token overlap (at least one meaningful shared token)
    parts_a = _extract_name_parts(name_a)
    parts_b = _extract_name_parts(name_b)
    
    if parts_a and parts_b:
        shared = parts_a & parts_b
        # Require at least one shared token of length >= 3
        meaningful_shared = {t for t in shared if len(t) >= 3}
        if meaningful_shared:
            return True
    
    return False


def _get_display_name(author_data: Dict, email: str) -> str:
    """Get the best display name for an author from their commit history."""
    recent = author_data.get("recent_commits", [])
    if recent:
        for commit in recent:
            name = commit.get("author_name", "")
            # Prefer real names over usernames (real names have spaces)
            if name and " " in name:
                return name
        # Fallback: first commit author_name
        return recent[0].get("author_name", email)
    return email


def _merge_author_data(entries: List[Tuple[str, Dict]]) -> Dict:
    """Merge multiple author entries into one combined entry."""
    merged = {
        "commits": 0,
        "files_changed": 0,
        "lines_added": 0,
        "lines_deleted": 0,
        "net_lines": 0,
        "first_commit": None,
        "last_commit": None,
        "recent_commits": [],
        "_emails": [],
    }
    
    for email, data in entries:
        merged["commits"] += data.get("commits", 0)
        merged["files_changed"] += data.get("files_changed", 0)
        merged["lines_added"] += data.get("lines_added", 0)
        merged["lines_deleted"] += data.get("lines_deleted", 0)
        merged["net_lines"] += data.get("net_lines", 0)
        merged["_emails"].append(email)
        
        fc = data.get("first_commit")
        lc = data.get("last_commit")
        
        if fc:
            if merged["first_commit"] is None or fc < merged["first_commit"]:
                merged["first_commit"] = fc
        if lc:
            if merged["last_commit"] is None or lc > merged["last_commit"]:
                merged["last_commit"] = lc
        
        merged["recent_commits"].extend(data.get("recent_commits", []))
    
    # Sort recent commits and keep top 5
    merged["recent_commits"] = sorted(
        merged["recent_commits"],
        key=lambda c: c.get("date", ""),
        reverse=True,
    )[:5]
    
    return merged


def merge_authors(authors: Dict[str, Dict]) -> List[Tuple[str, Dict]]:
    """
    Merge authors that appear to be the same person based on name/email similarity.
    
    Returns list of (display_name, merged_data) sorted by commits descending.
    """
    if not authors:
        return []
    
    # Build list of (email, data, display_name, all_names)
    entries = []
    for email, data in authors.items():
        display = _get_display_name(data, email)
        # Collect all name variants: email, display name, commit author names
        all_names = {email, display}
        for commit in data.get("recent_commits", []):
            name = commit.get("author_name", "")
            if name:
                all_names.add(name)
        entries.append((email, data, display, all_names))
    
    # Group by similarity using union-find style merging
    groups = []  # Each group is a list of indices into entries
    assigned = set()
    
    for i, (email_i, data_i, display_i, names_i) in enumerate(entries):
        if i in assigned:
            continue
        
        group = [i]
        assigned.add(i)
        
        for j, (email_j, data_j, display_j, names_j) in enumerate(entries):
            if j in assigned:
                continue
            
            # Check if any name from i matches any name from j
            matched = False
            for name_a in names_i:
                for name_b in names_j:
                    if _names_match(name_a, name_b):
                        matched = True
                        break
                if matched:
                    break
            
            if matched:
                group.append(j)
                assigned.add(j)
        
        groups.append(group)
    
    # Merge each group
    result = []
    for group in groups:
        group_entries = [(entries[i][0], entries[i][1]) for i in group]
        merged = _merge_author_data(group_entries)
        
        # Pick the best display name (prefer real name with space)
        best_name = None
        for i in group:
            name = entries[i][2]
            if " " in name:
                best_name = name
                break
        if not best_name:
            best_name = entries[group[0]][2]
        
        result.append((best_name, merged))
    
    # Sort by commits descending
    result.sort(key=lambda x: x[1]["commits"], reverse=True)
    return result


# ======================================================
# 🎨 RENDERING
# ======================================================

def render_contributions_tab(repo_name: str):
    """Render comprehensive contributions analytics in a Streamlit tab."""
    contributions = load_contributions_data(repo_name)
    
    if not contributions:
        st.info("📊 No contribution data available. Please ensure the repository was ingested with contribution analysis.")
        return
    
    authors_raw = contributions.get("authors", {})
    
    if not authors_raw:
        st.warning("No contribution data found in this repository.")
        return
    
    # Merge duplicate authors
    merged_authors = merge_authors(authors_raw)
    
    total_commits = sum(a["commits"] for _, a in merged_authors)
    total_authors = len(merged_authors)
    
    # ========== SUMMARY STATISTICS ==========
    st.markdown("### 📊 Contribution Summary")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("👥 Total Authors", total_authors)
    
    with col2:
        st.metric("📝 Total Commits", total_commits)
    
    total_files_changed = sum(a.get("files_changed", 0) for _, a in merged_authors)
    total_lines_added = sum(a.get("lines_added", 0) for _, a in merged_authors)
    
    with col3:
        st.metric("📁 Files Changed", total_files_changed)
    
    with col4:
        st.metric("➕ Lines Added", f"{total_lines_added:,}")
    
    st.divider()
    
    # ========== TOP CONTRIBUTORS ==========
    st.markdown("### 🏆 Top Contributors")
    
    top_n = min(15, len(merged_authors))
    
    col1, col2, col3, col4, col5 = st.columns([1, 3, 1.5, 1.5, 1.5])
    
    with col1:
        st.write("**Rank**")
    with col2:
        st.write("**Author**")
    with col3:
        st.write("**Commits**")
    with col4:
        st.write("**Files**")
    with col5:
        st.write("**Net Lines**")
    
    st.divider()
    
    for idx, (author_name, author_data) in enumerate(merged_authors[:top_n], 1):
        col1, col2, col3, col4, col5 = st.columns([1, 3, 1.5, 1.5, 1.5])
        
        commits = author_data.get("commits", 0)
        files_changed = author_data.get("files_changed", 0)
        net_lines = author_data.get("net_lines", 0)
        
        with col1:
            st.write(f"**#{idx}**")
        with col2:
            display = f"**{author_name}**"
            emails = author_data.get("_emails", [])
            if len(emails) > 1:
                display += f"  *(merged: {len(emails)} accounts)*"
            st.write(display)
        with col3:
            st.write(f"{commits}")
        with col4:
            st.write(f"{files_changed}")
        with col5:
            if net_lines > 0:
                st.write(f"🟢 **+{net_lines:,}**")
            elif net_lines < 0:
                st.write(f"🔴 **{net_lines:,}**")
            else:
                st.write(f"⚪ {net_lines}")
    
    st.divider()
    
    # ========== DETAILED AUTHOR BREAKDOWN ==========
    st.markdown("### 📋 Detailed Author Metrics")
    
    detail_count = min(5, len(merged_authors))
    if detail_count > 0:
        author_tabs = st.tabs([
            f"#{i+1}: {merged_authors[i][1]['commits']} commits - {merged_authors[i][0][:25]}"
            for i in range(detail_count)
        ])
        
        for tab_idx in range(detail_count):
            author_name, author_data = merged_authors[tab_idx]
            
            with author_tabs[tab_idx]:
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Commits", author_data.get("commits", 0))
                with col2:
                    st.metric("Files Modified", author_data.get("files_changed", 0))
                with col3:
                    st.metric("Lines Added", f"{author_data.get('lines_added', 0):,}")
                with col4:
                    st.metric("Lines Deleted", f"{author_data.get('lines_deleted', 0):,}")
                
                # Show merged emails if applicable
                emails = author_data.get("_emails", [])
                if len(emails) > 1:
                    st.caption(f"Merged from accounts: {', '.join(emails)}")
                
                st.divider()
                
                # Contribution period
                first_commit = author_data.get("first_commit")
                last_commit = author_data.get("last_commit")
                
                if first_commit and last_commit:
                    col1, col2 = st.columns(2)
                    with col1:
                        try:
                            first_dt = datetime.fromisoformat(first_commit.replace('Z', '+00:00'))
                            st.metric("First Commit", first_dt.strftime("%Y-%m-%d"))
                        except Exception:
                            st.metric("First Commit", str(first_commit)[:10])
                    with col2:
                        try:
                            last_dt = datetime.fromisoformat(last_commit.replace('Z', '+00:00'))
                            st.metric("Last Commit", last_dt.strftime("%Y-%m-%d"))
                        except Exception:
                            st.metric("Last Commit", str(last_commit)[:10])
                
                st.divider()
                
                # Recent commits
                recent_commits = author_data.get("recent_commits", [])
                if recent_commits:
                    st.markdown("**📅 Recent Commits:**")
                    for commit in recent_commits[:10]:
                        sha = commit.get("sha", "?")[:7]
                        msg = commit.get("message", "No message")
                        date = commit.get("date", "?")
                        try:
                            dt = datetime.fromisoformat(date.replace('Z', '+00:00'))
                            date_str = dt.strftime("%Y-%m-%d %H:%M")
                        except Exception:
                            date_str = str(date)[:16]
                        st.write(f"🕐 {date_str} | `{sha}` **{msg[:60]}**")
    
    st.divider()
    
    # ========== CONTRIBUTION DISTRIBUTION ==========
    st.markdown("### 📈 Contribution Distribution")
    
    try:
        import pandas as pd
        
        top_n_dist = min(20, len(merged_authors))
        chart_names = []
        chart_commits = []
        
        for name, data in merged_authors[:top_n_dist]:
            chart_names.append(name[:20])
            chart_commits.append(data.get("commits", 0))
        
        chart_data = pd.DataFrame({'Author': chart_names, 'Commits': chart_commits})
        st.bar_chart(chart_data.set_index('Author'), use_container_width=True)
    except Exception as e:
        st.warning(f"Could not render chart: {e}")
    
    # ========== PROJECT TIMELINE ==========
    st.markdown("### 📅 Project Timeline & Commit Activity")
    
    st.write(f"**Repository has {total_commits} commits from {total_authors} author(s)**")
    
    all_dates = []
    for _, author_data in merged_authors:
        for field in ("first_commit", "last_commit"):
            val = author_data.get(field)
            if val:
                try:
                    all_dates.append(datetime.fromisoformat(str(val).replace('Z', '+00:00')))
                except Exception:
                    pass
    
    if all_dates:
        earliest = min(all_dates)
        latest = max(all_dates)
        days_span = (latest - earliest).days
        st.metric(
            "📊 Project Timeline Span",
            f"{days_span} days ({earliest.strftime('%Y-%m-%d')} → {latest.strftime('%Y-%m-%d')})"
        )
    
    st.divider()
    
    # Commit share by author
    st.write("**📈 Commit Distribution by Author:**")
    max_commits_display = max(a.get("commits", 0) for _, a in merged_authors[:5]) if merged_authors else 1
    
    for rank, (author_name, author_data) in enumerate(merged_authors[:5], 1):
        commits_count = author_data.get("commits", 0)
        percentage = (commits_count / max(total_commits, 1)) * 100
        
        period_str = ""
        first_commit = author_data.get("first_commit")
        last_commit = author_data.get("last_commit")
        if first_commit and last_commit:
            try:
                first_dt = datetime.fromisoformat(str(first_commit).replace('Z', '+00:00'))
                last_dt = datetime.fromisoformat(str(last_commit).replace('Z', '+00:00'))
                period_str = f" ({first_dt.strftime('%Y-%m-%d')} to {last_dt.strftime('%Y-%m-%d')})"
            except Exception:
                pass
        
        st.write(f"**{rank}. {author_name}**: {commits_count} commits ({percentage:.1f}%){period_str}")
        st.progress(commits_count / max(max_commits_display, 1))
    
    st.divider()
    
    # ========== RECENT COMMITS (ALL AUTHORS) ==========
    st.markdown("### ⏱️ Recent Commits Timeline (All Authors)")
    
    try:
        all_commits_list = []
        for author_name, author_data in merged_authors:
            for commit in author_data.get("recent_commits", []):
                all_commits_list.append({
                    **commit,
                    "_display_name": author_name,
                })
        
        all_commits_list.sort(
            key=lambda x: x.get("date", "") or "",
            reverse=True,
        )
        
        for commit in all_commits_list[:15]:
            sha = commit.get("sha", "?")[:7]
            msg = commit.get("message", "No message")[:60]
            date = commit.get("date", "?")
            name = commit.get("_display_name", "Unknown")
            
            try:
                dt = datetime.fromisoformat(str(date).replace('Z', '+00:00'))
                date_str = dt.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                date_str = str(date)[:19]
            
            st.write(f"🕐 `{date_str}` | `{sha}` | **{name}**: {msg}")
    
    except Exception as e:
        st.warning(f"Could not load recent commits timeline: {e}")