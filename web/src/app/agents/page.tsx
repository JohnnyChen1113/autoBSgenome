import type { Metadata } from "next";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { SiteFooter, SiteHeader } from "@/components/SiteChrome";

export const metadata: Metadata = {
  title: "Agents - AutoBSgenome",
  description:
    "Use AutoBSgenome from agent skills and API workflows for BSgenome package construction.",
};

export default function AgentsPage() {
  return (
    <div className="flex min-h-screen flex-col bg-background">
      <SiteHeader active="agents" />

      <main className="mx-auto w-full max-w-4xl flex-1 px-6 py-10">
        <div>
          <div className="flex flex-wrap gap-2">
            <Badge>Agent Skill</Badge>
            <Badge variant="outline">MCP planned</Badge>
          </div>
          <h1 className="mt-4 text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
            AutoBSgenome for Agents
          </h1>
          <p className="mt-3 max-w-2xl text-base leading-relaxed text-muted-foreground">
            AutoBSgenome can be used by coding agents and research assistants to
            check existing BSgenome packages, trigger builds, poll status, and
            return R installation commands.
          </p>
        </div>

        <Separator className="my-8" />

        <div className="grid gap-4 md:grid-cols-2">
          <Card className="rounded-lg">
            <CardHeader>
              <CardTitle>Skill workflow</CardTitle>
              <CardDescription>
                The current integration path for Codex, Claude, and similar
                agent environments.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <div className="text-sm font-medium text-foreground">
                  Trigger phrases
                </div>
                <p className="mt-1 text-sm text-muted-foreground">
                  Use when a user needs a BSgenome package, mentions TSSr,
                  motifmatchr, ChIPseeker, Gviz, or has a missing genome error.
                </p>
              </div>
              <div>
                <div className="text-sm font-medium text-foreground">
                  Skill file
                </div>
                <code className="mt-1 block rounded-md bg-secondary px-3 py-2 font-mono text-xs text-foreground">
                  skill.md
                </code>
              </div>
            </CardContent>
          </Card>

          <Card className="rounded-lg">
            <CardHeader>
              <CardTitle>MCP status</CardTitle>
              <CardDescription>
                Useful later, but not required for the current web/API product.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-sm text-muted-foreground">
              <p>
                A future MCP server can expose tools like package lookup,
                metadata fetch, build submission, status polling, and publish.
              </p>
              <p>
                For now, the HTTP API already provides the stable backend
                surface that an MCP server would wrap.
              </p>
            </CardContent>
          </Card>
        </div>

        <section className="mt-8 space-y-4">
          <h2 className="font-heading text-2xl font-semibold text-foreground">
            API Commands
          </h2>
          <div className="rounded-lg border border-border bg-secondary p-4">
            <div className="text-sm font-medium text-foreground">
              Trigger a build
            </div>
            <pre className="mt-2 overflow-x-auto rounded-md bg-background p-3 font-mono text-xs text-foreground">
{`curl -s -X POST https://api.autobsgenome.org/api/build \\
  -H "Content-Type: application/json" \\
  -d '{
    "package_name": "BSgenome.Aluchuensis.NCBI.AkawachiiIFO4308",
    "organism": "Aspergillus luchuensis",
    "accession": "GCF_016861625.1",
    "data_source": "ncbi",
    "version": "1.0.0",
    "circ_seqs": "character(0)"
  }'`}
            </pre>
          </div>

          <div className="rounded-lg border border-border bg-secondary p-4">
            <div className="text-sm font-medium text-foreground">
              Poll build status
            </div>
            <pre className="mt-2 overflow-x-auto rounded-md bg-background p-3 font-mono text-xs text-foreground">
{`curl -s https://api.autobsgenome.org/api/status/JOB_ID`}
            </pre>
          </div>

          <div className="rounded-lg border border-border bg-secondary p-4">
            <div className="text-sm font-medium text-foreground">
              Install from the repository
            </div>
            <pre className="mt-2 overflow-x-auto rounded-md bg-background p-3 font-mono text-xs text-foreground">
{`install.packages("PACKAGE_NAME",
  repos = "https://johnnychen1113.github.io/autoBSgenome")`}
            </pre>
          </div>
        </section>
      </main>

      <SiteFooter />
    </div>
  );
}
