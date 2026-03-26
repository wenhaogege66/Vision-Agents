import { useCallback, useEffect, useRef, useState } from 'react';

import { materialApi } from '@/services/api';
import type { MaterialStatusResponse } from '@/types';

export interface UseReadinessCheckerReturn {
  /** Current material status, `null` until the first fetch completes. */
  status: MaterialStatusResponse | null;
  /** `true` while a fetch is in-flight. */
  loading: boolean;
  /** Manually re-fetch the material status. */
  refresh: () => void;
}

/**
 * Checks the readiness of project materials.
 *
 * Fetches material status on mount and exposes a manual refresh.
 */
export function useReadinessChecker(
  projectId: string,
): UseReadinessCheckerReturn {
  const [status, setStatus] = useState<MaterialStatusResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const mountedRef = useRef<boolean>(true);

  /** Fetch material status from the API. */
  const fetchStatus = useCallback(async () => {
    try {
      const data = await materialApi.status(projectId);
      if (!mountedRef.current) return;
      setStatus(data);
    } catch {
      // On error we simply keep the previous status.
    }
  }, [projectId]);

  /** Public refresh. */
  const refresh = useCallback(() => {
    setLoading(true);
    fetchStatus().then(() => {
      if (mountedRef.current) setLoading(false);
    });
  }, [fetchStatus]);

  // Initial fetch on mount / when projectId changes.
  useEffect(() => {
    mountedRef.current = true;
    setLoading(true);

    fetchStatus().then(() => {
      if (mountedRef.current) setLoading(false);
    });

    return () => {
      mountedRef.current = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  return { status, loading, refresh };
}
