const PACKAGE_DOWNLOAD_ORIGIN = "https://packages.autobsgenome.org";
const GITHUB_RELEASE_DOWNLOAD_RE =
  /^https:\/\/github\.com\/JohnnyChen1113\/autoBSgenome\/releases\/download\/([^/]+)\/([^/?#]+)([?#].*)?$/;

function escapeRString(value: string): string {
  return value.replace(/\\/g, "\\\\").replace(/"/g, '\\"');
}

export function publicPackageDownloadUrl(downloadUrl: string): string {
  const match = downloadUrl.match(GITHUB_RELEASE_DOWNLOAD_RE);
  if (!match) return downloadUrl;

  const [, tag, asset, suffix = ""] = match;
  return `${PACKAGE_DOWNLOAD_ORIGIN}/${tag}/${asset}${suffix}`;
}

export function warningFreeInstallCommand(downloadUrl: string): string {
  const url = escapeRString(publicPackageDownloadUrl(downloadUrl));
  return [
    `url <- "${url}"`,
    `pkg <- tempfile(fileext = ".tar.gz")`,
    `download.file(url, pkg, mode = "wb", method = "libcurl")`,
    `install.packages(pkg, repos = NULL, type = "source")`,
    `unlink(pkg)`,
  ].join("\n");
}
