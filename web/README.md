# AutoBSgenome Web

This is the AutoBSgenome frontend, built with TanStack Start, Vite, Nitro, React,
and Tailwind CSS.

The package builder API is intentionally kept in the sibling `worker/` project.
The web app calls `https://api.autobsgenome.org` through shared config in
`src/config/site.ts`.

## Development

```bash
npm install
npm run dev
```

Open `http://localhost:3000`.

## Project Structure

- `src/routes/` contains TanStack file routes.
- `src/features/` contains page-level feature modules.
- `src/components/` contains shared UI and shell components.
- `src/config/` contains public site/API/repository configuration.
- `src/styles/globals.css` contains Tailwind and design tokens.

## Build

```bash
npm run build
npm run cf:build
```

`npm run build` creates a local TanStack/Nitro build. `npm run cf:build` builds
for Cloudflare Workers using `NITRO_PRESET=cloudflare_module`.

## Deploy

Deployment uses `wrangler deploy` with `wrangler.jsonc`. Static assets are served
from `.output/public`, and the Worker server entry is `.output/server/index.mjs`.
The current Worker name is `autobsgenome-web-staging`; production cutover for
`autobsgenome.org` should be done separately after the staging build is reviewed.
