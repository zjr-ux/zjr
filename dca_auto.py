#!/usr/bin/env python3
"""
宽基指数 DCA 自动测算引擎
依赖：pip install yfinance
运行：python dca_auto.py
"""

import yfinance as yf
import json, os
from datetime import datetime

# ══════════ 配置区（只改这里）══════════
TARGETS = [
    {"symbol": "VOO",  "name": "VOO",  "base": 7000},   # 月度基准 HKD
    {"symbol": "QQQM", "name": "QQQM", "base": 3000},
]
DEAD_ZONE  = 0.05          # ±5% 死区
CAP        = 0.50          # ±50% 截断
DATA_FILE  = "dca_auto_data.json"

# ══════════ 持久化 ══════════
def load_state():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE) as f:
            return json.load(f)
    return {"vault": 0, "history": []}

def save_state(state):
    with open(DATA_FILE, "w") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

# ══════════ 核心计算（与 HTML 版逐行对齐）══════════
def calc(price, ma12, base):
    raw = price / ma12 - 1
    cut = max(-CAP, min(CAP, raw))
    if abs(cut) <= DEAD_ZONE:
        return raw, cut, base, "合理估值区间(-5%~+5%)"
    return raw, cut, base * (1 - cut), "线性折算区间"

# ══════════ 数据获取 ══════════
def fetch(symbol):
    """返回 (最新月度收盘价, 前12个月均线)，均为前复权"""
    df = yf.Ticker(symbol).history(period="2y", interval="1mo")
    closes = df["Close"].dropna()
    if len(closes) < 13:
        raise ValueError(f"{symbol} 历史数据不足13个月")
    price = round(float(closes.iloc[-1]), 2)
    ma12  = round(float(closes.iloc[-13:-1].mean()), 2)   # 前12个完整月
    return price, ma12

# ══════════ 主流程 ══════════
def main():
    state = load_state()
    now = datetime.now()
    month_key = now.strftime("%Y-%m")

    # 防重复：同月已跑过则拦截(已关闭)
    #if state["history"] and state["history"][-1].get("month") == month_key:
    #    print(f"⚠  {month_key} 已测算过。如需重算，请先在 {DATA_FILE} 中删除该月记录。")
     #   return

    vault = state["vault"]
    print(f"\n{'═'*54}")
    print(f"  DCA 自动测算 │ {now:%Y-%m-%d %H:%M}")
    print(f"{'═'*54}")

    for t in TARGETS:
        try:
            price, ma12 = fetch(t["symbol"])
        except Exception as e:
            print(f"  ✗ {t['name']}: {e}")
            continue

        raw, cut, amount, zone = calc(price, ma12, t["base"])

        # 金库抵扣（先扣后补）
        use_vault = min(vault, amount)
        self_pay  = amount - use_vault
        vault    -= use_vault

        rec = {
            "month":     month_key,
            "name":      t["name"],
            "price":     price,
            "ma12":      ma12,
            "raw_pct":   round(raw * 100, 2),
            "cut_pct":   round(cut * 100, 2),
            "zone":      zone,
            "amount":    round(amount, 2),
            "vault_pay": round(use_vault, 2),
            "self_pay":  round(self_pay, 2),
        }
        state["history"].append(rec)

        print(f"\n  【{t['name']}】{zone}")
        print(f"    现价 {price}  │  12月均线 {ma12}")
        print(f"    偏离 {rec['raw_pct']}%  →  截断 {rec['cut_pct']}%")
        print(f"    定投 {rec['amount']} HKD（金库 {rec['vault_pay']} + 自付 {rec['self_pay']}）")

    state["vault"] = round(vault, 2)
    save_state(state)

    print(f"\n  金库余额: {state['vault']} HKD")
    print(f"{'═'*54}\n")

    # ── 可选：推送通知（取消注释即可）──
    # notify(summary_text)

if __name__ == "__main__":
    main()