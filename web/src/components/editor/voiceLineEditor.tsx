import { Loader2, Mic, Play, Square } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import type { useFrameVoiceLine } from "@/hooks/useFrameVoiceLine";

type Props = {
  id: string;
  voice: ReturnType<typeof useFrameVoiceLine>;
};

// Text NAO says on frame, typed or dictated, with try on robot
export function VoiceLineEditor({ id, voice }: Props) {
  const { dictation } = voice;
  const dictationLabel = dictation === "recording" ? "Zastaviť diktovanie" : "Diktovať text";

  return (
    <div className="px-3 pt-5 pb-3 flex flex-col gap-2">
      <label htmlFor={id} className="text-xs font-medium text-foreground">
        Čo povie NAO
      </label>
      <Textarea
        id={id}
        placeholder="Napíšte alebo nadiktujte…"
        value={voice.text}
        onChange={(e) => voice.setText(e.target.value)}
        onBlur={voice.commit}
        disabled={dictation !== "idle"}
        className="min-h-18 resize-none px-2 py-1.5 text-xs md:text-xs"
      />
      <div className="flex items-center gap-1">
        <Button
          variant={dictation === "recording" ? "destructive" : "ghost"}
          size="icon-sm"
          onClick={voice.toggleDictation}
          disabled={dictation === "transcribing"}
          aria-label={dictationLabel}
          title={dictationLabel}
        >
          {dictation === "transcribing"
            ? <Loader2 className="h-4 w-4 animate-spin" />
            : dictation === "recording" ? <Square className="h-3.5 w-3.5" /> : <Mic className="h-4 w-4" />}
        </Button>
        <span className="truncate text-[11px] text-muted-foreground" aria-live="polite">
          {dictation === "recording" ? "Nahrávam…" : dictation === "transcribing" ? "Prepisujem…" : voice.saved ? "Uložené" : ""}
        </span>
        <Button variant="outline" size="sm" className="ml-auto shrink-0" onClick={voice.say} disabled={voice.saying}>
          {voice.saying ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
          Povedz
        </Button>
      </div>
    </div>
  );
}
