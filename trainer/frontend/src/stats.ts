import { api } from "./api";
import { createChart, LineSeries, ColorType, type UTCTimestamp } from "lightweight-charts";

const LBL: Record<string, string> = { up: "вверх", down: "вниз", flat: "флэт" };
const pct = (x: number | null | undefined) => x == null ? "—" : `${(x * 100).toFixed(1)}%`;
const num = (x: number | null | undefined, d = 2) => x == null ? "—" : x.toFixed(d);

export class StatsView {
  constructor(public root: HTMLElement) {}

  async render() {
    this.root.innerHTML = `<section class="panel" style="grid-column: 1 / -1"><div class="row"><h2 style="flex:1">Статистика</h2><button id="refresh">Обновить</button><button id="clear">Очистить историю</button></div><div id="body" class="muted">загрузка…</div></section>`;
    this.root.querySelector("#refresh")!.addEventListener("click", () => this.load());
    this.root.querySelector("#clear")!.addEventListener("click", async () => { if (confirm("Удалить всю историю раундов?")) { await api.clear(); this.load(); } });
    await this.load();
  }

  async load() {
    const s = await api.stats(); const body = this.root.querySelector("#body") as HTMLElement;
    const o = s.overall; const b = s.baselines; const t = s.tests; const mr = s.min_rounds; const tr = s.trades;
    if (!o.n) { body.innerHTML = `<p>Пока нет раундов. Сыграйте несколько в разделе «Тренажёр».</p><p class="small muted">Чтобы отличить точность от монетки (1/3), нужно примерно: 40% → ${mr.reference["40%"]} раундов, 45% → ${mr.reference["45%"]}, 50% → ${mr.reference["50%"]} (α = 0.05, мощность 0.8).</p>`; return; }
    const need = t.coin?.required_n; const enough = need != null && o.n >= need;
    const kpis = `<div class="kpi">
      <div><div class="muted small">раундов</div><div class="v">${o.n}</div></div>
      <div><div class="muted small">точность</div><div class="v">${pct(o.accuracy)}</div><div class="small muted">95% ДИ ${pct(o.ci95[0])}–${pct(o.ci95[1])}</div></div>
      <div><div class="muted small">монетка</div><div class="v">${pct(b.coin.accuracy)}</div><div class="small">p = ${num(t.coin?.p_value, 3)} ${t.coin?.significant_05 ? '<span class="ok">значимо</span>' : '<span class="muted">не значимо</span>'}</div></div>
      <div><div class="muted small">«всегда по тренду»</div><div class="v">${pct(b.trend.accuracy)}</div><div class="small">p = ${num(t.trend?.p_value, 3)} ${t.trend?.significant_05 ? '<span class="ok">значимо</span>' : '<span class="muted">не значимо</span>'}</div></div>
      <div><div class="muted small">самый частый класс</div><div class="v">${pct(b.majority.accuracy)}</div><div class="small">${b.majority.label}; p = ${num(t.majority?.p_value, 3)}</div></div>
      <div><div class="muted small">советник курса</div><div class="v">${pct(b.advisor.accuracy)}</div></div>
    </div>
    <div class="result ${enough ? "ok" : ""}" style="margin-top:10px"><b>Минимум раундов:</b> при текущей точности ${pct(o.accuracy)} нужно ${need ?? "— (точность не выше монетки)"} раундов, чтобы отличить её от монетки (сделано ${o.n}${need ? `, ${enough ? "достаточно" : `не хватает ${need - o.n}`}` : ""}); против «всегда по тренду» нужно ${mr.to_beat_trend_at_current_accuracy ?? "— (не выше базовой линии)"}.
    <div class="small muted">Справочно от монетки: 40% → ${mr.reference["40%"]}, 45% → ${mr.reference["45%"]}, 50% → ${mr.reference["50%"]}. ${mr.note}</div></div>`;
    const dist = Object.entries(s.outcome_distribution as Record<string, number>).map(([k, v]) => `${LBL[k]} ${pct(v)}`).join(", ");
    const table = (title: string, obj: Record<string, any>, keyLabel = (k: string) => k) => `<div class="panel"><h2>${title}</h2><table><tr><th>группа</th><th class="num">n</th><th class="num">точность</th><th class="num">95% ДИ</th></tr>${Object.entries(obj).sort((a, b) => b[1].n - a[1].n).map(([k, v]: any) => `<tr><td>${keyLabel(k)}</td><td class="num">${v.n}</td><td class="num">${pct(v.accuracy)}</td><td class="num">${v.ci95 ? `${pct(v.ci95[0])}–${pct(v.ci95[1])}` : "—"}</td></tr>`).join("")}</table></div>`;
    const conf = s.confusion as Record<string, number>;
    const confTable = `<div class="panel"><h2>Матрица ошибок (прогноз → факт)</h2><table><tr><th></th>${["up", "flat", "down"].map((k) => `<th class="num">факт ${LBL[k]}</th>`).join("")}</tr>${["up", "flat", "down"].map((p) => `<tr><td>прогноз ${LBL[p]}</td>${["up", "flat", "down"].map((o2) => `<td class="num">${conf[`${p}->${o2}`] ?? 0}</td>`).join("")}</tr>`).join("")}</table><div class="small muted">распределение фактов: ${dist}</div></div>`;
    const trades = `<div class="panel" style="grid-column: 1 / -1"><h2>Сделки (R)</h2>${tr.n ? `<div class="kpi">
      <div><div class="muted small">сделок</div><div class="v">${tr.n}</div><div class="small muted">не исполнилось: ${tr.not_filled}</div></div>
      <div><div class="muted small">expectancy</div><div class="v ${tr.expectancy > 0 ? "ok" : "bad"}">${tr.expectancy >= 0 ? "+" : ""}${num(tr.expectancy)}R</div><div class="small muted">95% ДИ ${tr.ci95_expectancy ? `${num(tr.ci95_expectancy[0])}…${num(tr.ci95_expectancy[1])}` : "—"}; p(>0) = ${num(tr.p_value_positive, 3)}</div></div>
      <div><div class="muted small">доля прибыльных</div><div class="v">${pct(tr.win_rate)}</div><div class="small muted">ср. +${num(tr.avg_win)} / ${num(tr.avg_loss)}</div></div>
      <div><div class="muted small">итого</div><div class="v">${tr.total_r >= 0 ? "+" : ""}${num(tr.total_r, 1)}R</div><div class="small muted">макс. просадка ${num(tr.max_drawdown_r, 1)}R</div></div>
      <div><div class="muted small">нужно сделок</div><div class="v">${tr.required_n ?? "—"}</div><div class="small muted">чтобы отличить expectancy от 0</div></div>
      <div><div class="muted small">советник (его план)</div><div class="v">${s.advisor_trades.n ? `${s.advisor_trades.expectancy >= 0 ? "+" : ""}${num(s.advisor_trades.expectancy)}R` : "—"}</div><div class="small muted">n = ${s.advisor_trades.n}</div></div>
    </div><div class="small muted" style="margin-top:6px">выходы: ${Object.entries(tr.exits).map(([k, v]) => `${k}: ${v}`).join(", ")}</div><div id="equity"></div>` : `<p class="muted">Сделок пока нет: поставьте вход, стоп и цель на графике перед раскрытием.</p>`}</div>`;
    body.innerHTML = kpis + `<div class="stats-grid" style="margin-top:12px">${table("По тегам (основание прогноза)", s.by_tag)}${table("По часу дня (ET)", s.by_hour, (k) => `${k}:00`)}${table("По тикеру", s.by_ticker)}${table("По режиму", s.by_mode)}${table("По своему прогнозу", s.by_prediction, (k) => LBL[k] ?? k)}${confTable}${trades}</div>`;
    if (tr.n) {
      const el = body.querySelector("#equity") as HTMLElement;
      const ch = createChart(el, { layout: { background: { type: ColorType.Solid, color: "#161c24" }, textColor: "#c3cad4" }, grid: { vertLines: { color: "#1b2330" }, horzLines: { color: "#1b2330" } }, timeScale: { visible: false }, autoSize: true, rightPriceScale: { borderColor: "#2a3441" } });
      const ls = ch.addSeries(LineSeries, { color: "#4f8cff", lineWidth: 2 });
      ls.setData((tr.equity as number[]).map((v, i) => ({ time: ((i + 1) * 86400) as UTCTimestamp, value: v })));
      ch.timeScale().fitContent();
    }
  }
}
