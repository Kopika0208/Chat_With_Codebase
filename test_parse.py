import json
from collections import defaultdict

# Direct test of parsing logic
st = json.load(open('data/MeetMate-AI-Meeting-Assistant/symbol_table.json'))

def _parse_symbol_table(symbol_table):
    """Parse symbol table - handles nested format."""
    if not symbol_table:
        return {}
    
    if 'global_index' in symbol_table:
        flattened = {}
        
        # Add global symbols
        global_symbols = symbol_table['global_index'].get('global_symbols', {})
        if isinstance(global_symbols, dict):
            for symbol_name, occurrences in global_symbols.items():
                # Each symbol can have multiple occurrences (in different files)
                # Use the first occurrence as the primary definition
                if isinstance(occurrences, list) and len(occurrences) > 0:
                    first_occurrence = occurrences[0]
                    if isinstance(first_occurrence, dict):
                        flattened[symbol_name] = {
                            "name": symbol_name,
                            "file": first_occurrence.get("file", "unknown"),
                            "type": "function",  # simplified
                            "kind": first_occurrence.get("kind", "unknown"),
                            "start_line": first_occurrence.get("line", 0),
                        }
        
        return flattened
    
    return symbol_table

# Parse
parsed = _parse_symbol_table(st)
print(f"Total symbols parsed: {len(parsed)}")

# Count functions
functions = {name: info for name, info in parsed.items() if info.get('kind') == 'function'}
imports = {name: info for name, info in parsed.items() if info.get('kind') == 'import'}
classes = {name: info for name, info in parsed.items() if info.get('kind') == 'class'}

print(f"Functions: {len(functions)}")
print(f"Imports: {len(imports)}")
print(f"Classes: {len(classes)}")
print(f"\nSample functions: {list(functions.keys())[:5]}")

# Get unique files
files = set(info.get('file', 'unknown') for info in parsed.values())
print(f"\nUnique files: {len(files)}")
print(f"Sample files: {sorted(files)[:5]}")
