#!/usr/bin/env python3
"""
Test hybrid ingestion system with size-based API/ZIP decision.

This script demonstrates:
1. Repository size analysis using GitHub API
2. Automatic decision between API and ZIP ingestion based on thresholds
3. Detailed timing information for each ingestion method
4. Memory-efficient processing of large repositories
"""

import os
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()  # Load environment variables from .env file if present
except ImportError:
    pass  # dotenv is optional

# Adjust this to your project root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ingestion.ingest import ingest_repo

# Configuration
owner = "pallets"
repo = "flask"
repo_url = f"https://github.com/{owner}/{repo}"
token = os.getenv("GITHUB_TOKEN")  # Recommended for rate limits

print("=" * 70)
print("HYBRID INGESTION TEST")
print("=" * 70)
print(f"\nRepository: {owner}/{repo}")
print(f"URL: {repo_url}")
print(f"GitHub Token: {'Available' if token else 'NOT SET (may hit rate limits)'}")

print("\n" + "=" * 70)
print("CONFIGURED THRESHOLDS:")
print("=" * 70)
from ingestion.ingest import MAX_API_FILES, MAX_API_SIZE_MB, MAX_API_ESTIMATED_CALLS
print(f"  MAX_API_FILES:           {MAX_API_FILES}")
print(f"  MAX_API_SIZE_MB:         {MAX_API_SIZE_MB} MB")
print(f"  MAX_API_ESTIMATED_CALLS: {MAX_API_ESTIMATED_CALLS}")

print("\n" + "=" * 70)
print("STARTING INGESTION PROCESS")
print("=" * 70 + "\n")

try:
    # Run ingestion with hybrid mode selection
    result = ingest_repo(
        repo_url_or_path=repo_url,
        repo_name=f"{owner}.{repo}",
        analyze_contributions=False,  # Skip for speed on large repos
        verbose=False,
    )
    
    print("\n[OK] Ingestion completed successfully!")
    
except Exception as e:
    print(f"\n[ERROR] Ingestion failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
