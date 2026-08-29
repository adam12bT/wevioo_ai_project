import { useCallback, useEffect, useRef, useState } from 'react';
import { fetchJob } from '@/api/client';
import { isTerminalStatus } from '@/api/normalize';
import type { Job, JobStatus } from '@/types';

/**
 * Polls a job's state on an interval. Stops polling when the job reaches a terminal state.
 * Used as a fallback alongside SSE (useJobEvents) to prevent race conditions.
 */
export function useJob(jobId: string | undefined) {
  const [job, setJob] = useState<Job | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const statusRef = useRef<JobStatus | undefined>(undefined);

  const load = useCallback(async () => {
    if (!jobId) return;
    try {
      const data = await fetchJob(jobId);
      setJob(data);
      statusRef.current = data.status;
      setError(null);
      if (isTerminalStatus(data.status) && pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load job');
    } finally {
      setLoading(false);
    }
  }, [jobId]);

  useEffect(() => {
    if (!jobId) return;
    setLoading(true);
    load();
    pollRef.current = setInterval(load, 3000);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
      pollRef.current = null;
    };
  }, [jobId, load]);

  return { job, setJob, loading, error, refresh: load };
}
