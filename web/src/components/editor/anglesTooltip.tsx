import { useRef, useState } from "react";

// Joint angles of frame on hover
export function AnglesTooltip({ angles }: { angles: Record<string, number> }) {
  const [open, setOpen] = useState(false);
  const hideTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const show = () => {
    if (hideTimer.current) clearTimeout(hideTimer.current);
    setOpen(true);
  };
  const hide = () => {
    hideTimer.current = setTimeout(() => setOpen(false), 120);
  };

  const count = Object.keys(angles).length;

  return (
    <div className="px-3 pt-1.5 relative">
      {count > 0 ? (
        <span
          className="text-[11px] text-muted-foreground underline decoration-dotted underline-offset-2 cursor-default hover:text-foreground transition-colors"
          onMouseEnter={show}
          onMouseLeave={hide}
        >
          Uhly
        </span>
      ) : (
        <span className="text-[11px] italic text-muted-foreground">žiadne dáta uhlov</span>
      )}
      {open && count > 0 && (
        <div
          className="absolute bottom-full left-3 mb-1 w-56 z-50 rounded-lg border bg-popover text-popover-foreground shadow-lg p-2"
          onMouseEnter={show}
          onMouseLeave={hide}
        >
          <p className="px-1 pb-1.5 mb-1 border-b text-[11px] font-medium">Uhly kĺbov (rad)</p>
          <div className="max-h-52 overflow-y-auto">
            {Object.entries(angles).map(([k, v]) => (
              <div key={k} className="flex justify-between gap-3 rounded px-1 py-0.5 text-[11px] hover:bg-muted">
                <span className="text-muted-foreground">{k}</span>
                <span className="font-mono tabular-nums">{typeof v === "number" ? v.toFixed(3) : v}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
