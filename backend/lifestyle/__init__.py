"""Lifestyle Match — match a person's lifestyle to Berlin neighbourhoods (ADR-0010).

Pure, deterministic code only: no LLM, no database, no network at request time.
  * attributes.py — the catalogue of lifestyle attributes (what we can score)
  * profiles.py   — typed neighbourhood profiles + provenance, loaded from
                    data/lifestyle/regions.json (built by data/lifestyle/build_profiles.py)
"""
