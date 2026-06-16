# ADR-0003 — Synthetic listings with hotlinked stock photos

**Status:** Accepted · **Date:** 2026-06-15

## Context

WohnIQ needs ~100 realistic listings with ~5 images each to feel like a real marketplace. The big Berlin portals offer no public APIs and prohibit scraping, and real listings would drag in legal, privacy, and freshness problems irrelevant to a portfolio project. We also need *ground-truth scam labels* to evaluate the showpiece detector — something real data can't give us. Separately, sourcing ~500 images by hand would be tedious and pointless.

## Decision

Use **synthetic listings**, generated programmatically with realistic Berlin distributions (Kieze, rents per m², sizes, room counts), including a labeled ~15% scam subset spanning each scam pattern plus hard negatives (cheap-but-legit, landlord-travels-but-legit).

For images, **script the sourcing** via the free Pexels (and/or Unsplash) search API: fetch by room type (`living room`, `bedroom`, `kitchen`, `bathroom`, `balcony`) into typed pools, then assign one of each per listing so every listing is a coherent set. **Hotlink the provider CDN URLs** (store URL + attribution) rather than downloading — zero storage, zero file management. The image seeder also computes a pHash per image (fetched once) for the scam detector, and deliberately reuses photo sets across a few scam listings to create realistic duplicate-photo fraud.

## Alternatives considered

- **Scrape real portals:** rejected — ToS violation, legal/privacy risk, no labels, brittle.
- **AI-generate images:** rejected — costs money (violates ADR's €0 budget), and we *want* real reusable photos to demo duplicate detection.
- **Download & host images in Supabase Storage:** rejected for default — unnecessary storage use and management; hotlinking is simpler. (We still fetch bytes once to compute pHash.)
- **Pre-grouped real-estate interior datasets (Kaggle/HF):** kept as an optional upgrade if we want each listing's photos to be the same physical flat.

## Consequences

- **+** €0, no manual image work, no legal exposure.
- **+** We control the dataset to showcase every AI feature and to hold scam ground truth for evals.
- **+** Finite image pool → realistic duplicate-photo scams for free (feeds the showpiece).
- **−** Hotlinked URLs can rot if a provider removes a photo (mitigated: re-runnable seeder; could switch to download mode).
- **−** Synthetic data must be *labeled clearly* in the README so reviewers see it as an intentional design choice, not a gap.
- Requires honoring Pexels/Unsplash attribution in the UI.
