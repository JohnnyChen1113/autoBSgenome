const DATASETS_BASE = "https://api.ncbi.nlm.nih.gov/datasets/v2/genome/accession";

export interface NCBIAssemblyInfo {
  accession: string;
  pairedAccession: string | null;
  organism: string;
  commonName: string;
  assemblyName: string;
  provider: string;
  releaseDate: string;
  sourceUrl: string;
}

export interface CircularSequence {
  name: string;
  type: string;
  length: number;
}

export function extractAccession(input: string): string | null {
  const match = input.match(/(GC[AF]_\d{9}\.\d+)/);
  return match ? match[1] : null;
}

function abbreviateOrganism(scientificName: string): string {
  const parts = scientificName.trim().split(/\s+/);
  if (parts.length < 2) return parts[0];
  return parts[0][0].toUpperCase() + parts[1].toLowerCase();
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
  const abbrev = abbreviateOrganism(info.organism);
  const assembly = info.assemblyName.replace(/\./g, "").replace(/[^a-zA-Z0-9]/g, "");
  return `BSgenome.${abbrev}.${info.provider}.${assembly}`;
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
    pairedAccession: report.paired_accession ?? null,
    organism: report.organism?.organism_name ?? "",
    commonName: report.organism?.common_name ?? "",
    assemblyName: report.assembly_info?.assembly_name ?? "",
    provider: "NCBI",
    releaseDate: report.assembly_info?.release_date
      ? formatReleaseDate(report.assembly_info.release_date)
      : "",
    sourceUrl: `https://www.ncbi.nlm.nih.gov/datasets/genome/${accession}/`,
  };
}

export async function fetchCircularSequences(
  accession: string
): Promise<CircularSequence[]> {
  const res = await fetch(
    `${DATASETS_BASE}/${accession}/sequence_reports`,
    { headers: { Accept: "application/json" } }
  );
  if (!res.ok) return [];
  const data = await res.json();

  const circular: CircularSequence[] = [];
  const circularTypes = new Set([
    "Mitochondrion",
    "Chloroplast",
    "Plasmid",
    "Apicoplast",
    "Kinetoplast",
  ]);

  for (const seq of data.reports ?? []) {
    const locType = seq.assigned_molecule_location_type;
    if (locType && circularTypes.has(locType)) {
      circular.push({
        name: seq.chr_name ?? seq.genbank_accession ?? "unknown",
        type: locType,
        length: seq.length ?? 0,
      });
    }
  }
  return circular;
}
