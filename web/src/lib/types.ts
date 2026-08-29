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
  errors: string[];
  created_at: string;
}

export interface JobSummary {
  id: string;
  status: JobStatus;
  products: number;
  created_at: string;
}

export interface BackgroundOption {
  background_key: string;
  url: string;
}
