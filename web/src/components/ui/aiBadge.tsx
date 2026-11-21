import { Badge } from "@/components/ui/badge";
import { LLM_AVAILABLE } from "@/lib/llm";

// Shows whether voice commands use LLM or keyword matching
export function AiBadge() {
  return LLM_AVAILABLE ? (
    <Badge className="bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400 px-1.5 py-0 text-[10px] font-medium">
      AI aktívna
    </Badge>
  ) : (
    <Badge variant="secondary" className="px-1.5 py-0 text-[10px] font-medium text-muted-foreground">
      Bez AI
    </Badge>
  );
}
