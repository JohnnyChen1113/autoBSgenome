"use client";

import { useState, useRef, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  extractAccession,
  fetchAssemblyInfo,
  fetchCircularSequences,
} from "@/lib/ncbi";
import {
  extractEnsemblSpecies,
  fetchEnsemblAssemblyInfo,
  detectCircularFromKaryotype,
} from "@/lib/ensembl";

const WORKER_API = "https://autobsgenome-api.dailylifecjh.workers.dev";

type BatchStatus = "pending" | "fetching" | "ready" | "ambiguous" | "error" | "building" | "done" | "failed";
type Source = "ncbi" | "ensembl";

interface BatchItem {
  id: string;
  rawInput: string;
  detectedType: "ncbi" | "ensembl" | "ambiguous" | "invalid";
  selectedSource: Source;
  status: BatchStatus;
  accession: string;
  organism: string;
  commonName: string;
  assembly: string;
  provider: string;
  packageName: string;
  version: string;
  circSeqs: string;
  title: string;
  description: string;
  sourceUrl: string;
  fastaSource: string;
  error: string;
  jobId: string;
  downloadUrl: string;
  publishChecked: boolean;
  buildTime: number;
}

function detectInputType(input: string): { type: "ncbi" | "ensembl" | "ambiguous" | "invalid"; accession: string } {
  const trimmed = input.trim();
  if (!trimmed) return { type: "invalid", accession: "" };

  // NCBI URL
  if (trimmed.includes("ncbi.nlm.nih.gov")) {
    const acc = extractAccession(trimmed);
    if (acc) return { type: acc.startsWith("GCF_") ? "ncbi" : "ambiguous", accession: acc };
  }

  // Ensembl URL (any sister site)
  if (trimmed.includes("ensembl.org")) {
    const species = extractEnsemblSpecies(trimmed);
    if (species) return { type: "ensembl", accession: species };
  }

  // GCF_ is always NCBI RefSeq
  if (/^GCF_\d{9}\.\d+$/.test(trimmed)) {
    return { type: "ncbi", accession: trimmed };
  }

  // GCA_ could be NCBI GenBank or Ensembl
  const gcaMatch = trimmed.match(/(GCA_\d{9}\.\d+)/);
  if (gcaMatch) {
    return { type: "ambiguous", accession: gcaMatch[1] };
  }

  // GCF/GCA embedded in text
  const accMatch = extractAccession(trimmed);
  if (accMatch) {
    return { type: accMatch.startsWith("GCF_") ? "ncbi" : "ambiguous", accession: accMatch };
  }

  // Ensembl species name (lowercase_lowercase)
  const ensemblSpecies = extractEnsemblSpecies(trimmed);
  if (ensemblSpecies) {
    return { type: "ensembl", accession: ensemblSpecies };
  }

  return { type: "invalid", accession: trimmed };
}

function createBatchItem(rawInput: string, index: number): BatchItem {
  const { type, accession } = detectInputType(rawInput);
  return {
    id: `batch-${index}`,
    rawInput,
    detectedType: type,
    selectedSource: type === "ensembl" ? "ensembl" : "ncbi",
    status: type === "invalid" ? "error" : "pending",
    accession,
    organism: "",
    commonName: "",
    assembly: "",
    provider: "",
    packageName: "",
    version: "1.0.0",
    circSeqs: "",
    title: "",
    description: "",
    sourceUrl: "",
    fastaSource: "ncbi",
    error: type === "invalid" ? "Could not detect a valid accession or species name" : "",
    jobId: "",
    downloadUrl: "",
    publishChecked: false,
    buildTime: 0,
  };
}

export default function BatchMode({ onExit }: { onExit: () => void }) {
  const [items, setItems] = useState<BatchItem[]>([]);
  const [textInput, setTextInput] = useState("");
  const [phase, setPhase] = useState<"input" | "review" | "building" | "results">("input");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [fetchingAll, setFetchingAll] = useState(false);
  const pollIntervals = useRef<Record<string, ReturnType<typeof setInterval>>>({});

  // Parse textarea into batch items
  const parseInput = () => {
    const lines = textInput.split("\n").map(l => l.trim()).filter(l => l.length > 0);
    // Deduplicate
    const unique = [...new Set(lines)];
    const newItems = unique.map((line, i) => createBatchItem(line, i));
    setItems(newItems);
    if (newItems.length > 0) setPhase("review");
  };

  // Update a single item
  const updateItem = useCallback((id: string, updates: Partial<BatchItem>) => {
    setItems(prev => prev.map(item => item.id === id ? { ...item, ...updates } : item));
  }, []);

  // Fetch metadata for a single item
  const fetchItem = async (item: BatchItem): Promise<Partial<BatchItem>> => {
    const source = item.selectedSource;
    try {
      if (source === "ensembl") {
        // Ensembl path
        let species = item.accession;
        // If GCA_ accession, need to get species name from NCBI first then use Ensembl
        if (species.startsWith("GCA_")) {
          const ncbiInfo = await fetchAssemblyInfo(species);
          const parts = ncbiInfo.organism.trim().split(/\s+/);
          species = parts.length >= 2 ? `${parts[0]}_${parts[1]}`.toLowerCase() : parts[0].toLowerCase();
        }

        const info = await fetchEnsemblAssemblyInfo(species);
        const circNames = detectCircularFromKaryotype(info.karyotype);
        const orgParts = info.organism.trim().split(/\s+/);
        const abbrev = orgParts.length >= 2 ? orgParts[0][0].toUpperCase() + orgParts[1].toLowerCase() : orgParts[0];
        const assembly = info.assemblyName.replace(/\./g, "").replace(/[^a-zA-Z0-9]/g, "");

        return {
          status: "ready",
          organism: info.organism,
          commonName: info.commonName,
          assembly: info.assemblyName,
          provider: "Ensembl",
          packageName: `BSgenome.${abbrev}.Ensembl.${assembly}`,
          circSeqs: circNames.length > 0 ? circNames.join(", ") : "character(0)",
          title: `Full genome sequences for ${info.organism} (Ensembl version ${info.assemblyName})`,
          description: `Full genome sequences for ${info.organism} (${info.commonName}) as provided by Ensembl (${info.assemblyName}) and stored in Biostrings objects.`,
          sourceUrl: `https://www.ensembl.org/${species.charAt(0).toUpperCase() + species.slice(1)}/Info/Index`,
          fastaSource: "ncbi",
        };
      } else {
        // NCBI path
        const info = await fetchAssemblyInfo(item.accession);
        const circs = await fetchCircularSequences(item.accession);
        const orgParts = info.organism.trim().split(/\s+/);
        const abbrev = orgParts.length >= 2 ? orgParts[0][0].toUpperCase() + orgParts[1].toLowerCase() : orgParts[0];
        const assembly = info.assemblyName.replace(/\./g, "").replace(/[^a-zA-Z0-9]/g, "");

        return {
          status: "ready",
          organism: info.organism,
          commonName: info.commonName,
          assembly: info.assemblyName,
          provider: info.provider || "NCBI",
          packageName: `BSgenome.${abbrev}.${info.provider || "NCBI"}.${assembly}`,
          circSeqs: circs.length > 0 ? circs.map(c => c.name).join(", ") : "character(0)",
          title: `Full genome sequences for ${info.organism} (${info.provider} version ${info.assemblyName})`,
          description: `Full genome sequences for ${info.organism} (${info.commonName}) as provided by ${info.provider} (${info.assemblyName}) and stored in Biostrings objects.`,
          sourceUrl: `https://www.ncbi.nlm.nih.gov/datasets/genome/${item.accession}/`,
          fastaSource: "ncbi",
        };
      }
    } catch (e) {
      return {
        status: "error",
        error: e instanceof Error ? e.message : "Failed to fetch metadata",
      };
    }
  };

  // Fetch all items
  const fetchAll = async () => {
    setFetchingAll(true);
    const fetchable = items.filter(i => i.status !== "error" && i.status !== "ready");

    for (const item of fetchable) {
      updateItem(item.id, { status: "fetching" });
      const result = await fetchItem(item);
      updateItem(item.id, result);
      // Rate limit
      await new Promise(r => setTimeout(r, 300));
    }
    setFetchingAll(false);
  };

  // Build a single item
  const buildItem = async (item: BatchItem) => {
    updateItem(item.id, { status: "building" });
    try {
      const res = await fetch(`${WORKER_API}/api/build`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          package_name: item.packageName,
          organism: item.organism,
          common_name: item.commonName,
          genome: item.assembly,
          provider: item.provider,
          release_date: "",
          version: item.version,
          circ_seqs: item.circSeqs,
          title: item.title,
          description: item.description,
          source_url: item.sourceUrl,
          accession: item.accession,
          fasta_source: item.fastaSource,
          data_source: item.selectedSource,
        }),
      });

      const data = await res.json() as { job_id?: string; error?: string };
      if (!res.ok || !data.job_id) {
        throw new Error(data.error ?? "Failed to start build");
      }

      updateItem(item.id, { jobId: data.job_id });
      startPolling(item.id, data.job_id);
    } catch (e) {
      updateItem(item.id, {
        status: "failed",
        error: e instanceof Error ? e.message : "Build request failed",
      });
    }
  };

  // Poll build status
  const startPolling = (itemId: string, jobId: string) => {
    const startTime = Date.now();
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${WORKER_API}/api/status/${jobId}`);
        const data = await res.json() as { status: string; download_url?: string; file_name?: string; error?: string };

        if (data.status === "completed" && data.download_url) {
          clearInterval(interval);
          delete pollIntervals.current[itemId];
          updateItem(itemId, {
            status: "done",
            downloadUrl: data.download_url,
            buildTime: Math.floor((Date.now() - startTime) / 1000),
          });
        } else if (data.status === "failed" || data.status === "error") {
          clearInterval(interval);
          delete pollIntervals.current[itemId];
          updateItem(itemId, {
            status: "failed",
            error: data.error || "Build failed",
          });
        }
      } catch {
        // Network error, keep polling
      }
    }, 15000);
    pollIntervals.current[itemId] = interval;
  };

  // Build all valid items
  const buildAll = async () => {
    setPhase("building");
    const ready = items.filter(i => i.status === "ready");
    for (const item of ready) {
      await buildItem(item);
      // 10s delay between dispatches
      await new Promise(r => setTimeout(r, 10000));
    }
  };

  // Publish selected
  const publishSelected = async () => {
    const toPublish = items.filter(i => i.status === "done" && i.publishChecked);
    for (const item of toPublish) {
      try {
        await fetch(`${WORKER_API}/api/publish`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            package_name: item.packageName,
            organism: item.organism,
            accession: item.accession,
          }),
        });
      } catch {}
    }
  };

  // Counts
  const readyCount = items.filter(i => i.status === "ready").length;
  const errorCount = items.filter(i => i.status === "error").length;
  const buildingCount = items.filter(i => i.status === "building").length;
  const doneCount = items.filter(i => i.status === "done").length;
  const totalValid = items.filter(i => i.status !== "error" && i.detectedType !== "invalid").length;

  // ── Render ──

  if (phase === "input") {
    return (
      <Card className="w-full">
        <CardContent className="pt-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-lg font-semibold">Batch Build</h3>
              <p className="text-sm text-muted-foreground">Enter one accession or species per line. Supports NCBI (GCF_/GCA_), Ensembl species names, and URLs.</p>
            </div>
            <Button variant="outline" size="sm" onClick={onExit}>Single Mode</Button>
          </div>
          <textarea
            className="w-full min-h-[160px] p-3 border rounded-lg font-mono text-sm resize-y focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
            placeholder={"GCF_000001215.4\nGCA_000002035.4\ndanio_rerio\nhttps://www.ncbi.nlm.nih.gov/datasets/genome/GCF_000001405.40/"}
            value={textInput}
            onChange={(e) => setTextInput(e.target.value)}
          />
          <div className="flex items-center justify-between mt-3">
            <span className="text-sm text-muted-foreground">
              {textInput.split("\n").filter(l => l.trim()).length} accession(s) detected
            </span>
            <Button onClick={parseInput} disabled={!textInput.trim()}>
              Continue
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="w-full">
      <CardContent className="pt-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-lg font-semibold">
              {phase === "review" && "Review & Build"}
              {phase === "building" && "Building..."}
              {phase === "results" && "Results"}
            </h3>
            <p className="text-sm text-muted-foreground">
              {readyCount} ready · {errorCount > 0 ? `${errorCount} errors · ` : ""}{buildingCount > 0 ? `${buildingCount} building · ` : ""}{doneCount > 0 ? `${doneCount} done` : ""}
            </p>
          </div>
          <div className="flex gap-2">
            {phase === "review" && (
              <>
                <Button variant="outline" size="sm" onClick={() => { setPhase("input"); }}>← Back</Button>
                <Button size="sm" onClick={fetchAll} disabled={fetchingAll}>
                  {fetchingAll ? "Fetching..." : "Fetch All"}
                </Button>
                <Button size="sm" onClick={buildAll} disabled={readyCount === 0}>
                  Build All ({readyCount})
                </Button>
              </>
            )}
            {phase === "building" && doneCount + errorCount >= totalValid && (
              <Button size="sm" onClick={() => setPhase("results")}>View Results</Button>
            )}
          </div>
        </div>

        {/* Progress bar */}
        {(phase === "building" || phase === "results") && (
          <div className="mb-4">
            <div className="flex justify-between text-xs text-muted-foreground mb-1">
              <span>{doneCount}/{totalValid} complete</span>
              {buildingCount > 0 && <span>{buildingCount} building...</span>}
            </div>
            <div className="w-full h-2 bg-muted rounded-full overflow-hidden">
              <div
                className="h-full bg-primary rounded-full transition-all duration-500"
                style={{ width: `${totalValid > 0 ? (doneCount / totalValid) * 100 : 0}%` }}
              />
            </div>
          </div>
        )}

        {/* Item list */}
        <div className="space-y-2">
          {items.map(item => (
            <div key={item.id} className="border rounded-lg overflow-hidden">
              {/* Collapsed header */}
              <div
                className="flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-muted/50"
                onClick={() => setExpandedId(expandedId === item.id ? null : item.id)}
              >
                <div className="flex items-center gap-3 min-w-0">
                  {/* Status icon */}
                  <span className="flex-shrink-0">
                    {item.status === "pending" && "⏸"}
                    {item.status === "fetching" && <span className="animate-spin inline-block">⟳</span>}
                    {item.status === "ready" && "✅"}
                    {item.status === "ambiguous" && "⚠️"}
                    {item.status === "error" && "❌"}
                    {item.status === "building" && <span className="animate-spin inline-block">⟳</span>}
                    {item.status === "done" && "✅"}
                    {item.status === "failed" && "❌"}
                  </span>
                  <div className="min-w-0">
                    <div className="font-medium text-sm truncate">
                      {item.organism || item.rawInput}
                    </div>
                    {item.organism && (
                      <div className="text-xs text-muted-foreground font-mono">{item.accession}</div>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  {item.commonName && <span className="text-xs text-muted-foreground hidden sm:inline">{item.commonName}</span>}
                  <Badge variant={item.selectedSource === "ensembl" ? "secondary" : "default"} className="text-[10px]">
                    {item.selectedSource === "ensembl" ? "Ensembl" : "NCBI"}
                  </Badge>
                  {item.status === "done" && item.downloadUrl && (
                    <a
                      href={item.downloadUrl}
                      className="text-xs bg-primary text-primary-foreground px-2 py-1 rounded"
                      onClick={(e) => e.stopPropagation()}
                    >
                      Download
                    </a>
                  )}
                  {item.status === "building" && (
                    <span className="text-xs text-muted-foreground">Building...</span>
                  )}
                  <svg
                    className={`w-4 h-4 text-muted-foreground transition-transform ${expandedId === item.id ? "rotate-180" : ""}`}
                    viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
                  >
                    <polyline points="6 9 12 15 18 9" />
                  </svg>
                </div>
              </div>

              {/* Expanded details */}
              {expandedId === item.id && (
                <div className="border-t px-4 py-3 bg-muted/30 space-y-3">
                  {/* Error message */}
                  {item.error && (
                    <p className="text-sm text-destructive">{item.error}</p>
                  )}

                  {/* Source selector for ambiguous GCA_ */}
                  {item.detectedType === "ambiguous" && (item.status === "pending" || item.status === "ambiguous") && (
                    <div>
                      <Label className="text-xs font-medium">Build from:</Label>
                      <div className="flex gap-4 mt-1">
                        {(["ncbi", "ensembl"] as Source[]).map(src => (
                          <label key={src} className="flex items-center gap-2 text-sm cursor-pointer">
                            <input
                              type="radio"
                              name={`source-${item.id}`}
                              checked={item.selectedSource === src}
                              onChange={() => updateItem(item.id, { selectedSource: src, status: "pending" })}
                            />
                            {src === "ncbi" ? "NCBI" : "Ensembl"}
                          </label>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Metadata fields (when ready) */}
                  {(item.status === "ready" || item.status === "done" || item.status === "building") && (
                    <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
                      <div><span className="text-muted-foreground">Package:</span> <span className="font-mono text-xs">{item.packageName}</span></div>
                      <div><span className="text-muted-foreground">Assembly:</span> {item.assembly}</div>
                      <div><span className="text-muted-foreground">Organism:</span> <em>{item.organism}</em></div>
                      <div><span className="text-muted-foreground">Provider:</span> {item.provider}</div>
                      <div><span className="text-muted-foreground">Circular:</span> {item.circSeqs || "none"}</div>
                      <div><span className="text-muted-foreground">Version:</span> {item.version}</div>
                    </div>
                  )}

                  {/* Done: install command + publish checkbox */}
                  {item.status === "done" && (
                    <div className="space-y-2 pt-2 border-t">
                      <div className="bg-background rounded p-2 flex items-center justify-between gap-2">
                        <code className="font-mono text-xs truncate">
                          install.packages(&quot;{item.packageName}&quot;, repos=&quot;https://johnnychen1113.github.io/autoBSgenome&quot;)
                        </code>
                        <Button
                          variant="outline"
                          size="sm"
                          className="text-xs flex-shrink-0"
                          onClick={(e) => {
                            e.stopPropagation();
                            navigator.clipboard.writeText(
                              `install.packages("${item.packageName}", repos="https://johnnychen1113.github.io/autoBSgenome")`
                            );
                          }}
                        >
                          Copy
                        </Button>
                      </div>
                      <label className="flex items-center gap-2 text-sm cursor-pointer">
                        <input
                          type="checkbox"
                          checked={item.publishChecked}
                          onChange={(e) => {
                            e.stopPropagation();
                            updateItem(item.id, { publishChecked: !item.publishChecked });
                          }}
                        />
                        Publish to community repository
                      </label>
                      {item.buildTime > 0 && (
                        <p className="text-xs text-muted-foreground">Built in {item.buildTime}s</p>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Bottom actions */}
        {phase === "results" && (
          <div className="flex justify-between items-center mt-4 pt-4 border-t">
            <Button variant="outline" onClick={onExit}>Start New Batch</Button>
            <Button
              onClick={publishSelected}
              disabled={items.filter(i => i.publishChecked).length === 0}
            >
              Publish Selected ({items.filter(i => i.publishChecked).length})
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
