import { useState } from "react";
import { Input } from "@/components/ui/input";
import { FileDropzone } from "@/components/ui/fileDropzone";
import { SelectedFileCard } from "@/components/ui/selectedFileCard";
import { VideoTrimmer } from "@/components/exercise/videoTrimmer";
import { useSelectedFile } from "@/hooks/useSelectedFile";
import type { UploadSettings } from "@/hooks/useExerciseEditor";
import type { VideoRange } from "@/lib/videoRange";

type Props = {
  settings: UploadSettings;
  onSettingsChange: (settings: UploadSettings) => void;
  uploading: boolean;
  onSelect: () => void;
  onReject: () => void;
  onUpload: (file: File, range: VideoRange | null) => void;
};

const clamp = (value: number, max: number) => Math.max(1, Math.min(max, value));

// Frame settings, then video drop zone, then range choice before upload
export function UploadPanel({ settings, onSettingsChange, uploading, onSelect, onReject, onUpload }: Props) {
  const pending = useSelectedFile();
  const [range, setRange] = useState<VideoRange | null>(null);

  const select = (file: File) => {
    onSelect();
    setRange(null);
    pending.select(file);
  };

  const clear = () => {
    pending.clear();
    setRange(null);
  };

  return (
    <>
      <div className="flex items-center gap-6">
        <label className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground whitespace-nowrap">Snímky za sekundu</span>
          <Input
            type="number"
            min={1}
            max={30}
            value={settings.fps}
            onChange={(e) => onSettingsChange({ ...settings, fps: clamp(Number(e.target.value), 30) })}
            className="h-7 w-16 px-2 text-center"
          />
        </label>
        <label className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground whitespace-nowrap">Max snímok</span>
          <Input
            type="number"
            min={1}
            max={200}
            value={settings.maxFrames}
            onChange={(e) => onSettingsChange({ ...settings, maxFrames: clamp(Number(e.target.value), 200) })}
            className="h-7 w-16 px-2 text-center"
          />
        </label>
      </div>

      {pending.file && pending.url ? (
        <SelectedFileCard
          file={pending.file}
          onClear={clear}
          onSubmit={() => onUpload(pending.file!, range)}
          submitLabel={uploading ? "Spracovanie videa…" : "Spracovať vybranú časť"}
          submitting={uploading}
          submitDisabled={!range}
        >
          <VideoTrimmer key={pending.url} src={pending.url} onChange={setRange} />
        </SelectedFileCard>
      ) : (
        <FileDropzone onFile={select} onReject={onReject} accept="video/*" formats="MP4, MOV, AVI, WEBM" />
      )}
    </>
  );
}
