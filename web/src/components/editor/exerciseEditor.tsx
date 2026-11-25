import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Film, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { StatusAlert } from "@/components/ui/statusAlert";
import { PageHeader } from "@/components/layout/pageHeader";
import { EditorActions } from "@/components/editor/editorActions";
import { ExerciseInfo } from "@/components/editor/exerciseInfo";
import { FrameList } from "@/components/editor/frameList";
import { UploadPanel } from "@/components/editor/uploadPanel";
import { VoiceEditPanel } from "@/components/editor/voiceEditPanel";
import { useExerciseEditor, type UploadSettings } from "@/hooks/useExerciseEditor";

// Video to frames, frame editing and run on robot, ?id= opens saved exercise
export default function ExerciseEditor() {
  const [searchParams] = useSearchParams();
  const editor = useExerciseEditor(searchParams.get("id"));
  const [settings, setSettings] = useState<UploadSettings>({ fps: 1, maxFrames: 8 });
  const [voiceEditOpen, setVoiceEditOpen] = useState(false);
  const { exerciseId, frames, loadingFrames } = editor;

  return (
    <div className="w-full max-w-7xl mx-auto px-4 py-6 pb-24 space-y-6">
      <PageHeader
        title="Editor"
        description="Nahrajte video, upravte snímky, spustite na robotovi."
        actions={exerciseId && (
          <EditorActions
            hasFrames={frames.length > 0}
            voiceEditOpen={voiceEditOpen}
            running={editor.running}
            onReset={editor.reset}
            onToggleVoiceEdit={() => setVoiceEditOpen((open) => !open)}
            onRun={editor.run}
          />
        )}
      />

      <StatusAlert status={editor.status} />

      {voiceEditOpen && exerciseId && (
        <VoiceEditPanel
          poses={editor.poses}
          frameCount={frames.length}
          onInsert={editor.insertPose}
          onClose={() => setVoiceEditOpen(false)}
        />
      )}

      {!exerciseId && (
        <UploadPanel
          settings={settings}
          onSettingsChange={setSettings}
          uploading={editor.uploading}
          onSelect={editor.clearStatus}
          onReject={() => editor.showStatus("error", "Prosím vyberte video súbor.")}
          onUpload={(file, range) => editor.upload(file, range, settings)}
        />
      )}

      {exerciseId && (
        <ExerciseInfo
          name={editor.exerciseName}
          onRename={editor.rename}
          calories={editor.calories}
          caloriesLoading={editor.caloriesLoading}
          description={editor.description}
          descLoading={editor.descLoading}
        />
      )}

      {loadingFrames && (
        <Card className="flex items-center justify-center py-16">
          <div className="flex flex-col items-center gap-3">
            <Loader2 className="h-8 w-8 text-primary animate-spin" />
            <p className="text-sm text-muted-foreground">Načítavam snímky…</p>
          </div>
        </Card>
      )}

      {!loadingFrames && exerciseId && frames.length > 0 && (
        <FrameList
          frames={frames}
          exerciseId={exerciseId}
          poses={editor.poses}
          insertingAt={editor.insertingAt}
          deletingAt={editor.deletingAt}
          onInsert={editor.insertPose}
          onDelete={editor.deleteFrame}
          onReorder={editor.reorderFrames}
          showStatus={editor.showStatus}
        />
      )}

      {!loadingFrames && exerciseId && frames.length === 0 && (
        <Card className="flex flex-col items-center justify-center py-16 gap-3">
          <Film className="h-8 w-8 text-muted-foreground opacity-40" />
          <p className="text-sm text-muted-foreground">Nenašli sa žiadne snímky.</p>
          <Button variant="outline" size="sm" onClick={() => editor.loadFrames(exerciseId)}>
            Skúsiť znova
          </Button>
        </Card>
      )}
    </div>
  );
}
