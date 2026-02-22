"""
Contribution analytics visualization for Streamlit.
Displays code contribution metrics, commit history, and author statistics.
"""

import streamlit as st
import json
import os
from typing import Dict, List, Optional
from datetime import datetime


def load_contributions_data(repo_name: str) -> Optional[Dict]:
    """
    Load contributions data from the data directory.
    
    Args:
        repo_name: Name of the repository
    
    Returns:
        Contributions data dict or None if not found
    """
    try:
        contributions_path = os.path.join("data", repo_name, "contributions.json")
        
        if os.path.exists(contributions_path):
            with open(contributions_path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"⚠️ Error loading contributions data: {e}")
    
    return None


def render_contributions_tab(repo_name: str):
    """
    Render comprehensive contributions analytics in a Streamlit tab.
    
    Args:
        repo_name: Name of the active repository
    """
    contributions = load_contributions_data(repo_name)
    
    if not contributions:
        st.info("📊 No contribution data available. Please ensure the repository was ingested with contribution analysis.")
        return
    
    # Extract summary and authors data
    authors = contributions.get("authors", {})
    total_authors = contributions.get("total_authors", 0)
    total_commits = contributions.get("total_commits", 0)
    
    if not authors:
        st.warning("No contribution data found in this repository.")
        return
    
    # ========== SUMMARY STATISTICS ==========
    st.markdown("### 📊 Contribution Summary")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("👥 Total Authors", total_authors)
    
    with col2:
        st.metric("📝 Total Commits", total_commits)
    
    # Calculate total files changed and lines
    total_files_changed = sum(author_data.get("files_changed", 0) for author_data in authors.values())
    total_lines_added = sum(author_data.get("lines_added", 0) for author_data in authors.values())
    
    with col3:
        st.metric("📁 Files Changed", total_files_changed)
    
    with col4:
        st.metric("➕ Lines Added", total_lines_added)
    
    st.divider()
    
    # ========== TOP CONTRIBUTORS ==========
    st.markdown("### 🏆 Top Contributors")
    
    # Sort authors by commits
    sorted_authors = sorted(
        authors.items(),
        key=lambda x: x[1].get("commits", 0),
        reverse=True
    )
    
    # Create a table with top contributors
    top_n = min(15, len(sorted_authors))
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.write("**Rank**")
    with col2:
        st.write("**Author**")
    with col3:
        st.write("**Commits**")
    with col4:
        st.write("**Files Changed**")
    with col5:
        st.write("**Net Lines**")
    
    st.divider()
    
    for idx, (author_email, author_data) in enumerate(sorted_authors[:top_n], 1):
        col1, col2, col3, col4, col5 = st.columns(5)
        
        # Extract author name from email if available
        author_display = author_email
        if "recent_commits" in author_data and author_data["recent_commits"]:
            author_display = author_data["recent_commits"][0].get("author_name", author_email)
        
        commits = author_data.get("commits", 0)
        files_changed = author_data.get("files_changed", 0)
        net_lines = author_data.get("net_lines", 0)
        
        with col1:
            st.write(f"**#{idx}**")
        with col2:
            st.write(author_display)
        with col3:
            st.write(f"{commits}")
        with col4:
            st.write(f"{files_changed}")
        with col5:
            color = "🟢" if net_lines > 0 else "🔴"
            st.write(f"{color} {net_lines:+,}")
    
    st.divider()
    
    # ========== DETAILED AUTHOR BREAKDOWN ==========
    st.markdown("### 📋 Detailed Author Metrics")
    
    # Create tabs for each top contributor
    if len(sorted_authors) > 0:
        author_tabs = st.tabs([
            f"{authors[email].get('commits', 0)} commits: {email[:30]}..."
            for email, _ in sorted_authors[:5]
        ])
        
        for tab_idx, (author_email, author_data) in enumerate(sorted_authors[:5]):
            with author_tabs[tab_idx]:
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Commits", author_data.get("commits", 0))
                
                with col2:
                    st.metric("Files Modified", author_data.get("files_changed", 0))
                
                with col3:
                    st.metric("Lines Added", author_data.get("lines_added", 0))
                
                with col4:
                    st.metric("Lines Deleted", author_data.get("lines_deleted", 0))
                
                st.divider()
                
                # Recent commits
                recent_commits = author_data.get("recent_commits", [])
                if recent_commits:
                    st.markdown("**Recent Commits:**")
                    for commit in recent_commits:
                        commit_sha = commit.get("sha", "?")
                        commit_msg = commit.get("message", "No message")
                        commit_date = commit.get("date", "?")
                        
                        # Format date for display
                        try:
                            dt = datetime.fromisoformat(commit_date)
                            date_str = dt.strftime("%Y-%m-%d %H:%M")
                        except:
                            date_str = commit_date
                        
                        st.write(f"**{commit_msg}** `{commit_sha}` ({date_str})")
                
                # Display contribution period
                first_commit = author_data.get("first_commit")
                last_commit = author_data.get("last_commit")
                
                if first_commit and last_commit:
                    st.divider()
                    try:
                        first_dt = datetime.fromisoformat(first_commit).strftime("%Y-%m-%d")
                        last_dt = datetime.fromisoformat(last_commit).strftime("%Y-%m-%d")
                        st.write(f"**Active Period:** {first_dt} to {last_dt}")
                    except:
                        st.write(f"**Active Period:** {first_commit} to {last_commit}")
    
    st.divider()
    
    # ========== CONTRIBUTION DISTRIBUTION ==========
    st.markdown("### 📈 Contribution Distribution")
    
    # Create a bar chart of commits per author using Streamlit (no plotly needed)
    try:
        import pandas as pd
        
        top_n_dist = min(20, len(sorted_authors))
        top_authors_data = sorted_authors[:top_n_dist]
        
        author_names = []
        commits_list = []
        
        for author_email, author_data in top_authors_data:
            # Get author name from recent commits if available
            author_name = author_email
            if author_data.get("recent_commits"):
                author_name = author_data["recent_commits"][0].get("author_name", author_email)
            
            author_names.append(author_name[:20])  # Truncate long names
            commits_list.append(author_data.get("commits", 0))
        
        # Create DataFrame for Streamlit's built-in chart
        chart_data = pd.DataFrame({
            'Author': author_names,
            'Commits': commits_list
        })
        
        st.bar_chart(chart_data.set_index('Author'), use_container_width=True)
    except Exception as e:
        st.warning(f"Could not render chart: {e}")
    
    # ========== COMMIT ACTIVITY ==========
    st.markdown("### 📅 Commits Over Time")
    
    # Group commits by author for timeline
    st.write(f"**Repository has {total_commits} commits from {total_authors} authors**")
    
    # Create a simple text timeline
    for rank, (author_email, author_data) in enumerate(sorted_authors[:5], 1):
        author_name = author_email
        if author_data.get("recent_commits"):
            author_name = author_data["recent_commits"][0].get("author_name", author_email)
        
        commits_count = author_data.get("commits", 0)
        percentage = (commits_count / total_commits * 100) if total_commits > 0 else 0
        
        # Create a progress bar
        st.write(f"{author_name}: {commits_count} commits ({percentage:.1f}%)")
        st.progress(commits_count / max(c for _, c in [(e, a.get("commits", 0)) for e, a in sorted_authors[:5]]))
        st.write("")
