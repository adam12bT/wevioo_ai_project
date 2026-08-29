import { useCallback, useEffect, useRef, useState } from 'react';
import { fetchHealth } from '@/api/client';
import type { HealthResponse } from '@/types';

export function useHealth(autoRefresh = true, intervalMs = 30000) {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await fetchHealth();
      setHealth(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load health');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    if (autoRefresh) {
      timerRef.current = setInterval(load, intervalMs);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [load, autoRefresh, intervalMs]);

  return { health, loading, error, refresh: load };
}
