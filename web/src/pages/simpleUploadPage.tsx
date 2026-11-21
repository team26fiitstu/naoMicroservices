import { useState } from "react";
import { FileDropzone } from "@/components/ui/fileDropzone";
import { SelectedFileCard } from "@/components/ui/selectedFileCard";
import { StatusAlert } from "@/components/ui/statusAlert";
import { PageHeader } from "@/components/layout/pageHeader";
import { useStatus } from "@/hooks/useStatus";
import { failureText } from "@/lib/errors";
import { VideoTrimmer } from "@/components/ui/videoTrimmer";
import { appendVideoRange, type VideoRange } from "@/lib/videoRange";
import { useSelectedFile } from "@/hooks/useSelectedFile";

const API_BASE_URL = "http://127.0.0.1:7000"; //(process.env.HOST_DOCKER_INTERNAL as string) + ":7000";

export default function SimpleUploadPage() {
  const { file, url: previewUrl, select, clear } = useSelectedFile();
  const [isUploading, setIsUploading] = useState(false);
  const [videoRange, setVideoRange] = useState<VideoRange | null>(null);
  const { status, show: showStatus, clear: clearStatus } = useStatus();

  const selectFile = (selected: File) => {
    select(selected);
    setVideoRange(null);
    clearStatus();
  };

  const clearFile = () => {
    clear();
    setVideoRange(null);
    clearStatus();
  };

  const sendToBackend = async () => {
    if (!file) { showStatus("error", "Najprv vyberte súbor."); return; }
    setIsUploading(true);
    clearStatus();
    try {
      const isVideo = file.type.startsWith("video/");
      const isImage = file.type.startsWith("image/");
      if (!isVideo && !isImage) throw new Error("Nahrajte platný video alebo obrázkový súbor");

      const exerciseName = file.name.replace(/\.[^/.]+$/, "");
      const formData = new FormData();
      if (isVideo) {
        formData.append("video", file);
        formData.append("name", exerciseName);
        formData.append("fps", "1");
        formData.append("seconds", "-1");
        appendVideoRange(formData, videoRange);
      } else {
        formData.append("image", file);
        formData.append("name", exerciseName);
      }

      const url = isVideo ? `${API_BASE_URL}/exercise/from_video` : `${API_BASE_URL}/exercise/from_image`;
      const response = await fetch(url, {
        method: "POST",
        body: formData,
      });

      const responseData = await response.json().catch(() => null);

      if (!response.ok) {
        const details = [responseData?.detail, responseData?.error, responseData?.message].filter(Boolean);
        throw new Error(`HTTP ${response.status}${details.length ? `, ${details.join(", ")}` : ""}`);
      }

      showStatus("success", `Cvičenie „${exerciseName}“ bolo vytvorené.`);
    } catch (error) {
      showStatus("error", failureText("Nahranie zlyhalo", error));
    } finally {
      setIsUploading(false);
    }
  };

  const isVideo = file?.type.startsWith("video/");

  return (
    <div className="w-full max-w-7xl mx-auto px-4 py-6 pb-24 space-y-4">
      <PageHeader title="Nahranie" description="Nahrajte video alebo obrázok a vytvorte z neho cvičenie." />
      <StatusAlert status={status} />

      {!file || !previewUrl ? (
        <FileDropzone
          onFile={selectFile}
          accept="video/*,image/*"
          formats="MP4, MOV, AVI, WEBM, JPG, PNG"
        />
      ) : (
        <SelectedFileCard
          file={file}
          onClear={clearFile}
          onSubmit={sendToBackend}
          submitLabel={isUploading ? "Nahrávanie…" : "Odoslať do API"}
          submitting={isUploading}
          // video waits for its range, otherwise the whole video would be processed
          submitDisabled={isVideo && !videoRange}
        >
          {isVideo
            ? <VideoTrimmer key={previewUrl} src={previewUrl} onChange={setVideoRange} />
            : <img src={previewUrl} alt="Náhľad" className="w-full max-h-80 object-contain rounded-lg bg-muted" />}
        </SelectedFileCard>
      )}
    </div>
  );
}
