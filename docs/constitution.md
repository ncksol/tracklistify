# Nick's Project Constitution

## Core Principles

### I. Simplicity First
YAGNI religiously. No abstractions until the second use case demands them. Prefer flat structures over nested hierarchies. If a junior dev couldn't understand the code in 5 minutes, it's too complex.

**Gates:**
- No more than 3 levels of directory nesting without justification
- No abstract base classes, factories, or strategy patterns unless two concrete implementations already exist
- Functions over classes when state isn't needed
- If you're writing a "utils" file, stop and rethink

### II. Security by Default
Never store secrets in code. Sanitise all user input. HTTPS everywhere. Principle of least privilege for all services and APIs. Dependencies must be actively maintained (no abandoned packages).

**Gates:**
- Zero hardcoded secrets, tokens, or credentials in source — environment variables or secret managers only
- All user input validated and sanitised at the boundary (entry points)
- All external communication over TLS
- Service accounts and API keys scoped to minimum required permissions
- No dependency with last publish > 2 years or known unpatched CVEs

### III. Type Safety & Linting
Strict types always (TypeScript strict, Python type hints, etc.). Linter and formatter configured from day one, zero warnings policy. Types are documentation.

**Gates:**
- TypeScript: `strict: true` in tsconfig (no `any` without explicit justification)
- Python: type hints on all function signatures, mypy/pyright in CI
- Linter + formatter configured in Phase 1 Setup — not optional
- Zero warnings in CI. Warnings are errors.

### IV. Test What Matters
No TDD mandate, but critical paths must have tests: auth flows, data mutations, payment/billing logic, anything that touches user data. Integration tests over unit tests. Don't test getters.

**Gates:**
- Auth/login flows: must have integration tests
- Data mutations (create, update, delete): must have tests
- Payment/billing logic: must have tests with edge cases
- User data handling: must have tests
- Pure display/formatting: tests optional
- Prefer integration tests that exercise real paths over isolated unit tests

### V. Ship Fast, Fix Fast
MVP is one user story. Deploy early, iterate. Feature flags over long-lived branches. Monitoring and error tracking from day one — you can't fix what you can't see.

**Gates:**
- MVP scope = User Story 1 (P1) only. Resist scope creep.
- Error tracking/monitoring configured in Phase 1 Setup
- No feature branch lives longer than 1 week
- If it works for one user (you), ship it

### VI. Minimal Dependencies
Every dependency is a liability. Prefer standard library. When adding a package, it must solve a real problem you've already hit (not a hypothetical one). Pin versions.

**Gates:**
- Before adding a dependency: can this be done in ≤50 lines with stdlib? If yes, do that.
- All dependency versions pinned (exact, not ranges)
- Each dependency must be justified in plan.md or research.md
- Audit: check download stats, maintenance activity, bundle size impact

### VII. Documentation as Code
README that explains how to run the project in under 2 minutes. Inline comments for WHY, not WHAT. API contracts are the documentation.

**Gates:**
- README must contain: what it does (1 sentence), how to run it (copy-pasteable commands), environment requirements
- No comment that restates what the code does (`// increment counter` → delete it)
- Comments explain WHY a non-obvious decision was made
- API contracts (OpenAPI/GraphQL schema) serve as the API documentation — no separate API docs

## Development Workflow

### Solo Developer Process
- No code review gates (you're the reviewer)
- Commit after each completed task or logical unit
- Main branch is always deployable
- Use conventional commits for clarity when you come back in 6 months

### Quality Gates (Automated)
- Linter + formatter must pass before commit (pre-commit hook or CI)
- Type checker must pass
- Critical path tests must pass
- No secrets in committed files (use git-secrets or similar)

### When to Break the Rules
Any principle can be violated if:
1. The violation is documented (in plan.md or code comment)
2. The justification explains why the simpler approach doesn't work
3. It's tracked in Complexity Tracking in plan.md

## Governance

This constitution applies to all projects created via `#speckit`. It guides `/plan` gate checks and `/tasks` structure. Principles are checked twice during planning: before research (Phase 0) and after design (Phase 1).

Amendments: just tell Jarvis to update it. No ceremony needed — you're the sole stakeholder.

**Version**: 1.0 | **Ratified**: 2026-02-16 | **Last Amended**: 2026-02-16
