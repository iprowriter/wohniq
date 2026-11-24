/**
 * BVG-style transport icons, drawn here (no external assets): S-Bahn green circle, U-Bahn
 * blue square, tram, bus, ferry and regional-train tiles in the BVG product colours, and the
 * yellow "H" stop sign for a stop whose type isn't known. Every icon has an accessible name,
 * so colour is never the only clue (design rule).
 */

export type TransitMode = "sbahn" | "ubahn" | "tram" | "bus" | "ferry" | "regional" | "stop";

export const MODE_LABEL: Record<TransitMode, string> = {
  sbahn: "S-Bahn",
  ubahn: "U-Bahn",
  tram: "Tram",
  bus: "Bus",
  ferry: "Ferry",
  regional: "Regional train",
  stop: "Stop",
};

/** Display order: rail first, then surface, as BVG signs list them. */
export const MODE_ORDER: TransitMode[] = ["ubahn", "sbahn", "regional", "tram", "bus", "ferry"];

const COLORS: Record<TransitMode, string> = {
  sbahn: "#008D4F",
  ubahn: "#115D91",
  tram: "#BE1414",
  bus: "#A5027D",
  ferry: "#0080BA",
  regional: "#E30613",
  stop: "#F6D330",
};

function Glyph({ mode }: { mode: TransitMode }) {
  switch (mode) {
    case "sbahn":
      return (
        <>
          <circle cx="12" cy="12" r="11" fill={COLORS.sbahn} />
          <text x="12" y="16.6" textAnchor="middle" fontSize="13.5" fontWeight="700" fill="#fff"
            fontFamily="Arial, Helvetica, sans-serif">S</text>
        </>
      );
    case "ubahn":
      return (
        <>
          <rect x="1" y="1" width="22" height="22" rx="2.5" fill={COLORS.ubahn} />
          <text x="12" y="16.6" textAnchor="middle" fontSize="13.5" fontWeight="700" fill="#fff"
            fontFamily="Arial, Helvetica, sans-serif">U</text>
        </>
      );
    case "tram":
      return (
        <>
          <rect x="1" y="1" width="22" height="22" rx="4" fill={COLORS.tram} />
          {/* pantograph, car body with windows, wheels */}
          <path d="M9 4.5h6M12 4.5v2.5" stroke="#fff" strokeWidth="1.4" strokeLinecap="round" />
          <rect x="7" y="7" width="10" height="10" rx="2" fill="#fff" />
          <rect x="8.4" y="8.5" width="7.2" height="3.6" rx="0.8" fill={COLORS.tram} />
          <path d="M8.5 19.5l1.5-2.5M15.5 19.5l-1.5-2.5" stroke="#fff" strokeWidth="1.4" strokeLinecap="round" />
        </>
      );
    case "bus":
      return (
        <>
          <rect x="1" y="1" width="22" height="22" rx="4" fill={COLORS.bus} />
          <rect x="6" y="5" width="12" height="12" rx="2.2" fill="#fff" />
          <rect x="7.4" y="6.6" width="9.2" height="4.4" rx="0.8" fill={COLORS.bus} />
          <circle cx="8.8" cy="14.2" r="1" fill={COLORS.bus} />
          <circle cx="15.2" cy="14.2" r="1" fill={COLORS.bus} />
          <rect x="7.3" y="17" width="2.4" height="2.5" rx="0.6" fill="#fff" />
          <rect x="14.3" y="17" width="2.4" height="2.5" rx="0.6" fill="#fff" />
        </>
      );
    case "ferry":
      return (
        <>
          <rect x="1" y="1" width="22" height="22" rx="4" fill={COLORS.ferry} />
          <path d="M9 6.5h4.5l1.5 3.5H9z" fill="#fff" />
          <path d="M5 12h14l-2.2 4.2H7.2z" fill="#fff" />
          <path d="M4.5 18.6c1.3 0 1.3-.9 2.6-.9s1.3.9 2.6.9 1.3-.9 2.6-.9 1.3.9 2.6.9 1.3-.9 2.6-.9 1.3.9 2.6.9"
            stroke="#fff" strokeWidth="1.2" fill="none" strokeLinecap="round" />
        </>
      );
    case "regional":
      return (
        <>
          <rect x="1" y="1" width="22" height="22" rx="4" fill={COLORS.regional} />
          <text x="12" y="15.8" textAnchor="middle" fontSize="9.5" fontWeight="700" fill="#fff"
            fontFamily="Arial, Helvetica, sans-serif">RE</text>
        </>
      );
    default:
      return (
        <>
          <circle cx="12" cy="12" r="11" fill={COLORS.stop} stroke="#0B5132" strokeWidth="1.4" />
          <text x="12" y="16.6" textAnchor="middle" fontSize="13" fontWeight="700" fill="#0B5132"
            fontFamily="Arial, Helvetica, sans-serif">H</text>
        </>
      );
  }
}

export function TransitIcon({ mode, size = 20 }: { mode: TransitMode; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" role="img" aria-label={MODE_LABEL[mode]}
      className="inline-block shrink-0">
      <title>{MODE_LABEL[mode]}</title>
      <Glyph mode={mode} />
    </svg>
  );
}

/** Icons for a stop's modes in BVG order; the "H" sign when the type isn't known. */
export function StopModes({ modes, size = 20 }: { modes: string[]; size?: number }) {
  const known = MODE_ORDER.filter((m) => modes.includes(m));
  const list: TransitMode[] = known.length ? known : ["stop"];
  return (
    <span className="inline-flex items-center gap-1">
      {list.map((m) => (
        <TransitIcon key={m} mode={m} size={size} />
      ))}
    </span>
  );
}
