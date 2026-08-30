export type Candidate = {
  candidate_id: string;
  text: string;
  rank: number;
  final_score: number;
};

export type PredictionRequest = {
  bci_input: string;
  partner: "family" | "friend" | "caregiver" | "medical_staff" | "other";
  situation: "general" | "home" | "hospital" | "meal" | "pain" | "positioning" | "schedule" | "entertainment" | "emergency";
  current_sentence?: string;
  recent_context?: string[];
  context_level?: "none" | "partner" | "partner_situation" | "full";
  top_k?: number;
};

export async function predict(apiBase: string, request: PredictionRequest) {
  const res = await fetch(`${apiBase}/predict`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ input_mode: "initials", ...request }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(JSON.stringify(data));
  return data as {
    request_id: string;
    candidates: Candidate[];
    fallback: string;
    hybrid_action: string;
    latency: { total_ms: number };
  };
}
