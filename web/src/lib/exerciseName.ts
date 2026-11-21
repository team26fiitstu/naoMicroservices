// Translator default for exercise without name
export const DEFAULT_EXERCISE_NAME = "Nepomenované cvičenie";

// Default of exercises created before Slovak UI
const LEGACY_DEFAULT_NAME = "Unnamed Exercise";

export const exerciseDisplayName = (name?: string | null) =>
  !name?.trim() || name === LEGACY_DEFAULT_NAME ? DEFAULT_EXERCISE_NAME : name;
