import {
  createChart, CandlestickSeries, HistogramSeries, LineSeries, LineStyle, ColorType, CrosshairMode, createSeriesMarkers,
  type IChartApi, type ISeriesApi, type UTCTimestamp, type IPriceLine, type SeriesMarker, type Time, type ISeriesMarkersPluginApi,
} from "lightweight-charts";
import type { Bar, Indicators, Level } from "./api";

const COLORS: Record<string, string> = { ema9: "#b388ff", ema20: "#4dd0e1", ema50: "#a1887f", vwap: "#ff9800", vwap_u1: "#ff980088", vwap_l1: "#ff980088", vwap_u2: "#ff980055", vwap_l2: "#ff980055" };
const PRE = { up: "#3a4a55", down: "#3a4a55", wick: "#55656f" };

export class ChartView {
  chart: IChartApi;
  candles: ISeriesApi<"Candlestick">;
  volume: ISeriesApi<"Histogram">;
  lines: Record<string, ISeriesApi<"Line">> = {};
  priceLines: IPriceLine[] = [];
  markers: ISeriesMarkersPluginApi<Time> | null = null;
  visible: Record<string, boolean> = { ema9: false, ema20: true, ema50: false, vwap: true, bands: false };
  bars: Bar[] = [];
  ind: Indicators = {};
  onClickPrice: ((price: number) => void) | null = null;

  constructor(el: HTMLElement) {
    this.chart = createChart(el, {
      layout: { background: { type: ColorType.Solid, color: "#0f1419" }, textColor: "#c3cad4" },
      grid: { vertLines: { color: "#1b2330" }, horzLines: { color: "#1b2330" } },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: "#2a3441" },
      timeScale: { borderColor: "#2a3441", timeVisible: true, secondsVisible: false, rightOffset: 12 },
      localization: { timeFormatter: (t: Time) => fmt(t as number) },
      autoSize: true,
    });
    this.candles = this.chart.addSeries(CandlestickSeries, { upColor: "#26a69a", downColor: "#ef5350", borderVisible: false, wickUpColor: "#26a69a", wickDownColor: "#ef5350" });
    this.volume = this.chart.addSeries(HistogramSeries, { priceFormat: { type: "volume" }, priceScaleId: "vol" });
    this.chart.priceScale("vol").applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
    for (const k of Object.keys(COLORS)) {
      this.lines[k] = this.chart.addSeries(LineSeries, { color: COLORS[k], lineWidth: k.startsWith("vwap_") ? 1 : 2, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false, lineStyle: k.startsWith("vwap_") ? LineStyle.Dotted : LineStyle.Solid });
    }
    this.chart.subscribeClick((p) => {
      if (!p.point || !this.onClickPrice) return;
      const price = this.candles.coordinateToPrice(p.point.y);
      if (price != null) this.onClickPrice(Number(price));
    });
  }

  setRound(bars: Bar[], ind: Indicators, levels: Level[]) {
    this.bars = bars.slice(); this.ind = ind;
    this.candles.setData(bars.map(toCandle));
    this.volume.setData(bars.map((b) => ({ time: b.tl as UTCTimestamp, value: b.v, color: b.c >= b.o ? "#26a69a55" : "#ef535055" })));
    this.redrawLines();
    this.clearPriceLines();
    const top = levels.slice().sort((a, b) => b.strength - a.strength).slice(0, 12);
    for (const lv of top) this.addPriceLine(lv.price, levelColor(lv.kind.split("+")[0]), lv.kind.replace(/\+/g, " + "), LineStyle.Dashed, lv.strength >= 4 ? 2 : 1);
    this.clearMarkers();
    this.chart.timeScale().setVisibleLogicalRange({ from: Math.max(0, bars.length - 160), to: bars.length + 14 });
  }

  redrawLines() {
    for (const k of Object.keys(this.lines)) {
      const on = k.startsWith("vwap_") ? this.visible.bands && this.visible.vwap : this.visible[k];
      const arr = this.ind[k] ?? [];
      this.lines[k].setData(on ? this.bars.map((b, i) => ({ time: b.tl as UTCTimestamp, value: arr[i] })).filter((p) => p.value != null).map((p) => ({ time: p.time, value: p.value as number })) : []);
    }
  }

  appendBar(b: Bar, indRow: Record<string, number | null>) {
    this.bars.push(b);
    this.candles.update(toCandle(b));
    this.volume.update({ time: b.tl as UTCTimestamp, value: b.v, color: b.c >= b.o ? "#26a69a55" : "#ef535055" });
    for (const k of Object.keys(this.lines)) {
      const v = indRow[k];
      (this.ind[k] ??= []).push(v ?? null);
      const on = k.startsWith("vwap_") ? this.visible.bands && this.visible.vwap : this.visible[k];
      if (on && v != null) this.lines[k].update({ time: b.tl as UTCTimestamp, value: v });
    }
  }

  addPriceLine(price: number, color: string, title: string, style = LineStyle.Solid, width: 1 | 2 = 1): IPriceLine {
    const pl = this.candles.createPriceLine({ price, color, lineWidth: width, lineStyle: style, axisLabelVisible: true, title });
    this.priceLines.push(pl);
    return pl;
  }
  removePriceLine(pl: IPriceLine) { this.candles.removePriceLine(pl); this.priceLines = this.priceLines.filter((x) => x !== pl); }
  clearPriceLines() { for (const pl of this.priceLines) this.candles.removePriceLine(pl); this.priceLines = []; }

  setMarkers(ms: SeriesMarker<Time>[]) {
    this.clearMarkers();
    this.markers = createSeriesMarkers(this.candles, ms);
  }
  clearMarkers() { if (this.markers) { this.markers.setMarkers([]); this.markers.detach(); this.markers = null; } }
  timeAt(i: number): UTCTimestamp { return this.bars[Math.max(0, Math.min(i, this.bars.length - 1))].tl as UTCTimestamp; }
}

function toCandle(b: Bar) {
  const base = { time: b.tl as UTCTimestamp, open: b.o, high: b.h, low: b.l, close: b.c };
  return b.s === "rth" ? base : { ...base, color: b.c >= b.o ? PRE.up : PRE.down, wickColor: PRE.wick, borderColor: PRE.wick };
}

export function levelColor(kind: string): string {
  if (kind.startsWith("PD")) return "#ef9a9a";
  if (kind.startsWith("PM")) return "#ce93d8";
  if (kind.startsWith("OR")) return "#90caf9";
  if (kind === "ROUND") return "#78909c";
  if (kind === "SWING") return "#a5d6a7";
  if (kind === "HOD" || kind === "LOD") return "#ffe082";
  return "#9aa4b2";
}

export function fmt(t: number): string {
  const d = new Date(t * 1000);
  const hh = String(d.getUTCHours()).padStart(2, "0"); const mm = String(d.getUTCMinutes()).padStart(2, "0");
  return `${hh}:${mm}`;
}
