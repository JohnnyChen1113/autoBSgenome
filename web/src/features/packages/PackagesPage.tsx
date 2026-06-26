import { RepositoryBrowser } from "@/features/packages/RepositoryBrowser";
import { SiteFooter, SiteHeader } from "@/components/SiteChrome";

export default function PackagesPage() {
  return (
    <div className="flex min-h-screen flex-col bg-background">
      <SiteHeader active="packages" />
      <RepositoryBrowser />
      <SiteFooter />
    </div>
  );
}
