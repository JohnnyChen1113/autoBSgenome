"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import confetti from "canvas-confetti";
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
import {
  completeUploadSession,
  createUploadSession,
  deleteBuild,
  fetchBuildStatus,
  fetchQueueStatus,
  startBuild,
  uploadPart,
  type BuildProgressStep,
  type BuildStatusResponse,
  type UploadPartResult,
} from "@/lib/autobsgenome-api";
import {
  buildBSgenomePackageName,
  cleanOrganismName,
  validateBSgenomePackageName,
} from "@/lib/package-name";
import { siteConfig } from "@/config";
import BatchMode from "@/features/build/BatchMode";
import { SiteFooter, SiteHeader } from "@/components/SiteChrome";

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
  fastaSource: "ncbi" | "url" | "upload";
  fastaUrl: string;
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
  fastaUrl: "",
};

type Step = "input" | "review" | "building" | "failed" | "result";

interface BuildRecord {
  jobId: string;
  packageName: string;
  organism: string;
  downloadUrl: string;
  deleteToken?: string;
  deleted?: boolean;
  buildTime: number;
  timestamp: number;
}

const MAX_FASTA_UPLOAD_BYTES = 4 * 1024 * 1024 * 1024;
const FASTA_PREVIEW_BYTES = 1024 * 1024;
const FASTA_FILE_RE = /\.(fa|fasta|fna|fas)(\.gz)?$/i;
const PROTEIN_FASTA_FILE_RE = /\.(faa|pep|aa)(\.gz)?$/i;
const NUCLEOTIDE_CHARS = new Set("ACGTUNRYSWKMBDHVacgtunryswkmbdhv.-");
const PROTEIN_ONLY_CHARS = new Set("EFILPQZJXO*efilpqzjxo*");

function formatBytes(bytes: number) {
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  let size = bytes;
  let unit = 0;
  while (size >= 1024 && unit < units.length - 1) {
    size /= 1024;
    unit += 1;
  }
  return `${size.toFixed(unit === 0 ? 0 : 1)} ${units[unit]}`;
}

function formatDuration(seconds?: number) {
  if (seconds === undefined || !Number.isFinite(seconds) || seconds < 0) return "";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const minutes = Math.floor(seconds / 60);
  const rest = Math.round(seconds % 60);
  return rest === 0 ? `${minutes}m` : `${minutes}m ${String(rest).padStart(2, "0")}s`;
}

function normalizeSubmittedAccession(input: string, source: DataSource) {
  const trimmed = input.trim();
  return source === "ncbi" ? extractAccession(trimmed) ?? trimmed : trimmed;
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
  } catch (error) {
    console.warn("Failed to save build history", error);
  }
}

function loadBuildHistory(): BuildRecord[] {
  try {
    return JSON.parse(localStorage.getItem("autobsgenome_history") ?? "[]");
  } catch {
    return [];
  }
}

function replaceBuildHistory(history: BuildRecord[]) {
  localStorage.setItem("autobsgenome_history", JSON.stringify(history.slice(0, 20)));
}

async function readFastaPreview(file: File): Promise<string> {
  const lowerName = file.name.toLowerCase();
  if (!lowerName.endsWith(".gz")) {
    const buffer = await file.slice(0, FASTA_PREVIEW_BYTES).arrayBuffer();
    return new TextDecoder("utf-8", { fatal: false }).decode(buffer);
  }

  if (typeof DecompressionStream === "undefined") {
    throw new Error("This browser cannot pre-check gzip FASTA files. Use an uncompressed FASTA or a current Chrome/Edge/Safari/Firefox release.");
  }

  const reader = file.stream().pipeThrough(new DecompressionStream("gzip")).getReader();
  const chunks: Uint8Array[] = [];
  let total = 0;
  try {
    while (total < FASTA_PREVIEW_BYTES) {
      const { done, value } = await reader.read();
      if (done) break;
      chunks.push(value);
      total += value.byteLength;
    }
  } finally {
    await reader.cancel().catch(() => undefined);
  }

  const merged = new Uint8Array(Math.min(total, FASTA_PREVIEW_BYTES));
  let offset = 0;
  for (const chunk of chunks) {
    const slice = chunk.subarray(0, Math.min(chunk.byteLength, merged.byteLength - offset));
    merged.set(slice, offset);
    offset += slice.byteLength;
    if (offset >= merged.byteLength) break;
  }
  return new TextDecoder("utf-8", { fatal: false }).decode(merged);
}

function validateNucleotideFastaPreview(text: string) {
  const normalized = text.replace(/^\uFEFF/, "");
  const first = normalized.trimStart()[0];
  if (!first) {
    throw new Error("The selected file appears to be empty after decompression.");
  }
  if (first === "@") {
    throw new Error("This looks like FASTQ, not FASTA. Upload a nucleotide FASTA file.");
  }
  if (first !== ">") {
    throw new Error("FASTA files must start with a > header line.");
  }

  let headerCount = 0;
  let sequenceChars = 0;
  const invalidChars = new Set<string>();
  const proteinChars = new Set<string>();

  for (const rawLine of normalized.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line) continue;
    if (line.startsWith(">")) {
      headerCount += 1;
      continue;
    }
    if (headerCount === 0) {
      throw new Error("Sequence data appears before the first FASTA header.");
    }

    for (const char of line.replace(/\s+/g, "")) {
      if (!NUCLEOTIDE_CHARS.has(char)) {
        invalidChars.add(char);
      }
      if (PROTEIN_ONLY_CHARS.has(char)) {
        proteinChars.add(char);
      }
      sequenceChars += 1;
    }
  }

  if (headerCount === 0 || sequenceChars === 0) {
    throw new Error("No FASTA sequence data was found in the selected file.");
  }
  if (invalidChars.size > 0) {
    const chars = [...invalidChars].slice(0, 12).join(" ");
    if (proteinChars.size > 0) {
      throw new Error(`This looks like a protein FASTA, not a nucleotide FASTA. Invalid nucleotide characters: ${chars}`);
    }
    throw new Error(`Invalid nucleotide FASTA characters detected: ${chars}`);
  }
}

export default function Home() {
  const [step, setStep] = useState<Step>("input");
  const [batchMode, setBatchMode] = useState(false);
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
    const errors = validateBSgenomePackageName(name);

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
        const organism = cleanOrganismName(ensInfo.organism);
        const packageName = buildBSgenomePackageName(
          organism,
          "Ensembl",
          ensInfo.assemblyName
        );
        if (!packageName.name) {
          throw new Error(`Could not generate a valid package name: ${packageName.reason}`);
        }

        newForm = {
          packageName: packageName.name,
          organism,
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
          fastaUrl: "",
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
          fastaUrl: "",
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
  const [deleteToken, setDeleteToken] = useState("");
  const [deleteError, setDeleteError] = useState("");
  const [deletingBuild, setDeletingBuild] = useState(false);
  const [deletingHistoryJobId, setDeletingHistoryJobId] = useState("");
  const [buildDeleted, setBuildDeleted] = useState(false);
  const [downloadUrl, setDownloadUrl] = useState("");
  const [fileName, setFileName] = useState("");
  const [fileSize, setFileSize] = useState(0);
  const [buildStep, setBuildStep] = useState(0);
  const [buildStartTime, setBuildStartTime] = useState(0);
  const [buildProgressSteps, setBuildProgressSteps] = useState<BuildProgressStep[]>([]);
  const [workflowRunUrl, setWorkflowRunUrl] = useState("");
  const [resumingJob, setResumingJob] = useState(false);
  const [queueInfo, setQueueInfo] = useState<{
    running: number;
    queued: number;
    runs: { id: number; status: string; name: string; created_at: string }[];
  } | null>(null);
  const [buildElapsed, setBuildElapsed] = useState(0);
  const [buildTotalTime, setBuildTotalTime] = useState(0);
  const [uploadedFasta, setUploadedFasta] = useState<File | null>(null);
  const [uploadError, setUploadError] = useState("");
  const [uploadState, setUploadState] = useState<"idle" | "validating" | "uploading" | "uploaded">("idle");
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadStepSeconds, setUploadStepSeconds] = useState(0);
  const [isDragActive, setIsDragActive] = useState(false);

  const buildStartTimeRef = useRef(0);
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const formRef = useRef(form);
  const fileInputRef = useRef<HTMLInputElement>(null);
  formRef.current = form;

  useEffect(() => {
    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
    };
  }, []);

  const selectFastaFile = useCallback(async (file?: File) => {
    setUploadError("");
    setUploadState("idle");
    setUploadProgress(0);

    if (!file) return;
    setUploadedFasta(file);
    if (PROTEIN_FASTA_FILE_RE.test(file.name)) {
      setUploadedFasta(null);
      setUploadError("Protein FASTA files are not supported. Choose a nucleotide genome FASTA file.");
      return;
    }
    if (!FASTA_FILE_RE.test(file.name)) {
      setUploadedFasta(null);
      setUploadError("Choose a FASTA file ending in .fa, .fasta, .fna, .fas, optionally .gz.");
      return;
    }
    if (file.size <= 0) {
      setUploadedFasta(null);
      setUploadError("The selected FASTA file is empty.");
      return;
    }
    if (file.size > MAX_FASTA_UPLOAD_BYTES) {
      setUploadedFasta(null);
      setUploadError(`The selected FASTA is too large. Maximum upload size is ${formatBytes(MAX_FASTA_UPLOAD_BYTES)}.`);
      return;
    }

    setUploadState("validating");
    try {
      const preview = await readFastaPreview(file);
      validateNucleotideFastaPreview(preview);
      setUploadState("idle");
    } catch (e) {
      setUploadedFasta(null);
      setUploadState("idle");
      setUploadError(e instanceof Error ? e.message : "Failed to pre-check FASTA file.");
    }
  }, []);

  // Restore build state or pre-fill accession from URL on page load
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const resumeJob = params.get("job");
    if (resumeJob) {
      setJobId(resumeJob);
      setDeleteToken("");
      setBuildDeleted(false);
      setBuildError("");
      setDeleteError("");
      setBuildProgressSteps([]);
      setWorkflowRunUrl("");
      setDownloadUrl("");
      setFileName("");
      setFileSize(0);
      setBuildElapsed(0);
      setBuildTotalTime(0);
      setResumingJob(true);
      const now = Date.now();
      setBuildStartTime(now);
      buildStartTimeRef.current = now;
      setStep("building");
      return pollBuildStatus(resumeJob, "", { resumed: true });
    }
    // Batch mode from URL
    if (params.get("batch") === "true") {
      setBatchMode(true);
      return;
    }
    // Pre-fill accession from URL and auto-fetch metadata
    // e.g., ?accession=GCF_000001215.4 or ?accession=danio_rerio&source=ensembl
    const prefillAccession = params.get("accession");
    const prefillSource = params.get("source");
    if (prefillAccession) {
      if (prefillSource === "ensembl") {
        setDataSource("ensembl");
      }
      setAccessionInput(prefillAccession);
      // Auto-trigger fetch after a short delay for React to commit state.
      // We click the Fetch button directly to avoid stale closure issues.
      setTimeout(() => {
        const fetchBtn = document.querySelector<HTMLButtonElement>("[data-auto-fetch]");
        if (fetchBtn) fetchBtn.click();
      }, 300);
    }
  }, []);

  // Fetch queue status on input and review steps
  useEffect(() => {
    if (step !== "input" && step !== "review") return;
    fetchQueueStatus()
      .then((data) => setQueueInfo(data))
      .catch(() => setQueueInfo(null));
  }, [step]);

  const [notifyEnabled, setNotifyEnabled] = useState(false);

  function playChime() {
    try {
      const ctx = new AudioContext();
      const notes = [523.25, 659.25, 783.99]; // C5, E5, G5 major chord
      notes.forEach((freq, i) => {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = "sine";
        osc.frequency.value = freq;
        gain.gain.setValueAtTime(0.15, ctx.currentTime + i * 0.15);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + i * 0.15 + 0.8);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start(ctx.currentTime + i * 0.15);
        osc.stop(ctx.currentTime + i * 0.15 + 0.8);
      });
    } catch (error) {
      console.warn("Failed to play notification chime", error);
    }
  }

  // Celebration confetti + sound on build success
  useEffect(() => {
    if (step !== "result") return;
    if (notifyEnabled) playChime();
    const duration = 2000;
    const end = Date.now() + duration;
    const frame = () => {
      confetti({
        particleCount: 3,
        angle: 60,
        spread: 55,
        origin: { x: 0, y: 0.6 },
        colors: ["#003DA5", "#4a7ec7", "#0f7b3f", "#f0f4fa"],
      });
      confetti({
        particleCount: 3,
        angle: 120,
        spread: 55,
        origin: { x: 1, y: 0.6 },
        colors: ["#003DA5", "#4a7ec7", "#0f7b3f", "#f0f4fa"],
      });
      if (Date.now() < end) requestAnimationFrame(frame);
    };
    frame();
  }, [step]);

  // 1-second timer for display (independent of 5s poll)
  useEffect(() => {
    if (step !== "building" || buildStartTime === 0) return;
    const tick = setInterval(() => {
      setBuildElapsed(Math.floor((Date.now() - buildStartTime) / 1000));
    }, 1000);
    return () => clearInterval(tick);
  }, [step, buildStartTime]);

  const uploadFastaFile = async (file: File) => {
    setUploadState("uploading");
    setUploadProgress(0);
    const startedAt = Date.now();
    const session = await createUploadSession({
      file_name: file.name,
      file_size: file.size,
      content_type: file.type || "application/octet-stream",
    });

    const partSize = session.part_size || 64 * 1024 * 1024;
    const totalParts = Math.ceil(file.size / partSize);
    const parts: UploadPartResult[] = [];

    for (let index = 0; index < totalParts; index += 1) {
      const partNumber = index + 1;
      const start = index * partSize;
      const end = Math.min(file.size, start + partSize);
      const partUrl = session.part_url_template.replace("{part_number}", String(partNumber));
      const part = await uploadPart(partUrl, file.slice(start, end));
      parts.push({ part_number: partNumber, etag: part.etag });
      setUploadProgress(Math.round((partNumber / totalParts) * 100));
    }

    await completeUploadSession(session.complete_url, parts);

    setUploadState("uploaded");
    setUploadProgress(100);
    setUploadStepSeconds(Math.max(1, Math.round((Date.now() - startedAt) / 1000)));
    return session;
  };

  const handleBuild = async () => {
    setBuildError("");
    setResumingJob(false);
    setDeleteError("");
    setDeleteToken("");
    setBuildDeleted(false);
    setUploadError("");

    if (form.fastaSource === "url") {
      try {
        const parsed = new URL(form.fastaUrl.trim());
        if (parsed.protocol !== "https:" && parsed.protocol !== "http:") {
          setUploadError("FASTA URL must start with http:// or https://.");
          return;
        }
      } catch {
        setUploadError("Enter a valid FASTA download URL before starting the build.");
        return;
      }
    }

    if (form.fastaSource === "upload" && !uploadedFasta) {
      setUploadError("Choose a FASTA file before starting the build.");
      return;
    }

    setStep("building");
    setBuildStep(0);
    setBuildProgressSteps([]);
    setWorkflowRunUrl("");
    setUploadStepSeconds(0);
    const startTime = Date.now();
    setBuildStartTime(startTime);
    buildStartTimeRef.current = startTime;
    setBuildElapsed(0);
    setBuildTotalTime(0);

    try {
      let uploadPayload: Record<string, string> = {};
      const submittedAccession = normalizeSubmittedAccession(accessionInput, dataSource);

      if (form.fastaSource === "upload" && uploadedFasta) {
        const session = await uploadFastaFile(uploadedFasta);
        uploadPayload = {
          fasta_upload_url: session.download_url,
          fasta_file_name: session.file_name,
          fasta_file_size: String(uploadedFasta.size),
        };
      }

      const data = await startBuild({
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
        accession: submittedAccession,
        fasta_source: form.fastaSource,
        fasta_url: form.fastaUrl.trim(),
        data_source: dataSource,
        ...uploadPayload,
      });

      setJobId(data.job_id);
      setDeleteToken(data.delete_token ?? "");
      setBuildStep(1);
      if (data.queue_position && data.queue_position > 0) {
        setBuildError(`Your build is #${data.queue_position + 1} in queue. It will start automatically.`);
      }

      // Save jobId to URL so page refresh can resume polling
      window.history.replaceState(null, "", `?job=${data.job_id}`);

      // Poll for status
      pollBuildStatus(data.job_id, data.delete_token ?? "");
    } catch (e) {
      setBuildError(e instanceof Error ? e.message : "Build request failed");
      setUploadState("idle");
      setUploadProgress(0);
      setStep("review");
    }
  };

  const deleteTemporaryBuild = async (targetJobId: string, targetDeleteToken: string) => {
    await deleteBuild(targetJobId, targetDeleteToken);
  };

  const markHistoryDeleted = (targetJobId: string) => {
    const nextHistory = loadBuildHistory().map((record) =>
      record.jobId === targetJobId
        ? { ...record, downloadUrl: "", deleteToken: "", deleted: true }
        : record
    );
    replaceBuildHistory(nextHistory);
    setBuildHistory(nextHistory);
  };

  const handleDeleteBuild = async () => {
    if (!jobId || !deleteToken || deletingBuild) return;
    const confirmed = window.confirm(
      "Delete this temporary GitHub Release now? This removes the download link and cannot be undone."
    );
    if (!confirmed) return;

    setDeletingBuild(true);
    setDeleteError("");
    try {
      await deleteTemporaryBuild(jobId, deleteToken);
      setBuildDeleted(true);
      setDownloadUrl("");
      setDeleteToken("");
      markHistoryDeleted(jobId);
    } catch (e) {
      setDeleteError(e instanceof Error ? e.message : "Failed to delete temporary package");
    } finally {
      setDeletingBuild(false);
    }
  };

  const handleDeleteHistoryBuild = async (record: BuildRecord) => {
    if (!record.deleteToken || record.deleted || deletingHistoryJobId) return;
    const confirmed = window.confirm(
      `Delete the temporary GitHub Release for ${record.packageName}? This removes the download link and cannot be undone.`
    );
    if (!confirmed) return;

    setDeletingHistoryJobId(record.jobId);
    try {
      await deleteTemporaryBuild(record.jobId, record.deleteToken);
      markHistoryDeleted(record.jobId);
      if (record.jobId === jobId) {
        setBuildDeleted(true);
        setDownloadUrl("");
        setDeleteToken("");
      }
    } catch (e) {
      window.alert(e instanceof Error ? e.message : "Failed to delete temporary package");
    } finally {
      setDeletingHistoryJobId("");
    }
  };

  const applyBuildProgress = (data: BuildStatusResponse) => {
    if (data.build_steps && data.build_steps.length > 0) {
      setBuildProgressSteps(data.build_steps);
    }
    if (data.workflow_run_url) {
      setWorkflowRunUrl(data.workflow_run_url);
    }
  };

  const pollBuildStatus = (
    id: string,
    currentDeleteToken = "",
    options: { resumed?: boolean } = {}
  ) => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }

    let interval: ReturnType<typeof setInterval> | null = null;
    const stopPolling = () => {
      if (interval) {
        clearInterval(interval);
      }
      if (pollIntervalRef.current === interval) {
        pollIntervalRef.current = null;
      }
    };
    let errorCount = 0;
    const checkStatus = async () => {
      const elapsedSec = Math.floor((Date.now() - buildStartTimeRef.current) / 1000);

      // Animate build steps based on elapsed time
      if (!options.resumed && buildProgressSteps.length === 0) {
        if (elapsedSec > 5) setBuildStep(1);
        if (elapsedSec > 15) setBuildStep(2);
        if (elapsedSec > 30) setBuildStep(3);
      }

      try {
        const data = await fetchBuildStatus(id);
        applyBuildProgress(data);

        if (data.status === "complete") {
          stopPolling();
          setResumingJob(false);
          setBuildStep(4);
          const totalTime =
            data.total_seconds ??
            Math.floor((Date.now() - buildStartTimeRef.current) / 1000);
          setBuildTotalTime(totalTime);
          setDownloadUrl(data.download_url ?? "");
          setFileName(data.file_name ?? "");
          setFileSize(data.file_size ?? 0);
          const record: BuildRecord = {
            jobId: id,
            packageName: formRef.current.packageName,
            organism: formRef.current.organism,
            downloadUrl: data.download_url ?? "",
            deleteToken: currentDeleteToken,
            deleted: false,
            buildTime: totalTime,
            timestamp: Date.now(),
          };
          saveBuildRecord(record);
          setBuildHistory(loadBuildHistory());
          window.history.replaceState(null, "", window.location.pathname);
          setStep("result");
          return;
        } else if (data.status === "failed") {
          stopPolling();
          setResumingJob(false);
          setBuildError(data.message ?? "Build failed");
          setStep(options.resumed ? "failed" : "review");
          return;
        } else if (data.status === "error") {
          errorCount++;
          // After 6 consecutive errors (30s), show a helpful message but keep polling
          if (errorCount >= 6 && errorCount % 6 === 0) {
            setBuildError(
              `Status check temporarily unavailable (${data.message ?? "API error"}). ` +
              `Your build is likely still running. You can check GitHub Actions directly: ` +
              `${siteConfig.githubUrl}/actions`
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

      // Timeout slightly after the GitHub Actions workflow's 60-minute limit.
      if (elapsedSec > 3900) {
        stopPolling();
        setResumingJob(false);
        setBuildError(
          "Status polling timed out after 65 minutes. Your build may still be running — " +
          `check ${siteConfig.githubUrl}/releases for your package.`
        );
        setStep(options.resumed ? "failed" : "review");
      }
    };
    void checkStatus();
    interval = setInterval(() => void checkStatus(), 5000);
    pollIntervalRef.current = interval;
    return stopPolling;
  };

  const needsUploadedFasta = form.fastaSource === "upload" && !uploadedFasta;
  const needsFastaUrl = form.fastaSource === "url" && !form.fastaUrl.trim();
  const uploadBusy = uploadState === "validating" || uploadState === "uploading";
  const buildButtonDisabled =
    !form.packageName ||
    !form.organism ||
    packageValidation.status !== "valid" ||
    needsUploadedFasta ||
    needsFastaUrl ||
    uploadBusy;
  const buildButtonText =
    packageValidation.status !== "valid"
      ? "Validate Package Name First"
      : uploadState === "validating"
      ? "Checking FASTA File..."
      : uploadState === "uploading"
      ? `Uploading FASTA... ${uploadProgress}%`
      : needsFastaUrl
      ? "Enter a FASTA URL First"
      : needsUploadedFasta
      ? "Choose a FASTA File First"
      : "Build BSgenome Package";
  const buildStepLabels =
    form.fastaSource === "upload"
      ? [
          "Uploading FASTA",
          "Queuing build on GitHub Actions",
          "Converting to 2bit format",
          "Building R package",
          "Uploading package release",
        ]
      : form.fastaSource === "url"
      ? [
          "Queuing build on GitHub Actions",
          "Downloading FASTA URL",
          "Converting to 2bit format",
          "Building R package",
          "Uploading package release",
        ]
      : [
          "Queuing build on GitHub Actions",
          "Downloading FASTA",
          "Converting to 2bit format",
          "Building R package",
          "Uploading package release",
        ];
  const showFallbackBuildSteps = !resumingJob;
  const normalizedProgressSteps =
    buildProgressSteps.length > 0
      ? buildProgressSteps.map((progressStep) =>
          progressStep.key === "download" && form.fastaSource === "url"
            ? { ...progressStep, label: "Downloading FASTA URL" }
            : progressStep
        )
      : [];
  const visibleBuildSteps: BuildProgressStep[] =
    normalizedProgressSteps.length > 0
      ? [
          ...(form.fastaSource === "upload"
            ? [
                {
                  key: "upload",
                  label: "Uploading FASTA",
                  status: "complete" as const,
                  seconds: uploadStepSeconds || undefined,
                },
              ]
            : []),
          ...normalizedProgressSteps,
        ]
      : showFallbackBuildSteps
      ? buildStepLabels.map((label, index) => ({
          key: `fallback-${index}`,
          label,
          status:
            index < buildStep
              ? "complete"
              : index === buildStep
              ? "running"
              : "pending",
        }))
      : [];
  const submittedAccession = normalizeSubmittedAccession(accessionInput, dataSource);
  const failedProgressStep = buildProgressSteps.find((progressStep) => progressStep.status === "failed");

  return (
    <div className="flex flex-col flex-1 bg-background">
      <SiteHeader active="build" />

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
          <p className="mt-3">
            <a
              href="/packages"
              className="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground shadow-sm transition-colors hover:bg-primary/90"
            >
              Browse all available packages
              <span aria-hidden="true">&rarr;</span>
            </a>
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
          {/* ─── Batch Mode ─── */}
          {step === "input" && batchMode && (
            <BatchMode onExit={() => setBatchMode(false)} />
          )}

          {/* ─── Step 1: Input ─── */}
          {step === "input" && !batchMode && (
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle>Enter Genome Information</CardTitle>
                    <CardDescription>
                      Choose a data source and provide an accession or URL to auto-fill all metadata.
                    </CardDescription>
                  </div>
                  <Button variant="outline" size="sm" onClick={() => setBatchMode(true)}>
                    Batch Mode
                  </Button>
                </div>
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
                    <Button onClick={handleFetch} disabled={fetching} className="min-w-[90px]" data-auto-fetch>
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
                        onClick={() => setAccessionInput("GCA_000003195.3")}
                      >
                        GCA_000003195.3
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
                      href={`${siteConfig.githubUrl}/issues/new?${new URLSearchParams({
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
                          "| **Accession** | `" + submittedAccession + "` |",
                          "| **Original Input** | `" + accessionInput.trim() + "` |",
                          "| **Data Source** | " + dataSource + " |",
                          "| **Circular Seqs** | `" + form.circSeqs + "` |",
                          "| **Version** | " + form.version + " |",
                          "| **Job ID** | `" + (jobId || "N/A") + "` |",
                          "| **Failed Step** | " + (failedProgressStep?.label ?? "N/A") + " |",
                          "",
                          "## Error Message",
                          "```",
                          buildError,
                          "```",
                          "",
                          "## Debug Links",
                          `- [GitHub Actions Runs](${siteConfig.githubUrl}/actions/workflows/build-bsgenome.yml)`,
                          workflowRunUrl ? `- [This GitHub Actions Run](${workflowRunUrl})` : "",
                          jobId ? `- [GitHub Release (if created)](${siteConfig.githubUrl}/releases/tag/build-${jobId})` : "",
                          "",
                          "## Additional Context",
                          "_Please describe what you were trying to do and any additional context._",
                          "",
                          "---",
                          "_Auto-generated by [AutoBSgenome Web](https://autobsgenome.org)_",
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
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
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
                        form.fastaSource === "url"
                          ? "bg-accent border-primary text-primary"
                          : "bg-background border-border text-muted-foreground hover:bg-secondary"
                      }`}
                      onClick={() => updateField("fastaSource", "url")}
                    >
                      Use FASTA URL
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

                {/* FASTA URL area */}
                {form.fastaSource === "url" && (
                  <div className="space-y-2">
                    <Label htmlFor="fastaUrl">FASTA Download URL</Label>
                    <Input
                      id="fastaUrl"
                      className="font-mono text-xs"
                      placeholder="https://example.org/path/genome.fa.gz"
                      value={form.fastaUrl}
                      onChange={(e) => {
                        setUploadError("");
                        updateField("fastaUrl", e.target.value);
                      }}
                    />
                    {uploadError && (
                      <p className="text-sm text-destructive">{uploadError}</p>
                    )}
                    <p className="text-sm text-muted-foreground">
                      GitHub Actions downloads this URL directly. Signed URLs are accepted, but the finished package is still delivered through a temporary public GitHub Release. Do not use private or sensitive sequence data here.
                    </p>
                  </div>
                )}

                {/* Upload area (shown when "upload" selected) */}
                {form.fastaSource === "upload" && (
                  <div className="space-y-2">
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept=".fa,.fasta,.fna,.fas,.fa.gz,.fasta.gz,.fna.gz,.fas.gz"
                      className="hidden"
                      onChange={(e) => selectFastaFile(e.target.files?.[0])}
                    />
                    <div
                      role="button"
                      tabIndex={0}
                      className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
                        isDragActive
                          ? "border-primary bg-accent"
                          : "border-border hover:border-primary/40"
                      }`}
                      onClick={() => fileInputRef.current?.click()}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          fileInputRef.current?.click();
                        }
                      }}
                      onDragOver={(e) => {
                        e.preventDefault();
                        setIsDragActive(true);
                      }}
                      onDragLeave={() => setIsDragActive(false)}
                      onDrop={(e) => {
                        e.preventDefault();
                        setIsDragActive(false);
                        selectFastaFile(e.dataTransfer.files?.[0]);
                      }}
                    >
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
                      {uploadedFasta ? (
                        <>
                          <p className="text-sm font-medium text-foreground">
                            {uploadedFasta.name}
                          </p>
                          <p className="text-sm text-muted-foreground mt-1">
                            {formatBytes(uploadedFasta.size)}
                            {uploadState === "validating" ? " · checking FASTA" : ""}
                            {uploadState === "uploading" ? ` · uploading ${uploadProgress}%` : ""}
                            {uploadState === "uploaded" ? " · uploaded" : ""}
                          </p>
                          {uploadState === "uploading" && (
                            <div className="mt-3 h-2 w-full max-w-sm mx-auto rounded-full bg-secondary overflow-hidden">
                              <div
                                className="h-full bg-primary transition-all"
                                style={{ width: `${uploadProgress}%` }}
                              />
                            </div>
                          )}
                        </>
                      ) : (
                        <>
                          <p className="text-sm text-muted-foreground">
                            Drop FASTA file here or{" "}
                            <span className="text-primary underline">browse</span>
                          </p>
                          <p className="text-sm text-muted-foreground mt-1">
                            .fa, .fasta, .fna, .fas, or gzip-compressed FASTA
                          </p>
                        </>
                      )}
                    </div>
                    {uploadError && (
                      <p className="text-sm text-destructive">{uploadError}</p>
                    )}
                    <p className="text-sm text-muted-foreground">
                      Upload supports nucleotide FASTA files up to {formatBytes(MAX_FASTA_UPLOAD_BYTES)}. The browser pre-checks the file before upload, and the build validates the full FASTA again. The finished package is delivered through a temporary public GitHub Release.
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
                {/* Queue status */}
                {queueInfo && (queueInfo.running > 0 || queueInfo.queued > 0) && (
                  <div className="bg-accent border border-border rounded-md px-4 py-2.5 text-sm text-muted-foreground flex items-center gap-2">
                    <svg className="animate-spin h-4 w-4 text-primary" viewBox="0 0 24 24" fill="none">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"/>
                    </svg>
                    Build queue: {queueInfo.running} running, {queueInfo.queued} waiting
                  </div>
                )}

                <Button
                  size="lg"
                  className="w-full text-base cursor-pointer"
                  onClick={handleBuild}
                  disabled={buildButtonDisabled}
                >
                  {buildButtonText}
                </Button>
              </CardContent>
            </Card>
          )}

          {/* ─── Step 3: Building ─── */}
          {step === "building" && (
            <Card>
              <CardHeader>
                <CardTitle>
                  {resumingJob ? "Checking Existing Build Status..." : "Building Package..."}
                </CardTitle>
                <CardDescription>
                  {resumingJob
                    ? `Polling job ${jobId}. Refreshing this page does not start a new GitHub Actions run.`
                    : "Build time depends on FASTA size: small genomes usually finish in ~1 min; mammalian-size genomes take ~3–6 min; very large plant genomes can take 10–30+ min."}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6 py-8">
                {visibleBuildSteps.length > 0 ? (
                  <div className="space-y-4">
                    {visibleBuildSteps.map((progressStep, i) => {
                      const done =
                        progressStep.status === "complete" ||
                        progressStep.status === "skipped";
                      const active = progressStep.status === "running";
                      const failed = progressStep.status === "failed";
                      const duration = formatDuration(progressStep.seconds);
                      return (
                        <div key={progressStep.key} className="flex items-center gap-3">
                          <div
                            className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
                              failed
                                ? "bg-destructive text-destructive-foreground"
                                : done
                                ? "bg-primary text-primary-foreground"
                                : active
                                ? "bg-primary text-primary-foreground animate-pulse"
                                : "bg-secondary text-muted-foreground"
                            }`}
                          >
                            {failed ? "!" : done ? "✓" : i + 1}
                          </div>
                          <div className="min-w-0 flex-1 sm:flex sm:items-baseline sm:justify-between sm:gap-3">
                            <span
                              className={
                                failed
                                  ? "text-destructive font-medium"
                                  : done
                                  ? "text-foreground"
                                  : active
                                  ? "text-foreground font-medium"
                                  : "text-muted-foreground"
                              }
                            >
                              {progressStep.label}
                            </span>
                            {duration && (
                              <span className="block text-xs font-mono text-muted-foreground sm:text-right">
                                {active ? `running ${duration}` : duration}
                              </span>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="rounded-md border border-border bg-secondary/40 px-4 py-4 text-sm text-muted-foreground">
                    Checking GitHub Actions and release status for this existing job.
                  </div>
                )}
                <div className="text-center space-y-1">
                  {resumingJob ? (
                    <>
                      <p className="text-base font-medium text-foreground">
                        Existing build lookup
                      </p>
                      <p className="text-sm text-muted-foreground">
                        No new build request has been sent.
                      </p>
                    </>
                  ) : (
                    <>
                      <p className="text-2xl font-mono font-semibold text-foreground">
                        {Math.floor(buildElapsed / 60)}:{String(buildElapsed % 60).padStart(2, "0")}
                      </p>
                      <p className="text-sm text-muted-foreground">Elapsed time</p>
                    </>
                  )}
                  {jobId && (
                    <p className="text-sm text-muted-foreground">
                      Job ID: <code className="font-mono">{jobId}</code>
                    </p>
                  )}
                  {workflowRunUrl && (
                    <p className="text-sm">
                      <a
                        href={workflowRunUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-primary hover:underline"
                      >
                        View GitHub Actions run
                      </a>
                    </p>
                  )}
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setNotifyEnabled(!notifyEnabled);
                    if (!notifyEnabled) playChime(); // Preview the sound
                  }}
                  className={`flex items-center gap-2 mx-auto px-4 py-2 rounded-full text-sm font-medium transition-colors cursor-pointer ${
                    notifyEnabled
                      ? "bg-primary text-primary-foreground"
                      : "bg-secondary text-muted-foreground border border-border hover:bg-accent"
                  }`}
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/>
                  </svg>
                  {notifyEnabled ? "Sound notification on" : "Notify me when done"}
                </button>
                {buildError && step === "building" && (
                  <div className="bg-amber-50 border border-amber-200 rounded-md px-4 py-3 text-sm text-amber-800">
                    {buildError}
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* ─── Existing Job Failed ─── */}
          {step === "failed" && (
            <Card>
              <CardHeader className="text-center pb-2">
                <div className="mx-auto w-14 h-14 rounded-full bg-destructive text-destructive-foreground flex items-center justify-center text-2xl font-bold mb-3">
                  !
                </div>
                <CardTitle className="text-xl">Build Failed</CardTitle>
                <CardDescription>
                  This is the saved status for job <code className="font-mono">{jobId}</code>.
                  Refreshing this page did not start a new build.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-5">
                <div className="rounded-md border border-destructive/20 bg-destructive/10 px-4 py-3 text-sm text-destructive">
                  {buildError || "The BSgenome package build failed."}
                </div>

                {buildProgressSteps.length > 0 && (
                  <div className="border border-border rounded-lg p-4 space-y-3">
                    <h4 className="font-heading font-semibold text-foreground">Build step status</h4>
                    <div className="space-y-2">
                      {visibleBuildSteps.map((progressStep) => {
                        const duration = formatDuration(progressStep.seconds);
                        return (
                          <div
                            key={progressStep.key}
                            className="flex items-center justify-between gap-3 text-sm"
                          >
                            <span
                              className={
                                progressStep.status === "failed"
                                  ? "text-destructive font-medium"
                                  : "text-muted-foreground"
                              }
                            >
                              {progressStep.label}
                            </span>
                            <span className="font-mono text-foreground">
                              {duration || progressStep.status}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                <div className="flex flex-col gap-3 sm:flex-row sm:justify-center">
                  <a
                    href={workflowRunUrl || `${siteConfig.githubUrl}/actions/workflows/build-bsgenome.yml`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex h-10 items-center justify-center rounded-md border border-border px-4 text-sm font-medium text-foreground transition-colors hover:bg-muted"
                  >
                    View GitHub Actions
                  </a>
                  <Button
                    type="button"
                    onClick={() => {
                      window.history.replaceState(null, "", window.location.pathname);
                      setJobId("");
                      setBuildError("");
                      setBuildProgressSteps([]);
                      setWorkflowRunUrl("");
                      setStep("input");
                    }}
                  >
                    Build Another Package
                  </Button>
                </div>
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
                  {buildTotalTime > 0 && ` · Built in ${formatDuration(buildTotalTime)}`}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-5">
                {/* Build time highlight */}
                {buildTotalTime > 0 && (
                  <div className="text-center py-2">
                    <p className="text-4xl font-mono font-bold text-primary">
                      {formatDuration(buildTotalTime)}
                    </p>
                    <p className="text-sm text-muted-foreground mt-1">Total build time</p>
                    {workflowRunUrl && (
                      <a
                        href={workflowRunUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="mt-1 inline-block text-sm text-primary hover:underline"
                      >
                        View GitHub Actions run
                      </a>
                    )}
                  </div>
                )}

                {buildProgressSteps.length > 0 && (
                  <div className="border border-border rounded-lg p-4 space-y-3">
                    <h4 className="font-heading font-semibold text-foreground">Build step timings</h4>
                    <div className="space-y-2">
                      {visibleBuildSteps.map((progressStep) => {
                        const duration = formatDuration(progressStep.seconds);
                        return (
                          <div
                            key={progressStep.key}
                            className="flex items-center justify-between gap-3 text-sm"
                          >
                            <span className="text-muted-foreground">{progressStep.label}</span>
                            <span className="font-mono text-foreground">
                              {duration || progressStep.status}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                <div className="flex gap-3 justify-center">
                  {downloadUrl && !buildDeleted ? (
                    <a
                      href={downloadUrl}
                      download
                      className="inline-flex items-center justify-center rounded-md bg-primary h-11 px-8 text-base font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
                    >
                      Download .tar.gz
                    </a>
                  ) : (
                    <Button size="lg" disabled>Download .tar.gz</Button>
                  )}
                  <Button
                    variant="outline"
                    className="h-11 px-8 text-base"
                    disabled={!downloadUrl || buildDeleted}
                    onClick={() => {
                      if (!downloadUrl || buildDeleted) return;
                      const cmd = `install.packages("${downloadUrl}", repos = NULL, type = "source")`;
                      navigator.clipboard.writeText(cmd);
                    }}
                  >
                    Copy Install Command
                  </Button>
                </div>

                <Separator />

                {buildDeleted ? (
                  <div className="bg-[--success-foreground] border border-[--success]/20 rounded-md px-4 py-3 text-sm" style={{ color: "#0f7b3f" }}>
                    Temporary GitHub Release deleted. The package download link is no longer available.
                  </div>
                ) : (
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
                )}

                {!buildDeleted && (
                  <div className="space-y-3">
                    <div className="bg-accent border-l-[3px] border-primary rounded-r-md px-4 py-3 text-sm text-muted-foreground">
                      This package will remain available for{" "}
                      <strong className="text-foreground">2 days</strong> at{" "}
                      <a
                        href={`${siteConfig.githubUrl}/releases`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-primary hover:underline"
                      >
                        GitHub Releases
                      </a>
                      . Download a local copy for permanent use.
                    </div>
                    {deleteToken && (
                      <div className="border border-border rounded-lg p-4 space-y-3 text-sm">
                        <div>
                          <h4 className="font-heading font-semibold text-foreground">Remove temporary download</h4>
                          <p className="text-muted-foreground mt-1">
                            Delete this build&apos;s temporary GitHub Release now instead of waiting for cleanup.
                          </p>
                        </div>
                        {deleteError && (
                          <p className="text-sm text-destructive">{deleteError}</p>
                        )}
                        <Button
                          type="button"
                          variant="outline"
                          className="w-full border-destructive/40 text-destructive hover:bg-destructive/10"
                          disabled={deletingBuild}
                          onClick={handleDeleteBuild}
                        >
                          {deletingBuild ? "Deleting..." : "Delete temporary package"}
                        </Button>
                      </div>
                    )}
                  </div>
                )}

                {/* AI tool prompt */}
                {!buildDeleted && (
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
                            {downloadUrl || `${siteConfig.githubUrl}/releases/download/build-${jobId}/${form.packageName}_${form.version}.tar.gz`}
                          </div>
                          <button
                            type="button"
                            className="absolute top-2 right-2 p-1.5 rounded bg-background border border-border text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
                            onClick={() => {
                              const prompt = `Help me install this BSgenome R package: ${downloadUrl || `${siteConfig.githubUrl}/releases/download/build-${jobId}/${form.packageName}_${form.version}.tar.gz`}`;
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
                )}

                <Button
                  variant="outline"
                  className="w-full"
                  onClick={() => {
                    setStep("input");
                    setForm(EMPTY_FORM);
                    setAccessionInput("");
                    setCircularSeqs([]);
                    setUploadedFasta(null);
                    setUploadError("");
                    setUploadState("idle");
                    setUploadProgress(0);
                    setDeleteToken("");
                    setDeleteError("");
                    setDeletingBuild(false);
                    setDeletingHistoryJobId("");
                    setBuildDeleted(false);
                  }}
                >
                  Build Another Package
                </Button>
              </CardContent>
            </Card>
          )}

          {/* Active Builds */}
          {step === "input" && queueInfo && (
            <Card className="mt-6">
              <CardHeader>
                <div className="flex items-center gap-2">
                  {queueInfo.runs && queueInfo.runs.length > 0 ? (
                    <svg className="animate-spin h-4 w-4 text-primary" viewBox="0 0 24 24" fill="none">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"/>
                    </svg>
                  ) : (
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#0f7b3f" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/></svg>
                  )}
                  <CardTitle className="text-lg">Build Status</CardTitle>
                </div>
                <CardDescription>
                  {queueInfo.runs && queueInfo.runs.length > 0
                    ? `${queueInfo.running} running, ${queueInfo.queued} waiting`
                    : "All clear — the build server is idle. Your build will start immediately!"}
                </CardDescription>
              </CardHeader>
              {queueInfo.runs && queueInfo.runs.length > 0 && (
                <CardContent>
                  <div className="space-y-2">
                    {queueInfo.runs.map((run, idx) => (
                      <div
                        key={run.id}
                        className="flex items-center justify-between gap-3 p-2.5 rounded-md bg-secondary/50 border border-border"
                      >
                        <div className="flex items-center gap-2.5 min-w-0">
                          <div className={`w-2 h-2 rounded-full shrink-0 ${
                            run.status === "running" ? "bg-primary animate-pulse" : "bg-muted-foreground"
                          }`} />
                          <div className="min-w-0">
                            <p className="text-sm font-medium text-foreground truncate">
                              {run.name || "BSgenome build"}
                            </p>
                            <p className="text-xs text-muted-foreground">
                              {run.status === "running" ? "Building now" : `Queue #${idx + 1}`}
                              {run.status !== "running" && ` · ~${(idx + 1) * 2} min wait`}
                            </p>
                          </div>
                        </div>
                        <Badge variant="outline" className="shrink-0 text-xs">
                          {run.status === "running" ? "Running" : "Queued"}
                        </Badge>
                      </div>
                    ))}
                  </div>
                </CardContent>
              )}
            </Card>
          )}

          {/* Recent Builds */}
          {buildHistory.filter(r => r.packageName && r.organism).length > 0 && step === "input" && (
            <Card className="mt-6">
              <CardHeader>
                <CardTitle className="text-lg">Recent Builds</CardTitle>
                <CardDescription>
                  Your previous builds (stored locally in this browser)
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {buildHistory.filter(r => r.packageName && r.organism).slice(0, 5).map((record) => (
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
                      <div className="shrink-0 flex items-center gap-2">
                        {record.deleted ? (
                          <Badge variant="outline" className="text-xs">Deleted</Badge>
                        ) : (
                          <>
                            {record.downloadUrl && (
                              <a
                                href={record.downloadUrl}
                                className="inline-flex items-center gap-1 rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
                              >
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                                Download
                              </a>
                            )}
                            {record.deleteToken && (
                              <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                className="border-destructive/40 text-destructive hover:bg-destructive/10"
                                disabled={deletingHistoryJobId === record.jobId}
                                onClick={() => handleDeleteHistoryBuild(record)}
                              >
                                {deletingHistoryJobId === record.jobId ? "Deleting..." : "Delete"}
                              </Button>
                            )}
                          </>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </main>

      <SiteFooter />
    </div>
  );
}
