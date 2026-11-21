import { AlertCircle, CheckCircle, Info } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import type { Status } from "@/hooks/useStatus";

const STYLES = {
  success: { icon: CheckCircle, className: "border-green-500 bg-green-50 dark:bg-green-950/20 [&>svg]:text-green-600" },
  info: { icon: Info, className: "border-blue-500 bg-blue-50 dark:bg-blue-950/20 [&>svg]:text-blue-600" },
  error: { icon: AlertCircle, className: "" },
};

export function StatusAlert({ status }: { status: Status }) {
  if (!status) return null;
  const { icon: Icon, className } = STYLES[status.type];
  return (
    <Alert variant={status.type === "error" ? "destructive" : "default"} className={className}>
      <Icon className="h-4 w-4" />
      <AlertDescription className="break-words">{status.text}</AlertDescription>
    </Alert>
  );
}
