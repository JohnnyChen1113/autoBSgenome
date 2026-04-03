import type { Metadata } from "next";
import { Source_Serif_4, Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const sourceSerif = Source_Serif_4({
  variable: "--font-serif",
  subsets: ["latin"],
  display: "swap",
});

const inter = Inter({
  variable: "--font-sans",
  subsets: ["latin"],
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-mono",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "AutoBSgenome — Build BSgenome R Packages Online",
  description:
    "Build BSgenome R packages for any organism in minutes. Paste an NCBI or Ensembl accession, review auto-filled metadata, and download a ready-to-install package. No local R setup required. Free and open source.",
  keywords: [
    "BSgenome",
    "Bioconductor",
    "R package",
    "genome",
    "NCBI",
    "Ensembl",
    "bioinformatics",
    "genomics",
    "BSgenomeForge",
    "reference genome",
  ],
  authors: [{ name: "Junhao Chen", url: "https://github.com/JohnnyChen1113" }],
  openGraph: {
    title: "AutoBSgenome — Build BSgenome R Packages Online",
    description:
      "Build BSgenome R packages for any organism in under a minute. Supports NCBI and Ensembl. Free, open source, zero setup.",
    url: "https://autobsgenome.pages.dev",
    siteName: "AutoBSgenome",
    type: "website",
    locale: "en_US",
  },
  twitter: {
    card: "summary_large_image",
    title: "AutoBSgenome — Build BSgenome R Packages Online",
    description:
      "Build BSgenome R packages for any organism in under a minute. Supports NCBI and Ensembl.",
  },
  robots: {
    index: true,
    follow: true,
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${sourceSerif.variable} ${inter.variable} ${jetbrainsMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
