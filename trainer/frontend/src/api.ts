export type Bar = { t: number; tl: number; o: number; h: number; l: number; c: number; v: number; s: string };
export type Level = { price: number; kind: string; label: string; strength: number };
export type Indicators = Record<string, (number | null)[]>;
export type Hints = {
  event: Record<string, any> | null;
  day_type: { label: string; score: number; reason: string };
  structure: string;
  advisor: Advisor;
  levels: Level[];
  snapshot: Record<string, any>;
};
export type Advisor = {
  action: "long" | "short" | "wait";
  lean: "up" | "down" | "flat";
  confidence: number;
  reasons: string[];
  plan: { setup: string; direction: string; entry: number; stop: number; target: number; note: string; rr: number } | null;
  checklist: { item: string; ok: boolean }[];
};
export type RoundPayload = {
  id: string; ticker: string | null; date: string | null; interval: string; horizon: number; flat_k: number; mode: string; topic: string | null;
  bars: Bar[]; cutoff_time: string; rth_start_idx: number; indicators: Indicators; levels: Level[]; atr: number; flat_threshold: number;
  last_close: number; tags: { key: string; label: string }[]; hints: Hints | null;
};
export type TradeResult = {
  filled: boolean; entry_type?: string; fill_price?: number; exit_price?: number; exit_reason?: string; r?: number | null; risk?: number;
  mfe_r?: number; mae_r?: number; planned_rr?: number | null; reason?: string; fill_idx?: number; exit_idx?: number;
};
export type Reveal = {
  id: string; ticker: string; date: string; interval: string; cutoff_time: string; hidden_bars: Bar[]; indicators_hidden: Indicators;
  outcome: { label: "up" | "down" | "flat"; move: number; threshold: number; move_in_thresholds: number | null };
  prediction: string | null; correct: boolean | null; baseline_trend: string; baseline_trend_correct: boolean;
  trade: TradeResult | null; advisor: Advisor; advisor_trade: TradeResult | null; markup: any; day_type_actual: any;
};
export type Config = {
  tickers: string[]; intervals: string[]; defaults: { horizon: number; flat_k: number; interval: string };
  topics: { key: string; label: string }[]; tags: { key: string; label: string }[];
};

async function j<T>(r: Promise<Response>): Promise<T> {
  const res = await r;
  if (!res.ok) {
    let msg = `${res.status}`;
    try { const b = await res.json(); msg = b.detail ?? JSON.stringify(b); } catch { /* ignore */ }
    throw new Error(msg);
  }
  return res.json() as Promise<T>;
}

export const api = {
  config: () => j<Config>(fetch("/api/config")),
  newRound: (body: Record<string, unknown>) => j<RoundPayload>(fetch("/api/round", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) })),
  answer: (id: string, body: Record<string, unknown>) => j<Reveal>(fetch(`/api/round/${id}/answer`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) })),
  stats: () => j<any>(fetch("/api/stats")),
  history: () => j<any[]>(fetch("/api/history")),
  clear: () => j<any>(fetch("/api/history", { method: "DELETE" })),
};
