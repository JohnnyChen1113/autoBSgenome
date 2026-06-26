const metaEnv: Record<string, string | undefined> =
  (import.meta as unknown as { env?: Record<string, string | undefined> }).env ??
  {};

const procEnv: Record<string, string | undefined> =
  typeof process !== "undefined" && process.env ? process.env : {};

function publicEnv(key: string): string | undefined {
  return metaEnv[key] ?? procEnv[key];
}

export const siteConfig = {
  name: publicEnv("VITE_APP_NAME") ?? "AutoBSgenome",
  description:
    publicEnv("VITE_APP_DESCRIPTION") ??
    "Build, browse, and automate BSgenome R packages from NCBI and Ensembl assemblies.",
  url: publicEnv("VITE_APP_URL") ?? "https://autobsgenome.org",
  apiBase: publicEnv("VITE_AUTOBSGENOME_API_BASE") ?? "https://api.autobsgenome.org",
  repositoryBase:
    publicEnv("VITE_REPOSITORY_BASE_URL") ??
    "https://johnnychen1113.github.io/autoBSgenome",
  githubUrl: "https://github.com/JohnnyChen1113/autoBSgenome",
  authorUrl: "https://github.com/JohnnyChen1113",
  linLabUrl: "https://zlinlab.org",
  sluUrl: "https://www.slu.edu",
  logo: "/brand-icon.svg",
  favicon: "/favicon.ico",
};

export const sitePaths = ["/", "/build", "/packages", "/help", "/api-docs", "/agents"];
