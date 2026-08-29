import { useCallback, useEffect, useState } from 'react';
import { fetchVersions } from '@/api/client';
import type { DocumentVersion } from '@/types';

export function useVersions(jobId: string | undefined) {
  const [versions, setVersions] = useState<DocumentVersion[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!jobId) return;
    setLoading(true);
    try {
      const data = await fetchVersions(jobId);
      setVersions(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load versions');
    } finally {
      setLoading(false);
    }
  }, [jobId]);

  useEffect(() => {
    load();
  }, [load]);

  return { versions, loading, error, refresh: load };
}
