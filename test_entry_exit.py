import json
from collections import defaultdict

# Load call graph (primary data source now)
cg = json.load(open('data/MeetMate-AI-Meeting-Assistant/call_graph.json'))
st = json.load(open('data/MeetMate-AI-Meeting-Assistant/symbol_table.json'))

print("=" * 60)
print("CALL GRAPH ANALYSIS")
print("=" * 60)

# Calculate in/out degrees
in_degree = defaultdict(int)
out_degree = defaultdict(int)
all_callers = set(cg.keys())
all_callees = set()

for caller, callees in cg.items():
    callees_list = callees if isinstance(callees, list) else list(callees.values())
    out_degree[caller] = len(callees_list)
    for callee in callees_list:
        in_degree[callee] += 1
        all_callees.add(callee)

print(f"\nTotal functions with outgoing calls: {len(all_callers)}")
print(f"Total functions called: {len(all_callees)}")
print(f"Functions that are called but don't call others: {len(all_callees - all_callers)}")

# Find entry points
print(f"\n--- ENTRY POINTS (Low in-degree) ---")
entry_points = []
for func_name, out_count in sorted(out_degree.items(), key=lambda x: (in_degree[x[0]], -x[1])):
    in_count = in_degree[func_name]
    short_name = func_name.split(':')[-1]
    
    if in_count <= 1 and out_count > 0:
        entry_points.append((func_name, in_count, out_count))
        print(f"  {short_name}: {in_count} caller(s), {out_count} callee(s)")
        if len(entry_points) >= 5:
            break

# Find exit points
print(f"\n--- EXIT POINTS (No outgoing calls) ---")
exit_count = 0
for func_name in all_callees - all_callers:
    if exit_count >= 5:
        break
    short_name = func_name.split(':')[-1]
    print(f"  {short_name}: {in_degree[func_name]} caller(s)")
    exit_count += 1

# Check for zero-out-degree
print(f"\n--- ZERO OUT-DEGREE (in graph) ---")
zero_out = [f for f, cnt in out_degree.items() if cnt == 0]
for func_name in zero_out[:5]:
    short_name = func_name.split(':')[-1]
    print(f"  {short_name}: {in_degree[func_name]} caller(s), 0 callees")
