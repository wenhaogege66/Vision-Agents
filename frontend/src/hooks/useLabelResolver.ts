import {
  createContext,
  createElement,
  useCallback,
  useContext,
  useEffect,
  useState,
} from 'react';
import type { ReactNode } from 'react';

import { competitionApi } from '@/services/api';
import type { NameMappings } from '@/types';

// ── Context ──────────────────────────────────────────────────

interface LabelResolverContextValue {
  mappings: NameMappings | null;
  loading: boolean;
}

export const LabelResolverContext = createContext<LabelResolverContextValue>({
  mappings: null,
  loading: true,
});

// ── Provider ─────────────────────────────────────────────────

interface LabelResolverProviderProps {
  children: ReactNode;
}

/**
 * Fetches name mappings on mount and caches them in context so every
 * descendant can resolve competition / track / group IDs to Chinese labels
 * without triggering additional requests.
 */
export function LabelResolverProvider({ children }: LabelResolverProviderProps) {
  const [mappings, setMappings] = useState<NameMappings | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    let cancelled = false;

    competitionApi
      .nameMappings()
      .then((data) => {
        if (!cancelled) {
          setMappings(data);
          setLoading(false);
        }
      })
      .catch(() => {
        // On failure we stop loading but leave mappings null –
        // resolve() will gracefully fall back to the raw ID.
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return createElement(
    LabelResolverContext.Provider,
    { value: { mappings, loading } },
    children,
  );
}

// ── Hook ─────────────────────────────────────────────────────

export interface UseLabelResolverReturn {
  /**
   * Resolve an English ID to its Chinese label.
   * Falls back to the raw `id` when the mapping is unavailable or missing.
   */
  resolve: (type: 'competition' | 'track' | 'group', id: string) => string;
  /** `true` while the name mappings are being fetched. */
  loading: boolean;
}

const TYPE_TO_KEY: Record<'competition' | 'track' | 'group', keyof NameMappings> = {
  competition: 'competitions',
  track: 'tracks',
  group: 'groups',
};

/**
 * Returns a `resolve` function that maps English IDs to Chinese labels
 * using the cached name mappings from `LabelResolverContext`.
 */
export function useLabelResolver(): UseLabelResolverReturn {
  const { mappings, loading } = useContext(LabelResolverContext);

  const resolve = useCallback(
    (type: 'competition' | 'track' | 'group', id: string): string => {
      if (!mappings) return id;
      const dict = mappings[TYPE_TO_KEY[type]];
      return dict[id] ?? id;
    },
    [mappings],
  );

  return { resolve, loading };
}
