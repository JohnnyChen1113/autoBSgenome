interface Env {
  GITHUB_PAT: string;
  GITHUB_REPO: string;
  ALLOWED_ORIGIN: string;
  FASTA_UPLOADS?: R2Bucket;
  UPLOAD_TOKEN_SECRET?: string;
}

function corsHeaders(origin: string, allowedOrigin: string): HeadersInit {
  const allowedOrigins = allowedOrigin
    .split(",")
    .map((entry) => entry.trim())
    .filter(Boolean);
  const fallbackOrigin = allowedOrigins[0] ?? allowedOrigin;

  // Allow localhost for development
  const isAllowed =
    allowedOrigins.includes(origin) ||
    origin.endsWith(".autobsgenome.pages.dev") ||
    origin === "https://autobsgenome.bioinfoark.workers.dev" ||
    /^https:\/\/autobsgenome-web-staging\.[a-z0-9-]+\.workers\.dev$/i.test(origin) ||
    origin.startsWith("http://localhost:");

  return {
    "Access-Control-Allow-Origin": isAllowed ? origin : fallbackOrigin,
    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
  };
}

function jsonResponse(
  data: unknown,
  status: number,
  origin: string,
  allowedOrigin: string
): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "Content-Type": "application/json",
      ...corsHeaders(origin, allowedOrigin),
    },
  });
}

function validatePackageName(name: string): string[] {
  const errors: string[] = [];
  const parts = name.split(".");

  if (parts.length !== 4) {
    errors.push("Must have exactly 4 parts separated by dots.");
    return errors;
  }

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
  if (!/^[A-Za-z][A-Za-z0-9.]*[A-Za-z0-9]$/.test(name) || name.includes("..")) {
    errors.push("Package name must contain only letters, numbers, and dots.");
  }

  return errors;
}

async function sha256Hex(blob: Blob): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", await blob.arrayBuffer());
  return [...new Uint8Array(digest)]
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

const MAX_QUEUE_SIZE = 5;
const MAX_FASTA_UPLOAD_BYTES = 4 * 1024 * 1024 * 1024;
const FASTA_UPLOAD_PART_SIZE_BYTES = 64 * 1024 * 1024;
const UPLOAD_URL_TTL_SECONDS = 2 * 24 * 60 * 60;
const FASTA_EXT_RE = /\.(fa|fasta|fna|fas)(\.gz)?$/i;

type GitHubWorkflowRun = {
  id: number;
  status: string;
  conclusion: string | null;
  created_at: string;
  run_started_at?: string | null;
  updated_at: string;
  display_title?: string;
  html_url?: string;
};

type GitHubWorkflowStep = {
  name: string;
  status: string;
  conclusion: string | null;
  started_at?: string | null;
  completed_at?: string | null;
};

type GitHubWorkflowJob = {
  id: number;
  name: string;
  status: string;
  conclusion: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  html_url?: string;
  steps?: GitHubWorkflowStep[];
};

type BuildProgressStep = {
  key: string;
  label: string;
  status: "pending" | "running" | "complete" | "failed" | "skipped";
  seconds?: number;
  started_at?: string;
  completed_at?: string;
};

type BuildProgress = {
  build_steps: BuildProgressStep[];
  workflow_run_id?: number;
  workflow_run_url?: string;
  workflow_status?: string;
  workflow_conclusion?: string | null;
  total_seconds?: number;
};

function githubHeaders(env: Env): HeadersInit {
  return {
    Authorization: `Bearer ${env.GITHUB_PAT}`,
    Accept: "application/vnd.github+json",
    "User-Agent": "AutoBSgenome-Worker",
    "X-GitHub-Api-Version": "2022-11-28",
  };
}

function sanitizeFileName(name: string): string {
  const baseName = name.split(/[\\/]/).pop()?.trim() || "genome.fa";
  const safe = baseName.replace(/[^A-Za-z0-9._-]+/g, "_").slice(0, 180);
  return safe || "genome.fa";
}

function uploadSecret(env: Env): string {
  return env.UPLOAD_TOKEN_SECRET || env.GITHUB_PAT;
}

async function hmacHex(secret: string, value: string): Promise<string> {
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"]
  );
  const signature = await crypto.subtle.sign(
    "HMAC",
    key,
    new TextEncoder().encode(value)
  );
  return [...new Uint8Array(signature)]
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

function constantTimeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let mismatch = 0;
  for (let i = 0; i < a.length; i += 1) {
    mismatch |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  return mismatch === 0;
}

async function uploadToken(
  env: Env,
  uploadId: string,
  fileName: string,
  expiresAt: number,
  r2UploadId = ""
): Promise<string> {
  const suffix = r2UploadId ? `:${r2UploadId}` : "";
  return hmacHex(uploadSecret(env), `${uploadId}:${fileName}:${expiresAt}${suffix}`);
}

async function buildDeleteToken(env: Env, jobId: string): Promise<string> {
  return hmacHex(uploadSecret(env), `build-delete:${jobId}`);
}

function uploadKey(uploadId: string, fileName: string): string {
  return `uploads/${uploadId}/${fileName}`;
}

async function verifyUploadUrl(
  env: Env,
  url: URL
): Promise<{ uploadId: string; fileName: string; key: string; r2UploadId: string } | null> {
  const match = url.pathname.match(
    /^\/api\/uploads\/([a-zA-Z0-9-]+)(?:\/(?:parts\/[0-9]+|complete))?$/
  );
  const fileName = sanitizeFileName(url.searchParams.get("name") ?? "");
  const token = url.searchParams.get("token") ?? "";
  const expiresAt = Number(url.searchParams.get("exp") ?? "0");
  const r2UploadId = url.searchParams.get("r2") ?? "";

  if (!match || !fileName || !token || !Number.isFinite(expiresAt)) {
    return null;
  }
  if (expiresAt < Math.floor(Date.now() / 1000)) {
    return null;
  }

  const expected = await uploadToken(env, match[1], fileName, expiresAt, r2UploadId);
  if (!constantTimeEqual(token, expected)) {
    return null;
  }

  return {
    uploadId: match[1],
    fileName,
    key: uploadKey(match[1], fileName),
    r2UploadId,
  };
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    const origin = request.headers.get("Origin") ?? "";

    // Handle CORS preflight
    if (request.method === "OPTIONS") {
      return new Response(null, {
        status: 204,
        headers: corsHeaders(origin, env.ALLOWED_ORIGIN),
      });
    }

    // GET /api/queue — check current build queue status
    if (url.pathname === "/api/queue" && request.method === "GET") {
      return handleQueue(env, origin);
    }

    // POST /api/build — trigger a BSgenome build
    if (url.pathname === "/api/build" && request.method === "POST") {
      return handleBuild(request, env, origin);
    }

    // DELETE /api/build/:jobId — delete a temporary build release
    const deleteBuildMatch = url.pathname.match(/^\/api\/build\/([a-zA-Z0-9-]+)$/);
    if (deleteBuildMatch && request.method === "DELETE") {
      return handleDeleteBuild(deleteBuildMatch[1], request, env, origin);
    }

    // POST /api/uploads — create a signed R2 upload URL for user FASTA files
    if (url.pathname === "/api/uploads" && request.method === "POST") {
      return handleCreateUpload(request, env, origin);
    }

    // PUT /api/uploads/:uploadId/parts/:partNumber — upload one multipart chunk
    const partMatch = url.pathname.match(/^\/api\/uploads\/([a-zA-Z0-9-]+)\/parts\/([0-9]+)$/);
    if (partMatch && request.method === "PUT") {
      return handleUploadPart(request, env, origin, Number(partMatch[2]));
    }

    // POST /api/uploads/:uploadId/complete — complete multipart FASTA upload
    const completeMatch = url.pathname.match(/^\/api\/uploads\/([a-zA-Z0-9-]+)\/complete$/);
    if (completeMatch && request.method === "POST") {
      return handleCompleteUpload(request, env, origin);
    }

    // PUT/GET/DELETE /api/uploads/:uploadId — upload, download, or delete FASTA
    const uploadMatch = url.pathname.match(/^\/api\/uploads\/([a-zA-Z0-9-]+)$/);
    if (uploadMatch && ["PUT", "GET", "DELETE"].includes(request.method)) {
      return handleUploadObject(request, env, origin);
    }

    // GET /api/status/:jobId — check build status via GitHub Release
    const statusMatch = url.pathname.match(/^\/api\/status\/([a-zA-Z0-9-]+)$/);
    if (statusMatch && request.method === "GET") {
      return handleStatus(statusMatch[1], env, origin);
    }

    // POST /api/publish — publish a temp build to the permanent repository
    if (url.pathname === "/api/publish" && request.method === "POST") {
      return handlePublish(request, env, origin);
    }

    return jsonResponse({ error: "Not found" }, 404, origin, env.ALLOWED_ORIGIN);
  },
};

async function getQueueInfo(env: Env): Promise<{
  running: number;
  queued: number;
  runs: { id: number; status: string; name: string; created_at: string }[];
}> {
  const ghHeaders = {
    Authorization: `Bearer ${env.GITHUB_PAT}`,
    Accept: "application/vnd.github+json",
    "User-Agent": "AutoBSgenome-Worker",
  };
  const res = await fetch(
    `https://api.github.com/repos/${env.GITHUB_REPO}/actions/workflows/build-bsgenome.yml/runs?status=in_progress&per_page=10`,
    { headers: ghHeaders }
  );
  const queuedRes = await fetch(
    `https://api.github.com/repos/${env.GITHUB_REPO}/actions/workflows/build-bsgenome.yml/runs?status=queued&per_page=10`,
    { headers: ghHeaders }
  );
  const waitingRes = await fetch(
    `https://api.github.com/repos/${env.GITHUB_REPO}/actions/workflows/build-bsgenome.yml/runs?status=waiting&per_page=10`,
    { headers: ghHeaders }
  );

  let running = 0, queued = 0;
  const runs: { id: number; status: string; name: string; created_at: string }[] = [];

  if (res.ok) {
    const data = await res.json<{ total_count: number; workflow_runs: { id: number; status: string; display_title: string; created_at: string }[] }>();
    running = data.total_count;
    for (const r of data.workflow_runs) {
      runs.push({ id: r.id, status: "running", name: r.display_title, created_at: r.created_at });
    }
  }
  if (queuedRes.ok) {
    const data = await queuedRes.json<{ total_count: number; workflow_runs: { id: number; status: string; display_title: string; created_at: string }[] }>();
    queued += data.total_count;
    for (const r of data.workflow_runs) {
      runs.push({ id: r.id, status: "queued", name: r.display_title, created_at: r.created_at });
    }
  }
  if (waitingRes.ok) {
    const data = await waitingRes.json<{ total_count: number; workflow_runs: { id: number; status: string; display_title: string; created_at: string }[] }>();
    queued += data.total_count;
    for (const r of data.workflow_runs) {
      runs.push({ id: r.id, status: "waiting", name: r.display_title, created_at: r.created_at });
    }
  }

  return { running, queued, runs };
}

async function handleQueue(
  env: Env,
  origin: string
): Promise<Response> {
  const queue = await getQueueInfo(env);
  return jsonResponse(
    {
      running: queue.running,
      queued: queue.queued,
      total: queue.running + queue.queued,
      max_queue: MAX_QUEUE_SIZE,
      runs: queue.runs,
    },
    200,
    origin,
    env.ALLOWED_ORIGIN
  );
}

async function handleCreateUpload(
  request: Request,
  env: Env,
  origin: string
): Promise<Response> {
  if (!env.FASTA_UPLOADS) {
    return jsonResponse(
      { error: "FASTA uploads are not configured on this API deployment" },
      503,
      origin,
      env.ALLOWED_ORIGIN
    );
  }

  const body = await request.json<{
    file_name?: string;
    file_size?: number;
    content_type?: string;
  }>();
  const fileName = sanitizeFileName(body.file_name ?? "");
  const fileSize = Number(body.file_size ?? 0);
  const contentType = body.content_type || "application/octet-stream";

  if (!FASTA_EXT_RE.test(fileName)) {
    return jsonResponse(
      { error: "Upload must be a FASTA file: .fa, .fasta, .fna, .fas, optionally .gz" },
      400,
      origin,
      env.ALLOWED_ORIGIN
    );
  }
  if (!Number.isFinite(fileSize) || fileSize <= 0) {
    return jsonResponse(
      { error: "Missing or invalid file_size" },
      400,
      origin,
      env.ALLOWED_ORIGIN
    );
  }
  if (fileSize > MAX_FASTA_UPLOAD_BYTES) {
    return jsonResponse(
      {
        error: "FASTA upload is too large",
        max_upload_bytes: MAX_FASTA_UPLOAD_BYTES,
      },
      413,
      origin,
      env.ALLOWED_ORIGIN
    );
  }

  const uploadId = crypto.randomUUID();
  const key = uploadKey(uploadId, fileName);
  const multipart = await env.FASTA_UPLOADS.createMultipartUpload(key, {
    httpMetadata: { contentType },
    customMetadata: {
      upload_id: uploadId,
      file_name: fileName,
      declared_size: String(fileSize),
      created_at: new Date().toISOString(),
    },
  });
  const r2UploadId = multipart.uploadId;
  const expiresAt = Math.floor(Date.now() / 1000) + UPLOAD_URL_TTL_SECONDS;
  const token = await uploadToken(env, uploadId, fileName, expiresAt, r2UploadId);
  const objectUrl = new URL(`/api/uploads/${uploadId}`, request.url);
  objectUrl.searchParams.set("name", fileName);
  objectUrl.searchParams.set("exp", String(expiresAt));
  objectUrl.searchParams.set("r2", r2UploadId);
  objectUrl.searchParams.set("token", token);
  const partUrlTemplate = new URL(`/api/uploads/${uploadId}/parts/{part_number}`, request.url);
  partUrlTemplate.search = objectUrl.search;
  const completeUrl = new URL(`/api/uploads/${uploadId}/complete`, request.url);
  completeUrl.search = objectUrl.search;

  return jsonResponse(
    {
      upload_id: uploadId,
      r2_upload_id: r2UploadId,
      file_name: fileName,
      file_size: fileSize,
      content_type: contentType,
      part_size: FASTA_UPLOAD_PART_SIZE_BYTES,
      part_url_template: partUrlTemplate
        .toString()
        .replace("%7Bpart_number%7D", "{part_number}"),
      complete_url: completeUrl.toString(),
      download_url: objectUrl.toString(),
      delete_url: objectUrl.toString(),
      expires_at: new Date(expiresAt * 1000).toISOString(),
      max_upload_bytes: MAX_FASTA_UPLOAD_BYTES,
    },
    200,
    origin,
    env.ALLOWED_ORIGIN
  );
}

async function handleUploadPart(
  request: Request,
  env: Env,
  origin: string,
  partNumber: number
): Promise<Response> {
  if (!env.FASTA_UPLOADS) {
    return jsonResponse(
      { error: "FASTA uploads are not configured on this API deployment" },
      503,
      origin,
      env.ALLOWED_ORIGIN
    );
  }
  if (!Number.isInteger(partNumber) || partNumber < 1 || partNumber > 10000) {
    return jsonResponse({ error: "Invalid part number" }, 400, origin, env.ALLOWED_ORIGIN);
  }

  const url = new URL(request.url);
  const verified = await verifyUploadUrl(env, url);
  if (!verified || !verified.r2UploadId) {
    return jsonResponse(
      { error: "Invalid or expired multipart upload URL" },
      403,
      origin,
      env.ALLOWED_ORIGIN
    );
  }

  const contentLength = Number(request.headers.get("Content-Length") ?? "0");
  if (contentLength > FASTA_UPLOAD_PART_SIZE_BYTES) {
    return jsonResponse(
      {
        error: "FASTA upload part is too large",
        max_part_bytes: FASTA_UPLOAD_PART_SIZE_BYTES,
      },
      413,
      origin,
      env.ALLOWED_ORIGIN
    );
  }
  if (!request.body) {
    return jsonResponse({ error: "Missing upload part body" }, 400, origin, env.ALLOWED_ORIGIN);
  }

  const multipart = env.FASTA_UPLOADS.resumeMultipartUpload(
    verified.key,
    verified.r2UploadId
  );
  const uploadedPart = await multipart.uploadPart(partNumber, request.body);
  return jsonResponse(
    {
      part_number: uploadedPart.partNumber,
      etag: uploadedPart.etag,
    },
    200,
    origin,
    env.ALLOWED_ORIGIN
  );
}

async function handleCompleteUpload(
  request: Request,
  env: Env,
  origin: string
): Promise<Response> {
  if (!env.FASTA_UPLOADS) {
    return jsonResponse(
      { error: "FASTA uploads are not configured on this API deployment" },
      503,
      origin,
      env.ALLOWED_ORIGIN
    );
  }

  const url = new URL(request.url);
  const verified = await verifyUploadUrl(env, url);
  if (!verified || !verified.r2UploadId) {
    return jsonResponse(
      { error: "Invalid or expired multipart upload URL" },
      403,
      origin,
      env.ALLOWED_ORIGIN
    );
  }

  const body = await request.json<{
    parts?: { part_number?: number; partNumber?: number; etag?: string }[];
  }>().catch(() => ({}));
  const parts = (body.parts ?? [])
    .map((part) => ({
      partNumber: Number(part.partNumber ?? part.part_number ?? 0),
      etag: String(part.etag ?? ""),
    }))
    .filter((part) => Number.isInteger(part.partNumber) && part.partNumber > 0 && part.etag)
    .sort((a, b) => a.partNumber - b.partNumber);

  if (parts.length === 0) {
    return jsonResponse({ error: "No upload parts supplied" }, 400, origin, env.ALLOWED_ORIGIN);
  }

  const multipart = env.FASTA_UPLOADS.resumeMultipartUpload(
    verified.key,
    verified.r2UploadId
  );
  await multipart.complete(parts);

  return jsonResponse(
    {
      status: "uploaded",
      upload_id: verified.uploadId,
      file_name: verified.fileName,
      download_url: url.origin + `/api/uploads/${verified.uploadId}` + url.search,
    },
    200,
    origin,
    env.ALLOWED_ORIGIN
  );
}

async function handleUploadObject(
  request: Request,
  env: Env,
  origin: string
): Promise<Response> {
  if (!env.FASTA_UPLOADS) {
    return jsonResponse(
      { error: "FASTA uploads are not configured on this API deployment" },
      503,
      origin,
      env.ALLOWED_ORIGIN
    );
  }

  const url = new URL(request.url);
  const verified = await verifyUploadUrl(env, url);
  if (!verified) {
    return jsonResponse(
      { error: "Invalid or expired upload URL" },
      403,
      origin,
      env.ALLOWED_ORIGIN
    );
  }

  if (request.method === "PUT") {
    return jsonResponse(
      { error: "Use multipart part URLs for FASTA uploads" },
      405,
      origin,
      env.ALLOWED_ORIGIN
    );
  }

  if (request.method === "DELETE") {
    if (verified.r2UploadId) {
      const multipart = env.FASTA_UPLOADS.resumeMultipartUpload(
        verified.key,
        verified.r2UploadId
      );
      await multipart.abort().catch(() => undefined);
    }
    await env.FASTA_UPLOADS.delete(verified.key);
    return jsonResponse(
      { status: "deleted", upload_id: verified.uploadId },
      200,
      origin,
      env.ALLOWED_ORIGIN
    );
  }

  const object = await env.FASTA_UPLOADS.get(verified.key);
  if (!object) {
    return jsonResponse(
      { error: "Uploaded FASTA not found" },
      404,
      origin,
      env.ALLOWED_ORIGIN
    );
  }

  return new Response(object.body, {
    headers: {
      "Content-Type": object.httpMetadata?.contentType || "application/octet-stream",
      "Content-Length": String(object.size),
      "Content-Disposition": `attachment; filename="${verified.fileName}"`,
      ...corsHeaders(origin, env.ALLOWED_ORIGIN),
    },
  });
}

async function handleBuild(
  request: Request,
  env: Env,
  origin: string
): Promise<Response> {
  const body = await request.json<Record<string, string>>();

  // Validate required fields
  if (!body.package_name || !body.organism) {
    return jsonResponse(
      { error: "Missing required fields: package_name, organism" },
      400,
      origin,
      env.ALLOWED_ORIGIN
    );
  }

  const packageNameErrors = validatePackageName(body.package_name);
  if (packageNameErrors.length > 0) {
    return jsonResponse(
      {
        error: "Invalid package_name",
        details: packageNameErrors,
      },
      400,
      origin,
      env.ALLOWED_ORIGIN
    );
  }

  const fastaSource = body.fasta_source === "upload"
    ? "upload"
    : body.fasta_source === "url"
    ? "url"
    : body.data_source ?? "ncbi";
  let fastaUploadUrl = "";
  let fastaUrl = "";
  let fastaFileName = "";
  let fastaFileSize = "";

  if (fastaSource === "url") {
    if (!body.fasta_url) {
      return jsonResponse(
        { error: "Missing fasta_url for FASTA URL build" },
        400,
        origin,
        env.ALLOWED_ORIGIN
      );
    }
    try {
      const parsed = new URL(body.fasta_url);
      if (parsed.protocol !== "https:" && parsed.protocol !== "http:") {
        throw new Error("unsupported protocol");
      }
      fastaUrl = parsed.toString();
    } catch {
      return jsonResponse(
        { error: "Invalid fasta_url; use an http or https URL" },
        400,
        origin,
        env.ALLOWED_ORIGIN
      );
    }
  }

  if (fastaSource === "upload") {
    if (!env.FASTA_UPLOADS) {
      return jsonResponse(
        { error: "FASTA uploads are not configured on this API deployment" },
        503,
        origin,
        env.ALLOWED_ORIGIN
      );
    }
    if (!body.fasta_upload_url) {
      return jsonResponse(
        { error: "Missing fasta_upload_url for uploaded FASTA build" },
        400,
        origin,
        env.ALLOWED_ORIGIN
      );
    }

    let uploadUrl: URL;
    try {
      uploadUrl = new URL(body.fasta_upload_url);
    } catch {
      return jsonResponse(
        { error: "Invalid fasta_upload_url" },
        400,
        origin,
        env.ALLOWED_ORIGIN
      );
    }
    if (uploadUrl.origin !== new URL(request.url).origin) {
      return jsonResponse(
        { error: "Uploaded FASTA URL must be issued by this API" },
        400,
        origin,
        env.ALLOWED_ORIGIN
      );
    }

    const verified = await verifyUploadUrl(env, uploadUrl);
    if (!verified) {
      return jsonResponse(
        { error: "Uploaded FASTA URL is invalid or expired" },
        403,
        origin,
        env.ALLOWED_ORIGIN
      );
    }
    const uploaded = await env.FASTA_UPLOADS.head(verified.key);
    if (!uploaded) {
      return jsonResponse(
        { error: "Upload the FASTA file before starting the build" },
        400,
        origin,
        env.ALLOWED_ORIGIN
      );
    }

    fastaUploadUrl = uploadUrl.toString();
    fastaFileName = verified.fileName;
    fastaFileSize = String(uploaded.size || body.fasta_file_size || "");
  }

  // Check queue depth for user info (never reject — always accept)
  const queue = await getQueueInfo(env);

  // Generate job ID
  const jobId = crypto.randomUUID().slice(0, 8);

  // Trigger GitHub Actions via repository_dispatch
  const ghResponse = await fetch(
    `https://api.github.com/repos/${env.GITHUB_REPO}/dispatches`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.GITHUB_PAT}`,
        Accept: "application/vnd.github+json",
        "User-Agent": "AutoBSgenome-Worker",
        "X-GitHub-Api-Version": "2022-11-28",
      },
      body: JSON.stringify({
        event_type: "build_bsgenome",
        client_payload: {
          job_id: jobId,
          package_name: body.package_name,
          organism: body.organism,
          common_name: body.common_name ?? "",
          genome: body.genome ?? "",
          provider: body.provider ?? "",
          version: body.version ?? "1.0.0",
          circ_seqs: body.circ_seqs ?? "character(0)",
          accession: body.accession ?? "",
          // Pack remaining fields into JSON to stay within 10-property limit
          extra: JSON.stringify({
            data_source: body.data_source ?? "ncbi",
            fasta_source: fastaSource,
            fasta_url: fastaUrl,
            fasta_upload_url: fastaUploadUrl,
            fasta_file_name: fastaFileName,
            fasta_file_size: fastaFileSize,
            release_date: body.release_date ?? "",
            title: body.title ?? "",
            description: body.description ?? "",
            source_url: body.source_url ?? "",
          }),
        },
      }),
    }
  );

  if (!ghResponse.ok) {
    const errText = await ghResponse.text();
    return jsonResponse(
      {
        error: "Failed to trigger build",
        details: {
          status: ghResponse.status,
          statusText: ghResponse.statusText,
          body: errText,
        },
      },
      500,
      origin,
      env.ALLOWED_ORIGIN
    );
  }

  return jsonResponse(
    {
      job_id: jobId,
      status: "queued",
      queue_position: queue.running + queue.queued,
      delete_token: await buildDeleteToken(env, jobId),
    },
    200,
    origin,
    env.ALLOWED_ORIGIN
  );
}

async function handleDeleteBuild(
  jobId: string,
  request: Request,
  env: Env,
  origin: string
): Promise<Response> {
  const body = await request.json<{ delete_token?: string }>().catch(() => ({}));
  const token = body.delete_token ?? "";
  const expected = await buildDeleteToken(env, jobId);
  if (!constantTimeEqual(token, expected)) {
    return jsonResponse(
      { error: "Invalid delete token" },
      403,
      origin,
      env.ALLOWED_ORIGIN
    );
  }

  const ghHeaders = {
    Authorization: `Bearer ${env.GITHUB_PAT}`,
    Accept: "application/vnd.github+json",
    "User-Agent": "AutoBSgenome-Worker",
    "X-GitHub-Api-Version": "2022-11-28",
  };
  const tag = `build-${jobId}`;

  let releaseDeleted = false;
  const releaseRes = await fetch(
    `https://api.github.com/repos/${env.GITHUB_REPO}/releases/tags/${tag}`,
    { headers: ghHeaders }
  );
  if (releaseRes.ok) {
    const release = await releaseRes.json<{ id: number }>();
    const deleteReleaseRes = await fetch(
      `https://api.github.com/repos/${env.GITHUB_REPO}/releases/${release.id}`,
      { method: "DELETE", headers: ghHeaders }
    );
    if (!deleteReleaseRes.ok) {
      const details = await deleteReleaseRes.text();
      return jsonResponse(
        { error: "Failed to delete temporary release", details },
        500,
        origin,
        env.ALLOWED_ORIGIN
      );
    }
    releaseDeleted = true;
  } else if (releaseRes.status !== 404) {
    const details = await releaseRes.text();
    return jsonResponse(
      { error: "Failed to look up temporary release", details },
      500,
      origin,
      env.ALLOWED_ORIGIN
    );
  }

  let tagDeleted = false;
  const deleteTagRes = await fetch(
    `https://api.github.com/repos/${env.GITHUB_REPO}/git/refs/tags/${tag}`,
    { method: "DELETE", headers: ghHeaders }
  );
  if (deleteTagRes.status === 204) {
    tagDeleted = true;
  } else if (deleteTagRes.status !== 404) {
    const details = await deleteTagRes.text();
    return jsonResponse(
      { error: "Temporary release was deleted, but deleting its tag failed", details },
      500,
      origin,
      env.ALLOWED_ORIGIN
    );
  }

  return jsonResponse(
    {
      status: "deleted",
      job_id: jobId,
      release_deleted: releaseDeleted,
      tag_deleted: tagDeleted,
    },
    200,
    origin,
    env.ALLOWED_ORIGIN
  );
}

function parseGitHubTime(value?: string | null): number | null {
  if (!value) return null;
  const timestamp = Date.parse(value);
  return Number.isFinite(timestamp) ? timestamp : null;
}

function elapsedSeconds(start?: string | null, end?: string | null): number | undefined {
  const startMs = parseGitHubTime(start);
  if (startMs === null) return undefined;
  const endMs = parseGitHubTime(end) ?? Date.now();
  return Math.max(0, Math.round((endMs - startMs) / 1000));
}

function actionStepState(step?: GitHubWorkflowStep): BuildProgressStep["status"] {
  if (!step) return "pending";
  if (step.status !== "completed") return "running";
  if (step.conclusion === "success") return "complete";
  if (step.conclusion === "skipped") return "skipped";
  return "failed";
}

function actionStepSummary(
  key: string,
  label: string,
  step?: GitHubWorkflowStep
): BuildProgressStep {
  const status = actionStepState(step);
  return {
    key,
    label,
    status,
    seconds: step ? elapsedSeconds(step.started_at, step.completed_at) : undefined,
    started_at: step?.started_at ?? undefined,
    completed_at: step?.completed_at ?? undefined,
  };
}

function findActionStep(
  job: GitHubWorkflowJob | null,
  names: string[]
): GitHubWorkflowStep | undefined {
  const nameSet = new Set(names);
  return job?.steps?.find((step) => nameSet.has(step.name));
}

function summarizeStepGroup(
  key: string,
  label: string,
  job: GitHubWorkflowJob | null,
  names: string[],
  completeWhenAnyLaterStepStarted = false,
  laterNames: string[] = []
): BuildProgressStep {
  const matching = job?.steps?.filter((step) => names.includes(step.name)) ?? [];
  const laterStarted = completeWhenAnyLaterStepStarted
    ? job?.steps?.some(
        (step) =>
          laterNames.includes(step.name) &&
          (step.started_at || step.status === "completed")
      )
    : false;

  if (matching.some((step) => step.status === "completed" && step.conclusion && !["success", "skipped"].includes(step.conclusion))) {
    const failed = matching.find((step) => step.status === "completed" && step.conclusion && !["success", "skipped"].includes(step.conclusion));
    return {
      key,
      label,
      status: "failed",
      seconds: failed ? elapsedSeconds(failed.started_at, failed.completed_at) : undefined,
      started_at: failed?.started_at ?? undefined,
      completed_at: failed?.completed_at ?? undefined,
    };
  }

  const started = matching.filter((step) => step.started_at || step.status === "completed");
  const running = matching.find((step) => step.status !== "completed" && step.started_at);
  const completed = matching.filter((step) => step.status === "completed" && step.conclusion === "success");
  const final = matching[matching.length - 1];
  const finalComplete =
    Boolean(final && final.status === "completed" && final.conclusion === "success") ||
    Boolean(laterStarted);

  const seconds =
    started.length > 0
      ? Math.round(
          started.reduce(
            (total, step) => total + (elapsedSeconds(step.started_at, step.completed_at) ?? 0),
            0
          )
        )
      : undefined;

  if (finalComplete) {
    return {
      key,
      label,
      status: "complete",
      seconds,
      started_at: started[0]?.started_at ?? undefined,
      completed_at:
        final?.completed_at ??
        completed[completed.length - 1]?.completed_at ??
        undefined,
    };
  }

  if (running || started.length > 0) {
    return {
      key,
      label,
      status: "running",
      seconds,
      started_at: started[0]?.started_at ?? running?.started_at ?? undefined,
      completed_at: undefined,
    };
  }

  return { key, label, status: "pending" };
}

async function findWorkflowRunForJob(
  jobId: string,
  env: Env
): Promise<GitHubWorkflowRun | null> {
  const headers = githubHeaders(env);
  for (let page = 1; page <= 3; page += 1) {
    const res = await fetch(
      `https://api.github.com/repos/${env.GITHUB_REPO}/actions/workflows/build-bsgenome.yml/runs?event=repository_dispatch&per_page=100&page=${page}`,
      { headers }
    );
    if (!res.ok) return null;
    const data = await res.json<{ workflow_runs?: GitHubWorkflowRun[] }>();
    const run = data.workflow_runs?.find((candidate) =>
      (candidate.display_title ?? "").includes(`[job ${jobId}]`)
    );
    if (run) return run;
    if (!data.workflow_runs || data.workflow_runs.length < 100) break;
  }
  return null;
}

async function getWorkflowJob(
  runId: number,
  env: Env
): Promise<GitHubWorkflowJob | null> {
  const res = await fetch(
    `https://api.github.com/repos/${env.GITHUB_REPO}/actions/runs/${runId}/jobs?per_page=100`,
    { headers: githubHeaders(env) }
  );
  if (!res.ok) return null;
  const data = await res.json<{ jobs?: GitHubWorkflowJob[] }>();
  return data.jobs?.find((job) => job.name === "build") ?? data.jobs?.[0] ?? null;
}

async function getBuildProgress(
  jobId: string,
  env: Env,
  releaseExists: boolean
): Promise<BuildProgress | null> {
  const run = await findWorkflowRunForJob(jobId, env);
  if (!run) return null;
  const job = await getWorkflowJob(run.id, env);
  const downloadStep = findActionStep(job, [
    "Download FASTA from NCBI",
    "Download FASTA from Ensembl",
    "Download FASTA from URL",
    "Download uploaded FASTA",
  ]);
  const convertStep = findActionStep(job, ["Convert FASTA to 2bit"]);
  const releaseStep = findActionStep(job, [
    "Create GitHub Release",
    "Publish oversized tarball to Zenodo",
  ]);
  const releaseStatus = releaseExists
    ? "complete"
    : actionStepState(releaseStep);
  const queueSeconds = elapsedSeconds(
    run.created_at,
    job?.started_at ?? run.run_started_at ?? null
  );
  const queueComplete = Boolean(job?.started_at || run.run_started_at);
  const buildSteps: BuildProgressStep[] = [
    {
      key: "queue",
      label: "Queuing build on GitHub Actions",
      status: queueComplete ? "complete" : "running",
      seconds: queueSeconds,
      started_at: run.created_at,
      completed_at: queueComplete ? job?.started_at ?? run.run_started_at ?? undefined : undefined,
    },
    actionStepSummary("download", "Downloading FASTA", downloadStep),
    actionStepSummary("twobit", "Converting to 2bit format", convertStep),
    summarizeStepGroup(
      "package",
      "Building R package",
      job,
      ["Generate seed file", "Forge BSgenome package", "R CMD build (assemble tarball)"],
      true,
      ["Determine storage backend", "Create GitHub Release", "Publish oversized tarball to Zenodo"]
    ),
    {
      ...actionStepSummary("release", "Uploading package release", releaseStep),
      status: releaseStatus,
      seconds:
        releaseStep ? elapsedSeconds(releaseStep.started_at, releaseStep.completed_at) : undefined,
      completed_at: releaseExists
        ? releaseStep?.completed_at ?? releaseStep?.started_at ?? undefined
        : releaseStep?.completed_at ?? undefined,
    },
  ];
  const totalSeconds = elapsedSeconds(
    run.run_started_at ?? run.created_at,
    run.status === "completed" ? run.updated_at : null
  );
  return {
    build_steps: buildSteps,
    workflow_run_id: run.id,
    workflow_run_url: run.html_url,
    workflow_status: run.status,
    workflow_conclusion: run.conclusion,
    total_seconds: totalSeconds,
  };
}

async function handleStatus(
  jobId: string,
  env: Env,
  origin: string
): Promise<Response> {
  const tag = `build-${jobId}`;
  const headers = githubHeaders(env);

  // Check if a release with this tag exists
  const ghResponse = await fetch(
    `https://api.github.com/repos/${env.GITHUB_REPO}/releases/tags/${tag}`,
    { headers }
  );

  if (ghResponse.status === 404) {
    // Release doesn't exist yet — still building
    const progress = await getBuildProgress(jobId, env, false).catch(() => null);
    return jsonResponse(
      { job_id: jobId, status: "building", ...(progress ?? {}) },
      200,
      origin,
      env.ALLOWED_ORIGIN
    );
  }

  if (!ghResponse.ok) {
    const errBody = await ghResponse.text();
    return jsonResponse(
      {
        job_id: jobId,
        status: "error",
        message: `GitHub API returned ${ghResponse.status}`,
        details: errBody,
      },
      200,
      origin,
      env.ALLOWED_ORIGIN
    );
  }

  const release = await ghResponse.json<{
    name: string;
    body: string;
    assets: { name: string; browser_download_url: string; size: number }[];
  }>();

  // Check if it's a failure marker
  if (release.body?.startsWith("BUILD_FAILED")) {
    const progress = await getBuildProgress(jobId, env, true).catch(() => null);
    return jsonResponse(
      { job_id: jobId, status: "failed", message: release.body, ...(progress ?? {}) },
      200,
      origin,
      env.ALLOWED_ORIGIN
    );
  }

  // Success — return download info
  const asset = release.assets?.[0];

  // Check if this package is already published to the permanent repo
  const permTag = `pkg-${asset?.name?.replace(/_\d+\.\d+\.\d+\.tar\.gz$/, "") ?? ""}`;
  const permCheck = await fetch(
    `https://api.github.com/repos/${env.GITHUB_REPO}/releases/tags/${permTag}`,
    { headers }
  );
  const published = permCheck.status === 200;
  const progress = await getBuildProgress(jobId, env, true).catch(() => null);

  return jsonResponse(
    {
      job_id: jobId,
      status: "complete",
      package_name: release.name,
      download_url: asset?.browser_download_url ?? "",
      file_name: asset?.name ?? "",
      file_size: asset?.size ?? 0,
      published,
      ...(progress ?? {}),
    },
    200,
    origin,
    env.ALLOWED_ORIGIN
  );
}

async function handlePublish(
  request: Request,
  env: Env,
  origin: string
): Promise<Response> {
  const body = await request.json<{ job_id: string; metadata: Record<string, string> }>();
  if (!body.job_id) {
    return jsonResponse({ error: "Missing job_id" }, 400, origin, env.ALLOWED_ORIGIN);
  }
  const meta = body.metadata ?? {};
  const fastaSource = meta.fasta_source ?? "ncbi";
  const userSuppliedFasta = fastaSource === "upload" || fastaSource === "url";
  if (userSuppliedFasta) {
    const confirmed =
      meta.public_opt_in === "true" &&
      meta.public_rights_confirmed === "true" &&
      meta.public_release_confirmed === "true";
    if (!confirmed) {
      return jsonResponse(
        { error: "Publishing user-supplied FASTA builds requires public sharing confirmation" },
        400,
        origin,
        env.ALLOWED_ORIGIN
      );
    }
    if (!meta.license) {
      return jsonResponse(
        { error: "Publishing user-supplied FASTA builds requires a license" },
        400,
        origin,
        env.ALLOWED_ORIGIN
      );
    }
  }

  const tempTag = `build-${body.job_id}`;
  const ghHeaders = {
    Authorization: `Bearer ${env.GITHUB_PAT}`,
    Accept: "application/vnd.github+json",
    "User-Agent": "AutoBSgenome-Worker",
    "X-GitHub-Api-Version": "2022-11-28",
  };

  // 1. Get the temp release
  const tempRes = await fetch(
    `https://api.github.com/repos/${env.GITHUB_REPO}/releases/tags/${tempTag}`,
    { headers: ghHeaders }
  );
  if (!tempRes.ok) {
    return jsonResponse({ error: "Build not found" }, 404, origin, env.ALLOWED_ORIGIN);
  }
  const tempRelease = await tempRes.json<{
    assets: { name: string; browser_download_url: string; size: number; url: string }[];
  }>();
  const asset = tempRelease.assets?.[0];
  if (!asset) {
    return jsonResponse({ error: "No package file in build" }, 404, origin, env.ALLOWED_ORIGIN);
  }

  // 2. Download the asset
  const assetRes = await fetch(asset.browser_download_url);
  if (!assetRes.ok) {
    return jsonResponse({ error: "Failed to download package" }, 500, origin, env.ALLOWED_ORIGIN);
  }
  const assetBlob = await assetRes.blob();

  // 3. Create permanent release
  const packageBaseName = asset.name.replace(/_\d+\.\d+\.\d+\.tar\.gz$/, "");
  const permTag = `pkg-${packageBaseName}`;

  // Delete existing permanent release if any (update)
  const existingRes = await fetch(
    `https://api.github.com/repos/${env.GITHUB_REPO}/releases/tags/${permTag}`,
    { headers: ghHeaders }
  );
  if (existingRes.ok) {
    const existing = await existingRes.json<{ id: number }>();
    await fetch(
      `https://api.github.com/repos/${env.GITHUB_REPO}/releases/${existing.id}`,
      { method: "DELETE", headers: ghHeaders }
    );
  }

  const sourceUrl = meta.source_url ?? "";
  const license = meta.license ?? "";
  const packageSha256 = await sha256Hex(assetBlob);
  const builtAt = new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
  const createRes = await fetch(
    `https://api.github.com/repos/${env.GITHUB_REPO}/releases`,
    {
      method: "POST",
      headers: { ...ghHeaders, "Content-Type": "application/json" },
      body: JSON.stringify({
        tag_name: permTag,
        name: `${packageBaseName} ${meta.version ?? "1.0.0"}`,
        body: [
          `| | |`,
          `|---|---|`,
          `| **Organism** | ${meta.organism ?? "N/A"} |`,
          `| **Assembly** | ${meta.assembly ?? "N/A"} |`,
          `| **Provider** | ${meta.provider ?? "NCBI"} |`,
          ...(userSuppliedFasta ? [`| **Submission** | Community-submitted, user asserted |`] : []),
          ...(sourceUrl ? [`| **Source** | [${meta.provider ?? "source"}](${sourceUrl}) |`] : []),
          ...(license ? [`| **License** | ${license} |`] : []),
          `| **Version** | ${meta.version ?? "1.0.0"} |`,
          `| **Package** | \`${packageBaseName}\` |`,
          "",
          "**Install in R:**",
          "```r",
          `install.packages("${packageBaseName}", repos = "https://johnnychen1113.github.io/autoBSgenome")`,
          "```",
          "",
          `> Browse all packages: [autobsgenome.org](https://autobsgenome.org) | [Package repository](https://johnnychen1113.github.io/autoBSgenome)`,
          "",
          userSuppliedFasta
            ? "Published via [AutoBSgenome Web](https://autobsgenome.org) from a user-supplied nucleotide FASTA. AutoBSgenome records this source as user asserted and does not independently verify redistribution rights."
            : "Published via [AutoBSgenome Web](https://autobsgenome.org).",
        ].join("\n"),
      }),
    }
  );
  if (!createRes.ok) {
    const err = await createRes.text();
    return jsonResponse({ error: "Failed to create release", details: err }, 500, origin, env.ALLOWED_ORIGIN);
  }
  const permRelease = await createRes.json<{ upload_url: string; id: number }>();

  // 4. Upload asset to permanent release
  const uploadUrl = permRelease.upload_url.replace("{?name,label}", `?name=${encodeURIComponent(asset.name)}`);
  const uploadRes = await fetch(uploadUrl, {
    method: "POST",
    headers: {
      ...ghHeaders,
      "Content-Type": "application/gzip",
    },
    body: assetBlob,
  });
  if (!uploadRes.ok) {
    return jsonResponse({ error: "Failed to upload package" }, 500, origin, env.ALLOWED_ORIGIN);
  }

  // 5. Trigger gh-pages update (via repository_dispatch)
  await fetch(
    `https://api.github.com/repos/${env.GITHUB_REPO}/dispatches`,
    {
      method: "POST",
      headers: { ...ghHeaders, "Content-Type": "application/json" },
      body: JSON.stringify({
        event_type: "update_repo_index",
        client_payload: {
          package_name: packageBaseName,
          version: meta.version ?? "1.0.0",
          organism: meta.organism ?? "",
          assembly: meta.assembly ?? "",
          provider: meta.provider ?? "",
          accession: meta.accession ?? "",
          file_name: asset.name,
          file_size: String(asset.size),
          seq_count: meta.seq_count ?? "",
          storage_info: JSON.stringify({
            storage: "github-release",
            source_url: sourceUrl,
            license,
            provenance: {
              schema_version: 1,
              provider: meta.provider ?? "",
              source_url: sourceUrl,
              source_accession: meta.accession ?? "",
              source_type: fastaSource,
              provenance_status: userSuppliedFasta ? "user_asserted" : "verified_provider",
              public_opt_in: userSuppliedFasta,
              license,
              built_at: builtAt,
              builder_image: "cloudflare-worker-publish",
              package_sha256: packageSha256,
            },
          }),
        },
      }),
    }
  );

  return jsonResponse(
    { status: "published", tag: permTag, package_name: packageBaseName },
    200,
    origin,
    env.ALLOWED_ORIGIN
  );
}
