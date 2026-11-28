import { useState } from "react";
import { Plus, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ExerciseSelect } from "@/components/exercise/exerciseSelect";
import { MediaUpload } from "@/components/exercise/mediaUpload";
import { createExerciseFromImage, createExerciseFromVideo, DEFAULT_VIDEO_SETTINGS, nameFromFile, type ExerciseRef, type ExerciseSummary } from "@/lib/exercises";
import type { VideoRange } from "@/lib/videoRange";

type Props = {
  // all saved exercises, same one may be added several times
  exercises: ExerciseSummary[];
  onAddExisting: (exercise: ExerciseRef) => void;
  onAddNew: (exercise: ExerciseRef) => void;
  onError: (action: string, err: unknown) => void;
  onReject: () => void;
  onClose: () => void;
};

// new state from saved exercise, or from new video or image like in upload page
export function AddStatePanel({ exercises, onAddExisting, onAddNew, onError, onReject, onClose }: Props) {
  const [exerciseId, setExerciseId] = useState("");
  const [uploading, setUploading] = useState(false);

  const addExisting = () => {
    const exercise = exercises.find((e) => e.id === exerciseId);
    if (!exercise) return;
    onAddExisting(exercise);
    setExerciseId("");
  };

  // video processed like in editor, image as single frame
  const addNew = async (file: File, range: VideoRange | null) => {
    setUploading(true);
    const name = nameFromFile(file);
    try {
      const { id } = file.type.startsWith("video/")
        ? await createExerciseFromVideo(file, range, { name, fps: DEFAULT_VIDEO_SETTINGS.fps, max_frames: DEFAULT_VIDEO_SETTINGS.maxFrames })
        : await createExerciseFromImage(file, name);
      onAddNew({ id, name });
      return true;
    } catch (err) {
      onError("Nahranie zlyhalo", err);
      return false;
    } finally {
      setUploading(false);
    }
  };

  return (
    <Card className="gap-5 px-6">
      <div className="flex items-start gap-3">
        <p className="text-sm font-medium text-foreground">Pridať stav</p>
        <Button variant="ghost" size="icon-sm" className="ml-auto -mt-1 -mr-2 shrink-0" onClick={onClose} aria-label="Zavrieť">
          <X className="h-4 w-4" />
        </Button>
      </div>

      <div className="space-y-2">
        <p className="text-xs font-medium text-muted-foreground">Existujúce cvičenie</p>
        <div className="flex flex-wrap gap-2">
          <ExerciseSelect
            className="max-w-sm"
            exercises={exercises}
            value={exerciseId}
            onValueChange={setExerciseId}
            placeholder="Vyberte cvičenie…"
            emptyText="Zatiaľ žiadne cvičenia"
          />
          <Button size="sm" onClick={addExisting} disabled={!exerciseId}>
            <Plus className="h-3.5 w-3.5" />
            Pridať
          </Button>
        </div>
      </div>

      <div className="space-y-2">
        <p className="text-xs font-medium text-muted-foreground">Nové cvičenie</p>
        <MediaUpload
          accept="video/*,image/*"
          formats="MP4, MOV, AVI, WEBM, JPG, PNG"
          submitLabel={uploading ? "Spracovanie…" : "Vytvoriť a pridať"}
          submitting={uploading}
          onSubmit={addNew}
          onReject={onReject}
        />
      </div>
    </Card>
  );
}
