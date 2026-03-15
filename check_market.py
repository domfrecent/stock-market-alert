import os
import smtplib
import sys
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf

THRESHOLDS = [
    ("Daily",     2,  -2),
    ("Weekly",    7,  -5),
    ("Monthly",  30, -10),
    ("Quarterly", 90, -20),
]


def get_sp500_history():
    ticker = yf.Ticker("^GSPC")
    hist = ticker.history(period="6mo")
    if hist.empty:
        print("No data returned from yfinance.")
        sys.exit(1)
    return hist


def find_peak_close_in_window(hist, n_days):
    """Return the highest closing price in the last n_days calendar days (excluding today)."""
    today = hist.index[-1]
    window_start = today - pd.Timedelta(days=n_days)
    window = hist[(hist.index >= window_start) & (hist.index < today)]
    if window.empty:
        return None, None
    peak_idx = window["Close"].idxmax()
    return window.loc[peak_idx, "Close"], peak_idx.date()


def pct_change(current, past):
    return (current - past) / past * 100


def check_thresholds(hist):
    today_close = hist["Close"].iloc[-1]
    today_date = hist.index[-1].date()

    alerts = []
    for label, n_days, threshold in THRESHOLDS:
        if label == "Daily":
            if len(hist) < 2:
                continue
            ref_close = hist["Close"].iloc[-2]
            ref_date = hist.index[-2].date()
        else:
            ref_close, ref_date = find_peak_close_in_window(hist, n_days)
            if ref_close is None:
                continue

        change = pct_change(today_close, ref_close)
        if change <= threshold:
            alerts.append({
                "label": label,
                "change": change,
                "threshold": threshold,
                "ref_close": ref_close,
                "ref_date": ref_date,
            })

    return alerts, today_close, today_date


def send_email(alerts, today_close, today_date):
    sender = os.environ["GMAIL_USER"]
    recipient = sender
    app_password = os.environ["GMAIL_APP_PASSWORD"]

    triggered = ", ".join(a["label"] for a in alerts)
    subject = f"S&P 500 Alert ({triggered}) — {today_date}"

    lines = [
        f"S&P 500 Market Alert",
        f"{'=' * 40}",
        f"Date:        {today_date}",
        f"Close:       {today_close:,.2f}",
        f"",
        f"Thresholds breached:",
        f"",
    ]
    for a in alerts:
        lines.append(
            f"  {a['label']:10s}  {a['change']:+.2f}%  "
            f"(threshold: {a['threshold']}%,  peak date: {a['ref_date']},  peak close: {a['ref_close']:,.2f})"
        )

    body = "\n".join(lines)
    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, app_password)
        server.sendmail(sender, recipient, msg.as_string())

    print(f"Alert sent to {recipient}: {triggered}")


def main():
    # Confirm the market was open today (ET). Skip on holidays.
    et_today = datetime.now(ZoneInfo("America/New_York")).date()
    hist = get_sp500_history()
    last_trading_day = hist.index[-1].date()

    if last_trading_day != et_today:
        print(f"Market closed today ({et_today}). Last trading day: {last_trading_day}. Skipping.")
        sys.exit(0)

    alerts, today_close, today_date = check_thresholds(hist)

    if not alerts:
        print(f"No thresholds breached. S&P 500 closed at {today_close:,.2f} on {today_date}.")
        return

    send_email(alerts, today_close, today_date)


if __name__ == "__main__":
    main()
