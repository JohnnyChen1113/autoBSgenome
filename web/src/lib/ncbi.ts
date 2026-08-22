import { buildBSgenomePackageName, cleanOrganismName } from "@/lib/package-name";

const DATASETS_BASE = "https://api.ncbi.nlm.nih.gov/datasets/v2/genome/accession";

export interface NCBIAssemblyInfo {
  accession: string;
  organism: string;
  commonName: string;
  assemblyName: string;
  provider: string;
  releaseDate: string;
  sourceUrl: string;
}

export function extractAccession(input: string): string | null {
  const match = input.match(/(GC[AF]_\d{9}\.\d+)/);
  return match ? match[1] : null;
}

function formatReleaseDate(isoDate: string): string {
  const date = new Date(isoDate);
  const months = [
    "Jan.", "Feb.", "Mar.", "Apr.", "May", "Jun.",
    "Jul.", "Aug.", "Sep.", "Oct.", "Nov.", "Dec.",
  ];
  return `${months[date.getMonth()]} ${date.getFullYear()}`;
}

export function generatePackageName(info: NCBIAssemblyInfo): string {
  const result = buildBSgenomePackageName(
    info.organism,
    info.provider,
    info.assemblyName
  );
  if (!result.name) {
    throw new Error(`Could not generate a valid package name: ${result.reason}`);
  }
  return result.name;
}

export function generateTitle(info: NCBIAssemblyInfo): string {
  return `Full genome sequences for ${info.organism} (${info.provider} version ${info.assemblyName})`;
}

export function generateDescription(
  info: NCBIAssemblyInfo,
  commonName: string
): string {
  return `Full genome sequences for ${info.organism} (${commonName}) as provided by ${info.provider} (${info.assemblyName}, ${info.releaseDate}) and stored in Biostrings objects.`;
}

export async function fetchAssemblyInfo(
  accession: string
): Promise<NCBIAssemblyInfo> {
  const res = await fetch(
    `${DATASETS_BASE}/${accession}/dataset_report`,
    { headers: { Accept: "application/json" } }
  );
  if (!res.ok) throw new Error(`NCBI API error: ${res.status} ${res.statusText}`);
  const data = await res.json();

  const report = data.reports?.[0];
  if (!report) throw new Error("No assembly found for this accession");

  return {
    accession,
    organism: cleanOrganismName(report.organism?.organism_name ?? ""),
    commonName: report.organism?.common_name ?? "",
    assemblyName: report.assembly_info?.assembly_name ?? "",
    provider: "NCBI",
    releaseDate: report.assembly_info?.release_date
      ? formatReleaseDate(report.assembly_info.release_date)
      : "",
    sourceUrl: `https://www.ncbi.nlm.nih.gov/datasets/genome/${accession}/`,
  };
}
