// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, render, screen } from '@testing-library/react';
import { SLOW_REQUEST_MS, apiFetch, isServerSlow } from './api';
import { useServerWaking } from './useServerWaking';
import { WakingBanner } from '../components/Feedback';

function Banner() {
  return <WakingBanner show={useServerWaking()} />;
}

// fetch that answers only when the test calls the returned function.
function slowFetch() {
  const pending = [];
  vi.stubGlobal('fetch', vi.fn(() => new Promise((resolve) => pending.push(resolve))));
  return () => pending.shift()(new Response(JSON.stringify({ ok: true }), { status: 200, headers: { 'Content-Type': 'application/json' } }));
}

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe('waking up the server', () => {
  it('shows after 3 seconds on any request and clears when the response arrives', async () => {
    const answer = slowFetch();
    render(<Banner />);
    const request = apiFetch('/cities');

    await act(async () => { vi.advanceTimersByTime(SLOW_REQUEST_MS - 1); });
    expect(screen.queryByRole('status')).toBeNull();

    await act(async () => { vi.advanceTimersByTime(1); });
    expect(screen.getByRole('status').textContent).toContain('Waking up the server');

    await act(async () => { answer(); await request; });
    expect(screen.queryByRole('status')).toBeNull();
  });

  it('never shows for a fast request', async () => {
    const answer = slowFetch();
    render(<Banner />);
    const request = apiFetch('/cities');
    await act(async () => { vi.advanceTimersByTime(500); answer(); await request; });
    await act(async () => { vi.advanceTimersByTime(SLOW_REQUEST_MS * 2); });
    expect(screen.queryByRole('status')).toBeNull();
  });

  it('stays while any slow request is still waiting', async () => {
    const answer = slowFetch();
    const first = apiFetch('/cities');
    const second = apiFetch('/itineraries/');
    await act(async () => { vi.advanceTimersByTime(SLOW_REQUEST_MS); });
    expect(isServerSlow()).toBe(true);
    await act(async () => { answer(); await first; });
    expect(isServerSlow()).toBe(true);
    await act(async () => { answer(); await second; });
    expect(isServerSlow()).toBe(false);
  });

  it('clears when a slow request fails', async () => {
    vi.stubGlobal('fetch', vi.fn(() => new Promise((_, reject) => setTimeout(() => reject(new TypeError('Failed to fetch')), 5000))));
    const request = apiFetch('/cities').catch((err) => err);
    await act(async () => { vi.advanceTimersByTime(SLOW_REQUEST_MS); });
    expect(isServerSlow()).toBe(true);
    await act(async () => { vi.advanceTimersByTime(5000); await request; });
    expect(isServerSlow()).toBe(false);
  });
});
