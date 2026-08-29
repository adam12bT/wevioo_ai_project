import { SPACE_WAKE_URLS } from '@/api/urls';

let wakeStarted = false;

/**
 * Fire one simple browser request at every hosted backend when the UI opens.
 * `no-cors` is intentional: the response body is irrelevant; reaching the
 * Hugging Face proxy is enough to start a sleeping Space.
 */
export function wakeHostedSpaces(): void {
  if (wakeStarted) return;
  wakeStarted = true;

  for (const root of SPACE_WAKE_URLS) {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 15_000);
    const wakeUrl = new URL(root);
    wakeUrl.searchParams.set('wake', String(Date.now()));

    void fetch(wakeUrl.toString(), {
      method: 'GET',
      mode: 'no-cors',
      cache: 'no-store',
      keepalive: true,
      signal: controller.signal,
    })
      .catch(() => {
        // A sleeping Space may close or time out the first request while it
        // starts. The request still served its purpose by triggering wake-up.
      })
      .finally(() => window.clearTimeout(timeout));
  }
}
