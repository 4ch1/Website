import re

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e


def _new_round(page: Page, mode="exam"):
    page.select_option("#mode", mode)
    page.click("#new")
    page.wait_for_function("document.querySelector('#meta').textContent.includes('обрыв')", timeout=30000)


def test_full_round_flow(page: Page, server_url: str):
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(server_url + "/")
    expect(page.locator("header h1")).to_contain_text("Тренажёр")
    _new_round(page, "exam")
    # тикер и дата скрыты
    assert "SPY" not in page.locator("#meta").inner_text() and "QQQ" not in page.locator("#meta").inner_text()
    expect(page.locator("#reveal")).to_be_disabled()
    page.click("button.pred.up")
    expect(page.locator("#reveal")).to_be_enabled()
    last = float(re.search(r"цена\s*([0-9.]+)", page.locator("#meta").inner_text()).group(1))
    page.select_option("#side", "long")
    page.fill("#stop", f"{last * 0.995:.2f}"); page.fill("#target", f"{last * 1.01:.2f}")
    expect(page.locator("#rr")).to_contain_text("R:R")
    page.click("span.chip[data-k=structure]")
    page.click("#reveal")
    page.wait_for_selector("#result .result", timeout=60000)
    txt = page.locator("#result").inner_text()
    assert ("верно" in txt) and ("факт" in txt) and ("Сделка" in txt) and ("Решение по правилам курса" in txt)
    assert re.search(r"(QQQ|SPY) 20\d\d-\d\d-\d\d", txt), "после раскрытия тикер и дата показаны"
    # повторный клик по прогнозу после раскрытия ничего не ломает
    page.click("button.pred.down")
    assert not errors, errors


def test_learning_mode_shows_hints(page: Page, server_url: str):
    page.goto(server_url + "/")
    _new_round(page, "learning")
    expect(page.locator("#hint .hint")).to_be_visible()
    assert "Советник" in page.locator("#hint").inner_text()


def test_stats_page_after_rounds(page: Page, server_url: str):
    page.goto(server_url + "/")
    for pred in ("up", "down"):
        _new_round(page, "exam")
        page.click(f"button.pred.{pred}")
        page.click("#reveal")
        page.wait_for_selector("#result .result", timeout=60000)
    page.click("nav a[data-v=stats]")
    page.wait_for_selector(".kpi", timeout=15000)
    body = page.locator("#body").inner_text()
    assert "раундов" in body and "монетка" in body and "Минимум раундов" in body
    n = int(re.search(r"раундов\n(\d+)", body).group(1))
    assert n >= 3   # два здесь + минимум один из предыдущего теста
