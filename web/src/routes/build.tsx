import { createFileRoute } from "@tanstack/react-router";

import BuildPage from "@/features/build/BuildPage";

export const Route = createFileRoute("/build")({
  component: BuildPage,
});
