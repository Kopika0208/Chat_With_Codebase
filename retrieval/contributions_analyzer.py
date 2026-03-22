"""
Contributions analyzer module for answering contribution-related queries.
Handles loading, analyzing, and querying git contribution data.
Includes fuzzy author merging for users with multiple emails/usernames.
"""

import os
import json
import re
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict


# ======================================================
# 🔀 FUZZY AUTHOR MERGING (shared logic with contributions_viz.py)
# ======================================================

def _normalize_name(name: str) -> str:
    """Normalize a name for comparison: lowercase, strip non-alphanumeric."""
    return re.sub(r'[^a-z0-9]', '', name.lower().strip())


def _extract_name_parts(name: str) -> set:
    """Extract meaningful tokens from a name or username."""
    tokens = re.split(r'[\s._\-@+]+', name.lower().strip())
    parts = set()
    for t in tokens:
        if len(t) < 2 or t.isdigit():
            continue
        parts.add(t)
        # Strip trailing digits (e.g. "kopika0208" -> "kopika")
        stripped = re.sub(r'\d+$', '', t)
        if stripped and len(stripped) >= 2:
            parts.add(stripped)
    return parts


def _names_match(name_a: str, name_b: str) -> bool:
    """Check if two author identifiers likely refer to the same person."""
    norm_a = _normalize_name(name_a)
    norm_b = _normalize_name(name_b)

    if norm_a == norm_b:
        return True
    if len(norm_a) >= 3 and len(norm_b) >= 3:
        if norm_a in norm_b or norm_b in norm_a:
            return True

    parts_a = _extract_name_parts(name_a)
    parts_b = _extract_name_parts(name_b)
    if parts_a and parts_b:
        meaningful_shared = {t for t in (parts_a & parts_b) if len(t) >= 3}
        if meaningful_shared:
            return True
    return False


def _get_display_name(author_data: Dict, email: str) -> str:
    """Get the best display name for an author."""
    recent = author_data.get("recent_commits", [])
    if recent:
        # Prefer real names with spaces over usernames
        for commit in recent:
            name = commit.get("author_name", "")
            if name and " " in name:
                return name
        return recent[0].get("author_name", email)
    return email


def _merge_authors_from_data(authors_raw: Dict[str, Dict]) -> Dict[str, Dict]:
    """
    Merge duplicate authors and return a clean dict keyed by display name.

    Returns:
        {display_name: {commits, files_changed, lines_added, lines_deleted,
                        net_lines, first_commit, last_commit, recent_commits, _emails}}
    """
    if not authors_raw:
        return {}

    entries = []
    for email, data in authors_raw.items():
        display = _get_display_name(data, email)
        all_names = {email, display}
        for commit in data.get("recent_commits", []):
            n = commit.get("author_name", "")
            if n:
                all_names.add(n)
        entries.append((email, data, display, all_names))

    groups = []
    assigned = set()

    for i, (email_i, data_i, display_i, names_i) in enumerate(entries):
        if i in assigned:
            continue
        group = [i]
        assigned.add(i)
        for j, (email_j, data_j, display_j, names_j) in enumerate(entries):
            if j in assigned:
                continue
            matched = False
            for na in names_i:
                for nb in names_j:
                    if _names_match(na, nb):
                        matched = True
                        break
                if matched:
                    break
            if matched:
                group.append(j)
                assigned.add(j)
        groups.append(group)

    result = {}
    for group in groups:
        merged = {
            "commits": 0, "files_changed": 0, "lines_added": 0,
            "lines_deleted": 0, "net_lines": 0,
            "first_commit": None, "last_commit": None,
            "recent_commits": [], "_emails": [],
        }
        for idx in group:
            email, data, _, _ = entries[idx]
            merged["commits"] += data.get("commits", 0)
            merged["files_changed"] += data.get("files_changed", 0)
            merged["lines_added"] += data.get("lines_added", 0)
            merged["lines_deleted"] += data.get("lines_deleted", 0)
            merged["net_lines"] += data.get("net_lines", 0)
            merged["_emails"].append(email)
            fc = data.get("first_commit")
            lc = data.get("last_commit")
            if fc and (merged["first_commit"] is None or str(fc) < str(merged["first_commit"])):
                merged["first_commit"] = fc
            if lc and (merged["last_commit"] is None or str(lc) > str(merged["last_commit"])):
                merged["last_commit"] = lc
            merged["recent_commits"].extend(data.get("recent_commits", []))

        merged["recent_commits"] = sorted(
            merged["recent_commits"], key=lambda c: c.get("date", ""), reverse=True
        )[:5]

        # Pick best display name
        best_name = None
        for idx in group:
            name = entries[idx][2]
            if " " in name:
                best_name = name
                break
        if not best_name:
            best_name = entries[group[0]][2]

        result[best_name] = merged

    return result


# ======================================================
# 📊 CONTRIBUTIONS DATA ANALYZER
# ======================================================

class ContributionsDataAnalyzer:
    """Analyze and query git contribution data from contributions.json"""

    def __init__(self, repo_name: str):
        self.repo_name = repo_name
        self.contributions_data = self._load_contributions_data()
        self.current_date = datetime.now()
        # Pre-merge authors once
        raw_authors = self.contributions_data.get("authors", {}) if self.contributions_data else {}
        self._merged_authors = _merge_authors_from_data(raw_authors)

    def _load_contributions_data(self) -> Optional[Dict]:
        """Load contributions.json for the repository."""
        contributions_path = os.path.join("data", self.repo_name, "contributions.json")
        try:
            if os.path.exists(contributions_path):
                with open(contributions_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return None
        except Exception as e:
            print(f"⚠️ Error loading contributions data: {e}")
            return None

    def is_contribution_query(self, query: str) -> bool:
        """Detect if the query is about contributions/commits/authors."""
        contribution_keywords = [
            r'commit', r'git', r'contribut', r'author',
            r'who\s+(wrote|made|created|changed|modified|contributed)',
            r'who\s+is\s+the\s+(most|top)',
            r'development\s+activity', r'code\s+changes?',
            r'changed?\s+files?', r'activity',
            r'lines?\s+(added|deleted)', r'(added|deleted)\s+lines?',
            r'files?\s+changed?',
            r'history', r'timeline',
            r'when\s+was', r'when\s+did',
            r'recently?', r'last\s+(modified|changed|commit)',
            r'first\s+commit', r'latest\s+commit',
            r'project\s+timeline', r'development\s+timeline',
            r'stats?', r'metrics?', r'frequency',
            r'how\s+many', r'total\s+commit',
            r'(top|most|active)', r'recent', r'latest',
        ]
        query_lower = query.lower()
        return any(re.search(p, query_lower) for p in contribution_keywords)

    def get_time_range(self, query: str) -> Tuple[Optional[datetime], Optional[datetime]]:
        """Extract time range from query."""
        query_lower = query.lower()
        end_date = self.current_date

        match = re.search(r'(?:last|previous)\s+(\d+)\s+(day|week|month|year)s?', query_lower)
        if match:
            num = int(match.group(1))
            unit = match.group(2)
            multiplier = {'day': 1, 'week': 7, 'month': 30, 'year': 365}
            start_date = end_date - timedelta(days=num * multiplier.get(unit, 1))
            return start_date, end_date

        match = re.search(r'in\s+(?:the\s+)?(?:last|previous)\s+(day|week|month|year)', query_lower)
        if match:
            unit = match.group(1)
            multiplier = {'day': 1, 'week': 7, 'month': 30, 'year': 365}
            start_date = end_date - timedelta(days=multiplier.get(unit, 1))
            return start_date, end_date

        return None, None

    def get_commits_in_range(self, start_date: Optional[datetime] = None,
                             end_date: Optional[datetime] = None) -> Dict:
        """Get commits within a specific date range (uses merged authors)."""
        if not self._merged_authors:
            return {"total_commits": 0, "authors": {}}

        total = 0
        author_commits = defaultdict(int)

        for author_name, author_data in self._merged_authors.items():
            for commit in author_data.get("recent_commits", []):
                try:
                    commit_date = datetime.fromisoformat(
                        commit.get("date", "").replace('Z', '+00:00')
                    ).replace(tzinfo=None)
                    s = start_date.replace(tzinfo=None) if start_date else None
                    e = end_date.replace(tzinfo=None) if end_date else None
                    if s and commit_date < s:
                        continue
                    if e and commit_date > e:
                        continue
                    total += 1
                    author_commits[author_name] += 1
                except Exception:
                    pass

        return {"total_commits": total, "authors": dict(author_commits)}

    def get_summary_stats(self) -> Dict:
        """Get overall contribution summary (merged authors)."""
        if not self._merged_authors:
            return {}

        total_commits = sum(a["commits"] for a in self._merged_authors.values())
        total_lines_added = sum(a.get("lines_added", 0) for a in self._merged_authors.values())
        total_lines_deleted = sum(a.get("lines_deleted", 0) for a in self._merged_authors.values())
        total_files_changed = sum(a.get("files_changed", 0) for a in self._merged_authors.values())

        sorted_authors = sorted(
            self._merged_authors.items(), key=lambda x: x[1]["commits"], reverse=True
        )

        return {
            "total_authors": len(self._merged_authors),
            "total_commits": total_commits,
            "total_lines_added": total_lines_added,
            "total_lines_deleted": total_lines_deleted,
            "net_lines": total_lines_added - total_lines_deleted,
            "total_files_changed": total_files_changed,
            "top_contributors": [
                {"name": name, "commits": data["commits"],
                 "emails": data.get("_emails", [])}
                for name, data in sorted_authors[:5]
            ],
        }

    def get_author_stats(self, author_query: str) -> Optional[Dict]:
        """Get statistics for a specific author (searches merged names and emails)."""
        if not self._merged_authors:
            return None

        query_lower = author_query.lower()

        # Search by display name
        for name, data in self._merged_authors.items():
            if query_lower in name.lower() or name.lower() in query_lower:
                return {"name": name, **data}

        # Search by email
        for name, data in self._merged_authors.items():
            for email in data.get("_emails", []):
                if query_lower in email.lower() or email.lower() in query_lower:
                    return {"name": name, **data}

        return None

    def get_most_active_authors(self, limit: int = 5) -> List[Dict]:
        """Get most active authors by commit count (merged)."""
        if not self._merged_authors:
            return []

        sorted_authors = sorted(
            self._merged_authors.items(), key=lambda x: x[1]["commits"], reverse=True
        )[:limit]

        return [
            {
                "name": name,
                "emails": data.get("_emails", []),
                "commits": data["commits"],
                "files_changed": data.get("files_changed", 0),
                "lines_added": data.get("lines_added", 0),
                "lines_deleted": data.get("lines_deleted", 0),
            }
            for name, data in sorted_authors
        ]

    def get_recent_commits(self, limit: int = 10) -> List[Dict]:
        """Get most recent commits across all merged authors."""
        if not self._merged_authors:
            return []

        all_commits = []
        for author_name, author_data in self._merged_authors.items():
            for commit in author_data.get("recent_commits", []):
                entry = dict(commit)
                entry["_display_name"] = author_name
                try:
                    dt = datetime.fromisoformat(
                        commit.get("date", "").replace('Z', '+00:00')
                    )
                    entry["formatted_date"] = dt.strftime("%Y-%m-%d %H:%M:%S")
                    entry["date_only"] = dt.strftime("%Y-%m-%d")
                except Exception:
                    entry["formatted_date"] = commit.get("date", "Unknown")
                    entry["date_only"] = "Unknown"
                all_commits.append(entry)

        all_commits.sort(key=lambda x: x.get("date", "") or "", reverse=True)
        return all_commits[:limit]

    def get_last_commit(self) -> Optional[Dict]:
        """Get the most recent commit."""
        recent = self.get_recent_commits(limit=1)
        return recent[0] if recent else None

    def get_timeline(self) -> Dict:
        """Get complete chronological timeline of the project."""
        if not self._merged_authors:
            return {}

        all_commits = []
        for author_name, author_data in self._merged_authors.items():
            for commit in author_data.get("recent_commits", []):
                entry = dict(commit)
                entry["_display_name"] = author_name
                try:
                    dt = datetime.fromisoformat(
                        commit.get("date", "").replace('Z', '+00:00')
                    )
                    entry["formatted_date"] = dt.strftime("%Y-%m-%d %H:%M:%S")
                    entry["date_only"] = dt.strftime("%Y-%m-%d")
                except Exception:
                    entry["formatted_date"] = commit.get("date", "Unknown")
                    entry["date_only"] = "Unknown"
                all_commits.append(entry)

        # Sort chronologically (oldest first)
        all_commits.sort(key=lambda x: x.get("date", "") or "")

        first_date = None
        last_date = None
        if all_commits:
            try:
                first_date = datetime.fromisoformat(
                    all_commits[0].get("date", "").replace('Z', '+00:00')
                )
                last_date = datetime.fromisoformat(
                    all_commits[-1].get("date", "").replace('Z', '+00:00')
                )
            except Exception:
                pass

        return {
            "commits": all_commits,
            "total_commits": len(all_commits),
            "first_commit_date": first_date.strftime("%Y-%m-%d") if first_date else None,
            "last_commit_date": last_date.strftime("%Y-%m-%d") if last_date else None,
            "date_range_days": (last_date - first_date).days if first_date and last_date else None,
        }

    def get_commits_by_date_period(self, period: str = 'day') -> Dict[str, List[Dict]]:
        """Group commits by time period (day, week, month)."""
        if not self._merged_authors:
            return {}

        commits_by_period = defaultdict(list)
        fmt = {'day': "%Y-%m-%d", 'week': "%Y-W%V", 'month': "%Y-%m"}

        for author_name, author_data in self._merged_authors.items():
            for commit in author_data.get("recent_commits", []):
                try:
                    dt = datetime.fromisoformat(
                        commit.get("date", "").replace('Z', '+00:00')
                    )
                    key = dt.strftime(fmt.get(period, "%Y-%m-%d"))
                    entry = dict(commit)
                    entry["_display_name"] = author_name
                    commits_by_period[key].append(entry)
                except Exception:
                    pass

        return dict(commits_by_period)

    def get_commit_frequency(self) -> Dict:
        """Get commit frequency statistics over time."""
        commits_by_day = self.get_commits_by_date_period('day')
        frequency_data = [
            {
                "date": day,
                "commit_count": len(commits),
                "authors_count": len(set(c.get("_display_name", "") for c in commits)),
            }
            for day, commits in sorted(commits_by_day.items())
        ]
        total = sum(f["commit_count"] for f in frequency_data)
        return {
            "frequency_by_day": frequency_data,
            "total_active_days": len(frequency_data),
            "average_commits_per_day": total / len(frequency_data) if frequency_data else 0,
        }

    def generate_contribution_context(self, query: str) -> str:
        """Generate relevant contribution context based on the query for LLM consumption."""
        if not self.contributions_data:
            return "No contribution data available for this repository."

        context_parts = []
        query_lower = query.lower()

        is_timeline_query = any(
            w in query_lower for w in ['when', 'last', 'first', 'timeline', 'recent', 'latest', 'date']
        )

        if is_timeline_query:
            timeline = self.get_timeline()
            if timeline and timeline.get("commits"):
                if any(p in query_lower for p in ['last commit', 'most recent', 'latest commit']):
                    recent = self.get_recent_commits(limit=5)
                    if recent:
                        context_parts.append("📅 Recent Commits:")
                        context_parts.append(f"  Last commit: {recent[0].get('formatted_date', 'Unknown')}")
                        context_parts.append(f"  Message: {recent[0].get('message', 'No message')}")
                        context_parts.append(f"  Author: {recent[0].get('_display_name', 'Unknown')}")
                        if len(recent) > 1:
                            context_parts.append("\n  Previous commits:")
                            for c in recent[1:5]:
                                context_parts.append(
                                    f"    - {c.get('formatted_date', '?')}: "
                                    f"{c.get('_display_name', '?')} - {c.get('message', 'N/A')[:50]}"
                                )

                elif any(p in query_lower for p in ['first commit', 'project start', 'initial commit']):
                    first = timeline["commits"][0]
                    context_parts.append("📅 Project Timeline:")
                    context_parts.append(f"  First commit: {first.get('formatted_date', 'Unknown')}")
                    context_parts.append(f"  Message: {first.get('message', 'No message')}")
                    context_parts.append(f"  Author: {first.get('_display_name', 'Unknown')}")

                else:
                    context_parts.append("📅 Project Timeline:")
                    if timeline.get("first_commit_date"):
                        context_parts.append(f"  First commit: {timeline['first_commit_date']}")
                    if timeline.get("last_commit_date"):
                        context_parts.append(f"  Last commit: {timeline['last_commit_date']}")
                    if timeline.get("date_range_days") is not None:
                        context_parts.append(f"  Project duration: {timeline['date_range_days']} days")
                    context_parts.append(f"  Total commits: {timeline.get('total_commits', 0)}")

                    freq = self.get_commit_frequency()
                    if freq.get("average_commits_per_day"):
                        context_parts.append(f"  Average commits per day: {freq['average_commits_per_day']:.2f}")
                        context_parts.append(f"  Active days: {freq.get('total_active_days', 0)}")

        # Time range queries
        start_date, end_date = self.get_time_range(query)
        if start_date and not is_timeline_query:
            range_stats = self.get_commits_in_range(start_date, end_date)
            context_parts.append(f"📊 Commits in specified time range: {range_stats['total_commits']}")
            if range_stats["authors"]:
                context_parts.append("Per-author breakdown:")
                for name, count in sorted(range_stats["authors"].items(), key=lambda x: x[1], reverse=True):
                    context_parts.append(f"  - {name}: {count} commits")

        # Author queries
        if not is_timeline_query and any(w in query_lower for w in ['who', 'author', 'by']):
            most_active = self.get_most_active_authors(limit=5)
            if most_active:
                context_parts.append("\n👥 Top Contributors:")
                for author in most_active:
                    context_parts.append(
                        f"  - {author['name']}: {author['commits']} commits, "
                        f"{author['lines_added']} lines added, "
                        f"{author['files_changed']} files changed"
                    )

        # Default summary
        if not context_parts:
            stats = self.get_summary_stats()
            context_parts.append("📈 Overall Contribution Statistics:")
            context_parts.append(f"  - Total commits: {stats.get('total_commits', 0)}")
            context_parts.append(f"  - Total authors: {stats.get('total_authors', 0)}")
            context_parts.append(f"  - Total lines added: {stats.get('total_lines_added', 0)}")
            context_parts.append(f"  - Total lines deleted: {stats.get('total_lines_deleted', 0)}")
            context_parts.append(f"  - Files changed: {stats.get('total_files_changed', 0)}")
            if stats.get("top_contributors"):
                context_parts.append("\n  🏆 Top contributors:")
                for c in stats["top_contributors"][:5]:
                    context_parts.append(f"    - {c['name']}: {c['commits']} commits")

        return "\n".join(context_parts)

    @staticmethod
    def extract_github_username(email: str) -> str:
        """Extract a readable username from an email address."""
        if not email:
            return "Unknown"
        if '+' in email:
            try:
                username = email.split('+')[1].split('@')[0]
                if username:
                    return username
            except Exception:
                pass
        try:
            return email.split('@')[0].replace('_', ' ').replace('.', ' ').title()
        except Exception:
            return email


def load_contributions_analyzer(repo_name: str) -> ContributionsDataAnalyzer:
    """Factory function to load contributions analyzer."""
    return ContributionsDataAnalyzer(repo_name)