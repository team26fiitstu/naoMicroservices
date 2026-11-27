import { Loader2 } from "lucide-react";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

// Card with spinner while page content loads
export function LoadingState({ text, className }: { text: string; className?: string }) {
  return (
    <Card className={cn("flex flex-col items-center justify-center gap-3 py-16", className)}>
      <Loader2 className="h-8 w-8 text-primary animate-spin" />
      <p className="text-sm text-muted-foreground">{text}</p>
    </Card>
  );
}
