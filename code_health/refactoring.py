"""
Refactoring Suggestion Generator.
Provides actionable refactoring guidance based on detected smells.
Uses LLM (Groq) for context-aware suggestions with fallback to hardcoded templates.
"""

from typing import Dict, List, Optional
import json
import os

# Try to import LLM from cache, fallback to None if unavailable
try:
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    from retrieval.cache import get_llm
    HAS_LLM = True
except Exception:
    get_llm = None
    HAS_LLM = False


class RefactoringAdvisor:
    """Generates refactoring suggestions using LLM with hardcoded fallback."""
    
    # Mapping from smell types to refactoring strategies
    REFACTORING_STRATEGIES = {
        'God File': {
            'strategies': ['split', 'extract', 'decompose'],
            'effort': 'high',
            'priority': 'high',
        },
        'Long Functions': {
            'strategies': ['extract', 'decompose', 'inline'],
            'effort': 'medium',
            'priority': 'high',
        },
        'High Cyclomatic Complexity': {
            'strategies': ['extract', 'polymorphism', 'guard_clauses'],
            'effort': 'medium',
            'priority': 'high',
        },
        'Tight Coupling': {
            'strategies': ['decouple', 'extract', 'interface'],
            'effort': 'high',
            'priority': 'medium',
        },
        'Dead/Unused Code': {
            'strategies': ['remove', 'archive'],
            'effort': 'low',
            'priority': 'medium',
        },
        'Orphaned File': {
            'strategies': ['remove', 'integrate', 'relocate'],
            'effort': 'low',
            'priority': 'low',
        },
        'Change Hotspot': {
            'strategies': ['split', 'extract', 'stabilize'],
            'effort': 'high',
            'priority': 'high',
        },
    }
    
    def __init__(self, smells: List[Dict], stats: Dict, code_snippets: Optional[Dict] = None, 
                 language: Optional[str] = None, use_llm: bool = True):
        """
        Initialize refactoring advisor.
        
        Args:
            smells: List of detected code smells
            stats: Code statistics
            code_snippets: Dict mapping file paths to code content for context
            language: Primary programming language (auto-detected if None)
            use_llm: Whether to use LLM for suggestions (True by default)
        """
        self.smells = smells
        self.stats = stats
        self.code_snippets = code_snippets or {}
        self.language = language or self._detect_language()
        self.use_llm = use_llm and HAS_LLM
        self.llm = None
        
        if self.use_llm:
            try:
                self.llm = get_llm()
            except Exception:
                self.use_llm = False
                self.llm = None
    
    def _detect_language(self) -> str:
        """Auto-detect primary programming language from stats."""
        file_stats = self.stats.get('file_stats', {})
        if not file_stats:
            return 'python'
        
        language_count = {}
        for file_path, stats_item in file_stats.items():
            lang = stats_item.get('language', 'python')
            language_count[lang] = language_count.get(lang, 0) + 1
        
        return max(language_count.items(), key=lambda x: x[1])[0] if language_count else 'python'
    
    def generate_suggestions(self) -> List[Dict]:
        """Generate refactoring suggestions for detected smells."""
        suggestions = []
        
        for smell in self.smells:
            # Try LLM first if available
            if self.use_llm and self.llm:
                suggestion = self._generate_llm_suggestion(smell)
                if suggestion:
                    suggestions.append(suggestion)
                    continue
            
            # Fallback to hardcoded suggestions
            suggestion = self._generate_suggestion_for_smell(smell)
            if suggestion:
                suggestions.append(suggestion)
        
        # Sort by priority and effort
        suggestions.sort(key=lambda x: (
            {'high': 0, 'medium': 1, 'low': 2}.get(x['priority'], 2),
            {'low': 0, 'medium': 1, 'high': 2}.get(x['effort'], 1),
        ))
        
        return suggestions
    
    def _generate_llm_suggestion(self, smell: Dict) -> Optional[Dict]:
        """Generate suggestion using LLM with code context."""
        if not self.llm:
            return None
        
        try:
            # Build context
            file_path = smell.get('file', '')
            code_preview = self.code_snippets.get(file_path, '')[:1000] if file_path in self.code_snippets else ''
            
            metrics = smell.get('metrics', {})
            smell_type = smell.get('type', '')
            
            # Build prompt
            prompt = self._build_llm_prompt(smell, metrics, code_preview)
            
            # Get LLM response
            response = self.llm.invoke(prompt)
            
            # Parse response
            suggestion = self._parse_llm_response(response, smell)
            return suggestion if suggestion else None
            
        except Exception as e:
            # Silently fallback to hardcoded on any LLM error
            return None
    
    def _build_llm_prompt(self, smell: Dict, metrics: Dict, code_preview: str) -> str:
        """Build prompt for LLM."""
        smell_type = smell.get('type', '')
        file_path = smell.get('file', '')
        
        prompt = f"""You are a senior software architect analyzing code smells.

DETECTED SMELL: {smell_type}
FILE: {file_path}
LANGUAGE: {self.language}
SEVERITY: {smell.get('severity', 'medium')}

METRICS:
{json.dumps(metrics, indent=2)}

CODE PREVIEW:
```
{code_preview}
```

REQUIREMENTS:
1. Analyze why this specific smell occurred in this code
2. Suggest 2-3 refactoring strategies tailored to this context
3. For each strategy, provide:
   - name: Strategy name
   - description: What it does
   - steps: Numbered actionable steps (4-8 steps)
   - benefit: Specific benefits for this code
4. Include real class/method names from the code when possible
5. Estimate effort realistically
6. Return ONLY valid JSON, no markdown code blocks

RESPONSE FORMAT:
{{
    "smell_type": "{smell_type}",
    "file": "{file_path}",
    "effort": "low/medium/high",
    "priority": "low/medium/high",
    "description": "Context-specific explanation",
    "why_it_happened": "Analysis of root cause in YOUR code",
    "strategies": [
        {{
            "name": "Strategy name",
            "description": "What it does",
            "steps": ["1. Step one", "2. Step two", ...],
            "benefit": "Specific benefits for this file"
        }}
    ],
    "affected_files": ["{file_path}"],
    "rationale": "Why this matters specifically for this code"
}}"""
        
        return prompt
    
    def _parse_llm_response(self, response: str, smell: Dict) -> Optional[Dict]:
        """Parse LLM response JSON."""
        try:
            # Extract JSON from response (handle markdown code blocks if present)
            json_str = response.strip()
            if '```json' in json_str:
                json_str = json_str.split('```json')[1].split('```')[0]
            elif '```' in json_str:
                json_str = json_str.split('```')[1].split('```')[0]
            
            suggestion = json.loads(json_str)
            
            # Validate required fields
            if not all(k in suggestion for k in ['smell_type', 'file', 'effort', 'priority']):
                return None
            
            # Ensure strategies exist
            if 'strategies' not in suggestion:
                suggestion['strategies'] = []
            
            return suggestion
            
        except (json.JSONDecodeError, ValueError, IndexError):
            return None
    
    def load_code_snippets(self, repo_dir: str) -> None:
        """Load code snippets from repository for LLM context."""
        try:
            for smell in self.smells:
                file_path = smell.get('file', '')
                if not file_path or file_path in self.code_snippets:
                    continue
                
                # Try to find file in repo
                full_path = os.path.join(repo_dir, file_path)
                if os.path.isfile(full_path):
                    try:
                        with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                            self.code_snippets[file_path] = f.read()
                    except Exception:
                        pass
        except Exception:
            pass  # Silently fail, continue without code snippets
    
    def _generate_suggestion_for_smell(self, smell: Dict) -> Dict:
        """Generate specific suggestion for a smell."""
        smell_type = smell.get('type', '')
        file_path = smell.get('file', '')
        
        strategy_info = self.REFACTORING_STRATEGIES.get(smell_type, {})
        strategies = strategy_info.get('strategies', [])
        effort = strategy_info.get('effort', 'medium')
        priority = strategy_info.get('priority', 'medium')
        
        # Generate detailed guidance based on smell type
        if smell_type == 'God File':
            return self._suggest_god_file_refactor(smell, effort, priority)
        elif smell_type == 'Long Functions':
            return self._suggest_long_function_refactor(smell, effort, priority)
        elif smell_type == 'High Cyclomatic Complexity':
            return self._suggest_complexity_refactor(smell, effort, priority)
        elif smell_type == 'Tight Coupling':
            return self._suggest_coupling_refactor(smell, effort, priority)
        elif smell_type == 'Dead/Unused Code':
            return self._suggest_dead_code_refactor(smell, effort, priority)
        elif smell_type == 'Orphaned File':
            return self._suggest_orphaned_file_refactor(smell, effort, priority)
        elif smell_type == 'Change Hotspot':
            return self._suggest_hotspot_refactor(smell, effort, priority)
        
        return None
    
    def _suggest_god_file_refactor(self, smell: Dict, effort: str, priority: str) -> Dict:
        """Suggestion for God File smell."""
        metrics = smell.get('metrics', {})
        num_classes = metrics.get('classes', 0)
        num_functions = metrics.get('functions', 0)
        
        strategies = []
        if num_classes > 1:
            strategies.append({
                'name': 'Split by Class',
                'description': f"Extract each of the {num_classes} classes into separate files. "
                             f"Each file should have a single responsibility.",
                'steps': [
                    f"Create new files for each class (e.g., class_name.py)",
                    "Move class definition and related helpers to new file",
                    f"Update imports in {smell['file']}",
                    "Add __all__ exports in new modules",
                    "Update __init__.py if this is a package",
                ],
                'benefit': "Improves modularity, testability, and reduces cognitive load",
            })
        
        if num_functions > 5:
            strategies.append({
                'name': 'Split by Functionality',
                'description': f"Group related functions into logical modules. "
                             f"Create sub-modules for related functionality.",
                'steps': [
                    "Identify functional groups or domains",
                    "Create separate module files for each domain",
                    "Move related functions and classes",
                    "Update imports throughout the codebase",
                    "Consider creating a facade module if inter-module communication is high",
                ],
                'benefit': "Reduces file size, improves discoverability, enables parallel development",
            })
        
        strategies.append({
            'name': 'Extract to Package',
            'description': f"Convert the single file into a package with multiple modules.",
            'steps': [
                f"Rename {smell['file']} directory (if not already a package)",
                "Create __init__.py",
                "Create sub-modules for logical groupings",
                "Expose public API via __init__.py using __all__",
                "Add documentation to __init__.py",
            ],
            'benefit': "Preserves namespace while enabling modular organization",
        })
        
        return {
            'smell_type': 'God File',
            'file': smell['file'],
            'effort': effort,
            'priority': priority,
            'description': smell.get('description', ''),
            'strategies': strategies,
            'affected_files': [smell['file']],
            'rationale': 'God files violate SRP and are hard to maintain. Breaking them down improves code quality.',
        }
    
    def _suggest_long_function_refactor(self, smell: Dict, effort: str, priority: str) -> Dict:
        """Suggestion for Long Function smell."""
        metrics = smell.get('metrics', {})
        avg_length = metrics.get('average_function_length', 0)
        
        strategies = [
            {
                'name': 'Extract Helper Methods',
                'description': f"Break down large functions (avg {int(avg_length)} lines) "
                             f"into smaller, focused helper methods.",
                'steps': [
                    "Identify logical blocks or sub-tasks in the function",
                    "Extract each block into a separate method with a descriptive name",
                    "Update the main function to call helpers in sequence",
                    "Add docstrings explaining what each helper does",
                    "Test extracted functions independently",
                ],
                'benefit': "Improves readability, testability, and reusability",
            },
            {
                'name': 'Extract to Separate Functions',
                'description': "Move related logic into standalone functions for clarity.",
                'steps': [
                    "Identify concepts or operations that can stand alone",
                    "Create new functions with single purposes",
                    "Reduce parameter count by grouping related params (e.g., Config objects)",
                    "Add type hints and docstrings",
                    "Consider making helper functions private (prefix with _)",
                ],
                'benefit': "Enables reuse, improves testability, reduces duplication",
            },
            {
                'name': 'Use Guard Clauses',
                'description': "Replace nested if statements with early returns.",
                'steps': [
                    "Identify deeply nested conditionals",
                    "Move validation/guard logic to the start of function",
                    "Use early returns for invalid cases",
                    "Reduce nesting depth to max 2 levels",
                    "Extract remaining logic if still too complex",
                ],
                'benefit': "Reduces cognitive load, improves code flow clarity",
            },
        ]
        
        return {
            'smell_type': 'Long Functions',
            'file': smell['file'],
            'effort': effort,
            'priority': priority,
            'description': smell.get('description', ''),
            'strategies': strategies,
            'affected_files': [smell['file']],
            'rationale': 'Long functions are hard to understand, test, and maintain.',
        }
    
    def _suggest_complexity_refactor(self, smell: Dict, effort: str, priority: str) -> Dict:
        """Suggestion for High Complexity smell."""
        metrics = smell.get('metrics', {})
        complexity = metrics.get('cyclomatic_complexity', 0)
        
        strategies = [
            {
                'name': 'Extract Methods',
                'description': f"High complexity (CC={int(complexity)}) indicates too many decision paths. "
                             f"Extract conditions into helper methods.",
                'steps': [
                    "Identify separate conditional branches",
                    "Extract each branch/condition into a descriptive method",
                    "Name methods after their purpose (e.g., is_valid_user())",
                    "Replace complex conditions with method calls",
                    "Return early when conditions fail",
                ],
                'benefit': "Reduces complexity, improves readability, easier to test each path",
            },
            {
                'name': 'Use Polymorphism',
                'description': "Replace complex if/elif chains with polymorphic dispatch.",
                'steps': [
                    "Identify if/elif chains checking types or categories",
                    "Create base class or interface",
                    "Create subclasses for each condition",
                    "Implement behavior in each subclass",
                    "Replace switch logic with polymorphic calls",
                ],
                'benefit': "Eliminates switch logic, enables extensibility without modification",
            },
            {
                'name': 'Simplify Logic',
                'description': "Refactor boolean logic and conditions for clarity.",
                'steps': [
                    "Extract complex boolean expressions into named variables",
                    "Use 'not' and 'in' instead of complex comparisons",
                    "Combine related conditions to reduce lines",
                    "Consider using guard clauses to reduce nesting",
                    "Add comments explaining non-obvious logic",
                ],
                'benefit': "Improves readability, reduces bug risk",
            },
        ]
        
        return {
            'smell_type': 'High Cyclomatic Complexity',
            'file': smell['file'],
            'effort': effort,
            'priority': priority,
            'description': smell.get('description', ''),
            'strategies': strategies,
            'affected_files': [smell['file']],
            'rationale': f'Complexity of {int(complexity)} means exponential test combinations. Each reduction matters.',
        }
    
    def _suggest_coupling_refactor(self, smell: Dict, effort: str, priority: str) -> Dict:
        """Suggestion for Tight Coupling smell."""
        metrics = smell.get('metrics', {})
        fan_out = metrics.get('fan_out', 0)
        
        strategies = [
            {
                'name': 'Extract Interface/Abstract Class',
                'description': f"Reduce direct dependencies ({fan_out}) by introducing abstractions.",
                'steps': [
                    "Identify dependencies this module relies on",
                    "Extract common interface from dependencies",
                    "Create abstract base class or protocol",
                    "Depend on abstraction instead of concrete classes",
                    "Inject dependencies at construction time",
                ],
                'benefit': "Decouples from concrete implementations, enables testing with mocks",
            },
            {
                'name': 'Apply Dependency Injection',
                'description': "Reduce coupling by injecting dependencies rather than importing directly.",
                'steps': [
                    "Identify direct imports/dependencies",
                    "Add parameters to functions/classes to accept dependencies",
                    "Remove hard-coded imports where possible",
                    "Create factory or container to wire dependencies",
                    "Test with mock implementations",
                ],
                'benefit': "Increases testability, reduces coupling, improves flexibility",
            },
            {
                'name': 'Reorganize Module Structure',
                'description': "Reduce dependencies by changing module organization.",
                'steps': [
                    "Analyze dependency graph for this module",
                    "Move common utilities to shared module",
                    "Create domain-specific sub-packages",
                    "Reduce cross-package dependencies",
                    "Consider pub/sub patterns for loose coupling",
                ],
                'benefit': "Clearer architecture, fewer circular dependencies, easier navigation",
            },
        ]
        
        return {
            'smell_type': 'Tight Coupling',
            'file': smell['file'],
            'effort': effort,
            'priority': priority,
            'description': smell.get('description', ''),
            'strategies': strategies,
            'affected_files': [smell['file']],
            'rationale': f'Too many dependencies ({fan_out}) create fragility and test complexity.',
        }
    
    def _suggest_dead_code_refactor(self, smell: Dict, effort: str, priority: str) -> Dict:
        """Suggestion for Dead Code smell."""
        metrics = smell.get('metrics', {})
        examples = metrics.get('examples', [])
        
        strategies = [
            {
                'name': 'Remove Dead Code',
                'description': "Delete unused symbols after verification.",
                'steps': [
                    f"Verify symbols are not used: {', '.join(examples[:3])}",
                    "Search codebase for any references (especially string-based lookups)",
                    "Check if exported in __all__ (remove if not)",
                    "Delete the unused symbol definitions",
                    "Run tests to ensure no breakage",
                    "Commit separately with clear message: 'Remove unused code'",
                ],
                'benefit': "Reduces code surface area, removes confusion, speeds up comprehension",
            },
            {
                'name': 'Archive If Uncertain',
                'description': "If unsure if code is used, archive it first.",
                'steps': [
                    "Move potentially unused code to _deprecated.py or archive/",
                    "Add deprecation warnings if it's part of public API",
                    "Wait 1-2 releases for user feedback",
                    "Delete if no one complains",
                    "Keep git history for recovery if needed",
                ],
                'benefit': "Safe removal, can restore if needed, signals intent to users",
            },
        ]
        
        return {
            'smell_type': 'Dead/Unused Code',
            'file': 'Multiple',
            'effort': effort,
            'priority': priority,
            'description': smell.get('description', ''),
            'strategies': strategies,
            'affected_files': examples,
            'rationale': 'Dead code clutters the codebase and confuses developers.',
        }
    
    def _suggest_orphaned_file_refactor(self, smell: Dict, effort: str, priority: str) -> Dict:
        """Suggestion for Orphaned File smell."""
        
        strategies = [
            {
                'name': 'Remove Orphaned File',
                'description': "Delete isolated files that serve no purpose.",
                'steps': [
                    "Verify the file truly has no dependencies",
                    "Check git history to understand original purpose",
                    "Confirm no external references to this module",
                    "Delete the file",
                    "Run tests and linter",
                ],
                'benefit': "Reduces clutter, simplifies project structure",
            },
            {
                'name': 'Integrate Into Existing Module',
                'description': "Move orphaned content into a related, active module.",
                'steps': [
                    "Identify the most related module based on functionality",
                    "Move classes/functions from orphan to target module",
                    "Consolidate imports",
                    "Update any imports that reference the orphan",
                    "Delete the orphaned file",
                    "Run tests",
                ],
                'benefit': "Improves organization, reduces fragmentation",
            },
            {
                'name': 'Establish Connections',
                'description': "If the file serves a purpose, establish its role.",
                'steps': [
                    "Understand what the file does",
                    "Find or create entry point that uses it",
                    "Add it to package __init__.py if needed",
                    "Update documentation to explain its role",
                    "Add comments explaining why it exists",
                ],
                'benefit': "Makes code discoverable, improves navigation",
            },
        ]
        
        return {
            'smell_type': 'Orphaned File',
            'file': smell['file'],
            'effort': effort,
            'priority': priority,
            'description': smell.get('description', ''),
            'strategies': strategies,
            'affected_files': [smell['file']],
            'rationale': 'Orphaned files are confusing and hard to maintain.',
        }
    
    def _suggest_hotspot_refactor(self, smell: Dict, effort: str, priority: str) -> Dict:
        """Suggestion for Change Hotspot smell."""
        
        strategies = [
            {
                'name': 'Stabilize Through Refactoring',
                'description': "Reduce hotspot risk by addressing root causes.",
                'steps': [
                    "Apply 'High Complexity' strategies to reduce CC",
                    "Apply 'God File' strategies to reduce size",
                    "Apply 'Tight Coupling' strategies to reduce dependencies",
                    "Add comprehensive tests",
                    "Consider extracting volatile parts",
                ],
                'benefit': "Reduces change frequency and bug risk",
            },
            {
                'name': 'Isolate Volatile Code',
                'description': "Separate stable and changing code.",
                'steps': [
                    "Identify what changes frequently vs. what's stable",
                    "Extract volatile logic into separate module",
                    "Create stable interface that hides volatility",
                    "Concentrate testing on volatile parts",
                    "Update other modules to use stable interface",
                ],
                'benefit': "Limits blast radius of changes, easier to test",
            },
            {
                'name': 'Improve Test Coverage',
                'description': "Add tests to hotspot to reduce change risks.",
                'steps': [
                    "Measure current test coverage for this file",
                    "Identify hard-to-test areas",
                    "Refactor to enable testing (extract, inject dependencies)",
                    "Add unit tests for all paths",
                    "Add property-based tests for complex logic",
                ],
                'benefit': "Catches regressions early, enables confident refactoring",
            },
        ]
        
        return {
            'smell_type': 'Change Hotspot',
            'file': smell['file'],
            'effort': effort,
            'priority': priority,
            'description': smell.get('description', ''),
            'strategies': strategies,
            'affected_files': [smell['file']],
            'rationale': 'Hotspots accumulate bugs and become resistant to change.',
        }