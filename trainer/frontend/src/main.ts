import { api } from "./api";
import { TrainView } from "./train";
import { StatsView } from "./stats";

async function boot() {
  const app = document.getElementById("app")!;
  app.innerHTML = `<header><h1>Тренажёр «куда пойдёт цена»</h1><nav><a data-v="train" class="active">Тренажёр</a><a data-v="stats">Статистика</a><a href="/docs" target="_blank">API</a></nav><span class="muted small" id="status"></span></header><main id="main"></main>`;
  const main = document.getElementById("main")!;
  let cfg;
  try { cfg = await api.config(); } catch (e: any) { main.innerHTML = `<div class="panel">Не удалось получить конфигурацию: ${e.message}</div>`; return; }
  const trainRoot = document.createElement("div"); trainRoot.style.display = "contents";
  const statsRoot = document.createElement("div"); statsRoot.style.display = "contents";
  main.append(trainRoot, statsRoot);
  const train = new TrainView(trainRoot, cfg); const stats = new StatsView(statsRoot);
  const show = (v: string) => {
    trainRoot.style.display = v === "train" ? "contents" : "none"; statsRoot.style.display = v === "stats" ? "contents" : "none";
    document.querySelectorAll("nav a[data-v]").forEach((a) => a.classList.toggle("active", (a as HTMLElement).dataset.v === v));
    if (v === "stats") stats.render();
    location.hash = v;
  };
  document.querySelectorAll("nav a[data-v]").forEach((a) => a.addEventListener("click", () => show((a as HTMLElement).dataset.v!)));
  show(location.hash === "#stats" ? "stats" : "train");
  if (!cfg.tickers.length) (document.getElementById("status")!).textContent = "нет данных: выполните `make data`";
  void train;
}
boot();
