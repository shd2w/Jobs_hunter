# Universal Standards

**Version:** 1.0  
**Authority:** Supplements the Engineering Constitution with detailed operational standards.

---

## 1. Code quality standards

### 1.1 General

- All code must be syntactically valid and free of obvious errors before commit.
- Follow the project's established style, naming conventions, and patterns.
- Do not introduce new patterns, abstractions, or architectural layers without project approval.
- Keep changes minimal and focused on the assigned scope.
- Preserve existing comments, docstrings, and documentation unrelated to the change.

### 1.2 Dependencies

- Do not add packages, tools, services, or external integrations unless:
  - project policy explicitly permits them; OR
  - the owner approves the addition in the current task.
- Record all new dependencies in the project's dependency manifest.
- Justify each new dependency with a concrete need that cannot be met by existing project code or dependencies.

### 1.3 Error handling

- Handle errors explicitly; do not silently swallow exceptions.
- Preserve existing error handling contracts unless the task specifically requires changing them.
- Log errors with sufficient context for diagnosis.
- Do not convert exceptions, unavailable services, or missing data into fake success responses.

### 1.4 Security

- Never hard-code credentials, API keys, tokens, or secrets in source code.
- Follow the project's data classification and security rules.
- Validate and sanitize untrusted input.
- Do not weaken existing security controls without explicit owner approval.
- Do not send sensitive data to external services without approval.

---

## 2. Testing standards

### 2.1 Baseline requirement

Before modifying any code, run the existing test suite and record:
- total tests, passed, failed, skipped, errored;
- exact command used;
- platform and environment details;
- pre-existing failures (classified as known issues).

### 2.2 Test-first for defects

When fixing a defect:
1. Write a regression test that reproduces the defect (shows the old/broken behavior).
2. Verify the test fails before the fix.
3. Apply the fix.
4. Verify the test passes after the fix.
5. Verify all other tests still pass.

If writing a regression test first is impractical, document why and add the test alongside the fix.

### 2.3 Test-with for features

When adding a new feature:
1. Define acceptance criteria before implementation.
2. Add acceptance tests before or alongside implementation.
3. Verify all new tests pass.
4. Verify all existing tests still pass.

### 2.4 Post-change validation

After every logical implementation increment:
- run narrow tests covering the change;
- after all changes are complete, run the full applicable test suite;
- record results with the same detail as the baseline.

### 2.5 Test classification

Tests must be accurately classified:

| Type | Scope | When required |
|---|---|---|
| Unit | Single function/method/class in isolation | Every code change |
| Integration | Multiple components interacting | Cross-component changes |
| End-to-end | Full user workflow | User-facing feature changes |
| Regression | Previously broken behavior | Every defect fix |
| Smoke | Basic application health | Every task completion |
| Browser/UI | Visual and interactive verification | UI-affecting changes |

---

## 3. Commit standards

### 3.1 Message format

```
<type>(<scope>): <short description>

[optional body with details]

Task: <task-id>
```

Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `style`, `perf`, `ci`, `build`.

Where the project defines its own commit convention it takes precedence (stricter-wins, constitution 1.4). JobHunter: the message starts with the work-package id (GOV-06 section 2, `commit_prefix` in `CONFIG/project_profile.yml`).

### 3.2 Commit discipline

- Each commit should represent one logical change.
- Do not mix unrelated changes in a single commit.
- Do not commit broken code that fails basic checks.
- Include task identifiers in every commit message.
- Keep commits small enough for meaningful review.

---

## 4. Review standards

### 4.1 Independence requirement

Review must occur in a separate context from implementation. The reviewer must not rely on the implementer's self-assessment. A different model or model family is preferred where available, but separate-context independence is the minimum requirement.

### 4.2 Review scope

The reviewer checks:
1. **Scope:** changes match the assigned task and do not exceed it.
2. **Correctness:** logic, edge cases, error handling, and data flow.
3. **Architecture:** compliance with project invariants and boundaries.
4. **Security:** no new vulnerabilities, credential exposure, or weakened controls.
5. **Tests:** adequate coverage, correct assertions, no false passes.
6. **UI/UX:** visual correctness, responsiveness, accessibility (for UI changes).
7. **Documentation:** registry, feature docs, and memory are current.
8. **Evidence:** completion claims are supported by recorded evidence.
9. **Side effects:** no unintended changes to unrelated functionality.

### 4.3 Review findings

Findings are recorded with:
- severity: `critical`, `major`, `minor`, `suggestion`;
- file and line reference;
- description of the issue;
- required evidence or action to resolve.

Critical and major findings must be resolved before merge. Minor findings and suggestions may be deferred with owner approval.

---

## 5. Documentation standards

### 5.1 File registry

Every maintained source file must have an entry in `FILE_REGISTRY.yml`. The entry records purpose, responsibility, component, dependencies, security classification, and related tests.

### 5.2 Feature documentation

Every user-facing or system-level feature has a feature document covering purpose, workflows, acceptance criteria, UI states, API contracts, architecture, security, tests, and known limitations.

### 5.3 Synchronization

Documentation must be updated in the same task that changes behavior. A task cannot close with stale documentation.

---

## 6. Platform portability

### 6.1 Path handling

- Use repository-relative paths in all framework files.
- Normalize path separators for cross-platform compatibility.
- Do not hard-code drive letters, absolute paths, or shell-specific syntax.

### 6.2 Commands

- Store project commands in configuration files, not hard-coded in instructions.
- Provide both PowerShell and shell variants where needed.
- Test exit codes, encoding, and line endings on each supported platform.

### 6.3 Scripts

- Prefer Python (standard library) for cross-platform framework scripts.
- Provide PowerShell entry points for Windows and shell entry points for Unix.
- Do not assume a specific shell is available.

