import { useState, useEffect } from "react";
import { FileUpload } from "@/components/ui/file-upload";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Loader2, AlertCircle, CheckCircle, X } from "lucide-react";

const NO_NAMING = true;
const API_BASE_URL = NO_NAMING? "http://127.0.0.1:7000" : ""; //(process.env.HOST_DOCKER_INTERNAL as string) + ":7000";

export default function SimpleUploadPage() {
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<{ type: "success" | "error" | null; message: string }>({ type: null, message: "" });

  useEffect(() => {
    return () => { if (previewUrl) URL.revokeObjectURL(previewUrl); };
  }, [previewUrl]);

  const handleFileUpload = (files: File[]) => {
    if (!files.length) return;
    const selected = files[0];
    setFile(selected);
    setUploadStatus({ type: null, message: "" });
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(URL.createObjectURL(selected));
  };

  const clearFile = () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setFile(null);
    setPreviewUrl(null);
    setUploadStatus({ type: null, message: "" });
  };

  const sendToBackend = async () => {
    if (!file) { setUploadStatus({ type: "error", message: "Najprv vyberte súbor" }); return; }
    setIsUploading(true);
    setUploadStatus({ type: null, message: "" });
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
      } else {
        formData.append("image", file);
        formData.append("name", exerciseName);
      }

      const url = isVideo ? `${API_BASE_URL}/exercise/from_video` : `${API_BASE_URL}/exercise/from_image`;
      console.log(url);
      const response = await fetch(url, {
        method: "POST",
        body: formData,
      });

      let responseData: any = null;
      try { responseData = await response.json(); } catch {}

      if (!response.ok) {
        const details = [responseData?.detail, responseData?.error, responseData?.message].filter(Boolean);
        throw new Error(`Chyba servera (${response.status}): ${details.join(" | ") || response.statusText}`);
      }

      setUploadStatus({ type: "success", message: `Cvičenie "${exerciseName}" bolo úspešne vytvorené!` });
    } catch (error) {
      setUploadStatus({ type: "error", message: error instanceof Error ? error.message : "Nahranie súboru zlyhalo" });
    } finally {
      setIsUploading(false);
    }
  };

  const isVideo = file?.type.startsWith("video/");

  return (
    <div className="w-full max-w-xl mx-auto px-4 py-6 pb-24 space-y-4">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-foreground">Jednoduché nahranie</h1>
        <p className="text-xs text-muted-foreground mt-0.5">Nahrajte video alebo obrázok a odošlite ho do API robota.</p>
      </div>

      <Card className="shadow-sm">
        <FileUpload onChange={handleFileUpload} />

        {file && previewUrl && (
          <div className="px-4 pb-4 space-y-3">
            <div className="relative bg-gray-100 rounded-lg overflow-hidden">
              <button onClick={clearFile} className="absolute top-2 right-2 z-10 bg-red-500 text-white rounded-full p-1 hover:bg-red-600 transition-colors">
                <X className="h-4 w-4" />
              </button>
              {isVideo
                ? <video src={previewUrl} controls className="w-full max-h-80 object-contain" />
                : <img src={previewUrl} alt="Náhľad" className="w-full max-h-80 object-contain" />
              }
            </div>
            <p className="text-xs text-muted-foreground">
              {file.name} · {(file.size / 1024 / 1024).toFixed(2)} MB · {isVideo ? "Video" : "Obrázok"}
            </p>
            <Button onClick={sendToBackend} disabled={isUploading} className="w-full text-white">
              {isUploading ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" />Nahrávanie…</> : "Odoslať do API"}
            </Button>
          </div>
        )}

        {uploadStatus.type && (
          <div className="px-4 pb-4">
            <Alert variant={uploadStatus.type === "error" ? "destructive" : "default"}
              className={uploadStatus.type === "success" ? "border-green-500 bg-green-50" : ""}>
              {uploadStatus.type === "error" ? <AlertCircle className="h-4 w-4" /> : <CheckCircle className="h-4 w-4 text-green-600" />}
              <AlertTitle>{uploadStatus.type === "error" ? "Chyba" : "Úspech"}</AlertTitle>
              <AlertDescription className="break-words">{uploadStatus.message}</AlertDescription>
            </Alert>
          </div>
        )}
      </Card>
    </div>
  );
}
