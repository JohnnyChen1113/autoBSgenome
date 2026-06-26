import { createFileRoute } from "@tanstack/react-router";

import ApiDocsPage from "@/features/api-docs/ApiDocsPage";

export const Route = createFileRoute("/api-docs")({
  component: ApiDocsPage,
});
