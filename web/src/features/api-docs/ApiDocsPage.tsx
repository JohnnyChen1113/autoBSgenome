import { Badge } from "@/components/ui/badge";
import { siteConfig } from "@/config";
import { Separator } from "@/components/ui/separator";
import { SiteFooter, SiteHeader } from "@/components/SiteChrome";

function CodeBlock({ children }: { children: string }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-border bg-secondary p-4 font-mono text-sm">
      <pre>{children}</pre>
    </div>
  );
}

function Endpoint({
  method,
  path,
  tone,
  children,
}: {
  method: "GET" | "POST" | "PUT" | "DELETE";
  path: string;
  tone: string;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-4">
      <div className="flex items-center gap-3">
        <Badge className={`${tone} text-white`}>{method}</Badge>
        <code className="font-mono text-lg font-semibold">{path}</code>
      </div>
      {children}
    </section>
  );
}

export default function ApiDocs() {
  const WORKER = siteConfig.apiBase;

  return (
    <div className="flex min-h-screen flex-col bg-background">
      <SiteHeader active="api" />

      <main className="mx-auto max-w-4xl flex-1 px-6 py-12">
        <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">API Reference</h1>
        <p className="mt-3 text-lg text-muted-foreground">
          Build BSgenome packages programmatically. The public API does not
          require user authentication; user-triggered build artifacts are
          temporary and permanent repository inclusion is maintainer-curated.
        </p>
        <p className="mt-2 text-sm text-muted-foreground">
          Base URL:{" "}
          <code className="rounded bg-accent px-2 py-0.5 font-mono text-primary">
            {WORKER}
          </code>
        </p>

        <Separator className="my-8" />

        <Endpoint method="POST" path="/api/build" tone="bg-green-600">
          <p className="text-muted-foreground">
            Trigger a new BSgenome package build from NCBI, Ensembl, a FASTA URL,
            or an uploaded FASTA file.
          </p>
          <div>
            <h3 className="mb-2 font-heading font-semibold text-foreground">
              Request Body
            </h3>
            <CodeBlock>{`{
  "package_name": "BSgenome.Hsapiens.NCBI.GRCh38",
  "organism": "Homo sapiens",
  "common_name": "human",
  "genome": "GRCh38",
  "provider": "NCBI",
  "version": "1.0.0",
  "circ_seqs": "MT",
  "accession": "GCF_000001405.40",
  "data_source": "ncbi",
  "release_date": "2022-02-03",
  "source_url": "https://www.ncbi.nlm.nih.gov/datasets/genome/GCF_000001405.40/"
}`}</CodeBlock>
          </div>
          <p className="text-sm leading-6 text-muted-foreground">
            For FASTA URL builds, set <code>fasta_source</code> to{" "}
            <code>url</code> and include <code>fasta_url</code>. For browser
            uploads, set <code>fasta_source</code> to <code>upload</code> and
            include the signed <code>fasta_upload_url</code> returned by{" "}
            <code>POST /api/uploads</code>.
          </p>
          <div>
            <h3 className="mb-2 font-heading font-semibold text-foreground">
              Response
            </h3>
            <CodeBlock>{`{
  "job_id": "4c1e14f7",
  "status": "queued",
  "queue_position": 0,
  "delete_token": "hmac-token-for-this-job"
}`}</CodeBlock>
          </div>
          <p className="text-sm leading-6 text-muted-foreground">
            Keep <code>delete_token</code> private. It can delete the temporary
            GitHub Release for this job before the scheduled two-day cleanup.
          </p>
        </Endpoint>

        <Separator className="my-8" />

        <Endpoint method="GET" path="/api/status/:jobId" tone="bg-blue-600">
          <p className="text-muted-foreground">
            Check build status. Poll every 5-10 seconds. When GitHub Actions
            metadata is available, the response includes live step timings.
          </p>
          <div>
            <h3 className="mb-2 font-heading font-semibold text-foreground">
              Response (building)
            </h3>
            <CodeBlock>{`{
  "job_id": "4c1e14f7",
  "status": "building",
  "build_steps": [
    { "key": "queue", "label": "Queuing build on GitHub Actions", "status": "complete", "seconds": 4 },
    { "key": "download", "label": "Downloading FASTA", "status": "running", "seconds": 18 },
    { "key": "twobit", "label": "Converting to 2bit format", "status": "pending" }
  ],
  "workflow_run_url": "https://github.com/.../actions/runs/123456789"
}`}</CodeBlock>
          </div>
          <div>
            <h3 className="mb-2 font-heading font-semibold text-foreground">
              Response (complete)
            </h3>
            <CodeBlock>{`{
  "job_id": "4c1e14f7",
  "status": "complete",
  "package_name": "BSgenome.Hsapiens.NCBI.GRCh38 1.0.0",
  "download_url": "https://github.com/.../BSgenome.Hsapiens.NCBI.GRCh38_1.0.0.tar.gz",
  "file_name": "BSgenome.Hsapiens.NCBI.GRCh38_1.0.0.tar.gz",
  "file_size": 782000000,
  "published": false,
  "total_seconds": 226
}`}</CodeBlock>
          </div>
          <div>
            <h3 className="mb-2 font-heading font-semibold text-foreground">
              Response (failed)
            </h3>
            <CodeBlock>{`{
  "job_id": "4c1e14f7",
  "status": "failed",
  "message": "BUILD_FAILED: Downloading FASTA failed. Check the linked GitHub Actions run for detailed logs.",
  "workflow_run_url": "https://github.com/.../actions/runs/123456789"
}`}</CodeBlock>
          </div>
        </Endpoint>

        <Separator className="my-8" />

        <Endpoint method="GET" path="/api/queue" tone="bg-blue-600">
          <p className="text-muted-foreground">
            Check current GitHub Actions queue depth.
          </p>
          <CodeBlock>{`{
  "running": 1,
  "queued": 2,
  "total": 3,
  "max_queue": 10,
  "runs": [
    { "id": 123, "status": "running", "name": "Build BSgenome.Xxx (...)", "created_at": "2026-07-01T12:00:00Z" }
  ]
}`}</CodeBlock>
        </Endpoint>

        <Separator className="my-8" />

        <Endpoint method="DELETE" path="/api/build/:jobId" tone="bg-red-600">
          <p className="text-muted-foreground">
            Delete a temporary <code>build-&lt;jobId&gt;</code> release and tag.
            This only applies to temporary build downloads.
          </p>
          <CodeBlock>{`{
  "delete_token": "hmac-token-from-post-build"
}`}</CodeBlock>
          <CodeBlock>{`{
  "status": "deleted",
  "job_id": "4c1e14f7",
  "release_deleted": true,
  "tag_deleted": true
}`}</CodeBlock>
        </Endpoint>

        <Separator className="my-8" />

        <Endpoint method="POST" path="/api/uploads" tone="bg-green-600">
          <p className="text-muted-foreground">
            Create a multipart upload session for a local nucleotide FASTA file.
            Uploads are staged in private R2 storage and expire after two days.
          </p>
          <CodeBlock>{`{
  "file_name": "my-genome.fasta.gz",
  "file_size": 73400320,
  "content_type": "application/gzip"
}`}</CodeBlock>
          <CodeBlock>{`{
  "upload_id": "9ccfb9e2-0ab9-4a23-a9de-6f8fd4c67c0a",
  "part_size": 67108864,
  "part_url_template": "${WORKER}/api/uploads/.../parts/{part_number}?...",
  "complete_url": "${WORKER}/api/uploads/.../complete?...",
  "download_url": "${WORKER}/api/uploads/...",
  "delete_url": "${WORKER}/api/uploads/...",
  "expires_at": "2026-07-03T12:00:00.000Z",
  "max_upload_bytes": 4294967296
}`}</CodeBlock>
          <p className="text-sm leading-6 text-muted-foreground">
            Supported filenames end in <code>.fa</code>, <code>.fasta</code>,{" "}
            <code>.fna</code>, or <code>.fas</code>, optionally with{" "}
            <code>.gz</code>. Protein FASTA extensions such as{" "}
            <code>.faa</code>, <code>.pep</code>, and <code>.aa</code> are
            rejected. Maximum browser upload size is 4 GB.
          </p>
        </Endpoint>

        <Separator className="my-8" />

        <section className="space-y-4">
          <h2 className="text-2xl font-bold">Examples</h2>

          <div>
            <h3 className="mb-2 font-heading font-semibold text-foreground">
              curl (bash)
            </h3>
            <CodeBlock>{`# 1. Trigger build
JOB=$(curl -s -X POST ${WORKER}/api/build \\
  -H "Content-Type: application/json" \\
  -d '{"package_name":"BSgenome.Scerevisiae.NCBI.R64","organism":"Saccharomyces cerevisiae","genome":"R64","provider":"NCBI","version":"1.0.0","accession":"GCF_000146045.2","data_source":"ncbi","circ_seqs":"MT"}')
JOB_ID=$(echo "$JOB" | python3 -c "import json,sys; print(json.load(sys.stdin)['job_id'])")
DELETE_TOKEN=$(echo "$JOB" | python3 -c "import json,sys; print(json.load(sys.stdin)['delete_token'])")

# 2. Poll for completion
while true; do
  STATUS=$(curl -s "${WORKER}/api/status/$JOB_ID")
  echo "$STATUS"
  echo "$STATUS" | python3 -c "import json,sys; s=json.load(sys.stdin)['status']; exit(0 if s in ('complete','failed') else 1)" && break
  sleep 10
done

# 3. Install in R when complete
URL=$(echo "$STATUS" | python3 -c "import json,sys; print(json.load(sys.stdin).get('download_url',''))")
Rscript -e "url <- '$URL'; pkg <- tempfile(fileext = '.tar.gz'); download.file(url, pkg, mode = 'wb', method = 'libcurl'); install.packages(pkg, repos = NULL, type = 'source'); unlink(pkg)"

# Optional: delete the temporary public release early
curl -X DELETE "${WORKER}/api/build/$JOB_ID" \\
  -H "Content-Type: application/json" \\
  -d "{\\"delete_token\\":\\"$DELETE_TOKEN\\"}"
`}</CodeBlock>
          </div>

          <div>
            <h3 className="mb-2 font-heading font-semibold text-foreground">
              R install command
            </h3>
            <CodeBlock>{`url <- "TARBALL_URL_FROM_STATUS_OR_PACKAGE_CARD"
pkg <- tempfile(fileext = ".tar.gz")
download.file(url, pkg, mode = "wb", method = "libcurl")
install.packages(pkg, repos = NULL, type = "source")
unlink(pkg)`}</CodeBlock>
          </div>
        </section>

        <Separator className="my-8" />

        <section>
          <h2 className="mb-3 text-2xl font-bold">Limits &amp; Notes</h2>
          <ul className="space-y-2 text-muted-foreground">
            <li>Build requests are queued through GitHub Actions.</li>
            <li>Status responses include live step timings when GitHub run metadata is available.</li>
            <li>Temporary build releases are automatically cleaned up after two days.</li>
            <li>Users can delete their current temporary build earlier with the returned <code>delete_token</code>.</li>
            <li>Permanent package repository inclusion is curated by maintainers and is not available through the public API.</li>
            <li>CORS is enabled for the AutoBSgenome site, staging Workers, preview deployments, and localhost development.</li>
          </ul>
        </section>
      </main>

      <SiteFooter />
    </div>
  );
}
