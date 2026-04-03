const REST_BASE = "https://rest.ensembl.org";

export interface EnsemblAssemblyInfo {
  species: string;
  organism: string;
  commonName: string;
  assemblyName: string;
  assemblyAccession: string;
  karyotype: string[];
}

export function extractEnsemblSpecies(input: string): string | null {
  // Match: https://www.ensembl.org/Danio_rerio/Info/Index
  const urlMatch = input.match(/ensembl\.org\/([A-Z][a-z]+_[a-z]+)/);
  if (urlMatch) return urlMatch[1].toLowerCase();

  // Match: plain species like "danio_rerio" or "homo_sapiens"
  const speciesMatch = input.match(/^([a-z]+_[a-z]+)$/);
  if (speciesMatch) return speciesMatch[1];

  return null;
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
  const infoRes = await fetch(
    `${REST_BASE}/info/genomes/${data.assembly_accession}?content-type=application/json`
  );

  let commonName = "";
  let organism = "";
  if (infoRes.ok) {
    const infoData = await infoRes.json();
    commonName = infoData.display_name ?? "";
    organism = infoData.scientific_name ?? "";
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
    karyotype: data.karyotype ?? [],
  };
}

export function detectCircularFromKaryotype(
  karyotype: string[]
): string[] {
  const circularNames: string[] = [];
  for (const name of karyotype) {
    const lower = name.toLowerCase();
    if (
      lower === "mt" ||
      lower === "chrm" ||
      lower === "pt" ||
      lower === "pltd"
    ) {
      circularNames.push(name);
    }
  }
  return circularNames;
}
