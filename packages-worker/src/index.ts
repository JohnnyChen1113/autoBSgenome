interface Env {
  GITHUB_REPO?: string;
}

const DEFAULT_GITHUB_REPO = "JohnnyChen1113/autoBSgenome";

const TAG_PATTERN = /^(?:pkg-BSgenome\.[A-Za-z0-9._-]+|build-[a-f0-9]{8,32})$/;
const ASSET_PATTERN = /^BSgenome\.[A-Za-z0-9._-]+_[0-9][A-Za-z0-9._-]*\.tar\.gz$/;

function json(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data, null, 2), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "no-store",
      "X-Content-Type-Options": "nosniff",
    },
  });
}

function redirectToGitHub(url: URL, env: Env): Response {
  const segments = url.pathname.split("/").filter(Boolean);

  if (segments.length !== 2) {
    return json(
      {
        error: "Not found",
        message:
          "Use /<release-tag>/<asset.tar.gz>, for example /pkg-BSgenome.Aarxii.Ensembl.Aaoar1/BSgenome.Aarxii.Ensembl.Aaoar1_1.0.0.tar.gz",
      },
      404,
    );
  }

  const [tag, asset] = segments;
  if (!TAG_PATTERN.test(tag) || !ASSET_PATTERN.test(asset)) {
    return json(
      {
        error: "Invalid package download path",
        message:
          "Only AutoBSgenome package release assets are supported. Arbitrary redirect targets are not accepted.",
      },
      400,
    );
  }

  const githubRepo = env.GITHUB_REPO || DEFAULT_GITHUB_REPO;
  const location = `https://github.com/${githubRepo}/releases/download/${tag}/${asset}`;

  return new Response(null, {
    status: 302,
    headers: {
      Location: location,
      "Cache-Control": "public, max-age=300",
      "X-Content-Type-Options": "nosniff",
    },
  });
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

    if (url.pathname === "/" && request.method === "GET") {
      return json({
        service: "AutoBSgenome package download redirect",
        example:
          "https://packages.autobsgenome.org/pkg-BSgenome.Aarxii.Ensembl.Aaoar1/BSgenome.Aarxii.Ensembl.Aaoar1_1.0.0.tar.gz",
      });
    }

    if (request.method !== "GET" && request.method !== "HEAD") {
      return json({ error: "Method not allowed" }, 405);
    }

    return redirectToGitHub(url, env);
  },
};
