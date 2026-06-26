import { siteConfig } from "@/config";

type JsonObject = Record<string, unknown>;

export type QueueInfo = {
  running: number;
  queued: number;
  runs: { id: number; status: string; name: string; created_at: string }[];
};

export type UploadSession = {
  upload_id: string;
  r2_upload_id: string;
  file_name: string;
  file_size: number;
  part_size: number;
  part_url_template: string;
  complete_url: string;
  download_url: string;
  delete_url: string;
  max_upload_bytes: number;
};

export type UploadPartResult = {
  part_number: number;
  etag: string;
};

export type BuildStartResponse = {
  job_id: string;
  delete_token?: string;
  queue_position?: number;
};

export type BuildStatusResponse = {
  status: string;
  download_url?: string;
  file_name?: string;
  file_size?: number;
  message?: string;
  error?: string;
};

async function readJson<T>(res: Response): Promise<T & { error?: string }> {
  return (await res.json().catch(() => ({}))) as T & { error?: string };
}

async function apiJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${siteConfig.apiBase}${path}`, init);
  const data = await readJson<T>(res);
  if (!res.ok) {
    throw new Error(data.error ?? `AutoBSgenome API request failed: ${path}`);
  }
  return data;
}

export function fetchQueueStatus(): Promise<QueueInfo> {
  return apiJson<QueueInfo>("/api/queue");
}

export async function createUploadSession(payload: {
  file_name: string;
  file_size: number;
  content_type: string;
}): Promise<UploadSession> {
  const session = await apiJson<UploadSession>("/api/uploads", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!session.part_url_template || !session.complete_url || !session.download_url) {
    throw new Error("Failed to create FASTA upload session");
  }
  return session;
}

export async function uploadPart(
  partUrl: string,
  body: Blob
): Promise<UploadPartResult> {
  const res = await fetch(partUrl, {
    method: "PUT",
    headers: { "Content-Type": "application/octet-stream" },
    body,
  });
  const part = await readJson<UploadPartResult>(res);
  if (!res.ok || !part.etag) {
    throw new Error(part.error ?? "FASTA upload failed");
  }
  return part;
}

export async function completeUploadSession(
  completeUrl: string,
  parts: UploadPartResult[]
): Promise<void> {
  const res = await fetch(completeUrl, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ parts }),
  });
  const data = await readJson<JsonObject>(res);
  if (!res.ok) {
    throw new Error(data.error ?? "Failed to finish FASTA upload");
  }
}

export async function startBuild(payload: JsonObject): Promise<BuildStartResponse> {
  const data = await apiJson<BuildStartResponse>("/api/build", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!data.job_id) {
    throw new Error("Failed to start build");
  }
  return data;
}

export function deleteBuild(jobId: string, deleteToken: string): Promise<void> {
  return apiJson<void>(`/api/build/${jobId}`, {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ delete_token: deleteToken }),
  });
}

export function publishBuild(payload: JsonObject): Promise<JsonObject> {
  return apiJson<JsonObject>("/api/publish", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function fetchBuildStatus(jobId: string): Promise<BuildStatusResponse> {
  return apiJson<BuildStatusResponse>(`/api/status/${jobId}`);
}
