import { useState, useCallback } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Loader2, CheckCircle2, XCircle, Clock, Play } from "lucide-react";
import { MicButton } from "@/components/ui/micButton";
import { POSE_LABELS, poseLabel, findPoses } from "@/lib/poses";
import { pluralSk } from "@/lib/plural";
import { api } from "@/lib/api";
import { useSpeechRecognition, SPEECH_UNSUPPORTED } from "@/hooks/useSpeechRecognition";
import { TranscriptBlock } from "@/components/ui/transcriptBlock";
import { askLlm, LLM_AVAILABLE } from "@/lib/llm";

const ALL_COMMANDS = Object.keys(POSE_LABELS);

async function interpretWithGPT(transcript: string): Promise<string[]> {
  const { commands } = await askLlm<{ commands: string[] }>(
    `You are a voice command parser for a NAO robot. The user speaks pose names (possibly in Slovak or with speech recognition errors). Map what they said to one or more of these exact command keys: ${ALL_COMMANDS.join(", ")}. Return ONLY a JSON object: {"commands": ["key1", "key2", ...]}. If nothing matches, return {"commands": []}. Preserve the order the user mentioned them.`,
    transcript,
  );
  return Array.isArray(commands) ? commands.filter((c) => ALL_COMMANDS.includes(c)) : [];
}

type QueueItem = {
  id: string;
  command: string;
  status: "pending" | "running" | "done" | "error";
  error?: string;
};

export function VoiceCommander() {
  const [detected, setDetected] = useState<string[]>([]);
  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isInterpreting, setIsInterpreting] = useState(false);

  const interpret = async (text: string) => {
    if (!text) return;
    if (!LLM_AVAILABLE) {
      setDetected(findPoses(text));
      return;
    }
    setIsInterpreting(true);
    try {
      const cmds = await interpretWithGPT(text);
      setDetected(cmds.length ? cmds : findPoses(text));
    } catch {
      setDetected(findPoses(text));
    } finally {
      setIsInterpreting(false);
    }
  };

  const { listening, transcript, start, stop: stopListening, reset } = useSpeechRecognition(interpret);

  const startListening = () => {
    setDetected([]);
    if (!start()) alert(SPEECH_UNSUPPORTED);
  };

  const clearResult = () => {
    reset();
    setDetected([]);
  };

  const executeQueue = useCallback(async (commands: string[]) => {
    if (!commands.length) return;

    const items: QueueItem[] = commands.map((cmd) => ({
      id: `${cmd}-${Date.now()}-${Math.random()}`,
      command: cmd,
      status: "pending",
    }));

    setQueue(items);
    setIsProcessing(true);

    for (let i = 0; i < items.length; i++) {
      setQueue((prev) =>
        prev.map((item, idx) => (idx === i ? { ...item, status: "running" } : item))
      );

      try {
        await api("/command", { method: "POST", json: { command: items[i].command } });

        setQueue((prev) =>
          prev.map((item, idx) => (idx === i ? { ...item, status: "done" } : item))
        );
      } catch (err) {
        setQueue((prev) =>
          prev.map((item, idx) =>
            idx === i
              ? { ...item, status: "error", error: err instanceof Error ? err.message : "Neznáma chyba" }
              : item
          )
        );
      }
    }

    setIsProcessing(false);
  }, []);

  return (
    <Card className="shadow-lg overflow-hidden">
      <div className="flex flex-col items-center gap-4 px-5 py-6">
        <MicButton listening={listening} onClick={listening ? stopListening : startListening} disabled={isProcessing} />

        <p className="text-xs text-muted-foreground">
          {listening ? "Počúvam… klepnite pre zastavenie" : "Klepnite pre hovorenie"}
        </p>
      </div>

      {transcript && (
        <TranscriptBlock
          className="px-5 pb-6"
          transcript={transcript}
          pending={isInterpreting}
          error={!listening && detected.length === 0 ? "Nerozpoznala sa žiadna póza." : undefined}
          result={detected.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {detected.map((cmd, i) => (
                <Badge key={i} variant="outline" className="gap-1 py-1 px-2.5 text-xs font-normal">
                  <span className="text-muted-foreground tabular-nums">{i + 1}.</span>
                  {poseLabel(cmd)}
                </Badge>
              ))}
            </div>
          )}
          actions={!listening && !isInterpreting && (
            detected.length > 0 ? (
              <>
                <Button size="sm" onClick={() => executeQueue(detected)} disabled={isProcessing}>
                  {isProcessing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
                  {isProcessing ? "Vykonávanie…" : `Vykonať ${detected.length} ${pluralSk(detected.length, "príkaz", "príkazy", "príkazov")}`}
                </Button>
                <Button size="sm" variant="outline" onClick={clearResult} disabled={isProcessing}>Zrušiť</Button>
              </>
            ) : (
              <Button size="sm" variant="outline" onClick={clearResult}>Skúsiť znova</Button>
            )
          )}
        />
      )}

      {queue.length > 0 && (
        <div className="mx-5 mb-5">
          <p className="text-xs font-medium text-muted-foreground mb-2">Priebeh</p>
          <div className="flex flex-col gap-1.5">
            {queue.map((item) => (
              <div
                key={item.id}
                className={[
                  "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors duration-200 border",
                  item.status === "running" ? "bg-primary/10 border-primary/20" : "",
                  item.status === "done"    ? "bg-success/10 border-success/20" : "",
                  item.status === "error"   ? "bg-destructive/10 border-destructive/20" : "",
                  item.status === "pending" ? "bg-muted/40 border-border/40" : "",
                ].join(" ")}
              >
                <span className="flex-shrink-0">
                  {item.status === "pending" && <Clock        className="h-3.5 w-3.5 text-muted-foreground" />}
                  {item.status === "running" && <Loader2      className="h-3.5 w-3.5 text-primary animate-spin" />}
                  {item.status === "done"    && <CheckCircle2 className="h-3.5 w-3.5 text-success" />}
                  {item.status === "error"   && <XCircle      className="h-3.5 w-3.5 text-destructive" />}
                </span>
                <span className="font-medium flex-1">{poseLabel(item.command)}</span>
                <span className="text-xs text-muted-foreground">
                  {item.status === "pending" ? "čaká" : item.status === "running" ? "odosiela…" : item.status === "done" ? "hotovo" : "chyba"}
                </span>
                {item.error && (
                  <span className="text-xs text-destructive truncate max-w-[120px]" title={item.error}>
                    {item.error}
                  </span>
                )}
              </div>
            ))}
          </div>
          {!isProcessing && (
            <Button
              variant="outline" size="sm"
              className="mt-3"
              onClick={() => { setQueue([]); clearResult(); }}
            >
              Vymazať
            </Button>
          )}
        </div>
      )}

      {!transcript && queue.length === 0 && (
        <div className="flex flex-col gap-1.5 px-5 pb-6">
          <p className="text-xs font-medium text-muted-foreground">Dostupné pózy</p>
          <div className="flex flex-wrap gap-1.5">
            {Object.values(POSE_LABELS).map((name) => (
              <Badge key={name} variant="outline" className="py-1 px-2.5 text-xs font-normal text-muted-foreground">
                {name}
              </Badge>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}