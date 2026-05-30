import type { Metadata } from "next";
import { Crimson_Pro, Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const crimson = Crimson_Pro({
  variable: "--font-serif",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700", "800"],
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
  title: "AutoBSgenome - BSgenome Packages and Builder",
  description:
    "Build, browse, and automate BSgenome R packages from NCBI and Ensembl assemblies.",
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
    title: "AutoBSgenome - BSgenome Packages and Builder",
    description:
      "Build, browse, and automate BSgenome R packages from NCBI and Ensembl assemblies.",
    url: "https://autobsgenome.org",
    siteName: "AutoBSgenome",
    type: "website",
    locale: "en_US",
  },
  twitter: {
    card: "summary_large_image",
    title: "AutoBSgenome - BSgenome Packages and Builder",
    description:
      "Build, browse, and automate BSgenome R packages from NCBI and Ensembl assemblies.",
  },
  icons: {
    icon: [
      { url: "/favicon.ico", sizes: "any" },
      { url: "/icon.svg", type: "image/svg+xml" },
      { url: "/icon.png", type: "image/png" },
    ],
    apple: [{ url: "/apple-icon.png", sizes: "180x180", type: "image/png" }],
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
      className={`${crimson.variable} ${inter.variable} ${jetbrainsMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
