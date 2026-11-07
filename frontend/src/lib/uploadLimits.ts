/** Largest audio upload the backend accepts. Mirrors MAX_AUDIO_BYTES in
 * backend/app/routes/scan.py, which sits under the host's ~4.5 MB request cap:
 * a body over that cap is refused at the edge without CORS headers, so the
 * browser would report only "Failed to fetch". Checked here before sending. */
export const MAX_AUDIO_BYTES = 4 * 1024 * 1024;

export function audioTooLarge(size: number): boolean {
  return size > MAX_AUDIO_BYTES;
}
