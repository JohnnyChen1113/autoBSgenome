import type { Metadata } from "next";
import { RepositoryBrowser } from "@/components/RepositoryBrowser";
import { SiteFooter, SiteHeader } from "@/components/SiteChrome";

export const metadata: Metadata = {
  title: "Packages - AutoBSgenome",
  description:
    "Browse community-built BSgenome packages and install them from the AutoBSgenome repository.",
};

export default function PackagesPage() {
  return (
    <div className="flex min-h-screen flex-col bg-background">
      <SiteHeader active="packages" />
      <RepositoryBrowser />
      <SiteFooter />
    </div>
  );
}
