import { fetchAssemblyInfo, formatReleaseDate } from "./ncbi.ts";

const REST_BASE = "https://rest.ensembl.org";

export interface EnsemblAssemblyInfo {
  species: string;
  organism: string;
  commonName: string;
  assemblyName: string;
  assemblyAccession: string;
  releaseDate: string;
}

export function extractEnsemblSpecies(input: string): string | null {
  let species = input.trim();
  if (/^https?:\/\//i.test(species)) {
    try {
      const url = new URL(species);
      if (url.hostname !== "ensembl.org" && !url.hostname.endsWith(".ensembl.org")) return null;
      species = decodeURIComponent(url.pathname.split("/")[1] ?? "");
    } catch {
      return null;
    }
  }
  return /^[a-z][a-z0-9]*(?:_[a-z0-9]+)+$/i.test(species)
    ? species.toLowerCase()
    : null;
}

export function normalizeEnsemblGroup(value?: string | null): string {
  const normalized = (value ?? "").toLowerCase();
  return ["bacteria", "fungi", "metazoa", "plants", "protists"].includes(normalized)
    ? normalized
    : "vertebrates";
}

export function inferEnsemblGroup(input: string): string {
  try {
    const host = new URL(input).hostname;
    return host.endsWith(".ensembl.org")
      ? normalizeEnsemblGroup(host.slice(0, -".ensembl.org".length))
      : "vertebrates";
  } catch {
    return "vertebrates";
  }
}

export function ensemblSourceUrl(species: string, group: string): string {
  const division = normalizeEnsemblGroup(group);
  const subdomain = division === "vertebrates" ? "www" : division;
  const path = species.charAt(0).toUpperCase() + species.slice(1);
  return `https://${subdomain}.ensembl.org/${path}/Info/Index`;
}

export async function fetchEnsemblAssemblyInfo(
  species: string
): Promise<EnsemblAssemblyInfo> {
  const res = await fetch(
    `${REST_BASE}/info/assembly/${species}?content-type=application/json`
  );
  if (!res.ok) {
    if (res.status === 400)
      throw new Error(`Species "${species}" not found in Ensembl.`);
    throw new Error(`Ensembl API error: ${res.status} ${res.statusText}`);
  }
  const data = await res.json();

  // Get species display info
  let commonName = "";
  let organism = "";
  let releaseDate = formatReleaseDate(data.assembly_date ?? "");
  try {
    const infoRes = await fetch(
      `${REST_BASE}/info/genomes/${data.assembly_accession}?content-type=application/json`
    );
    if (infoRes.ok) {
      const infoData = await infoRes.json();
      commonName = infoData.display_name ?? "";
      organism = infoData.scientific_name ?? "";
    }
  } catch {
    // Optional display metadata must not discard a resolved assembly.
  }
  if ((!releaseDate || !organism) && /^GC[AF]_\d+\.\d+$/.test(data.assembly_accession ?? "")) {
    try {
      const ncbiInfo = await fetchAssemblyInfo(data.assembly_accession);
      organism ||= ncbiInfo.organism;
      commonName ||= ncbiInfo.commonName;
      releaseDate ||= ncbiInfo.releaseDate;
    } catch {
      // Preserve the Ensembl result when optional NCBI enrichment is unavailable.
    }
  }

  // Fallback: derive organism from species name
  if (!organism) {
    const parts = species.split("_");
    organism =
      parts[0].charAt(0).toUpperCase() + parts[0].slice(1) + " " + parts[1];
  }

  return {
    species,
    organism,
    commonName,
    assemblyName: data.assembly_name ?? "",
    assemblyAccession: data.assembly_accession ?? "",
    releaseDate,
  };
}
