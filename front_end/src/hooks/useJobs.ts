import { useCallback, useEffect, useRef, useState } from 'react';
import { fetchJob, fetchJobs } from '@/api/client';
import { isTerminalStatus } from '@/api/normalize';
import type { Job } from '@/types';

export function useJobs(hydrateTerminalJobs = false) {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const detailCacheRef = useRef<Map<string, Job>>(new Map());

  const load = useCallback(async () => {
    try {
      const summaries = await fetchJobs();
      const data = hydrateTerminalJobs
        ? await Promise.all(
            summaries.map(async (summary) => {
              if (!summary.job_id || !isTerminalStatus(summary.status)) return summary;
              const cacheKey = `${summary.job_id}:${summary.updated_at || ''}`;
              const cached = detailCacheRef.current.get(cacheKey);
              if (cached) return cached;
              try {
                const detail = await fetchJob(summary.job_id);
                detailCacheRef.current.set(cacheKey, detail);
                return detail;
              } catch {
                // Keep the summary visible if a detail request fails temporarily.
                return summary;
              }
            }),
          )
        : summaries;
      setJobs(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load jobs');
    } finally {
      setLoading(false);
    }
  }, [hydrateTerminalJobs]);

  useEffect(() => {
    load();
    timerRef.current = setTimeout(function poll() {
      load();
      timerRef.current = setTimeout(poll, 10000);
    }, 10000);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [load]);

  return { jobs, loading, error, refresh: load };
}
