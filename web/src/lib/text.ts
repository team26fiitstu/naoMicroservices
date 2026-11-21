// Case-insensitive whole-word pattern, "a|b" allowed, letters of any alphabet count as word characters
export const wordPattern = (word: string) => new RegExp(`(?<!\\p{L})(?:${word})(?!\\p{L})`, "giu");
