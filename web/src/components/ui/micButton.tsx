import { Mic, MicOff } from "lucide-react";
import { cn } from "@/lib/utils";

type Props = {
  listening: boolean;
  onClick: () => void;
  disabled?: boolean;
  size?: "md" | "lg";
};

// Round microphone button, red with pulse while listening
export function MicButton({ listening, onClick, disabled, size = "lg" }: Props) {
  const icon = size === "lg" ? "h-8 w-8" : "h-6 w-6";
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      aria-label={listening ? "Zastaviť počúvanie" : "Začať počúvanie"}
      className={cn(
        "relative rounded-full flex items-center justify-center shadow-md transition-all duration-200",
        "disabled:opacity-50 disabled:cursor-not-allowed",
        size === "lg" ? "w-20 h-20" : "w-14 h-14",
        listening ? "bg-destructive hover:bg-destructive/90 shadow-lg scale-105" : "bg-primary hover:bg-primary/90",
      )}
    >
      {listening && <span className="absolute inset-0 rounded-full bg-destructive/40 animate-ping" />}
      {listening ? <MicOff className={cn(icon, "text-white")} /> : <Mic className={cn(icon, "text-primary-foreground")} />}
    </button>
  );
}
