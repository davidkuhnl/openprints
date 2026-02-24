# OpenPrints — Problem & Vision

## Problem

Today’s 3D design ecosystems are **centralized**: a few platforms host most designs, control discovery and monetization, and lock in creators. If a marketplace changes rules, shuts down, or takes a bigger cut, creators have limited recourse. Designs and reputation are tied to the platform, not to the creator. We want a world where 3D-printable designs are **portable**, **verifiable**, and **creator-owned**, with monetization that flows directly to makers instead of intermediaries.

## Approach

OpenPrints reimagines a 3D design marketplace as an **open protocol layer**:

- **Creators** publish designs as **Nostr events**; ownership is tied to their key, not a platform account.
- **Metadata** (file hash, format, license, preview, etc.) lives in the event. Files can sit on simple storage (S3/R2) or, later, decentralized blob storage (Blossom). Storage doesn’t matter—as long as the file is somewhere, it can be found and used. Nostr ties it all together.
- **Events** are standard updatable Nostr events that flow through ordinary relays.
- A **community-run indexer** subscribes to relays, reduces events into a database, and exposes a REST API for search and discovery. Anyone can run one. Multiple flavors of indexers can coexist—as long as the data is on the relays, any indexer can reconstruct the current state of the 3D design universe.
- A **thin client** lets anyone browse designs, endorse prints ("I printed this"), and support creators via **Lightning zaps**—no central custody, no platform cut.
- **Special-purpose Nostr relays** can evolve for this corner of the network: archiving, filtering, analyzing designs—you name it.
- The ecosystem is open and **machine-friendly**; your friendly AI agent can find, purchase, and maybe eventually print you something.
- **No single authority** controls the protocol, the data, or the money flow. Anyone can tap in at any level.

## Impact on Nostr

OpenPrints brings the 3D printing community—people who love a challenge and find joy in finicky machines—to Nostr, a network that’s finicky and challenging. A perfect match.

Hopefully the value-for-value activity from OpenPrints will spill over to other nooks of Nostr and help it grow.


## Goals

- ✔ Open, permissionless publishing of 3D-printable designs
- ✔ Portable ownership via Nostr keys
- ✔ Direct creator monetization via Lightning
- ✔ Open-source indexer for search, ranking, and aggregation
- ✔ Thin, fast UI built on modern web tools
- ✔ Optional decentralized blob storage (Blossom)
- ✔ Community-driven, censorship-resistant design

For architecture, event schema, and roadmap, see the [README](../README.md) and other docs in this folder.
