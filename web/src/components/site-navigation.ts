export type NavKey = "home" | "build" | "packages" | "help" | "api" | "agents";

export type SiteNavItem = {
  href: string;
  label: string;
  key: NavKey;
};

export const SITE_NAV_ITEMS: SiteNavItem[] = [
  { href: "/", label: "Home", key: "home" },
  { href: "/packages", label: "Browse", key: "packages" },
  { href: "/build", label: "Build", key: "build" },
  { href: "/help", label: "Help", key: "help" },
  { href: "/api-docs", label: "API", key: "api" },
  { href: "/agents", label: "Agents", key: "agents" },
];
