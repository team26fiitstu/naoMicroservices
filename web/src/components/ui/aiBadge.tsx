import { Badge } from "@/components/ui/badge";
import { LLM_AVAILABLE } from "@/lib/llm";

// Shows whether voice commands use LLM or keyword matching
export function AiBadge() {
  return LLM_AVAILABLE ? (
    <Badge className="bg-success/15 text-success px-1.5 py-0 text-[10px] font-medium">
      AI aktívna
    </Badge>
  ) : (
    <Badge variant="secondary" className="px-1.5 py-0 text-[10px] font-medium text-muted-foreground">
      Bez AI
    </Badge>
  );
}
