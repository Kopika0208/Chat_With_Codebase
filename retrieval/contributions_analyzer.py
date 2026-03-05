"""
Contributions analyzer module for answering contribution-related queries.
Handles loading, analyzing, and querying git contribution data.
"""

import os
import json
import re
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
from pathlib import Path


class ContributionsDataAnalyzer:
    """Analyze and query git contribution data from contributions.json"""
    
    def __init__(self, repo_name: str):
        """
        Initialize the contributions analyzer.
        
        Args:
            repo_name: Name of the repository (e.g., 'AskLegal.ai-AI-Legal-Assistant')
        """
        self.repo_name = repo_name
        self.contributions_data = self._load_contributions_data()
        self.current_date = datetime.now()
    
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
        """
        Detect if the query is about contributions/commits/authors.
        
        Args:
            query: User's question
            
        Returns:
            True if query is about contributions
        """
        contribution_keywords = [
            # Commit-related
            r'commit',
            r'git',
            # Contribution-related (matches contribute, contributor, contribution, contributed, etc.)
            r'contribut',
            # Author-related
            r'author',
            r'who\s+(wrote|made|created|changed|modified|contributed)',
            r'who\s+is\s+the\s+(most|top)',
            # Activity-related
            r'development\s+activity',
            r'code\s+changes?',
            r'changed?\s+files?',
            r'activity',
            # Lines changed
            r'lines?\s+(added|deleted)',
            r'(added|deleted)\s+lines?',
            # Files changed
            r'files?\s+changed?',
            r'changed?\s+files?',
            # Timeline and history
            r'history',
            r'timeline',
            r'when\s+was',
            r'when\s+did',
            r'recently?',
            r'last\s+(modified|changed|commit)',
            r'first\s+commit',
            r'latest\s+commit',
            r'project\s+timeline',
            r'development\s+timeline',
            # Stats and metrics
            r'stats?',
            r'metrics?',
            r'frequency',
            r'how\s+many',
            r'total\s+commit',
            r'(top|most|active)',
            # Recent/latest
            r'recent',
            r'latest',
        ]
        
        query_lower = query.lower()
        for pattern in contribution_keywords:
            if re.search(pattern, query_lower):
                return True
        
        return False
    
    def get_time_range(self, query: str) -> Tuple[Optional[datetime], Optional[datetime]]:
        """
        Extract time range from query.
        
        Returns:
            Tuple of (start_date, end_date) or (None, None) if not found
        """
        query_lower = query.lower()
        end_date = self.current_date
        start_date = None
        
        # Last N days/weeks/months
        match = re.search(r'(?:last|previous)\s+(\d+)\s+(day|week|month|year)s?', query_lower)
        if match:
            num = int(match.group(1))
            unit = match.group(2)
            if unit == 'day':
                start_date = end_date - timedelta(days=num)
            elif unit == 'week':
                start_date = end_date - timedelta(weeks=num)
            elif unit == 'month':
                start_date = end_date - timedelta(days=num*30)
            elif unit == 'year':
                start_date = end_date - timedelta(days=num*365)
            return start_date, end_date
        
        # "in the last month" etc
        match = re.search(r'in\s+(?:the\s+)?(?:last|previous)\s+(day|week|month|year)', query_lower)
        if match:
            unit = match.group(1)
            if unit == 'day':
                start_date = end_date - timedelta(days=1)
            elif unit == 'week':
                start_date = end_date - timedelta(weeks=1)
            elif unit == 'month':
                start_date = end_date - timedelta(days=30)
            elif unit == 'year':
                start_date = end_date - timedelta(days=365)
            return start_date, end_date
        
        return None, None
    
    def get_commits_in_range(self, start_date: Optional[datetime] = None, 
                           end_date: Optional[datetime] = None) -> Dict:
        """
        Get commits within a specific date range.
        
        Returns:
            Dict with total commits and per-author breakdown
        """
        if not self.contributions_data:
            return {"total_commits": 0, "authors": {}}
        
        total = 0
        author_commits = defaultdict(int)
        
        for author_email, author_data in self.contributions_data.get("authors", {}).items():
            recent_commits = author_data.get("recent_commits", [])
            
            for commit in recent_commits:
                try:
                    commit_date = datetime.fromisoformat(commit["date"].replace('Z', '+00:00'))
                    
                    # Remove timezone for comparison
                    commit_date = commit_date.replace(tzinfo=None)
                    if start_date:
                        start_date_naive = start_date.replace(tzinfo=None)
                    else:
                        start_date_naive = None
                    if end_date:
                        end_date_naive = end_date.replace(tzinfo=None)
                    else:
                        end_date_naive = None
                    
                    if start_date_naive and commit_date < start_date_naive:
                        continue
                    if end_date_naive and commit_date > end_date_naive:
                        continue
                    
                    total += 1
                    author_commits[author_email] += 1
                except Exception as e:
                    print(f"⚠️ Error parsing commit date: {e}")
        
        return {
            "total_commits": total,
            "authors": dict(author_commits)
        }
    
    def get_summary_stats(self) -> Dict:
        """Get overall contribution summary statistics."""
        if not self.contributions_data:
            return {}
        
        total_authors = self.contributions_data.get("total_authors", 0)
        total_commits = self.contributions_data.get("total_commits", 0)
        
        authors_data = self.contributions_data.get("authors", {})
        
        total_lines_added = sum(
            author.get("lines_added", 0) for author in authors_data.values()
        )
        total_lines_deleted = sum(
            author.get("lines_deleted", 0) for author in authors_data.values()
        )
        total_files_changed = sum(
            author.get("files_changed", 0) for author in authors_data.values()
        )
        
        # Get top contributors
        top_contributors = sorted(
            authors_data.items(),
            key=lambda x: x[1].get("commits", 0),
            reverse=True
        )[:5]
        
        return {
            "total_authors": total_authors,
            "total_commits": total_commits,
            "total_lines_added": total_lines_added,
            "total_lines_deleted": total_lines_deleted,
            "net_lines": total_lines_added - total_lines_deleted,
            "total_files_changed": total_files_changed,
            "top_contributors": [
                {
                    "email": email,
                    "name": author_data.get("recent_commits", [{}])[0].get("author_name", email),
                    "commits": author_data.get("commits", 0)
                }
                for email, author_data in top_contributors
            ]
        }
    
    def get_author_stats(self, author_query: str) -> Optional[Dict]:
        """
        Get statistics for a specific author.
        
        Args:
            author_query: Author name or email
            
        Returns:
            Author statistics or None
        """
        if not self.contributions_data:
            return None
        
        authors_data = self.contributions_data.get("authors", {})
        
        # Direct email match
        if author_query in authors_data:
            return {
                "email": author_query,
                **authors_data[author_query]
            }
        
        # Search by name
        for email, author_data in authors_data.items():
            recent_commits = author_data.get("recent_commits", [])
            if recent_commits:
                author_name = recent_commits[0].get("author_name", "").lower()
                if author_query.lower() in author_name or author_name in author_query.lower():
                    return {
                        "email": email,
                        **author_data
                    }
        
        return None
    
    def get_most_active_authors(self, limit: int = 5) -> List[Dict]:
        """
        Get most active authors by commit count.
        
        Args:
            limit: Number of authors to return
            
        Returns:
            List of author data
        """
        if not self.contributions_data:
            return []
        
        authors_data = self.contributions_data.get("authors", {})
        
        sorted_authors = sorted(
            authors_data.items(),
            key=lambda x: x[1].get("commits", 0),
            reverse=True
        )[:limit]
        
        result = []
        for email, author_data in sorted_authors:
            author_name = "Unknown"
            if author_data.get("recent_commits"):
                author_name = author_data["recent_commits"][0].get("author_name", email)
            
            result.append({
                "email": email,
                "name": author_name,
                "commits": author_data.get("commits", 0),
                "files_changed": author_data.get("files_changed", 0),
                "lines_added": author_data.get("lines_added", 0),
                "lines_deleted": author_data.get("lines_deleted", 0),
            })
        
        return result
    
    def generate_contribution_context(self, query: str) -> str:
        """
        Generate relevant contribution context based on the query.
        
        Args:
            query: User's question
            
        Returns:
            Formatted contribution information as context
        """
        if not self.contributions_data:
            return "No contribution data available for this repository."
        
        context_parts = []
        query_lower = query.lower()
        
        # Check if it's a timeline/date-related query
        is_timeline_query = any(word in query_lower for word in 
                               ['when', 'last', 'first', 'timeline', 'recent', 'latest', 'date'])
        
        if is_timeline_query:
            # Get timeline information
            timeline = self.get_timeline()
            if timeline and timeline.get('commits'):
                # Check for "last commit" query
                if any(phrase in query_lower for phrase in ['last commit', 'most recent', 'latest commit']):
                    recent = self.get_recent_commits(limit=5)
                    if recent:
                        context_parts.append("📅 Recent Commits:")
                        context_parts.append(f"  Last commit: {recent[0].get('formatted_date', 'Unknown')}")
                        context_parts.append(f"  Message: {recent[0].get('message', 'No message')}")
                        author_email = recent[0].get('author_email')
                        if author_email:
                            author_name = self._get_author_name(author_email)
                            context_parts.append(f"  Author: {author_name}")
                        
                        if len(recent) > 1:
                            context_parts.append("\n  Previous commits:")
                            for commit in recent[1:5]:
                                context_parts.append(
                                    f"    - {commit.get('formatted_date', 'Unknown')}: {commit.get('message', 'N/A')[:50]}"
                                )
                
                # Check for "first commit" query
                elif any(phrase in query_lower for phrase in ['first commit', 'project start', 'initial commit']):
                    if timeline.get('commits'):
                        first = timeline['commits'][0]
                        context_parts.append("📅 Project Timeline:")
                        context_parts.append(f"  First commit: {first.get('formatted_date', 'Unknown')}")
                        context_parts.append(f"  Message: {first.get('message', 'No message')}")
                        author_email = first.get('author_email')
                        if author_email:
                            author_name = self._get_author_name(author_email)
                            context_parts.append(f"  Author: {author_name}")
                
                # General timeline info
                else:
                    context_parts.append("📅 Project Timeline:")
                    if timeline.get('first_commit_date'):
                        context_parts.append(f"  First commit: {timeline['first_commit_date']}")
                    if timeline.get('last_commit_date'):
                        context_parts.append(f"  Last commit: {timeline['last_commit_date']}")
                    if timeline.get('date_range_days') is not None:
                        context_parts.append(f"  Project duration: {timeline['date_range_days']} days")
                    
                    context_parts.append(f"  Total commits: {timeline.get('total_commits', 0)}")
                    
                    # Add commit frequency
                    freq = self.get_commit_frequency()
                    if freq.get('average_commits_per_day'):
                        context_parts.append(f"  Average commits per day: {freq['average_commits_per_day']:.2f}")
                        context_parts.append(f"  Active days: {freq.get('total_active_days', 0)}")
        
        # Check if it's a time-range query
        start_date, end_date = self.get_time_range(query)
        if start_date and not is_timeline_query:
            range_stats = self.get_commits_in_range(start_date, end_date)
            context_parts.append(
                f"📊 Commits in the specified time range: {range_stats['total_commits']}"
            )
            if range_stats['authors']:
                context_parts.append("Per-author breakdown:")
                for email, count in sorted(range_stats['authors'].items(), 
                                         key=lambda x: x[1], reverse=True):
                    author_name = self._get_author_name(email)
                    context_parts.append(f"  - {author_name} ({email}): {count} commits")
        
        # Check if it's a specific author query
        if not is_timeline_query and any(word in query_lower for word in ['who', 'author', 'by']):
            most_active = self.get_most_active_authors(limit=3)
            if most_active:
                context_parts.append("\n👥 Top Contributors:")
                for author in most_active:
                    context_parts.append(
                        f"  - {author['name']}: {author['commits']} commits, "
                        f"{author['lines_added']} lines added, "
                        f"{author['files_changed']} files changed"
                    )
        
        # Default: provide overall summary if no specific query type matched
        if not context_parts:
            stats = self.get_summary_stats()
            context_parts.append(f"📈 Overall Contribution Statistics:")
            context_parts.append(f"  - Total commits: {stats.get('total_commits', 0)}")
            context_parts.append(f"  - Total authors: {stats.get('total_authors', 0)}")
            context_parts.append(f"  - Total lines added: {stats.get('total_lines_added', 0)}")
            context_parts.append(f"  - Total lines deleted: {stats.get('total_lines_deleted', 0)}")
            context_parts.append(f"  - Files changed: {stats.get('total_files_changed', 0)}")
            
            if stats.get('top_contributors'):
                context_parts.append("\n  🏆 Top contributors:")
                for contributor in stats['top_contributors'][:3]:
                    context_parts.append(
                        f"    - {contributor['name']}: {contributor['commits']} commits"
                    )
        
        return "\n".join(context_parts)
    
    def _get_author_name(self, email: str) -> str:
        """Helper to get author name from email."""
        if not self.contributions_data:
            return email
        
        author_data = self.contributions_data.get("authors", {}).get(email, {})
        if author_data.get("recent_commits"):
            return author_data["recent_commits"][0].get("author_name", email)
        
        return email
    
    @staticmethod
    def extract_github_username(email: str) -> str:
        """
        Extract a readable username from an email address.
        
        Args:
            email: Email address (e.g., "user@gmail.com" or "id+username@github.com")
            
        Returns:
            Readable username
        """
        if not email:
            return "Unknown"
        
        # If email contains GitHub username pattern (id+username@)
        if '+' in email:
            try:
                username = email.split('+')[1].split('@')[0]
                if username:
                    return username
            except:
                pass
        
        # Otherwise, just use the part before @
        try:
            username = email.split('@')[0]
            # Remove common prefixes
            username = username.replace('_', ' ').replace('.', ' ').title()
            return username
        except:
            return email
    
    def get_last_commit(self) -> Optional[Dict]:
        """
        Get the very last (most recent) commit across all authors.
        
        Returns:
            The most recent commit dict or None
        """
        recent = self.get_recent_commits(limit=1)
        return recent[0] if recent else None
    
    def get_recent_commits(self, limit: int = 10) -> List[Dict]:
        """
        Get most recent commits across all authors.
        
        Args:
            limit: Number of commits to return
            
        Returns:
            List of recent commits with formatted date info
        """
        if not self.contributions_data:
            return []
        
        all_commits = []
        
        for email, author_data in self.contributions_data.get("authors", {}).items():
            recent_commits = author_data.get("recent_commits", [])
            for commit in recent_commits:
                commit['author_email'] = email
                # Add formatted date for display
                try:
                    commit_date = datetime.fromisoformat(
                        commit.get("date", "").replace('Z', '+00:00')
                    )
                    commit['formatted_date'] = commit_date.strftime("%Y-%m-%d %H:%M:%S")
                    commit['date_only'] = commit_date.strftime("%Y-%m-%d")
                except:
                    commit['formatted_date'] = commit.get("date", "Unknown")
                    commit['date_only'] = "Unknown"
                all_commits.append(commit)
        
        # Sort by date (most recent first)
        try:
            all_commits.sort(
                key=lambda x: datetime.fromisoformat(
                    x.get("date", "").replace('Z', '+00:00')
                ),
                reverse=True
            )
        except Exception as e:
            print(f"⚠️ Error sorting commits: {e}")
        
        return all_commits[:limit]


    def get_commits_by_date_period(self, period: str = 'day') -> Dict[str, List[Dict]]:
        """
        Group commits by time period (day, week, month).
        
        Args:
            period: 'day', 'week', or 'month'
            
        Returns:
            Dict mapping date/period to list of commits
        """
        if not self.contributions_data:
            return {}
        
        commits_by_period = defaultdict(list)
        
        for email, author_data in self.contributions_data.get("authors", {}).items():
            recent_commits = author_data.get("recent_commits", [])
            
            for commit in recent_commits:
                try:
                    commit_date = datetime.fromisoformat(
                        commit.get("date", "").replace('Z', '+00:00')
                    )
                    
                    # Format key based on period
                    if period == 'day':
                        period_key = commit_date.strftime("%Y-%m-%d")
                    elif period == 'week':
                        # ISO week format
                        period_key = commit_date.strftime("%Y-W%V")
                    elif period == 'month':
                        period_key = commit_date.strftime("%Y-%m")
                    else:
                        period_key = commit_date.strftime("%Y-%m-%d")
                    
                    commit_with_email = commit.copy()
                    commit_with_email['author_email'] = email
                    commits_by_period[period_key].append(commit_with_email)
                except Exception as e:
                    print(f"⚠️ Error processing commit date: {e}")
        
        return dict(commits_by_period)
    
    def get_timeline(self) -> Dict:
        """
        Get complete chronological timeline of the project.
        
        Returns:
            Dict with sorted timeline data
        """
        if not self.contributions_data:
            return {}
        
        all_commits = []
        
        for email, author_data in self.contributions_data.get("authors", {}).items():
            recent_commits = author_data.get("recent_commits", [])
            for commit in recent_commits:
                commit['author_email'] = email
                all_commits.append(commit)
        
        # Sort chronologically (oldest first)
        try:
            all_commits.sort(
                key=lambda x: datetime.fromisoformat(
                    x.get("date", "").replace('Z', '+00:00')
                )
            )
        except Exception as e:
            print(f"⚠️ Error sorting timeline: {e}")
        
        # Add formatted dates
        for commit in all_commits:
            try:
                commit_date = datetime.fromisoformat(
                    commit.get("date", "").replace('Z', '+00:00')
                )
                commit['formatted_date'] = commit_date.strftime("%Y-%m-%d %H:%M:%S")
                commit['date_only'] = commit_date.strftime("%Y-%m-%d")
            except:
                commit['formatted_date'] = commit.get("date", "Unknown")
                commit['date_only'] = "Unknown"
        
        # Extract first and last commit dates
        first_commit_date = None
        last_commit_date = None
        
        if all_commits:
            try:
                first_commit_date = datetime.fromisoformat(
                    all_commits[0].get("date", "").replace('Z', '+00:00')
                )
                last_commit_date = datetime.fromisoformat(
                    all_commits[-1].get("date", "").replace('Z', '+00:00')
                )
            except:
                pass
        
        return {
            "commits": all_commits,
            "total_commits": len(all_commits),
            "first_commit_date": first_commit_date.strftime("%Y-%m-%d") if first_commit_date else None,
            "last_commit_date": last_commit_date.strftime("%Y-%m-%d") if last_commit_date else None,
            "date_range_days": (last_commit_date - first_commit_date).days if first_commit_date and last_commit_date else None
        }
    
    def get_commit_frequency(self) -> Dict:
        """
        Get commit frequency statistics over time.
        
        Returns:
            Dict with frequency data grouped by day
        """
        commits_by_day = self.get_commits_by_date_period('day')
        
        frequency_data = []
        for day in sorted(commits_by_day.keys()):
            frequency_data.append({
                "date": day,
                "commit_count": len(commits_by_day[day]),
                "authors_count": len(set(c.get('author_email') for c in commits_by_day[day]))
            })
        
        return {
            "frequency_by_day": frequency_data,
            "total_active_days": len(frequency_data),
            "average_commits_per_day": sum(f['commit_count'] for f in frequency_data) / len(frequency_data) if frequency_data else 0
        }


def load_contributions_analyzer(repo_name: str) -> ContributionsDataAnalyzer:
    """Factory function to load contributions analyzer."""
    return ContributionsDataAnalyzer(repo_name)
