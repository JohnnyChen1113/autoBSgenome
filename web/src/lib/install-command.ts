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
  return `local({url <- "${url}"; tarball <- tempfile(fileext = ".tar.gz"); on.exit(unlink(tarball), add = TRUE); download.file(url, tarball, mode = "wb", method = "libcurl"); install.packages(tarball, repos = NULL, type = "source")})`;
}
