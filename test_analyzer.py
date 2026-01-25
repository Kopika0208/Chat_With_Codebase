import json
import sys
sys.path.insert(0, '.')

from retrieval.onboarding.analyzer import CodebaseAnalyzer

# Load data
with open('data/MeetMate-AI-Meeting-Assistant/symbol_table.json') as f:
    st = json.load(f)
with open('data/MeetMate-AI-Meeting-Assistant/call_graph.json') as f:
    cg = json.load(f)

# Create analyzer
analyzer = CodebaseAnalyzer(
    call_graph=cg, 
    symbol_table=st, 
    repo_path='data/MeetMate-AI-Meeting-Assistant', 
    root_dir='repos/MeetMate-AI-Meeting-Assistant'
)

# Get stats
stats = analyzer.get_project_stats()
print(f'Files: {stats["total_files"]}')
print(f'Functions: {stats["total_functions"]}')
print(f'Classes: {stats["total_classes"]}')
print(f'Total Symbols: {stats["total_symbols"]}')
print(f'Sample Files: {stats["all_files"][:5]}')

# Test entry points
entry_points = analyzer.get_entry_points()
print(f'\nEntry Points Found: {len(entry_points)}')
for ep in entry_points[:3]:
    print(f'  - {ep["name"]} ({ep["type"]}) in {ep["file"]}')

# Test exit points
exit_points = analyzer.get_exit_points()
print(f'\nExit Points Found: {len(exit_points)}')
for xp in exit_points[:3]:
    print(f'  - {xp["name"]} ({xp["type"]}) in {xp["file"]}')
