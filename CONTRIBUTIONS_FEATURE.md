# Code Contributions Analytics Feature

## Overview

This feature adds comprehensive code contribution tracking and visualization to the Chat with Codebase project. It analyzes git commit history to show:

- **Total authors and commits** in the repository
- **Top contributors** ranked by commit count
- **Lines added/deleted** per author
- **Files modified** per author
- **Recent commit history** for each contributor
- **Contribution distribution charts** showing commit percentages
- **Contributor activity timeline**

## Files Added/Modified

### New Files Created:

1. **`ingestion/contributions.py`** - Core contribution analysis module
   - Analyzes git commit history
   - Extracts author information and contribution metrics
   - Computes lines added/deleted per file
   - Tracks files modified by each author
   - Exports contribution statistics to JSON

2. **`retrieval/contributions_viz.py`** - Streamlit visualization module
   - Loads contribution data from JSON files
   - Renders contribution statistics in Streamlit UI
   - Creates interactive charts and tables
   - Displays author-specific contribution details
   - Shows commit timelines and contribution distribution

### Modified Files:

1. **`ingestion/ingest.py`**
   - Added import for `extract_contributions` function
   - Integrated contribution analysis into main ingestion pipeline
   - Saves contributions data as `contributions.json` in data directory
   - Updated multi-repo ingestion to handle contributions
   - Saves aggregated contributions for multi-repo setups

2. **`retrieval/app.py`**
   - Added import for `render_contributions_tab`
   - Added "👥 Contributions" tab to onboarding tabs
   - Integrated contribution visualization in the UI
   - Tab displays comprehensive contribution analytics

## How It Works

### 1. During Repository Ingestion

When a repository is ingested:
```
retrieval/app.py (Ingest Button)
    ↓
ingestion/ingest.py (ingest_repo function)
    ↓
ingestion/contributions.py (extract_contributions)
    ↓
git history analysis
    ↓
Save to data/{repo_name}/contributions.json
```

### 2. Data Collection Process

The `ContributionsAnalyzer` class:
- Iterates through all commits in chronological order
- Extracts author information and timestamps
- Analyzes code changes (diffs) for each commit
- Counts lines added/deleted per file
- Tracks files modified by each author
- Groups recent commits for each author

### 3. UI Display

When viewing a repository in the app:
1. Click on the **"👥 Contributions"** tab
2. View:
   - **Summary Statistics**: Total authors, commits, files changed, lines added
   - **Top Contributors Table**: Ranked by commits with detailed metrics
   - **Detailed Metrics Per Author**: Tabbed view showing recent commits and activity period
   - **Contribution Distribution Chart**: Visual bar chart of commits per author
   - **Contribution Timeline**: Progress bars showing contribution percentages

## Data Structure

### contributions.json Format

```json
{
  "total_authors": 5,
  "total_commits": 150,
  "authors": {
    "john@example.com": {
      "commits": 45,
      "files_changed": 23,
      "lines_added": 1500,
      "lines_deleted": 300,
      "net_lines": 1200,
      "first_commit": "2025-01-15T10:30:00+00:00",
      "last_commit": "2026-02-21T14:45:00+00:00",
      "recent_commits": [
        {
          "sha": "a1b2c3d",
          "message": "Fix: Update API endpoints",
          "date": "2026-02-21T14:45:00+00:00",
          "author_name": "John Doe",
          "author_email": "john@example.com"
        }
      ]
    }
  }
}
```

## Key Features

### 1. Comprehensive Metrics
- **Commits**: Number of commits per author
- **Files Changed**: Unique files modified
- **Lines Added/Deleted**: Code changes per author
- **Net Lines**: Net contribution (added - deleted)
- **Activity Period**: First and last commit dates

### 2. Visualization
- **Top Contributors Table**: Easy-to-scan ranking
- **Interactive Charts**: Plotly-based bar charts
- **Author Tabs**: Drill-down into individual contributors
- **Timeline View**: Visual representation of commit percentages

### 3. Multi-Repository Support
- Each repository tracks contributions separately
- Aggregated contributions data when ingesting multiple repos
- Per-repository data in `data/{repo_name}/contributions.json`
- Aggregated data in `data/contributions.json`

## Usage

### Viewing Contributions

1. **Start the app**:
   ```bash
   streamlit run retrieval/app.py
   ```

2. **Ingest a repository** or select an existing one

3. **Navigate to the "👥 Contributions" tab** in the onboarding section

4. **Explore the metrics**:
   - See summary statistics at the top
   - View top contributors in ranked table
   - Click on author tabs to see detailed commit history
   - View distribution chart and timeline

### API Usage (Programmatic)

```python
from ingestion.contributions import extract_contributions

# Extract contribution data for a repository
contributions = extract_contributions(
    repo_path="/path/to/repo",
    save_path="/path/to/data/contributions.json"
)

# Access statistics
print(f"Total authors: {contributions['total_authors']}")
print(f"Total commits: {contributions['total_commits']}")

# Get specific author info
author_data = contributions['authors']['john@example.com']
print(f"Commits: {author_data['commits']}")
print(f"Files changed: {author_data['files_changed']}")
```

## Performance Considerations

### Processing Time
- Analyzing git history can take time for large repositories
- Time depends on:
  - Number of commits
  - Depth of commit history
  - Complexity of diffs
  - File sizes and count

### Typical Processing Times
- **Small repos (100-500 commits)**: 5-15 seconds
- **Medium repos (500-5000 commits)**: 30-120 seconds
- **Large repos (5000+ commits)**: 2-10+ minutes

### Optimization Tips
- For very large repos, consider analyzing a specific branch:
  ```python
  # In contributions.py, limit commits with max_count parameter
  commits = list(self.repo.iter_commits(max_count=1000))
  ```

## Troubleshooting

### Issue: "No contribution data available"
**Cause**: Repository was ingested before this feature was added, or git analysis failed
**Solution**: Re-ingest the repository

### Issue: Git analysis is slow
**Cause**: Large repository or slow disk/network I/O
**Solution**: 
- Use a local repository copy
- Consider analyzing specific branches
- Increase timeout in ingestion settings

### Issue: Author names show as emails
**Cause**: Some commits don't have author name configured
**Solution**: This is normal; git uses email when name is unavailable

## Future Enhancements

Potential improvements:
1. **Time-series analysis**: Contribution trends over months/years
2. **File-level attribution**: Which files each author touched
3. **Code review metrics**: Integration with GitHub/GitLab APIs
4. **Collaboration patterns**: Author interaction analysis
5. **Code ownership**: Automatic codebase ownership assignment
6. **Contributor onboarding**: Identify new vs. veteran contributors
7. **Team metrics**: Contribution patterns per team
8. **Export reports**: PDF/HTML reports of contribution metrics

## Technical Details

### Dependencies
- `GitPython`: For git repository analysis
- `Streamlit`: For UI rendering
- `Plotly`: For interactive charts

### Files Modified Statistics
The analysis tracks:
- Files added
- Files modified
- Files deleted (if diff detected)
- Lines added per file
- Lines deleted per file

### Commit Time Processing
- All timestamps standardized to UTC via `astimezone(timezone.utc)`
- ISO 8601 format for storage: `YYYY-MM-DDTHH:MM:SS+00:00`

## Examples

### Example 1: Find Most Active Developer
```python
from retrieval.contributions_viz import load_contributions_data

contributions = load_contributions_data("my-repo")
authors = sorted(
    contributions["authors"].items(),
    key=lambda x: x[1]["commits"],
    reverse=True
)
top_author = authors[0]
print(f"Most active: {top_author[0]} with {top_author[1]['commits']} commits")
```

### Example 2: Calculate Team Productivity
```python
contributions = load_contributions_data("my-repo")
total_lines = sum(a["lines_added"] for a in contributions["authors"].values())
print(f"Total lines added by team: {total_lines}")
```

### Example 3: Identify Code Experts
```python
contributions = load_contributions_data("my-repo")
for author, data in contributions["authors"].items():
    if data["files_changed"] > 50:  # High-file count = broad expertise
        print(f"{author} is an expert (modified {data['files_changed']} files)")
```

## Contributing

To improve the contributions feature:
1. Modify `ingestion/contributions.py` for analysis logic
2. Modify `retrieval/contributions_viz.py` for UI visualization
3. Run tests with various repository types
4. Update this documentation

## License

This feature is part of the Chat with Codebase project.
