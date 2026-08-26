import type { BackgroundOption, Job, JobSummary } from "./types";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";

/** Une una URL relativa devuelta por el backend (p.ej. `/files/...`) con API_URL. */
export function absoluteUrl(path: string | null | undefined): string | null {
  if (!path) return null;
  if (path.startsWith("http://") || path.startsWith("https://")) return path;
  return `${API_URL}${path}`;
}

async function asJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}: ${body}`);
  }
  return res.json() as Promise<T>;
}

export async function listJobs(): Promise<JobSummary[]> {
  const res = await fetch(`${API_URL}/jobs`);
  return asJson(res);
}

export async function getJob(id: string): Promise<Job> {
  const res = await fetch(`${API_URL}/jobs/${id}`);
  return asJson(res);
}

export interface CreateJobInput {
  files: File[];
  backgroundFile?: File | null;
  backgroundKey?: string | null;
}

export async function createJob({ files, backgroundFile, backgroundKey }: CreateJobInput): Promise<Job> {
  const form = new FormData();
  for (const file of files) form.append("files", file);
  if (backgroundFile) form.append("background", backgroundFile);
  if (backgroundKey) form.append("background_key", backgroundKey);

  const res = await fetch(`${API_URL}/jobs`, { method: "POST", body: form });
  return asJson(res);
}

export async function listBackgrounds(): Promise<BackgroundOption[]> {
  const res = await fetch(`${API_URL}/backgrounds`);
  return asJson(res);
}

export async function uploadBackground(file: File): Promise<BackgroundOption> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_URL}/backgrounds`, { method: "POST", body: form });
  return asJson(res);
}
