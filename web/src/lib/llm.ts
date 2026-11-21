export const LLM_API_BASE = import.meta.env.VITE_LLM_API_BASE ?? "https://litellm.blockfinlab.xyz";
export const LLM_API_KEY = import.meta.env.VITE_LLM_API_KEY ?? "";
export const LLM_MODEL = "gpt-5.4-fiit";
export const LLM_AVAILABLE = !!LLM_API_KEY;
