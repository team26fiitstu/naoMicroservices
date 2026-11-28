import { BaseEdge, EdgeLabelRenderer, useInternalNode, type Edge, type EdgeProps, type InternalNode } from "@xyflow/react";
import { cn } from "@/lib/utils";

export type EdgeMarkers = { plain: string; selected: string; next: string };
// run: next for transitions out of current state, dimmed for other ones
type TransitionEdgeData = { label: string; curved: boolean; markers: EdgeMarkers; run?: "next" | "dimmed" };
export type TransitionFlowEdge = Edge<TransitionEdgeData, "transition">;

type Point = { x: number; y: number };

const BEND = 40;
const LOOP_HEIGHT = 56;

// arrow from node border to node border, opposite transitions bend apart, self transition loops above node
export function TransitionEdge({ id, source, target, data, selected }: EdgeProps<TransitionFlowEdge>) {
  const from = useInternalNode(source);
  const to = useInternalNode(target);
  if (!from || !to || !data) return null;

  const a = center(from);
  let path: string;
  let label: Point;
  if (source === target) {
    const top = from.internals.positionAbsolute.y;
    path = `M${a.x - 24} ${top} C${a.x - 44} ${top - LOOP_HEIGHT} ${a.x + 44} ${top - LOOP_HEIGHT} ${a.x + 24} ${top}`;
    label = { x: a.x, y: top - LOOP_HEIGHT + 8 };
  } else {
    const b = center(to);
    const length = Math.hypot(b.x - a.x, b.y - a.y) || 1;
    const bend = data.curved ? BEND : 0;
    const control = { x: (a.x + b.x) / 2 - ((b.y - a.y) / length) * bend, y: (a.y + b.y) / 2 + ((b.x - a.x) / length) * bend };
    const start = border(from, control);
    const end = border(to, control);
    path = `M${start.x} ${start.y} Q${control.x} ${control.y} ${end.x} ${end.y}`;
    label = { x: (start.x + 2 * control.x + end.x) / 4, y: (start.y + 2 * control.y + end.y) / 4 };
  }

  return (
    <>
      <BaseEdge
        id={id}
        path={path}
        markerEnd={`url(#${data.run === "next" ? data.markers.next : selected ? data.markers.selected : data.markers.plain})`}
        style={data.run === "next" ? { stroke: "var(--success)" } : data.run === "dimmed" ? { opacity: 0.35 } : undefined}
        interactionWidth={16}
      />
      <EdgeLabelRenderer>
        <div
          style={{ transform: `translate(-50%, -50%) translate(${label.x}px, ${label.y}px)` }}
          className={cn(
            "pointer-events-none absolute max-w-40 truncate rounded-base border bg-card px-1.5 py-0.5 text-[11px] text-foreground shadow-sm",
            data.run === "next" && "border-success bg-[color-mix(in_oklab,var(--success)_12%,var(--card))]",
            data.run === "dimmed" && "opacity-35",
            !data.run && selected && "border-info bg-[color-mix(in_oklab,var(--info)_12%,var(--card))]",
          )}
        >
          {data.label}
        </div>
      </EdgeLabelRenderer>
    </>
  );
}

const size = (node: InternalNode) => ({ w: node.measured.width ?? 0, h: node.measured.height ?? 0 });

const center = (node: InternalNode): Point => {
  const { w, h } = size(node);
  return { x: node.internals.positionAbsolute.x + w / 2, y: node.internals.positionAbsolute.y + h / 2 };
};

// point where line from node center toward target leaves node box
function border(node: InternalNode, toward: Point): Point {
  const c = center(node);
  const { w, h } = size(node);
  const dx = toward.x - c.x;
  const dy = toward.y - c.y;
  const scale = Math.min(w / 2 / Math.abs(dx || 1e-9), h / 2 / Math.abs(dy || 1e-9));
  return { x: c.x + dx * scale, y: c.y + dy * scale };
}
