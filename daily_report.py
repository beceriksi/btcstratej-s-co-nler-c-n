import os
import json
import requests
from datetime import datetime, timezone, timedelta

STORE_PATH = "signals_store.json"

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")


def send_telegram(text: str):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("\n[UYARI] Telegram TOKEN veya CHAT_ID yok. Mesaj gösteriliyor:")
        print(text)
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {'chat_id': CHAT_ID, 'text': text, 'disable_web_page_preview': True}

    try:
        r = requests.post(url, data=payload, timeout=10)
        if r.status_code != 200:
            print("[HATA] Telegram gönderilemedi:", r.text)
    except Exception as e:
        print("[HATA] Telegram hatası:", e)


def load_store():
    if not os.path.exists(STORE_PATH):
        return {"signals": []}
    try:
        with open(STORE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "signals" not in data:
                data["signals"] = []
            return data
    except Exception as e:
        print("[HATA] signals_store.json okunamadı:", e)
        return {"signals": []}


def parse_ts(s):
    # ts() fonksiyonu "%Y-%m-%d %H:%M:%S UTC" formatında yazıyor
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S UTC").replace(tzinfo=timezone.utc)


def side_text(d):
    return "LONG" if d == "UP" else "SHORT"


def px(x):
    try:
        return f"{x:,.2f}"
    except Exception:
        return str(x)


def main():
    store = load_store()
    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=24)

    tp_hits = []
    sl_hits = []
    still_open = []

    for sig in store["signals"]:
        status = sig.get("status")

        if status in ("TP_HIT", "SL_HIT") and sig.get("closed_at"):
            try:
                closed_at = parse_ts(sig["closed_at"])
            except Exception:
                continue

            if closed_at >= since:
                if status == "TP_HIT":
                    tp_hits.append(sig)
                else:
                    sl_hits.append(sig)

        elif status == "OPEN":
            try:
                opened_at = parse_ts(sig["opened_at"])
            except Exception:
                continue
            if opened_at >= since:
                still_open.append(sig)

    if not tp_hits and not sl_hits and not still_open:
        send_telegram("📊 Günlük Rapor\n\nSon 24 saatte kapanan veya açılan sinyal yok.")
        print("[INFO] Rapor: sinyal yok.")
        return

    lines = ["📊 GÜNLÜK RAPOR (Son 24 Saat)\n"]

    if tp_hits:
        lines.append(f"✅ Hedefe Ulaşanlar ({len(tp_hits)}):")
        for s in tp_hits:
            sym = s["symbol"].split("-")[0]
            lines.append(
                f"  {sym} {side_text(s['direction'])} | Giriş: {px(s['entry'])} "
                f"-> Kapanış: {px(s['close_price'])} (TP1)"
            )
        lines.append("")

    if sl_hits:
        lines.append(f"🛑 Stop Olanlar ({len(sl_hits)}):")
        for s in sl_hits:
            sym = s["symbol"].split("-")[0]
            lines.append(
                f"  {sym} {side_text(s['direction'])} | Giriş: {px(s['entry'])} "
                f"-> Kapanış: {px(s['close_price'])} (SL)"
            )
        lines.append("")

    if still_open:
        lines.append(f"⏳ Hâlâ Açık Olanlar (son 24s içinde açılan) ({len(still_open)}):")
        for s in still_open:
            sym = s["symbol"].split("-")[0]
            lines.append(
                f"  {sym} {side_text(s['direction'])} | Giriş: {px(s['entry'])} "
                f"SL: {px(s['sl'])} TP1: {px(s['tp1'])}"
            )

    total_closed = len(tp_hits) + len(sl_hits)
    if total_closed > 0:
        winrate = (len(tp_hits) / total_closed) * 100
        lines.append(f"\nBaşarı Oranı: {winrate:.0f}% ({len(tp_hits)}/{total_closed})")

    text = "\n".join(lines)
    send_telegram(text)
    print("[INFO] Günlük rapor gönderildi.")


if __name__ == "__main__":
    main()
