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

    // POST /api/build — trigger a BSgenome build
    if (url.pathname === "/api/build" && request.method === "POST") {
      return handleBuild(request, env, origin);
    }

    // GET /api/status/:jobId — check build status via GitHub Release
    const statusMatch = url.pathname.match(/^\/api\/status\/([a-zA-Z0-9-]+)$/);
    if (statusMatch && request.method === "GET") {
      return handleStatus(statusMatch[1], env, origin);
    }

    return jsonResponse({ error: "Not found" }, 404, origin, env.ALLOWED_ORIGIN);
  },
};

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
    { job_id: jobId, status: "queued" },
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
  return jsonResponse(
    {
      job_id: jobId,
      status: "complete",
      package_name: release.name,
      download_url: asset?.browser_download_url ?? "",
      file_name: asset?.name ?? "",
      file_size: asset?.size ?? 0,
    },
    200,
    origin,
    env.ALLOWED_ORIGIN
  );
}
