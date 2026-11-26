"use client";

import type { NeighborhoodCatalog } from "@/lib/neighborhoods/types";
import { OVERALL } from "@/lib/neighborhoods/logic";
import { CategoryIcon } from "@/components/lifestyle/explorer/icons";

/** Category switcher: re-ranks the list and recolours the map. */
export function CategoryTabs({
  catalog,
  active,
  onChange,
}: {
  catalog: NeighborhoodCatalog;
  active: string;
  onChange: (id: string) => void;
}) {
  const items = [{ id: OVERALL, label: catalog.overall.label }, ...catalog.categories];
  return (
    <div className="relative">
      <div
        role="group"
        aria-label="Rank neighborhoods by"
        className="-mx-4 overflow-x-auto px-4 pb-1 [scrollbar-width:thin]"
      >
        <div className="flex w-max gap-2 pr-8">
          {items.map((c) => {
            const on = c.id === active;
            return (
              <button
                key={c.id}
                type="button"
                aria-pressed={on}
                onClick={() => onChange(c.id)}
                className={`flex items-center gap-1.5 whitespace-nowrap rounded-full px-3.5 py-2 text-sm font-medium transition focus:outline-none focus-visible:ring-2 focus-visible:ring-accent ${
                  on
                    ? "bg-accent text-white shadow-md shadow-accent/20"
                    : "border border-line bg-white text-text-body hover:border-accent/50 hover:text-accent"
                }`}
              >
                <CategoryIcon id={c.id === OVERALL ? "overall" : c.id} size={16} />
                {c.label}
              </button>
            );
          })}
        </div>
      </div>
      {/* fade: there are more categories to scroll to */}
      <div
        className="pointer-events-none absolute -right-4 top-0 h-full w-12 bg-gradient-to-l from-ground to-transparent"
        aria-hidden="true"
      />
    </div>
  );
}
