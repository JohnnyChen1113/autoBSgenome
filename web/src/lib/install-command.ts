const PACKAGE_DOWNLOAD_ORIGIN = "https://packages.autobsgenome.org";
const GITHUB_RELEASE_DOWNLOAD_RE =
  /^https:\/\/github\.com\/JohnnyChen1113\/autoBSgenome\/releases\/download\/([^/]+)\/([^/?#]+)([?#].*)?$/;

function escapeRString(value: string): string {
  return value.replace(/\\/g, "\\\\").replace(/"/g, '\\"');
}

type InstallCommandOptions = {
  fileName?: string;
  size?: number;
  storage?: string;
};

export function publicPackageDownloadUrl(downloadUrl: string): string {
  const match = downloadUrl.match(GITHUB_RELEASE_DOWNLOAD_RE);
  if (!match) return downloadUrl;

  const [, tag, asset, suffix = ""] = match;
  return `${PACKAGE_DOWNLOAD_ORIGIN}/${tag}/${asset}${suffix}`;
}

function zenodoInstallCommand(downloadUrl: string, options: InstallCommandOptions): string {
  const url = escapeRString(downloadUrl);
  const fileName = escapeRString(options.fileName ?? "");
  const expectedSize = Number.isFinite(options.size)
    ? String(Math.trunc(options.size as number))
    : "NA_real_";
  const fileNameExpr = fileName
    ? `"${fileName}"`
    : 'basename(sub("\\\\?.*$", "", url))';

  return `local({options(timeout = 7200); url <- "${url}"; expected_size <- ${expectedSize}; file_name <- ${fileNameExpr}; cache <- tools::R_user_dir("autoBSgenome", "cache"); dir.create(cache, recursive = TRUE, showWarnings = FALSE); tarball <- file.path(cache, file_name); curl <- Sys.which("curl"); if (!nzchar(curl)) stop("curl is required for resumable Zenodo downloads"); status <- system2(curl, c("-L", "--fail", "--retry", "10", "--retry-delay", "10", "--retry-all-errors", "-C", "-", "-o", tarball, url)); if (!identical(status, 0L)) stop("Download incomplete; re-run this command to resume from ", tarball); actual_size <- file.info(tarball)$size; if (!is.na(expected_size) && !is.na(actual_size) && actual_size != expected_size) stop("Downloaded file size mismatch: expected ", expected_size, " bytes, got ", actual_size, " bytes. Delete ", tarball, " and retry."); install.packages(tarball, repos = NULL, type = "source")})`;
}

export function warningFreeInstallCommand(
  downloadUrl: string,
  options: InstallCommandOptions = {}
): string {
  if (options.storage === "zenodo" || /\bzenodo\.org\/records\//.test(downloadUrl)) {
    return zenodoInstallCommand(downloadUrl, options);
  }

  const url = escapeRString(publicPackageDownloadUrl(downloadUrl));
  return `local({options(timeout = 7200); url <- "${url}"; tarball <- tempfile(fileext = ".tar.gz"); on.exit(unlink(tarball), add = TRUE); download.file(url, tarball, mode = "wb", method = "libcurl"); install.packages(tarball, repos = NULL, type = "source")})`;
}
