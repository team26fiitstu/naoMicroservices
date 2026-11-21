// "Nahranie zlyhalo: HTTP 502"
export const failureText = (action: string, err: unknown) =>
  `${action}: ${err instanceof Error ? err.message : String(err)}`;
