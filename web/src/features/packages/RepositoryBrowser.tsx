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
  X,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { SpeciesImage } from "@/components/SpeciesImage";
import { Input } from "@/components/ui/input";
import { siteConfig } from "@/config";
import {
  publicPackageDownloadUrl,
  warningFreeInstallCommand,
} from "@/lib/install-command";
import { cleanOrganismName } from "@/lib/package-name";
import { cn } from "@/lib/utils";
import { fetchRepositoryJson } from "@/features/packages/repository-api";

const INITIAL_LIMIT = 160;
const PAGE_SIZE = 160;

type Taxonomy = Partial<
  Record<"domain" | "kingdom" | "phylum" | "class" | "order" | "family" | "genus", string>
>;

type CatalogAccession = {
  accession: string;
  assembly: string;
  source?: string;
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
  metrics?: {
    fasta_size_bytes?: number;
    tarball_size_bytes?: number;
    timings_sec?: Record<string, number>;
  };
  seq_ids?: string[];
  seq_count?: number;
  group?: string;
  taxonomy?: Taxonomy;
  common_name?: string;
  published?: string;
  release_date?: string;
  indexed_at?: string;
  storage?: string;
  download_url?: string;
  doi?: string;
  bioc_url?: string;
  _bioc?: boolean;
  // Set by scripts/backfill-ensembl-urls.py when a build's species was
  // probed against every plausible Ensembl URL and all 404'd. The UI uses
  // this to suppress the Ensembl chip for cases the upstream really
  // doesn't host, instead of offering a link that lands on 404.
  _ensembl_status?: "not_indexed";
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

type SpeciesMetadata = {
  organism: string;
  canonical_name?: string;
  scientific_name?: string;
  common_name?: string;
  group?: string;
  rank?: string;
  taxid?: number;
  species_taxid?: number;
  assembly_level?: string;
  release_date?: string;
  image_url?: string;
  sources?: string[];
  taxonomy?: Taxonomy;
  aliases?: string[];
};

type SpeciesMetadataIndex = {
  version: number;
  total: number;
  shards: { key: string; path: string; count: number }[];
};

type SpeciesMetadataShard = {
  version: number;
  key: string;
  entries: Record<string, SpeciesMetadata>;
};

type SpeciesMetadataShardState =
  | SpeciesMetadataShard
  | "loading"
  | "missing";

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

type Kingdom = "all" | "animal" | "plant" | "fungi" | "prokaryote";
type AvailabilityFilter = "built" | "unbuilt" | "catalog";
type DataSourceFilter = "all" | "ncbi" | "ensembl" | "bioconductor";
type PackageDataSource = Exclude<DataSourceFilter, "all">;

function stripGenusBrackets(name: string): string {
  return cleanOrganismName(name);
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

function metadataLookupKey(name: string): string {
  return stripGenusBrackets(name).trim().replace(/\s+/g, " ").toLowerCase();
}

function metadataShardKey(name: string): string {
  const first = speciesName(name)[0]?.toUpperCase();
  return first && first >= "A" && first <= "Z" ? first : "_";
}

function mergeTaxonomy(
  primary?: Taxonomy,
  fallback?: Taxonomy
): Taxonomy | undefined {
  const merged = { ...(fallback ?? {}), ...(primary ?? {}) };
  return Object.keys(merged).length > 0 ? merged : undefined;
}

function metadataForOrganism(
  org: OrganismEntry,
  metadata: Map<string, SpeciesMetadata>
): SpeciesMetadata | undefined {
  const candidates = [
    org.organism,
    org.canonical_name ?? "",
    speciesName(org.organism),
  ]
    .filter(Boolean)
    .map(metadataLookupKey);

  for (const candidate of candidates) {
    const found = metadata.get(candidate);
    if (found) return found;
  }
  return undefined;
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

function formatMegabases(sizeMb?: number): string {
  if (!sizeMb || sizeMb <= 0) return "";
  return `${sizeMb.toLocaleString(undefined, {
    maximumFractionDigits: 1,
  })} Mb`;
}

function normalizeComparable(value?: string): string {
  return (value ?? "").trim().toLowerCase();
}

function genomeSizeForBuild(
  build: BuildPackage,
  accessions: CatalogAccession[]
): { sizeMb: number; approximate: boolean } | undefined {
  const candidates = accessions.filter(
    (accession) => typeof accession.size_mb === "number" && accession.size_mb > 0
  );
  if (candidates.length === 0) return undefined;

  const buildAccession = normalizeComparable(build.accession);
  const exactAccession = candidates.find(
    (accession) => normalizeComparable(accession.accession) === buildAccession
  );
  if (exactAccession?.size_mb) {
    return { sizeMb: exactAccession.size_mb, approximate: false };
  }

  const buildAssembly = normalizeComparable(build.assembly);
  if (!buildAssembly) {
    const onlyCandidate = candidates.length === 1 ? candidates[0] : undefined;
    return onlyCandidate?.size_mb
      ? { sizeMb: onlyCandidate.size_mb, approximate: true }
      : undefined;
  }

  const buildSource = buildDataSource(build);
  const sameSourceAssembly = candidates.find(
    (accession) =>
      normalizeComparable(accession.assembly) === buildAssembly &&
      catalogAccessionSource(accession) === buildSource
  );
  if (sameSourceAssembly?.size_mb) {
    return { sizeMb: sameSourceAssembly.size_mb, approximate: false };
  }

  const assemblyMatch = candidates.find(
    (accession) => normalizeComparable(accession.assembly) === buildAssembly
  );
  if (assemblyMatch?.size_mb) {
    return { sizeMb: assemblyMatch.size_mb, approximate: false };
  }

  const onlyCandidate = candidates.length === 1 ? candidates[0] : undefined;
  return onlyCandidate?.size_mb
    ? { sizeMb: onlyCandidate.size_mb, approximate: true }
    : undefined;
}

function genomeSizeLabelForBuild(
  build: BuildPackage,
  accessions: CatalogAccession[]
): { label: string; value: string } | null {
  const genomeSizeForPackage = genomeSizeForBuild(build, accessions);
  const genomeSize = formatMegabases(genomeSizeForPackage?.sizeMb);
  if (genomeSize) {
    return {
      label: genomeSizeForPackage?.approximate
        ? "Approx. genome size"
        : "Genome size",
      value: genomeSize,
    };
  }

  const fastaSize = formatBytes(build.metrics?.fasta_size_bytes);
  if (fastaSize) {
    return { label: "FASTA size", value: fastaSize };
  }

  return null;
}

function genomeSizeLabelForCatalog(
  accessions: CatalogAccession[]
): { label: string; value: string } | null {
  const exact = accessions.find(
    (accession) => typeof accession.size_mb === "number" && accession.size_mb > 0
  );
  const genomeSize = formatMegabases(exact?.size_mb);
  return genomeSize ? { label: "Genome size", value: genomeSize } : null;
}

function preferNcbiForAccession(accession: CatalogAccession): boolean {
  return accession.accession.startsWith("GC");
}

function preferredCatalogAccession(
  accessions: CatalogAccession[]
): CatalogAccession | undefined {
  return (
    accessions.find(
      (accession) =>
        preferNcbiForAccession(accession) &&
        typeof accession.size_mb === "number" &&
        accession.size_mb > 0
    ) ??
    accessions.find((accession) => preferNcbiForAccession(accession)) ??
    accessions.find(
      (accession) => typeof accession.size_mb === "number" && accession.size_mb > 0
    ) ??
    accessions[0]
  );
}

function formatMetadataDate(value?: string): string {
  if (!value) return "";
  const normalized = value.replace(/\//g, "-");
  const date = new Date(normalized);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString();
}

function sanitizePackageToken(value?: string): string {
  if (!value) return "";
  return value
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^A-Za-z0-9]/g, "");
}

function packageAssemblyToken(packageName: string): string {
  const parts = packageName.split(".");
  return parts.length === 4 ? parts[3] : "";
}

function assemblyNameNote(build: BuildPackage): string {
  const assembly = build.assembly?.trim();
  if (!assembly) return "";

  const normalized = sanitizePackageToken(assembly);
  const token = packageAssemblyToken(build.package);
  if (!normalized || !token || normalized === assembly || normalized !== token) {
    return "";
  }

  return `Package name uses ${token} because BSgenome package names must have exactly four dot-separated parts; the original assembly name is ${assembly}.`;
}

function sourceUrl(build: BuildPackage): string {
  if (build.source_url) return build.source_url;
  if (build.accession?.startsWith("GC")) {
    return `https://www.ncbi.nlm.nih.gov/datasets/genome/${build.accession}/`;
  }
  return "";
}

function ncbiAccessionLink(accession: string): { label: string; url: string } {
  return {
    label: "NCBI",
    url: `https://www.ncbi.nlm.nih.gov/datasets/genome/${accession}/`,
  };
}

function ensemblAccessionLink(
  accession: CatalogAccession,
  speciesQuery: string,
  group: string | undefined
): { label: string; url: string } {
  const subdomain = ensemblSubdomain(group);
  const slug = ensemblSlug(speciesQuery, group, accession.accession);
  return {
    label: "Ensembl",
    url: `https://${subdomain}/${slug}/Info/Index`,
  };
}

function catalogAccessionSourceLink(
  accession: CatalogAccession,
  speciesQuery: string,
  group: string | undefined
): { label: string; url: string } | null {
  const source = (accession.source ?? "").toLowerCase();

  // The compact catalog usually stores only an accession, not a verified
  // Ensembl species URL. For INSDC assembly accessions, NCBI Datasets is the
  // stable canonical page; generated EnsemblGenomes URLs often 403/500 for
  // multi-assembly and "sp." entries.
  if (preferNcbiForAccession(accession)) {
    return ncbiAccessionLink(accession.accession);
  }

  if (
    source.includes("ensembl") ||
    (source === "ensembl" && accession.accession.startsWith("GCA_"))
  ) {
    return ensemblAccessionLink(accession, speciesQuery, group);
  }

  if (
    source.includes("ncbi") ||
    source.includes("refseq") ||
    source.includes("genbank") ||
    accession.accession.startsWith("GC")
  ) {
    return ncbiAccessionLink(accession.accession);
  }

  return null;
}

function catalogAccessionSourceLinks(
  accessions: CatalogAccession[],
  speciesQuery: string,
  group: string | undefined
): { label: string; url: string }[] {
  const links = new Map<string, { label: string; url: string }>();

  for (const accession of accessions) {
    const link = catalogAccessionSourceLink(accession, speciesQuery, group);
    if (link && !links.has(link.label)) {
      links.set(link.label, link);
    }
  }

  const order: Record<string, number> = { NCBI: 0, Ensembl: 1 };
  return [...links.values()].sort(
    (a, b) =>
      (order[a.label] ?? 99) - (order[b.label] ?? 99) ||
      a.label.localeCompare(b.label)
  );
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

function normalizedEnsemblUrl(url: string, group?: string): string {
  const expectedHost = ensemblSubdomain(group);
  try {
    const parsed = new URL(url);
    const isEnsemblHost =
      parsed.hostname === "www.ensembl.org" ||
      parsed.hostname === "useast.ensembl.org" ||
      parsed.hostname === "uswest.ensembl.org" ||
      parsed.hostname.endsWith(".ensembl.org");

    if (isEnsemblHost && expectedHost !== "www.ensembl.org") {
      parsed.hostname = expectedHost;
      return parsed.toString();
    }
  } catch {
    return url;
  }

  return url;
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

  // Capital Genus, lowercase species. Ensembl uses /Arabidopsis_thaliana,
  // not /Arabidopsis_Thaliana (the latter 301-redirects to the canonical
  // form). Keep the redirect-free URL.
  const parts = cleaned.split(/\s+/).filter(Boolean);
  if (parts.length === 0) return cleaned;
  const genus = parts[0].charAt(0).toUpperCase() + parts[0].slice(1).toLowerCase();
  const rest = parts.slice(1).map((p) => p.toLowerCase());
  return [genus, ...rest].join("_");
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
      return { label: "Ensembl", url: normalizedEnsemblUrl(build.source_url, group) };
    }
    // The backfill script already verified this species isn't on any
    // Ensembl subdomain. Don't offer a chip that will lead to a 404.
    if (build._ensembl_status === "not_indexed") {
      return null;
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
  return warningFreeInstallCommand(build.download_url);
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

function matchesAvailability(
  org: OrganismEntry,
  availability: AvailabilityFilter
): boolean {
  const builds = org.builds ?? [];
  const accessions = org._accessions ?? [];
  switch (availability) {
    case "built":
      return builds.length > 0;
    case "unbuilt":
      return builds.length === 0 && accessions.length > 0;
    case "catalog":
      return true;
  }
}

function catalogAccessionSource(accession: CatalogAccession): DataSourceFilter | "" {
  const raw = (accession.source ?? "").toLowerCase();
  if (raw.includes("ensembl")) return "ensembl";
  if (
    raw.includes("ncbi") ||
    raw.includes("refseq") ||
    raw.includes("genbank") ||
    accession.accession.startsWith("GC")
  ) {
    return "ncbi";
  }
  return "";
}

function buildDataSource(build: BuildPackage): DataSourceFilter | "" {
  if (build._bioc) return "bioconductor";
  const provider = build.provider?.toLowerCase();
  if (provider === "ensembl") return "ensembl";
  if (provider === "ncbi" || build.accession?.startsWith("GC")) return "ncbi";
  return "";
}

const packageSourceOrder: PackageDataSource[] = [
  "bioconductor",
  "ncbi",
  "ensembl",
];

function packageSourceLabel(source: PackageDataSource): string {
  switch (source) {
    case "bioconductor":
      return "Bioconductor";
    case "ncbi":
      return "NCBI";
    case "ensembl":
      return "Ensembl";
  }
}

function packageSourceBadges(builds: BuildPackage[]): PackageDataSource[] {
  const sources = new Set<PackageDataSource>();
  for (const build of builds) {
    const source = buildDataSource(build);
    if (source && source !== "all") {
      sources.add(source);
    }
  }
  return packageSourceOrder.filter((source) => sources.has(source));
}

function matchesDataSource(
  org: OrganismEntry,
  dataSource: DataSourceFilter
): boolean {
  if (dataSource === "all") return true;
  return (
    (org.builds ?? []).some((build) => buildDataSource(build) === dataSource) ||
    (org._accessions ?? []).some(
      (accession) => catalogAccessionSource(accession) === dataSource
    )
  );
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
      const key = metadataLookupKey(organism);
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
    merged.set(metadataLookupKey(org.organism), {
      ...org,
      builds: org.builds ?? [],
      _source: "community",
    });
  }

  let biocCount = 0;
  for (const build of biocPackages ?? []) {
    const organism = build.organism || "Unknown";
    const key = metadataLookupKey(organism);
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
    const key = metadataLookupKey(row.o);
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
      cleanOrganismName(a.organism).localeCompare(cleanOrganismName(b.organism))
    ),
    flat,
    biocCount,
  };
}

function filterOrganisms(
  organisms: OrganismEntry[],
  kingdom: Kingdom,
  availability: AvailabilityFilter,
  dataSource: DataSourceFilter,
  query: string,
  letter: string
): OrganismEntry[] {
  const normalized = query.trim().toLowerCase();
  return organisms.filter((org) => {
    if (!matchesKingdom(org.group, kingdom)) return false;
    if (!matchesAvailability(org, availability)) return false;
    if (!matchesDataSource(org, dataSource)) return false;

    if (letter && speciesName(org.organism)[0]?.toUpperCase() !== letter) {
      return false;
    }

    if (normalized.length >= 2) {
      const builds = org.builds ?? [];
      const haystack = [
        org.organism,
        cleanOrganismName(org.organism),
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

type ProviderToneKey = "bioconductor" | "ensembl" | "ncbi" | "ucsc" | "default";

function providerToneKey(provider?: string): ProviderToneKey {
  const normalized = provider?.toLowerCase() ?? "";
  if (normalized.includes("bioconductor") || normalized === "bioc") {
    return "bioconductor";
  }
  if (normalized.includes("ensembl")) return "ensembl";
  if (normalized.includes("ucsc")) return "ucsc";
  if (
    !normalized ||
    normalized.includes("ncbi") ||
    normalized.includes("refseq") ||
    normalized.includes("genbank")
  ) {
    return "ncbi";
  }
  return "default";
}

function providerTone(provider?: string): string {
  switch (providerToneKey(provider)) {
    case "bioconductor":
      return "border-emerald-200 bg-emerald-50 text-emerald-800";
    case "ensembl":
      return "border-amber-200 bg-amber-50 text-amber-800";
    case "ucsc":
      return "border-violet-200 bg-violet-50 text-violet-800";
    case "ncbi":
      return "border-blue-200 bg-blue-50 text-blue-800";
    default:
      return "border-slate-200 bg-slate-50 text-slate-700";
  }
}

function sourceChipTone(label?: string): string {
  switch (providerToneKey(label)) {
    case "bioconductor":
      return "border-emerald-300 bg-emerald-50 text-emerald-700 hover:border-emerald-500 hover:bg-emerald-100 hover:text-emerald-800";
    case "ensembl":
      return "border-amber-200 bg-amber-50 text-amber-700 hover:border-amber-300 hover:bg-amber-100 hover:text-amber-800";
    case "ucsc":
      return "border-violet-300 bg-violet-50 text-violet-700 hover:border-violet-500 hover:bg-violet-100 hover:text-violet-800";
    case "ncbi":
      return "border-blue-300 bg-blue-50 text-blue-700 hover:border-blue-500 hover:bg-blue-100 hover:text-blue-800";
    default:
      return "border-border bg-background text-muted-foreground hover:border-primary hover:text-primary";
  }
}

function sourcePillTone(label?: string): string {
  switch (providerToneKey(label)) {
    case "bioconductor":
      return "border-emerald-200 bg-emerald-50 text-emerald-700";
    case "ensembl":
      return "border-amber-200 bg-amber-50 text-amber-700";
    case "ucsc":
      return "border-violet-200 bg-violet-50 text-violet-700";
    case "ncbi":
      return "border-blue-200 bg-blue-50 text-blue-700";
    default:
      return "border-border bg-secondary text-muted-foreground";
  }
}

function neutralPillTone(kind: "group" | "count"): string {
  if (kind === "count") {
    return "border-slate-200 bg-slate-100 text-slate-800";
  }
  return "border-border bg-background text-foreground";
}

function downloadButtonTone(provider?: string): string {
  switch (providerToneKey(provider)) {
    case "bioconductor":
      return "border-emerald-700 bg-emerald-600 text-white shadow-emerald-100 hover:border-emerald-800 hover:bg-emerald-700 focus-visible:ring-emerald-600";
    case "ensembl":
      return "border-amber-300 bg-amber-50 text-amber-900 shadow-amber-100 hover:border-amber-400 hover:bg-amber-100 focus-visible:ring-amber-300";
    case "ucsc":
      return "border-violet-700 bg-violet-600 text-white shadow-violet-100 hover:border-violet-800 hover:bg-violet-700 focus-visible:ring-violet-600";
    case "ncbi":
      return "border-blue-800 bg-blue-700 text-white shadow-blue-100 hover:border-blue-900 hover:bg-blue-800 focus-visible:ring-blue-700";
    default:
      return "border-primary bg-primary text-primary-foreground shadow-primary/20 hover:bg-primary/90 focus-visible:ring-primary";
  }
}

function initialSearchQuery(): string {
  if (typeof window === "undefined") return "";
  const params = new URLSearchParams(window.location.search);
  return params.get("q") ?? params.get("search") ?? "";
}

export function RepositoryBrowser() {
  const [organisms, setOrganisms] = useState<OrganismEntry[]>([]);
  const [flatCount, setFlatCount] = useState(0);
  const [biocCount, setBiocCount] = useState(0);
  const [metadataIndex, setMetadataIndex] = useState<SpeciesMetadataIndex | null>(null);
  const [metadataShards, setMetadataShards] = useState<
    Record<string, SpeciesMetadataShardState>
  >({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [query, setQuery] = useState(initialSearchQuery);
  const [kingdom, setKingdom] = useState<Kingdom>("all");
  const [availability, setAvailability] = useState<AvailabilityFilter>("built");
  const [dataSource, setDataSource] = useState<DataSourceFilter>("all");
  const [letter, setLetter] = useState("");
  const [visibleLimit, setVisibleLimit] = useState({
    filterKey: "",
    count: INITIAL_LIMIT,
  });
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [copied, setCopied] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError("");

      const [community, biocPackages, catalog, speciesMetadataIndex] =
        await Promise.all([
        fetchRepositoryJson<RepositoryData | BuildPackage[]>("packages.json"),
        fetchRepositoryJson<BuildPackage[]>("bioc-packages.json"),
        fetchRepositoryJson<CatalogRow[]>("catalog.json"),
        fetchRepositoryJson<SpeciesMetadataIndex>("species-metadata/index.json"),
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
      setMetadataIndex(speciesMetadataIndex);

      setLoading(false);
    }

    void load();

    return () => {
      cancelled = true;
    };
  }, []);

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
      if (!matchesAvailability(org, availability)) continue;
      if (!matchesDataSource(org, dataSource)) continue;
      c.all += 1;
      if (isAnimal(org.group)) c.animal += 1;
      if (isPlant(org.group)) c.plant += 1;
      if (isFungi(org.group)) c.fungi += 1;
      if (isProkaryote(org.group)) c.prokaryote += 1;
    }
    return c;
  }, [organisms, availability, dataSource]);

  const availabilityCounts = useMemo(() => {
    const c = { built: 0, unbuilt: 0, catalog: 0 };
    for (const org of organisms) {
      if (!matchesKingdom(org.group, kingdom)) continue;
      if (!matchesDataSource(org, dataSource)) continue;
      if (matchesAvailability(org, "built")) c.built += 1;
      if (matchesAvailability(org, "unbuilt")) c.unbuilt += 1;
      c.catalog += 1;
    }
    return c;
  }, [organisms, kingdom, dataSource]);

  const dataSourceCounts = useMemo(() => {
    const c = { all: 0, ncbi: 0, ensembl: 0, bioconductor: 0 };
    for (const org of organisms) {
      if (!matchesKingdom(org.group, kingdom)) continue;
      if (!matchesAvailability(org, availability)) continue;
      c.all += 1;
      if (matchesDataSource(org, "ncbi")) c.ncbi += 1;
      if (matchesDataSource(org, "ensembl")) c.ensembl += 1;
      if (matchesDataSource(org, "bioconductor")) c.bioconductor += 1;
    }
    return c;
  }, [organisms, kingdom, availability]);

  const availableLetters = useMemo(() => {
    const set = new Set<string>();
    for (const org of filterOrganisms(organisms, kingdom, availability, dataSource, query, "")) {
      const first = speciesName(org.organism)[0]?.toUpperCase();
      if (first) set.add(first);
    }
    return set;
  }, [kingdom, availability, dataSource, organisms, query]);

  const filtered = useMemo(
    () => filterOrganisms(organisms, kingdom, availability, dataSource, query, letter),
    [kingdom, availability, dataSource, letter, organisms, query]
  );

  const filterKey = `${query}\u0000${kingdom}\u0000${availability}\u0000${dataSource}\u0000${letter}`;
  const visibleCount =
    visibleLimit.filterKey === filterKey ? visibleLimit.count : INITIAL_LIMIT;
  const displayed = filtered.slice(0, visibleCount);
  const metadataEntries = useMemo(() => {
    const entries = new Map<string, SpeciesMetadata>();
    for (const shard of Object.values(metadataShards)) {
      if (!shard || shard === "loading" || shard === "missing") continue;
      for (const [key, value] of Object.entries(shard.entries ?? {})) {
        entries.set(key, value);
      }
    }
    return entries;
  }, [metadataShards]);

  const metadataShardPaths = useMemo(() => {
    const paths = new Map<string, string>();
    for (const shard of metadataIndex?.shards ?? []) {
      paths.set(shard.key, shard.path);
    }
    return paths;
  }, [metadataIndex]);

  const missingMetadataShardKeys = useMemo(() => {
    if (!metadataIndex) return [];
    const keys = new Set<string>();
    for (const org of displayed) {
      const key = metadataShardKey(org.canonical_name ?? org.organism);
      if (!metadataShardPaths.has(key)) continue;
      if (Object.prototype.hasOwnProperty.call(metadataShards, key)) continue;
      keys.add(key);
    }
    return [...keys];
  }, [displayed, metadataIndex, metadataShardPaths, metadataShards]);
  const missingMetadataShardKey = missingMetadataShardKeys.join("|");

  useEffect(() => {
    if (missingMetadataShardKeys.length === 0) return;
    let cancelled = false;

    setMetadataShards((previous) => {
      const next = { ...previous };
      for (const key of missingMetadataShardKeys) {
        next[key] = "loading";
      }
      return next;
    });

    async function loadShards() {
      const results = await Promise.all(
        missingMetadataShardKeys.map(async (key) => {
          const path = metadataShardPaths.get(key);
          if (!path) return [key, null] as const;
          const shard = await fetchRepositoryJson<SpeciesMetadataShard>(
            `species-metadata/${path}`
          );
          return [key, shard] as const;
        })
      );

      if (cancelled) return;
      setMetadataShards((previous) => {
        const next = { ...previous };
        for (const [key, shard] of results) {
          next[key] = shard ?? "missing";
        }
        return next;
      });
    }

    void loadShards();

    return () => {
      cancelled = true;
    };
  }, [missingMetadataShardKey, missingMetadataShardKeys, metadataShardPaths]);

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
    { key: "all", label: "All taxa", count: kingdomCounts.all },
    { key: "animal", label: "Animals", count: kingdomCounts.animal },
    { key: "plant", label: "Plants", count: kingdomCounts.plant },
    { key: "fungi", label: "Fungi", count: kingdomCounts.fungi },
    { key: "prokaryote", label: "Prokaryotes", count: kingdomCounts.prokaryote },
  ];

  const availabilityOptions: {
    key: AvailabilityFilter;
    label: string;
    count: number;
  }[] = [
    { key: "built", label: "Already built", count: availabilityCounts.built },
    { key: "unbuilt", label: "Not built yet", count: availabilityCounts.unbuilt },
    { key: "catalog", label: "Full catalog", count: availabilityCounts.catalog },
  ];

  const dataSourceOptions: {
    key: DataSourceFilter;
    label: string;
    count: number;
  }[] = [
    { key: "all", label: "All sources", count: dataSourceCounts.all },
    { key: "ncbi", label: "NCBI", count: dataSourceCounts.ncbi },
    { key: "ensembl", label: "Ensembl", count: dataSourceCounts.ensembl },
    { key: "bioconductor", label: "Bioconductor", count: dataSourceCounts.bioconductor },
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
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
              <div className="min-w-0 flex-1">
                <div className="text-sm font-medium text-foreground">
                  How to install
                </div>
                <div className="mt-3 grid gap-3 lg:grid-cols-2">
                  <div className="flex min-w-0 gap-3">
                    <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary font-mono text-xs font-semibold text-primary-foreground">
                      1
                    </span>
                    <div className="min-w-0">
                      <p className="text-sm text-foreground">
                        Each package card below shows a ready-to-copy R command
                        that downloads the tarball first, then installs it from a
                        local temporary file.
                      </p>
                      <code className="mt-2 block overflow-x-auto rounded-md bg-secondary px-3 py-2 font-mono text-xs text-foreground">
                        local(&#123;url &lt;- &quot;TARBALL_URL&quot;; tarball &lt;- tempfile(fileext = &quot;.tar.gz&quot;); on.exit(unlink(tarball), add = TRUE); download.file(url, tarball, mode = &quot;wb&quot;, method = &quot;libcurl&quot;); install.packages(tarball, repos = NULL, type = &quot;source&quot;)&#125;)
                      </code>
                    </div>
                  </div>
                  <div className="flex min-w-0 gap-3">
                    <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary font-mono text-xs font-semibold text-primary-foreground">
                      2
                    </span>
                    <p className="text-sm leading-6 text-foreground">
                      You can also click Download to grab the tarball and install offline.
                    </p>
                  </div>
                </div>
              </div>
              <a
                href={`${siteConfig.githubUrl}/releases`}
                target="_blank"
                rel="noreferrer"
                className="inline-flex h-8 shrink-0 items-center justify-center gap-1.5 rounded-lg border border-border px-2.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              >
                <Database className="size-4" />
                All tarballs
              </a>
            </div>
          </div>

        </div>
      </section>

      <section className="mx-auto max-w-6xl px-6 py-6">
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search organism, package, accession, assembly..."
            className="pl-9 pr-10"
          />
          {query && (
            <button
              type="button"
              aria-label="Clear search"
              className="absolute right-2 top-1/2 inline-flex size-7 -translate-y-1/2 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              onClick={() => setQuery("")}
            >
              <X className="size-4" />
            </button>
          )}
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          {dataSourceOptions.map((option) => (
            <Button
              key={option.key}
              type="button"
              variant={dataSource === option.key ? "default" : "outline"}
              onClick={() => setDataSource(option.key)}
            >
              {option.label}
              <span className="font-mono text-xs opacity-75">
                {option.count.toLocaleString()}
              </span>
            </Button>
          ))}
        </div>

        <div className="mt-3 flex flex-wrap gap-2">
          {kingdomOptions.map((option) => (
            <Button
              key={option.key}
              type="button"
              variant={kingdom === option.key ? "default" : "outline"}
              onClick={() => setKingdom(option.key)}
            >
              {option.label}
              <span className="font-mono text-xs opacity-75">
                {option.count.toLocaleString()}
              </span>
            </Button>
          ))}
        </div>

        <div className="mt-3 flex flex-wrap gap-2">
          {availabilityOptions.map((option) => (
            <Button
              key={option.key}
              type="button"
              variant={availability === option.key ? "default" : "outline"}
              onClick={() => setAvailability(option.key)}
            >
              {option.label}
              <span className="font-mono text-xs opacity-75">
                {option.count.toLocaleString()}
              </span>
            </Button>
          ))}
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
            const firstAccession = preferredCatalogAccession(accessions);
            const catalogOnly = builds.length === 0 && accessions.length > 0;
            const visibleBuilds = isOpen ? builds : builds.slice(0, 1);
            const metadata = metadataForOrganism(org, metadataEntries);
            const displayName =
              metadata?.canonical_name ??
              metadata?.scientific_name ??
              org.canonical_name ??
              org.organism;
            const commonName = org.common_name || metadata?.common_name;
            const displayGroup = org.group || metadata?.group;
            const displayTaxonomy = mergeTaxonomy(org.taxonomy, metadata?.taxonomy);
            const crumbs = taxonomyBreadcrumb(displayTaxonomy);
            const catalogSource = firstAccession
              ? catalogAccessionSourceLink(
                  firstAccession,
                  speciesName(displayName),
                  displayGroup
                )
              : null;
            const catalogSources = catalogOnly
              ? catalogAccessionSourceLinks(
                  accessions,
                  speciesName(displayName),
                  displayGroup
                )
              : [];
            const catalogGenomeSize = catalogOnly
              ? genomeSizeLabelForCatalog(accessions)
              : null;
            const packageSources = packageSourceBadges(builds);
            const imageUrl = metadata?.image_url ?? null;

            return (
              <Card key={key} className="rounded-lg py-0">
                <CardContent className="px-0">
                  <div className="flex flex-col gap-4 p-4 md:flex-row md:items-start md:justify-between">
                    {imageUrl && (
                      <SpeciesImage
                        src={imageUrl}
                        alt={`${speciesName(displayName)} reference image`}
                        fit="contain"
                        fallback="hidden"
                        className="hidden h-16 w-16 shrink-0 rounded-md border border-border bg-background p-1 md:block"
                      />
                    )}
                    <div className="min-w-0 flex-1">
                      {(() => {
                        // Prefer the offline-enriched canonical name when
                        // present, otherwise fall back to the raw NCBI
                        // assembly metadata string.
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
                              {commonName && (
                                <span className="text-sm text-muted-foreground">
                                  {commonName}
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
                        <span
                          className={cn(
                            "inline-flex h-6 items-center rounded-full border px-2.5 text-xs font-medium",
                            neutralPillTone("group")
                          )}
                        >
                          {groupLabel(displayGroup)}
                        </span>
                        {builds.length > 0 && (
                          <span
                            className={cn(
                              "inline-flex h-6 items-center gap-1 rounded-full border px-2.5 text-xs font-medium",
                              neutralPillTone("count")
                            )}
                          >
                            <Package className="size-3" />
                            {builds.length} build{builds.length === 1 ? "" : "s"}
                          </span>
                        )}
                        {packageSources.map((source) => {
                          const label = packageSourceLabel(source);
                          return (
                            <span
                              key={source}
                              title={`${label} package source available`}
                              className={cn(
                                "inline-flex h-6 cursor-text items-center rounded-full border px-2.5 text-xs font-medium",
                                sourcePillTone(label)
                              )}
                            >
                              {label}
                            </span>
                          );
                        })}
                        {catalogOnly && (
                          <Badge
                            className="border-primary/30 bg-primary/10 text-primary"
                            title="No BSgenome package built yet. Click Build to start one."
                          >
                            Build on click
                          </Badge>
                        )}
                        {catalogSources.map((source) => (
                          <a
                            key={source.label}
                            href={source.url}
                            target="_blank"
                            rel="noreferrer"
                            title={`View this reference on ${source.label}`}
                            className={cn(
                              "inline-flex h-6 items-center gap-1 rounded border px-2 font-mono text-[10px] uppercase tracking-[0.1em] transition-colors",
                              sourceChipTone(source.label)
                            )}
                          >
                            {source.label}
                            <ExternalLink className="size-3" />
                          </a>
                        ))}
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
                      {metadata && (
                        <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
                          {metadata.taxid && (
                            <a
                              href={`https://www.ncbi.nlm.nih.gov/Taxonomy/Browser/wwwtax.cgi?id=${metadata.taxid}`}
                              target="_blank"
                              rel="noreferrer"
                              className="text-primary hover:underline"
                            >
                              TaxID: {metadata.taxid}
                            </a>
                          )}
                          {metadata.species_taxid &&
                            metadata.species_taxid !== metadata.taxid && (
                              <a
                                href={`https://www.ncbi.nlm.nih.gov/Taxonomy/Browser/wwwtax.cgi?id=${metadata.species_taxid}`}
                                target="_blank"
                                rel="noreferrer"
                                className="text-primary hover:underline"
                              >
                                Species TaxID: {metadata.species_taxid}
                              </a>
                            )}
                          {metadata.assembly_level && (
                            <span>Assembly level: {metadata.assembly_level}</span>
                          )}
                          {metadata.release_date && (
                            <span>
                              Genome release:{" "}
                              {formatMetadataDate(metadata.release_date)}
                            </span>
                          )}
                        </div>
                      )}
                      {catalogOnly && firstAccession && (
                        <div className="mt-3 grid gap-x-4 gap-y-1 text-sm text-muted-foreground sm:grid-cols-2 lg:grid-cols-3">
                          {firstAccession.assembly && (
                            <span>
                              Assembly:{" "}
                              <span className="text-foreground">
                                {firstAccession.assembly}
                              </span>
                            </span>
                          )}
                          {firstAccession.accession && (
                            <span className="min-w-0">
                              Accession:{" "}
                              {catalogSource ? (
                                <a
                                  href={catalogSource.url}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="text-primary hover:underline"
                                >
                                  {firstAccession.accession}
                                </a>
                              ) : (
                                <span className="text-foreground">
                                  {firstAccession.accession}
                                </span>
                              )}
                            </span>
                          )}
                          {catalogGenomeSize && (
                            <span>
                              {catalogGenomeSize.label}:{" "}
                              <span className="text-foreground">
                                {catalogGenomeSize.value}
                              </span>
                            </span>
                          )}
                        </div>
                      )}
                    </div>

                    <div className="flex shrink-0 items-center gap-2">
                      {catalogOnly && firstAccession ? (
                        <a
                          href={`/build?accession=${encodeURIComponent(
                            firstAccession.accession
                          )}${
                            firstAccession.source === "ensembl" &&
                            !preferNcbiForAccession(firstAccession)
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
                        const genomeSizeLabel = genomeSizeLabelForBuild(
                          build,
                          accessions
                        );
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
                                    speciesName(displayName),
                                    displayGroup
                                  );
                                  if (!src) return null;
                                  return (
                                    <a
                                      href={src.url}
                                      target="_blank"
                                      rel="noreferrer"
                                      title={`View this build's reference on ${src.label}`}
                                      className={cn(
                                        "inline-flex h-6 items-center gap-1 rounded border px-2 font-mono text-[10px] uppercase tracking-[0.1em] transition-colors",
                                        sourceChipTone(src.label)
                                      )}
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
                                {genomeSizeLabel && (
                                  <span>
                                    {genomeSizeLabel.label}:{" "}
                                    <span className="text-foreground">
                                      {genomeSizeLabel.value}
                                    </span>
                                  </span>
                                )}
                                {build.size && (
                                  <span>
                                    Package size:{" "}
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
                                {build.release_date && (
                                  <span>
                                    Genome release:{" "}
                                    <span className="text-foreground">
                                      {formatMetadataDate(build.release_date)}
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
                                const note = assemblyNameNote(build);
                                if (!note) return null;
                                return (
                                  <div className="mt-2 rounded-md border border-primary/20 bg-primary/5 px-3 py-2 text-xs leading-5 text-muted-foreground">
                                    {note}
                                  </div>
                                );
                              })()}
                              {(() => {
                                const cmd = installCommand(build);

                                // Bioconductor: only the BiocManager command,
                                // no download (Bioc hosts the binary itself).
                                if (build._bioc) {
                                  return (
                                    <div className="mt-4 space-y-2">
                                      <div className="text-right text-xs font-medium uppercase tracking-wide text-foreground/60">
                                        Install from Bioconductor
                                      </div>
                                      <div className="flex justify-end">
                                        <Button
                                          type="button"
                                          size="sm"
                                          variant="outline"
                                          className="bg-background"
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
                                      <div className="rounded-md bg-secondary p-3">
                                        <pre className="m-0 min-w-0 overflow-hidden whitespace-pre-wrap break-all font-mono text-xs leading-5 text-foreground">
                                          {cmd ?? `BiocManager::install("${build.package}")`}
                                        </pre>
                                      </div>
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
                                      Check back later, or open an issue if it&apos;s
                                      been stuck for more than a day.
                                    </div>
                                  );
                                }

                                // Keep the install snippet full width, with
                                // offline download as a secondary compact
                                // action below it.
                                return (
                                  <div className="mt-4 space-y-3">
                                    {/* Method 1 — install in R online */}
                                    <div className="min-w-0 space-y-2">
                                      <div className="text-right text-xs font-medium uppercase tracking-wide text-foreground/60">
                                        Install in R (online)
                                      </div>
                                      <div className="flex justify-end">
                                        <Button
                                          type="button"
                                          size="sm"
                                          variant="outline"
                                          className="bg-background"
                                          onClick={() => copyCommand(cmd, copyKey)}
                                        >
                                          <Copy className="size-3.5" />
                                          {copied === copyKey ? "Copied" : "Copy"}
                                        </Button>
                                      </div>
                                      <div className="rounded-md bg-secondary p-3">
                                        <pre className="m-0 min-w-0 overflow-hidden whitespace-pre-wrap break-all font-mono text-xs leading-5 text-foreground">
                                          {cmd}
                                        </pre>
                                      </div>
                                    </div>

                                    {/* Method 2 — download tarball (compact) */}
                                    <div className="flex flex-col items-end gap-2">
                                      <div className="text-right text-xs font-medium uppercase tracking-wide text-foreground/60">
                                        Or download (offline)
                                      </div>
                                      <a
                                        href={publicPackageDownloadUrl(build.download_url)}
                                        title={`Download ${build.package}`}
                                        className={cn(
                                          "inline-flex min-h-12 w-fit max-w-full items-center justify-start gap-2 rounded-md border px-3.5 py-2 text-sm font-semibold shadow-sm transition-all hover:-translate-y-0.5 hover:shadow-md active:translate-y-0 active:shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 sm:max-w-lg",
                                          downloadButtonTone(build.provider)
                                        )}
                                      >
                                        <Download className="size-4 shrink-0" />
                                        <span className="flex min-w-0 flex-col items-start">
                                          <span className="block max-w-full truncate font-mono text-[11px] leading-4">
                                            {build.package}
                                          </span>
                                          <span className="text-xs font-semibold leading-4 opacity-80">
                                            {build.size
                                              ? `Package: ${formatBytes(build.size)}`
                                              : ".tar.gz package"}
                                          </span>
                                        </span>
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
              onClick={() =>
                setVisibleLimit({
                  filterKey,
                  count: visibleCount + PAGE_SIZE,
                })
              }
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
