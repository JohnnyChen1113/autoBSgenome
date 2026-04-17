# Alternative Compute Options for autoBSgenome Builds

> Recorded 2026-04-17. Context: Batch-building 3,553 eukaryote BSgenome packages on GitHub Actions. Looking for redundancy/resilience options outside GHA.

## Current setup

- **GitHub Actions** runs `build-bsgenome.yml` per package (1 job ≈ 5-15 min)
- **Batch dispatcher** (`batch-build.yml`) cron every 30 min, fans out via `repository_dispatch`
- **Hard limits**: 20 concurrent jobs (free tier), 2000 min/month per private repo (this repo is public, so unlimited but fair-use applies), 6 hour per-job timeout, 14 days log retention
- **Failure modes seen**: rate limits on `dispatches` API, runner queue saturation when many repos share quota, runner image cold-start latency

---

## Tier 1 — drop-in alternatives (public CI, free for OSS)

### Cirrus CI ⭐⭐⭐⭐
- Free for public repos with generous Linux/macOS minutes
- **Concurrency**: higher than GHA free tier (≥4 parallel jobs)
- **Resources**: 2 CPU / 4 GB by default, can request 8 CPU / 30 GB
- **Setup**: `.cirrus.yml` at repo root, GitHub App install
- **Fit**: very good — same triggering model (push, PR, cron, manual), supports container images
- **Caveat**: runner image differs from GHA's `ubuntu-latest`; need to re-test our `ghcr.io/johnnychen1113/autobsgenome-builder:latest` image works as-is

### GitLab CI (mirror mode) ⭐⭐⭐⭐
- Mirror this GitHub repo to GitLab.com, run pipelines there
- **Free tier**: 400 CI/CD minutes/month for private; **public projects get unlimited shared runner minutes**
- **Resources**: 1 CPU / 4 GB (Small), 2 CPU / 8 GB (Medium, paid)
- **Setup**: `.gitlab-ci.yml` + GitHub→GitLab mirror via Settings → Repository
- **Fit**: good — but cron triggers on the mirror, dispatch back to GitHub for releases is awkward (would need GitLab→GitHub API token)
- **Best use**: spillover for batch builds when GHA queue is saturated

### Cloud Build (Google Cloud) ⭐⭐⭐
- Free tier: 120 build-min/day on `e2-medium` runners
- **Resources**: configurable, billing scales with machine type
- **Setup**: `cloudbuild.yaml`, GitHub App connector
- **Fit**: ok — billing kicks in fast for batch work; better as paid backup than free-tier alternative

---

## Tier 2 — self-hosted (you control the box)

### Self-hosted GHA runner ⭐⭐⭐⭐⭐
- Already documented in `docs/SELF-HOSTED-RUNNER-PLAN.md`
- **Pros**: zero per-job cost, predictable performance, no concurrency cap, can run on home server / cheap VPS
- **Cons**: maintenance burden (runner updates, disk cleanup, network reliability)
- **Cost**: $0 if home machine, ~$5-20/mo for a 2-4 GB VPS (Hetzner, OVH, Contabo)
- **Decision**: deferred per user request — skip for now

### Drone CI / Woodpecker CI ⭐⭐⭐
- Self-hosted, single-binary CI
- **Setup**: Docker container + GitHub OAuth
- **Fit**: clean if we already run a server; overkill if not

---

## Tier 3 — serverless / function platforms

### Cloudflare Containers ⭐⭐
- New (2026), Workers-adjacent container runtime
- **Limits**: short max runtime, modest CPU/RAM, billing per-request
- **Fit**: poor — building BSgenome (R package + 2bit conversion) commonly takes 5-15 min per genome, exceeds typical serverless budget
- **Maybe useful**: lightweight orchestrator (queue tail) — not for actual builds

### Modal.com ⭐⭐⭐
- Python-native serverless GPU/CPU
- **Free tier**: $30/month credit
- **Pros**: trivial to spin up jobs, fast cold start, can request large memory
- **Cons**: not designed for R toolchains; we'd need to rebuild our R container as Modal image

---

## Recommendation (today)

1. **Fix the underlying Ensembl path bug first** — alt compute won't help if the build itself is wrong
2. **Mid-term**: stand up the self-hosted runner from `SELF-HOSTED-RUNNER-PLAN.md` once the queue stabilizes — best cost/resilience trade-off
3. **Backup plan**: pre-write `.cirrus.yml` mirroring `build-bsgenome.yml` so we can fail over in <1 day if GHA goes down

## Not recommended

- **CircleCI / Travis** — restrictive free tiers for public repos in 2026
- **AWS CodeBuild / Azure Pipelines** — billing complexity not worth it for hobby-scale OSS
- **Cloudflare Containers** for actual builds — runtime/RAM ceiling too low

---

## Trigger model when adding a second runner

When adding any second platform, the dispatcher logic in `batch-build.yml` needs a small change: it currently sends `repository_dispatch` to GitHub. To distribute work across platforms, either:

- (a) keep GHA as dispatcher, but route a fraction of items to a non-GHA pipeline via webhook, OR
- (b) move dispatch state to gh-pages/build-queue.json polling, and let each runner pull from the queue (simpler, more resilient)

Option (b) is cleaner and matches the existing queue model.
