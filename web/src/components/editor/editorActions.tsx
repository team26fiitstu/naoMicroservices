import { Loader2, Mic, Play, Upload } from "lucide-react";
import { Button } from "@/components/ui/button";

type Props = {
  hasFrames: boolean;
  voiceEditOpen: boolean;
  running: boolean;
  onReset: () => void;
  onToggleVoiceEdit: () => void;
  onRun: () => void;
};

// Editor header buttons: new video, voice edit, run on robot
export function EditorActions({ hasFrames, voiceEditOpen, running, onReset, onToggleVoiceEdit, onRun }: Props) {
  return (
    <>
      <Button size="sm" variant="outline" onClick={onReset}>
        <Upload className="h-3.5 w-3.5" />
        Nahrať iné video
      </Button>
      <Button size="sm" variant={voiceEditOpen ? "secondary" : "outline"} onClick={onToggleVoiceEdit} disabled={!hasFrames}>
        <Mic className="h-3.5 w-3.5" />
        Hlasová úprava
      </Button>
      <Button size="sm" onClick={onRun} disabled={running || !hasFrames}>
        {running ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
        Spustiť na robotovi
      </Button>
    </>
  );
}
