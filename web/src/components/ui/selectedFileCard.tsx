import type { ReactNode } from "react";
import { Film, Image as ImageIcon, Loader2, Upload, X } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

type Props = {
  file: File;
  onClear: () => void;
  onSubmit: () => void;
  submitLabel: string;
  submitting: boolean;
  submitDisabled?: boolean;
  children: ReactNode;
};

// Chosen file with preview, waiting for submit
export function SelectedFileCard({ file, onClear, onSubmit, submitLabel, submitting, submitDisabled, children }: Props) {
  const isVideo = file.type.startsWith("video/");
  const Icon = isVideo ? Film : ImageIcon;

  return (
    <Card className="gap-4 px-6">
      <div className="flex items-start gap-3">
        <Icon className="h-4 w-4 mt-0.5 shrink-0 text-muted-foreground" />
        <div className="min-w-0">
          <p className="text-sm font-medium text-foreground truncate">{file.name}</p>
          <p className="text-xs text-muted-foreground mt-0.5">
            {isVideo ? "Video" : "Obrázok"}, {(file.size / 1024 / 1024).toFixed(2)} MB
          </p>
        </div>
        <Button
          variant="ghost"
          size="icon-sm"
          className="ml-auto -mt-1 -mr-2 shrink-0"
          onClick={onClear}
          disabled={submitting}
          aria-label="Zrušiť"
        >
          <X className="h-4 w-4" />
        </Button>
      </div>

      {children}

      <Button onClick={onSubmit} disabled={submitting || submitDisabled} className="w-full">
        {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
        {submitLabel}
      </Button>
    </Card>
  );
}
