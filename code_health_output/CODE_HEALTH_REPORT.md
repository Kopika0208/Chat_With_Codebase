# Code Health & Quality Report

Generated: 2026-01-25 13:15:16

## Overall Health Score: 32.2/100 (Grade: D - Poor)

Code health is poor. Major refactoring recommended.

---

## Health Dimensions

- **Maintainability:** 0.0/100
- **Modularity:** 78.7/100
- **Readability:** 50.2/100
- **Change Risk:** 0.0/100
- **Dependency Hygiene:** 0.0/100

## Code Statistics

### Repository Summary

| Metric | Value |
|--------|-------|
| Total Files | 15 |
| Total LOC | 5841 |
| Code LOC | 4392 |
| Comment LOC | 3380 |
| Blank Lines | 1075 |
| Functions | 179 |
| Classes | 34 |
| Modules | 2 |
| Avg Function Length | 142.9 |
| Avg Cyclomatic Complexity | 89.20 |
| Comment-to-Code Ratio | 0.77 |

## Code Smells

Total smells detected: 29

### Change Hotspot (5)

- **File:** `app.py`
  - **Severity:** HIGH
  - **Description:** File is a change hotspot: complex (145 CC), large (748 LOC), and tightly coupled (11 dependencies).
  - **Why it's a problem:** Hotspot files are high-risk: changes are frequent and error-prone. They accumulate complexity and create maintenance burden.

- **File:** `unified_retrieval.py`
  - **Severity:** HIGH
  - **Description:** File is a change hotspot: complex (200 CC), large (802 LOC), and tightly coupled (5 dependencies).
  - **Why it's a problem:** Hotspot files are high-risk: changes are frequent and error-prone. They accumulate complexity and create maintenance burden.

- **File:** `symbol_driven_ranking.py`
  - **Severity:** HIGH
  - **Description:** File is a change hotspot: complex (138 CC), large (659 LOC), and tightly coupled (4 dependencies).
  - **Why it's a problem:** Hotspot files are high-risk: changes are frequent and error-prone. They accumulate complexity and create maintenance burden.

- **File:** `query_understanding.py`
  - **Severity:** HIGH
  - **Description:** File is a change hotspot: complex (138 CC), large (644 LOC), and tightly coupled (3 dependencies).
  - **Why it's a problem:** Hotspot files are high-risk: changes are frequent and error-prone. They accumulate complexity and create maintenance burden.

- **File:** `retrieval.py`
  - **Severity:** HIGH
  - **Description:** File is a change hotspot: complex (108 CC), large (406 LOC), and tightly coupled (5 dependencies).
  - **Why it's a problem:** Hotspot files are high-risk: changes are frequent and error-prone. They accumulate complexity and create maintenance burden.

### High Cyclomatic Complexity (13)

- **File:** `app.py`
  - **Severity:** CRITICAL
  - **Description:** High cyclomatic complexity: 145. This file has 144 decision points (if/for/while/except etc.).
  - **Why it's a problem:** High complexity increases bug risk, testing effort, and cognitive load. Each decision point adds exponential test combinations.

- **File:** `cache.py`
  - **Severity:** CRITICAL
  - **Description:** High cyclomatic complexity: 26. This file has 25 decision points (if/for/while/except etc.).
  - **Why it's a problem:** High complexity increases bug risk, testing effort, and cognitive load. Each decision point adds exponential test combinations.

- **File:** `graph.py`
  - **Severity:** CRITICAL
  - **Description:** High cyclomatic complexity: 59. This file has 58 decision points (if/for/while/except etc.).
  - **Why it's a problem:** High complexity increases bug risk, testing effort, and cognitive load. Each decision point adds exponential test combinations.

- **File:** `graph_rag.py`
  - **Severity:** CRITICAL
  - **Description:** High cyclomatic complexity: 38. This file has 37 decision points (if/for/while/except etc.).
  - **Why it's a problem:** High complexity increases bug risk, testing effort, and cognitive load. Each decision point adds exponential test combinations.

- **File:** `graph_traversal.py`
  - **Severity:** CRITICAL
  - **Description:** High cyclomatic complexity: 71. This file has 70 decision points (if/for/while/except etc.).
  - **Why it's a problem:** High complexity increases bug risk, testing effort, and cognitive load. Each decision point adds exponential test combinations.

- **File:** `query_understanding.py`
  - **Severity:** CRITICAL
  - **Description:** High cyclomatic complexity: 138. This file has 137 decision points (if/for/while/except etc.).
  - **Why it's a problem:** High complexity increases bug risk, testing effort, and cognitive load. Each decision point adds exponential test combinations.

- **File:** `reasoning.py`
  - **Severity:** CRITICAL
  - **Description:** High cyclomatic complexity: 60. This file has 59 decision points (if/for/while/except etc.).
  - **Why it's a problem:** High complexity increases bug risk, testing effort, and cognitive load. Each decision point adds exponential test combinations.

- **File:** `retrieval.py`
  - **Severity:** CRITICAL
  - **Description:** High cyclomatic complexity: 108. This file has 107 decision points (if/for/while/except etc.).
  - **Why it's a problem:** High complexity increases bug risk, testing effort, and cognitive load. Each decision point adds exponential test combinations.

- **File:** `symbol_driven_ranking.py`
  - **Severity:** CRITICAL
  - **Description:** High cyclomatic complexity: 138. This file has 137 decision points (if/for/while/except etc.).
  - **Why it's a problem:** High complexity increases bug risk, testing effort, and cognitive load. Each decision point adds exponential test combinations.

- **File:** `unified_retrieval.py`
  - **Severity:** CRITICAL
  - **Description:** High cyclomatic complexity: 200. This file has 199 decision points (if/for/while/except etc.).
  - **Why it's a problem:** High complexity increases bug risk, testing effort, and cognitive load. Each decision point adds exponential test combinations.

- **File:** `utils.py`
  - **Severity:** CRITICAL
  - **Description:** High cyclomatic complexity: 33. This file has 32 decision points (if/for/while/except etc.).
  - **Why it's a problem:** High complexity increases bug risk, testing effort, and cognitive load. Each decision point adds exponential test combinations.

- **File:** `onboarding\analyzer.py`
  - **Severity:** CRITICAL
  - **Description:** High cyclomatic complexity: 233. This file has 232 decision points (if/for/while/except etc.).
  - **Why it's a problem:** High complexity increases bug risk, testing effort, and cognitive load. Each decision point adds exponential test combinations.

- **File:** `onboarding\visualization.py`
  - **Severity:** CRITICAL
  - **Description:** High cyclomatic complexity: 83. This file has 82 decision points (if/for/while/except etc.).
  - **Why it's a problem:** High complexity increases bug risk, testing effort, and cognitive load. Each decision point adds exponential test combinations.

### Long Functions (8)

- **File:** `app.py`
  - **Severity:** HIGH
  - **Description:** Functions are too long (average: 354 lines). Contains 3 functions.
  - **Why it's a problem:** Long functions are difficult to understand, test, and reuse. They often do multiple things and have hidden bugs.

- **File:** `graph.py`
  - **Severity:** MEDIUM
  - **Description:** Functions are too long (average: 53 lines). Contains 10 functions.
  - **Why it's a problem:** Long functions are difficult to understand, test, and reuse. They often do multiple things and have hidden bugs.

- **File:** `graph_rag.py`
  - **Severity:** HIGH
  - **Description:** Functions are too long (average: 143 lines). Contains 9 functions.
  - **Why it's a problem:** Long functions are difficult to understand, test, and reuse. They often do multiple things and have hidden bugs.

- **File:** `graph_traversal.py`
  - **Severity:** HIGH
  - **Description:** Functions are too long (average: 265 lines). Contains 15 functions.
  - **Why it's a problem:** Long functions are difficult to understand, test, and reuse. They often do multiple things and have hidden bugs.

- **File:** `reasoning.py`
  - **Severity:** HIGH
  - **Description:** Functions are too long (average: 153 lines). Contains 8 functions.
  - **Why it's a problem:** Long functions are difficult to understand, test, and reuse. They often do multiple things and have hidden bugs.

- **File:** `symbol_driven_ranking.py`
  - **Severity:** MEDIUM
  - **Description:** Functions are too long (average: 78 lines). Contains 27 functions.
  - **Why it's a problem:** Long functions are difficult to understand, test, and reuse. They often do multiple things and have hidden bugs.

- **File:** `unified_retrieval.py`
  - **Severity:** HIGH
  - **Description:** Functions are too long (average: 111 lines). Contains 37 functions.
  - **Why it's a problem:** Long functions are difficult to understand, test, and reuse. They often do multiple things and have hidden bugs.

- **File:** `onboarding\analyzer.py`
  - **Severity:** HIGH
  - **Description:** Functions are too long (average: 688 lines). Contains 14 functions.
  - **Why it's a problem:** Long functions are difficult to understand, test, and reuse. They often do multiple things and have hidden bugs.

### Orphaned File (1)

- **File:** `onboarding\analyzer.py`
  - **Severity:** MEDIUM
  - **Description:** File is isolated with no imports and not imported by any other file. May be dead code or incorrectly placed.
  - **Why it's a problem:** Orphaned files indicate potential dead code or organizational issues. They may indicate incomplete refactoring or misplaced functionality.

### Tight Coupling (2)

- **File:** `app.py`
  - **Severity:** MEDIUM
  - **Description:** File depends on too many other modules (11 dependencies). Average is 4 dependencies.
  - **Why it's a problem:** Too many dependencies make code fragile and difficult to test. Changes in dependencies have cascading effects.

- **File:** `cache.py`
  - **Severity:** MEDIUM
  - **Description:** File depends on too many other modules (11 dependencies). Average is 4 dependencies.
  - **Why it's a problem:** Too many dependencies make code fragile and difficult to test. Changes in dependencies have cascading effects.

---

## Refactoring Suggestions

Total suggestions: 29

### 1. Long Functions - `app.py`

**Priority:** HIGH | **Effort:** MEDIUM

**Problem:** Functions are too long (average: 354 lines). Contains 3 functions.

**Rationale:** Long functions are hard to understand, test, and maintain.

**Strategies:**

- **Extract Helper Methods:** Break down large functions (avg 354 lines) into smaller, focused helper methods.
- **Extract to Separate Functions:** Move related logic into standalone functions for clarity.
- **Use Guard Clauses:** Replace nested if statements with early returns.

---

### 2. Long Functions - `graph.py`

**Priority:** HIGH | **Effort:** MEDIUM

**Problem:** Functions are too long (average: 53 lines). Contains 10 functions.

**Rationale:** Long functions are hard to understand, test, and maintain.

**Strategies:**

- **Extract Helper Methods:** Break down large functions (avg 53 lines) into smaller, focused helper methods.
- **Extract to Separate Functions:** Move related logic into standalone functions for clarity.
- **Use Guard Clauses:** Replace nested if statements with early returns.

---

### 3. Long Functions - `graph_rag.py`

**Priority:** HIGH | **Effort:** MEDIUM

**Problem:** Functions are too long (average: 143 lines). Contains 9 functions.

**Rationale:** Long functions are hard to understand, test, and maintain.

**Strategies:**

- **Extract Helper Methods:** Break down large functions (avg 143 lines) into smaller, focused helper methods.
- **Extract to Separate Functions:** Move related logic into standalone functions for clarity.
- **Use Guard Clauses:** Replace nested if statements with early returns.

---

### 4. Long Functions - `graph_traversal.py`

**Priority:** HIGH | **Effort:** MEDIUM

**Problem:** Functions are too long (average: 265 lines). Contains 15 functions.

**Rationale:** Long functions are hard to understand, test, and maintain.

**Strategies:**

- **Extract Helper Methods:** Break down large functions (avg 265 lines) into smaller, focused helper methods.
- **Extract to Separate Functions:** Move related logic into standalone functions for clarity.
- **Use Guard Clauses:** Replace nested if statements with early returns.

---

### 5. Long Functions - `reasoning.py`

**Priority:** HIGH | **Effort:** MEDIUM

**Problem:** Functions are too long (average: 153 lines). Contains 8 functions.

**Rationale:** Long functions are hard to understand, test, and maintain.

**Strategies:**

- **Extract Helper Methods:** Break down large functions (avg 153 lines) into smaller, focused helper methods.
- **Extract to Separate Functions:** Move related logic into standalone functions for clarity.
- **Use Guard Clauses:** Replace nested if statements with early returns.

---

### 6. Long Functions - `symbol_driven_ranking.py`

**Priority:** HIGH | **Effort:** MEDIUM

**Problem:** Functions are too long (average: 78 lines). Contains 27 functions.

**Rationale:** Long functions are hard to understand, test, and maintain.

**Strategies:**

- **Extract Helper Methods:** Break down large functions (avg 78 lines) into smaller, focused helper methods.
- **Extract to Separate Functions:** Move related logic into standalone functions for clarity.
- **Use Guard Clauses:** Replace nested if statements with early returns.

---

### 7. Long Functions - `unified_retrieval.py`

**Priority:** HIGH | **Effort:** MEDIUM

**Problem:** Functions are too long (average: 111 lines). Contains 37 functions.

**Rationale:** Long functions are hard to understand, test, and maintain.

**Strategies:**

- **Extract Helper Methods:** Break down large functions (avg 111 lines) into smaller, focused helper methods.
- **Extract to Separate Functions:** Move related logic into standalone functions for clarity.
- **Use Guard Clauses:** Replace nested if statements with early returns.

---

### 8. Long Functions - `onboarding\analyzer.py`

**Priority:** HIGH | **Effort:** MEDIUM

**Problem:** Functions are too long (average: 688 lines). Contains 14 functions.

**Rationale:** Long functions are hard to understand, test, and maintain.

**Strategies:**

- **Extract Helper Methods:** Break down large functions (avg 688 lines) into smaller, focused helper methods.
- **Extract to Separate Functions:** Move related logic into standalone functions for clarity.
- **Use Guard Clauses:** Replace nested if statements with early returns.

---

### 9. High Cyclomatic Complexity - `app.py`

**Priority:** HIGH | **Effort:** MEDIUM

**Problem:** High cyclomatic complexity: 145. This file has 144 decision points (if/for/while/except etc.).

**Rationale:** Complexity of 145 means exponential test combinations. Each reduction matters.

**Strategies:**

- **Extract Methods:** High complexity (CC=145) indicates too many decision paths. Extract conditions into helper methods.
- **Use Polymorphism:** Replace complex if/elif chains with polymorphic dispatch.
- **Simplify Logic:** Refactor boolean logic and conditions for clarity.

---

### 10. High Cyclomatic Complexity - `cache.py`

**Priority:** HIGH | **Effort:** MEDIUM

**Problem:** High cyclomatic complexity: 26. This file has 25 decision points (if/for/while/except etc.).

**Rationale:** Complexity of 26 means exponential test combinations. Each reduction matters.

**Strategies:**

- **Extract Methods:** High complexity (CC=26) indicates too many decision paths. Extract conditions into helper methods.
- **Use Polymorphism:** Replace complex if/elif chains with polymorphic dispatch.
- **Simplify Logic:** Refactor boolean logic and conditions for clarity.

---

### 11. High Cyclomatic Complexity - `graph.py`

**Priority:** HIGH | **Effort:** MEDIUM

**Problem:** High cyclomatic complexity: 59. This file has 58 decision points (if/for/while/except etc.).

**Rationale:** Complexity of 59 means exponential test combinations. Each reduction matters.

**Strategies:**

- **Extract Methods:** High complexity (CC=59) indicates too many decision paths. Extract conditions into helper methods.
- **Use Polymorphism:** Replace complex if/elif chains with polymorphic dispatch.
- **Simplify Logic:** Refactor boolean logic and conditions for clarity.

---

### 12. High Cyclomatic Complexity - `graph_rag.py`

**Priority:** HIGH | **Effort:** MEDIUM

**Problem:** High cyclomatic complexity: 38. This file has 37 decision points (if/for/while/except etc.).

**Rationale:** Complexity of 38 means exponential test combinations. Each reduction matters.

**Strategies:**

- **Extract Methods:** High complexity (CC=38) indicates too many decision paths. Extract conditions into helper methods.
- **Use Polymorphism:** Replace complex if/elif chains with polymorphic dispatch.
- **Simplify Logic:** Refactor boolean logic and conditions for clarity.

---

### 13. High Cyclomatic Complexity - `graph_traversal.py`

**Priority:** HIGH | **Effort:** MEDIUM

**Problem:** High cyclomatic complexity: 71. This file has 70 decision points (if/for/while/except etc.).

**Rationale:** Complexity of 71 means exponential test combinations. Each reduction matters.

**Strategies:**

- **Extract Methods:** High complexity (CC=71) indicates too many decision paths. Extract conditions into helper methods.
- **Use Polymorphism:** Replace complex if/elif chains with polymorphic dispatch.
- **Simplify Logic:** Refactor boolean logic and conditions for clarity.

---

### 14. High Cyclomatic Complexity - `query_understanding.py`

**Priority:** HIGH | **Effort:** MEDIUM

**Problem:** High cyclomatic complexity: 138. This file has 137 decision points (if/for/while/except etc.).

**Rationale:** Complexity of 138 means exponential test combinations. Each reduction matters.

**Strategies:**

- **Extract Methods:** High complexity (CC=138) indicates too many decision paths. Extract conditions into helper methods.
- **Use Polymorphism:** Replace complex if/elif chains with polymorphic dispatch.
- **Simplify Logic:** Refactor boolean logic and conditions for clarity.

---

### 15. High Cyclomatic Complexity - `reasoning.py`

**Priority:** HIGH | **Effort:** MEDIUM

**Problem:** High cyclomatic complexity: 60. This file has 59 decision points (if/for/while/except etc.).

**Rationale:** Complexity of 60 means exponential test combinations. Each reduction matters.

**Strategies:**

- **Extract Methods:** High complexity (CC=60) indicates too many decision paths. Extract conditions into helper methods.
- **Use Polymorphism:** Replace complex if/elif chains with polymorphic dispatch.
- **Simplify Logic:** Refactor boolean logic and conditions for clarity.

---

### 16. High Cyclomatic Complexity - `retrieval.py`

**Priority:** HIGH | **Effort:** MEDIUM

**Problem:** High cyclomatic complexity: 108. This file has 107 decision points (if/for/while/except etc.).

**Rationale:** Complexity of 108 means exponential test combinations. Each reduction matters.

**Strategies:**

- **Extract Methods:** High complexity (CC=108) indicates too many decision paths. Extract conditions into helper methods.
- **Use Polymorphism:** Replace complex if/elif chains with polymorphic dispatch.
- **Simplify Logic:** Refactor boolean logic and conditions for clarity.

---

### 17. High Cyclomatic Complexity - `symbol_driven_ranking.py`

**Priority:** HIGH | **Effort:** MEDIUM

**Problem:** High cyclomatic complexity: 138. This file has 137 decision points (if/for/while/except etc.).

**Rationale:** Complexity of 138 means exponential test combinations. Each reduction matters.

**Strategies:**

- **Extract Methods:** High complexity (CC=138) indicates too many decision paths. Extract conditions into helper methods.
- **Use Polymorphism:** Replace complex if/elif chains with polymorphic dispatch.
- **Simplify Logic:** Refactor boolean logic and conditions for clarity.

---

### 18. High Cyclomatic Complexity - `unified_retrieval.py`

**Priority:** HIGH | **Effort:** MEDIUM

**Problem:** High cyclomatic complexity: 200. This file has 199 decision points (if/for/while/except etc.).

**Rationale:** Complexity of 200 means exponential test combinations. Each reduction matters.

**Strategies:**

- **Extract Methods:** High complexity (CC=200) indicates too many decision paths. Extract conditions into helper methods.
- **Use Polymorphism:** Replace complex if/elif chains with polymorphic dispatch.
- **Simplify Logic:** Refactor boolean logic and conditions for clarity.

---

### 19. High Cyclomatic Complexity - `utils.py`

**Priority:** HIGH | **Effort:** MEDIUM

**Problem:** High cyclomatic complexity: 33. This file has 32 decision points (if/for/while/except etc.).

**Rationale:** Complexity of 33 means exponential test combinations. Each reduction matters.

**Strategies:**

- **Extract Methods:** High complexity (CC=33) indicates too many decision paths. Extract conditions into helper methods.
- **Use Polymorphism:** Replace complex if/elif chains with polymorphic dispatch.
- **Simplify Logic:** Refactor boolean logic and conditions for clarity.

---

### 20. High Cyclomatic Complexity - `onboarding\analyzer.py`

**Priority:** HIGH | **Effort:** MEDIUM

**Problem:** High cyclomatic complexity: 233. This file has 232 decision points (if/for/while/except etc.).

**Rationale:** Complexity of 233 means exponential test combinations. Each reduction matters.

**Strategies:**

- **Extract Methods:** High complexity (CC=233) indicates too many decision paths. Extract conditions into helper methods.
- **Use Polymorphism:** Replace complex if/elif chains with polymorphic dispatch.
- **Simplify Logic:** Refactor boolean logic and conditions for clarity.

---

### 21. High Cyclomatic Complexity - `onboarding\visualization.py`

**Priority:** HIGH | **Effort:** MEDIUM

**Problem:** High cyclomatic complexity: 83. This file has 82 decision points (if/for/while/except etc.).

**Rationale:** Complexity of 83 means exponential test combinations. Each reduction matters.

**Strategies:**

- **Extract Methods:** High complexity (CC=83) indicates too many decision paths. Extract conditions into helper methods.
- **Use Polymorphism:** Replace complex if/elif chains with polymorphic dispatch.
- **Simplify Logic:** Refactor boolean logic and conditions for clarity.

---

### 22. Change Hotspot - `app.py`

**Priority:** HIGH | **Effort:** HIGH

**Problem:** File is a change hotspot: complex (145 CC), large (748 LOC), and tightly coupled (11 dependencies).

**Rationale:** Hotspots accumulate bugs and become resistant to change.

**Strategies:**

- **Stabilize Through Refactoring:** Reduce hotspot risk by addressing root causes.
- **Isolate Volatile Code:** Separate stable and changing code.
- **Improve Test Coverage:** Add tests to hotspot to reduce change risks.

---

### 23. Change Hotspot - `unified_retrieval.py`

**Priority:** HIGH | **Effort:** HIGH

**Problem:** File is a change hotspot: complex (200 CC), large (802 LOC), and tightly coupled (5 dependencies).

**Rationale:** Hotspots accumulate bugs and become resistant to change.

**Strategies:**

- **Stabilize Through Refactoring:** Reduce hotspot risk by addressing root causes.
- **Isolate Volatile Code:** Separate stable and changing code.
- **Improve Test Coverage:** Add tests to hotspot to reduce change risks.

---

### 24. Change Hotspot - `symbol_driven_ranking.py`

**Priority:** HIGH | **Effort:** HIGH

**Problem:** File is a change hotspot: complex (138 CC), large (659 LOC), and tightly coupled (4 dependencies).

**Rationale:** Hotspots accumulate bugs and become resistant to change.

**Strategies:**

- **Stabilize Through Refactoring:** Reduce hotspot risk by addressing root causes.
- **Isolate Volatile Code:** Separate stable and changing code.
- **Improve Test Coverage:** Add tests to hotspot to reduce change risks.

---

### 25. Change Hotspot - `query_understanding.py`

**Priority:** HIGH | **Effort:** HIGH

**Problem:** File is a change hotspot: complex (138 CC), large (644 LOC), and tightly coupled (3 dependencies).

**Rationale:** Hotspots accumulate bugs and become resistant to change.

**Strategies:**

- **Stabilize Through Refactoring:** Reduce hotspot risk by addressing root causes.
- **Isolate Volatile Code:** Separate stable and changing code.
- **Improve Test Coverage:** Add tests to hotspot to reduce change risks.

---

### 26. Change Hotspot - `retrieval.py`

**Priority:** HIGH | **Effort:** HIGH

**Problem:** File is a change hotspot: complex (108 CC), large (406 LOC), and tightly coupled (5 dependencies).

**Rationale:** Hotspots accumulate bugs and become resistant to change.

**Strategies:**

- **Stabilize Through Refactoring:** Reduce hotspot risk by addressing root causes.
- **Isolate Volatile Code:** Separate stable and changing code.
- **Improve Test Coverage:** Add tests to hotspot to reduce change risks.

---

### 27. Tight Coupling - `app.py`

**Priority:** MEDIUM | **Effort:** HIGH

**Problem:** File depends on too many other modules (11 dependencies). Average is 4 dependencies.

**Rationale:** Too many dependencies (11) create fragility and test complexity.

**Strategies:**

- **Extract Interface/Abstract Class:** Reduce direct dependencies (11) by introducing abstractions.
- **Apply Dependency Injection:** Reduce coupling by injecting dependencies rather than importing directly.
- **Reorganize Module Structure:** Reduce dependencies by changing module organization.

---

### 28. Tight Coupling - `cache.py`

**Priority:** MEDIUM | **Effort:** HIGH

**Problem:** File depends on too many other modules (11 dependencies). Average is 4 dependencies.

**Rationale:** Too many dependencies (11) create fragility and test complexity.

**Strategies:**

- **Extract Interface/Abstract Class:** Reduce direct dependencies (11) by introducing abstractions.
- **Apply Dependency Injection:** Reduce coupling by injecting dependencies rather than importing directly.
- **Reorganize Module Structure:** Reduce dependencies by changing module organization.

---

### 29. Orphaned File - `onboarding\analyzer.py`

**Priority:** LOW | **Effort:** LOW

**Problem:** File is isolated with no imports and not imported by any other file. May be dead code or incorrectly placed.

**Rationale:** Orphaned files are confusing and hard to maintain.

**Strategies:**

- **Remove Orphaned File:** Delete isolated files that serve no purpose.
- **Integrate Into Existing Module:** Move orphaned content into a related, active module.
- **Establish Connections:** If the file serves a purpose, establish its role.

---

