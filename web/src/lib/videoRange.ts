// Video part chosen for processing, in seconds
export type VideoRange = { start: number; end: number; duration: number };

// Range unknown, e.g. browser cannot play the video, whole video is processed
export const WHOLE_VIDEO: VideoRange = { start: 0, end: 0, duration: 0 };

export const isTrimmed = (range: VideoRange | null): range is VideoRange =>
  range !== null && (range.start > 0 || range.end < range.duration);

// Range sent only when video trimmed
export const appendVideoRange = (form: FormData, range: VideoRange | null) => {
  if (!isTrimmed(range)) return;
  form.append("start", range.start.toFixed(2));
  form.append("end", range.end.toFixed(2));
};
