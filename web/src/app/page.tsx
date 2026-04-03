"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import {
  extractAccession,
  fetchAssemblyInfo,
  fetchCircularSequences,
  generatePackageName,
  generateTitle,
  generateDescription,
  type CircularSequence,
} from "@/lib/ncbi";
import {
  extractEnsemblSpecies,
  fetchEnsemblAssemblyInfo,
  detectCircularFromKaryotype,
} from "@/lib/ensembl";

type DataSource = "ncbi" | "ensembl";

interface FormData {
  packageName: string;
  organism: string;
  commonName: string;
  assembly: string;
  provider: string;
  releaseDate: string;
  version: string;
  circSeqs: string;
  title: string;
  description: string;
  sourceUrl: string;
  fastaSource: "ncbi" | "upload";
}

const EMPTY_FORM: FormData = {
  packageName: "",
  organism: "",
  commonName: "",
  assembly: "",
  provider: "",
  releaseDate: "",
  version: "1.0.0",
  circSeqs: "",
  title: "",
  description: "",
  sourceUrl: "",
  fastaSource: "ncbi",
};

type Step = "input" | "review" | "building" | "result";

interface BuildRecord {
  jobId: string;
  packageName: string;
  organism: string;
  downloadUrl: string;
  buildTime: number;
  timestamp: number;
}

function saveBuildRecord(record: BuildRecord) {
  try {
    const history: BuildRecord[] = JSON.parse(
      localStorage.getItem("autobsgenome_history") ?? "[]"
    );
    history.unshift(record);
    // Keep last 20
    localStorage.setItem(
      "autobsgenome_history",
      JSON.stringify(history.slice(0, 20))
    );
  } catch {}
}

function loadBuildHistory(): BuildRecord[] {
  try {
    return JSON.parse(localStorage.getItem("autobsgenome_history") ?? "[]");
  } catch {
    return [];
  }
}

export default function Home() {
  const [step, setStep] = useState<Step>("input");
  const [buildHistory, setBuildHistory] = useState<BuildRecord[]>([]);

  // Load build history on mount
  useEffect(() => {
    setBuildHistory(loadBuildHistory());
  }, []);
  const [dataSource, setDataSource] = useState<DataSource>("ncbi");
  const [accessionInput, setAccessionInput] = useState("");
  const [form, setForm] = useState<FormData>(EMPTY_FORM);
  const [circularSeqs, setCircularSeqs] = useState<CircularSequence[]>([]);
  const [fetching, setFetching] = useState(false);
  const [error, setError] = useState("");
  const [gcfSuggestion, setGcfSuggestion] = useState<string | null>(null);
  const [packageValidation, setPackageValidation] = useState<{
    status: "idle" | "valid" | "invalid";
    errors: string[];
  }>({ status: "idle", errors: [] });

  const validatePackageName = useCallback((name: string) => {
    const errors: string[] = [];
    const parts = name.split(".");

    if (parts.length !== 4) {
      errors.push("Must have exactly 4 parts separated by dots.");
    } else {
      if (parts[0] !== "BSgenome") {
        errors.push('Part 1 must be "BSgenome".');
      }
      if (!/^[A-Z][a-z]+$/.test(parts[1])) {
        errors.push(
          "Part 2 (organism) must start with uppercase followed by lowercase (e.g. Hsapiens)."
        );
      }
      if (!/^[A-Za-z]+$/.test(parts[2])) {
        errors.push("Part 3 (provider) must be letters only (e.g. NCBI, UCSC).");
      }
      if (!/^[A-Za-z0-9]+$/.test(parts[3])) {
        errors.push(
          "Part 4 (assembly) must be alphanumeric only (e.g. GRCh38, hg38)."
        );
      }
    }

    if (errors.length === 0) {
      setPackageValidation({ status: "valid", errors: [] });
    } else {
      setPackageValidation({ status: "invalid", errors });
    }
  }, []);

  const updateField = useCallback(
    (field: keyof FormData, value: string) => {
      setForm((prev) => ({ ...prev, [field]: value }));
      // Reset validation when package name changes
      if (field === "packageName") {
        setPackageValidation({ status: "idle", errors: [] });
      }
    },
    []
  );

  const handleFetch = async () => {
    setError("");
    setFetching(true);

    try {
      let newForm: FormData;
      let circs: CircularSequence[] = [];

      if (dataSource === "ensembl") {
        // ── Ensembl path ──
        const species = extractEnsemblSpecies(accessionInput.trim());
        if (!species) {
          setError(
            "Could not detect species. Paste an Ensembl URL (e.g. https://www.ensembl.org/Danio_rerio/Info/Index) or enter a species name (e.g. danio_rerio)."
          );
          setFetching(false);
          return;
        }

        const ensInfo = await fetchEnsemblAssemblyInfo(species);
        const circNames = detectCircularFromKaryotype(ensInfo.karyotype);

        // Build abbreviation from organism
        const orgParts = ensInfo.organism.trim().split(/\s+/);
        const abbrev =
          orgParts.length >= 2
            ? orgParts[0][0].toUpperCase() + orgParts[1].toLowerCase()
            : orgParts[0];
        const assembly = ensInfo.assemblyName.replace(/\./g, "").replace(/[^a-zA-Z0-9]/g, "");

        newForm = {
          packageName: `BSgenome.${abbrev}.Ensembl.${assembly}`,
          organism: ensInfo.organism,
          commonName: ensInfo.commonName,
          assembly: ensInfo.assemblyName,
          provider: "Ensembl",
          releaseDate: "",
          version: "1.0.0",
          circSeqs: circNames.length > 0 ? circNames.join(", ") : "character(0)",
          title: `Full genome sequences for ${ensInfo.organism} (Ensembl version ${ensInfo.assemblyName})`,
          description: `Full genome sequences for ${ensInfo.organism} (${ensInfo.commonName}) as provided by Ensembl (${ensInfo.assemblyName}) and stored in Biostrings objects.`,
          sourceUrl: `https://www.ensembl.org/${species.charAt(0).toUpperCase() + species.slice(1)}/Info/Index`,
          fastaSource: "ncbi",
        };

        setGcfSuggestion(null);
      } else {
        // ── NCBI path ──
        const accession = extractAccession(accessionInput.trim());
        if (!accession) {
          setError(
            "Invalid accession. Enter a valid NCBI accession (e.g. GCF_000001405.40) or paste a full URL."
          );
          setFetching(false);
          return;
        }

        const [info, ncbiCircs] = await Promise.all([
          fetchAssemblyInfo(accession),
          fetchCircularSequences(accession),
        ]);
        circs = ncbiCircs;

        const circSeqsStr =
          circs.length > 0
            ? circs.map((c) => c.name).join(", ")
            : "character(0)";

        newForm = {
          packageName: generatePackageName(info),
          organism: info.organism,
          commonName: info.commonName,
          assembly: info.assemblyName,
          provider: info.provider,
          releaseDate: info.releaseDate,
          version: "1.0.0",
          circSeqs: circSeqsStr,
          title: generateTitle(info),
          description: generateDescription(info, info.commonName),
          sourceUrl: info.sourceUrl,
          fastaSource: "ncbi",
        };

        // If GCA_ has no circular seqs but has a paired GCF_, suggest switching
        if (
          accession.startsWith("GCA_") &&
          circs.length === 0 &&
          info.pairedAccession
        ) {
          setGcfSuggestion(info.pairedAccession);
        } else {
          setGcfSuggestion(null);
        }
      }

      setCircularSeqs(circs);
      setForm(newForm);
      validatePackageName(newForm.packageName);
      setStep("review");
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : "Failed to fetch assembly info. Please check your accession."
      );
    } finally {
      setFetching(false);
    }
  };

  const [jobId, setJobId] = useState("");
  const [buildError, setBuildError] = useState("");
  const [downloadUrl, setDownloadUrl] = useState("");
  const [fileName, setFileName] = useState("");
  const [fileSize, setFileSize] = useState(0);
  const [buildStep, setBuildStep] = useState(0);
  const [buildStartTime, setBuildStartTime] = useState(0);
  const [buildElapsed, setBuildElapsed] = useState(0);
  const [buildTotalTime, setBuildTotalTime] = useState(0);

  const WORKER_API = "https://autobsgenome-api.dailylifecjh.workers.dev";
  const buildStartTimeRef = useRef(0);
  const formRef = useRef(form);
  formRef.current = form;

  // Restore build state from URL on page load
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const resumeJob = params.get("job");
    if (resumeJob) {
      setJobId(resumeJob);
      const now = Date.now();
      setBuildStartTime(now);
      buildStartTimeRef.current = now;
      setStep("building");
      pollBuildStatus(resumeJob);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 1-second timer for display (independent of 5s poll)
  useEffect(() => {
    if (step !== "building" || buildStartTime === 0) return;
    const tick = setInterval(() => {
      setBuildElapsed(Math.floor((Date.now() - buildStartTime) / 1000));
    }, 1000);
    return () => clearInterval(tick);
  }, [step, buildStartTime]);

  const handleBuild = async () => {
    setStep("building");
    setBuildError("");
    setBuildStep(0);
    const startTime = Date.now();
    setBuildStartTime(startTime);
    buildStartTimeRef.current = startTime;
    setBuildElapsed(0);
    setBuildTotalTime(0);

    try {
      // Trigger build via Worker API
      const res = await fetch(`${WORKER_API}/api/build`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          package_name: form.packageName,
          organism: form.organism,
          common_name: form.commonName,
          genome: form.assembly,
          provider: form.provider,
          release_date: form.releaseDate,
          version: form.version,
          circ_seqs: form.circSeqs,
          title: form.title,
          description: form.description,
          source_url: form.sourceUrl,
          accession: accessionInput,
          fasta_source: form.fastaSource,
          data_source: dataSource,
        }),
      });

      const data = await res.json() as { job_id?: string; error?: string };
      if (!res.ok || !data.job_id) {
        throw new Error(data.error ?? "Failed to start build");
      }

      setJobId(data.job_id);
      setBuildStep(1);

      // Save jobId to URL so page refresh can resume polling
      window.history.replaceState(null, "", `?job=${data.job_id}`);

      // Poll for status
      pollBuildStatus(data.job_id);
    } catch (e) {
      setBuildError(e instanceof Error ? e.message : "Build request failed");
      setStep("review");
    }
  };

  const pollBuildStatus = (id: string) => {
    let errorCount = 0;
    let pollCount = 0;
    const interval = setInterval(async () => {
      pollCount++;
      const elapsedSec = Math.floor((Date.now() - buildStartTimeRef.current) / 1000);

      // Animate build steps based on elapsed time
      if (elapsedSec > 5) setBuildStep(1);
      if (elapsedSec > 15) setBuildStep(2);
      if (elapsedSec > 30) setBuildStep(3);

      try {
        const res = await fetch(`${WORKER_API}/api/status/${id}`);
        const data = await res.json() as {
          status: string;
          download_url?: string;
          file_name?: string;
          file_size?: number;
          message?: string;
        };

        if (data.status === "complete") {
          clearInterval(interval);
          setBuildStep(4);
          const totalTime = Math.floor((Date.now() - buildStartTimeRef.current) / 1000);
          setBuildTotalTime(totalTime);
          setDownloadUrl(data.download_url ?? "");
          setFileName(data.file_name ?? "");
          setFileSize(data.file_size ?? 0);
          const record: BuildRecord = {
            jobId: id,
            packageName: formRef.current.packageName,
            organism: formRef.current.organism,
            downloadUrl: data.download_url ?? "",
            buildTime: totalTime,
            timestamp: Date.now(),
          };
          saveBuildRecord(record);
          setBuildHistory(loadBuildHistory());
          window.history.replaceState(null, "", window.location.pathname);
          setStep("result");
          return;
        } else if (data.status === "failed") {
          clearInterval(interval);
          setBuildError(data.message ?? "Build failed");
          setStep("review");
          return;
        } else if (data.status === "error") {
          errorCount++;
          // After 6 consecutive errors (30s), show a helpful message but keep polling
          if (errorCount >= 6 && errorCount % 6 === 0) {
            setBuildError(
              `Status check temporarily unavailable (${data.message ?? "API error"}). ` +
              `Your build is likely still running. You can check GitHub Actions directly: ` +
              `https://github.com/JohnnyChen1113/autoBSgenome/actions`
            );
          }
        } else {
          // "building" status — reset error count
          errorCount = 0;
          setBuildError("");
        }
      } catch {
        errorCount++;
      }

      // Timeout after 10 minutes
      if (elapsedSec > 600) {
        clearInterval(interval);
        setBuildError(
          "Status polling timed out after 10 minutes. Your build may still be running — " +
          "check https://github.com/JohnnyChen1113/autoBSgenome/releases for your package."
        );
        setStep("review");
      }
    }, 5000);
  };

  return (
    <div className="flex flex-col flex-1 bg-background">
      {/* Header */}
      <header className="border-b border-border">
        <div className="mx-auto max-w-4xl px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded bg-primary flex items-center justify-center">
              <span className="text-primary-foreground font-mono text-xs font-bold">
                BS
              </span>
            </div>
            <span className="font-heading text-lg font-semibold text-foreground">
              AutoBSgenome
            </span>
          </div>
          <nav className="flex items-center gap-5 text-base text-muted-foreground">
            <a
              href="https://github.com/JohnnyChen1113/autoBSgenome"
              className="hover:text-foreground transition-colors"
            >
              GitHub
            </a>
            <a
              href="https://bioconductor.org/packages/BSgenome/"
              className="hover:text-foreground transition-colors"
            >
              BSgenome Docs
            </a>
          </nav>
        </div>
      </header>

      <main className="flex-1">
        {/* Hero */}
        <section className="mx-auto max-w-4xl px-6 pt-12 pb-8 sm:pt-16 sm:pb-12 text-center">
          <h1 className="text-3xl font-bold tracking-tight text-foreground sm:text-5xl">
            Build BSgenome R Packages Online
          </h1>
          <p className="mt-4 text-lg text-muted-foreground max-w-2xl mx-auto leading-relaxed">
            Paste an NCBI accession or Ensembl URL, review auto-filled metadata,
            and download a ready-to-install BSgenome package. No local R setup required.
          </p>
        </section>

        {/* How it works */}
        {step === "input" && (
          <section className="mx-auto max-w-4xl px-6 pb-8">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-center">
              {[
                {
                  num: "1",
                  title: "Paste Accession",
                  desc: "Enter an NCBI or Ensembl accession — metadata fills automatically",
                },
                {
                  num: "2",
                  title: "Review & Build",
                  desc: "Check the auto-filled fields, then click Build",
                },
                {
                  num: "3",
                  title: "Download Package",
                  desc: "Get your .tar.gz in under a minute — install with R CMD INSTALL",
                },
              ].map((s) => (
                <div
                  key={s.num}
                  className="flex flex-col items-center gap-2 p-4 rounded-lg bg-secondary/50"
                >
                  <div className="w-8 h-8 rounded-full bg-primary text-primary-foreground flex items-center justify-center text-sm font-bold">
                    {s.num}
                  </div>
                  <h3 className="font-heading font-semibold text-foreground">
                    {s.title}
                  </h3>
                  <p className="text-sm text-muted-foreground">{s.desc}</p>
                </div>
              ))}
            </div>
          </section>
        )}

        <div className="mx-auto max-w-4xl px-6 pb-20">
          {/* ─── Step 1: Input ─── */}
          {step === "input" && (
            <Card>
              <CardHeader>
                <CardTitle>Enter Genome Information</CardTitle>
                <CardDescription>
                  Choose a data source and provide an accession or URL to auto-fill all metadata.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Data source toggle */}
                <div className="space-y-2">
                  <Label>Data Source</Label>
                  <div className="grid grid-cols-2 gap-2">
                    <button
                      type="button"
                      className={`rounded-md border px-4 py-2.5 text-sm font-medium transition-colors cursor-pointer ${
                        dataSource === "ncbi"
                          ? "bg-accent border-primary text-primary"
                          : "bg-background border-border text-muted-foreground hover:bg-secondary"
                      }`}
                      onClick={() => {
                        setDataSource("ncbi");
                        setAccessionInput("");
                        setError("");
                      }}
                    >
                      NCBI
                    </button>
                    <button
                      type="button"
                      className={`rounded-md border px-4 py-2.5 text-sm font-medium transition-colors cursor-pointer ${
                        dataSource === "ensembl"
                          ? "bg-accent border-primary text-primary"
                          : "bg-background border-border text-muted-foreground hover:bg-secondary"
                      }`}
                      onClick={() => {
                        setDataSource("ensembl");
                        setAccessionInput("");
                        setError("");
                      }}
                    >
                      Ensembl
                    </button>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="accession">
                    {dataSource === "ncbi"
                      ? "NCBI Assembly Accession or URL"
                      : "Ensembl Species URL or Name"}
                  </Label>
                  <div className="flex gap-2">
                    <Input
                      id="accession"
                      placeholder={
                        dataSource === "ncbi"
                          ? "e.g. GCF_000001405.40 or https://ncbi.nlm.nih.gov/assembly/..."
                          : "e.g. https://www.ensembl.org/Danio_rerio/Info/Index or danio_rerio"
                      }
                      className="font-mono flex-1"
                      value={accessionInput}
                      onChange={(e) => setAccessionInput(e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && handleFetch()}
                    />
                    <Button onClick={handleFetch} disabled={fetching} className="min-w-[90px]">
                      {fetching ? (
                        <span className="flex items-center gap-1.5">
                          <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"/>
                          </svg>
                          Fetching
                        </span>
                      ) : "Fetch"}
                    </Button>
                  </div>
                  {dataSource === "ncbi" ? (
                    <p className="text-sm text-muted-foreground">
                      Supports GCF_ (RefSeq) and GCA_ (GenBank) accessions.
                      Examples:{" "}
                      <button
                        type="button"
                        className="font-mono text-primary hover:underline cursor-pointer"
                        onClick={() => setAccessionInput("GCF_016861625.1")}
                      >
                        GCF_016861625.1
                      </button>
                      {" · "}
                      <button
                        type="button"
                        className="font-mono text-primary hover:underline cursor-pointer"
                        onClick={() => setAccessionInput("GCA_000002515.2")}
                      >
                        GCA_000002515.2
                      </button>
                    </p>
                  ) : (
                    <p className="text-sm text-muted-foreground">
                      Paste an Ensembl species page URL or enter a species name.
                      Examples:{" "}
                      <button
                        type="button"
                        className="font-mono text-primary hover:underline cursor-pointer"
                        onClick={() =>
                          setAccessionInput(
                            "https://www.ensembl.org/Danio_rerio/Info/Index"
                          )
                        }
                      >
                        Danio_rerio
                      </button>
                      {" · "}
                      <button
                        type="button"
                        className="font-mono text-primary hover:underline cursor-pointer"
                        onClick={() =>
                          setAccessionInput(
                            "https://www.ensembl.org/Saccharomyces_cerevisiae/Info/Index"
                          )
                        }
                      >
                        Saccharomyces_cerevisiae
                      </button>
                    </p>
                  )}
                </div>

                {error && (
                  <div className="bg-destructive/10 border border-destructive/20 text-destructive rounded-md px-4 py-3 text-sm">
                    {error}
                  </div>
                )}

                <div className="relative py-2">
                  <Separator />
                  <span className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 bg-card px-3 text-sm text-muted-foreground">
                    or fill in manually
                  </span>
                </div>

                <Button
                  variant="outline"
                  className="w-full"
                  onClick={() => setStep("review")}
                >
                  Skip to manual entry
                </Button>
              </CardContent>
            </Card>
          )}

          {/* ─── Step 2: Review ─── */}
          {step === "review" && (
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle>Review Metadata</CardTitle>
                    <CardDescription>
                      Auto-filled from {dataSource === "ensembl" ? "Ensembl" : "NCBI"}. All fields are editable.
                    </CardDescription>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      setStep("input");
                      setError("");
                    }}
                  >
                    &larr; Back
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="space-y-5">
                {/* Build error */}
                {buildError && (
                  <div className="bg-destructive/10 border border-destructive/20 rounded-md px-4 py-3 text-sm space-y-3">
                    <p className="text-destructive">
                      <strong>Build failed:</strong> {buildError}
                    </p>
                    <a
                      href={`https://github.com/JohnnyChen1113/autoBSgenome/issues/new?${new URLSearchParams({
                        title: `Build failed: ${form.packageName}`,
                        body: [
                          "## Build Failure Report",
                          "",
                          "| Field | Value |",
                          "|-------|-------|",
                          "| **Package** | `" + form.packageName + "` |",
                          "| **Organism** | " + form.organism + " |",
                          "| **Common Name** | " + form.commonName + " |",
                          "| **Assembly** | " + form.assembly + " |",
                          "| **Provider** | " + form.provider + " |",
                          "| **Accession** | `" + accessionInput + "` |",
                          "| **Data Source** | " + dataSource + " |",
                          "| **Circular Seqs** | `" + form.circSeqs + "` |",
                          "| **Version** | " + form.version + " |",
                          "| **Job ID** | `" + (jobId || "N/A") + "` |",
                          "",
                          "## Error Message",
                          "```",
                          buildError,
                          "```",
                          "",
                          "## Debug Links",
                          "- [GitHub Actions Runs](https://github.com/JohnnyChen1113/autoBSgenome/actions/workflows/build-bsgenome.yml)",
                          jobId ? "- [GitHub Release (if created)](https://github.com/JohnnyChen1113/autoBSgenome/releases/tag/build-" + jobId + ")" : "",
                          "",
                          "## Additional Context",
                          "_Please describe what you were trying to do and any additional context._",
                          "",
                          "---",
                          "_Auto-generated by [AutoBSgenome Web](https://autobsgenome.pages.dev)_",
                        ].join("\n"),
                        labels: "build-failure",
                      }).toString()}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1.5 rounded-md border border-destructive/30 bg-background px-3 py-1.5 text-sm font-medium text-destructive hover:bg-destructive/5 transition-colors cursor-pointer"
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                      Report this issue on GitHub
                    </a>
                  </div>
                )}

                {/* GCA → GCF suggestion */}
                {gcfSuggestion && (
                  <div className="bg-amber-50 border border-amber-200 rounded-md px-4 py-3 text-sm">
                    <p className="text-amber-800">
                      <strong>Note:</strong> You used a GenBank accession (GCA_), which may not include
                      organelle sequences like mitochondria. A paired RefSeq version is available:{" "}
                      <code className="font-mono text-amber-900 font-medium">{gcfSuggestion}</code>
                    </p>
                    <div className="mt-2 flex gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        className="text-amber-800 border-amber-300 hover:bg-amber-100 cursor-pointer"
                        onClick={() => {
                          setAccessionInput(gcfSuggestion);
                          setGcfSuggestion(null);
                          setStep("input");
                        }}
                      >
                        Switch to {gcfSuggestion}
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="text-amber-600 cursor-pointer"
                        onClick={() => setGcfSuggestion(null)}
                      >
                        Keep current (GCA_)
                      </Button>
                    </div>
                  </div>
                )}

                {/* Package Name */}
                <div className="space-y-2">
                  <Label htmlFor="packageName">Package Name</Label>
                  <div className="flex gap-2">
                    <Input
                      id="packageName"
                      className={`font-mono flex-1 ${
                        packageValidation.status === "valid"
                          ? "border-[--success] focus-visible:border-[--success]"
                          : packageValidation.status === "invalid"
                          ? "border-destructive focus-visible:border-destructive"
                          : ""
                      }`}
                      placeholder="BSgenome.Organism.Provider.Assembly"
                      value={form.packageName}
                      onChange={(e) =>
                        updateField("packageName", e.target.value)
                      }
                    />
                    <Button
                      variant={
                        packageValidation.status === "valid"
                          ? "outline"
                          : "secondary"
                      }
                      onClick={() => validatePackageName(form.packageName)}
                      className={
                        packageValidation.status === "valid"
                          ? "text-[--success] border-[--success]/30 cursor-pointer"
                          : "cursor-pointer"
                      }
                    >
                      {packageValidation.status === "valid"
                        ? "✓ Valid"
                        : "Validate"}
                    </Button>
                  </div>
                  {packageValidation.status === "invalid" && (
                    <div className="bg-destructive/10 border border-destructive/20 text-destructive rounded-md px-3 py-2 text-sm space-y-1">
                      {packageValidation.errors.map((err, i) => (
                        <p key={i}>{err}</p>
                      ))}
                    </div>
                  )}
                  {packageValidation.status === "valid" && (
                    <p className="text-sm font-medium flex items-center gap-1.5" style={{ color: "#0f7b3f" }}>
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#0f7b3f" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/></svg>
                      Package name format is correct.
                    </p>
                  )}
                  {packageValidation.status === "idle" && (
                    <p className="text-sm text-muted-foreground">
                      4-part format: BSgenome.Organism.Provider.Assembly — click Validate to check
                    </p>
                  )}
                </div>

                {/* Organism + Common Name */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="organism">Organism</Label>
                    <Input
                      id="organism"
                      placeholder="e.g. Homo sapiens"
                      className="italic"
                      value={form.organism}
                      onChange={(e) =>
                        updateField("organism", e.target.value)
                      }
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="commonName">Common Name</Label>
                    <Input
                      id="commonName"
                      placeholder="e.g. Human"
                      value={form.commonName}
                      onChange={(e) =>
                        updateField("commonName", e.target.value)
                      }
                    />
                  </div>
                </div>

                {/* Assembly + Provider */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="assembly">Assembly</Label>
                    <Input
                      id="assembly"
                      className="font-mono"
                      placeholder="e.g. GRCh38.p14"
                      value={form.assembly}
                      onChange={(e) =>
                        updateField("assembly", e.target.value)
                      }
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="provider">Provider</Label>
                    <Input
                      id="provider"
                      placeholder="e.g. NCBI"
                      value={form.provider}
                      onChange={(e) =>
                        updateField("provider", e.target.value)
                      }
                    />
                  </div>
                </div>

                {/* Release Date + Version */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="releaseDate">Release Date</Label>
                    <Input
                      id="releaseDate"
                      placeholder="e.g. Feb. 2022"
                      value={form.releaseDate}
                      onChange={(e) =>
                        updateField("releaseDate", e.target.value)
                      }
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="version">Version</Label>
                    <Input
                      id="version"
                      className="font-mono"
                      placeholder="1.0.0"
                      value={form.version}
                      onChange={(e) =>
                        updateField("version", e.target.value)
                      }
                    />
                  </div>
                </div>

                {/* Circular Sequences */}
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <Label htmlFor="circSeqs">Circular Sequences</Label>
                    {circularSeqs.length > 0 && (
                      <Badge
                        variant="outline"
                        className="text-[--success] border-[--success]/30 text-[10px]"
                      >
                        Auto-detected
                      </Badge>
                    )}
                  </div>
                  <Input
                    id="circSeqs"
                    className="font-mono"
                    placeholder='character(0)'
                    value={form.circSeqs}
                    onChange={(e) =>
                      updateField("circSeqs", e.target.value)
                    }
                  />
                  {circularSeqs.length > 0 ? (
                    <p className="text-sm text-muted-foreground">
                      Detected:{" "}
                      {circularSeqs
                        .map((c) => `${c.name} (${c.type})`)
                        .join(", ")}
                    </p>
                  ) : (
                    <p className="text-sm text-muted-foreground">
                      Enter circular sequence names (e.g. MT, chrM) separated by
                      commas. Use{" "}
                      <code className="font-mono text-[11px]">character(0)</code>{" "}
                      only if the genome has no circular sequences.
                    </p>
                  )}
                </div>

                {/* FASTA Source */}
                <div className="space-y-2">
                  <Label>FASTA Source</Label>
                  <div className="grid grid-cols-2 gap-2">
                    <button
                      type="button"
                      className={`rounded-md border px-4 py-2.5 text-sm font-medium transition-colors cursor-pointer ${
                        form.fastaSource === "ncbi"
                          ? "bg-accent border-primary text-primary"
                          : "bg-background border-border text-muted-foreground hover:bg-secondary"
                      }`}
                      onClick={() => updateField("fastaSource", "ncbi")}
                    >
                      Use official FASTA
                    </button>
                    <button
                      type="button"
                      className={`rounded-md border px-4 py-2.5 text-sm font-medium transition-colors cursor-pointer ${
                        form.fastaSource === "upload"
                          ? "bg-accent border-primary text-primary"
                          : "bg-background border-border text-muted-foreground hover:bg-secondary"
                      }`}
                      onClick={() => updateField("fastaSource", "upload")}
                    >
                      Upload my own file
                    </button>
                  </div>
                </div>

                {/* Upload area (shown when "upload" selected) */}
                {form.fastaSource === "upload" && (
                  <div className="border-2 border-dashed border-border rounded-lg p-8 text-center cursor-pointer hover:border-primary/40 transition-colors">
                    <svg
                      className="mx-auto mb-2"
                      width="28"
                      height="28"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="1.5"
                    >
                      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                      <polyline points="17 8 12 3 7 8" />
                      <line x1="12" y1="3" x2="12" y2="15" />
                    </svg>
                    <p className="text-sm text-muted-foreground">
                      Drop FASTA file here or{" "}
                      <span className="text-primary underline">browse</span>
                    </p>
                    <p className="text-sm text-muted-foreground mt-1">
                      .fa, .fasta, .fna, .fas
                    </p>
                  </div>
                )}

                {/* Advanced Options */}
                <Accordion>
                  <AccordionItem value="advanced">
                    <AccordionTrigger className="text-sm">
                      Advanced options (Title, Description, Source URL...)
                    </AccordionTrigger>
                    <AccordionContent className="space-y-4 pt-2">
                      <div className="space-y-2">
                        <Label htmlFor="title">Title</Label>
                        <Input
                          id="title"
                          placeholder="Full genome sequences for..."
                          value={form.title}
                          onChange={(e) =>
                            updateField("title", e.target.value)
                          }
                        />
                        <p className="text-sm text-muted-foreground">
                          Auto-generated from BSgenome convention
                        </p>
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="description">Description</Label>
                        <textarea
                          id="description"
                          rows={2}
                          className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                          placeholder="Full genome sequences for..."
                          value={form.description}
                          onChange={(e) =>
                            updateField("description", e.target.value)
                          }
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="sourceUrl">Source URL</Label>
                        <Input
                          id="sourceUrl"
                          className="font-mono text-xs"
                          placeholder="https://www.ncbi.nlm.nih.gov/datasets/genome/..."
                          value={form.sourceUrl}
                          onChange={(e) =>
                            updateField("sourceUrl", e.target.value)
                          }
                        />
                      </div>
                    </AccordionContent>
                  </AccordionItem>
                </Accordion>

                {/* Build button */}
                <Button
                  size="lg"
                  className="w-full text-base cursor-pointer"
                  onClick={handleBuild}
                  disabled={
                    !form.packageName ||
                    !form.organism ||
                    packageValidation.status !== "valid"
                  }
                >
                  {packageValidation.status !== "valid"
                    ? "Validate Package Name First"
                    : "Build BSgenome Package"}
                </Button>
              </CardContent>
            </Card>
          )}

          {/* ─── Step 3: Building ─── */}
          {step === "building" && (
            <Card>
              <CardHeader>
                <CardTitle>Building Package...</CardTitle>
                <CardDescription>
                  This usually takes 3–10 minutes. You can keep this tab open.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6 py-8">
                <div className="space-y-4">
                  {[
                    "Queuing build on GitHub Actions",
                    "Downloading FASTA",
                    "Converting to 2bit format",
                    "Building R package",
                    "Uploading to repository",
                  ].map((label, i) => {
                    const done = i < buildStep;
                    const active = i === buildStep;
                    return (
                      <div key={i} className="flex items-center gap-3">
                        <div
                          className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
                            done
                              ? "bg-[--success] text-white"
                              : active
                              ? "bg-primary text-primary-foreground animate-pulse"
                              : "bg-secondary text-muted-foreground"
                          }`}
                        >
                          {done ? "✓" : i + 1}
                        </div>
                        <span
                          className={
                            done
                              ? "text-muted-foreground line-through"
                              : active
                              ? "text-foreground font-medium"
                              : "text-muted-foreground"
                          }
                        >
                          {label}
                        </span>
                      </div>
                    );
                  })}
                </div>
                <div className="text-center space-y-1">
                  <p className="text-2xl font-mono font-semibold text-foreground">
                    {Math.floor(buildElapsed / 60)}:{String(buildElapsed % 60).padStart(2, "0")}
                  </p>
                  <p className="text-sm text-muted-foreground">Elapsed time</p>
                  {jobId && (
                    <p className="text-sm text-muted-foreground">
                      Job ID: <code className="font-mono">{jobId}</code>
                    </p>
                  )}
                </div>
                {buildError && step === "building" && (
                  <div className="bg-amber-50 border border-amber-200 rounded-md px-4 py-3 text-sm text-amber-800">
                    {buildError}
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* ─── Step 4: Result ─── */}
          {step === "result" && (
            <Card>
              <CardHeader className="text-center pb-2">
                <div className="mx-auto w-14 h-14 rounded-full bg-[--success-foreground] text-[--success] flex items-center justify-center text-2xl font-bold mb-3">
                  ✓
                </div>
                <CardTitle className="text-xl">
                  Package Built Successfully
                </CardTitle>
                <CardDescription>
                  {fileName || `${form.packageName}_${form.version}.tar.gz`}
                  {fileSize > 0 && ` · ${(fileSize / 1024 / 1024).toFixed(1)} MB`}
                  {buildTotalTime > 0 && ` · Built in ${buildTotalTime}s`}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-5">
                <div className="flex gap-3 justify-center">
                  {downloadUrl ? (
                    <a
                      href={downloadUrl}
                      download
                      className="inline-flex items-center justify-center rounded-md bg-primary px-6 py-2.5 text-base font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
                    >
                      Download .tar.gz
                    </a>
                  ) : (
                    <Button size="lg" disabled>Download .tar.gz</Button>
                  )}
                  <Button
                    variant="outline"
                    size="lg"
                    onClick={() => {
                      const cmd = `install.packages("${downloadUrl}", repos = NULL, type = "source")`;
                      navigator.clipboard.writeText(cmd);
                    }}
                  >
                    Copy Install Command
                  </Button>
                </div>

                <Separator />

                <div className="space-y-2">
                  <Label>Install directly in R:</Label>
                  <div className="bg-secondary border border-border rounded-md p-3 font-mono text-sm leading-relaxed overflow-x-auto">
                    install.packages(
                    <br />
                    &nbsp;&nbsp;
                    <span className="text-primary">
                      &quot;{downloadUrl || "loading..."}&quot;
                    </span>
                    ,
                    <br />
                    &nbsp;&nbsp;repos = NULL, type ={" "}
                    <span className="text-primary">&quot;source&quot;</span>
                    <br />)
                  </div>
                </div>

                <div className="bg-accent border-l-[3px] border-primary rounded-r-md px-4 py-3 text-sm text-muted-foreground">
                  This package will remain available for{" "}
                  <strong className="text-foreground">14 days</strong> at{" "}
                  <a
                    href="https://github.com/JohnnyChen1113/autoBSgenome/releases"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary hover:underline"
                  >
                    GitHub Releases
                  </a>
                  . Download a local copy for permanent use.
                </div>

                {/* AI tool prompt */}
                <Accordion>
                  <AccordionItem value="ai-prompt">
                    <AccordionTrigger className="text-sm">
                      Use with AI coding tools (Claude Code, Claw, Cursor...)
                    </AccordionTrigger>
                    <AccordionContent>
                      <p className="text-sm text-muted-foreground mb-2">
                        Copy this prompt and paste it into your AI coding assistant:
                      </p>
                      <div className="relative">
                        <div className="bg-secondary border border-border rounded-md p-3 font-mono text-sm leading-relaxed overflow-x-auto">
                          Help me install this BSgenome R package:{" "}
                          {downloadUrl || `https://github.com/JohnnyChen1113/autoBSgenome/releases/download/build-${jobId}/${form.packageName}_${form.version}.tar.gz`}
                        </div>
                        <button
                          type="button"
                          className="absolute top-2 right-2 p-1.5 rounded bg-background border border-border text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
                          onClick={() => {
                            const prompt = `Help me install this BSgenome R package: ${downloadUrl || `https://github.com/JohnnyChen1113/autoBSgenome/releases/download/build-${jobId}/${form.packageName}_${form.version}.tar.gz`}`;
                            navigator.clipboard.writeText(prompt);
                          }}
                          title="Copy to clipboard"
                        >
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                        </button>
                      </div>
                    </AccordionContent>
                  </AccordionItem>
                </Accordion>

                <Button
                  variant="outline"
                  className="w-full"
                  onClick={() => {
                    setStep("input");
                    setForm(EMPTY_FORM);
                    setAccessionInput("");
                    setCircularSeqs([]);
                  }}
                >
                  Build Another Package
                </Button>
              </CardContent>
            </Card>
          )}

          {/* Recent Builds */}
          {buildHistory.length > 0 && step === "input" && (
            <Card className="mt-6">
              <CardHeader>
                <CardTitle className="text-lg">Recent Builds</CardTitle>
                <CardDescription>
                  Your previous builds (stored locally in this browser)
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {buildHistory.slice(0, 5).map((record) => (
                    <div
                      key={record.jobId}
                      className="flex items-center justify-between gap-4 p-3 rounded-md bg-secondary/50 border border-border"
                    >
                      <div className="min-w-0">
                        <p className="font-mono text-sm font-medium text-foreground truncate">
                          {record.packageName}
                        </p>
                        <p className="text-sm text-muted-foreground">
                          {record.organism} &middot; {record.buildTime}s &middot;{" "}
                          {new Date(record.timestamp).toLocaleDateString()}
                        </p>
                      </div>
                      {record.downloadUrl && (
                        <a
                          href={record.downloadUrl}
                          className="shrink-0 inline-flex items-center gap-1 rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
                        >
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                          Download
                        </a>
                      )}
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-border bg-secondary">
        <div className="mx-auto max-w-4xl px-6 py-6 text-center text-sm text-muted-foreground">
          <p>
            <a
              href="https://github.com/JohnnyChen1113/autoBSgenome"
              className="text-primary hover:underline"
            >
              AutoBSgenome
            </a>{" "}
            &mdash; Making BSgenome accessible for every organism.
          </p>
          <p className="mt-1 text-xs">
            Built by{" "}
            <a
              href="https://github.com/JohnnyChen1113"
              className="hover:underline"
            >
              Junhao Chen
            </a>{" "}
            at Saint Louis University
          </p>
        </div>
      </footer>
    </div>
  );
}
