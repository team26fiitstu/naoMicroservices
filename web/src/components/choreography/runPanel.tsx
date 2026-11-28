import { ArrowRight, Loader2, Square } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import type { Choreography } from "@/lib/choreography";
import { runErrorText, type RunSnapshot } from "@/lib/choreographyRun";

type Props = {
  graph: Choreography;
  run: RunSnapshot;
  sending: boolean;
  onSignal: (transitionId: string) => void;
  onStop: () => void;
};

// run control instead of state details: current state, next transitions as buttons, stop
export function RunPanel({ graph, run, sending, onSignal, onStop }: Props) {
  const label = (stateId: string) => graph.states.find((s) => s.state_id === stateId)?.label ?? stateId;
  const waiting = run.status === "waiting";

  return (
    <Card className="gap-4 px-5 py-4">
      <div className="space-y-1">
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
          {waiting ? "Čaká na signál" : <><Loader2 className="h-3.5 w-3.5 animate-spin text-success" />Vykonáva sa</>}
        </p>
        <p className="text-sm font-medium text-foreground">{label(run.state_id)}</p>
        {run.error && <p className="text-xs text-destructive">{runErrorText(run.error)}</p>}
      </div>

      <div className="space-y-2">
        <p className="text-xs font-medium text-muted-foreground">Prechody</p>
        {run.outgoing_transitions.length === 0 && (
          <p className="text-xs text-muted-foreground">Zo stavu nevedie žiadny prechod.</p>
        )}
        {run.outgoing_transitions.map((t) => (
          <Button key={t.id} size="sm" variant="outline" className="w-full justify-start" disabled={!waiting || sending} onClick={() => onSignal(t.id)}>
            <span className="truncate">{t.label}</span>
            <ArrowRight className="ml-auto h-3.5 w-3.5 shrink-0 text-muted-foreground" />
            <span className="max-w-24 truncate text-muted-foreground">{label(t.to)}</span>
          </Button>
        ))}
      </div>

      <p className="text-xs leading-relaxed text-muted-foreground">Klik na stav v grafe ho nastaví bez vykonania.</p>

      <Button size="sm" variant="outline" onClick={onStop} disabled={sending}>
        <Square className="h-3.5 w-3.5" />
        Zastaviť
      </Button>
    </Card>
  );
}
