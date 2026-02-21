# OpenPrints

**OpenPrints** is an open-source, decentralized platform for discovering, publishing, and monetizing **3D-printable designs** using the **Nostr protocol** and **Lightning zaps**.  
The goal is to create a censorship-resistant, creator-owned ecosystem for 3D models, where designs are portable, events are verifiable, and monetization is peer-to-peer.

This document defines the project intent, long-term architecture, and initial development roadmap.

---

## Table of Contents

- [Overview](#overview)
- [Goals](#goals)
- [Architecture](#architecture)
  - [Core Components](#core-components)
  - [Event Flow](#event-flow)
- [Nostr Event Schema](#nostr-event-schema)
  - [Design Listing — kind 33001](#design-listing--kind-33001)
  - [Endorsement — kind-33002](#endorsement--kind-33002)
  - [Zap Receipts — kind-9735](#zap-receipts--kind-9735)
- [Technology Choices](#technology-choices)
- [Repository Structure](#repository-structure)
- [Development Roadmap](#development-roadmap)
- [Local Development Setup](#local-development-setup)
- [Domains & Branding](#domains--branding)
- [License](#license)

---

# Overview

**OpenPrints** re-imagines a 3D design marketplace as an open protocol layer:

- Creators publish designs as **Nostr events**  
- Ownership is tied to their **Nostr keypair**  
- Metadata describes the design (file hash, material, printer, license…)  
- Files are hosted on **simple storage** (R2/S3/minio) or **Blossom**  
- Monetization happens through **Lightning zaps** directly to the creator  
- A community-run **indexer** aggregates the public Nostr data  
- A lightweight **UI client** lets users explore, rate, and support creators  

There is no central authority, no lock-in, no platform control — just a protocol-driven ecosystem for sharing 3D-printable models.

---

# Goals

### ✔ Open, permissionless publishing of 3D-printable designs  
### ✔ Portable ownership via Nostr keys  
### ✔ Direct creator monetization via Lightning  
### ✔ Open-source indexer for search, ranking, and aggregation  
### ✔ Thin, fast UI built on modern web tools  
### ✔ Optional decentralized blob storage (Blossom)  
### ✔ Community-driven, censorship-resistant design  

---

# Architecture

## Core Components

### **1. OpenPrints Client (Astro + React Islands)**
- Browse designs (SSR for SEO + speed)
- View details and previews
- Publish new designs (NIP-07 signing)
- Endorse prints (“I printed this”)
- Send Lightning zaps to creators

### **2. OpenPrints Indexer (Python + FastAPI)**
- Connects to multiple Nostr relays
- Subscribes to design/endorsement/zap events
- Reduces and stores events into SQLite/Postgres
- Exposes REST API for filtering & search

### **3. Storage**
- MVP: traditional object storage (R2/S3/minio)
- Later: optional Blossom blob server uploads for decentralized hosting

### **4. Dev Relay**
- Repo includes a dockerized Nostr relay for local development

---

## Event Flow

1. User fills "Create Design" form in UI  
2. Client uploads file → computes sha256 → gets URL  
3. Client constructs a `33001` Nostr event  
4. NIP-07 signs event  
5. Event is broadcast to relays  
6. Indexer receives event from relays, reduces it into DB  
7. UI fetches design info from indexer’s REST API  
8. Optional: indexer posts a `kind:1` announcement note

---

# Nostr Event Schema

## **Design Listing — kind 33001**
Parameterized replaceable: newest `created_at` wins per (`pubkey`, `d` tag).

**Required tags:**
```
["d", "<design_id>"]
["name", "Phone Stand"]
["format", "stl|3mf"]
["sha256", "<sha256-hash>"]
["url", "https://.../file.stl"]
```

**Recommended tags:**

```
["category", "holder"]
["material", "PLA,PETG"]
["printer", "Prusa MK4"]
["license", "CC-BY-4.0"]
["preview", "https://.../preview.png"]
["lnurl", "lnurlp://creator-address"]
["m", "<mime-type>"]
```


---

## **Endorsement — kind 33002**
Append-only “I printed this” events.

```
["e", "<design-event-id>"]
["rating", "1..5"]
["material", "PETG"]
["printer", "Prusa MK4"]
```

Content may contain a short review.

---

## **Zap Receipts — kind 9735**
Optional indexing for:
- total sats per design  
- trending designs  
- recent activity feed  

---

# Technology Choices

### **Backend (Indexer)**
- Python 3.11+
- FastAPI
- asyncio + WebSockets
- SQLAlchemy / SQLite (dev) / Postgres (prod)
- `python-nostr` or raw websocket handling

### **Frontend (Client)**
- Astro (SSR)
- React islands for interactive flows
- Tailwind optional

### **Storage**
- MVP: simple HTTP/S3/R2 storage
- Optional: Blossom blob servers (NIP-B7 support later)

### **Infrastructure**
- Docker Compose development environment
- Included local Nostr relay

---

# Repository Structure
```
openprints/
  README.md
  docs/
    event-schema.md
    architecture.md
    dev-setup.md
  infra/
    docker-compose.yml
    nostr-relay.config.toml
  apps/
    indexer/     # Python + FastAPI + asyncio + DB
    client/      # Astro + React islands
  packages/
    shared/      # optional shared helpers/types
```


---

# Development Roadmap

Legend: `[x]` done, `[~]` current, `[>]` next, `[ ]` upcoming, `[!]` blocked

Current Phase: **Phase 0 - Repo + Docs Setup**

Next Phase: **Phase 1 - Event Publishing Test Harness**

- `[~]` Phase 0 - Repo + Docs Setup
- `[>]` Phase 1 - Event Publishing Test Harness
- `[ ]` Phase 2 - Indexer Core (Relay Subscriptions + Reducer + DB)
- `[ ]` Phase 3 - REST API
- `[ ]` Phase 4 - Client MVP (List + Detail Pages)
- `[ ]` Phase 5 - Design Publishing Flow
- `[ ]` Phase 6 - Endorsements ("I printed this")
- `[ ]` Phase 7 - Lightning Zaps
- `[ ]` Phase 8 - Blossom Support
- `[ ]` Phase 9 - Announcement Notes
- `[ ]` Phase 10 - Public Release + OpenSats Grant Application

---

# Local Development Setup

This repository includes a complete local environment:
```
docker compose up
```

Services include:

- Local Nostr relay  
- Indexer (Python)  
- Database (SQLite or Postgres)  
- Astro client (dev mode)  

Detailed instructions live in `docs/dev-setup.md`.

---

# Domains & Branding

- Primary domain: **openprints.dev**  
- Secondary domain: **openprints.app**  
- Repository name: **openprints**  
- Open-source, community-first identity  
- No central ownership or lock-in  

---

# License

**TBD** — likely MIT, BSD, or Apache 2.0.  
OpenPrints will be fully open-source.
