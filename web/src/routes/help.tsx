import { createFileRoute } from "@tanstack/react-router";

import HelpPage from "@/features/help/HelpPage";
import { seoHead } from "@/lib/seo";

export const Route = createFileRoute("/help")({
  head: () =>
    seoHead({
      title: "AutoBSgenome Help - Install and Build BSgenome Packages",
      description:
        "Learn how to search, build, download, and install BSgenome R packages with AutoBSgenome, including warning-free local tarball install commands.",
      path: "/help",
      keywords:
        "AutoBSgenome help, BSgenome install command, install BSgenome tarball, build BSgenome tutorial",
    }),
  component: HelpPage,
});
