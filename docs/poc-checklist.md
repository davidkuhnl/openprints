## OpenPrints PoC + OpenSats Checklist

> Temporary working checklist for getting to a public PoC and a draft OpenSats application.

---

### 1. Client MVP (List + Detail)

- [ ] **Bootstrap client**
  - [ ] Initialize Astro project structure in `apps/client`
  - [ ] Add basic layout, navigation, and logo
  - [ ] Add simple styling and mobile-friendly layout
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
- [ ] **Docs cleanup**
  - [ ] Update `README.md` to clearly state:
    - [ ] What currently works (PoC scope)
    - [ ] How to run the PoC (CLI + client + relay/indexer)
    - [ ] What’s planned next (link to roadmap phases)
  - [ ] Ensure `docs/dev-setup.md` matches the actual setup from a fresh clone
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
- [ ] **Milestones & timeline**
  - [ ] Turn roadmap Phases 4–10 into milestones with:
    - [ ] Scope/feature description
    - [ ] Success criteria
    - [ ] Rough timeline per phase
  - [ ] Clearly mark Phases 0–3 as “already implemented / PoC basis”
- [ ] **Budget & sustainability**
  - [ ] Draft a budget tied to milestones (dev time, infra costs, etc.)
  - [ ] Add a short section on openness/governance and how the project remains neutral
- [ ] **Artifacts for reviewers**
  - [ ] Capture a few up-to-date screenshots of the PoC client
  - [ ] (Optional) Record a short walkthrough video and link it from docs/application

---

### 6. Nice-to-haves (If Time Allows)

- [ ] Add a few FastAPI tests for `GET /health`, `GET /designs`, `GET /designs/{id}`
- [ ] Add a minimal browser smoke test for the client list/detail pages
- [ ] Add a “Future work” section to docs summarizing endorsements, zaps, Blossom support, and announcement notes

