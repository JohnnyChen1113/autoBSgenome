const PACKAGE_STAGES = [
  "Generating package metadata",
  "Forging BSgenome package",
  "Compressing package archive",
  "Validating package archive",
  "Uploading package release",
] as const;

export function fallbackBuildStepLabels(source: string): string[] {
  if (source === "ncbi") {
    return [
      "Queuing build on GitHub Actions",
      "Resolving NCBI source",
      "Streaming FASTA to 2bit",
      ...PACKAGE_STAGES,
    ];
  }

  return [
    ...(source === "upload" ? ["Uploading FASTA"] : []),
    "Queuing build on GitHub Actions",
    "Streaming FASTA to 2bit",
    ...PACKAGE_STAGES,
  ];
}
