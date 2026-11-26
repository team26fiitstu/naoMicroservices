import { useState, type DragEvent } from "react";
import { GripVertical } from "lucide-react";
import { ConfirmDialog } from "@/components/ui/confirmDialog";
import { AnglesTooltip } from "@/components/editor/anglesTooltip";
import { FrameImage } from "@/components/editor/frameImage";
import { FrameMenu } from "@/components/editor/frameMenu";
import { VoiceLineEditor } from "@/components/editor/voiceLineEditor";
import { useFrameVoiceLine } from "@/hooks/useFrameVoiceLine";
import type { StatusType } from "@/hooks/useStatus";
import type { Frame } from "@/lib/frames";
import type { PoseCommand } from "@/lib/poses";

type Props = {
  frame: Frame;
  position: number;
  exerciseId: string;
  poses: PoseCommand[];
  onInsertBefore: (pose: string) => void;
  onInsertAfter: (pose: string) => void;
  onDelete: () => void;
  inserting: boolean;
  deleting: boolean;
  showStatus: (type: StatusType, text: string) => void;
  onDragStart: () => void;
  onDragEnd: () => void;
  onDragOver: (e: DragEvent) => void;
};

// Frame in timeline: compact row on mobile, card with voice line on desktop
export function FrameCard({
  frame,
  position,
  exerciseId,
  poses,
  onInsertBefore,
  onInsertAfter,
  onDelete,
  inserting,
  deleting,
  showStatus,
  ...dragProps
}: Props) {
  const voice = useFrameVoiceLine(exerciseId, frame.idx, showStatus);
  const [confirmDelete, setConfirmDelete] = useState(false);

  // shared by mobile and desktop layouts
  const menu = (
    <FrameMenu
      poses={poses}
      busy={inserting || deleting}
      language={voice.language}
      speed={voice.speed}
      onInsertBefore={onInsertBefore}
      onInsertAfter={onInsertAfter}
      onVoiceChange={voice.changeVoice}
      onDelete={() => setConfirmDelete(true)}
    />
  );

  return (
    <div
      draggable
      {...dragProps}
      className={[
        "w-full md:w-60 md:shrink-0 rounded-xl border bg-card text-card-foreground shadow-sm",
        "transition-all duration-150 cursor-grab active:cursor-grabbing",
        deleting ? "opacity-40 pointer-events-none" : "",
      ].join(" ")}
    >
      {/* mobile: compact row */}
      <div className="flex md:hidden items-center gap-3 px-3 py-2">
        <FrameImage frame={frame} exerciseId={exerciseId} className="w-14 h-14 shrink-0 object-cover" />
        <span className="text-sm font-medium text-foreground tabular-nums">{position + 1}</span>
        <div className="ml-auto flex items-center gap-1">
          <GripVertical className="h-4 w-4 text-muted-foreground opacity-40" />
          {menu}
        </div>
      </div>

      {/* desktop: vertical card */}
      <div className="hidden md:flex flex-col h-full">
        <div className="flex items-center gap-1 pl-3 pr-1.5 pt-1.5 pb-1">
          <span className="text-sm font-medium text-foreground tabular-nums">{position + 1}</span>
          <GripVertical className="h-4 w-4 ml-auto text-muted-foreground opacity-40" />
          {menu}
        </div>

        <div className="px-3 flex-1">
          <FrameImage frame={frame} exerciseId={exerciseId} className="w-full min-h-32" />
        </div>

        <AnglesTooltip angles={frame.angles} />

        <div className="mt-auto">
          <VoiceLineEditor id={`voice-text-${frame.idx}`} voice={voice} />
        </div>
      </div>

      <ConfirmDialog
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
        title="Odstrániť snímku?"
        description={`Snímka ${position + 1} sa natrvalo odstráni z cvičenia.`}
        confirmLabel="Odstrániť"
        onConfirm={onDelete}
      />
    </div>
  );
}
