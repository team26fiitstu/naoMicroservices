import type { ReactNode } from "react";
import { Film, type LucideIcon } from "lucide-react";
import { Card } from "@/components/ui/card";

// Card shown when there is nothing to list, with action to continue
export function EmptyState({ text, action, icon: Icon = Film }: { text: string; action: ReactNode; icon?: LucideIcon }) {
  return (
    <Card className="flex flex-col items-center justify-center gap-3 py-16">
      <Icon className="h-8 w-8 text-muted-foreground opacity-40" />
      <p className="text-sm text-muted-foreground">{text}</p>
      {action}
    </Card>
  );
}
