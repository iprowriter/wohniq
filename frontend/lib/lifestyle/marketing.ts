// Facts quoted on the homepage. A test (tests/lifestyle-marketing.test.ts) checks them
// against the real catalog, so marketing copy can't drift from what the feature does.

export const LIFESTYLE_FACTS = {
  areas: 143, // LOR Bezirksregionen scored
  factors: 16, // lifestyle attributes (14 about the area + budget + commute)
  sources: 10, // official & open data publications cited
  presets: 5,
} as const;

export const LIFESTYLE_PATH = "/lifestyle";
