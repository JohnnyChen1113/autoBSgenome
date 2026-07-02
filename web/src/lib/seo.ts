import { siteConfig } from "@/config";

type SeoOptions = {
  title: string;
  description: string;
  path: string;
  keywords?: string;
};

export function absoluteSiteUrl(path = "/"): string {
  const appUrl = siteConfig.url.replace(/\/$/, "");
  return `${appUrl}${path.startsWith("/") ? path : `/${path}`}`;
}

export function seoHead({ title, description, path, keywords }: SeoOptions) {
  const url = absoluteSiteUrl(path);
  return {
    meta: [
      { title },
      { name: "description", content: description },
      ...(keywords ? [{ name: "keywords", content: keywords }] : []),
      { property: "og:title", content: title },
      { property: "og:description", content: description },
      { property: "og:url", content: url },
      { property: "og:site_name", content: siteConfig.name },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
      { name: "twitter:title", content: title },
      { name: "twitter:description", content: description },
    ],
    links: [{ rel: "canonical", href: url }],
  };
}
