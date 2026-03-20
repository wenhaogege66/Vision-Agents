import { useCallback, useEffect, useRef, useState } from 'react';

// ── Types ────────────────────────────────────────────────────

export type OperationType =
  | 'upload_bp'
  | 'upload_text_ppt'
  | 'upload_presentation_ppt'
  | 'upload_presentation_video'
  | 'upload_presentation_audio'
  | 'profile_extract'
  | 'text_review'
  | 'offline_review'
  | 'export_pdf';

export type OperationStatus = 'idle' | 'loading' | 'success' | 'error';

export interface OperationState {
  status: OperationStatus;
  error?: string;
}

export interface UseConcurrentStateReturn {
  /** Full state map keyed by operation ID. */
  states: Record<string, OperationState>;
  /** Mark an operation as loading. */
  startOperation: (opId: string) => void;
  /** Mark an operation as successfully completed. */
  completeOperation: (opId: string) => void;
  /** Mark an operation as failed with an error message. */
  failOperation: (opId: string, error: string) => void;
  /** Get the current status of an operation (defaults to 'idle'). */
  getStatus: (opId: string) => OperationStatus;
}

// ── SessionStorage helpers ───────────────────────────────────

const STORAGE_KEY = 'concurrent_op_states';

function persistLoadingStates(states: Record<string, OperationState>): void {
  try {
    const loading: Record<string, OperationState> = {};
    for (const [key, value] of Object.entries(states)) {
      if (value.status === 'loading') {
        loading[key] = value;
      }
    }
    if (Object.keys(loading).length > 0) {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(loading));
    } else {
      sessionStorage.removeItem(STORAGE_KEY);
    }
  } catch {
    // sessionStorage may be unavailable (e.g. SSR) – silently ignore.
  }
}

function restoreLoadingStates(): Record<string, OperationState> {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    const parsed: unknown = JSON.parse(raw);
    if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) return {};
    return parsed as Record<string, OperationState>;
  } catch {
    return {};
  }
}

// ── Hook ─────────────────────────────────────────────────────

/**
 * Manages independent loading / success / error states for concurrent
 * async operations.  Persists "loading" states to `sessionStorage` so
 * they survive component unmount → remount (e.g. page navigation).
 */
export function useConcurrentState(): UseConcurrentStateReturn {
  const [states, setStates] = useState<Record<string, OperationState>>(() =>
    restoreLoadingStates(),
  );

  // Keep a ref in sync so callbacks always see the latest states without
  // needing `states` in their dependency arrays (avoids stale closures).
  const statesRef = useRef(states);
  useEffect(() => {
    statesRef.current = states;
  }, [states]);

  // Persist loading states whenever they change.
  useEffect(() => {
    persistLoadingStates(states);
  }, [states]);

  const startOperation = useCallback((opId: string) => {
    setStates((prev) => ({
      ...prev,
      [opId]: { status: 'loading' },
    }));
  }, []);

  const completeOperation = useCallback((opId: string) => {
    setStates((prev) => ({
      ...prev,
      [opId]: { status: 'success' },
    }));
  }, []);

  const failOperation = useCallback((opId: string, error: string) => {
    setStates((prev) => ({
      ...prev,
      [opId]: { status: 'error', error },
    }));
  }, []);

  const getStatus = useCallback(
    (opId: string): OperationStatus => {
      return statesRef.current[opId]?.status ?? 'idle';
    },
    [],
  );

  return { states, startOperation, completeOperation, failOperation, getStatus };
}
