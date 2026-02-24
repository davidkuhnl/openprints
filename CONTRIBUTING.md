# Contributing to OpenPrints

Thanks for your interest in contributing to OpenPrints! This is a small, open-source, bootstrapped project that is just getting started.

Before doing any substantial work, **please reach out first** so we can align on priorities and approach:

- Open an issue describing your idea, or
- Email `openprints@pm.me` with what you’d like to work on.

Help of all kinds is appreciated — from bug reports and docs fixes to new features and protocol work.

Before you start, please read our:

- `CODE_OF_CONDUCT.md` for community expectations
- `SECURITY.md` for how to report security issues

---

## Ways to Contribute

- **Use the project** and file issues for bugs, rough edges, or confusing behavior
- **Improve docs** (README, dev setup, architecture notes, comments)
- **Tackle small refactors** or TODOs
- **Work on roadmap items** (client, indexer, protocol features) after some discussion

If you're not sure where to start, look at:

- The roadmap in `README.md`
- The refactor backlog in `README.md`
- Open issues tagged as good first issues (when available)

---

## Getting Set Up

From a fresh clone, the recommended path is:

```bash
make setup
```

This runs the bootstrap script (`scripts/setup.sh`) and installs dependencies and pre-commit hooks.

For more detail, see:

- `README.md` (project overview and roadmap)
- `docs/dev-setup.md` (local dev environment, relay, indexer, and CLI)

---

## Running Checks

Before opening a pull request, please make sure:

- Tests and linters pass locally:

```bash
make check
```

This typically runs formatting, linting, type checks, and tests for the indexer/CLI. CI will run similar checks on your PR.

---

## Pull Requests

Because the project is new and the architecture is still evolving, we prefer to **discuss contributions before you start coding** (see above).

Once we’ve aligned on a change:

1. **Fork** the repository (or use a branch if you have direct access).
2. Create a branch for your change.
3. Make your edits, keeping commits reasonably small and focused.
4. Run `make check` and fix any issues.
5. Open a pull request with:
   - A clear description of the change and motivation
   - Any relevant screenshots or logs (especially for UI changes)
   - Notes about breaking changes, if any

Guidelines:

- Prefer **small, focused PRs** over large, multi-purpose ones.
- For significant feature work or protocol changes, please open an issue or discussion first so we can align on approach.

---

## Style and Design Notes

- **Python (indexer/CLI)**: follow the existing style and rely on configured tools (e.g. `ruff`, formatters) via `make check`.
- **Client (Astro/React)**: prefer simple, accessible components and keep protocol logic in shared helpers rather than views when practical.
- Avoid introducing new dependencies unless they provide clear, long-term value.

If you're unsure about design or structure, feel free to ask in an issue or PR — explaining your tradeoffs in the description is very helpful.

---

## Community and Contact

- **Code of Conduct**: see `CODE_OF_CONDUCT.md`
- **Security Reports**: see `SECURITY.md` (`openprints@pm.me`)

For general questions or ideas, opening an issue is usually the best way to start the conversation.

Thanks again for helping improve OpenPrints.

