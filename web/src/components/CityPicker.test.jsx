// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router';
import { useState } from 'react';
import App from '../App';
import CityPicker from './CityPicker';
import { matchCities, resetCities } from '../lib/cities';

const CITIES = [
  { slug: 'cape-town', name: 'Cape Town', province: 'Western Cape', country_code: 'ZA', currency: 'ZAR', status: 'live', aliases: ['Mother City', 'Kaapstad', 'CPT'] },
  { slug: 'johannesburg', name: 'Johannesburg', province: 'Gauteng', country_code: 'ZA', currency: 'ZAR', status: 'beta', aliases: ['Joburg', 'Jozi', 'Jhb', 'Egoli'] },
  { slug: 'pretoria', name: 'Pretoria', province: 'Gauteng', country_code: 'ZA', currency: 'ZAR', status: 'beta', aliases: ['Tshwane', 'PTA'] },
  { slug: 'london', name: 'London', province: 'England', country_code: 'GB', currency: 'GBP', status: 'beta', aliases: [] },
];

function fakeApi(routes) {
  const calls = [];
  vi.stubGlobal('fetch', vi.fn(async (url, init = {}) => {
    const key = `${init.method || 'GET'} ${new URL(url).pathname.replace('/api/v1', '')}`;
    calls.push({ key, body: init.body ? JSON.parse(init.body) : undefined });
    const [status, body] = routes[key] || [404, { detail: 'Not found' }];
    return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
  }));
  return calls;
}

function Picker({ onRequestCity }) {
  const [city, setCity] = useState('cape-town');
  return (
    <>
      <span id="label">Where?</span>
      <CityPicker value={city} onChange={setCity} labelledBy="label" onRequestCity={onRequestCity} />
      <output data-testid="chosen">{city}</output>
    </>
  );
}

async function box() {
  const input = screen.getByRole('combobox', { name: 'Where?' });
  await vi.waitFor(() => expect(input.value).toBe('Cape Town'));
  return input;
}

const names = () => screen.queryAllByRole('option').map((o) => o.querySelector('.city-search__name').textContent);
const type = (input, text) => fireEvent.change(input, { target: { value: text } });
const key = (input, k) => fireEvent.keyDown(input, { key: k });

beforeEach(() => {
  resetCities();
  fakeApi({ 'GET /cities': [200, CITIES] });
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe('matching', () => {
  it.each([
    ['Joburg', ['Johannesburg']],
    ['jozi', ['Johannesburg']],
    ['  JOBURG ', ['Johannesburg']],
    ['gauteng', ['Johannesburg', 'Pretoria']],
    ['mother', ['Cape Town']],
    ['town', ['Cape Town']],
    ['kaapstäd', ['Cape Town']],
    ['p', ['Pretoria', 'Cape Town']],
    ['Paris', []],
  ])('%j finds %j', (query, expected) => {
    expect(matchCities(CITIES, query).map((c) => c.name)).toEqual(expected);
  });

  it('lists every city for an empty query', () => {
    expect(matchCities(CITIES, '')).toBe(CITIES);
  });
});

describe('the search box', () => {
  it('is a labelled combobox that lists cities on focus with a Beta tag on beta ones', async () => {
    render(<Picker />);
    const input = await box();
    expect(input.getAttribute('aria-expanded')).toBe('false');
    fireEvent.focus(input);
    expect(input.getAttribute('aria-expanded')).toBe('true');
    expect(screen.getByRole('listbox', { name: 'Where?' }).id).toBe(input.getAttribute('aria-controls'));
    expect(names()).toEqual(['Cape Town', 'Johannesburg', 'Pretoria', 'London']);
    const options = screen.getAllByRole('option');
    expect(options[0].textContent).not.toContain('Beta');
    expect(options[1].textContent).toContain('Beta');
  });

  it('filters as you type: "Jozi" finds Johannesburg', async () => {
    render(<Picker />);
    const input = await box();
    type(input, 'Jozi');
    expect(names()).toEqual(['Johannesburg']);
  });

  it('works with the keyboard only', async () => {
    render(<Picker />);
    const input = await box();
    input.focus();
    type(input, 'gau');
    expect(input.getAttribute('aria-activedescendant')).toBe(screen.getAllByRole('option')[0].id);
    key(input, 'ArrowDown');
    const pretoria = screen.getByRole('option', { name: /Pretoria/ });
    expect(pretoria.getAttribute('aria-selected')).toBe('true');
    expect(input.getAttribute('aria-activedescendant')).toBe(pretoria.id);
    key(input, 'ArrowDown'); // wraps round
    expect(screen.getByRole('option', { name: /Johannesburg/ }).getAttribute('aria-selected')).toBe('true');
    key(input, 'ArrowUp');
    key(input, 'Enter');
    expect(screen.getByTestId('chosen').textContent).toBe('pretoria');
    expect(input.value).toBe('Pretoria');
    expect(input.getAttribute('aria-expanded')).toBe('false');
  });

  it('Escape closes the list and puts back the chosen city', async () => {
    render(<Picker />);
    const input = await box();
    type(input, 'Lon');
    key(input, 'Escape');
    expect(input.value).toBe('Cape Town');
    expect(input.getAttribute('aria-expanded')).toBe('false');
    expect(screen.getByTestId('chosen').textContent).toBe('cape-town');
  });

  it('chooses a city with a click', async () => {
    render(<Picker />);
    const input = await box();
    fireEvent.focus(input);
    fireEvent.click(screen.getByRole('option', { name: /London/ }));
    expect(screen.getByTestId('chosen').textContent).toBe('london');
  });

  it('offers to request a city it doesn’t cover, and says when it’s sent', async () => {
    const onRequestCity = vi.fn(async () => true);
    render(<Picker onRequestCity={onRequestCity} />);
    const input = await box();
    type(input, 'Gqeberha ');
    expect(screen.queryAllByRole('option')).toEqual([]);
    expect(screen.getByText("We don't cover Gqeberha yet").closest('[role="status"]').getAttribute('aria-live')).toBe('polite');
    key(input, 'Enter'); // nothing to choose: Enter doesn't submit the form
    expect(onRequestCity).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Request this city' }));
    expect(onRequestCity).toHaveBeenCalledWith('Gqeberha');
    expect(await screen.findByText("Thanks, we've noted Gqeberha.")).toBeTruthy();
  });

  it('shows why a request failed', async () => {
    render(<Picker onRequestCity={async () => { throw new Error("You've asked for 5 cities today. Try again tomorrow."); }} />);
    const input = await box();
    type(input, 'Knysna');
    fireEvent.click(screen.getByRole('button', { name: 'Request this city' }));
    expect(await screen.findByText(/asked for 5 cities today/)).toBeTruthy();
  });
});

describe('in the app', () => {
  function Where() {
    return <output data-testid="where">{useLocation().pathname}</output>;
  }

  function renderApp(path, session = { token: 'header.payload.signature', username: 'sam' }) {
    render(
      <MemoryRouter initialEntries={[path]}>
        <App initialSession={session} />
        <Where />
      </MemoryRouter>,
    );
  }

  beforeEach(() => {
    window.scrollTo = vi.fn();
    localStorage.clear();
  });

  it('choosing a city on the planner opens /plan/{city}', async () => {
    renderApp('/plan');
    const input = await box();
    type(input, 'Joburg');
    key(input, 'Enter');
    expect(screen.getByTestId('where').textContent).toBe('/plan/johannesburg');
    await vi.waitFor(() => expect(input.value).toBe('Johannesburg'));
  });

  it('/plan/{city} plans in that city, and an unknown one goes back to /plan', async () => {
    renderApp('/plan/pretoria');
    await vi.waitFor(() => expect(screen.getByRole('combobox', { name: 'Where?' }).value).toBe('Pretoria'));
    cleanup();
    renderApp('/plan/atlantis');
    await vi.waitFor(() => expect(screen.getByTestId('where').textContent).toBe('/plan'));
  });

  it('"Request this city" posts what was typed to /city-requests', async () => {
    resetCities();
    const calls = fakeApi({ 'GET /cities': [200, CITIES], 'GET /hotspots/': [200, []], 'GET /itineraries/': [200, []], 'POST /city-requests': [201, { id: 1, text: 'Hermanus', created_at: '2026-11-16T20:00:00' }] });
    renderApp('/plan');
    const input = await box();
    type(input, 'Hermanus');
    fireEvent.click(screen.getByRole('button', { name: 'Request this city' }));
    expect(await screen.findByText("Thanks, we've noted Hermanus.")).toBeTruthy();
    expect(calls.find((c) => c.key === 'POST /city-requests').body).toEqual({ text: 'Hermanus' });
  });

  it('signed out, "Request this city" asks you to sign in first', async () => {
    renderApp('/plan', { token: '', username: '' });
    const input = await box();
    type(input, 'Hermanus');
    fireEvent.click(screen.getByRole('button', { name: 'Request this city' }));
    await vi.waitFor(() => expect(screen.getByTestId('where').textContent).toBe('/login'));
  });
});
