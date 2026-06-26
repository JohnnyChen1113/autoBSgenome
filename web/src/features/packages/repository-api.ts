import { siteConfig } from "@/config";

export async function fetchRepositoryJson<T>(path: string): Promise<T | null> {
  try {
    const res = await fetch(`${siteConfig.repositoryBase}/${path}?t=${Date.now()}`);
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}
