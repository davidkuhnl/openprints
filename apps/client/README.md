# OpenPrints Client

Web frontend for [OpenPrints](https://github.com/davidkuhnl/openprints)—browse and (later) publish 3D-printable designs. Built with **Astro** and **Tailwind CSS**.

Part of the OpenPrints monorepo. For project overview, architecture, and full local setup (relay + indexer + client), see the [root README](../../README.md) and [Development Setup](../../docs/dev-setup.md).

## Quick start

```bash
npm install
npm run dev
```

Dev server: **http://localhost:4321**

| Command           | Action                    |
| ----------------- | ------------------------- |
| `npm run dev`     | Start dev server          |
| `npm run build`   | Production build → `dist/` |
| `npm run preview` | Preview production build  |
| `npm run format`  | Format with Prettier      |

To run the full stack (relay, indexer, client), use the [repo root setup](../../README.md#local-development-setup).

## License

Same as the repository: [AGPL-3.0](../../LICENSE).
