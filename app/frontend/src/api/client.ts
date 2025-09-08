/**
 * API client for interacting with the backend.
 * Provides functions for health checks and data computation.
 */

/* ---------------------------------------------------------------------------
 *  Types (subset of backend pydantic models, enough for Phase 1 UI)
 * ------------------------------------------------------------------------- */

export interface ImportResponse {
  columns: string[];
  rows: Record<string, number | string>[];
  time_unit: string;
  decimal_separator: string;
  column_separator: string;
}

export interface ColumnMapping {
  ph: string;
  time: string;
  pump_flow?: string | null;
  naoh_conc?: string | null;
}

export interface ComputeSettings {
  c_b: number;
  q: number;
  v0: number;
  t: number;
  ph_cutoff: number;
  start_index: number;
  /** If provided, use this fixed total sulfate concentration instead of estimating it */
  c_a_known?: number | null;
  /** Ignore rows with pH below this value when estimating C_A (only if c_a_known is null) */
  ph_ignore_below?: number | null;
  column_mapping: ColumnMapping;
  rows: Record<string, number | string>[];
}

export interface ProcessedRow {
  time: number;
  ph: number;
  v_b: number;
  n_b: number;
  b_meas: number;
  na: number;
  b_model: number;
  delta_b: number;
  d_delta_b_d_ph: number;
}

export interface ModelData {
  ph: number[];
  b_model: number[];
  /** Optional standalone model curve up to pH ≈ 7 (or backend limit) */
  ph_model?: number[];
  /** Corresponding base values for the standalone model curve */
  b_model_curve?: number[];
  /** Model base values evaluated at the same pH as each measurement */
  b_model_ph_aligned?: (number | null)[];
  /** ΔB computed using pH-aligned model values */
  delta_b_ph_aligned?: (number | null)[];
}

export interface Peak {
  peak_id: number;
  ph_start: number;
  ph_apex: number;
  ph_end: number;
  delta_b_step: number;
  // optional assignment fields omitted for brevity
}

export interface ComputeResponse {
  processed_table: ProcessedRow[];
  model_data: ModelData;
  peaks: Peak[];
  c_a: number;
}

/**
 * Get the health status of the backend API.
 * @returns The health status response.
 */
export async function getHealth(): Promise<any> {
  const response = await fetch('/api/health');
  return response.json();
}

/**
 * Upload a CSV file to the backend import endpoint.
 * @param file CSV file selected by the user.
 * @returns Parsed columns and sample rows detected by the backend.
 */
export async function uploadCsv(file: File): Promise<ImportResponse> {
  const form = new FormData();
  form.append('file', file, file.name);

  const res = await fetch('/api/import', {
    method: 'POST',
    body: form,
  });

  if (!res.ok) {
    throw new Error(`Import failed: ${await res.text()}`);
  }

  return res.json() as Promise<ImportResponse>;
}

/**
 * Send computation settings to the backend and receive processed data.
 * @param settings Configuration + raw rows/mapping.
 * @returns Complete computation response.
 */
export async function compute(
  settings: ComputeSettings,
): Promise<ComputeResponse> {
  const res = await fetch('/api/compute', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(settings),
  });

  if (!res.ok) {
    throw new Error(`Compute failed: ${await res.text()}`);
  }

  return res.json() as Promise<ComputeResponse>;
}

/* ---------------------------------------------------------------------------
 *  Export helpers
 * ------------------------------------------------------------------------- */

export interface ExportResponse {
  filename: string;
  content_type: string;
  // The backend returns either a CSV string or a JSON-serialisable object.
  data: any;
}

/**
 * Export data (processed table, peaks, or full session) from the backend.
 *
 * @param format    'csv' or 'json'
 * @param dataType  'processed' | 'peaks' | 'session'
 * @returns         Object containing filename suggestion, MIME type and payload
 */
export async function exportData(
  format: 'csv' | 'json',
  dataType: 'processed' | 'peaks' | 'session',
): Promise<ExportResponse> {
  const body = {
    format,
    data_type: dataType,
    include_plots: false,
  };

  const res = await fetch('/api/export', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    throw new Error(`Export failed: ${await res.text()}`);
  }

  return res.json() as Promise<ExportResponse>;
}
