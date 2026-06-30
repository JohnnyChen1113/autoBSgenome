const BS_GENOME_PACKAGE_RE = /^[A-Za-z][A-Za-z0-9.]*[A-Za-z0-9]$/;
const PLACEHOLDER_EPITHETS = new Set([
  "sp",
  "cf",
  "aff",
  "subsp",
  "var",
  "ssp",
  "str",
]);

export type PackageNameResult = {
  name: string | null;
  reason: string;
};

export function cleanOrganismName(value: string): string {
  return value
    .replace(/\[([^\]]+)\]/g, "$1")
    .replace(/[\u0027\u0022\u2018\u2019\u201c\u201d]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

function stripAccents(value: string): string {
  return value.normalize("NFKD").replace(/[\u0300-\u036f]/g, "");
}

function alphaOnly(value: string): string {
  return stripAccents(value).replace(/[^A-Za-z]/g, "");
}

function pickSpeciesEpithet(parts: string[]): string {
  for (let i = 1; i < parts.length; i += 1) {
    const clean = alphaOnly(parts[i]).toLowerCase();
    if (!clean) continue;

    if (PLACEHOLDER_EPITHETS.has(clean)) {
      const nextToken = parts[i + 1];
      if (nextToken && /^[a-z]/.test(nextToken) && alphaOnly(nextToken)) {
        continue;
      }
      return clean;
    }

    return clean;
  }

  return "";
}

export function buildOrganismAbbrev(organism: string): string {
  const parts = cleanOrganismName(organism).split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "";

  const genusFirst = alphaOnly(parts[0]).slice(0, 1).toUpperCase();
  if (!genusFirst) return "";

  const epithet = pickSpeciesEpithet(parts);
  if (!epithet) {
    const genus = alphaOnly(parts[0]).slice(0, 6).toLowerCase();
    return genus ? genus[0].toUpperCase() + genus.slice(1) : "";
  }

  return genusFirst + epithet;
}

export function sanitizePackageComponent(value: string): string {
  return stripAccents(value).replace(/[^A-Za-z0-9]/g, "");
}

export function validateBSgenomePackageName(name: string): string[] {
  const errors: string[] = [];
  const parts = name.split(".");

  if (parts.length !== 4) {
    errors.push("Must have exactly 4 parts separated by dots.");
    return errors;
  }

  if (parts[0] !== "BSgenome") {
    errors.push('Part 1 must be "BSgenome".');
  }
  if (!/^[A-Z][a-z]+$/.test(parts[1])) {
    errors.push(
      "Part 2 (organism) must start with uppercase followed by lowercase (e.g. Hsapiens)."
    );
  }
  if (!/^[A-Za-z]+$/.test(parts[2])) {
    errors.push("Part 3 (provider) must be letters only (e.g. NCBI, UCSC).");
  }
  if (!/^[A-Za-z0-9]+$/.test(parts[3])) {
    errors.push(
      "Part 4 (assembly) must be alphanumeric only (e.g. GRCh38, hg38)."
    );
  }
  if (!BS_GENOME_PACKAGE_RE.test(name) || name.includes("..")) {
    errors.push("Package name must contain only letters, numbers, and dots.");
  }

  return errors;
}

export function buildBSgenomePackageName(
  organism: string,
  provider: string,
  assembly: string
): PackageNameResult {
  if (!organism || !provider || !assembly) {
    return { name: null, reason: "missing organism, provider, or assembly" };
  }

  const abbrev = buildOrganismAbbrev(organism);
  if (!abbrev) {
    return {
      name: null,
      reason: `cannot build abbreviation from organism ${JSON.stringify(organism)}`,
    };
  }

  const providerToken = sanitizePackageComponent(provider);
  if (!providerToken) {
    return {
      name: null,
      reason: `provider ${JSON.stringify(provider)} has no alphanumeric content`,
    };
  }

  const assemblyToken = sanitizePackageComponent(assembly);
  if (!assemblyToken) {
    return {
      name: null,
      reason: `assembly ${JSON.stringify(assembly)} has no alphanumeric content`,
    };
  }

  const name = `BSgenome.${abbrev}.${providerToken}.${assemblyToken}`;
  const errors = validateBSgenomePackageName(name);
  if (errors.length > 0) {
    return {
      name: null,
      reason: `constructed name ${JSON.stringify(name)} failed validation: ${errors.join(" ")}`,
    };
  }

  return { name, reason: "" };
}
