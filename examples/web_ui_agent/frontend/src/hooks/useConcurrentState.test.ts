import { describe, it, expect, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';

import { useConcurrentState } from './useConcurrentState';

// ── Helpers ──────────────────────────────────────────────────

const STORAGE_KEY = 'concurrent_op_states';

beforeEach(() => {
  sessionStorage.clear();
});

// ── Unit Tests ───────────────────────────────────────────────

describe('useConcurrentState', () => {
  it('returns idle for unknown operations', () => {
    const { result } = renderHook(() => useConcurrentState());
    expect(result.current.getStatus('upload_bp')).toBe('idle');
  });

  it('transitions through the full lifecycle: idle → loading → success', () => {
    const { result } = renderHook(() => useConcurrentState());

    act(() => result.current.startOperation('upload_bp'));
    expect(result.current.getStatus('upload_bp')).toBe('loading');

    act(() => result.current.completeOperation('upload_bp'));
    expect(result.current.getStatus('upload_bp')).toBe('success');
  });

  it('transitions through the error path: idle → loading → error', () => {
    const { result } = renderHook(() => useConcurrentState());

    act(() => result.current.startOperation('text_review'));
    expect(result.current.getStatus('text_review')).toBe('loading');

    act(() => result.current.failOperation('text_review', 'timeout'));
    expect(result.current.getStatus('text_review')).toBe('error');
    expect(result.current.states['text_review'].error).toBe('timeout');
  });

  it('maintains independent states for concurrent operations', () => {
    const { result } = renderHook(() => useConcurrentState());

    act(() => {
      result.current.startOperation('upload_bp');
      result.current.startOperation('upload_text_ppt');
    });

    // Complete one, the other stays loading
    act(() => result.current.completeOperation('upload_bp'));

    expect(result.current.getStatus('upload_bp')).toBe('success');
    expect(result.current.getStatus('upload_text_ppt')).toBe('loading');
  });

  it('persists loading states to sessionStorage', () => {
    const { result } = renderHook(() => useConcurrentState());

    act(() => result.current.startOperation('profile_extract'));

    const stored = JSON.parse(sessionStorage.getItem(STORAGE_KEY) ?? '{}');
    expect(stored['profile_extract']).toEqual({ status: 'loading' });
  });

  it('removes sessionStorage entry when no operations are loading', () => {
    const { result } = renderHook(() => useConcurrentState());

    act(() => result.current.startOperation('export_pdf'));
    expect(sessionStorage.getItem(STORAGE_KEY)).not.toBeNull();

    act(() => result.current.completeOperation('export_pdf'));
    expect(sessionStorage.getItem(STORAGE_KEY)).toBeNull();
  });

  it('restores loading states from sessionStorage on mount', () => {
    // Simulate a previous session that left a loading state
    sessionStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ offline_review: { status: 'loading' } }),
    );

    const { result } = renderHook(() => useConcurrentState());
    expect(result.current.getStatus('offline_review')).toBe('loading');
  });
});
