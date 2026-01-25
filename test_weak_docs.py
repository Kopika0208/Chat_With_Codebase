import json
from collections import defaultdict

# Load data
st = json.load(open('data/MeetMate-AI-Meeting-Assistant/symbol_table.json'))
cg = json.load(open('data/MeetMate-AI-Meeting-Assistant/call_graph.json'))
df = json.load(open('data/MeetMate-AI-Meeting-Assistant/dataflow_analysis.json'))

# Parse symbol table
def parse_st(st_data):
    if 'global_index' in st_data:
        flattened = {}
        gs = st_data['global_index'].get('global_symbols', {})
        for name, occs in gs.items():
            if isinstance(occs, list) and len(occs) > 0:
                first = occs[0]
                flattened[name] = {
                    'kind': first.get('kind'),
                    'file': first.get('file'),
                    'line': first.get('line', 0),
                }
        return flattened
    return {}

parsed_st = parse_st(st)

# Find weak doc candidates
print("=" * 60)
print("WEAK DOCUMENTATION DETECTION")
print("=" * 60)

# Calculate complexity for each function/method
candidates = []

for name, info in parsed_st.items():
    if info.get('kind') not in ['function', 'method']:
        continue
    
    # Get metrics
    num_callees = len(cg.get(name, []))
    
    # Count callers
    in_degree = sum(1 for callees in cg.values() 
                   if (isinstance(callees, list) and name in callees) or 
                       (isinstance(callees, dict) and name in callees.values()))
    
    # Dataflow ops
    df_ops = 0
    if name in df:
        df_data = df[name]
        df_ops = len(df_data.get('reads', [])) + len(df_data.get('writes', []))
    
    complexity = (num_callees * 5) + (df_ops * 3) + (in_degree * 2)
    
    if num_callees > 0 or in_degree > 0:  # Only include if it has relationships
        candidates.append({
            'name': name,
            'kind': info['kind'],
            'callees': num_callees,
            'callers': in_degree,
            'dataflow_ops': df_ops,
            'complexity': complexity,
        })

candidates = sorted(candidates, key=lambda x: -x['complexity'])

print(f"\nFunctions/Methods with relationships: {len(candidates)}")
print(f"\nTop 10 Most Complex (potential weak documentation targets):")
for i, c in enumerate(candidates[:10], 1):
    print(f"\n{i}. {c['name']}")
    print(f"   Kind: {c['kind']}")
    print(f"   Calls {c['callees']} functions")
    print(f"   Called by {c['callers']} places")
    print(f"   Dataflow operations: {c['dataflow_ops']}")
    print(f"   Complexity score: {c['complexity']}")
