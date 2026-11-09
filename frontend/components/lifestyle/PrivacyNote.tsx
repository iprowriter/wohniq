export function PrivacyNote({ text, compact = false }: { text: string; compact?: boolean }) {
  return (
    <div
      className={`flex items-start gap-3 rounded-2xl border border-emerald-100 bg-emerald-50/70 text-emerald-900 ${
        compact ? "px-3 py-2 text-xs" : "px-4 py-3 text-sm"
      }`}
    >
      <svg className="mt-0.5 flex-shrink-0" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
        <rect x="4" y="11" width="16" height="10" rx="2" />
        <path d="M8 11V7a4 4 0 018 0v4" />
      </svg>
      <p className="leading-relaxed">{text}</p>
    </div>
  );
}
