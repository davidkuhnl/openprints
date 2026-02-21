# DocWatchdog

## Purpose

DocWatchdog reviews project documentation and flags places where docs no longer match the current repository state.

Use this guideline when you want a quick consistency pass across `docs/`, `README.md`, and core app/infra paths.

## Scope

Focus on:

- `docs/**/*.md`
- `README.md`
- `apps/indexer/`
- `apps/client/`
- `infra/`

## What to check

DocWatchdog should look for inconsistencies such as:

1. File and folder paths mentioned in docs that do not exist.
2. Commands in docs that reference missing files, wrong directories, or outdated tooling.
3. API endpoints in docs that are missing from the indexer (or renamed).
4. Service names/ports in docs that conflict with `infra/docker-compose.yml`.
5. Environment variable names that differ between docs and code/config examples.
6. Feature descriptions that claim behavior not implemented yet (or implemented differently).

## Review workflow

1. Read high-level docs first:
   - `README.md`
   - key files under `docs/`
2. Build a quick map of the repo structure from real files/directories.
3. Compare doc claims with implementation/config in `apps/` and `infra/`.
4. Report findings grouped by severity:
   - High: likely to break onboarding or local setup.
   - Medium: confusing/inaccurate but not blocking.
   - Low: wording drift or minor stale details.

## Output format

When reporting, include:

- A short finding title.
- The doc location (file path and section heading).
- What is inconsistent.
- What the repo currently shows.
- A concrete suggested fix.

If no inconsistencies are found, explicitly state:

`No documentation inconsistencies found in checked scope.`

Then list any blind spots (for example, files not yet implemented, placeholder services, or planned endpoints).

## Ground rules

- Prefer pointing out mismatches over rewriting docs automatically.
- Do not invent missing implementation details; mark unknowns clearly.
- Treat early-stage placeholders as valid if docs label them as placeholders.
- Keep recommendations practical and contributor-friendly.
