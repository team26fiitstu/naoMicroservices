import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { failureText } from "@/lib/errors";
import type { StatusType } from "@/hooks/useStatus";
import {
  NO_VOICE_TEXT,
  hasVoiceText,
  voiceTextFromConfig,
  blobToBase64,
  DEFAULT_SPEECH_LANGUAGE,
  DEFAULT_SPEECH_SPEED,
  type VoiceLinesConfig,
} from "@/lib/voiceLines";

export type Dictation = "idle" | "recording" | "transcribing";

// What NAO says on frame, saved on blur, after dictation and on voice change
export function useFrameVoiceLine(
  exerciseId: string,
  frameIdx: number,
  showStatus: (type: StatusType, text: string) => void,
) {
  const [text, setText] = useState("");
  const [language, setLanguage] = useState<string>(DEFAULT_SPEECH_LANGUAGE);
  const [speed, setSpeed] = useState<number>(DEFAULT_SPEECH_SPEED);
  const [saved, setSaved] = useState(false);
  const [dictation, setDictation] = useState<Dictation>("idle");
  const [saying, setSaying] = useState(false);
  const savedText = useRef("");
  const recorder = useRef<MediaRecorder | null>(null);
  const configPath = `/voiceLines/config/exercise/${exerciseId}/frame/${frameIdx}`;

  useEffect(() => {
    api<VoiceLinesConfig>(configPath)
      .catch((): VoiceLinesConfig => ({}))
      .then((config) => {
        const loaded = voiceTextFromConfig(config);
        savedText.current = loaded;
        setText(loaded);
        if (config.lang) setLanguage(config.lang);
        if (config.speed !== undefined) setSpeed(Number(config.speed));
      });
  }, [configPath]);

  // release microphone when card unmounts mid-recording
  useEffect(() => () => recorder.current?.stream.getTracks().forEach((track) => track.stop()), []);

  // field is the only source: saving drops older recorded lines, so a cleared field means silence
  const save = async (value: string, lang = language, rate = speed) => {
    const config: VoiceLinesConfig = { extractedText: hasVoiceText(value) ? value : NO_VOICE_TEXT, lang, speed: rate };
    try {
      await api(configPath, { method: "POST", json: { voice_lines: config } });
      savedText.current = value;
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (err) {
      showStatus("error", failureText("Uloženie textu zlyhalo", err));
    }
  };

  // on blur, only when changed
  const commit = () => {
    if (text !== savedText.current) save(text);
  };

  const changeVoice = (lang: string, rate: number) => {
    setLanguage(lang);
    setSpeed(rate);
    save(text, lang, rate);
  };

  // record voice, transcribe, append text to field
  const toggleDictation = async () => {
    if (dictation === "recording") {
      recorder.current?.stop();
      return;
    }
    if (typeof MediaRecorder === "undefined" || !MediaRecorder.isTypeSupported("audio/webm")) {
      showStatus("error", "Diktovanie nie je v tomto prehliadači podporované. Použite Chrome alebo Edge.");
      return;
    }
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      showStatus("error", "Mikrofón nie je dostupný.");
      return;
    }
    const chunks: Blob[] = [];
    const mediaRecorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
    mediaRecorder.ondataavailable = (e) => chunks.push(e.data);
    mediaRecorder.onstop = async () => {
      stream.getTracks().forEach((track) => track.stop());
      setDictation("transcribing");
      try {
        const audio = await blobToBase64(new Blob(chunks, { type: "audio/webm" }));
        const { translation } = await api<{ translation?: string }>("/translate/webm", {
          method: "POST",
          json: { audio_file: audio, model: "large-v1" },
        });
        if (translation) {
          const next = text.trim() ? `${text.trim()} ${translation}` : translation;
          setText(next);
          save(next);
        } else {
          showStatus("info", "Nič sa nerozpoznalo.");
        }
      } catch (err) {
        showStatus("error", failureText("Prepis reči zlyhal", err));
      } finally {
        setDictation("idle");
      }
    };
    recorder.current = mediaRecorder;
    mediaRecorder.start();
    setDictation("recording");
  };

  // robot says text now, nothing saved
  const say = async () => {
    if (!hasVoiceText(text)) {
      showStatus("info", "Najprv napíšte, čo má robot povedať.");
      return;
    }
    setSaying(true);
    try {
      await api("/voiceLines/applyVoiceLine", {
        method: "POST",
        json: { voice_lines: { voice_lines_configs: { entire: { translation: text } }, lang: language, speed } },
      });
    } catch (err) {
      showStatus("error", failureText("Robot nemohol hovoriť", err));
    } finally {
      setSaying(false);
    }
  };

  return { text, setText, language, speed, saved, dictation, saying, commit, changeVoice, toggleDictation, say };
}
