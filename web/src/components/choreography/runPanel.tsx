import { ArrowRight, CircleDashed, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { stateLabel, type Choreography } from "@/lib/choreography";
import { runErrorText, type RunSnapshot } from "@/lib/choreographyRun";

type Props = {
  graph: Choreography;
  run: RunSnapshot;
  sending: boolean;
  onSignal: (transitionId: string) => void;
};

// run control instead of state details: current state, next transitions as buttons
export function RunPanel({ graph, run, sending, onSignal }: Props) {
  const waiting = run.status === "waiting";

  return (
    <Card className="gap-4 px-5 py-4">
      <div className="space-y-1">
        <p className="text-sm font-medium text-foreground">{stateLabel(graph, run.state_id)}</p>
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
          {waiting ? <CircleDashed className="h-3.5 w-3.5" /> : <Loader2 className="h-3.5 w-3.5 animate-spin text-success" />}
          {waiting ? "Čaká na signál" : "Vykonáva sa"}
        </p>
        {run.error && <p className="text-xs text-destructive">{runErrorText(run.error)}</p>}
      </div>

      <div className="space-y-2">
        <p className="text-xs font-medium text-muted-foreground">Prechody</p>
        {run.outgoing_transitions.length === 0 && (
          <p className="text-xs text-muted-foreground">Zo stavu nevedie žiadny prechod.</p>
        )}
        {run.outgoing_transitions.map((t) => (
          <Button key={t.id} size="sm" variant="outline" className="w-full justify-start" disabled={!waiting || sending} onClick={() => onSignal(t.id)}>
            <span className="max-w-[50%] shrink-0 truncate">{t.label}</span>
            <ArrowRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
            <span className="min-w-0 truncate text-muted-foreground">{stateLabel(graph, t.to)}</span>
          </Button>
        ))}
      </div>
    </Card>
  );
}
