// Compile-time checks that the generated types match what the web relies on.
// Never imported at runtime; `npm run check:api` type-checks this file.

/** @type {import('./api').Stop} */
export const stop = {
  day: 1,
  time: '09:00 AM',
  activity: 'Breakfast',
  estimated_cost: 180,
  google_place_id: 'ChIJabc123def456',
  verified: true,
};

/** @type {import('./api').PlanToSave} */
export const plan = {
  title: 'A day out in Cape Town',
  destination: 'Cape Town',
  budget: '$$',
  items: [stop],
};

/** @type {import('./api').PlanToSave['budget']} */
// @ts-expect-error: a budget outside $, $$ and $$$ must not type-check
export const badBudget = 'lots';
