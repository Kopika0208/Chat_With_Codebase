"""
Git contributions analyzer - tracks commits, authors, and code changes.
Computes contribution metrics like commits per author, lines changed, files modified.
"""

import json
import os
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

try:
    from git import Repo
except ImportError:
    Repo = None


class ContributionsAnalyzer:
    """Analyzes git history to compute contribution metrics."""

    def __init__(self, repo_path: str):
        self.repo_path = repo_path
        try:
            self.repo = Repo(repo_path)
        except Exception as exc:
            print(f"Error initializing repo: {exc}")
            self.repo = None

        self.contributions = defaultdict(
            lambda: {
                "commits": 0,
                "files_changed": set(),
                "lines_added": 0,
                "lines_deleted": 0,
                "first_commit": None,
                "last_commit": None,
                "commit_details": [],
            }
        )

    def analyze_all_commits(
        self,
        max_commits: Optional[int] = None,
        include_commit_details: bool = True,
        progress_every: int = 500,
    ) -> Dict:
        """Analyze all commits in the repository."""
        if not self.repo:
            return {}

        try:
            commit_iter = self.repo.iter_commits(max_count=max_commits)
            processed_commits = 0
            limit_msg = f" (limit: {max_commits})" if max_commits else ""
            print(f"Analyzing git commits{limit_msg}...")

            for idx, commit in enumerate(commit_iter):
                if progress_every and idx > 0 and idx % progress_every == 0:
                    print(f"  Processed {idx} commit(s)...")

                author = (commit.author.email if commit.author else "Unknown").lower()
                author_name = commit.author.name if commit.author else "Unknown"
                processed_commits += 1

                self.contributions[author]["commits"] += 1
                commit_dt = commit.committed_datetime
                if self.contributions[author]["first_commit"] is None:
                    self.contributions[author]["first_commit"] = commit_dt
                self.contributions[author]["last_commit"] = commit_dt

                try:
                    if commit.parents:
                        diff_output = self.repo.git.diff(
                            commit.parents[0].hexsha,
                            commit.hexsha,
                            numstat=True,
                        )
                        if diff_output:
                            for line in diff_output.split("\n"):
                                if not line.strip():
                                    continue
                                parts = line.split("\t")
                                if len(parts) < 3:
                                    continue
                                try:
                                    added = int(parts[0]) if parts[0] != "-" else 0
                                    deleted = int(parts[1]) if parts[1] != "-" else 0
                                except ValueError:
                                    continue
                                file_path = parts[2]
                                self.contributions[author]["lines_added"] += added
                                self.contributions[author]["lines_deleted"] += deleted
                                self.contributions[author]["files_changed"].add(file_path)
                    elif commit.tree:
                        file_count = 0
                        for item in commit.tree.traverse():
                            if item.type == "blob":
                                self.contributions[author]["files_changed"].add(item.path)
                                file_count += 1
                        self.contributions[author]["lines_added"] += file_count * 10
                except Exception as exc:
                    print(f"  Error processing diff for commit {commit.hexsha[:7]}: {exc}")

                if include_commit_details:
                    self.contributions[author]["commit_details"].append({
                        "sha": commit.hexsha[:7],
                        "message": commit.message.strip().split("\n")[0],
                        "date": commit.committed_datetime.isoformat(),
                        "author_name": author_name,
                        "author_email": author,
                    })
        except Exception as exc:
            print(f"Error analyzing commits: {exc}")

        stats = self._compile_statistics()
        stats["analysis_scope"] = {
            "max_commits": max_commits,
            "processed_commits": processed_commits if 'processed_commits' in locals() else 0,
            "include_commit_details": include_commit_details,
        }
        return stats

    def _compile_statistics(self) -> Dict:
        """Compile final contribution statistics."""
        deduped_contributions = {}
        email_mapping = {}

        for author, data in self.contributions.items():
            author_lower = author.lower()
            if author_lower not in email_mapping:
                email_mapping[author_lower] = author
                deduped_contributions[author] = data
            else:
                canonical_author = email_mapping[author_lower]
                deduped_contributions[canonical_author]["commits"] += data["commits"]
                deduped_contributions[canonical_author]["files_changed"].update(data["files_changed"])
                deduped_contributions[canonical_author]["lines_added"] += data["lines_added"]
                deduped_contributions[canonical_author]["lines_deleted"] += data["lines_deleted"]

                if data["first_commit"] and (
                    not deduped_contributions[canonical_author]["first_commit"]
                    or data["first_commit"] < deduped_contributions[canonical_author]["first_commit"]
                ):
                    deduped_contributions[canonical_author]["first_commit"] = data["first_commit"]
                if data["last_commit"] and (
                    not deduped_contributions[canonical_author]["last_commit"]
                    or data["last_commit"] > deduped_contributions[canonical_author]["last_commit"]
                ):
                    deduped_contributions[canonical_author]["last_commit"] = data["last_commit"]

                deduped_contributions[canonical_author]["commit_details"].extend(data["commit_details"])

        stats = {
            "total_authors": len(deduped_contributions),
            "total_commits": sum(entry["commits"] for entry in deduped_contributions.values()),
            "authors": {},
        }

        for author, data in deduped_contributions.items():
            recent_commits = sorted(
                data["commit_details"],
                key=lambda item: item.get("date", ""),
                reverse=True,
            )[:5]
            stats["authors"][author] = {
                "commits": data["commits"],
                "files_changed": len(data["files_changed"]),
                "lines_added": data["lines_added"],
                "lines_deleted": data["lines_deleted"],
                "net_lines": data["lines_added"] - data["lines_deleted"],
                "first_commit": data["first_commit"].isoformat() if data["first_commit"] else None,
                "last_commit": data["last_commit"].isoformat() if data["last_commit"] else None,
                "recent_commits": recent_commits,
            }

        stats["authors"] = dict(
            sorted(
                stats["authors"].items(),
                key=lambda item: item[1]["commits"],
                reverse=True,
            )
        )
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
            "total_files_changed": sum(author["files_changed"] for author in stats["authors"].values()),
            "total_lines_added": sum(author["lines_added"] for author in stats["authors"].values()),
            "total_lines_deleted": sum(author["lines_deleted"] for author in stats["authors"].values()),
            "top_contributor": next(iter(stats["authors"].keys())) if stats["authors"] else None,
            "top_contributor_commits": next(iter(stats["authors"].values()))["commits"] if stats["authors"] else 0,
        }


def extract_contributions(
    repo_path: str,
    save_path: Optional[str] = None,
    max_commits: Optional[int] = None,
    include_commit_details: bool = True,
) -> Dict:
    """Extract contribution data from a repository."""
    analyzer = ContributionsAnalyzer(repo_path)
    stats = analyzer.analyze_all_commits(
        max_commits=max_commits,
        include_commit_details=include_commit_details,
    )

    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        with open(save_path, "w", encoding="utf-8") as handle:
            json.dump(stats, handle, indent=2, default=str)
        print(f"Contributions saved to {save_path}")

    return stats
