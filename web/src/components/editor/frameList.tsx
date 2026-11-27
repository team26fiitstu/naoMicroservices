import type { DragEvent } from "react";
import { GripVertical } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { FrameCard } from "@/components/editor/frameCard";
import { useDragReorder } from "@/hooks/useDragReorder";
import type { StatusType } from "@/hooks/useStatus";
import type { Frame } from "@/lib/frames";
import type { PoseCommand } from "@/lib/poses";

type Props = {
  frames: Frame[];
  exerciseId: string;
  poses: PoseCommand[];
  insertingAt: number | null;
  deletingAt: number | null;
  onInsert: (position: number, pose: string) => void;
  onDelete: (frameIdx: number) => void;
  onReorder: (frames: Frame[]) => void;
  showStatus: (type: StatusType, text: string) => void;
};

// Frame timeline, order changed by dragging between cards
export function FrameList({ frames, exerciseId, poses, insertingAt, deletingAt, onInsert, onDelete, onReorder, showStatus }: Props) {
  const drag = useDragReorder(frames, onReorder);

  // slot before or after card, by cursor side
  const dragOver = (e: DragEvent, i: number) => {
    e.preventDefault();
    const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
    drag.over(e.clientX < rect.left + rect.width / 2 ? i : i + 1);
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <h2 className="text-sm font-medium text-foreground">Snímky</h2>
        <Badge variant="secondary" className="tabular-nums">{frames.length}</Badge>
        <p className="ml-2 flex items-center gap-1 text-xs text-muted-foreground">
          <GripVertical className="h-3.5 w-3.5" />
          Poradie zmeníte pretiahnutím
        </p>
      </div>

      <div className="overflow-x-auto overflow-y-auto pb-3">
        <div className="flex flex-col md:flex-row items-stretch gap-(--layout-gap) md:min-w-max">
          {frames.map((frame, i) => (
            <div key={`${frame.idx}-${i}`} className="flex items-stretch gap-(--layout-gap)">
              {drag.overSlot === i && (
                <div className="md:w-0.5 md:self-stretch h-0.5 md:h-auto w-full bg-primary rounded-full shrink-0" />
              )}
              <FrameCard
                frame={frame}
                position={i}
                exerciseId={exerciseId}
                poses={poses}
                onInsertBefore={(pose) => onInsert(i, pose)}
                onInsertAfter={(pose) => onInsert(i + 1, pose)}
                onDelete={() => onDelete(frame.idx)}
                inserting={insertingAt !== null}
                deleting={deletingAt === frame.idx}
                showStatus={showStatus}
                onDragStart={() => drag.start(i)}
                onDragEnd={drag.end}
                onDragOver={(e) => dragOver(e, i)}
              />
            </div>
          ))}
          {drag.overSlot === frames.length && (
            <div className="w-0.5 self-stretch bg-primary rounded-full flex-shrink-0" />
          )}
        </div>
      </div>
    </div>
  );
}
