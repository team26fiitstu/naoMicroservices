import { useEffect, useState } from "react";

// Chosen file with preview URL, URL released on change and unmount
export function useSelectedFile() {
  const [file, setFile] = useState<File | null>(null);
  const [url, setUrl] = useState<string | null>(null);

  useEffect(() => () => { if (url) URL.revokeObjectURL(url); }, [url]);

  const select = (next: File) => {
    setFile(next);
    setUrl(URL.createObjectURL(next));
  };

  const clear = () => {
    setFile(null);
    setUrl(null);
  };

  return { file, url, select, clear };
}
