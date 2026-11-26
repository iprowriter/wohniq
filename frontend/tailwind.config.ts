import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      // Berlin Ink design tokens (docs/design/berlin-ink/tokens.css), as CSS variables in
      // app/globals.css so components and the map share one source.
      colors: {
        ink: "var(--color-ink)",
        ground: "var(--color-ground)",
        surface: "var(--color-surface)",
        chip: "var(--color-chip)",
        placeholder: "var(--color-placeholder)",
        line: { DEFAULT: "var(--color-line)", strong: "var(--color-line-strong)" },
        input: "var(--color-input-border)",
        accent: {
          DEFAULT: "var(--color-accent)",
          hover: "var(--color-accent-hover)",
          "on-ink": "var(--color-accent-on-ink)",
          logo: "var(--color-accent-logo)",
          soft: "var(--color-accent-soft)",
          tint: "var(--color-accent-tint)",
        },
        text: {
          DEFAULT: "var(--color-text)",
          body: "var(--color-text-body)",
          muted: "var(--color-text-muted)",
          faint: "var(--color-text-faint)",
          "on-ink": "var(--color-text-on-ink)",
          "on-ink-muted": "var(--color-text-on-ink-muted)",
          "on-ink-soft": "var(--color-text-on-ink-soft)",
        },
        ok: {
          DEFAULT: "var(--color-ok-text)",
          strong: "var(--color-ok-strong)",
          body: "var(--color-ok-body)",
          bg: "var(--color-ok-bg)",
          bar: "var(--color-ok-bar)",
        },
        warn: { DEFAULT: "var(--color-warn-text)", bg: "var(--color-warn-bg)" },
        live: { DEFAULT: "var(--color-live)", text: "var(--color-live-text)" },
        map: {
          land: "var(--color-map-land)",
          water: "var(--color-map-water)",
          green: "var(--color-map-green)",
        },
        // BVG product colours for transport badges (components/ui/TransitIcon.tsx).
        bvg: {
          s: "#008D4F",
          u: "#115D91",
          tram: "#BE1414",
          bus: "#A5027D",
          ferry: "#0080BA",
          regional: "#E30613",
          stop: "#F6D330",
          "stop-text": "#0B5132",
        },
      },
      fontFamily: {
        sans: ["var(--font-geist-sans)", "Inter", "system-ui", "sans-serif"],
        mono: ["var(--font-geist-mono)", "ui-monospace", "monospace"],
      },
      borderRadius: {
        sm: "8px",
        md: "12px",
        lg: "16px",
        xl: "20px",
      },
      minHeight: { tap: "44px" },
      maxWidth: { page: "1280px" },
      keyframes: {
        // Lifestyle Match: step transitions and the persona reveal.
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(12px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "pop-in": {
          "0%": { opacity: "0", transform: "scale(0.94)" },
          "100%": { opacity: "1", transform: "scale(1)" },
        },
        "slide-in": {
          "0%": { transform: "translateX(100%)" },
          "100%": { transform: "translateX(0)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "0% 50%" },
          "100%": { backgroundPosition: "200% 50%" },
        },
      },
      animation: {
        "fade-up": "fade-up 0.45s ease-out both",
        "pop-in": "pop-in 0.5s cubic-bezier(0.2, 0.8, 0.2, 1) both",
        shimmer: "shimmer 6s linear infinite",
      },
    },
  },
  plugins: [],
};

export default config;
