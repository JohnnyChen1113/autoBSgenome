import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";

export default function ApiDocs() {
  const WORKER = "https://autobsgenome-api.dailylifecjh.workers.dev";

  return (
    <div className="flex flex-col flex-1 bg-background">
      <header className="border-b border-border">
        <div className="mx-auto max-w-4xl px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded bg-primary flex items-center justify-center">
              <span className="text-primary-foreground font-mono text-xs font-bold">BS</span>
            </div>
            <span className="font-heading text-lg font-semibold">AutoBSgenome API</span>
          </div>
          <nav className="flex items-center gap-5 text-base text-muted-foreground">
            <a href="/" className="hover:text-foreground transition-colors">Build Tool</a>
            <a href="https://johnnychen1113.github.io/autoBSgenome" className="hover:text-foreground transition-colors">Browse Packages</a>
          </nav>
        </div>
      </header>

      <main className="flex-1 mx-auto max-w-4xl px-6 py-12">
        <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">API Reference</h1>
        <p className="mt-3 text-lg text-muted-foreground">
          Build BSgenome packages programmatically. Free, no authentication required.
        </p>
        <p className="mt-2 text-sm text-muted-foreground">
          Base URL: <code className="font-mono text-primary bg-accent px-2 py-0.5 rounded">{WORKER}</code>
        </p>

        <Separator className="my-8" />

        {/* POST /api/build */}
        <section className="space-y-4">
          <div className="flex items-center gap-3">
            <Badge className="bg-green-600 text-white">POST</Badge>
            <code className="font-mono text-lg font-semibold">/api/build</code>
          </div>
          <p className="text-muted-foreground">Trigger a new BSgenome package build.</p>

          <div>
            <h3 className="font-heading font-semibold text-foreground mb-2">Request Body</h3>
            <div className="bg-secondary border border-border rounded-lg p-4 font-mono text-sm overflow-x-auto">
              <pre>{`{
  "package_name": "BSgenome.Hsapiens.NCBI.GRCh38",
  "organism": "Homo sapiens",
  "common_name": "Human",        // optional
  "genome": "GRCh38",            // optional
  "provider": "NCBI",            // optional
  "version": "1.0.0",            // optional, default "1.0.0"
  "circ_seqs": "MT",             // optional, or "character(0)"
  "accession": "GCF_000001405.40",
  "data_source": "ncbi"          // "ncbi" or "ensembl"
}`}</pre>
            </div>
          </div>

          <div>
            <h3 className="font-heading font-semibold text-foreground mb-2">Response</h3>
            <div className="bg-secondary border border-border rounded-lg p-4 font-mono text-sm">
              <pre>{`{
  "job_id": "4c1e14f7",
  "status": "queued",
  "queue_position": 0
}`}</pre>
            </div>
          </div>
        </section>

        <Separator className="my-8" />

        {/* GET /api/status */}
        <section className="space-y-4">
          <div className="flex items-center gap-3">
            <Badge className="bg-blue-600 text-white">GET</Badge>
            <code className="font-mono text-lg font-semibold">/api/status/:jobId</code>
          </div>
          <p className="text-muted-foreground">Check build status. Poll every 5–10 seconds.</p>

          <div>
            <h3 className="font-heading font-semibold text-foreground mb-2">Response (building)</h3>
            <div className="bg-secondary border border-border rounded-lg p-4 font-mono text-sm">
              <pre>{`{ "job_id": "4c1e14f7", "status": "building" }`}</pre>
            </div>
          </div>

          <div>
            <h3 className="font-heading font-semibold text-foreground mb-2">Response (complete)</h3>
            <div className="bg-secondary border border-border rounded-lg p-4 font-mono text-sm">
              <pre>{`{
  "job_id": "4c1e14f7",
  "status": "complete",
  "package_name": "BSgenome.Hsapiens.NCBI.GRCh38 1.0.0",
  "download_url": "https://github.com/.../BSgenome...tar.gz",
  "file_name": "BSgenome.Hsapiens.NCBI.GRCh38_1.0.0.tar.gz",
  "file_size": 782000000
}`}</pre>
            </div>
          </div>
        </section>

        <Separator className="my-8" />

        {/* GET /api/queue */}
        <section className="space-y-4">
          <div className="flex items-center gap-3">
            <Badge className="bg-blue-600 text-white">GET</Badge>
            <code className="font-mono text-lg font-semibold">/api/queue</code>
          </div>
          <p className="text-muted-foreground">Check current build queue status.</p>

          <div>
            <h3 className="font-heading font-semibold text-foreground mb-2">Response</h3>
            <div className="bg-secondary border border-border rounded-lg p-4 font-mono text-sm">
              <pre>{`{
  "running": 2,
  "queued": 1,
  "total": 3,
  "runs": [
    { "id": 123, "status": "running", "name": "Build BSgenome.Xxx (...)" }
  ]
}`}</pre>
            </div>
          </div>
        </section>

        <Separator className="my-8" />

        {/* Examples */}
        <section className="space-y-4">
          <h2 className="text-2xl font-bold">Examples</h2>

          <div>
            <h3 className="font-heading font-semibold text-foreground mb-2">curl (bash)</h3>
            <div className="bg-secondary border border-border rounded-lg p-4 font-mono text-sm overflow-x-auto">
              <pre>{`# 1. Trigger build
JOB=$(curl -s -X POST ${WORKER}/api/build \\
  -H "Content-Type: application/json" \\
  -d '{"package_name":"BSgenome.Scerevisiae.NCBI.R64","organism":"Saccharomyces cerevisiae","accession":"GCF_000146045.2","data_source":"ncbi","circ_seqs":"MT"}')
JOB_ID=$(echo $JOB | python3 -c "import json,sys;print(json.load(sys.stdin)['job_id'])")

# 2. Poll for completion
while true; do
  STATUS=$(curl -s "${WORKER}/api/status/$JOB_ID")
  echo $STATUS | python3 -c "import json,sys;print(json.load(sys.stdin)['status'])"
  echo $STATUS | python3 -c "import json,sys;d=json.load(sys.stdin);exit(0 if d['status'] in ('complete','failed') else 1)" && break
  sleep 10
done

# 3. Install in R
URL=$(echo $STATUS | python3 -c "import json,sys;print(json.load(sys.stdin)['download_url'])")
Rscript -e "install.packages('$URL', repos=NULL, type='source')"
`}</pre>
            </div>
          </div>

          <div>
            <h3 className="font-heading font-semibold text-foreground mb-2">R</h3>
            <div className="bg-secondary border border-border rounded-lg p-4 font-mono text-sm overflow-x-auto">
              <pre>{`# Install from community repository (if already built)
install.packages("BSgenome.Scerevisiae.NCBI.R64",
  repos = "https://johnnychen1113.github.io/autoBSgenome")

# Or install from direct URL
install.packages(
  "https://github.com/.../BSgenome.Scerevisiae.NCBI.R64_1.0.0.tar.gz",
  repos = NULL, type = "source")
`}</pre>
            </div>
          </div>
        </section>

        <Separator className="my-8" />

        <section>
          <h2 className="text-2xl font-bold mb-3">Rate Limits &amp; Notes</h2>
          <ul className="space-y-2 text-muted-foreground">
            <li>No authentication required</li>
            <li>Builds are queued and processed sequentially (~45s for small genomes, ~5min for large)</li>
            <li>Packages are permanently published to the community repository</li>
            <li>CORS enabled for browser requests from any origin</li>
          </ul>
        </section>
      </main>

      <footer className="border-t border-border bg-secondary">
        <div className="mx-auto max-w-4xl px-6 py-6 text-center text-sm text-muted-foreground">
          <a href="https://github.com/JohnnyChen1113/autoBSgenome" className="text-primary hover:underline">AutoBSgenome</a>
          {" "}&mdash; Making BSgenome accessible for every organism.
        </div>
      </footer>
    </div>
  );
}
