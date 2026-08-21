export const DEFAULT_BUILD_RETENTION_DAYS = 2;

export function buildRetentionMessage(
  retentionDays = DEFAULT_BUILD_RETENTION_DAYS
): string {
  return `The server-hosted .tar.gz download is public and scheduled for automatic cleanup approximately ${retentionDays} days after build completion. Download and keep a local copy if you need it later.`;
}

export function formatScheduledCleanupAfter(value: string): string {
  const timestamp = Date.parse(value);
  if (!Number.isFinite(timestamp)) return "";
  return `${new Date(timestamp).toISOString().slice(0, 16).replace("T", " ")} UTC`;
}
