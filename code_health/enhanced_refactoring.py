"""
Enhanced Refactoring Suggestions with Code Examples and Implementation Details.
Provides detailed, actionable refactoring recommendations with before/after examples.
Supports multiple languages: Python, Java, C/C++, JavaScript, TypeScript, Go, Rust.
"""

from typing import Dict, List, Optional


class EnhancedRefactoringAdvisor:
    """Generates comprehensive refactoring suggestions with implementation details."""
    
    def __init__(self, analyzer, smells: List[Dict], stats: Dict):
        """Initialize advisor with enhanced analyzer."""
        self.analyzer = analyzer
        self.smells = smells
        self.stats = stats
        self.language = self._detect_language()
    
    def _detect_language(self) -> str:
        """Detect the primary programming language from stats."""
        file_stats = self.stats.get('file_stats', {})
        if not file_stats:
            return 'python'  # Default
        
        # Count files by language
        language_count = {}
        for file_path, stats in file_stats.items():
            lang = stats.get('language', 'python')
            language_count[lang] = language_count.get(lang, 0) + 1
        
        # Return most common language
        return max(language_count.items(), key=lambda x: x[1])[0] if language_count else 'python'
    
    def generate_enhanced_suggestions(self) -> List[Dict]:
        """Generate detailed refactoring suggestions with examples."""
        suggestions = []
        
        for smell in self.smells:
            suggestion = self._create_detailed_suggestion(smell)
            if suggestion:
                suggestions.append(suggestion)
        
        # Add preventive suggestions
        suggestions.extend(self._generate_preventive_suggestions())
        
        # Sort by impact and effort
        suggestions.sort(key=lambda x: (
            -x['impact_score'],
            {'low': 0, 'medium': 1, 'high': 2}.get(x['effort'], 1),
        ))
        
        return suggestions
    
    def _create_detailed_suggestion(self, smell: Dict) -> Optional[Dict]:
        """Create detailed suggestion for a specific smell."""
        smell_type = smell.get('type', '')
        
        suggestions_map = {
            'God File': self._suggest_god_file_refactor,
            'Long Functions': self._suggest_long_function_refactor,
            'High Cyclomatic Complexity': self._suggest_complexity_refactor,
            'Tight Coupling': self._suggest_coupling_refactor,
            'Dead/Unused Code': self._suggest_dead_code_refactor,
            'Change Hotspot': self._suggest_hotspot_refactor,
        }
        
        handler = suggestions_map.get(smell_type)
        return handler(smell) if handler else None
    
    def _suggest_god_file_refactor(self, smell: Dict) -> Dict:
        """Detailed suggestion for God File refactoring."""
        metrics = smell.get('metrics', {})
        file_path = smell['file']
        
        return {
            'id': f"god_file_{file_path}",
            'smell_type': 'God File',
            'file': file_path,
            'severity': smell.get('severity', 'medium'),
            'effort': 'high',
            'impact_score': 85,
            'estimated_time': '4-8 hours',
            'description': smell.get('description', ''),
            'why_it_matters': [
                "Large files violate the Single Responsibility Principle",
                "Increases cognitive load for developers",
                "Makes testing and maintenance difficult",
                "Increases risk of bugs and side effects",
                "Reduces code reusability",
            ],
            'current_metrics': {
                'loc': metrics.get('loc', 0),
                'functions': metrics.get('functions', 0),
                'classes': metrics.get('classes', 0),
            },
            'strategies': [
                {
                    'name': 'Extract by Responsibility',
                    'description': 'Split into separate files based on functionality',
                    'steps': [
                        '1. Analyze the file and identify logical domains/responsibilities',
                        '2. Group related classes and functions by domain',
                        f'3. Create new files: {file_path.replace(".py", "")}_<domain>.py',
                        '4. Move grouped items to new files',
                        '5. Update imports in original file',
                        '6. Add __all__ export in __init__.py or refactored modules',
                        '7. Update any dependent imports across project',
                        '8. Run tests to ensure functionality preserved',
                    ],
                    'benefits': 'Improves modularity, testability, readability',
                    'code_example': self._generate_god_file_example(file_path),
                },
                {
                    'name': 'Extract by Layer',
                    'description': 'If file has mixed concerns (models, logic, utils), separate them',
                    'steps': [
                        '1. Identify different layers: models, logic, utilities, helpers',
                        '2. Create subdirectory: <filename>/',
                        '3. Create files: models.py, logic.py, utils.py',
                        '4. Move code to appropriate layer files',
                        '5. Create __init__.py to expose public API',
                        '6. Update imports',
                        '7. Delete original large file',
                        '8. Test all functionality',
                    ],
                    'benefits': 'Better separation of concerns, clearer structure',
                    'code_example': self._generate_layer_extraction_example(file_path),
                },
                {
                    'name': 'Convert to Package',
                    'description': 'Convert file into a package with modular subfiles',
                    'steps': [
                        f'1. Create directory: {file_path.replace(".py", "")}/',
                        '2. Create __init__.py (initial imports here)',
                        '3. Create sub-modules for each major component',
                        '4. Move related code to each sub-module',
                        '5. Update __init__.py to expose public interface',
                        '6. Update project imports to use new package',
                        '7. Remove original file if no longer needed',
                        '8. Run comprehensive tests',
                    ],
                    'benefits': 'Enables parallel development, better organization',
                    'code_example': self._generate_package_conversion_example(file_path),
                },
            ],
            'before_after': {
                'before': f'''# {file_path} - 2000+ LOC
class UserManager: ...
class AuthManager: ...
class MailManager: ...
class NotificationHandler: ...
# 50+ functions
# Multiple responsibilities''',
                'after': f'''# {file_path}/ (now a package)
from .user_manager import UserManager
from .auth_manager import AuthManager
from .mail_manager import MailManager
from .notification import NotificationHandler

__all__ = ['UserManager', 'AuthManager', 'MailManager', 'NotificationHandler']''',
            },
            'next_steps': [
                'Create refactoring task with acceptance criteria',
                'Write tests before refactoring (golden master test)',
                'Refactor incrementally, testing after each change',
                'Update documentation and architecture diagram',
                'Review import paths and update them globally',
            ],
        }
    
    def _suggest_long_function_refactor(self, smell: Dict) -> Dict:
        """Detailed suggestion for Long Function refactoring."""
        metrics = smell.get('metrics', {})
        file_path = smell['file']
        avg_length = metrics.get('average_function_length', 50)
        
        return {
            'id': f"long_func_{file_path}",
            'smell_type': 'Long Functions',
            'file': file_path,
            'severity': 'high' if avg_length > 100 else 'medium',
            'effort': 'medium',
            'impact_score': 75,
            'estimated_time': '2-4 hours',
            'description': smell.get('description', ''),
            'why_it_matters': [
                f"Average function length is {int(avg_length)} lines (threshold: 30 lines)",
                "Long functions are hard to understand and debug",
                "Functions doing multiple things violate SRP",
                "Difficult to unit test effectively",
                "Increases cognitive complexity",
            ],
            'current_metrics': {
                'average_length': avg_length,
                'num_functions': metrics.get('num_functions', 0),
                'threshold': 30,
            },
            'strategies': [
                {
                    'name': 'Extract Helper Methods',
                    'description': 'Break long function into smaller, focused methods',
                    'steps': [
                        '1. Read through the function and identify logical blocks',
                        '2. Look for: loops, conditionals, repeated code',
                        '3. Extract each block into a helper method with descriptive name',
                        '4. Call helpers from main function in sequence',
                        '5. Add docstrings to helpers explaining their purpose',
                        '6. Add type hints for parameters and return values',
                        '7. Write unit tests for each helper',
                        '8. Consider making helpers private (prefix with _)',
                    ],
                    'benefits': 'Better readability, easier testing, improves reusability',
                    'code_example': self._generate_long_function_example(),
                },
                {
                    'name': 'Use Guard Clauses',
                    'description': 'Replace nested conditionals with early returns',
                    'steps': [
                        '1. Identify nested if-else blocks',
                        '2. Replace with guard clauses (early returns)',
                        '3. Reduces indentation level',
                        '4. Makes control flow clearer',
                        '5. Each guard clause handles invalid case and returns',
                        '6. Main logic follows at the end',
                    ],
                    'benefits': 'Better readability, fewer nesting levels',
                    'code_example': self._generate_guard_clause_example(),
                },
                {
                    'name': 'Extract to Separate Functions',
                    'description': 'Move independent logic to standalone functions',
                    'steps': [
                        '1. Identify sub-tasks or operations',
                        '2. Create separate functions for each sub-task',
                        '3. Group related parameters (consider Config objects)',
                        '4. Make main function a coordinator calling helpers',
                        '5. Add comprehensive docstrings',
                        '6. Use type hints',
                        '7. Test each function independently',
                    ],
                    'benefits': 'Enables reuse, better testability, clearer intent',
                    'code_example': self._generate_extraction_example(),
                },
            ],
            'before_after': {
                'before': '''def process_user_data(user_id, action):
    # 80+ lines
    user = get_user(user_id)
    if user is None:
        # Handle error...
    if user.status == 'active':
        # 20 lines of validation
        # 20 lines of processing
        # 15 lines of cleanup
        # 15 lines of logging...''',
                'after': '''def process_user_data(user_id, action):
    user = get_user(user_id)
    validate_user(user)
    execute_action(user, action)
    log_completion(user_id, action)

def validate_user(user): ...
def execute_action(user, action): ...
def log_completion(user_id, action): ...''',
            },
            'next_steps': [
                'Start with helper methods extraction',
                'Add unit tests for each extracted method',
                'Use IDE refactoring tools (Extract Method)',
                'Profile to ensure no performance regression',
                'Update documentation with new structure',
            ],
        }
    
    def _suggest_complexity_refactor(self, smell: Dict) -> Dict:
        """Detailed suggestion for Complexity reduction."""
        metrics = smell.get('metrics', {})
        file_path = smell['file']
        complexity = metrics.get('cyclomatic_complexity', 10)
        
        return {
            'id': f"complexity_{file_path}",
            'smell_type': 'High Cyclomatic Complexity',
            'file': file_path,
            'severity': 'high',
            'effort': 'medium',
            'impact_score': 80,
            'estimated_time': '2-3 hours',
            'description': smell.get('description', ''),
            'why_it_matters': [
                f"Current complexity: {complexity} (threshold: 7)",
                f"Requires {complexity} test cases to achieve full coverage",
                "Each conditional path adds exponential testing overhead",
                "High complexity correlates with more bugs",
                "Difficult to maintain and reason about",
            ],
            'current_metrics': {
                'cyclomatic_complexity': complexity,
                'test_paths_required': complexity,
                'threshold': 7,
            },
            'strategies': [
                {
                    'name': 'Extract Complex Conditions',
                    'description': 'Break complex boolean expressions into named methods',
                    'steps': [
                        '1. Identify complex if conditions',
                        '2. Extract each condition to a method with clear name',
                        '3. Replace inline condition with method call',
                        '4. This names the condition intent (self-documenting)',
                        '5. Easier to test and modify',
                    ],
                    'benefits': 'Improves readability and testability',
                    'code_example': self._generate_condition_extraction(),
                },
                {
                    'name': 'Use Polymorphism',
                    'description': 'Replace switch/case or type checks with polymorphism',
                    'steps': [
                        '1. Identify switch/case statements or type checking',
                        '2. Create hierarchy: base class + subclasses',
                        '3. Move logic to appropriate subclass',
                        '4. Replace switch with polymorphic call',
                        '5. Use strategy or visitor pattern if needed',
                    ],
                    'benefits': 'Enables easy extension, more OOP-like',
                    'code_example': self._generate_polymorphism_example(),
                },
                {
                    'name': 'Extract to State Machine',
                    'description': 'For status-dependent logic, use state pattern',
                    'steps': [
                        '1. Map out all states and transitions',
                        '2. Create State base class or interface',
                        '3. Create concrete state classes',
                        '4. Move status-specific logic to states',
                        '5. Original class delegates to current state',
                    ],
                    'benefits': 'Clear state management, extensible',
                    'code_example': self._generate_state_pattern_example(),
                },
            ],
            'before_after': {
                'before': '''def calculate_price(item, qty, customer):
    price = item.base_price * qty
    if customer.type == 'premium' and qty > 10:
        price *= 0.9
    elif customer.type == 'regular' and qty > 20:
        price *= 0.95
    elif customer.is_government:
        price *= 0.85
    # More complex conditions...''',
                'after': '''def calculate_price(item, qty, customer):
    price = item.base_price * qty
    discount = customer.get_discount(qty)
    return price * (1 - discount)

class Customer:
    def get_discount(self, qty):
        # Overridden by subclasses PremiumCustomer, GovernmentCustomer''',
            },
            'test_coverage': f'Aim for {min(complexity, 10)} test cases minimum',
            'next_steps': [
                'Measure current test coverage',
                'Write tests for each execution path',
                'Refactor to reduce paths',
                'Verify coverage after refactoring',
            ],
        }
    
    def _suggest_coupling_refactor(self, smell: Dict) -> Dict:
        """Detailed suggestion for Coupling reduction."""
        return {
            'id': f"coupling_{smell['file']}",
            'smell_type': 'Tight Coupling',
            'file': smell['file'],
            'severity': 'medium',
            'effort': 'high',
            'impact_score': 70,
            'estimated_time': '4-6 hours',
            'description': smell.get('description', ''),
            'why_it_matters': [
                "Tight coupling makes changes risky and time-consuming",
                "Breaking one file can break many others",
                "Difficult to test in isolation",
                "Reduces code reusability",
            ],
            'strategies': [
                {
                    'name': 'Extract Dependencies to Interface',
                    'description': 'Use dependency injection and interfaces',
                    'steps': [
                        '1. Identify hard dependencies (new, direct calls)',
                        '2. Create interface/protocol for dependency',
                        '3. Pass dependency to constructor (injection)',
                        '4. Use interface, not concrete class',
                        '5. Allows mocking in tests',
                    ],
                    'benefits': 'Loosely coupled, easier to test and extend',
                },
                {
                    'name': 'Create Facade',
                    'description': 'Use facade to simplify dependency across modules',
                    'steps': [
                        '1. Create facade class wrapping complex dependencies',
                        '2. Expose simplified interface',
                        '3. Module depends on facade, not individual classes',
                        '4. Reduces number of dependencies',
                    ],
                    'benefits': 'Simplifies interactions, centralizes coupling',
                },
            ],
        }
    
    def _suggest_dead_code_refactor(self, smell: Dict) -> Dict:
        """Detailed suggestion for Dead Code removal."""
        return {
            'id': f"dead_code_{smell['file']}",
            'smell_type': 'Dead/Unused Code',
            'file': smell['file'],
            'severity': 'low',
            'effort': 'low',
            'impact_score': 30,
            'estimated_time': '30 minutes',
            'description': smell.get('description', ''),
            'why_it_matters': [
                "Dead code confuses developers",
                "Increases maintenance burden",
                "Takes up real estate in files",
                "May be outdated or incorrect",
            ],
            'strategies': [
                {
                    'name': 'Remove Unused Code',
                    'description': 'Use IDE to find and remove unused symbols',
                    'steps': [
                        '1. Use IDE "Find Unused" feature',
                        '2. Review each unused symbol',
                        '3. If truly unused, delete it',
                        '4. If might be needed, move to archive branch',
                        '5. Commit with clear message: "Remove unused XYZ"',
                    ],
                    'benefits': 'Cleaner codebase, easier to understand',
                },
            ],
        }
    
    def _suggest_hotspot_refactor(self, smell: Dict) -> Dict:
        """Detailed suggestion for Hotspot refactoring."""
        return {
            'id': f"hotspot_{smell['file']}",
            'smell_type': 'Change Hotspot',
            'file': smell['file'],
            'severity': 'high',
            'effort': 'high',
            'impact_score': 90,
            'estimated_time': '6-8 hours',
            'description': smell.get('description', ''),
            'why_it_matters': [
                "Frequently modified files are prone to bugs",
                "Each change risks introducing new issues",
                "High churn indicates poor design",
                "Needs stabilization and refactoring",
            ],
            'strategies': [
                {
                    'name': 'Stabilize Through Refactoring',
                    'description': 'Extract volatile parts to reduce need for changes',
                    'steps': [
                        '1. Analyze recent changes (git log)',
                        '2. Identify what changes most frequently',
                        '3. Create stable core and volatile wrapper',
                        '4. Isolate change points',
                        '5. Add comprehensive tests around changes',
                    ],
                    'benefits': 'Reduces churn, improves stability',
                },
                {
                    'name': 'Extract to Plugin System',
                    'description': 'If changes are due to new features, use plugins',
                    'steps': [
                        '1. Define core, unchanging API',
                        '2. Move changing logic to plugin architecture',
                        '3. New features = new plugins, not core changes',
                        '4. Reduces hotspot file churn',
                    ],
                    'benefits': 'Extensible without modifying core',
                },
            ],
        }
    
    def _generate_preventive_suggestions(self) -> List[Dict]:
        """Generate suggestions to prevent future issues."""
        return [
            {
                'id': 'preventive_architecture',
                'smell_type': 'Preventive - Architecture',
                'severity': 'medium',
                'effort': 'medium',
                'impact_score': 60,
                'description': 'Establish architectural guidelines to prevent anti-patterns',
                'strategies': [
                    {
                        'name': 'Define Coding Standards',
                        'steps': [
                            '1. Document max function length (30 lines recommended)',
                            '2. Document max file size (250 lines recommended)',
                            '3. Document max cyclomatic complexity (5-7 recommended)',
                            '4. Enforce via linters (pylint, flake8, black)',
                            '5. Add pre-commit hooks to check standards',
                        ],
                    },
                    {
                        'name': 'Code Review Checklist',
                        'steps': [
                            '• Does function/file exceed size limits?',
                            '• Are responsibilities mixed?',
                            '• Is there sufficient documentation?',
                            '• Does code follow DRY principle?',
                            '• Are edge cases handled?',
                        ],
                    },
                ],
            },
            {
                'id': 'preventive_testing',
                'smell_type': 'Preventive - Testing',
                'severity': 'medium',
                'effort': 'medium',
                'impact_score': 65,
                'description': 'Improve test coverage to catch regressions early',
                'strategies': [
                    {
                        'name': 'Unit Test Coverage',
                        'steps': [
                            '1. Aim for >80% line coverage',
                            '2. Focus on critical paths and edge cases',
                            '3. Test each function independently',
                            '4. Use mocks for external dependencies',
                            '5. Run tests in CI/CD pipeline',
                        ],
                    },
                ],
            },
        ]
    
    # Helper methods for code examples
    
    def _generate_god_file_example(self, file_path: str) -> str:
        """Generate example for god file refactoring (language-aware)."""
        if self.language in ('cpp', 'c'):
            return '''// Before: huge models.h/models.cpp (2000+ LOC)
// After: Refactored as modular headers/sources

models/
├── CMakeLists.txt
├── user.h / user.cpp          # User, UserProfile classes
├── auth.h / auth.cpp          # Authentication logic
├── permissions.h / permissions.cpp  # Permission checking
└── validators.h / validators.cpp    # Data validation'''
        elif self.language == 'java':
            return '''// Before: huge Models.java (2000+ LOC)
// After: Refactored as package/
            
com/app/models/
├── User.java
├── UserProfile.java
├── Authentication.java
├── Permission.java
└── DataValidator.java'''
        elif self.language in ('javascript', 'typescript'):
            return '''// Before: huge models.js/ts (2000+ LOC)
// After: Refactored as modular exports

models/
├── index.ts          # Exports public API
├── user.ts           # User, UserProfile classes
├── auth.ts           # Authentication logic
├── permissions.ts    # Permission checking
└── validators.ts     # Data validation'''
        else:  # Python default
            return '''# Before: huge models.py (2000+ LOC)
# After: Refactored as package/

models/
├── __init__.py      # Exports public API
├── user.py          # User, UserProfile classes
├── auth.py          # Authentication logic
├── permissions.py   # Permission checking
└── validators.py    # Data validation'''
    
    def _generate_layer_extraction_example(self, file_path: str) -> str:
        """Generate example for layer extraction (language-aware)."""
        if self.language in ('cpp', 'c'):
            return '''// Before: services.h/cpp has everything mixed
// After: Separated by layers

services/
├── CMakeLists.txt
├── models.h/cpp          # Data models
├── business_logic.h/cpp  # Business logic
├── utils.h/cpp           # Utilities
└── exceptions.h/cpp      # Custom exceptions'''
        elif self.language == 'java':
            return '''// Before: Services.java has everything mixed
// After: Separated by layers

com/app/services/
├── model/
│   └── UserModel.java
├── logic/
│   └── UserBusinessLogic.java
├── utils/
│   └── UserUtils.java
└── exception/
    └── UserException.java'''
        elif self.language in ('javascript', 'typescript'):
            return '''// Before: services.ts has everything mixed
// After: Separated by layers

services/
├── models.ts         # Data models
├── logic.ts          # Business logic
├── utils.ts          # Utilities
└── exceptions.ts     # Custom exceptions'''
        else:  # Python default
            return '''# Before: services.py has everything mixed
# After: Separated by layers

services/
├── __init__.py
├── models.py        # Data models
├── logic.py         # Business logic
├── utils.py         # Utilities
└── exceptions.py    # Custom exceptions'''
    
    def _generate_package_conversion_example(self, file_path: str) -> str:
        """Generate example for package conversion (language-aware)."""
        if self.language in ('cpp', 'c'):
            return '''// AFTER: Modular includes
#include "payment/processor.h"
#include "payment/validators.h"
#include "payment/handlers.h"

// vs BEFORE: Everything in one huge payment.h'''
        elif self.language == 'java':
            return '''// AFTER: Modular imports
import com.payment.processor.PaymentProcessor;
import com.payment.validators.PaymentValidator;
import com.payment.handlers.ErrorHandler;

// vs BEFORE: Everything in one huge Payment.java'''
        elif self.language in ('javascript', 'typescript'):
            return '''// AFTER: Modular imports
import { PaymentProcessor } from './payment/processor';
import { PaymentValidator } from './payment/validators';
import { ErrorHandler } from './payment/handlers';

// vs BEFORE: Everything in payment.ts'''
        else:  # Python default
            return '''from payment.processor import PaymentProcessor
from payment.validators import PaymentValidator
from payment.handlers import ErrorHandler

# vs before:
from payment import PaymentProcessor, PaymentValidator, ErrorHandler'''
    
    def _generate_long_function_example(self) -> str:
        """Generate example for long function extraction (language-aware)."""
        if self.language in ('cpp', 'c'):
            return '''// BEFORE: 75-line function
void processOrder(Order& order) {
    // Validation - 15 lines
    if (order.items.empty()) {
        throw std::invalid_argument("Empty order");
    }
    // ... more validation
    
    // Processing - 30 lines
    double total = 0;
    for (auto& item : order.items) total += item.price;
    // ... more processing
    
    // Save - 10 lines
    db.save(order);
    
    // Notification - 20 lines
    sendEmail(...);
}

// AFTER: Extracted helpers
void processOrder(Order& order) {
    validateOrder(order);
    calculateTotal(order);
    saveOrder(order);
    notifyCustomer(order);
}

void validateOrder(Order& order) { ... }
void calculateTotal(Order& order) { ... }
void saveOrder(Order& order) { ... }
void notifyCustomer(Order& order) { ... }'''
        elif self.language == 'java':
            return '''// BEFORE: 75-line function
public void processOrder(Order order) {
    // Validation - 15 lines
    if (order.getItems().isEmpty()) {
        throw new IllegalArgumentException("Empty order");
    }
    // ... more validation
    
    // Processing - 30 lines
    double total = order.getItems().stream()
        .mapToDouble(Item::getPrice).sum();
    // ... more processing
    
    // Save - 10 lines
    db.save(order);
    
    // Notification - 20 lines
    sendEmail(...);
}

// AFTER: Extracted helpers
public void processOrder(Order order) {
    validateOrder(order);
    calculateTotal(order);
    saveOrder(order);
    notifyCustomer(order);
}

private void validateOrder(Order order) { ... }
private double calculateTotal(Order order) { ... }
private void saveOrder(Order order) { ... }
private void notifyCustomer(Order order) { ... }'''
        elif self.language in ('javascript', 'typescript'):
            return '''// BEFORE: 75-line function
function processOrder(order: Order) {
    // Validation - 15 lines
    if (!order.items || order.items.length === 0) {
        throw new Error("Empty order");
    }
    // ... more validation
    
    // Processing - 30 lines
    const total = order.items.reduce((sum, item) => sum + item.price, 0);
    // ... more processing
    
    // Save - 10 lines
    db.save(order);
    
    // Notification - 20 lines
    sendEmail(...);
}

// AFTER: Extracted helpers
function processOrder(order: Order) {
    validateOrder(order);
    calculateTotal(order);
    saveOrder(order);
    notifyCustomer(order);
}

function validateOrder(order: Order) { ... }
function calculateTotal(order: Order) { ... }
function saveOrder(order: Order) { ... }
function notifyCustomer(order: Order) { ... }'''
        else:  # Python default
            return '''# BEFORE: 75-line function
def process_order(order):
    # Validation - 15 lines
    if not order.items:
        raise ValueError("Empty order")
    # ... more validation
    
    # Processing - 30 lines
    total = sum(item.price for item in order.items)
    # ... more processing
    
    # Save - 10 lines
    db.save(order)
    
    # Notification - 20 lines
    send_email(...)

# AFTER: Extracted helpers
def process_order(order):
    validate_order(order)
    calculate_total(order)
    save_order(order)
    notify_customer(order)

def validate_order(order): ...
def calculate_total(order): ...
def save_order(order): ...
def notify_customer(order): ...'''
    
    def _generate_guard_clause_example(self) -> str:
        """Generate example for guard clauses (language-aware)."""
        if self.language in ('cpp', 'c'):
            return '''// BEFORE: Nested conditionals
double calculateDiscount(Customer* customer, double total) {
    if (customer) {
        if (customer->isPremium()) {
            if (total > 1000) {
                return 0.2;
            } else {
                return 0.1;
            }
        } else {
            return 0.05;
        }
    } else {
        return 0;
    }
}

// AFTER: Guard clauses
double calculateDiscount(Customer* customer, double total) {
    if (!customer) return 0;
    if (!customer->isPremium()) return 0.05;
    return total > 1000 ? 0.2 : 0.1;
}'''
        elif self.language == 'java':
            return '''// BEFORE: Nested conditionals
public double calculateDiscount(Customer customer, double total) {
    if (customer != null) {
        if (customer.isPremium()) {
            if (total > 1000) {
                return 0.2;
            } else {
                return 0.1;
            }
        } else {
            return 0.05;
        }
    } else {
        return 0;
    }
}

// AFTER: Guard clauses
public double calculateDiscount(Customer customer, double total) {
    if (customer == null) return 0;
    if (!customer.isPremium()) return 0.05;
    return total > 1000 ? 0.2 : 0.1;
}'''
        elif self.language in ('javascript', 'typescript'):
            return '''// BEFORE: Nested conditionals
function calculateDiscount(customer: Customer | null, total: number): number {
    if (customer) {
        if (customer.isPremium()) {
            if (total > 1000) {
                return 0.2;
            } else {
                return 0.1;
            }
        } else {
            return 0.05;
        }
    } else {
        return 0;
    }
}

// AFTER: Guard clauses
function calculateDiscount(customer: Customer | null, total: number): number {
    if (!customer) return 0;
    if (!customer.isPremium()) return 0.05;
    return total > 1000 ? 0.2 : 0.1;
}'''
        else:  # Python default
            return '''# BEFORE: Nested conditionals
def calculate_discount(customer, total):
    if customer:
        if customer.is_premium:
            if total > 1000:
                return 0.2
            else:
                return 0.1
        else:
            return 0.05
    else:
        return 0

# AFTER: Guard clauses
def calculate_discount(customer, total):
    if not customer:
        return 0
    if not customer.is_premium:
        return 0.05
    return 0.2 if total > 1000 else 0.1'''
    
    def _generate_extraction_example(self) -> str:
        """Generate example for function extraction."""
        return '''# BEFORE: Mixed concerns
def import_users(file_path):
    data = read_file(file_path)          # 10 lines
    users = parse_csv(data)              # 8 lines
    validated = validate_all(users)      # 12 lines
    for user in validated:               # 15 lines
        save_user(user)
    generate_report(len(validated))      # 6 lines

# AFTER: Separated concerns
def import_users(file_path):
    data = read_file(file_path)
    users = parse_csv(data)
    validated = validate_all(users)
    save_users(validated)
    generate_report(len(validated))

def save_users(users):
    for user in users:
        save_user(user)'''
    
    def _generate_condition_extraction(self) -> str:
        """Generate example for condition extraction."""
        return '''# BEFORE: Complex condition
if user.age > 18 and user.verified and user.country in ALLOWED_COUNTRIES and user.balance > 100:
    process_payment(user)

# AFTER: Named conditions
if is_eligible_for_payment(user):
    process_payment(user)

def is_eligible_for_payment(user):
    return (
        is_adult(user) and
        is_verified(user) and
        is_in_allowed_region(user) and
        has_sufficient_balance(user)
    )'''
    
    def _generate_polymorphism_example(self) -> str:
        """Generate example for polymorphism."""
        return '''# BEFORE: Type checking
if customer_type == "premium":
    discount = 0.2
elif customer_type == "regular":
    discount = 0.1
else:
    discount = 0

# AFTER: Polymorphism
class Customer:
    def get_discount(self): pass

class PremiumCustomer(Customer):
    def get_discount(self): return 0.2

class RegularCustomer(Customer):
    def get_discount(self): return 0.1'''
    
    def _generate_state_pattern_example(self) -> str:
        """Generate example for state pattern."""
        return '''# BEFORE: Multiple status checks
if order.status == "pending":
    order.cancel()
elif order.status == "shipped":
    send_cancel_message()
    order.status = "cancelled"

# AFTER: State pattern
class OrderState:
    def cancel(self): pass

class PendingOrder(OrderState):
    def cancel(self): order.status = "cancelled"

class ShippedOrder(OrderState):
    def cancel(self): send_cancel_message()'''
