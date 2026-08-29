import { useCallback, useEffect, useState } from 'react';
import { fetchEvaluation } from '@/api/client';
import type { Evaluation } from '@/types';

export function useEvaluation(jobId: string | undefined) {
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!jobId) return;
    setLoading(true);
    try {
      const data = await fetchEvaluation(jobId);
      setEvaluation(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load evaluation');
    } finally {
      setLoading(false);
    }
  }, [jobId]);

  useEffect(() => {
    load();
  }, [load]);

  return { evaluation, loading, error, refresh: load };
}
