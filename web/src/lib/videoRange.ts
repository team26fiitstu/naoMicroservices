// Video part chosen for processing, in seconds
export type VideoRange = { start: number; end: number; duration: number };

export const isTrimmed = (range: VideoRange | null): range is VideoRange =>
  range !== null && (range.start > 0 || range.end < range.duration);

// Range sent only when video trimmed
export const appendVideoRange = (form: FormData, range: VideoRange | null) => {
  if (!isTrimmed(range)) return;
  form.append("start", range.start.toFixed(2));
  form.append("end", range.end.toFixed(2));
};
