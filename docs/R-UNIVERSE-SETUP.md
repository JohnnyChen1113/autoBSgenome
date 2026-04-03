# R-universe Setup for AutoBSgenome

## Status

- [x] Created registry repo: https://github.com/JohnnyChen1113/johnnychen1113.r-universe.dev
- [x] Added `packages.json` with autoBSgenome package
- [ ] **TODO (manual step):** Install R-universe GitHub App at https://github.com/apps/r-universe/installations/new

## What This Does

Once the GitHub App is installed, R-universe will automatically:
1. Build the autoBSgenome R package from the GitHub repo
2. Host it at `https://johnnychen1113.r-universe.dev`
3. Provide binary packages for all platforms (Linux, macOS, Windows)

## User Installation (after setup)

```r
# Install autoBSgenome CLI tool from R-universe
install.packages("autoBSgenome",
  repos = c("https://johnnychen1113.r-universe.dev", "https://cloud.r-project.org"))
```

## Note

This hosts the **autoBSgenome CLI tool** as an R package, NOT the built BSgenome data packages.
The web-built BSgenome packages are hosted on GitHub Releases (14-day TTL).

In the future, we may use R-universe to also host commonly-built BSgenome data packages
as a community repository.
