import { AlertCircle, CheckCircle, Info } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import type { Status } from "@/hooks/useStatus";

const STYLES = {
  success: { icon: CheckCircle, className: "border-success/50 bg-success/10 [&>svg]:text-success" },
  info: { icon: Info, className: "border-info/50 bg-info/10 [&>svg]:text-info" },
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
