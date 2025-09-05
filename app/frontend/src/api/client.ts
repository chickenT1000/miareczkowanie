/**
 * API client for interacting with the backend.
 * Provides functions for health checks and data computation.
 */

/**
 * Get the health status of the backend API.
 * @returns The health status response.
 */
export async function getHealth(): Promise<any> {
  const response = await fetch('/api/health');
  return response.json();
}

/**
 * Send data to the backend for computation.
 * @param data FormData or object containing the data to compute.
 * @returns The computation results.
 */
export async function compute(data: FormData | object): Promise<any> {
  // TODO: Implement actual computation API call
  // Should POST to /api/compute with the provided data
  console.log('Compute called with:', data);
  return null;
}
