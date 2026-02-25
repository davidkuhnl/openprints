# OpenPrints

**OpenPrints** is an open-source, decentralized ecosystem for discovering, publishing, and monetizing **3D-printable designs** on the **Nostr protocol** with **Lightning zaps**. Creators publish designs as Nostr events; a community-run indexer aggregates them; a thin client lets anyone browse, endorse, and support creators—no central authority or platform lock-in.

Read more about the problem, approach, and our vision in [docs/vision-statement.md](docs/vision-statement.md).


## Quick start

From the repo root:

```bash
make setup
docker compose up
```

This brings up the local Nostr relay, indexer, and (with a bit of config) the Astro client. **Full instructions**, prerequisites, and all `make`/CLI details are in [Development Setup](docs/dev-setup.md).

Quality checks: `make lint`, `make test`, `make check`. See [docs/dev-setup.md](docs/dev-setup.md) for the full list.

## State of the Union (2026-02-25)

### Deploy
- client: live on https://openprints.dev/ via CF talking to the indexer api via a secure tunnel
- indexer: limping on my trusty old raspberry pi

### Roadmap

- [x] Phase 0 — Vision, Repo Setup, Plumbing, Docs
- [x] Phase 1 — Event Handling CLI
- [x] Phase 2 — Indexer Core (Relay Subscriptions + Reducer + DB)
- [x] Phase 3 — REST API
- [x] Phase 4 — Client MVP (List + Detail Pages + search)
- [ ] WIP Phase 5 — Design Publishing Flow
- [ ] Phase 6 — Endorsements ("I printed this")
- [ ] Phase 7 — Lightning Zaps
- [ ] Phase 8 — File Storage Support
- [ ] Phase 9 — Announcement Notes
- [ ] Phase 99 — Catchall (distant future)

Full roadmap and refactor backlog: [docs/roadmap.md](docs/roadmap.md).

## Documentation

| Doc | Description |
|-----|-------------|
| [docs/vision-statement.md](docs/vision-statement.md) | Problem, approach, and vision |
| [docs/dev-setup.md](docs/dev-setup.md) | Prerequisites, clone, `make setup`, relay/indexer/client, CLI reference |
| [docs/architecture.md](docs/architecture.md) | Components, event flow, tech choices |
| [docs/event-schema.md](docs/event-schema.md) | Nostr event kinds and tags (designs, endorsements, zaps) |
| [docs/roadmap.md](docs/roadmap.md) | Development roadmap (phases 0–10) and refactor backlog |

## Repo layout

```
openprints/
  apps/
    indexer/   # Python + FastAPI, CLI, indexer, REST API
    client/    # Astro frontend
  docs/
  infra/       # docker-compose, relay config
  scripts/     # setup, test-drive, etc.
```

## Contributing & License

- [CONTRIBUTING.md](CONTRIBUTING.md) — contribution guidelines  
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) — community standards  
- [SECURITY.md](SECURITY.md) — security and contact  
- [AGPL-3.0](LICENSE)
