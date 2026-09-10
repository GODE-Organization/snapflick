import type { BackgroundOption, Job, ProductSheet } from "./types";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";
export const WS_URL = API_URL.replace(/^http/, "ws");

/** Sentinel de `background_key` para "no tocar el fondo de la foto tal como
 * se subió" — espejo de `KEEP_ORIGINAL_BACKGROUND` en `pipeline.py`. */
export const KEEP_ORIGINAL_BACKGROUND = "__original__";

/** Sentinel de `background_key` para "blanco, elegido explícitamente" —
 * espejo de `EXPLICIT_WHITE_BACKGROUND` en `main.py`. Se necesita porque
 * `null`/ausente ahora cae de vuelta al fondo marcado como "Por defecto"
 * (ver `PUT /backgrounds/default`); sin este sentinel, un click en "Blanco"
 * no se podría distinguir de "no elegí nada". */
export const EXPLICIT_WHITE_BACKGROUND = "__white__";

/** Une una URL relativa devuelta por el backend (p.ej. `/files/...`) con API_URL. */
export function absoluteUrl(path: string | null | undefined): string | null {
  if (!path) return null;
  if (path.startsWith("http://") || path.startsWith("https://")) return path;
  return `${API_URL}${path}`;
}

/** La sesión anónima (`sf_session`) viaja como cookie cross-origin (web y agent
 * corren en orígenes distintos) — sin esto el navegador ni la manda ni la guarda. */
const WITH_SESSION: RequestInit = { credentials: "include" };

async function asJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}: ${body}`);
  }
  return res.json() as Promise<T>;
}

export interface CreateJobInput {
  files: File[];
  backgroundFile?: File | null;
  backgroundKey?: string | null;
  /** Fondo por foto (mismo orden que `files`); `null`/ausente = usa el fondo por defecto. */
  backgroundKeys?: (string | null)[];
}

export async function createJob({
  files,
  backgroundFile,
  backgroundKey,
  backgroundKeys,
}: CreateJobInput): Promise<Job> {
  const form = new FormData();
  for (const file of files) form.append("files", file);
  if (backgroundFile) form.append("background", backgroundFile);
  if (backgroundKey) form.append("background_key", backgroundKey);
  if (backgroundKeys?.some((k) => k)) form.append("background_keys", JSON.stringify(backgroundKeys));

  const res = await fetch(`${API_URL}/jobs`, { ...WITH_SESSION, method: "POST", body: form });
  return asJson(res);
}

export async function updateProduct(
  jobId: string,
  productId: string,
  patch: Partial<ProductSheet> & { visible?: boolean },
): Promise<Job> {
  const res = await fetch(`${API_URL}/jobs/${jobId}/products/${productId}`, {
    ...WITH_SESSION,
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  return asJson(res);
}

export async function addProduct(jobId: string, file: File, backgroundKey?: string | null): Promise<Job> {
  const form = new FormData();
  form.append("file", file);
  if (backgroundKey) form.append("background_key", backgroundKey);
  const res = await fetch(`${API_URL}/jobs/${jobId}/products`, {
    ...WITH_SESSION,
    method: "POST",
    body: form,
  });
  return asJson(res);
}

export async function deleteProduct(jobId: string, productId: string): Promise<Job> {
  const res = await fetch(`${API_URL}/jobs/${jobId}/products/${productId}`, {
    ...WITH_SESSION,
    method: "DELETE",
  });
  return asJson(res);
}

export async function updateProductBackground(
  jobId: string,
  productId: string,
  backgroundKey: string | null,
): Promise<Job> {
  const res = await fetch(`${API_URL}/jobs/${jobId}/products/${productId}/background`, {
    ...WITH_SESSION,
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ background_key: backgroundKey }),
  });
  return asJson(res);
}

export interface CatalogMetaPatch {
  catalog_title?: string;
  catalog_summary?: string;
}

export async function updateCatalog(jobId: string, patch: CatalogMetaPatch): Promise<Job> {
  const res = await fetch(`${API_URL}/jobs/${jobId}`, {
    ...WITH_SESSION,
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  return asJson(res);
}

export async function deleteJob(jobId: string): Promise<void> {
  const res = await fetch(`${API_URL}/jobs/${jobId}`, { ...WITH_SESSION, method: "DELETE" });
  await asJson(res);
}

export async function listBackgrounds(): Promise<BackgroundOption[]> {
  const res = await fetch(`${API_URL}/backgrounds`, WITH_SESSION);
  return asJson(res);
}

export async function uploadBackground(file: File): Promise<BackgroundOption> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_URL}/backgrounds`, { ...WITH_SESSION, method: "POST", body: form });
  return asJson(res);
}

export async function deleteBackground(backgroundKey: string): Promise<void> {
  const res = await fetch(`${API_URL}/backgrounds/${encodeURIComponent(backgroundKey)}`, {
    ...WITH_SESSION,
    method: "DELETE",
  });
  await asJson(res);
}

export async function setDefaultBackground(
  backgroundKey: string | null,
): Promise<{ default_background_key: string | null }> {
  const res = await fetch(`${API_URL}/backgrounds/default`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ background_key: backgroundKey }),
  });
  return asJson(res);
}
