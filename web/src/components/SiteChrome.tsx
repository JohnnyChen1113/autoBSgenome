
import { siteConfig } from "@/config";
import { SITE_FOOTER_CONTENT } from "@/components/site-footer";
import { SITE_NAV_ITEMS, type NavKey } from "@/components/site-navigation";

function GithubMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      aria-hidden="true"
      fill="currentColor"
      className={className}
    >
      <path d="M12 .5C5.65.5.5 5.65.5 12c0 5.09 3.29 9.4 7.86 10.93.58.11.79-.25.79-.56 0-.27-.01-1-.02-1.96-3.2.69-3.87-1.54-3.87-1.54-.52-1.33-1.27-1.68-1.27-1.68-1.04-.71.08-.7.08-.7 1.15.08 1.76 1.18 1.76 1.18 1.02 1.75 2.68 1.24 3.34.95.1-.74.4-1.24.72-1.53-2.55-.29-5.24-1.28-5.24-5.69 0-1.26.45-2.29 1.18-3.1-.12-.29-.51-1.46.11-3.05 0 0 .97-.31 3.18 1.18a11.07 11.07 0 0 1 5.79 0c2.2-1.49 3.17-1.18 3.17-1.18.63 1.59.24 2.76.12 3.05.74.81 1.18 1.84 1.18 3.1 0 4.42-2.69 5.4-5.26 5.68.41.36.78 1.07.78 2.16 0 1.56-.01 2.82-.01 3.2 0 .31.21.68.8.56 4.56-1.54 7.85-5.84 7.85-10.93C23.5 5.65 18.35.5 12 .5Z" />
    </svg>
  );
}

function navLinkClass(active: boolean): string {
  // The active indicator is the link's own bottom border, pulled down 1px
  // so it overlaps the header's bottom border. No magic spacing required.
  return [
    "inline-flex items-center font-heading text-[1.18rem] font-semibold tracking-tight transition-colors",
    "border-b-2 -mb-px",
    active
      ? "border-primary text-primary"
      : "border-transparent text-ink hover:text-primary",
  ].join(" ");
}

export function SiteHeader({ active }: { active?: NavKey }) {
  return (
    <header className="sticky top-0 z-40 border-b border-[color:var(--rule)]/10 bg-background/85 backdrop-blur supports-[backdrop-filter]:bg-background/70">
      <div className="mx-auto flex max-w-6xl items-stretch gap-8 px-6">
        <a
          href="/"
          className="flex shrink-0 items-center gap-3 py-3"
        >
          <img
            src="/brand-icon.svg"
            alt="AutoBSgenome logo"
            className="h-14 w-14"
          />
          <span className="font-heading text-[1.18rem] font-semibold tracking-tight text-ink transition-colors hover:text-primary">
            AutoBSgenome
          </span>
        </a>

        <nav className="flex flex-wrap items-stretch gap-x-7">
          {SITE_NAV_ITEMS.map((item) => (
            <a
              key={item.href}
              href={item.href}
              className={navLinkClass(item.key === active)}
            >
              {item.label}
            </a>
          ))}
        </nav>

        <a
          href={siteConfig.githubUrl}
          target="_blank"
          rel="noreferrer"
          aria-label="View source on GitHub"
          className="ml-auto my-auto inline-flex h-9 w-9 items-center justify-center rounded-md border border-[color:var(--rule)]/20 bg-background text-ink transition-all hover:border-primary hover:bg-primary hover:text-primary-foreground"
        >
          <GithubMark className="size-4" />
        </a>
      </div>
    </header>
  );
}

export function SiteFooter() {
  return (
    <footer className="mt-16 border-t border-[color:var(--rule)]/15 bg-paper">
      <div className="mx-auto flex max-w-6xl flex-col gap-5 px-6 py-8 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-col gap-2 text-sm text-muted-foreground sm:flex-row sm:items-center sm:gap-4">
          <p>
            {SITE_FOOTER_CONTENT.copyright.prefix}
            <a
              href={SITE_FOOTER_CONTENT.copyright.lab.href}
              target="_blank"
              rel="noreferrer"
              className="text-foreground/80 underline decoration-foreground/25 underline-offset-4 transition-colors hover:text-primary"
            >
              {SITE_FOOTER_CONTENT.copyright.lab.label}
            </a>
            {SITE_FOOTER_CONTENT.copyright.suffix}
          </p>
          <span aria-hidden="true" className="hidden text-foreground/25 sm:inline">
            ·
          </span>
          <a
            href={SITE_FOOTER_CONTENT.reportIssue.href}
            target="_blank"
            rel="noreferrer"
            className="w-fit text-foreground/80 underline decoration-foreground/25 underline-offset-4 transition-colors hover:text-primary"
          >
            {SITE_FOOTER_CONTENT.reportIssue.label}
          </a>
        </div>
        <a
          href={SITE_FOOTER_CONTENT.university.href}
          target="_blank"
          rel="noreferrer"
          aria-label={SITE_FOOTER_CONTENT.university.imageAlt}
          className="inline-flex w-fit transition-opacity hover:opacity-80"
        >
          <img
            src={SITE_FOOTER_CONTENT.university.imageSrc}
            alt={SITE_FOOTER_CONTENT.university.imageAlt}
            width={240}
            height={60}
            className="h-10 w-auto max-w-[220px] sm:max-w-[260px]"
          />
        </a>
      </div>
    </footer>
  );
}
