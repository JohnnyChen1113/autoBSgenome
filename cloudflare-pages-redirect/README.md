# AutoBSgenome Pages Redirect

This directory is deployed to the legacy Cloudflare Pages project that serves
`autobsgenome.pages.dev`.

The canonical web app now runs on Cloudflare Workers at:

https://autobsgenome.org

Keep this Pages deployment redirect-only so users, crawlers, and older links do
not land on the stale pre-migration Pages/Next.js build.

Deploy with:

```sh
npx wrangler pages deploy cloudflare-pages-redirect --project-name autobsgenome
```
