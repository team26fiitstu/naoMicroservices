import { useState } from "react";
import { FileDropzone } from "@/components/ui/fileDropzone";
import { SelectedFileCard } from "@/components/ui/selectedFileCard";
import { VideoTrimmer } from "@/components/exercise/videoTrimmer";
import { useSelectedFile } from "@/hooks/useSelectedFile";
import type { VideoRange } from "@/lib/videoRange";

type Props = {
  accept: string;
  formats: string;
  submitLabel: string;
  submitting: boolean;
  // resolves true when processed, file is then cleared so it is not sent twice
  onSubmit: (file: File, range: VideoRange | null) => Promise<boolean>;
  onSelect?: () => void;
  // chosen file removed by user
  onClear?: () => void;
  onReject: () => void;
};

// Drop zone, then chosen file with range for video or preview for image, then submit
export function MediaUpload({ accept, formats, submitLabel, submitting, onSubmit, onSelect, onClear, onReject }: Props) {
  const { file, url, select, clear } = useSelectedFile();
  const [range, setRange] = useState<VideoRange | null>(null);
  const isVideo = file?.type.startsWith("video/");

  const choose = (next: File) => {
    onSelect?.();
    setRange(null);
    select(next);
  };

  const reset = () => {
    clear();
    setRange(null);
  };

  if (!file || !url) {
    return <FileDropzone onFile={choose} onReject={onReject} accept={accept} formats={formats} />;
  }
  return (
    <SelectedFileCard
      file={file}
      onClear={() => { reset(); onClear?.(); }}
      onSubmit={async () => { if (await onSubmit(file, range)) reset(); }}
      submitLabel={submitLabel}
      submitting={submitting}
      // video waits for its range, otherwise the whole video would be processed
      submitDisabled={isVideo && !range}
    >
      {isVideo
        ? <VideoTrimmer key={url} src={url} onChange={setRange} />
        : <img src={url} alt="Náhľad" className="w-full max-h-80 object-contain rounded-base bg-muted" />}
    </SelectedFileCard>
  );
}
