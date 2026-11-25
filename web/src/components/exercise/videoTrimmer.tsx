import { useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { isTrimmed, WHOLE_VIDEO, type VideoRange } from "@/lib/videoRange";

type Props = {
  src: string;
  onChange: (range: VideoRange) => void;
};

// Shortest selectable range, seconds
const MIN_LENGTH = 0.1;

// m:ss.s, e.g. 1:05.3
const formatTime = (seconds: number) => {
  const tenths = Math.round(seconds * 10);
  const minutes = Math.floor(tenths / 600);
  const rest = ((tenths % 600) / 10).toFixed(1).padStart(4, "0");
  return `${minutes}:${rest}`;
};

// Video preview with start/end range, playback kept inside range; render with key={src} to reset
export function VideoTrimmer({ src, onChange }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [duration, setDuration] = useState(0);
  const [start, setStart] = useState(0);
  const [end, setEnd] = useState(0);
  const [current, setCurrent] = useState(0);
  const [unavailable, setUnavailable] = useState(false);

  const select = (nextStart: number, nextEnd: number, total = duration) => {
    setStart(nextStart);
    setEnd(nextEnd);
    onChange({ start: nextStart, end: nextEnd, duration: total });
  };

  const seek = (time: number) => {
    if (videoRef.current) videoRef.current.currentTime = time;
    setCurrent(time);
  };

  // server can still decode videos the browser cannot play
  const markUnavailable = () => {
    setUnavailable(true);
    onChange(WHOLE_VIDEO);
  };

  const onLoadedMetadata = () => {
    const total = videoRef.current?.duration ?? 0;
    if (!Number.isFinite(total) || total <= 0) return markUnavailable();
    setDuration(total);
    select(0, total, total);
  };

  const onTimeUpdate = () => {
    const video = videoRef.current;
    if (!video) return;
    setCurrent(video.currentTime);
    if (!video.paused && video.currentTime >= end) {
      video.pause();
      video.currentTime = end;
    }
  };

  // playback always starts inside range
  const onPlay = () => {
    const video = videoRef.current;
    if (video && (video.currentTime < start || video.currentTime >= end)) video.currentTime = start;
  };

  const changeStart = (value: number) => {
    const next = Math.max(0, Math.min(value, end - MIN_LENGTH));
    select(next, end);
    seek(next);
  };

  const changeEnd = (value: number) => {
    const next = Math.min(duration, Math.max(value, start + MIN_LENGTH));
    select(start, next);
    seek(next);
  };

  const percent = (time: number) => (time / duration) * 100;
  // when handles meet, movable one on top
  const startOnTop = start > duration / 2;

  return (
    <div className="flex flex-col gap-3">
      <video
        ref={videoRef}
        src={src}
        controls
        preload="metadata"
        onLoadedMetadata={onLoadedMetadata}
        onTimeUpdate={onTimeUpdate}
        onPlay={onPlay}
        onError={markUnavailable}
        className={unavailable ? "hidden" : "w-full max-h-80 object-contain bg-black rounded-lg"}
      />

      {unavailable && (
        <p className="rounded-lg bg-muted px-4 py-8 text-center text-sm text-muted-foreground">
          Video sa nedá prehrať v prehliadači, spracuje sa celé.
        </p>
      )}

      {duration > 0 && (
        <>
          <div className="relative h-5 select-none">
            {/* inset by half handle, track ends under handle centres */}
            <div className="absolute inset-x-[7px] top-1/2 -translate-y-1/2 h-1.5">
              <div className="absolute inset-0 rounded-full bg-muted" />
              <div
                className="absolute inset-y-0 rounded-full bg-primary"
                style={{ left: `${percent(start)}%`, width: `${percent(end - start)}%` }}
              />
              <div
                className="absolute top-1/2 -translate-x-1/2 -translate-y-1/2 w-0.5 h-3.5 rounded-full bg-foreground/50"
                style={{ left: `${percent(current)}%` }}
              />
            </div>
            <input
              type="range"
              aria-label="Začiatok"
              min={0}
              max={duration}
              step="any"
              value={start}
              onChange={(e) => changeStart(Number(e.target.value))}
              className={`range-thumb absolute inset-0 w-full ${startOnTop ? "z-20" : "z-10"}`}
            />
            <input
              type="range"
              aria-label="Koniec"
              min={0}
              max={duration}
              step="any"
              value={end}
              onChange={(e) => changeEnd(Number(e.target.value))}
              className="range-thumb absolute inset-0 w-full z-[15]"
            />
          </div>

          <div className="flex items-center justify-between gap-3">
            <p className="text-xs text-muted-foreground tabular-nums">
              Vybrané: <span className="font-medium text-foreground">{formatTime(start)} – {formatTime(end)}</span>
              {" "}({(end - start).toFixed(1)} s)
            </p>
            <Button
              variant="outline"
              size="sm"
              disabled={!isTrimmed({ start, end, duration })}
              onClick={() => { select(0, duration); seek(0); }}
            >
              Celé video
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
