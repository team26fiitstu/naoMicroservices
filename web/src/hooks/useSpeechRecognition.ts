import { useEffect, useRef, useState } from "react";

// Subset of the Web Speech API used here; TypeScript has no built-in types for it
type RecognitionEvent = { results: ArrayLike<ArrayLike<{ transcript: string }>> };
type Recognition = {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onstart: () => void;
  onresult: (event: RecognitionEvent) => void;
  onend: () => void;
  onerror: () => void;
  start: () => void;
  stop: () => void;
};
type RecognitionConstructor = new () => Recognition;

const recognitionConstructor = () => {
  const speechWindow = window as Window & {
    SpeechRecognition?: RecognitionConstructor;
    webkitSpeechRecognition?: RecognitionConstructor;
  };
  return speechWindow.SpeechRecognition ?? speechWindow.webkitSpeechRecognition;
};

export const SPEECH_UNSUPPORTED = "Rozpoznávanie hlasu nie je podporované. Použite Chrome alebo Edge.";

// One Slovak utterance via browser speech recognition, onEnd gets the final text
export function useSpeechRecognition(onEnd?: (transcript: string) => void) {
  const [listening, setListening] = useState(false);
  const [transcript, setTranscript] = useState("");
  const recognition = useRef<Recognition | null>(null);
  const onEndRef = useRef(onEnd);

  useEffect(() => {
    onEndRef.current = onEnd;
  });

  // false when the browser has no speech recognition
  const start = () => {
    const Constructor = recognitionConstructor();
    if (!Constructor) return false;
    const rec = new Constructor();
    let text = "";
    rec.continuous = false;
    rec.interimResults = true;
    rec.lang = "sk-SK";
    rec.onstart = () => {
      setTranscript("");
      setListening(true);
    };
    rec.onresult = (event) => {
      text = Array.from(event.results, (result) => result[0].transcript).join("");
      setTranscript(text);
    };
    rec.onend = () => {
      setListening(false);
      onEndRef.current?.(text.trim());
    };
    rec.onerror = () => setListening(false);
    recognition.current = rec;
    rec.start();
    return true;
  };

  const stop = () => recognition.current?.stop();
  const reset = () => setTranscript("");

  return { listening, transcript, start, stop, reset };
}
