import type { ReactNode } from "react";
import { AlertCircle, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

type Props = {
  transcript?: string;
  pending?: boolean;
  result?: ReactNode;
  error?: string;
  actions?: ReactNode;
  className?: string;
};

// Voice command outcome: what was said, what was recognized, actions
export function TranscriptBlock({ transcript, pending, result, error, actions, className }: Props) {
  return (
    <div className={cn("flex flex-col gap-4", className)}>
      {transcript && (
        <Section label="Povedané">
          <p className="text-sm text-foreground">„{transcript}“</p>
        </Section>
      )}
      {(pending || error || result) && (
        <Section label="Rozpoznané">
          {pending ? (
            <p className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Rozpoznávam…
            </p>
          ) : error ? (
            <p className="flex items-center gap-2 text-sm text-destructive">
              <AlertCircle className="h-4 w-4 shrink-0" />
              {error}
            </p>
          ) : (
            result
          )}
        </Section>
      )}
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}

function Section({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="space-y-1.5">
      <p className="text-xs font-medium text-muted-foreground">{label}</p>
      {children}
    </div>
  );
}
