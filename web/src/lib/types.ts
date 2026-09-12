/**
 * Espejo TypeScript de agent/src/snapflick/models/schemas.py.
 * Mantener campo a campo — es el contrato compartido agente/API/frontend.
 */

export type Confidence = "high" | "medium" | "low";

export type JobStatus = "pending" | "processing" | "done" | "failed";

export interface ProductSheet {
  name: string;
  brand: string | null;
  presentation: string | null;
  description: string;
  category: string | null;
  keywords: string[];
  ingredients: string | null;
  barcode: string | null;
  language_detected: string | null;
  confidence: Confidence;
  notes: string | null;
}

export interface ProcessedImage {
  source_path: string | null;
  cutout_path: string | null;
  composed_path: string | null;
  thumbnail_path: string | null;
  error: string | null;
}

export interface ProductRecord {
  id: string;
  sheet: ProductSheet;
  image: ProcessedImage;
  visible: boolean;
  background_key: string | null;
  created_at: string;
}

export interface CategoryAssignment {
  product_id: string;
  category: string;
  reason: string;
}

export interface CatalogPlan {
  categories: string[];
  assignments: CategoryAssignment[];
  catalog_title: string;
  catalog_summary: string;
}

export interface Job {
  id: string;
  status: JobStatus;
  background_key: string | null;
  total_images: number;
  processed_images: number;
  products: ProductRecord[];
  plan: CatalogPlan | null;
  catalog_html_path: string | null;
  catalog_json_path: string | null;
  catalog_pdf_path: string | null;
  errors: string[];
  created_at: string;
}

export interface JobSummary {
  id: string;
  status: JobStatus;
  products: number;
  created_at: string;
  catalog_title: string | null;
  catalog_html_path: string | null;
  thumbnail_url: string | null;
}

export interface BackgroundOption {
  background_key: string;
  url: string;
  is_default: boolean;
}

export interface AgentSettings {
  product_rules: string;
  catalog_rules: string;
}

/** Espejo de `PublicCatalogProduct`/`PublicCatalog` en main.py — el
 * subconjunto de `Job`/`ProductRecord` que ve un visitante anónimo en
 * /c/[jobId], sin productos ocultos ni campos internos (session_id, errors,
 * paths de filesystem). */
export interface PublicCatalogProduct {
  id: string;
  name: string;
  brand: string | null;
  presentation: string | null;
  description: string;
  keywords: string[];
  category: string;
  image_url: string | null;
}

export interface PublicCatalog {
  id: string;
  catalog_title: string;
  catalog_summary: string;
  categories: string[];
  products: PublicCatalogProduct[];
}
