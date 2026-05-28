import type { Metadata } from "next";
import Link from "next/link";
import { ArrowUpRight, ArrowRight, Search, Hammer } from "lucide-react";
import { SiteHeader } from "@/components/SiteChrome";
import { SpeciesImage } from "@/components/SpeciesImage";

export const metadata: Metadata = {
  title: "AutoBSgenome - BSgenome Packages and Builder",
  description:
    "Find existing BSgenome packages or build new ones from NCBI and Ensembl assemblies, for every species and every assembly version.",
};

const commonPackages = [
  {
    species: "Human",
    organism: "Homo sapiens",
    provider: "Ensembl",
    assembly: "GRCh38.p14",
    packageName: "BSgenome.Hsapiens.Ensembl.GRCh38p14",
    query: "BSgenome.Hsapiens.Ensembl.GRCh38p14",
    image: "https://www.ensembl.org/i/species/Homo_sapiens.png",
    imageFit: "contain" as const,
  },
  {
    species: "Mouse",
    organism: "Mus musculus",
    provider: "UCSC",
    assembly: "mm39",
    packageName: "BSgenome.Mmusculus.UCSC.mm39",
    query: "BSgenome.Mmusculus.UCSC.mm39",
    image: "https://www.ensembl.org/i/species/Mus_musculus.png",
    imageFit: "contain" as const,
  },
  {
    species: "Zebrafish",
    organism: "Danio rerio",
    provider: "Ensembl",
    assembly: "GRCz11",
    packageName: "BSgenome.Drerio.Ensembl.GRCz11",
    query: "BSgenome.Drerio.Ensembl.GRCz11",
    image: "https://www.ensembl.org/i/species/Danio_rerio.png",
    imageFit: "contain" as const,
  },
  {
    species: "Fruit fly",
    organism: "Drosophila melanogaster",
    provider: "Ensembl",
    assembly: "BDGP6.54",
    packageName: "BSgenome.Dmelanogaster.Ensembl.BDGP654",
    query: "BSgenome.Dmelanogaster.Ensembl.BDGP654",
    image: "https://www.ensembl.org/i/species/Drosophila_melanogaster.png",
    imageFit: "contain" as const,
  },
  {
    species: "Arabidopsis",
    organism: "Arabidopsis thaliana",
    provider: "Ensembl",
    assembly: "TAIR10",
    packageName: "BSgenome.Athaliana.Ensembl.TAIR10",
    query: "BSgenome.Athaliana.Ensembl.TAIR10",
    image:
      "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6f/Arabidopsis_thaliana.jpg/330px-Arabidopsis_thaliana.jpg",
    imageFit: "cover" as const,
  },
];

export default function HomePage() {
  return (
    <div className="flex min-h-screen flex-col">
      <SiteHeader active="home" />

      <main className="flex-1">
        {/* HERO */}
        <section className="border-b border-[color:var(--rule)]/15">
          <div className="mx-auto max-w-6xl px-6 pt-16 pb-20 sm:pt-20 sm:pb-24">
            <h1 className="display text-5xl sm:text-6xl lg:text-[5rem]">
              Build <span className="text-primary">BSgenomes</span> for
              <br />
              any species, any assembly,
              <br />
              automatically.
            </h1>

            <p className="mt-10 max-w-2xl text-lg leading-8 text-foreground/75">
              Paste an{" "}
              <span className="font-medium text-foreground">NCBI</span>{" "}
              accession, an{" "}
              <span className="font-medium text-foreground">Ensembl</span>{" "}
              species URL, or upload your own FASTA. We build the BSgenome
              package and hand you an installable tarball. No R, no
              Bioconductor, no local toolchain to set up.
            </p>
          </div>
        </section>

        {/* QUICK START · two large option cards */}
        <section id="quick-start" className="border-b border-[color:var(--rule)]/15">
          <div className="mx-auto max-w-6xl px-6 pt-16 pb-16">
            <div className="flex items-baseline justify-between gap-6">
              <div>
                <span className="eyebrow-accent">Quick start</span>
                <h2 className="mt-3 font-heading text-3xl font-semibold tracking-tight text-ink sm:text-4xl">
                  Pick one of two paths.
                </h2>
              </div>
              <span className="hidden font-mono text-[11px] uppercase tracking-[0.18em] text-muted-foreground sm:inline">
                A · B
              </span>
            </div>

            <div className="mt-10 grid gap-px bg-[color:var(--rule)]/15 sm:grid-cols-2 sm:overflow-hidden sm:rounded-md sm:border sm:border-[color:var(--rule)]/15">
              {/* A · Search existing */}
              <Link
                href="/packages"
                className="group flex flex-col bg-background p-8 transition-colors hover:bg-paper sm:p-10"
              >
                <div className="flex items-start justify-between">
                  <span className="font-mono text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
                    Path A
                  </span>
                  <span className="flex size-10 items-center justify-center rounded-md border border-[color:var(--rule)]/20 bg-paper text-primary">
                    <Search className="size-4" />
                  </span>
                </div>
                <h3 className="mt-6 font-heading text-3xl font-semibold tracking-tight text-ink">
                  Search an existing package.
                </h3>
                <p className="mt-4 text-[15px] leading-7 text-foreground/70">
                  Browse a growing community repository. Filter by species,
                  assembly, provider, or accession; install the result with a
                  single R command.
                </p>
                <span className="mt-8 inline-flex h-10 w-fit items-center gap-2 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground shadow-sm transition-all group-hover:bg-primary/90 group-hover:shadow-md">
                  Open package browser
                  <ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5" />
                </span>
              </Link>

              {/* B · Build new */}
              <Link
                href="/build"
                className="group flex flex-col bg-background p-8 transition-colors hover:bg-paper sm:p-10"
              >
                <div className="flex items-start justify-between">
                  <span className="font-mono text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
                    Path B
                  </span>
                  <span className="flex size-10 items-center justify-center rounded-md border border-[color:var(--rule)]/20 bg-paper text-primary">
                    <Hammer className="size-4" />
                  </span>
                </div>
                <h3 className="mt-6 font-heading text-3xl font-semibold tracking-tight text-ink">
                  Build your own package.
                </h3>
                <p className="mt-4 text-[15px] leading-7 text-foreground/70">
                  Paste an NCBI accession or an Ensembl species URL. We fetch
                  metadata, generate a clean BSgenome source package, and hand
                  you an installable tarball.
                </p>
                <span className="mt-8 inline-flex h-10 w-fit items-center gap-2 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground shadow-sm transition-all group-hover:bg-primary/90 group-hover:shadow-md">
                  Open builder
                  <ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5" />
                </span>
              </Link>
            </div>

            <p className="mt-6 text-sm text-foreground/60">
              New here?{" "}
              <Link href="/help" className="link-underline">
                Read the workflow guide
              </Link>{" "}
              for a 3-step walk-through with example inputs and install
              snippets.
            </p>
          </div>
        </section>

        {/* COMMON ASSEMBLIES · editorial list with species images */}
        <section className="bg-paper">
          <div className="mx-auto max-w-6xl px-6 py-16">
            <div className="grid gap-10 lg:grid-cols-[0.7fr_1.3fr] lg:items-start">
              <div className="lg:sticky lg:top-24">
                <span className="eyebrow">Frequently requested</span>
                <h2 className="mt-3 font-heading text-3xl font-semibold tracking-tight text-ink sm:text-4xl">
                  Common species &amp; assemblies
                </h2>
                <p className="mt-4 max-w-md text-sm leading-7 text-foreground/70">
                  Jump straight into the package browser with a search term
                  applied. If the exact assembly version is missing, the
                  builder is one click away.
                </p>
                <Link
                  href="/packages"
                  className="mt-6 inline-flex h-10 items-center gap-2 rounded-md border border-primary/30 bg-background px-4 text-sm font-medium text-primary transition-all hover:border-primary hover:bg-primary hover:text-primary-foreground hover:shadow-sm"
                >
                  View all packages
                  <ArrowRight className="size-4" />
                </Link>
              </div>

              <ul className="divide-y divide-[color:var(--rule)]/15 border-y border-[color:var(--rule)]/15">
                {commonPackages.map((item) => (
                  <li key={item.packageName}>
                    <Link
                      href={`/packages?q=${encodeURIComponent(item.query)}`}
                      className="group grid grid-cols-[auto_1fr_auto] items-center gap-x-6 gap-y-1 py-5 transition-colors hover:bg-background sm:grid-cols-[auto_minmax(0,1fr)_auto_auto]"
                    >
                      <span className="block size-16 overflow-hidden">
                        <SpeciesImage
                          src={item.image}
                          alt=""
                          fit={item.imageFit}
                        />
                      </span>
                      <div className="min-w-0">
                        <div className="font-heading text-2xl font-semibold tracking-tight text-ink">
                          {item.species}{" "}
                          <span className="text-lg font-normal italic text-foreground/55">
                            {item.organism}
                          </span>
                        </div>
                        <div className="mt-1 truncate font-mono text-sm text-foreground/55">
                          {item.packageName}
                        </div>
                      </div>
                      <div className="hidden whitespace-nowrap font-mono text-sm uppercase tracking-[0.14em] text-foreground/70 sm:block">
                        <span className="text-muted-foreground">
                          {item.provider}
                        </span>
                        <span className="mx-2 text-foreground/30">/</span>
                        {item.assembly}
                      </div>
                      <ArrowUpRight className="size-5 shrink-0 text-foreground/30 transition-all group-hover:-translate-y-0.5 group-hover:translate-x-0.5 group-hover:text-primary" />
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </section>

      </main>

      {/* CLOSING SECTION AS FOOTER */}
      <footer className="border-t border-[color:var(--rule)]/15">
        <div className="mx-auto max-w-6xl px-6 pt-16 pb-10">
          <div className="grid gap-10 lg:grid-cols-[1fr_auto] lg:items-end">
            <p className="max-w-3xl font-heading text-2xl font-medium leading-snug tracking-tight text-ink sm:text-3xl">
              Every BSgenome on Bioconductor took an expert and an afternoon
              to assemble. AutoBSgenome turns that into a paste-and-wait web
              service. Anyone, any genome, install-ready in minutes.
            </p>
            <div className="flex flex-wrap gap-3">
              <Link
                href="/build"
                className="inline-flex h-11 items-center gap-2 rounded-md bg-primary px-5 text-sm font-medium text-primary-foreground transition-all hover:bg-primary/90 hover:shadow-md"
              >
                Start a build
                <ArrowRight className="size-4" />
              </Link>
              <a
                href="https://github.com/JohnnyChen1113/autoBSgenome"
                target="_blank"
                rel="noreferrer"
                className="inline-flex h-11 items-center gap-2 rounded-md border border-foreground/15 px-5 text-sm font-medium text-foreground hover:border-foreground/40 hover:bg-paper"
              >
                GitHub
                <ArrowUpRight className="size-4" />
              </a>
            </div>
          </div>

          <div className="mt-10 rule" />

          <div className="mt-5 flex flex-col gap-2 text-sm text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
            <p>
              Built by{" "}
              <a
                href="https://github.com/JohnnyChen1113"
                className="text-foreground/80 hover:text-primary"
              >
                Junhao Chen
              </a>
              , Saint Louis University.
            </p>
            <a
              href="https://github.com/JohnnyChen1113/autoBSgenome"
              className="link-underline"
            >
              github.com/JohnnyChen1113/autoBSgenome
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}
