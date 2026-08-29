import { useEffect, useRef } from 'react';
import { API } from '@/api/urls';
import { isTerminalStatus, normalizeStatus } from '@/api/normalize';
import type { Job } from '@/types';

/**
 * Subscribes to Server-Sent Events for a job and merges updates into the job state.
 * Closes the EventSource when the job reaches a terminal state or the component unmounts.
 */
export function useJobEvents(
  jobId: string | undefined,
  onUpdate: (job: Job) => void,
  onTerminal: () => void,
) {
  const sourceRef = useRef<EventSource | null>(null);
  // Keep latest callbacks without re-opening the connection
  const updateRef = useRef(onUpdate);
  const terminalRef = useRef(onTerminal);
  updateRef.current = onUpdate;
  terminalRef.current = onTerminal;

  useEffect(() => {
    if (!jobId) return;

    const url = API.jobEvents(jobId);
    let source: EventSource;
    try {
      source = new EventSource(url);
    } catch {
      return;
    }
    sourceRef.current = source;

    const handleData = (raw: unknown) => {
      if (!raw) return;
      try {
        let data: Record<string, unknown>;
        if (typeof raw === 'string') {
          data = JSON.parse(raw);
        } else {
          data = raw as Record<string, unknown>;
        }
        // Event payloads may wrap the job under "job" or be the job itself
        const jobData = (data.job as Record<string, unknown>) || data;
        // Worker events are partial job updates. Do not normalize them into a
        // complete job here, otherwise absent fields overwrite polled state.
        updateRef.current(jobData as Job);
        const status = normalizeStatus(jobData.status);
        if (status && isTerminalStatus(status)) {
          source.close();
          sourceRef.current = null;
          terminalRef.current();
        }
      } catch {
        // Ignore malformed event payloads — polling is the fallback
      }
    };

    const eventTypes = ['queued', 'submitting', 'pipeline', 'progress', 'stage', 'evaluation', 'complete', 'failed'];
    eventTypes.forEach((type) => {
      source.addEventListener(type, (e: MessageEvent) => handleData(e.data));
    });
    // Generic message fallback
    source.addEventListener('message', (e: MessageEvent) => handleData(e.data));

    source.addEventListener('error', () => {
      // SSE can drop; polling (useJob) is the safety net. Reconnect after a delay.
      source.close();
      sourceRef.current = null;
    });

    return () => {
      source.close();
      sourceRef.current = null;
    };
  }, [jobId]);
}
