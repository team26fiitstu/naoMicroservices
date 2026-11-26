import { useState } from "react";
import { Check, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { NativeSelect } from "@/components/ui/native-select";
import { AiBadge } from "@/components/voice/aiBadge";
import { MicButton } from "@/components/voice/micButton";
import { TranscriptBlock } from "@/components/voice/transcriptBlock";
import { useSpeechRecognition, SPEECH_UNSUPPORTED } from "@/hooks/useSpeechRecognition";
import { poseLabel, type PoseCommand } from "@/lib/poses";
import { parseEditCommand, type EditCommand } from "@/lib/voiceEditCommand";

type Props = {
  poses: PoseCommand[];
  frameCount: number;
  onInsert: (position: number, poseName: string) => void;
  onClose: () => void;
};

// Spoken command like "vlož drep za snímku 3", confirmed before insert
export function VoiceEditPanel({ poses, frameCount, onInsert, onClose }: Props) {
  const { listening, transcript, start, stop: stopListening, reset: resetTranscript } = useSpeechRecognition();
  const [phase, setPhase] = useState<"idle" | "parsing" | "pick_pose" | "confirm" | "error">("idle");
  const [parsed, setParsed] = useState<EditCommand | null>(null);
  const [pickedPose, setPickedPose] = useState("");
  const [errorMsg, setErrorMsg] = useState("");

  const startListening = () => {
    if (!start()) { setErrorMsg(SPEECH_UNSUPPORTED); setPhase("error"); }
  };

  const recognize = async () => {
    if (!transcript.trim()) return;
    setPhase("parsing");
    const result = await parseEditCommand(transcript, poses, frameCount);
    if (!result) {
      setErrorMsg("Nepodarilo sa rozpoznať príkaz. Skúste znova.");
      setPhase("error");
      return;
    }
    setParsed(result);
    if (!result.pose) { setPickedPose(""); setPhase("pick_pose"); }
    else setPhase("confirm");
  };

  const confirm = (poseOverride?: string) => {
    if (!parsed) return;
    const pose = poseOverride ?? parsed.pose;
    if (!pose) return;
    const position = parsed.side === "after" ? parsed.frame : parsed.frame - 1;
    onInsert(position, pose);
    onClose();
  };

  const reset = () => { setPhase("idle"); setParsed(null); resetTranscript(); setPickedPose(""); };

  return (
    <Card className="gap-4 px-6">
      <div className="flex items-start gap-3">
        <div className="min-w-0">
          <p className="text-sm font-medium text-foreground">Hlasová úprava</p>
          <p className="text-xs text-muted-foreground mt-0.5 flex flex-wrap items-center gap-2">
            <span>Povedzte napr. <span className="italic">„vlož drep za snímku 3“</span>.</span>
            <AiBadge />
          </p>
        </div>
        <Button variant="ghost" size="icon-sm" className="ml-auto -mt-1 -mr-2 shrink-0" onClick={onClose} aria-label="Zavrieť">
          <X className="h-4 w-4" />
        </Button>
      </div>

      <div className="flex flex-col items-center gap-2 py-2">
        <MicButton size="md" listening={listening} onClick={listening ? stopListening : startListening} />
        <p className="text-xs text-muted-foreground">
          {listening ? "Počúvam… klepnite pre zastavenie" : "Klepnite pre hovorenie"}
        </p>
      </div>

      {(transcript || phase === "error") && (
        <TranscriptBlock
          transcript={transcript}
          pending={phase === "parsing"}
          error={phase === "error" ? errorMsg : undefined}
          result={
            phase === "confirm" && parsed?.pose ? (
              <p className="text-sm text-foreground">
                Vložiť <strong>{poseLabel(parsed.pose)}</strong> {parsed.side === "before" ? "pred" : "za"} snímku <strong>{parsed.frame}</strong>
              </p>
            ) : phase === "pick_pose" && parsed ? (
              // frame and side known, pose unclear
              <div className="space-y-2">
                <p className="text-sm text-foreground">
                  Snímka <strong>{parsed.frame}</strong>, {parsed.side === "before" ? "pred" : "za"}. Vyberte pózu:
                </p>
                <NativeSelect className="max-w-xs" value={pickedPose} onChange={(e) => setPickedPose(e.target.value)}>
                  <option value="" disabled>Póza…</option>
                  {poses.map((p) => (
                    <option key={p.name} value={p.name}>{poseLabel(p.name)}</option>
                  ))}
                </NativeSelect>
              </div>
            ) : null
          }
          actions={
            phase === "idle" && !listening ? (
              <>
                <Button size="sm" onClick={recognize}>Rozpoznať príkaz</Button>
                <Button size="sm" variant="outline" onClick={reset}>Zrušiť</Button>
              </>
            ) : phase === "confirm" || phase === "pick_pose" ? (
              <>
                <Button size="sm" disabled={phase === "pick_pose" && !pickedPose} onClick={() => confirm(phase === "pick_pose" ? pickedPose : undefined)}>
                  <Check className="h-3.5 w-3.5" />Potvrdiť
                </Button>
                <Button size="sm" variant="outline" onClick={reset}>Skúsiť znova</Button>
              </>
            ) : phase === "error" ? (
              <Button size="sm" variant="outline" onClick={reset}>Skúsiť znova</Button>
            ) : null
          }
        />
      )}
    </Card>
  );
}
