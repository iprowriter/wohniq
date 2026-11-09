interface Props {
  steps: { id: string; label: string }[];
  current: string;
  onJump?: (id: string) => void; // only steps already visited are clickable
  visited: Set<string>;
}

export function StepProgress({ steps, current, onJump, visited }: Props) {
  const index = Math.max(0, steps.findIndex((s) => s.id === current));
  const pct = steps.length > 1 ? (index / (steps.length - 1)) * 100 : 100;
  return (
    <div>
      <div className="relative h-1.5 overflow-hidden rounded-full bg-gray-100">
        <div
          className="absolute inset-y-0 left-0 rounded-full bg-gradient-to-r from-indigo-500 via-violet-500 to-fuchsia-500 transition-[width] duration-500 ease-out"
          style={{ width: `${pct}%` }}
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={Math.round(pct)}
          aria-label={`Step ${index + 1} of ${steps.length}`}
        />
      </div>
      <ol className="mt-3 hidden justify-between text-xs sm:flex">
        {steps.map((s, i) => {
          const clickable = onJump && visited.has(s.id) && s.id !== current;
          const state = i < index ? "text-indigo-600" : i === index ? "font-semibold text-gray-900" : "text-gray-400";
          return (
            <li key={s.id}>
              {clickable ? (
                <button type="button" onClick={() => onJump(s.id)} className={`${state} hover:underline`}>
                  {s.label}
                </button>
              ) : (
                <span className={state} aria-current={s.id === current ? "step" : undefined}>
                  {s.label}
                </span>
              )}
            </li>
          );
        })}
      </ol>
    </div>
  );
}
