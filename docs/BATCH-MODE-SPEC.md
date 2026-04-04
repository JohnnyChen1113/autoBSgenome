# Batch Build Mode — Design Spec

## Overview

Allow users to build multiple BSgenome packages in one session. Input multiple accessions, review all metadata, build in parallel, download results individually.

## User Flow

```
1. Input              2. Fetch & Review         3. Build                 4. Results
┌────────────────┐   ┌─────────────────────┐   ┌─────────────────────┐   ┌─────────────────────┐
│ GCF_000001215.4│   │ ▼ D. melanogaster   │   │ ✅ D. melanogaster  │   │ ✅ D. melanogaster  │
│ GCA_000002035.4│   │   NCBI (auto)       │   │   Done (45s)        │   │   [Download] ☑      │
│ danio_rerio    │   │ ▼ Danio rerio       │   │ 🔄 Danio rerio     │   │ ✅ Danio rerio      │
│ GCF_000001405.4│   │   ⚠ NCBI / Ensembl? │   │   Building... 32s   │   │   [Download] ☑      │
│                │   │   ○ NCBI ● Ensembl  │   │ ⏳ Homo sapiens     │   │ ✅ Homo sapiens     │
│ [Fetch All]    │   │ ▼ Homo sapiens      │   │   Queued (3/3)      │   │   [Download] ☑      │
│                │   │   NCBI (auto)       │   │                     │   │                     │
│                │   │ [Build All Valid]    │   │                     │   │ [Publish Selected]  │
└────────────────┘   └─────────────────────┘   └─────────────────────┘   └─────────────────────┘
```

## Step 1: Input

- Toggle between "Single" and "Batch" mode via a button next to the accession input
- Batch mode shows a textarea (min 5 rows), one accession/identifier per line
- Accepts mixed input types:
  - `GCF_xxx` → NCBI RefSeq (unambiguous)
  - `GCA_xxx` → ambiguous (could be NCBI GenBank or Ensembl) → needs source selector
  - `danio_rerio` → Ensembl species name (unambiguous)
  - `https://ncbi.nlm.nih.gov/datasets/genome/GCF_xxx/` → NCBI URL (unambiguous)
  - `https://*.ensembl.org/Species_name/...` → Ensembl URL (unambiguous, covers all sister sites)
- "Fetch All" button triggers parallel metadata lookups (with 300ms delay between requests for rate limiting)
- Empty lines and duplicates are silently ignored

## Step 2: Fetch & Review

- Each accession becomes a collapsible card showing:
  - **Collapsed**: organism name, accession, source badge (NCBI/Ensembl), status icon
  - **Expanded**: full metadata (same fields as single-build review page)
- States per item:
  - `fetching` — spinner, querying API
  - `ready` — metadata loaded, green checkmark
  - `error` — red X, error message (invalid accession, API failure, etc.)
  - `ambiguous` — yellow warning, GCA_ accession needs source selection (radio: NCBI / Ensembl)
- All fields are editable per item (same as single-build review)
- Bottom: "Build All Valid" button (skips items with errors)

### Source ambiguity resolution for GCA_ accessions

When a GCA_ accession is entered:
1. Fetch from NCBI first (always works for GCA_)
2. Show a source selector: "Build from: ○ NCBI  ○ Ensembl"
3. Default to NCBI
4. If user selects Ensembl, re-fetch metadata from Ensembl REST API using the organism name

## Step 3: Build

- Triggers `/api/build` for each valid item sequentially (10s delay between dispatches to respect GitHub Actions rate limits)
- Each item shows independent status:
  - `queued` — waiting to be dispatched
  - `building` — GitHub Actions running, live timer
  - `done` — build complete, download available
  - `failed` — build failed, error message + link to GitHub issue
- Progress bar at top: "3/5 complete"
- Items can finish in any order (parallel GitHub Actions jobs)
- Poll status for all active builds every 15 seconds

## Step 4: Results

- Each completed item shows:
  - Download button (direct .tar.gz link)
  - Install command (inline code block with copy button)
  - Checkbox: "Publish to community repository" (default unchecked)
- Bottom: "Publish Selected to Repository" button
  - Triggers `/api/publish` for each checked item
- Failed items show retry button

## Data Structure

```typescript
interface BatchItem {
  id: string;                          // unique ID (index-based)
  rawInput: string;                    // original user input
  detectedType: 'ncbi' | 'ensembl' | 'ambiguous' | 'invalid';
  selectedSource: 'ncbi' | 'ensembl'; // user's choice (for ambiguous GCA_)
  status: 'pending' | 'fetching' | 'ready' | 'ambiguous' | 'error' | 'building' | 'done' | 'failed';
  accession: string;                  // extracted accession
  form?: FormData;                    // reuse existing FormData type
  circularSeqs?: CircularSequence[];
  error?: string;
  jobId?: string;
  downloadUrl?: string;
  publishChecked: boolean;
}
```

## UI Components

### BatchInput
- Textarea with placeholder: "Enter one accession per line, e.g.\nGCF_000001215.4\nGCA_000002035.4\ndanio_rerio"
- Line count indicator: "5 accessions detected"
- "Fetch All" button

### BatchItemCard
- Collapsible card component
- Collapsed: `[status icon] Organism Name  |  GCF_xxx  |  NCBI badge  |  [expand chevron]`
- Expanded: same layout as single-build ReviewStep, but embedded in card
- Source selector (only for ambiguous GCA_): radio buttons NCBI / Ensembl

### BatchProgress
- Top-level progress: "Building 2/5..."
- Progress bar

### BatchResults
- Checkboxes for publish selection
- Bulk "Publish Selected" action

## Technical Notes

- **State persistence**: Save batch state to localStorage on every status change. Restore on page refresh.
- **URL param**: `?batch=true` to open directly in batch mode (for future API integration)
- **Concurrency**: GitHub Actions free tier allows ~20 concurrent jobs. We dispatch with 10s delay but jobs run in parallel.
- **Error handling**: Individual item failures don't block other items. Each item is independent.
- **No backend changes needed**: Each batch item uses the same `/api/build`, `/api/status/:id`, `/api/publish` endpoints as single builds.

## Entry Points

1. Web tool: "Batch Mode" toggle button on the input step
2. Browse page: future "Add to batch" button on each species card (Phase 2)
