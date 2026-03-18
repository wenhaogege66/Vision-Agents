import { useCallback, useEffect, useRef, useState } from 'react';

import { materialApi } from '@/services/api';
import type { MaterialStatusResponse } from '@/types';

/** Maximum polling duration in milliseconds (5 minutes). */
const POLL_TIMEOUT_MS = 5 * 60 * 1000;
/** Polling interval in milliseconds (5 seconds). */
const POLL_INTERVAL_MS = 5 * 1000;

export interface UseReadinessCheckerReturn {
  /** Current material status, `null` until the first fetch completes. */
  status: MaterialStatusResponse | null;
  /** `true` while a fetch is in-flight. */
  loading: boolean;
  /** Manually re-fetch the material status. */
  refresh: () => void;
}

/**
 * Checks and tracks the readiness of project materials.
 *
 * - Fetches material status on mount.
 * - Polls every 5 s while any PPT material is uploaded but not yet converted.
 * - Stops polling once conversion completes or after 5 minutes.
 * - Cleans up all timers on unmount.
 */
export function useReadinessChecker(
  projectId: string,
): UseReadinessCheckerReturn {
  const [status, setStatus] = useState<MaterialStatusResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  // Refs to manage polling lifecycle across renders.
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef<boolean>(true);
  const pollingStartRef = useRef<number | null>(null);

  /** Stop all polling timers. */
  const stopPolling = useCallback(() => {
    if (intervalRef.current !== null) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    if (timeoutRef.current !== null) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
    pollingStartRef.current = null;
  }, []);

  /** Returns `true` when at least one PPT is uploaded but not yet converted. */
  const needsPolling = useCallback(
    (s: MaterialStatusResponse): boolean =>
      (s.text_ppt.uploaded && s.text_ppt.image_paths_ready === false) ||
      (s.presentation_ppt.uploaded &&
        s.presentation_ppt.image_paths_ready === false),
    [],
  );

  /** Fetch material status from the API. */
  const fetchStatus = useCallback(async () => {
    try {
      const data = await materialApi.status(projectId);
      if (!mountedRef.current) return;
      setStatus(data);
      return data;
    } catch {
      // On error we simply keep the previous status.
      return undefined;
    }
  }, [projectId]);

  /** Start polling if conversion is still pending. */
  const startPolling = useCallback(
    (currentStatus: MaterialStatusResponse) => {
      // Already polling or no need to poll – bail out.
      if (intervalRef.current !== null || !needsPolling(currentStatus)) return;

      pollingStartRef.current = Date.now();

      intervalRef.current = setInterval(async () => {
        // Check timeout before fetching.
        if (
          pollingStartRef.current !== null &&
          Date.now() - pollingStartRef.current >= POLL_TIMEOUT_MS
        ) {
          stopPolling();
          return;
        }

        const data = await fetchStatus();
        if (!mountedRef.current) {
          stopPolling();
          return;
        }

        if (data && !needsPolling(data)) {
          stopPolling();
        }
      }, POLL_INTERVAL_MS);

      // Safety-net timeout: forcefully stop after 5 minutes.
      timeoutRef.current = setTimeout(() => {
        stopPolling();
      }, POLL_TIMEOUT_MS);
    },
    [fetchStatus, needsPolling, stopPolling],
  );

  /** Public refresh – re-fetch and (re-)evaluate polling. */
  const refresh = useCallback(() => {
    setLoading(true);
    stopPolling();
    fetchStatus().then((data) => {
      if (!mountedRef.current) return;
      setLoading(false);
      if (data && needsPolling(data)) {
        startPolling(data);
      }
    });
  }, [fetchStatus, needsPolling, startPolling, stopPolling]);

  // Initial fetch on mount / when projectId changes.
  useEffect(() => {
    mountedRef.current = true;
    setLoading(true);

    fetchStatus().then((data) => {
      if (!mountedRef.current) return;
      setLoading(false);
      if (data && needsPolling(data)) {
        startPolling(data);
      }
    });

    return () => {
      mountedRef.current = false;
      stopPolling();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  return { status, loading, refresh };
}
