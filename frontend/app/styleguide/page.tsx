import type { Metadata } from "next";
import {
  Button,
  ButtonLink,
  Chip,
  MeasureBar,
  SectionHeading,
  SourceLabel,
  VerdictCard,
} from "@/components/ui/primitives";
import { RentScale } from "@/components/ui/RentScale";
import { MODE_LABEL, StopModes, TransitIcon, type TransitMode } from "@/components/ui/TransitIcon";
import { StyleguideMap } from "./StyleguideMap";

export const metadata: Metadata = { title: "Styleguide — WohnIQ" };

const COLORS: [string, string][] = [
  ["ink", "--color-ink"],
  ["ground", "--color-ground"],
  ["surface", "--color-surface"],
  ["chip", "--color-chip"],
  ["accent", "--color-accent"],
  ["accent tint", "--color-accent-tint"],
  ["ok", "--color-ok-text"],
  ["ok bg", "--color-ok-bg"],
  ["ok bar", "--color-ok-bar"],
  ["warn", "--color-warn-text"],
  ["warn bg", "--color-warn-bg"],
  ["live", "--color-live"],
  ["map land", "--color-map-land"],
  ["map water", "--color-map-water"],
  ["map green", "--color-map-green"],
];

const MODES: TransitMode[] = ["sbahn", "ubahn", "tram", "bus", "ferry", "regional", "stop"];

export default function StyleguidePage() {
  return (
    <div className="mx-auto flex max-w-page flex-col gap-10 px-[18px] py-10 md:px-8">
      <header>
        <p className="text-sm font-semibold uppercase tracking-[0.08em] text-accent">Berlin Ink</p>
        <h1 className="mt-2 text-[44px] font-bold leading-tight tracking-[-0.03em]">Styleguide</h1>
        <p className="mt-2 max-w-2xl text-text-muted">
          The shared building blocks of WohnIQ. Verdicts use two states plus neutral, never red;
          every chip carries words; everything clickable is at least 44 px tall.
        </p>
      </header>

      <section className="flex flex-col gap-4">
        <SectionHeading title="Colours" lede="docs/design/berlin-ink/tokens.css" />
        <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          {COLORS.map(([name, v]) => (
            <li key={name} className="overflow-hidden rounded-md border border-line bg-surface">
              <div className="h-14" style={{ background: `var(${v})` }} />
              <div className="px-3 py-2 text-[13px]">
                <div className="font-medium">{name}</div>
                <code className="font-mono text-[12px] text-text-muted">{v}</code>
              </div>
            </li>
          ))}
        </ul>
      </section>

      <section className="flex flex-col gap-4">
        <SectionHeading title="Type" />
        <div className="flex flex-col gap-2 rounded-lg border border-line bg-surface p-6">
          <p className="text-[64px] font-bold leading-none tracking-[-0.04em]">Display 64</p>
          <p className="text-[44px] font-bold tracking-[-0.03em]">Heading 44</p>
          <p className="text-[22px] font-semibold">Section 22</p>
          <p className="text-[17px] font-semibold">Card title 17</p>
          <p className="text-base text-text-body">Body 16: Every listing gets three verdicts, each explained in plain words.</p>
          <p className="text-sm text-text-muted">Small 14 · tabular figures €1,284 · 61 m² · €14.10/m²</p>
          <p className="font-mono text-[13px]">Geist Mono 13 · 01 02 03</p>
        </div>
      </section>

      <section className="flex flex-col gap-4">
        <SectionHeading title="Chips and buttons" />
        <div className="flex flex-wrap gap-2">
          <Chip tone="ok">Fair rent · in Mietspiegel range</Chip>
          <Chip tone="warn">Above index · €14.10/m²</Chip>
          <Chip tone="ok">Low scam risk</Chip>
          <Chip tone="warn">Worth asking: some signals</Chip>
          <Chip>New build: no rent brake</Chip>
          <Chip tone="accent">In Mitte</Chip>
        </div>
        <div className="flex flex-wrap gap-3">
          <Button>Search</Button>
          <Button variant="dark">View dossier</Button>
          <Button variant="outline">Compare</Button>
          <Button variant="ghost">Open the full rent check</Button>
          <ButtonLink href="/rent-check" variant="outline">Check a rent</ButtonLink>
        </div>
      </section>

      <section className="flex flex-col gap-4">
        <SectionHeading title="Verdict cards" />
        <div className="grid gap-3 md:grid-cols-3">
          <VerdictCard tone="ink" label="Fit for your search" value="92" detail="Strong match: Mitte, 2 rooms, quiet" />
          <VerdictCard tone="warn" label="Rent check" value="Above the rent-brake limit" detail="€17.86/m² cold · limit €10.20" />
          <VerdictCard label="Scam risk" value="Low · 12/100" detail="No warning signs found" />
        </div>
        <div className="grid gap-3 md:grid-cols-3">
          <VerdictCard tone="ok" label="Rent check" value="Within the rent-brake limit" detail="€9.56/m² cold · limit €9.98" />
        </div>
      </section>

      <section className="flex flex-col gap-4">
        <SectionHeading title="Transport" lede="BVG-style icons, drawn for WohnIQ. Each has a screen-reader name." />
        <ul className="flex flex-wrap gap-4">
          {MODES.map((m) => (
            <li key={m} className="flex items-center gap-2 text-sm">
              <TransitIcon mode={m} size={24} /> {MODE_LABEL[m]}
            </li>
          ))}
        </ul>
        <ul className="flex flex-col gap-2 rounded-lg bg-ink p-5 text-text-on-ink-soft">
          {[
            { name: "U Rosenthaler Platz", modes: ["ubahn", "tram", "bus"], min: 1 },
            { name: "S+U Warschauer Str.", modes: ["sbahn", "ubahn", "tram", "bus"], min: 7 },
            { name: "Wannsee", modes: ["sbahn", "regional", "bus", "ferry"], min: 4 },
            { name: "U Weinmeisterstr./Gipsstr.", modes: [], min: 8 },
          ].map((s) => (
            <li key={s.name} className="flex items-center gap-3 text-[15px]">
              <StopModes modes={s.modes} />
              <span className="flex-1">{s.name}</span>
              <span className="font-semibold text-white">{s.min} min</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="flex flex-col gap-4">
        <SectionHeading title="Rent scale" />
        <div className="flex flex-col gap-6 rounded-lg border border-line bg-surface p-6">
          <RentScale low={7.01} mean={9.27} high={12.25} limit={10.2} asked={17.86} />
          <RentScale low={7.4} mean={9.07} high={11.42} limit={9.98} asked={9.56} />
          <RentScale low={11.31} mean={19.04} high={26.81} limit={null} asked={20.25} />
        </div>
      </section>

      <section className="flex flex-col gap-4">
        <SectionHeading title="Comparison bar and source label" />
        <div className="flex max-w-md flex-col gap-2 rounded-lg border border-line bg-surface p-4">
          <div className="flex justify-between text-[13px] text-text-muted">
            <span>Nearest S/U-Bahn</span>
            <SourceLabel>VBB</SourceLabel>
          </div>
          <p className="text-[17px] font-semibold">U Moritzplatz · 4 min walk</p>
          <MeasureBar position={98} />
          <p className="text-[13px] text-text-body">Closer than 98% of Berlin&apos;s 542 planning areas</p>
        </div>
      </section>

      <section className="flex flex-col gap-4">
        <SectionHeading title="Offline map" lede="berlin.pmtiles from the API, drawn in the browser. No tile server." />
        <StyleguideMap />
      </section>
    </div>
  );
}
