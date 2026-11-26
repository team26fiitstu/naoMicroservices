import { useRef, useState } from "react";

// Drag items between slots, slot i is before item i, slot length is after last
export function useDragReorder<T>(items: T[], onReorder: (items: T[]) => void) {
  const dragIdx = useRef<number | null>(null);
  const [overSlot, setOverSlot] = useState<number | null>(null);

  const start = (i: number) => { dragIdx.current = i; };

  const over = (slot: number) => setOverSlot(slot);

  const end = () => {
    const from = dragIdx.current;
    const slot = overSlot;
    dragIdx.current = null;
    setOverSlot(null);
    if (from === null || slot === null || slot === from || slot === from + 1) return;
    const next = [...items];
    const [moved] = next.splice(from, 1);
    next.splice(slot > from ? slot - 1 : slot, 0, moved);
    onReorder(next);
  };

  return { overSlot, start, over, end };
}
