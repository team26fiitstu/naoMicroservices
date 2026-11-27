import { useEffect, useId, useMemo, useRef, useState } from "react";
import { Background, BackgroundVariant, Controls, ReactFlow, useNodesState, type ReactFlowInstance } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { StateNode, type StateFlowNode } from "@/components/choreography/stateNode";
import { TransitionEdge, type TransitionFlowEdge } from "@/components/choreography/transitionEdge";
import type { Choreography, GraphSelection } from "@/lib/choreography";
import type { ExerciseSummary } from "@/lib/exercises";

const nodeTypes = { state: StateNode };
const edgeTypes = { transition: TransitionEdge };
const FIT_VIEW = { padding: 0.25, maxZoom: 1 };

type Props = {
  graph: Choreography;
  exercises: Map<string, ExerciseSummary>;
  selection: GraphSelection;
  onSelect: (selection: GraphSelection) => void;
  onMove: (stateId: string, x: number, y: number) => void;
  onOpen: (stateId: string) => void;
};

// Graph on React Flow, positions saved when drag ends
export function GraphCanvas({ graph, exercises, selection, onSelect, onMove, onOpen }: Props) {
  // marker ids go into url(#...), keep only safe characters
  const id = useId().replace(/[^\w-]/g, "");
  const marker = `${id}-arrow`;
  const selectedMarker = `${id}-arrow-selected`;

  // local copy so nodes follow pointer while dragging, reset from graph after each save
  const [nodes, setNodes, onNodesChange] = useNodesState<StateFlowNode>([]);
  useEffect(() => {
    setNodes(graph.states.map((s) => ({
      id: s.state_id,
      type: "state",
      position: { x: s.x, y: s.y },
      data: { label: s.label, initial: s.state_id === graph.initial_state, source: exercises.get(s.state_id)?.source },
      selected: selection?.kind === "state" && selection.id === s.state_id,
    })));
  }, [graph, exercises, selection, setNodes]);

  // added state may be outside view, fit graph again once it is drawn
  const [flow, setFlow] = useState<ReactFlowInstance<StateFlowNode, TransitionFlowEdge> | null>(null);
  const stateCount = useRef(graph.states.length);
  useEffect(() => {
    const added = graph.states.length > stateCount.current;
    stateCount.current = graph.states.length;
    if (!added || !flow) return;
    const frame = requestAnimationFrame(() => flow.fitView({ ...FIT_VIEW, duration: 300 }));
    return () => cancelAnimationFrame(frame);
  }, [graph.states.length, flow]);

  const edges = useMemo<TransitionFlowEdge[]>(() => graph.transitions.map((t) => ({
    id: t.id,
    source: t.from,
    target: t.to,
    type: "transition",
    selected: selection?.kind === "transition" && selection.id === t.id,
    data: { label: t.label, curved: graph.transitions.some((o) => o.from === t.to && o.to === t.from), marker, selectedMarker },
  })), [graph, selection, marker, selectedMarker]);

  return (
    <div className="h-[420px] md:h-[560px]">
      <svg className="absolute h-0 w-0">
        <defs>
          {[[marker, "fill-muted-foreground"], [selectedMarker, "fill-info"]].map(([markerId, fill]) => (
            <marker key={markerId} id={markerId} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
              <path d="M0 0 L10 5 L0 10 z" className={fill} />
            </marker>
          ))}
        </defs>
      </svg>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        onNodesChange={onNodesChange}
        onNodeDragStop={(_, node) => onMove(node.id, Math.round(node.position.x), Math.round(node.position.y))}
        onNodeClick={(_, node) => onSelect({ kind: "state", id: node.id })}
        onNodeDoubleClick={(_, node) => onOpen(node.id)}
        onEdgeClick={(_, edge) => onSelect({ kind: "transition", id: edge.id })}
        onPaneClick={() => onSelect(null)}
        nodesConnectable={false}
        deleteKeyCode={null}
        zoomOnDoubleClick={false}
        minZoom={0.3}
        maxZoom={2}
        onInit={setFlow}
        fitView
        fitViewOptions={FIT_VIEW}
      >
        <Background variant={BackgroundVariant.Dots} gap={20} size={1} />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}
