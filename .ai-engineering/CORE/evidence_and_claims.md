# Evidence and Claims Policy

**Version:** 1.0  
**Authority:** Defines mandatory rules for evidence collection, classification, storage, and claims. Supplements the Engineering Constitution Section 4.

---

## 1. Core rule

**No claim without evidence.** Every assertion that work is complete, a test passes, a feature works, or a gate is satisfied must link to a specific, reproducible piece of evidence stored in the repository.

---

## 2. Evidence requirements by gate type

| Gate | Minimum evidence |
|---|---|
| Unit tests | Command, output, pass/fail counts, coverage if available |
| Integration tests | Command, output, component interactions verified |
| End-to-end tests | Command, output, user workflow steps, screenshots if UI |
| Lint/format/type check | Command, output, clean or itemized violations |
| Security scan | Command, output, findings classified |
| Build/package | Command, output, artifact produced |
| Application startup | Command, output, health check result, port/URL |
| Browser/UI verification | Screenshots at configured viewports, console logs, user workflow steps |
| Documentation check | Registry diff, feature doc diff, consistency check output |
| Independent review | Review report with findings, severity, and verdict |
| Regression test | Before-fix failure evidence AND after-fix pass evidence |

---

## 3. Evidence storage

### 3.1 Location

All task evidence is stored under:

```
.ai-engineering/EVIDENCE/<task-id>/
├── baseline/          # Pre-change state
├── validation/        # Post-change test results
├── browser/           # Screenshots, console logs, network logs
└── review/            # Review reports and findings
```

### 3.2 Naming convention

Evidence files use descriptive names with timestamps:

```
<gate-type>_<description>_<YYYYMMDD-HHmmss>.<ext>
```

Examples:
- `unit-tests_full-suite_20261110-101500.txt`
- `screenshot_dashboard-desktop-1920x1080_20261110-102000.png`
- `review_independent-review-report_20261110-110000.md`

### 3.3 Evidence file content

Each evidence file must include at minimum:
- date and time of execution;
- agent/model/CLI identifier (no secrets);
- exact command or action performed;
- environment details (OS, runtime versions);
- complete output or meaningful excerpt with truncation noted;
- pass/fail verdict with rationale.

---

## 4. Claim semantics

### 4.1 Valid claims

A claim is valid only when:
- it references specific evidence file(s);
- the evidence file exists in the repository;
- the evidence classification accurately reflects the verification level;
- the evidence was produced against the current code (same commit or later).

### 4.2 Invalid claims

The following are **never** valid completion evidence:
- "I tested it and it works" without a recorded test execution.
- A build succeeding as proof a feature works correctly.
- Generated code existing as proof it is correct.
- A previous session's test results when code has changed since.
- Mocked or simulated results labeled as live verification.
- A partially completed test run presented as a full run.
- An agent's confidence or training knowledge about expected behavior.

### 4.3 Stale evidence

Evidence becomes stale when:
- the source code it tested has been modified;
- the configuration it ran against has changed;
- the environment or dependencies have changed materially.

Stale evidence must be refreshed before it supports a completion claim.

---

## 5. Baseline evidence

### 5.1 Purpose

Baseline evidence establishes the pre-change state. It proves:
- what worked before the change (to detect regressions);
- what was already broken (to avoid blame for pre-existing failures);
- the starting point for measuring the task's impact.

### 5.2 Requirements

Baseline evidence must be captured **before any code changes** and must include:
- full test suite results;
- lint/format/type check results if applicable;
- application health status if applicable;
- UI state screenshots if the task affects the UI;
- git status and HEAD commit.

---

## 6. Review evidence

### 6.1 Review reports

A review report must contain:
- reviewer identity (agent/model, not a person's credentials);
- date and commit reviewed;
- scope of review;
- findings with severity, file/line references, and required actions;
- overall verdict: `approved`, `approved-with-conditions`, `changes-required`, or `blocked`;
- evidence that the reviewer independently verified claims rather than accepting the implementer's assertions.

### 6.2 Review independence

The reviewer must demonstrate independence by:
- operating in a separate context from the implementer;
- running at least a subset of the validation checks independently;
- checking the actual code and evidence, not just the implementer's summary.

