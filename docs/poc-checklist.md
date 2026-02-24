## OpenPrints PoC + OpenSats Checklist

> Temporary working checklist for getting to a public PoC and a draft OpenSats application.

**Current state:** Phases 0–3 done (vision/repo/plumbing, Event Handling CLI, Indexer Core, REST API with `GET /designs`, `GET /designs/stats`, `GET /designs/{id}`). Rudimentary Astro client and marketing/landing page in `apps/client`; list/detail pages not yet wired to API. LICENSE, CONTRIBUTING, CODE_OF_CONDUCT, SECURITY at repo root. README cleaned up with State of the Union and phase list; vision, roadmap, dev-setup, architecture, event-schema in `docs/`. `docs/README-backup.md` removed (redundant with other docs).

---

### 1. Client MVP (List + Detail)

- [ ] **Bootstrap client** _(marketing/landing page in place; list + detail not yet)_
  - [x] Initialize Astro project structure in `apps/client`
  - [x] Add basic layout, navigation, and logo
  - [x] Add simple styling and mobile-friendly layout
- [ ] **List page**
  - [ ] Configure API base URL via env/config (e.g. `OPENPRINTS_API_BASE_URL`)
  - [ ] Call `GET /designs` from the indexer API
  - [ ] Render a list of design cards (title, creator/pubkey, date, category)
  - [ ] Handle empty/loading/error states gracefully
- [ ] **Detail page**
  - [ ] Route by opaque design id (from list `items[].id`)
  - [ ] Call `GET /designs/{id}` to fetch full metadata
  - [ ] Show key fields (name, format, sha256, url, license, preview if present)
  - [ ] Include a clear “Download file” link/button
- [ ] **End-to-end demo**
  - [ ] Ensure `make test-drive` (or equivalent) populates designs that appear in the client
  - [ ] Document in README: “how to run the PoC” (commands + URLs)

---

### 2. Indexer + CLI PoC Flow

- [ ] **CLI publish flow**
  - [ ] Verify `build -> sign -> publish` works against the PoC relay from a fresh clone
  - [ ] Confirm `make` shortcuts (`make cli-build`, `make cli-sign`, `make cli-publish`) are documented and accurate
  - [ ] Show a minimal example in docs using a stub STL/hash
- [ ] **Indexer integration**
  - [ ] Confirm published designs appear in DB (`make cli-db-stats`)
  - [ ] Confirm the same designs appear via `GET /designs` and `GET /designs/{id}`
  - [ ] Confirm the client list/detail shows those designs without manual DB edits

---

### 3. “Public Repo” Polish

- [ ] **Licensing & policies**
  - [x] Choose and add LICENSE file (AGPL-3.0)
  - [x] Add `CONTRIBUTING.md` with simple contribution guidelines
  - [x] Add `CODE_OF_CONDUCT.md` (short, standard template is fine)
  - [x] Add `SECURITY.md` or clearly documented security/contact section
- [x] **Docs cleanup**
  - [x] Update `README.md` to clearly state:
    - [x] What currently works (PoC scope)
    - [x] How to run the PoC (CLI + client + relay/indexer)
    - [x] What’s planned next (link to roadmap phases)
  - [x] Ensure `docs/dev-setup.md` matches the actual setup from a fresh clone
  - [ ] Add a short “Architecture overview” section (or link) for reviewers
- [ ] **Repo hygiene**
  - [ ] Remove or update stale TODOs that would confuse new readers
  - [ ] Ensure `make setup`, `make check`, and CI all pass

---

### 4. Minimal “Prod-ish” Deployment

- [ ] **Indexer deployment**
  - [ ] Deploy indexer (FastAPI) to a simple host (VPS / Fly / Render / Railway, etc.)
  - [ ] Expose it under `https://api.openprints.dev` (DNS or Cloudflare Tunnel)
  - [ ] Verify health/readiness endpoints and `GET /designs` work externally
- [ ] **Client on Cloudflare Pages**
  - [ ] Configure Astro build for Cloudflare Pages
  - [ ] Point client to `https://api.openprints.dev` via env/config
  - [ ] Attach `openprints.dev` or `app.openprints.dev` to the client Pages project
- [ ] **Deployment docs**
  - [ ] Add a short doc or section describing the PoC deployment layout:
    - [ ] Where the relay runs
    - [ ] Where the indexer/API runs
    - [ ] Where the client runs

---

### 5. OpenSats Grant Application Prep

- [ ] **Narrative**
  - [ ] Write 1–2 pages covering:
    - [ ] Problem: closed/centralized 3D design marketplaces and creator lock-in
    - [ ] Solution: OpenPrints using Nostr events + Lightning zaps + open indexer/client
    - [ ] Why now, and why you/this project
- [x] **Milestones & timeline**
  - [x] Turn roadmap Phases 4–10 into milestones with:
    - [x] Scope/feature description
    - [x] Success criteria
    - [ ] Rough timeline per phase (grant notes in this doc; formal timeline TBD)
  - [x] Clearly mark Phases 0–3 as “already implemented / PoC basis”
- [ ] **Budget & sustainability**
  - [ ] Draft a budget tied to milestones (dev time, infra costs, etc.)
  - [ ] Add a short section on openness/governance and how the project remains neutral
- [ ] **Artifacts for reviewers**
  - [ ] Capture a few up-to-date screenshots of the PoC client
  - [ ] (Optional) Record a short walkthrough video and link it from docs/application

---

### Grant scope & timeline — discussion notes

Notes from internal discussion on what to commit to for a **3‑month grant** (single contributor, OpenSats or similar).

**Commit to (core deliverable):** **Phases 4, 5, and 6** over 3 months.

- **Phase 4** (Client MVP): list + detail pages, API wiring, empty/loading/error states. ~2–3 weeks.
- **Phase 5** (Publish from client): metadata + URL form, build event, sign in browser (NIP-07 / Nostr Connect), publish to relay(s). ~3–4 weeks (browser signing is the main variable).
- **Phase 6** (Endorsements): indexer 33311, reducer, API, client “I printed this” + counts. ~2–3 weeks.

Total ~8–10 weeks of focused work; 2–4 weeks buffer for integration, polish, docs. **Doable in 12 weeks.**

**Tangible benefit for community:** Full loop — discover designs (4), publish your own (5), endorse others (6). No CLI required; open, non-custodial pipeline. Clear value: “usable by the community.”

**How to phrase in the application:**
- By end of month 3: Phases 4, 5, 6 delivered (browse, publish, endorse).
- Stretch only (do not promise): Phase 7 (Lightning zaps) if time permits.
- Milestones: e.g. Month 1 → Phase 4 done; Month 2 → Phase 5 done; Month 3 → Phase 6 done.

**Out of scope for this grant (keep 3 months credible):** Phase 8 (file storage), Phase 9 (announcement notes), Phase 99 (catchall). List as “next steps after grant,” not as committed deliverables.

**Roadmap gaps for grant applications (in general):**
- Add explicit **milestone dates** and **budget** (person-time, rate, infra).
- Keep Phase 99 as “future vision”; don’t promise it in the grant.
- Consider narrowing Phase 8 to one backend (or defer) if storage is ever in scope.
- Add 1–2 **impact metrics** if the grant asks (e.g. “N designs published in first 6 months,” “N endorsements”).

---

### 6. Nice-to-haves (If Time Allows)

- [ ] Add a few FastAPI tests for `GET /health`, `GET /designs`, `GET /designs/{id}`
- [ ] Add a minimal browser smoke test for the client list/detail pages
- [ ] Add a “Future work” section to docs summarizing endorsements, zaps, Blossom support, and announcement notes

