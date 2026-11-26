const LLM_API_BASE = import.meta.env.VITE_LLM_API_BASE ?? "https://litellm.blockfinlab.xyz";
const LLM_API_KEY = import.meta.env.VITE_LLM_API_KEY ?? "";
const LLM_MODEL = "gpt-5.4-fiit";
export const LLM_AVAILABLE = !!LLM_API_KEY;

// Chat completion answering with JSON object, fields not guaranteed
export async function askLlm<T>(system: string, user: string): Promise<Partial<T>> {
  const res = await fetch(`${LLM_API_BASE}/v1/chat/completions`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "Authorization": `Bearer ${LLM_API_KEY}` },
    body: JSON.stringify({
      model: LLM_MODEL,
      response_format: { type: "json_object" },
      messages: [
        { role: "system", content: system },
        { role: "user", content: user },
      ],
    }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const data = await res.json();
  return JSON.parse(data.choices?.[0]?.message?.content ?? "{}");
}
