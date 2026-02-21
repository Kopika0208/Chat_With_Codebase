"""
Git contributions analyzer - tracks commits, authors, and code changes.
Computes contribution metrics like commits per author, lines changed, files modified.
"""

import os
import json
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
from datetime import datetime, timezone
from git import Repo
from pathlib import Path


class ContributionsAnalyzer:
    """Analyzes git history to compute contribution metrics."""
    
    def __init__(self, repo_path: str):
        """
        Initialize contributions analyzer.
        
        Args:
            repo_path: Path to git repository
        """
        self.repo_path = repo_path
        try:
            self.repo = Repo(repo_path)
        except Exception as e:
            print(f"⚠️ Error initializing repo: {e}")
            self.repo = None
        
        self.contributions = defaultdict(lambda: {
            "commits": 0,
            "files_changed": set(),
            "lines_added": 0,
            "lines_deleted": 0,
            "first_commit": None,
            "last_commit": None,
            "commit_details": []
        })
    
    def analyze_all_commits(self) -> Dict:
        """Analyze all commits in the repository."""
        if not self.repo:
            return {}
        
        try:
            commits = list(self.repo.iter_commits())
            print(f"📊 Analyzing {len(commits)} commits...")
            
            for idx, commit in enumerate(commits):
                if idx % 100 == 0:
                    print(f"  Processing commit {idx}/{len(commits)}...")
                
                author = commit.author.email if commit.author else "Unknown"
                author_name = commit.author.name if commit.author else "Unknown"
                
                # Update commit count
                self.contributions[author]["commits"] += 1
                
                # Update timestamp
                commit_dt = commit.committed_datetime
                if self.contributions[author]["first_commit"] is None:
                    self.contributions[author]["first_commit"] = commit_dt
                self.contributions[author]["last_commit"] = commit_dt
                
                # Get diff stats
                try:
                    if commit.parents:
                        diffs = commit.parents[0].diff(commit)
                        for diff in diffs:
                            # Track files changed
                            if diff.b_path:
                                self.contributions[author]["files_changed"].add(diff.b_path)
                            
                            # Count lines added/deleted
                            if diff.diff:
                                lines = diff.diff.decode('utf-8', errors='ignore').split('\n')
                                for line in lines:
                                    if line.startswith('+') and not line.startswith('+++'):
                                        self.contributions[author]["lines_added"] += 1
                                    elif line.startswith('-') and not line.startswith('---'):
                                        self.contributions[author]["lines_deleted"] += 1
                    else:
                        # Initial commit - count all files as changed
                        if commit.tree:
                            self.contributions[author]["files_changed"].update(
                                [item.path for item in commit.tree.traverse()]
                            )
                            self.contributions[author]["lines_added"] += 1000  # Approximate
                except Exception as e:
                    print(f"  ⚠️ Error processing diff for commit {commit.hexsha[:7]}: {e}")
                
                # Store commit details
                self.contributions[author]["commit_details"].append({
                    "sha": commit.hexsha[:7],
                    "message": commit.message.strip().split('\n')[0],
                    "date": commit.committed_datetime.isoformat(),
                    "author_name": author_name,
                    "author_email": author
                })
        
        except Exception as e:
            print(f"❌ Error analyzing commits: {e}")
        
        return self._compile_statistics()
    
    def _compile_statistics(self) -> Dict:
        """Compile final contribution statistics."""
        stats = {
            "total_authors": len(self.contributions),
            "total_commits": sum(c["commits"] for c in self.contributions.values()),
            "authors": {}
        }
        
        for author, data in self.contributions.items():
            stats["authors"][author] = {
                "commits": data["commits"],
                "files_changed": len(data["files_changed"]),
                "lines_added": data["lines_added"],
                "lines_deleted": data["lines_deleted"],
                "net_lines": data["lines_added"] - data["lines_deleted"],
                "first_commit": data["first_commit"].isoformat() if data["first_commit"] else None,
                "last_commit": data["last_commit"].isoformat() if data["last_commit"] else None,
                "recent_commits": data["commit_details"][-5:]  # Last 5 commits
            }
        
        # Sort by commits descending
        stats["authors"] = dict(sorted(
            stats["authors"].items(),
            key=lambda x: x[1]["commits"],
            reverse=True
        ))
        
        return stats
    
    def get_top_contributors(self, limit: int = 10) -> List[Tuple[str, Dict]]:
        """Get top contributors by commit count."""
        stats = self._compile_statistics()
        return list(stats["authors"].items())[:limit]
    
    def get_contribution_summary(self) -> Dict:
        """Get summary statistics about contributions."""
        stats = self._compile_statistics()
        
        if not stats["authors"]:
            return {
                "total_authors": 0,
                "total_commits": 0,
                "total_files_changed": 0,
                "total_lines_added": 0,
                "total_lines_deleted": 0,
            }
        
        return {
            "total_authors": stats["total_authors"],
            "total_commits": stats["total_commits"],
            "total_files_changed": sum(a["files_changed"] for a in stats["authors"].values()),
            "total_lines_added": sum(a["lines_added"] for a in stats["authors"].values()),
            "total_lines_deleted": sum(a["lines_deleted"] for a in stats["authors"].values()),
            "top_contributor": next(iter(stats["authors"].keys())) if stats["authors"] else None,
            "top_contributor_commits": next(iter(stats["authors"].values()))["commits"] if stats["authors"] else 0
        }


def extract_contributions(repo_path: str, save_path: Optional[str] = None) -> Dict:
    """
    Extract contribution data from a repository.
    
    Args:
        repo_path: Path to repository
        save_path: Optional path to save JSON results
    
    Returns:
        Dictionary with contribution statistics
    """
    analyzer = ContributionsAnalyzer(repo_path)
    stats = analyzer.analyze_all_commits()
    
    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        with open(save_path, 'w') as f:
            json.dump(stats, f, indent=2, default=str)
        print(f"💾 Contributions saved to {save_path}")
    
    return stats
