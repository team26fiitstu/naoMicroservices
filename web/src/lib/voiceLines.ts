// Stored for frame without text, robot API checks this exact value
export const NO_VOICE_TEXT = "Nothing so far";

export const hasVoiceText = (text?: string) => !!text && text.trim() !== "" && text !== NO_VOICE_TEXT;

// Frame voice lines as stored by exerciseConfigService and read by robot
export type VoiceLinesConfig = {
  extractedText?: string;
  lang?: string;
  speed?: number;
  voice_lines_configs?: Record<string, { translation?: string; wait?: number }>;
};

// Typed text, or older recorded lines joined
export const voiceTextFromConfig = (config: VoiceLinesConfig) =>
  hasVoiceText(config.extractedText)
    ? config.extractedText!
    : Object.values(config.voice_lines_configs ?? {})
        .map((line) => line.translation)
        .filter(Boolean)
        .join(" ");

// NAOqi language names
export const SPEECH_LANGUAGES: [string, string][] = [
  ["English", "Angličtina"],
  ["Czech", "Čeština"],
  ["Chinese", "Čínština"],
  ["Russian", "Ruština"],
];
export const SPEECH_SPEEDS = [25, 50, 75, 100];
export const DEFAULT_SPEECH_LANGUAGE = "English";
export const DEFAULT_SPEECH_SPEED = 100;

export const blobToBase64 = (blob: Blob) =>
  new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split("base64,")[1] ?? "");
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(blob);
  });
