export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

export type Health = { status: string };

export async function fetchHealth(signal?: AbortSignal): Promise<Health> {
  const res = await fetch(`${API_URL}/healthz`, { signal });
  if (!res.ok) throw new Error(`healthz returned ${res.status}`);
  return (await res.json()) as Health;
}
