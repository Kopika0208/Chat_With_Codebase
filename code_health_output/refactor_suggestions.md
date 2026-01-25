# Refactoring Suggestions

Generated: 2026-01-25 13:15:16

---

## Summary

Total suggestions: 29

- High Priority: 26
- Medium Priority: 2
- Low Priority: 1

---

## #1 Long Functions

**File:** `app.py`

**Priority:** HIGH | **Effort:** MEDIUM

### Problem

Functions are too long (average: 354 lines). Contains 3 functions.

### Rationale

Long functions are hard to understand, test, and maintain.

### Suggested Strategies

#### 1. Extract Helper Methods

Break down large functions (avg 354 lines) into smaller, focused helper methods.

**Steps:**

- Identify logical blocks or sub-tasks in the function
- Extract each block into a separate method with a descriptive name
- Update the main function to call helpers in sequence
- Add docstrings explaining what each helper does
- Test extracted functions independently

**Benefit:** Improves readability, testability, and reusability

#### 2. Extract to Separate Functions

Move related logic into standalone functions for clarity.

**Steps:**

- Identify concepts or operations that can stand alone
- Create new functions with single purposes
- Reduce parameter count by grouping related params (e.g., Config objects)
- Add type hints and docstrings
- Consider making helper functions private (prefix with _)

**Benefit:** Enables reuse, improves testability, reduces duplication

#### 3. Use Guard Clauses

Replace nested if statements with early returns.

**Steps:**

- Identify deeply nested conditionals
- Move validation/guard logic to the start of function
- Use early returns for invalid cases
- Reduce nesting depth to max 2 levels
- Extract remaining logic if still too complex

**Benefit:** Reduces cognitive load, improves code flow clarity

### Affected Files

- `app.py`

---

## #2 Long Functions

**File:** `graph.py`

**Priority:** HIGH | **Effort:** MEDIUM

### Problem

Functions are too long (average: 53 lines). Contains 10 functions.

### Rationale

Long functions are hard to understand, test, and maintain.

### Suggested Strategies

#### 1. Extract Helper Methods

Break down large functions (avg 53 lines) into smaller, focused helper methods.

**Steps:**

- Identify logical blocks or sub-tasks in the function
- Extract each block into a separate method with a descriptive name
- Update the main function to call helpers in sequence
- Add docstrings explaining what each helper does
- Test extracted functions independently

**Benefit:** Improves readability, testability, and reusability

#### 2. Extract to Separate Functions

Move related logic into standalone functions for clarity.

**Steps:**

- Identify concepts or operations that can stand alone
- Create new functions with single purposes
- Reduce parameter count by grouping related params (e.g., Config objects)
- Add type hints and docstrings
- Consider making helper functions private (prefix with _)

**Benefit:** Enables reuse, improves testability, reduces duplication

#### 3. Use Guard Clauses

Replace nested if statements with early returns.

**Steps:**

- Identify deeply nested conditionals
- Move validation/guard logic to the start of function
- Use early returns for invalid cases
- Reduce nesting depth to max 2 levels
- Extract remaining logic if still too complex

**Benefit:** Reduces cognitive load, improves code flow clarity

### Affected Files

- `graph.py`

---

## #3 Long Functions

**File:** `graph_rag.py`

**Priority:** HIGH | **Effort:** MEDIUM

### Problem

Functions are too long (average: 143 lines). Contains 9 functions.

### Rationale

Long functions are hard to understand, test, and maintain.

### Suggested Strategies

#### 1. Extract Helper Methods

Break down large functions (avg 143 lines) into smaller, focused helper methods.

**Steps:**

- Identify logical blocks or sub-tasks in the function
- Extract each block into a separate method with a descriptive name
- Update the main function to call helpers in sequence
- Add docstrings explaining what each helper does
- Test extracted functions independently

**Benefit:** Improves readability, testability, and reusability

#### 2. Extract to Separate Functions

Move related logic into standalone functions for clarity.

**Steps:**

- Identify concepts or operations that can stand alone
- Create new functions with single purposes
- Reduce parameter count by grouping related params (e.g., Config objects)
- Add type hints and docstrings
- Consider making helper functions private (prefix with _)

**Benefit:** Enables reuse, improves testability, reduces duplication

#### 3. Use Guard Clauses

Replace nested if statements with early returns.

**Steps:**

- Identify deeply nested conditionals
- Move validation/guard logic to the start of function
- Use early returns for invalid cases
- Reduce nesting depth to max 2 levels
- Extract remaining logic if still too complex

**Benefit:** Reduces cognitive load, improves code flow clarity

### Affected Files

- `graph_rag.py`

---

## #4 Long Functions

**File:** `graph_traversal.py`

**Priority:** HIGH | **Effort:** MEDIUM

### Problem

Functions are too long (average: 265 lines). Contains 15 functions.

### Rationale

Long functions are hard to understand, test, and maintain.

### Suggested Strategies

#### 1. Extract Helper Methods

Break down large functions (avg 265 lines) into smaller, focused helper methods.

**Steps:**

- Identify logical blocks or sub-tasks in the function
- Extract each block into a separate method with a descriptive name
- Update the main function to call helpers in sequence
- Add docstrings explaining what each helper does
- Test extracted functions independently

**Benefit:** Improves readability, testability, and reusability

#### 2. Extract to Separate Functions

Move related logic into standalone functions for clarity.

**Steps:**

- Identify concepts or operations that can stand alone
- Create new functions with single purposes
- Reduce parameter count by grouping related params (e.g., Config objects)
- Add type hints and docstrings
- Consider making helper functions private (prefix with _)

**Benefit:** Enables reuse, improves testability, reduces duplication

#### 3. Use Guard Clauses

Replace nested if statements with early returns.

**Steps:**

- Identify deeply nested conditionals
- Move validation/guard logic to the start of function
- Use early returns for invalid cases
- Reduce nesting depth to max 2 levels
- Extract remaining logic if still too complex

**Benefit:** Reduces cognitive load, improves code flow clarity

### Affected Files

- `graph_traversal.py`

---

## #5 Long Functions

**File:** `reasoning.py`

**Priority:** HIGH | **Effort:** MEDIUM

### Problem

Functions are too long (average: 153 lines). Contains 8 functions.

### Rationale

Long functions are hard to understand, test, and maintain.

### Suggested Strategies

#### 1. Extract Helper Methods

Break down large functions (avg 153 lines) into smaller, focused helper methods.

**Steps:**

- Identify logical blocks or sub-tasks in the function
- Extract each block into a separate method with a descriptive name
- Update the main function to call helpers in sequence
- Add docstrings explaining what each helper does
- Test extracted functions independently

**Benefit:** Improves readability, testability, and reusability

#### 2. Extract to Separate Functions

Move related logic into standalone functions for clarity.

**Steps:**

- Identify concepts or operations that can stand alone
- Create new functions with single purposes
- Reduce parameter count by grouping related params (e.g., Config objects)
- Add type hints and docstrings
- Consider making helper functions private (prefix with _)

**Benefit:** Enables reuse, improves testability, reduces duplication

#### 3. Use Guard Clauses

Replace nested if statements with early returns.

**Steps:**

- Identify deeply nested conditionals
- Move validation/guard logic to the start of function
- Use early returns for invalid cases
- Reduce nesting depth to max 2 levels
- Extract remaining logic if still too complex

**Benefit:** Reduces cognitive load, improves code flow clarity

### Affected Files

- `reasoning.py`

---

## #6 Long Functions

**File:** `symbol_driven_ranking.py`

**Priority:** HIGH | **Effort:** MEDIUM

### Problem

Functions are too long (average: 78 lines). Contains 27 functions.

### Rationale

Long functions are hard to understand, test, and maintain.

### Suggested Strategies

#### 1. Extract Helper Methods

Break down large functions (avg 78 lines) into smaller, focused helper methods.

**Steps:**

- Identify logical blocks or sub-tasks in the function
- Extract each block into a separate method with a descriptive name
- Update the main function to call helpers in sequence
- Add docstrings explaining what each helper does
- Test extracted functions independently

**Benefit:** Improves readability, testability, and reusability

#### 2. Extract to Separate Functions

Move related logic into standalone functions for clarity.

**Steps:**

- Identify concepts or operations that can stand alone
- Create new functions with single purposes
- Reduce parameter count by grouping related params (e.g., Config objects)
- Add type hints and docstrings
- Consider making helper functions private (prefix with _)

**Benefit:** Enables reuse, improves testability, reduces duplication

#### 3. Use Guard Clauses

Replace nested if statements with early returns.

**Steps:**

- Identify deeply nested conditionals
- Move validation/guard logic to the start of function
- Use early returns for invalid cases
- Reduce nesting depth to max 2 levels
- Extract remaining logic if still too complex

**Benefit:** Reduces cognitive load, improves code flow clarity

### Affected Files

- `symbol_driven_ranking.py`

---

## #7 Long Functions

**File:** `unified_retrieval.py`

**Priority:** HIGH | **Effort:** MEDIUM

### Problem

Functions are too long (average: 111 lines). Contains 37 functions.

### Rationale

Long functions are hard to understand, test, and maintain.

### Suggested Strategies

#### 1. Extract Helper Methods

Break down large functions (avg 111 lines) into smaller, focused helper methods.

**Steps:**

- Identify logical blocks or sub-tasks in the function
- Extract each block into a separate method with a descriptive name
- Update the main function to call helpers in sequence
- Add docstrings explaining what each helper does
- Test extracted functions independently

**Benefit:** Improves readability, testability, and reusability

#### 2. Extract to Separate Functions

Move related logic into standalone functions for clarity.

**Steps:**

- Identify concepts or operations that can stand alone
- Create new functions with single purposes
- Reduce parameter count by grouping related params (e.g., Config objects)
- Add type hints and docstrings
- Consider making helper functions private (prefix with _)

**Benefit:** Enables reuse, improves testability, reduces duplication

#### 3. Use Guard Clauses

Replace nested if statements with early returns.

**Steps:**

- Identify deeply nested conditionals
- Move validation/guard logic to the start of function
- Use early returns for invalid cases
- Reduce nesting depth to max 2 levels
- Extract remaining logic if still too complex

**Benefit:** Reduces cognitive load, improves code flow clarity

### Affected Files

- `unified_retrieval.py`

---

## #8 Long Functions

**File:** `onboarding\analyzer.py`

**Priority:** HIGH | **Effort:** MEDIUM

### Problem

Functions are too long (average: 688 lines). Contains 14 functions.

### Rationale

Long functions are hard to understand, test, and maintain.

### Suggested Strategies

#### 1. Extract Helper Methods

Break down large functions (avg 688 lines) into smaller, focused helper methods.

**Steps:**

- Identify logical blocks or sub-tasks in the function
- Extract each block into a separate method with a descriptive name
- Update the main function to call helpers in sequence
- Add docstrings explaining what each helper does
- Test extracted functions independently

**Benefit:** Improves readability, testability, and reusability

#### 2. Extract to Separate Functions

Move related logic into standalone functions for clarity.

**Steps:**

- Identify concepts or operations that can stand alone
- Create new functions with single purposes
- Reduce parameter count by grouping related params (e.g., Config objects)
- Add type hints and docstrings
- Consider making helper functions private (prefix with _)

**Benefit:** Enables reuse, improves testability, reduces duplication

#### 3. Use Guard Clauses

Replace nested if statements with early returns.

**Steps:**

- Identify deeply nested conditionals
- Move validation/guard logic to the start of function
- Use early returns for invalid cases
- Reduce nesting depth to max 2 levels
- Extract remaining logic if still too complex

**Benefit:** Reduces cognitive load, improves code flow clarity

### Affected Files

- `onboarding\analyzer.py`

---

## #9 High Cyclomatic Complexity

**File:** `app.py`

**Priority:** HIGH | **Effort:** MEDIUM

### Problem

High cyclomatic complexity: 145. This file has 144 decision points (if/for/while/except etc.).

### Rationale

Complexity of 145 means exponential test combinations. Each reduction matters.

### Suggested Strategies

#### 1. Extract Methods

High complexity (CC=145) indicates too many decision paths. Extract conditions into helper methods.

**Steps:**

- Identify separate conditional branches
- Extract each branch/condition into a descriptive method
- Name methods after their purpose (e.g., is_valid_user())
- Replace complex conditions with method calls
- Return early when conditions fail

**Benefit:** Reduces complexity, improves readability, easier to test each path

#### 2. Use Polymorphism

Replace complex if/elif chains with polymorphic dispatch.

**Steps:**

- Identify if/elif chains checking types or categories
- Create base class or interface
- Create subclasses for each condition
- Implement behavior in each subclass
- Replace switch logic with polymorphic calls

**Benefit:** Eliminates switch logic, enables extensibility without modification

#### 3. Simplify Logic

Refactor boolean logic and conditions for clarity.

**Steps:**

- Extract complex boolean expressions into named variables
- Use 'not' and 'in' instead of complex comparisons
- Combine related conditions to reduce lines
- Consider using guard clauses to reduce nesting
- Add comments explaining non-obvious logic

**Benefit:** Improves readability, reduces bug risk

### Affected Files

- `app.py`

---

## #10 High Cyclomatic Complexity

**File:** `cache.py`

**Priority:** HIGH | **Effort:** MEDIUM

### Problem

High cyclomatic complexity: 26. This file has 25 decision points (if/for/while/except etc.).

### Rationale

Complexity of 26 means exponential test combinations. Each reduction matters.

### Suggested Strategies

#### 1. Extract Methods

High complexity (CC=26) indicates too many decision paths. Extract conditions into helper methods.

**Steps:**

- Identify separate conditional branches
- Extract each branch/condition into a descriptive method
- Name methods after their purpose (e.g., is_valid_user())
- Replace complex conditions with method calls
- Return early when conditions fail

**Benefit:** Reduces complexity, improves readability, easier to test each path

#### 2. Use Polymorphism

Replace complex if/elif chains with polymorphic dispatch.

**Steps:**

- Identify if/elif chains checking types or categories
- Create base class or interface
- Create subclasses for each condition
- Implement behavior in each subclass
- Replace switch logic with polymorphic calls

**Benefit:** Eliminates switch logic, enables extensibility without modification

#### 3. Simplify Logic

Refactor boolean logic and conditions for clarity.

**Steps:**

- Extract complex boolean expressions into named variables
- Use 'not' and 'in' instead of complex comparisons
- Combine related conditions to reduce lines
- Consider using guard clauses to reduce nesting
- Add comments explaining non-obvious logic

**Benefit:** Improves readability, reduces bug risk

### Affected Files

- `cache.py`

---

## #11 High Cyclomatic Complexity

**File:** `graph.py`

**Priority:** HIGH | **Effort:** MEDIUM

### Problem

High cyclomatic complexity: 59. This file has 58 decision points (if/for/while/except etc.).

### Rationale

Complexity of 59 means exponential test combinations. Each reduction matters.

### Suggested Strategies

#### 1. Extract Methods

High complexity (CC=59) indicates too many decision paths. Extract conditions into helper methods.

**Steps:**

- Identify separate conditional branches
- Extract each branch/condition into a descriptive method
- Name methods after their purpose (e.g., is_valid_user())
- Replace complex conditions with method calls
- Return early when conditions fail

**Benefit:** Reduces complexity, improves readability, easier to test each path

#### 2. Use Polymorphism

Replace complex if/elif chains with polymorphic dispatch.

**Steps:**

- Identify if/elif chains checking types or categories
- Create base class or interface
- Create subclasses for each condition
- Implement behavior in each subclass
- Replace switch logic with polymorphic calls

**Benefit:** Eliminates switch logic, enables extensibility without modification

#### 3. Simplify Logic

Refactor boolean logic and conditions for clarity.

**Steps:**

- Extract complex boolean expressions into named variables
- Use 'not' and 'in' instead of complex comparisons
- Combine related conditions to reduce lines
- Consider using guard clauses to reduce nesting
- Add comments explaining non-obvious logic

**Benefit:** Improves readability, reduces bug risk

### Affected Files

- `graph.py`

---

## #12 High Cyclomatic Complexity

**File:** `graph_rag.py`

**Priority:** HIGH | **Effort:** MEDIUM

### Problem

High cyclomatic complexity: 38. This file has 37 decision points (if/for/while/except etc.).

### Rationale

Complexity of 38 means exponential test combinations. Each reduction matters.

### Suggested Strategies

#### 1. Extract Methods

High complexity (CC=38) indicates too many decision paths. Extract conditions into helper methods.

**Steps:**

- Identify separate conditional branches
- Extract each branch/condition into a descriptive method
- Name methods after their purpose (e.g., is_valid_user())
- Replace complex conditions with method calls
- Return early when conditions fail

**Benefit:** Reduces complexity, improves readability, easier to test each path

#### 2. Use Polymorphism

Replace complex if/elif chains with polymorphic dispatch.

**Steps:**

- Identify if/elif chains checking types or categories
- Create base class or interface
- Create subclasses for each condition
- Implement behavior in each subclass
- Replace switch logic with polymorphic calls

**Benefit:** Eliminates switch logic, enables extensibility without modification

#### 3. Simplify Logic

Refactor boolean logic and conditions for clarity.

**Steps:**

- Extract complex boolean expressions into named variables
- Use 'not' and 'in' instead of complex comparisons
- Combine related conditions to reduce lines
- Consider using guard clauses to reduce nesting
- Add comments explaining non-obvious logic

**Benefit:** Improves readability, reduces bug risk

### Affected Files

- `graph_rag.py`

---

## #13 High Cyclomatic Complexity

**File:** `graph_traversal.py`

**Priority:** HIGH | **Effort:** MEDIUM

### Problem

High cyclomatic complexity: 71. This file has 70 decision points (if/for/while/except etc.).

### Rationale

Complexity of 71 means exponential test combinations. Each reduction matters.

### Suggested Strategies

#### 1. Extract Methods

High complexity (CC=71) indicates too many decision paths. Extract conditions into helper methods.

**Steps:**

- Identify separate conditional branches
- Extract each branch/condition into a descriptive method
- Name methods after their purpose (e.g., is_valid_user())
- Replace complex conditions with method calls
- Return early when conditions fail

**Benefit:** Reduces complexity, improves readability, easier to test each path

#### 2. Use Polymorphism

Replace complex if/elif chains with polymorphic dispatch.

**Steps:**

- Identify if/elif chains checking types or categories
- Create base class or interface
- Create subclasses for each condition
- Implement behavior in each subclass
- Replace switch logic with polymorphic calls

**Benefit:** Eliminates switch logic, enables extensibility without modification

#### 3. Simplify Logic

Refactor boolean logic and conditions for clarity.

**Steps:**

- Extract complex boolean expressions into named variables
- Use 'not' and 'in' instead of complex comparisons
- Combine related conditions to reduce lines
- Consider using guard clauses to reduce nesting
- Add comments explaining non-obvious logic

**Benefit:** Improves readability, reduces bug risk

### Affected Files

- `graph_traversal.py`

---

## #14 High Cyclomatic Complexity

**File:** `query_understanding.py`

**Priority:** HIGH | **Effort:** MEDIUM

### Problem

High cyclomatic complexity: 138. This file has 137 decision points (if/for/while/except etc.).

### Rationale

Complexity of 138 means exponential test combinations. Each reduction matters.

### Suggested Strategies

#### 1. Extract Methods

High complexity (CC=138) indicates too many decision paths. Extract conditions into helper methods.

**Steps:**

- Identify separate conditional branches
- Extract each branch/condition into a descriptive method
- Name methods after their purpose (e.g., is_valid_user())
- Replace complex conditions with method calls
- Return early when conditions fail

**Benefit:** Reduces complexity, improves readability, easier to test each path

#### 2. Use Polymorphism

Replace complex if/elif chains with polymorphic dispatch.

**Steps:**

- Identify if/elif chains checking types or categories
- Create base class or interface
- Create subclasses for each condition
- Implement behavior in each subclass
- Replace switch logic with polymorphic calls

**Benefit:** Eliminates switch logic, enables extensibility without modification

#### 3. Simplify Logic

Refactor boolean logic and conditions for clarity.

**Steps:**

- Extract complex boolean expressions into named variables
- Use 'not' and 'in' instead of complex comparisons
- Combine related conditions to reduce lines
- Consider using guard clauses to reduce nesting
- Add comments explaining non-obvious logic

**Benefit:** Improves readability, reduces bug risk

### Affected Files

- `query_understanding.py`

---

## #15 High Cyclomatic Complexity

**File:** `reasoning.py`

**Priority:** HIGH | **Effort:** MEDIUM

### Problem

High cyclomatic complexity: 60. This file has 59 decision points (if/for/while/except etc.).

### Rationale

Complexity of 60 means exponential test combinations. Each reduction matters.

### Suggested Strategies

#### 1. Extract Methods

High complexity (CC=60) indicates too many decision paths. Extract conditions into helper methods.

**Steps:**

- Identify separate conditional branches
- Extract each branch/condition into a descriptive method
- Name methods after their purpose (e.g., is_valid_user())
- Replace complex conditions with method calls
- Return early when conditions fail

**Benefit:** Reduces complexity, improves readability, easier to test each path

#### 2. Use Polymorphism

Replace complex if/elif chains with polymorphic dispatch.

**Steps:**

- Identify if/elif chains checking types or categories
- Create base class or interface
- Create subclasses for each condition
- Implement behavior in each subclass
- Replace switch logic with polymorphic calls

**Benefit:** Eliminates switch logic, enables extensibility without modification

#### 3. Simplify Logic

Refactor boolean logic and conditions for clarity.

**Steps:**

- Extract complex boolean expressions into named variables
- Use 'not' and 'in' instead of complex comparisons
- Combine related conditions to reduce lines
- Consider using guard clauses to reduce nesting
- Add comments explaining non-obvious logic

**Benefit:** Improves readability, reduces bug risk

### Affected Files

- `reasoning.py`

---

## #16 High Cyclomatic Complexity

**File:** `retrieval.py`

**Priority:** HIGH | **Effort:** MEDIUM

### Problem

High cyclomatic complexity: 108. This file has 107 decision points (if/for/while/except etc.).

### Rationale

Complexity of 108 means exponential test combinations. Each reduction matters.

### Suggested Strategies

#### 1. Extract Methods

High complexity (CC=108) indicates too many decision paths. Extract conditions into helper methods.

**Steps:**

- Identify separate conditional branches
- Extract each branch/condition into a descriptive method
- Name methods after their purpose (e.g., is_valid_user())
- Replace complex conditions with method calls
- Return early when conditions fail

**Benefit:** Reduces complexity, improves readability, easier to test each path

#### 2. Use Polymorphism

Replace complex if/elif chains with polymorphic dispatch.

**Steps:**

- Identify if/elif chains checking types or categories
- Create base class or interface
- Create subclasses for each condition
- Implement behavior in each subclass
- Replace switch logic with polymorphic calls

**Benefit:** Eliminates switch logic, enables extensibility without modification

#### 3. Simplify Logic

Refactor boolean logic and conditions for clarity.

**Steps:**

- Extract complex boolean expressions into named variables
- Use 'not' and 'in' instead of complex comparisons
- Combine related conditions to reduce lines
- Consider using guard clauses to reduce nesting
- Add comments explaining non-obvious logic

**Benefit:** Improves readability, reduces bug risk

### Affected Files

- `retrieval.py`

---

## #17 High Cyclomatic Complexity

**File:** `symbol_driven_ranking.py`

**Priority:** HIGH | **Effort:** MEDIUM

### Problem

High cyclomatic complexity: 138. This file has 137 decision points (if/for/while/except etc.).

### Rationale

Complexity of 138 means exponential test combinations. Each reduction matters.

### Suggested Strategies

#### 1. Extract Methods

High complexity (CC=138) indicates too many decision paths. Extract conditions into helper methods.

**Steps:**

- Identify separate conditional branches
- Extract each branch/condition into a descriptive method
- Name methods after their purpose (e.g., is_valid_user())
- Replace complex conditions with method calls
- Return early when conditions fail

**Benefit:** Reduces complexity, improves readability, easier to test each path

#### 2. Use Polymorphism

Replace complex if/elif chains with polymorphic dispatch.

**Steps:**

- Identify if/elif chains checking types or categories
- Create base class or interface
- Create subclasses for each condition
- Implement behavior in each subclass
- Replace switch logic with polymorphic calls

**Benefit:** Eliminates switch logic, enables extensibility without modification

#### 3. Simplify Logic

Refactor boolean logic and conditions for clarity.

**Steps:**

- Extract complex boolean expressions into named variables
- Use 'not' and 'in' instead of complex comparisons
- Combine related conditions to reduce lines
- Consider using guard clauses to reduce nesting
- Add comments explaining non-obvious logic

**Benefit:** Improves readability, reduces bug risk

### Affected Files

- `symbol_driven_ranking.py`

---

## #18 High Cyclomatic Complexity

**File:** `unified_retrieval.py`

**Priority:** HIGH | **Effort:** MEDIUM

### Problem

High cyclomatic complexity: 200. This file has 199 decision points (if/for/while/except etc.).

### Rationale

Complexity of 200 means exponential test combinations. Each reduction matters.

### Suggested Strategies

#### 1. Extract Methods

High complexity (CC=200) indicates too many decision paths. Extract conditions into helper methods.

**Steps:**

- Identify separate conditional branches
- Extract each branch/condition into a descriptive method
- Name methods after their purpose (e.g., is_valid_user())
- Replace complex conditions with method calls
- Return early when conditions fail

**Benefit:** Reduces complexity, improves readability, easier to test each path

#### 2. Use Polymorphism

Replace complex if/elif chains with polymorphic dispatch.

**Steps:**

- Identify if/elif chains checking types or categories
- Create base class or interface
- Create subclasses for each condition
- Implement behavior in each subclass
- Replace switch logic with polymorphic calls

**Benefit:** Eliminates switch logic, enables extensibility without modification

#### 3. Simplify Logic

Refactor boolean logic and conditions for clarity.

**Steps:**

- Extract complex boolean expressions into named variables
- Use 'not' and 'in' instead of complex comparisons
- Combine related conditions to reduce lines
- Consider using guard clauses to reduce nesting
- Add comments explaining non-obvious logic

**Benefit:** Improves readability, reduces bug risk

### Affected Files

- `unified_retrieval.py`

---

## #19 High Cyclomatic Complexity

**File:** `utils.py`

**Priority:** HIGH | **Effort:** MEDIUM

### Problem

High cyclomatic complexity: 33. This file has 32 decision points (if/for/while/except etc.).

### Rationale

Complexity of 33 means exponential test combinations. Each reduction matters.

### Suggested Strategies

#### 1. Extract Methods

High complexity (CC=33) indicates too many decision paths. Extract conditions into helper methods.

**Steps:**

- Identify separate conditional branches
- Extract each branch/condition into a descriptive method
- Name methods after their purpose (e.g., is_valid_user())
- Replace complex conditions with method calls
- Return early when conditions fail

**Benefit:** Reduces complexity, improves readability, easier to test each path

#### 2. Use Polymorphism

Replace complex if/elif chains with polymorphic dispatch.

**Steps:**

- Identify if/elif chains checking types or categories
- Create base class or interface
- Create subclasses for each condition
- Implement behavior in each subclass
- Replace switch logic with polymorphic calls

**Benefit:** Eliminates switch logic, enables extensibility without modification

#### 3. Simplify Logic

Refactor boolean logic and conditions for clarity.

**Steps:**

- Extract complex boolean expressions into named variables
- Use 'not' and 'in' instead of complex comparisons
- Combine related conditions to reduce lines
- Consider using guard clauses to reduce nesting
- Add comments explaining non-obvious logic

**Benefit:** Improves readability, reduces bug risk

### Affected Files

- `utils.py`

---

## #20 High Cyclomatic Complexity

**File:** `onboarding\analyzer.py`

**Priority:** HIGH | **Effort:** MEDIUM

### Problem

High cyclomatic complexity: 233. This file has 232 decision points (if/for/while/except etc.).

### Rationale

Complexity of 233 means exponential test combinations. Each reduction matters.

### Suggested Strategies

#### 1. Extract Methods

High complexity (CC=233) indicates too many decision paths. Extract conditions into helper methods.

**Steps:**

- Identify separate conditional branches
- Extract each branch/condition into a descriptive method
- Name methods after their purpose (e.g., is_valid_user())
- Replace complex conditions with method calls
- Return early when conditions fail

**Benefit:** Reduces complexity, improves readability, easier to test each path

#### 2. Use Polymorphism

Replace complex if/elif chains with polymorphic dispatch.

**Steps:**

- Identify if/elif chains checking types or categories
- Create base class or interface
- Create subclasses for each condition
- Implement behavior in each subclass
- Replace switch logic with polymorphic calls

**Benefit:** Eliminates switch logic, enables extensibility without modification

#### 3. Simplify Logic

Refactor boolean logic and conditions for clarity.

**Steps:**

- Extract complex boolean expressions into named variables
- Use 'not' and 'in' instead of complex comparisons
- Combine related conditions to reduce lines
- Consider using guard clauses to reduce nesting
- Add comments explaining non-obvious logic

**Benefit:** Improves readability, reduces bug risk

### Affected Files

- `onboarding\analyzer.py`

---

## #21 High Cyclomatic Complexity

**File:** `onboarding\visualization.py`

**Priority:** HIGH | **Effort:** MEDIUM

### Problem

High cyclomatic complexity: 83. This file has 82 decision points (if/for/while/except etc.).

### Rationale

Complexity of 83 means exponential test combinations. Each reduction matters.

### Suggested Strategies

#### 1. Extract Methods

High complexity (CC=83) indicates too many decision paths. Extract conditions into helper methods.

**Steps:**

- Identify separate conditional branches
- Extract each branch/condition into a descriptive method
- Name methods after their purpose (e.g., is_valid_user())
- Replace complex conditions with method calls
- Return early when conditions fail

**Benefit:** Reduces complexity, improves readability, easier to test each path

#### 2. Use Polymorphism

Replace complex if/elif chains with polymorphic dispatch.

**Steps:**

- Identify if/elif chains checking types or categories
- Create base class or interface
- Create subclasses for each condition
- Implement behavior in each subclass
- Replace switch logic with polymorphic calls

**Benefit:** Eliminates switch logic, enables extensibility without modification

#### 3. Simplify Logic

Refactor boolean logic and conditions for clarity.

**Steps:**

- Extract complex boolean expressions into named variables
- Use 'not' and 'in' instead of complex comparisons
- Combine related conditions to reduce lines
- Consider using guard clauses to reduce nesting
- Add comments explaining non-obvious logic

**Benefit:** Improves readability, reduces bug risk

### Affected Files

- `onboarding\visualization.py`

---

## #22 Change Hotspot

**File:** `app.py`

**Priority:** HIGH | **Effort:** HIGH

### Problem

File is a change hotspot: complex (145 CC), large (748 LOC), and tightly coupled (11 dependencies).

### Rationale

Hotspots accumulate bugs and become resistant to change.

### Suggested Strategies

#### 1. Stabilize Through Refactoring

Reduce hotspot risk by addressing root causes.

**Steps:**

- Apply 'High Complexity' strategies to reduce CC
- Apply 'God File' strategies to reduce size
- Apply 'Tight Coupling' strategies to reduce dependencies
- Add comprehensive tests
- Consider extracting volatile parts

**Benefit:** Reduces change frequency and bug risk

#### 2. Isolate Volatile Code

Separate stable and changing code.

**Steps:**

- Identify what changes frequently vs. what's stable
- Extract volatile logic into separate module
- Create stable interface that hides volatility
- Concentrate testing on volatile parts
- Update other modules to use stable interface

**Benefit:** Limits blast radius of changes, easier to test

#### 3. Improve Test Coverage

Add tests to hotspot to reduce change risks.

**Steps:**

- Measure current test coverage for this file
- Identify hard-to-test areas
- Refactor to enable testing (extract, inject dependencies)
- Add unit tests for all paths
- Add property-based tests for complex logic

**Benefit:** Catches regressions early, enables confident refactoring

### Affected Files

- `app.py`

---

## #23 Change Hotspot

**File:** `unified_retrieval.py`

**Priority:** HIGH | **Effort:** HIGH

### Problem

File is a change hotspot: complex (200 CC), large (802 LOC), and tightly coupled (5 dependencies).

### Rationale

Hotspots accumulate bugs and become resistant to change.

### Suggested Strategies

#### 1. Stabilize Through Refactoring

Reduce hotspot risk by addressing root causes.

**Steps:**

- Apply 'High Complexity' strategies to reduce CC
- Apply 'God File' strategies to reduce size
- Apply 'Tight Coupling' strategies to reduce dependencies
- Add comprehensive tests
- Consider extracting volatile parts

**Benefit:** Reduces change frequency and bug risk

#### 2. Isolate Volatile Code

Separate stable and changing code.

**Steps:**

- Identify what changes frequently vs. what's stable
- Extract volatile logic into separate module
- Create stable interface that hides volatility
- Concentrate testing on volatile parts
- Update other modules to use stable interface

**Benefit:** Limits blast radius of changes, easier to test

#### 3. Improve Test Coverage

Add tests to hotspot to reduce change risks.

**Steps:**

- Measure current test coverage for this file
- Identify hard-to-test areas
- Refactor to enable testing (extract, inject dependencies)
- Add unit tests for all paths
- Add property-based tests for complex logic

**Benefit:** Catches regressions early, enables confident refactoring

### Affected Files

- `unified_retrieval.py`

---

## #24 Change Hotspot

**File:** `symbol_driven_ranking.py`

**Priority:** HIGH | **Effort:** HIGH

### Problem

File is a change hotspot: complex (138 CC), large (659 LOC), and tightly coupled (4 dependencies).

### Rationale

Hotspots accumulate bugs and become resistant to change.

### Suggested Strategies

#### 1. Stabilize Through Refactoring

Reduce hotspot risk by addressing root causes.

**Steps:**

- Apply 'High Complexity' strategies to reduce CC
- Apply 'God File' strategies to reduce size
- Apply 'Tight Coupling' strategies to reduce dependencies
- Add comprehensive tests
- Consider extracting volatile parts

**Benefit:** Reduces change frequency and bug risk

#### 2. Isolate Volatile Code

Separate stable and changing code.

**Steps:**

- Identify what changes frequently vs. what's stable
- Extract volatile logic into separate module
- Create stable interface that hides volatility
- Concentrate testing on volatile parts
- Update other modules to use stable interface

**Benefit:** Limits blast radius of changes, easier to test

#### 3. Improve Test Coverage

Add tests to hotspot to reduce change risks.

**Steps:**

- Measure current test coverage for this file
- Identify hard-to-test areas
- Refactor to enable testing (extract, inject dependencies)
- Add unit tests for all paths
- Add property-based tests for complex logic

**Benefit:** Catches regressions early, enables confident refactoring

### Affected Files

- `symbol_driven_ranking.py`

---

## #25 Change Hotspot

**File:** `query_understanding.py`

**Priority:** HIGH | **Effort:** HIGH

### Problem

File is a change hotspot: complex (138 CC), large (644 LOC), and tightly coupled (3 dependencies).

### Rationale

Hotspots accumulate bugs and become resistant to change.

### Suggested Strategies

#### 1. Stabilize Through Refactoring

Reduce hotspot risk by addressing root causes.

**Steps:**

- Apply 'High Complexity' strategies to reduce CC
- Apply 'God File' strategies to reduce size
- Apply 'Tight Coupling' strategies to reduce dependencies
- Add comprehensive tests
- Consider extracting volatile parts

**Benefit:** Reduces change frequency and bug risk

#### 2. Isolate Volatile Code

Separate stable and changing code.

**Steps:**

- Identify what changes frequently vs. what's stable
- Extract volatile logic into separate module
- Create stable interface that hides volatility
- Concentrate testing on volatile parts
- Update other modules to use stable interface

**Benefit:** Limits blast radius of changes, easier to test

#### 3. Improve Test Coverage

Add tests to hotspot to reduce change risks.

**Steps:**

- Measure current test coverage for this file
- Identify hard-to-test areas
- Refactor to enable testing (extract, inject dependencies)
- Add unit tests for all paths
- Add property-based tests for complex logic

**Benefit:** Catches regressions early, enables confident refactoring

### Affected Files

- `query_understanding.py`

---

## #26 Change Hotspot

**File:** `retrieval.py`

**Priority:** HIGH | **Effort:** HIGH

### Problem

File is a change hotspot: complex (108 CC), large (406 LOC), and tightly coupled (5 dependencies).

### Rationale

Hotspots accumulate bugs and become resistant to change.

### Suggested Strategies

#### 1. Stabilize Through Refactoring

Reduce hotspot risk by addressing root causes.

**Steps:**

- Apply 'High Complexity' strategies to reduce CC
- Apply 'God File' strategies to reduce size
- Apply 'Tight Coupling' strategies to reduce dependencies
- Add comprehensive tests
- Consider extracting volatile parts

**Benefit:** Reduces change frequency and bug risk

#### 2. Isolate Volatile Code

Separate stable and changing code.

**Steps:**

- Identify what changes frequently vs. what's stable
- Extract volatile logic into separate module
- Create stable interface that hides volatility
- Concentrate testing on volatile parts
- Update other modules to use stable interface

**Benefit:** Limits blast radius of changes, easier to test

#### 3. Improve Test Coverage

Add tests to hotspot to reduce change risks.

**Steps:**

- Measure current test coverage for this file
- Identify hard-to-test areas
- Refactor to enable testing (extract, inject dependencies)
- Add unit tests for all paths
- Add property-based tests for complex logic

**Benefit:** Catches regressions early, enables confident refactoring

### Affected Files

- `retrieval.py`

---

## #27 Tight Coupling

**File:** `app.py`

**Priority:** MEDIUM | **Effort:** HIGH

### Problem

File depends on too many other modules (11 dependencies). Average is 4 dependencies.

### Rationale

Too many dependencies (11) create fragility and test complexity.

### Suggested Strategies

#### 1. Extract Interface/Abstract Class

Reduce direct dependencies (11) by introducing abstractions.

**Steps:**

- Identify dependencies this module relies on
- Extract common interface from dependencies
- Create abstract base class or protocol
- Depend on abstraction instead of concrete classes
- Inject dependencies at construction time

**Benefit:** Decouples from concrete implementations, enables testing with mocks

#### 2. Apply Dependency Injection

Reduce coupling by injecting dependencies rather than importing directly.

**Steps:**

- Identify direct imports/dependencies
- Add parameters to functions/classes to accept dependencies
- Remove hard-coded imports where possible
- Create factory or container to wire dependencies
- Test with mock implementations

**Benefit:** Increases testability, reduces coupling, improves flexibility

#### 3. Reorganize Module Structure

Reduce dependencies by changing module organization.

**Steps:**

- Analyze dependency graph for this module
- Move common utilities to shared module
- Create domain-specific sub-packages
- Reduce cross-package dependencies
- Consider pub/sub patterns for loose coupling

**Benefit:** Clearer architecture, fewer circular dependencies, easier navigation

### Affected Files

- `app.py`

---

## #28 Tight Coupling

**File:** `cache.py`

**Priority:** MEDIUM | **Effort:** HIGH

### Problem

File depends on too many other modules (11 dependencies). Average is 4 dependencies.

### Rationale

Too many dependencies (11) create fragility and test complexity.

### Suggested Strategies

#### 1. Extract Interface/Abstract Class

Reduce direct dependencies (11) by introducing abstractions.

**Steps:**

- Identify dependencies this module relies on
- Extract common interface from dependencies
- Create abstract base class or protocol
- Depend on abstraction instead of concrete classes
- Inject dependencies at construction time

**Benefit:** Decouples from concrete implementations, enables testing with mocks

#### 2. Apply Dependency Injection

Reduce coupling by injecting dependencies rather than importing directly.

**Steps:**

- Identify direct imports/dependencies
- Add parameters to functions/classes to accept dependencies
- Remove hard-coded imports where possible
- Create factory or container to wire dependencies
- Test with mock implementations

**Benefit:** Increases testability, reduces coupling, improves flexibility

#### 3. Reorganize Module Structure

Reduce dependencies by changing module organization.

**Steps:**

- Analyze dependency graph for this module
- Move common utilities to shared module
- Create domain-specific sub-packages
- Reduce cross-package dependencies
- Consider pub/sub patterns for loose coupling

**Benefit:** Clearer architecture, fewer circular dependencies, easier navigation

### Affected Files

- `cache.py`

---

## #29 Orphaned File

**File:** `onboarding\analyzer.py`

**Priority:** LOW | **Effort:** LOW

### Problem

File is isolated with no imports and not imported by any other file. May be dead code or incorrectly placed.

### Rationale

Orphaned files are confusing and hard to maintain.

### Suggested Strategies

#### 1. Remove Orphaned File

Delete isolated files that serve no purpose.

**Steps:**

- Verify the file truly has no dependencies
- Check git history to understand original purpose
- Confirm no external references to this module
- Delete the file
- Run tests and linter

**Benefit:** Reduces clutter, simplifies project structure

#### 2. Integrate Into Existing Module

Move orphaned content into a related, active module.

**Steps:**

- Identify the most related module based on functionality
- Move classes/functions from orphan to target module
- Consolidate imports
- Update any imports that reference the orphan
- Delete the orphaned file
- Run tests

**Benefit:** Improves organization, reduces fragmentation

#### 3. Establish Connections

If the file serves a purpose, establish its role.

**Steps:**

- Understand what the file does
- Find or create entry point that uses it
- Add it to package __init__.py if needed
- Update documentation to explain its role
- Add comments explaining why it exists

**Benefit:** Makes code discoverable, improves navigation

### Affected Files

- `onboarding\analyzer.py`

---

