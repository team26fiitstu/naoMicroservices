import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/emptyState";
import { LoadingState } from "@/components/ui/loadingState";
import { StatusAlert } from "@/components/ui/statusAlert";
import { Page } from "@/components/layout/page";
import { EditorActions } from "@/components/editor/editorActions";
import { ExerciseInfo } from "@/components/editor/exerciseInfo";
import { FrameList } from "@/components/editor/frameList";
import { UploadPanel } from "@/components/editor/uploadPanel";
import { VoiceEditPanel } from "@/components/editor/voiceEditPanel";
import { useExerciseEditor, type UploadSettings } from "@/hooks/useExerciseEditor";
import { DEFAULT_VIDEO_SETTINGS } from "@/lib/exercises";

// Video to frames, frame editing and run on robot, ?id= opens saved exercise
export default function ExerciseEditor() {
  const [searchParams] = useSearchParams();
  const editor = useExerciseEditor(searchParams.get("id"));
  const [settings, setSettings] = useState<UploadSettings>(DEFAULT_VIDEO_SETTINGS);
  const [voiceEditOpen, setVoiceEditOpen] = useState(false);
  const { exerciseId, frames, loadingFrames } = editor;

  return (
    <Page
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
    >
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

      {loadingFrames && <LoadingState text="Načítavam snímky…" />}

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
        <EmptyState
          text="Nenašli sa žiadne snímky."
          action={<Button variant="outline" size="sm" onClick={() => editor.loadFrames(exerciseId)}>Skúsiť znova</Button>}
        />
      )}
    </Page>
  );
}
