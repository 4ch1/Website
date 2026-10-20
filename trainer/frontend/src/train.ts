import { api, type Config, type RoundPayload, type Reveal, type Bar } from "./api";
import { ChartView, levelColor } from "./chart";
import { LineStyle, type IPriceLine, type SeriesMarker, type Time } from "lightweight-charts";

type Pred = "up" | "down" | "flat";
const LBL: Record<string, string> = { up: "вверх", down: "вниз", flat: "флэт" };
const EXIT: Record<string, string> = { target: "цель", stop: "стоп", time: "выход по времени", invalid: "некорректная сделка" };

export class TrainView {
  root: HTMLElement; cfg: Config; chart!: ChartView;
  round: RoundPayload | null = null; reveal: Reveal | null = null;
  pred: Pred | null = null; tags = new Set<string>();
  trade = { side: "none" as "none" | "long" | "short", entry: null as number | null, stop: null as number | null, target: null as number | null };
  placing: "entry" | "stop" | "target" | null = null;
  tradeLines: Partial<Record<"entry" | "stop" | "target", IPriceLine>> = {};
  busy = false;
  el: Record<string, HTMLElement> = {};

  constructor(root: HTMLElement, cfg: Config) {
    this.root = root; this.cfg = cfg; this.render();
  }

  q<T extends HTMLElement>(sel: string): T { return this.root.querySelector(sel) as T; }

  render() {
    const c = this.cfg;
    this.root.innerHTML = `
      <section class="panel" id="settings">
        <h2>Раунд</h2>
        <label>Режим</label>
        <select id="mode"><option value="exam">Экзамен: случайные точки, без подсказок</option><option value="learning">Обучающий: точки с сетапом, с подсказками</option><option value="topic">По теме: тренировка одного сетапа</option></select>
        <label>Тема (для режима «по теме»)</label>
        <select id="topic" disabled>${c.topics.map((t) => `<option value="${t.key}">${t.label}</option>`).join("")}</select>
        <label>Тикеры</label>
        <div class="ticks">${c.tickers.map((t) => `<label><input type="checkbox" class="tk" value="${t}" ${["SPY", "QQQ"].includes(t) || c.tickers.length <= 3 ? "checked" : ""}> ${t}</label>`).join("")}</div>
        <div class="row">
          <div style="flex:1"><label>Таймфрейм</label><select id="interval">${c.intervals.map((i) => `<option value="${i}" ${i === c.defaults.interval ? "selected" : ""}>${i}</option>`).join("")}</select></div>
          <div style="flex:1"><label>Горизонт N, свечей</label><input id="horizon" type="number" min="1" max="120" value="${c.defaults.horizon}"></div>
        </div>
        <label>Порог флэта k (порог = k · ATR14 · √N)</label>
        <input id="flatk" type="number" min="0" max="3" step="0.05" value="${c.defaults.flat_k}">
        <label class="toggle" style="display:block;margin-top:8px"><input id="hide" type="checkbox" checked> скрыть тикер и дату</label>
        <div class="row" style="margin-top:10px"><button id="new" class="primary" style="flex:1">Новый раунд (N)</button></div>
        <div class="error" id="err"></div>
        <h2 style="margin-top:14px">Индикаторы</h2>
        <div>
          <label class="toggle"><input type="checkbox" class="ind" data-k="ema9"> EMA9</label>
          <label class="toggle"><input type="checkbox" class="ind" data-k="ema20" checked> EMA20</label>
          <label class="toggle"><input type="checkbox" class="ind" data-k="ema50"> EMA50</label>
          <label class="toggle"><input type="checkbox" class="ind" data-k="vwap" checked> VWAP</label>
          <label class="toggle"><input type="checkbox" class="ind" data-k="bands"> ±1σ/±2σ</label>
        </div>
        <div class="legend" style="margin-top:6px"><span style="color:#ef9a9a">PDH/PDL/PDC</span><span style="color:#ce93d8">PMH/PML</span><span style="color:#90caf9">OR</span><span style="color:#a5d6a7">свинг-уровень</span><span style="color:#78909c">круглый</span><span style="color:#55656f">премаркет</span></div>
        <p class="small muted" style="margin-top:10px">Клавиши: 1 вверх, 2 вниз, 3 флэт, Enter раскрыть, N новый раунд.</p>
      </section>
      <section class="panel">
        <div class="meta" id="meta">Нажмите «Новый раунд»</div>
        <div id="chart"></div>
        <div id="hint"></div>
      </section>
      <section class="panel" id="answer">
        <h2>Прогноз на N свечей</h2>
        <div class="row">
          <button class="pred up" data-p="up">▲ вверх</button>
          <button class="pred flat" data-p="flat">▬ флэт</button>
          <button class="pred down" data-p="down">▼ вниз</button>
        </div>
        <h2 style="margin-top:12px">Сделка (опционально)</h2>
        <div class="row">
          <select id="side" style="flex:1"><option value="none">без сделки</option><option value="long">лонг</option><option value="short">шорт</option></select>
        </div>
        <div class="row" style="margin-top:6px">
          <button class="place" data-f="entry" title="кликните по графику">вход</button>
          <button class="place" data-f="stop">стоп</button>
          <button class="place" data-f="target">цель</button>
        </div>
        <div class="row" style="margin-top:6px">
          <input id="entry" type="number" step="0.01" placeholder="вход (пусто = по рынку)">
          <input id="stop" type="number" step="0.01" placeholder="стоп">
          <input id="target" type="number" step="0.01" placeholder="цель">
        </div>
        <div class="small muted" id="rr"></div>
        <h2 style="margin-top:12px">На чём основан прогноз</h2>
        <div class="chips" id="tags">${c.tags.map((t) => `<span class="chip" data-k="${t.key}">${t.label}</span>`).join("")}</div>
        <div class="row" style="margin-top:12px"><button id="reveal" class="primary" style="flex:1" disabled>Раскрыть (Enter)</button></div>
        <div id="result"></div>
      </section>`;
    this.chart = new ChartView(this.q("#chart"));
    this.chart.onClickPrice = (p) => this.placePrice(p);
    this.q<HTMLSelectElement>("#mode").addEventListener("change", (e) => { this.q<HTMLSelectElement>("#topic").disabled = (e.target as HTMLSelectElement).value !== "topic"; });
    this.q("#new").addEventListener("click", () => this.newRound());
    this.root.querySelectorAll<HTMLInputElement>(".ind").forEach((i) => i.addEventListener("change", () => { this.chart.visible[i.dataset.k!] = i.checked; this.chart.redrawLines(); }));
    this.root.querySelectorAll<HTMLButtonElement>(".pred").forEach((b) => b.addEventListener("click", () => this.setPred(b.dataset.p as Pred)));
    this.root.querySelectorAll<HTMLElement>(".chip").forEach((ch) => ch.addEventListener("click", () => { const k = ch.dataset.k!; this.tags.has(k) ? this.tags.delete(k) : this.tags.add(k); ch.classList.toggle("on", this.tags.has(k)); }));
    this.root.querySelectorAll<HTMLButtonElement>(".place").forEach((b) => b.addEventListener("click", () => { this.placing = this.placing === b.dataset.f ? null : (b.dataset.f as any); this.root.querySelectorAll(".place").forEach((x) => x.classList.toggle("primary", (x as HTMLElement).dataset.f === this.placing)); }));
    for (const f of ["entry", "stop", "target"] as const) this.q<HTMLInputElement>(`#${f}`).addEventListener("input", (e) => { const v = (e.target as HTMLInputElement).value; this.trade[f] = v === "" ? null : Number(v); this.syncTrade(); });
    this.q<HTMLSelectElement>("#side").addEventListener("change", (e) => { this.trade.side = (e.target as HTMLSelectElement).value as any; this.syncTrade(); });
    this.q("#reveal").addEventListener("click", () => this.doReveal());
    window.addEventListener("keydown", (e) => {
      if ((e.target as HTMLElement).tagName === "INPUT" || (e.target as HTMLElement).tagName === "SELECT") return;
      if (e.key === "1") this.setPred("up"); else if (e.key === "2") this.setPred("down"); else if (e.key === "3") this.setPred("flat");
      else if (e.key === "Enter") this.doReveal(); else if (e.key.toLowerCase() === "n") this.newRound();
    });
  }

  setPred(p: Pred) {
    if (this.reveal || !this.round) return;
    this.pred = p;
    this.root.querySelectorAll<HTMLButtonElement>(".pred").forEach((b) => b.classList.toggle("selected", b.dataset.p === p));
    this.q<HTMLButtonElement>("#reveal").disabled = false;
  }

  placePrice(price: number) {
    if (!this.placing || this.reveal) return;
    const f = this.placing; this.trade[f] = Math.round(price * 100) / 100;
    this.q<HTMLInputElement>(`#${f}`).value = String(this.trade[f]);
    if (this.trade.side === "none") { // авто-сторона по стопу относительно цены
      const last = this.round!.last_close;
      if (f === "stop") { this.trade.side = price < last ? "long" : "short"; this.q<HTMLSelectElement>("#side").value = this.trade.side; }
    }
    this.placing = null; this.root.querySelectorAll(".place").forEach((x) => x.classList.remove("primary"));
    this.syncTrade();
  }

  syncTrade() {
    for (const f of ["entry", "stop", "target"] as const) {
      const v = this.trade[f];
      if (this.tradeLines[f]) { this.chart.removePriceLine(this.tradeLines[f]!); delete this.tradeLines[f]; }
      if (v != null && this.trade.side !== "none") this.tradeLines[f] = this.chart.addPriceLine(v, f === "entry" ? "#4f8cff" : f === "stop" ? "#ef5350" : "#26a69a", f === "entry" ? "вход" : f === "stop" ? "стоп" : "цель", LineStyle.Solid, 2);
    }
    const rr = this.q("#rr");
    const { side, stop, target } = this.trade; const entry = this.trade.entry ?? this.round?.last_close ?? null;
    if (side !== "none" && entry != null && stop != null) {
      const risk = side === "long" ? entry - stop : stop - entry;
      const atr = this.round?.atr ?? 0;
      let txt = `риск ${risk.toFixed(2)} (${atr ? (risk / atr).toFixed(2) : "?"} ATR)`;
      if (target != null) txt += `, R:R ${((side === "long" ? target - entry : entry - target) / risk).toFixed(2)}`;
      if (risk <= 0) txt = "стоп по неправильную сторону от входа";
      rr.textContent = txt;
    } else rr.textContent = side === "none" ? "" : "поставьте стоп (клик по графику или число)";
  }

  async newRound() {
    if (this.busy) return;
    this.busy = true; this.q("#err").textContent = "";
    this.round = null; this.reveal = null; this.pred = null;
    this.q("#meta").innerHTML = '<span class="muted">загрузка раунда…</span>'; this.q("#result").innerHTML = ""; this.q("#hint").innerHTML = "";
    this.q<HTMLButtonElement>("#reveal").disabled = true;
    const tickers = [...this.root.querySelectorAll<HTMLInputElement>(".tk:checked")].map((i) => i.value);
    const mode = this.q<HTMLSelectElement>("#mode").value;
    try {
      const r = await api.newRound({ mode, topic: mode === "topic" ? this.q<HTMLSelectElement>("#topic").value : null, tickers: tickers.length ? tickers : null,
        interval: this.q<HTMLSelectElement>("#interval").value, horizon: Number(this.q<HTMLInputElement>("#horizon").value), flat_k: Number(this.q<HTMLInputElement>("#flatk").value), hide_meta: this.q<HTMLInputElement>("#hide").checked });
      this.round = r; this.reveal = null; this.pred = null; this.tags.clear(); this.placing = null;
      this.trade = { side: "none", entry: null, stop: null, target: null }; this.tradeLines = {};
      this.root.querySelectorAll(".pred").forEach((b) => b.classList.remove("selected"));
      this.root.querySelectorAll(".chip").forEach((b) => b.classList.remove("on"));
      for (const f of ["entry", "stop", "target"]) this.q<HTMLInputElement>(`#${f}`).value = "";
      this.q<HTMLSelectElement>("#side").value = "none"; this.q("#rr").textContent = ""; this.q("#result").innerHTML = "";
      this.q<HTMLButtonElement>("#reveal").disabled = true;
      this.chart.setRound(r.bars, r.indicators, r.levels);
      const meta = [`обрыв: <b>${r.cutoff_time} ET</b>`, `ТФ <b>${r.interval}</b>`, `N = <b>${r.horizon}</b>`, `ATR14 <b>${r.atr.toFixed(2)}</b>`, `порог флэта ±<b>${r.flat_threshold.toFixed(2)}</b> (${(r.flat_threshold / r.last_close * 100).toFixed(2)}%)`, `цена <b>${r.last_close.toFixed(2)}</b>`];
      if (r.ticker) meta.unshift(`<b>${r.ticker}</b> ${r.date}`);
      this.q("#meta").innerHTML = meta.map((m) => `<span>${m}</span>`).join(" · ");
      this.q("#hint").innerHTML = r.hints ? this.hintHtml(r) : "";
      if (r.hints?.event && r.hints.event.entry != null) this.markEvent(r.bars.length - 1, r.hints.event.direction);
    } catch (e: any) { this.q("#err").textContent = `Ошибка: ${e.message}`; }
    this.busy = false;
  }

  hintHtml(r: RoundPayload): string {
    const h = r.hints!; const ev = h.event; const a = h.advisor;
    const lines: string[] = [];
    if (ev) lines.push(`<b>Сетап на последнем баре:</b> ${ev.label ?? ev.kind}${ev.note ? ` — ${ev.note}` : ""}. План по правилам курса: вход ${fmtN(ev.entry)}, стоп ${fmtN(ev.stop)}, цель ${fmtN(ev.target)}.`);
    lines.push(`<b>Структура 5m:</b> ${h.structure}. <b>Тип дня:</b> ${h.day_type.label} (score ${h.day_type.score}). <b>VWAP:</b> ${h.snapshot.above_vwap == null ? "нет" : h.snapshot.above_vwap ? "цена выше" : "цена ниже"}, RVOL ${h.snapshot.rvol?.toFixed?.(1) ?? "—"}.`);
    lines.push(`<b>Советник:</b> ${a.action === "wait" ? "ждать" : a.action === "long" ? "лонг" : "шорт"}; склонность ${LBL[a.lean]} (уверенность ${a.confidence}). ${a.reasons[0] ?? ""}`);
    if (a.checklist.length) lines.push(`<ul class="check" style="margin:4px 0 0 16px;padding:0">${a.checklist.map((c) => `<li class="${c.ok ? "ok" : "bad"}">${c.item}</li>`).join("")}</ul>`);
    return `<div class="hint">${lines.map((l) => `<div>${l}</div>`).join("")}</div>`;
  }

  markEvent(i: number, dir: string) {
    this.chart.setMarkers([{ time: this.chart.timeAt(i), position: dir === "up" ? "belowBar" : "aboveBar", color: dir === "up" ? "#26a69a" : "#ef5350", shape: dir === "up" ? "arrowUp" : "arrowDown", text: "сетап" }]);
  }

  async doReveal() {
    if (!this.round || this.reveal || this.busy || !this.pred) return;
    this.busy = true; this.q<HTMLButtonElement>("#reveal").disabled = true;
    const t = this.trade;
    const trade = t.side !== "none" && t.stop != null ? { side: t.side, entry: t.entry, stop: t.stop, target: t.target } : null;
    try {
      const rv = await api.answer(this.round.id, { prediction: this.pred, tags: [...this.tags], trade });
      this.reveal = rv;
      await this.animate(rv);
      this.showResult(rv);
    } catch (e: any) { this.q("#err").textContent = `Ошибка: ${e.message}`; }
    this.busy = false;
  }

  animate(rv: Reveal): Promise<void> {
    const bars = rv.hidden_bars; const ih = rv.indicators_hidden;
    return new Promise((resolve) => {
      let i = 0;
      const step = () => {
        if (i >= bars.length) { resolve(); return; }
        const row: Record<string, number | null> = {}; for (const k of Object.keys(ih)) row[k] = ih[k][i];
        this.chart.appendBar(bars[i], row); i++;
        setTimeout(step, Math.max(40, Math.min(160, 1600 / bars.length)));
      };
      step();
    });
  }

  showResult(rv: Reveal) {
    const r = this.round!; const o = rv.outcome; const ok = rv.correct;
    const n = r.bars.length; const cut = n - 1;
    const pieces: string[] = [];
    pieces.push(`<div class="result ${ok ? "ok" : "bad"}"><div class="big">${ok ? "✓ верно" : "✗ неверно"}: факт — ${LBL[o.label]}</div>
      <div class="small">ход ${o.move >= 0 ? "+" : ""}${o.move.toFixed(2)} при пороге ±${o.threshold.toFixed(2)} (${o.move_in_thresholds?.toFixed(2)} порога). Ваш прогноз: ${LBL[rv.prediction ?? ""] ?? "—"}. Базовая линия «по тренду»: ${LBL[rv.baseline_trend]} ${rv.baseline_trend_correct ? "✓" : "✗"}. Советник: ${LBL[rv.advisor.lean]} ${rv.advisor.lean === o.label ? "✓" : "✗"}.</div>
      <div class="small muted">${rv.ticker} ${rv.date}, обрыв ${rv.cutoff_time}</div></div>`);
    if (rv.trade) {
      const tr = rv.trade;
      if (!tr.filled) pieces.push(`<div class="result"><b>Сделка:</b> вход не исполнился (${tr.reason ?? ""}).</div>`);
      else if (tr.r == null) pieces.push(`<div class="result bad"><b>Сделка:</b> ${tr.reason}</div>`);
      else pieces.push(`<div class="result ${tr.r > 0 ? "ok" : "bad"}"><b>Сделка:</b> <span class="big">${tr.r >= 0 ? "+" : ""}${tr.r.toFixed(2)}R</span> · ${EXIT[tr.exit_reason!] ?? tr.exit_reason} · вход ${tr.entry_type} по ${tr.fill_price!.toFixed(2)}, выход ${tr.exit_price!.toFixed(2)} · MFE +${tr.mfe_r!.toFixed(2)}R, MAE −${tr.mae_r!.toFixed(2)}R${tr.planned_rr ? ` · план R:R ${tr.planned_rr.toFixed(2)}` : ""}</div>`);
    }
    const a = rv.advisor; const mk = rv.markup;
    const adv: string[] = [];
    adv.push(`<b>Решение по правилам курса:</b> ${a.action === "wait" ? "ждать (без сделки)" : a.action === "long" ? "лонг" : "шорт"}; склонность ${LBL[a.lean]} (уверенность ${a.confidence}).`);
    if (a.plan) adv.push(`План: ${a.plan.setup}, вход ${fmtN(a.plan.entry)}, стоп ${fmtN(a.plan.stop)}, цель ${fmtN(a.plan.target)} (R:R ${a.plan.rr})${rv.advisor_trade && rv.advisor_trade.r != null ? ` → результат ${rv.advisor_trade.r >= 0 ? "+" : ""}${rv.advisor_trade.r.toFixed(2)}R (${EXIT[rv.advisor_trade.exit_reason!]})` : ""}.`);
    adv.push(`<ul class="reasons">${a.reasons.map((x) => `<li>${x}</li>`).join("")}</ul>`);
    if (a.checklist.length) adv.push(`<ul class="check" style="margin:0 0 0 16px;padding:0">${a.checklist.map((c) => `<li class="${c.ok ? "ok" : "bad"}">${c.item}</li>`).join("")}</ul>`);
    pieces.push(`<div class="result">${adv.join("")}</div>`);
    // разметка
    const m: string[] = [];
    m.push(`<b>Структура:</b> ${mk.structure.trend} (${mk.structure.reason}).`);
    m.push(`<b>Тип дня (оценка в точке обрыва):</b> ${mk.day_type.label}; <b>факт:</b> ${rv.day_type_actual?.label ?? "—"}.`);
    const near = (mk.levels as any[]).slice().sort((x, y) => Math.abs(x.price - r.last_close) - Math.abs(y.price - r.last_close)).slice(0, 5);
    if (near.length) m.push(`<b>Уровни рядом:</b> ${near.map((x) => `${x.kind} ${x.price.toFixed(2)}`).join(", ")}.`);
    if (mk.volume_profile?.poc) m.push(`<b>Профиль дня:</b> POC ${mk.volume_profile.poc.toFixed(2)}, VA ${mk.volume_profile.val.toFixed(2)}–${mk.volume_profile.vah.toFixed(2)}.`);
    const setups = (mk.setups as any[]).slice(-4); if (setups.length) m.push(`<b>Сетапы дня:</b> ${setups.map((e) => `${e.label} (${e.direction}, бар ${e.idx - r.rth_start_idx + 1} RTH)`).join("; ")}.`);
    const pats = (mk.chart_patterns as any[]).slice(-3); if (pats.length) m.push(`<b>Фигуры:</b> ${pats.map((e) => `${e.label} (${e.direction})`).join("; ")}.`);
    const cands = (mk.candles as any[]).filter((e) => e.idx >= cut - 5); if (cands.length) m.push(`<b>Свечи у обрыва:</b> ${cands.map((e) => `${e.label} (бар −${cut - e.idx})`).join("; ")}.`);
    if (mk.volume_climax?.length) m.push(`<b>Климакс-объём:</b> ${mk.volume_climax.map((e: any) => e.label).join("; ")}.`);
    pieces.push(`<div class="result"><h2>Разметка в точке обрыва</h2>${m.map((x) => `<div class="small">${x}</div>`).join("")}</div>`);
    this.q("#result").innerHTML = pieces.join("");
    // маркеры на графике: сетапы, свечи, фигуры (только видимые до обрыва)
    const marks: SeriesMarker<Time>[] = [];
    for (const e of mk.setups as any[]) marks.push({ time: this.chart.timeAt(e.idx), position: e.direction === "up" ? "belowBar" : "aboveBar", color: e.direction === "up" ? "#26a69a" : "#ef5350", shape: e.direction === "up" ? "arrowUp" : "arrowDown", text: shortName(e.kind) });
    for (const e of mk.chart_patterns as any[]) marks.push({ time: this.chart.timeAt(e.idx), position: "aboveBar", color: "#90caf9", shape: "square", text: shortName(e.kind) });
    for (const e of (mk.candles as any[]).filter((x) => x.idx >= cut - 12)) marks.push({ time: this.chart.timeAt(e.idx), position: e.direction === "down" ? "aboveBar" : "belowBar", color: "#ffe082", shape: "circle", text: shortName(e.kind) });
    for (const b of mk.structure.breaks as any[]) marks.push({ time: this.chart.timeAt(b.idx), position: b.direction === "up" ? "belowBar" : "aboveBar", color: "#ce93d8", shape: "circle", text: b.kind });
    marks.sort((x, y) => (x.time as number) - (y.time as number));
    this.chart.setMarkers(marks);
    this.chart.addPriceLine(r.last_close, "#9aa4b2", "обрыв", LineStyle.Dotted);
    if (a.plan) { this.chart.addPriceLine(a.plan.stop, "#ef535099", "стоп (курс)", LineStyle.Dashed); this.chart.addPriceLine(a.plan.target, "#26a69a99", "цель (курс)", LineStyle.Dashed); }
    this.chart.chart.timeScale().setVisibleLogicalRange({ from: Math.max(0, n - 120), to: n + r.horizon + 6 });
  }
}

function fmtN(x: any): string { return typeof x === "number" ? x.toFixed(2) : "—"; }
function shortName(k: string): string {
  const m: Record<string, string> = { ORB: "ORB", GAP_GO: "gap&go", GAP_FILL: "gap fill", VWAP_RECLAIM: "VWAP↩", VWAP_REJECT: "VWAP⊥", BREAK_RETEST: "ретест", FAKEOUT: "fakeout", LEVEL_REVERSAL: "разворот", PIN: "pin", ENGULF: "engulf", DOJI: "doji", INSIDE: "inside", OUTSIDE: "outside", MORNING_STAR: "m.star", EVENING_STAR: "e.star", FLAG: "флаг", PENNANT: "вымпел", TRI_ASC: "▲tri", TRI_DESC: "▼tri", TRI_SYM: "tri", WEDGE_RISING: "клин↑", WEDGE_FALLING: "клин↓", DOUBLE_TOP: "2top", DOUBLE_BOTTOM: "2bot", HS: "H&S", IHS: "iH&S", RANGE: "range", RANGE_BREAK: "range brk", CUP_HANDLE: "cup" };
  return m[k] ?? k;
}
export type { Bar };
