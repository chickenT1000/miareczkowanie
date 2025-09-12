/**
 * API client for Sankey diagram functionality.
 * Provides types and functions for interacting with the Sankey backend.
 */

/* ---------------------------------------------------------------------------
 *  Types (matching backend Pydantic models)
 * ------------------------------------------------------------------------- */

export interface Meta {
  version: number;
  units: { mass: string };
  notes?: string;
  batch_target_kg?: number;
}

export interface Node {
  id: string;
  label: string;
  type: "machine" | "stream" | "product";
  tags?: string[];
}

export interface Link {
  id: string;
  from: string;
  to: string;
  measured_kg?: number;
  scaled_kg?: number;
  percent_of_parent?: number;
  trial_id?: string;
  notes?: string;
}

export interface Graph {
  meta: Meta;
  nodes: Node[];
  links: Link[];
  sources: string[];
  sinks: string[];
}

export interface ScaleRequest {
  batch_target_kg: number;
  strategy: "global" | "per-node";
}

/* ---------------------------------------------------------------------------
 *  API Functions
 * ------------------------------------------------------------------------- */

/**
 * Get the current Sankey graph from the backend.
 * @returns The current graph or default if none exists.
 */
export async function getGraph(): Promise<Graph> {
  const response = await fetch('/api/sankey/graph');
  
  if (!response.ok) {
    throw new Error(`Failed to get graph: ${await response.text()}`);
  }
  
  return response.json() as Promise<Graph>;
}

/**
 * Set the current Sankey graph on the backend.
 * @param graph The graph to set
 * @returns The normalized graph after processing
 */
export async function setGraph(graph: Graph): Promise<Graph> {
  const response = await fetch('/api/sankey/graph', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(graph),
  });
  
  if (!response.ok) {
    throw new Error(`Failed to set graph: ${await response.text()}`);
  }
  
  return response.json() as Promise<Graph>;
}

/**
 * Scale the current graph based on target batch size.
 * @param batchTargetKg The target batch size in kg
 * @param strategy The scaling strategy ("global" or "per-node")
 * @returns The scaled graph
 */
export async function scaleGraph(
  batchTargetKg: number,
  strategy: "global" | "per-node" = "global"
): Promise<Graph> {
  const request: ScaleRequest = {
    batch_target_kg: batchTargetKg,
    strategy,
  };
  
  const response = await fetch('/api/sankey/scale', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });
  
  if (!response.ok) {
    throw new Error(`Failed to scale graph: ${await response.text()}`);
  }
  
  return response.json() as Promise<Graph>;
}

/**
 * Import graph data from JSON or CSV.
 * @param fileContent The content of the file as a string
 * @param fileType The type of file ("json" or "csv")
 * @returns The imported and normalized graph
 */
export async function importData(
  fileContent: string,
  fileType: "json" | "csv" = "json"
): Promise<Graph> {
  const response = await fetch('/api/sankey/import', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      file_content: fileContent,
      file_type: fileType,
    }),
  });
  
  if (!response.ok) {
    throw new Error(`Import failed: ${await response.text()}`);
  }
  
  return response.json() as Promise<Graph>;
}

/**
 * Helper to download graph as a file
 * @param graph The graph to download
 * @param filename The filename to suggest
 */
export function downloadGraph(graph: Graph, filename: string = "sankey_graph.json"): void {
  const blob = new Blob([JSON.stringify(graph, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
