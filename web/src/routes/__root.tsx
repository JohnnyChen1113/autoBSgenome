/// <reference types="vite/client" />
import {
  createRootRoute,
  HeadContent,
  Outlet,
  Scripts,
} from "@tanstack/react-router";
import type { ReactNode } from "react";

import { siteConfig } from "@/config";

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
    const appUrl = siteConfig.url.replace(/\/$/, "");
    return {
      meta: [
        { charSet: "utf-8" },
        { name: "viewport", content: "width=device-width, initial-scale=1" },
        { title: `${siteConfig.name} - BSgenome Packages and Builder` },
        { name: "description", content: siteConfig.description },
        {
          name: "keywords",
          content:
            "BSgenome,Bioconductor,R package,genome,NCBI,Ensembl,bioinformatics,genomics,BSgenomeForge,reference genome",
        },
        { name: "author", content: "Junhao Chen" },
        { property: "og:title", content: `${siteConfig.name} - BSgenome Packages and Builder` },
        { property: "og:description", content: siteConfig.description },
        { property: "og:url", content: appUrl },
        { property: "og:site_name", content: siteConfig.name },
        { property: "og:type", content: "website" },
        { name: "twitter:card", content: "summary_large_image" },
        { name: "twitter:title", content: `${siteConfig.name} - BSgenome Packages and Builder` },
        { name: "twitter:description", content: siteConfig.description },
      ],
      links: [
        { rel: "icon", href: siteConfig.favicon, sizes: "any" },
        { rel: "icon", href: "/brand-icon.svg", type: "image/svg+xml" },
        { rel: "apple-touch-icon", href: "/icon-256.png" },
        { rel: "canonical", href: `${appUrl}/` },
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
  return (
    <html lang="en" className="h-full antialiased">
      <head>
        <HeadContent />
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
