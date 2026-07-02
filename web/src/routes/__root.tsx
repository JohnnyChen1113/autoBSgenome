/// <reference types="vite/client" />
import {
  createRootRoute,
  HeadContent,
  Outlet,
  Scripts,
} from "@tanstack/react-router";
import type { ReactNode } from "react";

import { siteConfig } from "@/config";
import { absoluteSiteUrl } from "@/lib/seo";

import "@fontsource-variable/inter";
import "@fontsource/crimson-pro/400.css";
import "@fontsource/crimson-pro/500.css";
import "@fontsource/crimson-pro/600.css";
import "@fontsource/crimson-pro/700.css";
import "@fontsource/crimson-pro/800.css";
import "@fontsource/jetbrains-mono/400.css";
import "@fontsource/jetbrains-mono/500.css";
import "@/styles/globals.css";

export const Route = createRootRoute({
  head: () => {
    return {
      meta: [
        { charSet: "utf-8" },
        { name: "viewport", content: "width=device-width, initial-scale=1" },
        {
          name: "keywords",
          content:
            "BSgenome,Bioconductor,R package,genome,NCBI,Ensembl,bioinformatics,genomics,BSgenomeForge,reference genome",
        },
        { name: "author", content: "Junhao Chen" },
        { name: "theme-color", content: "#0f47b5" },
        { name: "robots", content: "index, follow" },
        { name: "googlebot", content: "index, follow" },
      ],
      links: [
        { rel: "icon", href: siteConfig.favicon, sizes: "any" },
        { rel: "icon", href: "/brand-icon.svg", type: "image/svg+xml" },
        { rel: "apple-touch-icon", href: "/icon-256.png" },
      ],
    };
  },
  component: RootComponent,
  shellComponent: RootDocument,
  notFoundComponent: NotFound,
});

function RootComponent() {
  return <Outlet />;
}

function RootDocument({ children }: { children: ReactNode }) {
  const structuredData = {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: "AutoBSgenome",
    applicationCategory: "Bioinformatics software",
    operatingSystem: "Web",
    url: absoluteSiteUrl("/"),
    description:
      "AutoBSgenome builds and hosts installable BSgenome R packages from NCBI, Ensembl, FASTA URLs, and local nucleotide FASTA uploads.",
    softwareHelp: absoluteSiteUrl("/help"),
    programmingLanguage: ["R", "TypeScript"],
    keywords:
      "BSgenome, Bioconductor, R package, NCBI, Ensembl, reference genome, bioinformatics",
  };

  return (
    <html lang="en" className="h-full antialiased">
      <head>
        <HeadContent />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(structuredData) }}
        />
      </head>
      <body className="min-h-full font-sans">
        {children}
        <Scripts />
      </body>
    </html>
  );
}

function NotFound() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 bg-background px-6 text-center text-foreground">
      <h1 className="text-6xl font-bold">404</h1>
      <p className="text-muted-foreground">Page not found</p>
      <a href="/" className="text-sm underline underline-offset-4">
        Back to home
      </a>
    </main>
  );
}
