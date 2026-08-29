import { useCallback, useEffect, useState } from 'react';
import { fetchKnowledgeDocuments } from '@/api/client';

export interface KnowledgeDoc {
  id: string;
  name: string;
  category: string;
  size?: number;
  created_at?: string;
  status?: string;
}

export function useKnowledge() {
  const [documents, setDocuments] = useState<KnowledgeDoc[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await fetchKnowledgeDocuments();
      setDocuments(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load knowledge base');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return { documents, loading, error, refresh: load };
}
