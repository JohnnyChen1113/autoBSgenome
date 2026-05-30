"use client";

import { useEffect, useMemo, useState } from "react";
import {
  ChevronDown,
  Copy,
  Database,
  Download,
  ExternalLink,
  Loader2,
  Package,
  Search,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";

const REPO_BASE =
  process.env.NEXT_PUBLIC_REPOSITORY_BASE_URL ??
  "https://johnnychen1113.github.io/autoBSgenome";
const INITIAL_LIMIT = 160;
const PAGE_SIZE = 160;

type Taxonomy = Partial<
  Record<"domain" | "kingdom" | "phylum" | "class" | "order" | "family" | "genus", string>
>;

type CatalogAccession = {
  accession: string;
  assembly: string;
  source: string;
  size_mb?: number;
};

type BuildPackage = {
  package: string;
  version?: string;
  organism?: string;
  assembly?: string;
  provider?: string;
  accession?: string;
  source_url?: string;
  file_name?: string;
  size?: number;
  seq_ids?: string[];
  seq_count?: number;
  group?: string;
  taxonomy?: Taxonomy;
  common_name?: string;
  published?: string;
  storage?: string;
  download_url?: string;
  doi?: string;
  bioc_url?: string;
  _bioc?: boolean;
};

type OrganismEntry = {
  organism: string;
  common_name?: string;
  group?: string;
  taxonomy?: Taxonomy;
  builds: BuildPackage[];
  _source?: "community" | "bioconductor" | "both" | "catalog";
  _accessions?: CatalogAccession[];
  // Optional fields populated by the offline catalog-enrichment script
  // once it lands. UI renders them when present, otherwise falls back to
  // the raw `organism` string from NCBI assembly metadata.
  canonical_name?: string;
  synonyms?: string[];
};

type RepositoryData = {
  organisms: OrganismEntry[];
  flat: BuildPackage[];
};

type CatalogRow = {
  a?: string;
  o?: string;
  m?: string;
  g?: string;
  s?: string;
  z?: number;
};

type ProgressData = {
  total: number;
  done: number;
  building: number;
  pending: number;
};

type Kingdom = "all" | "animal" | "plant" | "fungi" | "prokaryote";
type SourceFilter = "ready" | "community" | "bioconductor" | "catalog";

async function fetchJson<T>(path: string): Promise<T | null> {
  try {
    const res = await fetch(`${REPO_BASE}/${path}?t=${Date.now()}`);
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

// NCBI assembly metadata uses bracket notation like "[Candida] arabinofermentans"
// to mark a historically classified but now-disputed genus. We strip the
// brackets for both display and URL construction; the bracket itself isn't a
// taxonomically meaningful character that any external service understands.
function stripGenusBrackets(name: string): string {
  return name.replace(/\[([^\]]+)\]/g, "$1");
}

function speciesName(name: string): string {
  const cleaned = stripGenusBrackets(name).trim();
  const parts = cleaned.split(/\s+/);
  return parts.length >= 2 ? parts.slice(0, 2).join(" ") : cleaned;
}

function strainInfo(name: string): string {
  const cleaned = stripGenusBrackets(name).trim();
  const parts = cleaned.split(/\s+/);
  return parts.length > 2 ? parts.slice(2).join(" ") : "";
}

function isAnimal(group?: string): boolean {
  return [
    "vertebrate_mammalian",
    "vertebrate_other",
    "invertebrate",
    "metazoa",
  ].includes(group ?? "");
}

function isPlant(group?: string): boolean {
  return ["plant", "plants"].includes(group ?? "");
}

function isFungi(group?: string): boolean {
  return group === "fungi";
}

// Strict prokaryotes: bacteria + archaea only. Viruses are not life;
// protozoa/protists are eukaryotes. Neither belongs here.
function isProkaryote(group?: string): boolean {
  return ["bacteria", "archaea"].includes(group ?? "");
}

function groupLabel(group?: string): string {
  const labels: Record<string, string> = {
    vertebrate_mammalian: "Mammal",
    vertebrate_other: "Vertebrate",
    invertebrate: "Invertebrate",
    metazoa: "Animal",
    plant: "Plant",
    plants: "Plant",
    fungi: "Fungi",
    bacteria: "Bacteria",
    archaea: "Archaea",
    viral: "Virus",
    protozoa: "Protozoa",
    protists: "Protist",
  };
  return labels[group ?? ""] ?? "Other";
}

function formatBytes(bytes?: number): string {
  if (!bytes || bytes <= 0) return "";
  const units = ["B", "KB", "MB", "GB"];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value.toFixed(unit < 2 ? 0 : 1)} ${units[unit]}`;
}

function sourceUrl(build: BuildPackage): string {
  if (build.source_url) return build.source_url;
  if (build.accession?.startsWith("GC")) {
    return `https://www.ncbi.nlm.nih.gov/datasets/genome/${build.accession}/`;
  }
  return "";
}

// Pick the right Ensembl subdomain by taxonomic kingdom. Vertebrates live
// on the main site; everything else has its own EnsemblGenomes sister.
function ensemblSubdomain(group?: string): string {
  if (isPlant(group)) return "plants.ensembl.org";
  if (isFungi(group)) return "fungi.ensembl.org";
  if (group === "invertebrate" || group === "metazoa") return "metazoa.ensembl.org";
  if (group === "protozoa" || group === "protists") return "protists.ensembl.org";
  if (isProkaryote(group)) return "bacteria.ensembl.org";
  return "www.ensembl.org";
}

// Construct an Ensembl species-page slug. EnsemblGenomes (Plants/Fungi/etc.)
// uses two URL conventions and we have to pick one:
//   - Multi-assembly species: /_genus_species_gca_NNNNNNNNN/Info/Index
//   - Single canonical species: /Genus_species/Info/Index
// When we have a GCA accession for a non-vertebrate organism, prefer the
// accession-anchored form because it's the one that resolves for species
// where multiple assemblies coexist on Ensembl (e.g. Candida auris).
function ensemblSlug(
  speciesQuery: string,
  group?: string,
  accession?: string
): string {
  const cleaned = stripGenusBrackets(speciesQuery).trim();
  const isVertebrate = group?.startsWith("vertebrate_") ?? false;

  if (!isVertebrate && accession?.startsWith("GCA_")) {
    const accDigits = accession.match(/GCA_(\d+)/)?.[1];
    if (accDigits) {
      const lower = cleaned.toLowerCase().replace(/\s+/g, "_");
      return `_${lower}_gca_${accDigits}`;
    }
  }

  // Title-case binomial: Genus_species
  return cleaned
    .split(/\s+/)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
    .join("_");
}

// Per-build source link. The chip shows where THIS specific build pulled
// its reference sequence from — which can differ from another build for
// the same organism (an NCBI build and an Ensembl build for one species).
// For Ensembl we prefer the build's recorded source_url; if missing, we
// construct a best-guess species URL on the right subdomain. Some species
// genuinely aren't indexed on any Ensembl site and will 404 regardless,
// which is a data-source problem we can't fix client-side.
function buildSourceLink(
  build: BuildPackage,
  speciesQuery: string,
  group: string | undefined
): { label: string; url: string } | null {
  if (build._bioc) {
    return build.bioc_url
      ? { label: "Bioconductor", url: build.bioc_url }
      : null;
  }

  const provider = build.provider?.toLowerCase();

  if (provider === "ensembl") {
    if (build.source_url && /\bensembl\.org\b/i.test(build.source_url)) {
      return { label: "Ensembl", url: build.source_url };
    }
    const subdomain = ensemblSubdomain(group);
    const slug = ensemblSlug(speciesQuery, group, build.accession);
    return {
      label: "Ensembl",
      url: `https://${subdomain}/${slug}/Info/Index`,
    };
  }

  if (provider === "ucsc" && build.assembly) {
    return {
      label: "UCSC",
      url: `https://genome.ucsc.edu/cgi-bin/hgGateway?db=${encodeURIComponent(
        build.assembly
      )}`,
    };
  }

  if (build.accession?.startsWith("GC")) {
    return {
      label: "NCBI",
      url: `https://www.ncbi.nlm.nih.gov/datasets/genome/${build.accession}/`,
    };
  }

  return null;
}

function installCommand(build: BuildPackage): string | null {
  if (build._bioc) {
    return `BiocManager::install("${build.package}")`;
  }
  // Community build: only generate a one-line install snippet when we know
  // the file is actually published. The github.io repo's src/contrib/ index
  // is not reliably populated, so falling back to it would hand the user a
  // command that 404s.
  if (!build.download_url) return null;
  return `install.packages(\n  "${build.download_url}",\n  repos = NULL, type = "source"\n)`;
}

function matchesKingdom(group: string | undefined, kingdom: Kingdom): boolean {
  switch (kingdom) {
    case "all":
      return true;
    case "animal":
      return isAnimal(group);
    case "plant":
      return isPlant(group);
    case "fungi":
      return isFungi(group);
    case "prokaryote":
      return isProkaryote(group);
  }
}

function matchesSource(
  org: OrganismEntry,
  source: SourceFilter
): boolean {
  const builds = org.builds ?? [];
  switch (source) {
    case "ready":
      return builds.length > 0;
    case "community":
      return builds.some((b) => !b._bioc);
    case "bioconductor":
      return builds.some((b) => b._bioc);
    case "catalog":
      return true;
  }
}

function mergeRepositoryData(
  community: RepositoryData | BuildPackage[] | null,
  biocPackages: BuildPackage[] | null,
  catalog: CatalogRow[] | null
): { organisms: OrganismEntry[]; flat: BuildPackage[]; biocCount: number } {
  let flat: BuildPackage[] = [];
  let communityOrganisms: OrganismEntry[] = [];

  if (Array.isArray(community)) {
    flat = community;
    const byOrg = new Map<string, OrganismEntry>();
    for (const build of flat) {
      const organism = build.organism || "Unknown";
      const key = organism.toLowerCase();
      const existing =
        byOrg.get(key) ??
        ({
          organism,
          common_name: build.common_name,
          group: build.group,
          taxonomy: build.taxonomy,
          builds: [],
          _source: "community",
        } satisfies OrganismEntry);
      existing.builds.push(build);
      byOrg.set(key, existing);
    }
    communityOrganisms = [...byOrg.values()];
  } else if (community) {
    flat = community.flat ?? [];
    communityOrganisms = community.organisms ?? [];
  }

  const merged = new Map<string, OrganismEntry>();
  for (const org of communityOrganisms) {
    merged.set(org.organism.toLowerCase(), {
      ...org,
      builds: org.builds ?? [],
      _source: "community",
    });
  }

  let biocCount = 0;
  for (const build of biocPackages ?? []) {
    const organism = build.organism || "Unknown";
    const key = organism.toLowerCase();
    const current = merged.get(key);
    const biocBuild: BuildPackage = { ...build, _bioc: true };
    biocCount += 1;

    if (current) {
      current.builds = [...current.builds, biocBuild];
      current._source = current._source === "community" ? "both" : current._source;
      if (!current.common_name && build.common_name) current.common_name = build.common_name;
      if (!current.taxonomy && build.taxonomy) current.taxonomy = build.taxonomy;
      if (!current.group && build.group) current.group = build.group;
    } else {
      merged.set(key, {
        organism,
        common_name: build.common_name,
        group: build.group,
        taxonomy: build.taxonomy,
        builds: [biocBuild],
        _source: "bioconductor",
      });
    }
  }

  for (const row of catalog ?? []) {
    if (!row.o) continue;
    const key = row.o.toLowerCase();
    const accession = {
      accession: row.a ?? "",
      assembly: row.m ?? "",
      source: row.s ?? "",
      size_mb: row.z,
    };
    const current = merged.get(key);
    if (current) {
      current._accessions = [...(current._accessions ?? []), accession];
    } else {
      merged.set(key, {
        organism: row.o,
        group: row.g,
        taxonomy: {},
        builds: [],
        _source: "catalog",
        _accessions: [accession],
      });
    }
  }

  return {
    organisms: [...merged.values()].sort((a, b) =>
      a.organism.localeCompare(b.organism)
    ),
    flat,
    biocCount,
  };
}

function filterOrganisms(
  organisms: OrganismEntry[],
  kingdom: Kingdom,
  source: SourceFilter,
  query: string,
  letter: string
): OrganismEntry[] {
  const normalized = query.trim().toLowerCase();
  return organisms.filter((org) => {
    // When the user is typing a free search, ignore both filter axes
    // so the search can find anything in the index.
    if (normalized.length < 2) {
      if (!matchesKingdom(org.group, kingdom)) return false;
      if (!matchesSource(org, source)) return false;
    }

    if (letter && speciesName(org.organism)[0]?.toUpperCase() !== letter) {
      return false;
    }

    if (normalized.length >= 2) {
      const builds = org.builds ?? [];
      const haystack = [
        org.organism,
        org.common_name ?? "",
        org.group ?? "",
        ...(org._accessions ?? []).map(
          (a) => `${a.accession} ${a.assembly} ${a.source}`
        ),
        ...builds.map(
          (b) =>
            `${b.package} ${b.assembly ?? ""} ${b.accession ?? ""} ${
              b.provider ?? ""
            }`
        ),
      ]
        .join(" ")
        .toLowerCase();
      return haystack.includes(normalized);
    }

    return true;
  });
}

function taxonomyBreadcrumb(taxonomy?: Taxonomy): string[] {
  return ["phylum", "class", "order", "family"]
    .map((rank) => taxonomy?.[rank as keyof Taxonomy])
    .filter(Boolean) as string[];
}

function providerTone(provider?: string): string {
  if (provider?.toLowerCase() === "ensembl") {
    return "border-amber-200 bg-amber-50 text-amber-800";
  }
  if (provider?.toLowerCase() === "ucsc") {
    return "border-violet-200 bg-violet-50 text-violet-800";
  }
  return "border-blue-200 bg-blue-50 text-blue-800";
}

export function RepositoryBrowser() {
  const [organisms, setOrganisms] = useState<OrganismEntry[]>([]);
  const [flatCount, setFlatCount] = useState(0);
  const [biocCount, setBiocCount] = useState(0);
  const [progress, setProgress] = useState<ProgressData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [kingdom, setKingdom] = useState<Kingdom>("all");
  const [source, setSource] = useState<SourceFilter>("ready");
  const [letter, setLetter] = useState("");
  const [visibleCount, setVisibleCount] = useState(INITIAL_LIMIT);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [copied, setCopied] = useState("");

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const initialQuery = params.get("q") ?? params.get("search");
    if (initialQuery) {
      setQuery(initialQuery);
      setLetter("");
    }
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError("");

      const [community, biocPackages, catalog, queue] = await Promise.all([
        fetchJson<RepositoryData | BuildPackage[]>("packages.json"),
        fetchJson<BuildPackage[]>("bioc-packages.json"),
        fetchJson<CatalogRow[]>("catalog.json"),
        fetchJson<{ status: string }[]>("build-queue.json"),
      ]);

      if (cancelled) return;
      if (!community) {
        setError("Could not load repository metadata from the package index.");
        setLoading(false);
        return;
      }

      const merged = mergeRepositoryData(community, biocPackages, catalog);
      setOrganisms(merged.organisms);
      setFlatCount(merged.flat.length);
      setBiocCount(merged.biocCount);

      if (queue) {
        const eukaryotes = queue.filter(
          (item) => !item.status?.startsWith("skip_prokaryote")
        );
        setProgress({
          total: eukaryotes.length,
          done: eukaryotes.filter((item) => item.status === "done").length,
          building: eukaryotes.filter((item) => item.status === "building").length,
          pending: eukaryotes.filter((item) => item.status === "pending").length,
        });
      }

      setLoading(false);
    }

    void load();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    setVisibleCount(INITIAL_LIMIT);
  }, [query, kingdom, source, letter]);

  // Absolute number of organisms with any installable build. Used in the
  // top stats card, where filter state should not affect the headline number.
  const readyOrganisms = useMemo(
    () =>
      organisms.reduce(
        (n, org) => ((org.builds ?? []).length > 0 ? n + 1 : n),
        0
      ),
    [organisms]
  );

  // Cross-axis counts: each chip shows how many rows would match if THAT
  // chip became the active value, given the OTHER axis's current selection.
  // This is what users actually want when comparing chips, instead of raw
  // population numbers that don't intersect.
  const kingdomCounts = useMemo(() => {
    const c = { all: 0, animal: 0, plant: 0, fungi: 0, prokaryote: 0 };
    for (const org of organisms) {
      if (!matchesSource(org, source)) continue;
      c.all += 1;
      if (isAnimal(org.group)) c.animal += 1;
      if (isPlant(org.group)) c.plant += 1;
      if (isFungi(org.group)) c.fungi += 1;
      if (isProkaryote(org.group)) c.prokaryote += 1;
    }
    return c;
  }, [organisms, source]);

  const sourceCounts = useMemo(() => {
    const c = { ready: 0, community: 0, bioconductor: 0, catalog: 0 };
    for (const org of organisms) {
      if (!matchesKingdom(org.group, kingdom)) continue;
      const builds = org.builds ?? [];
      if (builds.length > 0) c.ready += 1;
      if (builds.some((b) => !b._bioc)) c.community += 1;
      if (builds.some((b) => b._bioc)) c.bioconductor += 1;
      c.catalog += 1;
    }
    return c;
  }, [organisms, kingdom]);

  const availableLetters = useMemo(() => {
    const set = new Set<string>();
    for (const org of filterOrganisms(organisms, kingdom, source, query, "")) {
      const first = speciesName(org.organism)[0]?.toUpperCase();
      if (first) set.add(first);
    }
    return set;
  }, [kingdom, source, organisms, query]);

  const filtered = useMemo(
    () => filterOrganisms(organisms, kingdom, source, query, letter),
    [kingdom, source, letter, organisms, query]
  );

  const displayed = filtered.slice(0, visibleCount);
  const progressPercent =
    progress && progress.total > 0 ? (progress.done / progress.total) * 100 : 0;

  function toggleExpanded(key: string) {
    setExpanded((previous) => {
      const next = new Set(previous);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  }

  async function copyCommand(text: string, key: string) {
    await navigator.clipboard.writeText(text);
    setCopied(key);
    window.setTimeout(() => setCopied(""), 1400);
  }

  const kingdomOptions: { key: Kingdom; label: string; count: number }[] = [
    { key: "all", label: "All", count: kingdomCounts.all },
    { key: "animal", label: "Animals", count: kingdomCounts.animal },
    { key: "plant", label: "Plants", count: kingdomCounts.plant },
    { key: "fungi", label: "Fungi", count: kingdomCounts.fungi },
    { key: "prokaryote", label: "Prokaryotes", count: kingdomCounts.prokaryote },
  ];

  const sourceOptions: { key: SourceFilter; label: string; count: number }[] = [
    { key: "ready", label: "All built", count: sourceCounts.ready },
    { key: "community", label: "Built by us", count: sourceCounts.community },
    { key: "bioconductor", label: "Bioconductor", count: sourceCounts.bioconductor },
    { key: "catalog", label: "Full catalog", count: sourceCounts.catalog },
  ];

  return (
    <main className="flex-1">
      <section className="border-b border-border bg-secondary/40">
        <div className="mx-auto max-w-6xl px-6 py-10">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-2xl">
              <h1 className="text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
                BSgenome Package Repository
              </h1>
              <p className="mt-3 text-base leading-relaxed text-muted-foreground">
                Browse community-built and Bioconductor BSgenome packages from
                the same AutoBSgenome interface used to build new packages.
              </p>
            </div>
            <div className="grid grid-cols-3 gap-3 text-center sm:min-w-[360px]">
              <div className="rounded-lg border border-border bg-background px-3 py-3">
                <div className="font-mono text-xl font-semibold text-primary">
                  {loading ? "-" : (flatCount + biocCount).toLocaleString()}
                </div>
                <div className="text-xs text-muted-foreground">packages</div>
              </div>
              <div className="rounded-lg border border-border bg-background px-3 py-3">
                <div className="font-mono text-xl font-semibold text-primary">
                  {loading ? "-" : readyOrganisms.toLocaleString()}
                </div>
                <div className="text-xs text-muted-foreground">organisms</div>
              </div>
              <div className="rounded-lg border border-border bg-background px-3 py-3">
                <div className="font-mono text-xl font-semibold text-primary">
                  {loading ? "-" : organisms.length.toLocaleString()}
                </div>
                <div className="text-xs text-muted-foreground">catalog</div>
              </div>
            </div>
          </div>

          <div className="mt-6 rounded-lg border border-border bg-background p-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div className="min-w-0 flex-1">
                <div className="text-sm font-medium text-foreground">
                  How to install
                </div>
                <p className="mt-1 text-xs text-muted-foreground">
                  Each package card below shows a ready-to-copy one-line R
                  command. Or click Download to grab the tarball and install
                  offline.
                </p>
                <code className="mt-2 block overflow-x-auto rounded-md bg-secondary px-3 py-2 font-mono text-xs text-foreground">
                  install.packages(&quot;TARBALL_URL&quot;, repos = NULL, type = &quot;source&quot;)
                </code>
              </div>
              <a
                href="https://github.com/JohnnyChen1113/autoBSgenome/releases"
                target="_blank"
                rel="noreferrer"
                className="inline-flex h-8 shrink-0 items-center justify-center gap-1.5 rounded-lg border border-border px-2.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              >
                <Database className="size-4" />
                All tarballs
              </a>
            </div>
          </div>

          {progress && progress.total > 0 && (
            <div className="mt-4 rounded-lg border border-border bg-background p-4">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <div className="text-sm font-medium text-foreground">
                    Eukaryotic reference genome coverage
                  </div>
                  <div className="mt-1 text-xs text-muted-foreground">
                    {progress.done.toLocaleString()} built, {progress.building}{" "}
                    building, {progress.pending.toLocaleString()} pending
                  </div>
                </div>
                <div className="font-mono text-sm font-semibold text-primary">
                  {progressPercent.toFixed(1)}%
                </div>
              </div>
              <Progress value={progressPercent} className="mt-3" />
            </div>
          )}
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-6 py-6">
        {/* Row 1: Kingdom */}
        <div className="flex flex-wrap gap-2">
          {kingdomOptions.map((option) => (
            <Button
              key={option.key}
              type="button"
              variant={kingdom === option.key ? "default" : "outline"}
              onClick={() => setKingdom(option.key)}
            >
              {option.label}
              {option.count !== null && (
                <span className="font-mono text-xs opacity-75">
                  {option.count.toLocaleString()}
                </span>
              )}
            </Button>
          ))}
        </div>

        {/* Row 2: Source */}
        <div className="mt-3 flex flex-wrap gap-2">
          {sourceOptions.map((option) => (
            <Button
              key={option.key}
              type="button"
              variant={source === option.key ? "default" : "outline"}
              onClick={() => setSource(option.key)}
            >
              {option.label}
              <span className="font-mono text-xs opacity-75">
                {option.count.toLocaleString()}
              </span>
            </Button>
          ))}
        </div>

        {/* Row 3: Search */}
        <div className="relative mt-4">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search organism, package, accession, assembly..."
            className="pl-9"
          />
        </div>

        <div className="mt-4 flex flex-wrap gap-1">
          <Button
            type="button"
            size="xs"
            variant={letter ? "outline" : "default"}
            onClick={() => setLetter("")}
          >
            All
          </Button>
          {"ABCDEFGHIJKLMNOPQRSTUVWXYZ".split("").map((item) => {
            const disabled = !availableLetters.has(item);
            return (
              <Button
                key={item}
                type="button"
                size="xs"
                variant={letter === item ? "default" : "outline"}
                disabled={disabled}
                onClick={() => setLetter(item)}
                className="w-7 px-0"
              >
                {item}
              </Button>
            );
          })}
        </div>

        <div className="mt-5 text-sm text-muted-foreground">
          {loading
            ? "Loading repository metadata..."
            : `${filtered.length.toLocaleString()} matching organisms`}
        </div>

        {loading && (
          <div className="mt-8 flex items-center gap-2 text-muted-foreground">
            <Loader2 className="size-4 animate-spin" />
            Loading packages from the repository index.
          </div>
        )}

        {error && (
          <div className="mt-8 rounded-lg border border-destructive/20 bg-destructive/10 p-4 text-sm text-destructive">
            {error}
          </div>
        )}

        {!loading && !error && displayed.length === 0 && (
          <div className="mt-8 rounded-lg border border-border bg-secondary p-8 text-center text-muted-foreground">
            No matching packages found.
          </div>
        )}

        <div className="mt-4 grid gap-3">
          {displayed.map((org) => {
            const key = org.organism;
            const builds = org.builds ?? [];
            const accessions = org._accessions ?? [];
            const isOpen = expanded.has(key);
            const firstAccession = accessions[0];
            const catalogOnly = builds.length === 0 && accessions.length > 0;
            const crumbs = taxonomyBreadcrumb(org.taxonomy);
            const visibleBuilds = isOpen ? builds : builds.slice(0, 1);

            return (
              <Card key={key} className="rounded-lg py-0">
                <CardContent className="px-0">
                  <div className="flex flex-col gap-4 p-4 md:flex-row md:items-start md:justify-between">
                    <div className="min-w-0 flex-1">
                      {(() => {
                        // Prefer the offline-enriched canonical name when
                        // present, otherwise fall back to the raw NCBI
                        // assembly metadata string.
                        const displayName = org.canonical_name ?? org.organism;
                        const synonyms = (org.synonyms ?? []).filter(
                          (s) =>
                            stripGenusBrackets(s).trim() !==
                            stripGenusBrackets(displayName).trim()
                        );
                        return (
                          <>
                            <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
                              <h2 className="font-heading text-lg font-semibold leading-snug text-foreground">
                                <span className="italic">{speciesName(displayName)}</span>
                                {strainInfo(displayName) && (
                                  <span className="ml-1 font-sans text-sm font-normal text-muted-foreground">
                                    {strainInfo(displayName)}
                                  </span>
                                )}
                              </h2>
                              {org.common_name && (
                                <span className="text-sm text-muted-foreground">
                                  {org.common_name}
                                </span>
                              )}
                            </div>
                      {synonyms.length > 0 && (
                        <div className="mt-1 text-xs text-muted-foreground">
                          <span className="font-medium">Formerly:</span>{" "}
                          <span className="italic">
                            {synonyms
                              .map((s) => stripGenusBrackets(s).trim())
                              .join("; ")}
                          </span>
                        </div>
                      )}
                          </>
                        );
                      })()}
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        <Badge variant="outline">{groupLabel(org.group)}</Badge>
                        {builds.length > 0 && (
                          <Badge variant="secondary">
                            <Package className="size-3" />
                            {builds.length} build{builds.length === 1 ? "" : "s"}
                          </Badge>
                        )}
                        {builds.some((build) => build._bioc) && (
                          <Badge className="border-green-200 bg-green-50 text-green-800">
                            Bioconductor
                          </Badge>
                        )}
                        {catalogOnly && (
                          <Badge
                            className="border-primary/30 bg-primary/10 text-primary"
                            title="No BSgenome package built yet. Click Build to start one."
                          >
                            Build on click
                          </Badge>
                        )}
                      </div>
                      {crumbs.length > 0 && (
                        <div className="mt-2 flex flex-wrap gap-1 text-xs text-muted-foreground">
                          {crumbs.map((crumb) => (
                            <span
                              key={crumb}
                              className="rounded bg-secondary px-1.5 py-0.5"
                            >
                              {crumb}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>

                    <div className="flex shrink-0 items-center gap-2">
                      {catalogOnly && firstAccession ? (
                        <a
                          href={`/build?accession=${encodeURIComponent(
                            firstAccession.accession
                          )}${
                            firstAccession.source === "ensembl"
                              ? "&source=ensembl"
                              : ""
                          }`}
                          className="inline-flex h-8 items-center justify-center rounded-lg bg-primary px-2.5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
                        >
                          Build
                        </a>
                      ) : builds.length > 1 ? (
                        // Only offer Details when there's actually something to
                        // expand. A single-build card already shows everything.
                        <Button
                          type="button"
                          variant="outline"
                          onClick={() => toggleExpanded(key)}
                        >
                          Details
                          <ChevronDown
                            className={cn(
                              "size-4 transition-transform",
                              isOpen && "rotate-180"
                            )}
                          />
                        </Button>
                      ) : null}
                    </div>
                  </div>

                  {builds.length > 0 && (
                    <div className="border-t border-border">
                      {visibleBuilds.map((build) => {
                        const copyKey = `${org.organism}-${build.package}`;
                        return (
                          <div
                            key={copyKey}
                            className="border-b border-border px-4 py-4 last:border-b-0"
                          >
                            <div className="min-w-0">
                              <div className="flex flex-wrap items-center gap-2">
                                <div className="break-words font-mono text-sm font-medium text-foreground">
                                  {build.package}
                                </div>
                                {(() => {
                                  const src = buildSourceLink(
                                    build,
                                    speciesName(org.canonical_name ?? org.organism),
                                    org.group
                                  );
                                  if (!src) return null;
                                  return (
                                    <a
                                      href={src.url}
                                      target="_blank"
                                      rel="noreferrer"
                                      title={`View this build's reference on ${src.label}`}
                                      className="inline-flex h-6 items-center gap-1 rounded border border-border bg-background px-2 font-mono text-[10px] uppercase tracking-[0.1em] text-muted-foreground transition-colors hover:border-primary hover:text-primary"
                                    >
                                      {src.label}
                                      <ExternalLink className="size-3" />
                                    </a>
                                  );
                                })()}
                              </div>
                              <div className="mt-2 grid gap-x-4 gap-y-1 text-sm text-muted-foreground sm:grid-cols-2 lg:grid-cols-4">
                                <span>
                                  Assembly:{" "}
                                  <span className="text-foreground">
                                    {build.assembly || "N/A"}
                                  </span>
                                </span>
                                <span>
                                  Provider:{" "}
                                  <Badge
                                    variant="outline"
                                    className={providerTone(build.provider)}
                                  >
                                    {build.provider || "NCBI"}
                                  </Badge>
                                </span>
                                <span>
                                  Version:{" "}
                                  <span className="text-foreground">
                                    {build.version || "1.0.0"}
                                  </span>
                                </span>
                                {build.size && (
                                  <span>
                                    Size:{" "}
                                    <span className="text-foreground">
                                      {formatBytes(build.size)}
                                    </span>
                                  </span>
                                )}
                                {build.accession && (
                                  <span className="min-w-0">
                                    Accession:{" "}
                                    <a
                                      href={sourceUrl(build)}
                                      target="_blank"
                                      rel="noreferrer"
                                      className="text-primary hover:underline"
                                    >
                                      {build.accession}
                                    </a>
                                  </span>
                                )}
                                {build.seq_count && (
                                  <span>
                                    Sequences:{" "}
                                    <span className="text-foreground">
                                      {build.seq_count.toLocaleString()}
                                    </span>
                                  </span>
                                )}
                                {build.published && (
                                  <span>
                                    Published:{" "}
                                    <span className="text-foreground">
                                      {new Date(build.published).toLocaleDateString()}
                                    </span>
                                  </span>
                                )}
                                {build.doi && (
                                  <span>
                                    DOI:{" "}
                                    <a
                                      href={`https://doi.org/${build.doi}`}
                                      target="_blank"
                                      rel="noreferrer"
                                      className="text-primary hover:underline"
                                    >
                                      {build.doi}
                                    </a>
                                  </span>
                                )}
                              </div>
                              {(() => {
                                const cmd = installCommand(build);

                                // Bioconductor: only the BiocManager command,
                                // no download (Bioc hosts the binary itself).
                                if (build._bioc) {
                                  return (
                                    <div className="mt-4 space-y-2">
                                      <div className="text-xs font-medium uppercase tracking-wide text-foreground/60">
                                        Install from Bioconductor
                                      </div>
                                      <div className="relative rounded-md bg-secondary p-3 pr-20">
                                        <pre className="m-0 min-w-0 overflow-hidden whitespace-pre-wrap break-all font-mono text-xs leading-5 text-foreground">
                                          {cmd ?? `BiocManager::install("${build.package}")`}
                                        </pre>
                                        <Button
                                          type="button"
                                          size="sm"
                                          variant="outline"
                                          className="absolute right-2 top-2 bg-background"
                                          onClick={() =>
                                            copyCommand(
                                              cmd ?? `BiocManager::install("${build.package}")`,
                                              copyKey
                                            )
                                          }
                                        >
                                          <Copy className="size-3.5" />
                                          {copied === copyKey ? "Copied" : "Copy"}
                                        </Button>
                                      </div>
                                      {build.bioc_url && (
                                        <a
                                          href={build.bioc_url}
                                          target="_blank"
                                          rel="noreferrer"
                                          className="inline-flex h-8 items-center gap-1.5 text-xs font-medium text-primary link-underline"
                                        >
                                          View on Bioconductor
                                          <ExternalLink className="size-3.5" />
                                        </a>
                                      )}
                                    </div>
                                  );
                                }

                                // Community build: requires download_url to
                                // produce a working snippet AND a working
                                // direct download. If missing, show one note.
                                if (!cmd || !build.download_url) {
                                  return (
                                    <div className="mt-4 rounded-md border border-dashed border-border bg-secondary/50 px-3 py-2 text-xs text-muted-foreground">
                                      Tarball not yet published for this build.
                                      Check back later, or open an issue if it's
                                      been stuck for more than a day.
                                    </div>
                                  );
                                }

                                // Two methods side by side. Left column is
                                // the install snippet (takes remaining width).
                                // Right column is a compact download card
                                // (auto-width, top-aligned, not stretched).
                                return (
                                  <div className="mt-4 grid items-center gap-3 md:grid-cols-[1fr_minmax(11rem,auto)]">
                                    {/* Method 1 — install in R online */}
                                    <div className="min-w-0 space-y-2">
                                      <div className="text-xs font-medium uppercase tracking-wide text-foreground/60">
                                        Install in R (online)
                                      </div>
                                      <div className="relative rounded-md bg-secondary p-3 pr-20">
                                        <pre className="m-0 min-w-0 overflow-hidden whitespace-pre-wrap break-all font-mono text-xs leading-5 text-foreground">
                                          {cmd}
                                        </pre>
                                        <Button
                                          type="button"
                                          size="sm"
                                          variant="outline"
                                          className="absolute right-2 top-2 bg-background"
                                          onClick={() => copyCommand(cmd, copyKey)}
                                        >
                                          <Copy className="size-3.5" />
                                          {copied === copyKey ? "Copied" : "Copy"}
                                        </Button>
                                      </div>
                                    </div>

                                    {/* Method 2 — download tarball (compact) */}
                                    <div className="space-y-2">
                                      <div className="text-xs font-medium uppercase tracking-wide text-foreground/60">
                                        Or download (offline)
                                      </div>
                                      <a
                                        href={build.download_url}
                                        className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground transition-all hover:bg-primary/90 hover:shadow-sm"
                                      >
                                        <Download className="size-4" />
                                        {build.size ? formatBytes(build.size) : ".tar.gz"}
                                      </a>
                                    </div>
                                  </div>
                                );
                              })()}
                            </div>
                          </div>
                        );
                      })}

                      {!isOpen && builds.length > visibleBuilds.length && (
                        <div className="flex justify-center px-4 py-4">
                          <button
                            type="button"
                            className="inline-flex h-9 items-center gap-2 rounded-md border border-primary/30 bg-background px-4 text-sm font-medium text-primary transition-all hover:border-primary hover:bg-primary hover:text-primary-foreground hover:shadow-sm"
                            onClick={() => toggleExpanded(key)}
                          >
                            Show {builds.length - visibleBuilds.length} more
                            <ChevronDown className="size-4" />
                          </button>
                        </div>
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>

        {!loading && filtered.length > displayed.length && (
          <div className="mt-6 flex justify-center">
            <Button
              type="button"
              variant="outline"
              onClick={() => setVisibleCount((value) => value + PAGE_SIZE)}
            >
              Show more
              <span className="font-mono text-xs opacity-75">
                {displayed.length.toLocaleString()} /{" "}
                {filtered.length.toLocaleString()}
              </span>
            </Button>
          </div>
        )}
      </section>
    </main>
  );
}
