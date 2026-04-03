interface Env {
  GITHUB_PAT: string;
  GITHUB_REPO: string;
  ALLOWED_ORIGIN: string;
}

function corsHeaders(origin: string, allowedOrigin: string): HeadersInit {
  // Allow localhost for development
  const isAllowed =
    origin === allowedOrigin ||
    origin.endsWith(".autobsgenome.pages.dev") ||
    origin.startsWith("http://localhost:");

  return {
    "Access-Control-Allow-Origin": isAllowed ? origin : allowedOrigin,
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
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

const MAX_QUEUE_SIZE = 5;

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
      { error: "Failed to trigger build", details: errText },
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
    },
    200,
    origin,
    env.ALLOWED_ORIGIN
  );
}

async function handleStatus(
  jobId: string,
  env: Env,
  origin: string
): Promise<Response> {
  const tag = `build-${jobId}`;

  // Check if a release with this tag exists
  const ghResponse = await fetch(
    `https://api.github.com/repos/${env.GITHUB_REPO}/releases/tags/${tag}`,
    {
      headers: {
        Authorization: `Bearer ${env.GITHUB_PAT}`,
        Accept: "application/vnd.github+json",
        "User-Agent": "AutoBSgenome-Worker",
        "X-GitHub-Api-Version": "2022-11-28",
      },
    }
  );

  if (ghResponse.status === 404) {
    // Release doesn't exist yet — still building
    return jsonResponse(
      { job_id: jobId, status: "building" },
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
    return jsonResponse(
      { job_id: jobId, status: "failed", message: release.body },
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
    {
      headers: {
        Authorization: `Bearer ${env.GITHUB_PAT}`,
        Accept: "application/vnd.github+json",
        "User-Agent": "AutoBSgenome-Worker",
      },
    }
  );
  const published = permCheck.status === 200;

  return jsonResponse(
    {
      job_id: jobId,
      status: "complete",
      package_name: release.name,
      download_url: asset?.browser_download_url ?? "",
      file_name: asset?.name ?? "",
      file_size: asset?.size ?? 0,
      published,
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

  const meta = body.metadata ?? {};
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
          `| **Version** | ${meta.version ?? "1.0.0"} |`,
          `| **Package** | \`${packageBaseName}\` |`,
          "",
          "**Install in R:**",
          "```r",
          `install.packages("${packageBaseName}", repos = "https://johnnychen1113.github.io/autoBSgenome")`,
          "```",
          "",
          `> Browse all packages: [autobsgenome.pages.dev](https://autobsgenome.pages.dev) | [Package repository](https://johnnychen1113.github.io/autoBSgenome)`,
          "",
          "Published via [AutoBSgenome Web](https://autobsgenome.pages.dev).",
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
          file_name: asset.name,
          file_size: String(asset.size),
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
