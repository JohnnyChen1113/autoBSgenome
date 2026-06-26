import { createFileRoute } from "@tanstack/react-router";

import PackagesPage from "@/features/packages/PackagesPage";

export const Route = createFileRoute("/packages")({
  component: PackagesPage,
});
