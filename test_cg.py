import json

cg = json.load(open('data/MeetMate-AI-Meeting-Assistant/call_graph.json'))
print(f'Call graph nodes: {len(cg)}')
print(f'Sample nodes: {list(cg.keys())[:10]}')

# Analyze structure
sample_val = list(cg.values())[0] if cg else {}
print(f'Sample value type: {type(sample_val)}')
print(f'Sample value: {sample_val}')
