import {
  ArrowRight,
  ArrowUpRight,
  CheckCircle2,
  ClipboardCheck,
  Dna,
  Download,
  FileSearch,
  Hammer,
} from "lucide-react";
import { SiteFooter, SiteHeader } from "@/components/SiteChrome";

const workflows = [
  {
    no: "01",
    icon: FileSearch,
    title: "Search and download",
    description:
      "Best when you need a common organism or want to avoid rebuilding an existing package.",
    href: "/packages",
    steps: [
      "Open Packages and search by species, assembly, accession, or package name.",
      "Choose a matching package and inspect provider, assembly, source, and storage.",
      "Install from Bioconductor when available, or copy the AutoBSgenome direct tarball command.",
    ],
  },
  {
    no: "02",
    icon: Dna,
    title: "One-click build",
    description:
      "Best when you already have an NCBI accession or Ensembl species page.",
    href: "/build",
    steps: [
      "Open Build and paste an NCBI accession such as GCF_000001405.40, or an Ensembl species URL.",
      "Fetch metadata, check the generated package name and organism information, then submit the build.",
      "Wait for the job to finish, then download the tarball or publish it to the repository.",
    ],
  },
  {
    no: "03",
    icon: ClipboardCheck,
    title: "Manual review",
    description:
      "Best when the metadata needs correction before the package is built.",
    href: "/build",
    steps: [
      "After metadata fetch, review package name, organism, common name, assembly, provider, and version.",
      "Check circular sequences, title, description, and source URL before starting the build.",
      "Use the generated result as the final installable source package for downstream R analysis.",
    ],
  },
];

const examples = [
  {
    label: "NCBI RefSeq accession",
    value: "GCF_000001405.40",
    note: "Use this form for NCBI-hosted assemblies.",
  },
  {
    label: "Ensembl species page",
    value: "https://www.ensembl.org/Danio_rerio/Info/Index",
    note: "Use this form when the genome is easier to identify from Ensembl.",
  },
  {
    label: "Package search",
    value: "BSgenome.Hsapiens.NCBI.GRCh38",
    note: "Use this form when you already know the BSgenome package name.",
  },
];

const installSnippets = [
  {
    icon: Download,
    title: "Install an AutoBSgenome-hosted package",
    note: "Use the Copy button on a package card; it provides the real tarball URL.",
    code: `install.packages(
  "TARBALL_URL",
  repos = NULL,
  type = "source"
)`,
  },
  {
    icon: Hammer,
    title: "Install a Bioconductor-hosted package",
    note: "Use this only for package cards labeled Bioconductor.",
    code: `BiocManager::install(
  "BSgenome.Hsapiens.UCSC.hg38"
)`,
  },
];

export default function HelpPage() {
  return (
    <div className="flex min-h-screen flex-col bg-background">
      <SiteHeader active="help" />

      <main className="flex-1">
        {/* HERO */}
        <section className="border-b border-[color:var(--rule)]/15">
          <div className="mx-auto max-w-6xl px-6 pt-14 pb-16">
            <span className="eyebrow-accent">Workflow guide · 01 / 03</span>
            <h1 className="display mt-5 text-4xl sm:text-6xl">
              How to use{" "}
              <span className="italic">AutoBSgenome</span>.
            </h1>
            <p className="mt-6 max-w-2xl text-lg leading-8 text-foreground/75">
              Search the package repository first. If the genome you need is
              not there, build a new one from NCBI or Ensembl and install the
              resulting tarball in R.
            </p>
          </div>
        </section>

        {/* WORKFLOWS */}
        <section>
          <div className="mx-auto max-w-6xl px-6 pt-14 pb-12">
            <div className="grid gap-px bg-[color:var(--rule)]/15 sm:grid-cols-3 sm:overflow-hidden sm:rounded-md sm:border sm:border-[color:var(--rule)]/15">
              {workflows.map((wf) => {
                const Icon = wf.icon;
                return (
                  <div
                    key={wf.title}
                    className="flex flex-col bg-background p-7"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
                        {wf.no}
                      </span>
                      <Icon className="size-4 text-primary/70" />
                    </div>
                    <h2 className="mt-5 font-heading text-2xl font-semibold tracking-tight text-ink">
                      {wf.title}
                    </h2>
                    <p className="mt-2 text-sm leading-6 text-foreground/65">
                      {wf.description}
                    </p>
                    <ol className="mt-6 space-y-3">
                      {wf.steps.map((step, i) => (
                        <li
                          key={step}
                          className="flex gap-3 text-sm leading-6 text-foreground/80"
                        >
                          <span className="mt-0.5 font-mono text-[11px] tabular-nums text-primary">
                            {String(i + 1).padStart(2, "0")}
                          </span>
                          <span>{step}</span>
                        </li>
                      ))}
                    </ol>
                    <a
                      href={wf.href}
                      className="mt-7 inline-flex h-10 w-fit items-center gap-2 self-start rounded-md border border-primary/30 bg-background px-4 text-sm font-medium text-primary transition-all hover:border-primary hover:bg-primary hover:text-primary-foreground hover:shadow-sm"
                    >
                      Open {wf.title.toLowerCase()}
                      <ArrowRight className="size-4" />
                    </a>
                  </div>
                );
              })}
            </div>
          </div>
        </section>

        {/* INPUTS */}
        <section className="bg-paper border-y border-[color:var(--rule)]/15">
          <div className="mx-auto max-w-6xl px-6 py-16">
            <div className="grid gap-10 lg:grid-cols-[0.8fr_1.2fr]">
              <div className="lg:sticky lg:top-24 lg:self-start">
                <span className="eyebrow">Inputs</span>
                <h2 className="mt-3 font-heading text-3xl font-semibold tracking-tight text-ink sm:text-4xl">
                  Common things users paste
                </h2>
                <p className="mt-4 max-w-md text-sm leading-7 text-foreground/70">
                  AutoBSgenome accepts accessions, Ensembl pages, and package
                  names depending on the page you are using.
                </p>
              </div>

              <ul className="divide-y divide-[color:var(--rule)]/15 border-y border-[color:var(--rule)]/15">
                {examples.map((ex) => (
                  <li key={ex.label} className="py-6">
                    <div className="flex flex-wrap items-baseline justify-between gap-3">
                      <span className="font-heading text-lg font-semibold text-ink">
                        {ex.label}
                      </span>
                      <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                        input · paste
                      </span>
                    </div>
                    <div className="mt-3 break-all border-l-2 border-primary/60 bg-background px-4 py-3 font-mono text-[13px] text-primary">
                      {ex.value}
                    </div>
                    <p className="mt-3 text-sm leading-6 text-foreground/70">
                      {ex.note}
                    </p>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </section>

        {/* INSTALL SNIPPETS */}
        <section>
          <div className="mx-auto max-w-6xl px-6 py-16">
            <span className="eyebrow">Install in R</span>
            <h2 className="mt-3 font-heading text-3xl font-semibold tracking-tight text-ink sm:text-4xl">
              From a package card.
            </h2>

            <div className="mt-10 grid gap-6 lg:grid-cols-2">
              {installSnippets.map((snip) => {
                const Icon = snip.icon;
                return (
                  <figure
                    key={snip.title}
                    className="overflow-hidden rounded-md border border-[color:var(--rule)]/15 bg-background"
                  >
                    <figcaption className="flex items-center justify-between border-b border-[color:var(--rule)]/15 bg-paper px-5 py-3">
                      <div className="flex items-center gap-3">
                        <Icon className="size-4 text-primary" />
                        <span className="font-heading text-base font-semibold text-ink">
                          {snip.title}
                        </span>
                      </div>
                      <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                        R
                      </span>
                    </figcaption>
                    <pre className="overflow-x-auto bg-[#0b0e14] p-5 font-mono text-[12.5px] leading-6 text-slate-100">
                      <code>{snip.code}</code>
                    </pre>
                    <p className="border-t border-[color:var(--rule)]/15 px-5 py-3 text-sm text-foreground/65">
                      {snip.note}
                    </p>
                  </figure>
                );
              })}
            </div>
          </div>
        </section>

        {/* RECOMMENDED ORDER */}
        <section className="border-t border-[color:var(--rule)]/15 bg-paper">
          <div className="mx-auto max-w-6xl px-6 py-14">
            <div className="grid gap-6 lg:grid-cols-[auto_1fr_auto] lg:items-center">
              <CheckCircle2 className="size-8 text-primary" />
              <div>
                <span className="eyebrow">Recommended order</span>
                <p className="mt-2 font-heading text-xl font-medium leading-snug text-ink sm:text-2xl">
                  Search first. Build only if the package is missing. Then
                  install the snippet shown by the browser or build result.
                </p>
              </div>
              <a
                href="/packages"
                className="inline-flex h-10 items-center gap-2 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
              >
                Start searching
                <ArrowUpRight className="size-4" />
              </a>
            </div>
          </div>
        </section>
      </main>

      <SiteFooter />
    </div>
  );
}
