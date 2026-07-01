import { Badge } from "@/components/ui/badge";
import {
  Bot,
  CheckCircle2,
  Clock3,
  Download,
  FileText,
  Hammer,
  Search,
  ShieldCheck,
  Trash2,
  Upload,
} from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { siteConfig } from "@/config";
import { SiteFooter, SiteHeader } from "@/components/SiteChrome";

const workflow = [
  {
    icon: Search,
    title: "Search first",
    description:
      "Look for an existing package before submitting a new build. Prefer Bioconductor or an existing AutoBSgenome tarball when it matches the requested organism and assembly.",
  },
  {
    icon: Hammer,
    title: "Build only when needed",
    description:
      "Submit builds from NCBI, Ensembl, FASTA URL, or local nucleotide FASTA upload. Keep metadata visible to the user before triggering GitHub Actions.",
  },
  {
    icon: Clock3,
    title: "Poll status",
    description:
      "Poll /api/status/:jobId and surface the live step list, workflow run URL, final download URL, or failure message.",
  },
  {
    icon: Download,
    title: "Install direct tarballs",
    description:
      "Use install.packages(download_url, repos = NULL, type = \"source\"). Do not use the old CRAN-like repository install snippet.",
  },
];

const safeguards = [
  "Keep delete_token private. It can delete a user's temporary build release.",
  "Do not publish user-supplied FASTA builds unless the user explicitly confirms public sharing and provides a license.",
  "Report build failures with job_id, workflow_run_url, package metadata, and the exact API message.",
  "Use the package browser for lookup; use /api-docs as the source of truth for endpoint details.",
];

export default function AgentsPage() {
  const WORKER = siteConfig.apiBase;

  return (
    <div className="flex min-h-screen flex-col bg-background">
      <SiteHeader active="agents" />

      <main className="mx-auto w-full max-w-4xl flex-1 px-6 py-10">
        <div>
          <div className="flex flex-wrap gap-2">
            <Badge>Agent Skill</Badge>
            <Badge variant="outline">HTTP API live</Badge>
            <Badge variant="outline">MCP optional later</Badge>
          </div>
          <h1 className="mt-4 text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
            AutoBSgenome for Agents
          </h1>
          <p className="mt-3 max-w-2xl text-base leading-relaxed text-muted-foreground">
            AutoBSgenome can be used by coding agents and research assistants to
            check existing BSgenome packages, trigger builds, poll status, and
            return direct R installation commands. The current integration
            surface is the public HTTP API; a native MCP wrapper is not required
            for the web product to work.
          </p>
        </div>

        <Separator className="my-8" />

        <section className="space-y-4">
          <h2 className="font-heading text-2xl font-semibold text-foreground">
            Recommended Agent Loop
          </h2>
          <div className="grid gap-4 md:grid-cols-2">
            {workflow.map((item) => {
              const Icon = item.icon;
              return (
                <Card key={item.title} className="rounded-lg">
                  <CardHeader>
                    <div className="flex items-center justify-between gap-4">
                      <CardTitle>{item.title}</CardTitle>
                      <Icon className="size-5 text-primary" />
                    </div>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm leading-6 text-muted-foreground">
                      {item.description}
                    </p>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </section>

        <Separator className="my-8" />

        <div className="grid gap-4 md:grid-cols-2">
          <Card className="rounded-lg">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Bot className="size-5 text-primary" />
                Skill workflow
              </CardTitle>
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
                <p className="mt-2 text-sm text-muted-foreground">
                  Keep this file aligned with the HTTP API docs. It should tell
                  agents to use direct tarball installs and to treat publishing
                  as an explicit user decision.
                </p>
              </div>
            </CardContent>
          </Card>

          <Card className="rounded-lg">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FileText className="size-5 text-primary" />
                MCP status
              </CardTitle>
              <CardDescription>
                Useful later, but not the current source of truth.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-sm text-muted-foreground">
              <p>
                A future MCP server can wrap package lookup, upload session
                creation, build submission, status polling, deletion, and
                publish.
              </p>
              <p>
                For now, agents should call the HTTP API directly and link users
                to the package browser or API docs when they need human review.
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
{`curl -s -X POST ${WORKER}/api/build \\
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
{`curl -s ${WORKER}/api/status/JOB_ID`}
            </pre>
          </div>

          <div className="rounded-lg border border-border bg-secondary p-4">
            <div className="text-sm font-medium text-foreground">
              Install the completed tarball
            </div>
            <pre className="mt-2 overflow-x-auto rounded-md bg-background p-3 font-mono text-xs text-foreground">
{`install.packages(
  "TARBALL_URL_FROM_STATUS_OR_PACKAGE_CARD",
  repos = NULL,
  type = "source"
)`}
            </pre>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <div className="rounded-lg border border-border bg-secondary p-4">
              <div className="flex items-center gap-2 text-sm font-medium text-foreground">
                <Trash2 className="size-4 text-primary" />
                Delete a temporary build
              </div>
              <pre className="mt-2 overflow-x-auto rounded-md bg-background p-3 font-mono text-xs text-foreground">
{`curl -s -X DELETE ${WORKER}/api/build/JOB_ID \\
  -H "Content-Type: application/json" \\
  -d '{"delete_token":"DELETE_TOKEN"}'`}
              </pre>
            </div>

            <div className="rounded-lg border border-border bg-secondary p-4">
              <div className="flex items-center gap-2 text-sm font-medium text-foreground">
                <Upload className="size-4 text-primary" />
                Upload a local FASTA
              </div>
              <pre className="mt-2 overflow-x-auto rounded-md bg-background p-3 font-mono text-xs text-foreground">
{`curl -s -X POST ${WORKER}/api/uploads \\
  -H "Content-Type: application/json" \\
  -d '{"file_name":"genome.fa","file_size":123456}'`}
              </pre>
            </div>
          </div>
        </section>

        <section className="mt-8 rounded-lg border border-border bg-background p-5">
          <div className="flex items-center gap-2">
            <ShieldCheck className="size-5 text-primary" />
            <h2 className="font-heading text-xl font-semibold text-foreground">
              Agent safeguards
            </h2>
          </div>
          <ul className="mt-4 space-y-3">
            {safeguards.map((item) => (
              <li key={item} className="flex gap-3 text-sm leading-6 text-muted-foreground">
                <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-primary" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </section>
      </main>

      <SiteFooter />
    </div>
  );
}
