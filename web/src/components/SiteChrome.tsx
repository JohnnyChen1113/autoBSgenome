import Link from "next/link";
import { Dna } from "lucide-react";

type NavKey = "home" | "build" | "packages" | "help" | "api" | "agents";

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
  const navItems: Array<{
    href: string;
    label: string;
    key?: NavKey;
  }> = [
    { href: "/packages", label: "Browse", key: "packages" },
    { href: "/build", label: "Build", key: "build" },
    { href: "/help", label: "Help", key: "help" },
    { href: "/api-docs", label: "API", key: "api" },
    { href: "/agents", label: "Agents", key: "agents" },
  ];

  return (
    <header className="sticky top-0 z-40 border-b border-[color:var(--rule)]/10 bg-background/85 backdrop-blur supports-[backdrop-filter]:bg-background/70">
      <div className="mx-auto flex max-w-6xl items-stretch gap-8 px-6">
        <Link
          href="/"
          className="flex shrink-0 items-center gap-3 py-4 group"
        >
          <Dna
            className="size-12 text-primary transition-transform group-hover:rotate-12"
            strokeWidth={1.6}
            aria-hidden="true"
          />
          <span className="font-heading text-[1.18rem] font-semibold tracking-tight text-ink group-hover:text-primary transition-colors">
            AutoBSgenome
          </span>
        </Link>

        <nav className="flex flex-wrap items-stretch gap-x-7">
          {navItems.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={navLinkClass(item.key === active)}
            >
              {item.label}
            </Link>
          ))}
        </nav>

        <a
          href="https://github.com/JohnnyChen1113/autoBSgenome"
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
      <div className="mx-auto max-w-6xl px-6 py-10">
        <div className="flex flex-col gap-6 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <div className="flex items-center gap-2.5">
              <Dna className="size-7 text-primary" strokeWidth={1.6} aria-hidden="true" />
              <span className="font-heading text-base font-semibold tracking-tight text-ink">
                AutoBSgenome
              </span>
            </div>
            <p className="mt-3 max-w-md text-sm leading-6 text-muted-foreground">
              An open infrastructure for finding and building BSgenome R
              packages from NCBI and Ensembl genome assemblies.
            </p>
          </div>
          <div className="flex flex-col items-start gap-1 text-sm sm:items-end">
            <a
              href="https://github.com/JohnnyChen1113/autoBSgenome"
              className="link-underline"
            >
              github.com/JohnnyChen1113/autoBSgenome
            </a>
            <p className="text-xs text-muted-foreground">
              Built by{" "}
              <a
                href="https://github.com/JohnnyChen1113"
                className="text-foreground/80 hover:text-primary"
              >
                Junhao Chen
              </a>{" "}
              · Saint Louis University
            </p>
          </div>
        </div>
        <div className="mt-8 rule" />
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
          <span>autobsgenome · open source</span>
          <span>build · browse · automate</span>
        </div>
      </div>
    </footer>
  );
}
