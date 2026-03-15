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
    ("Quarterly", 90, -15),
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


def build_email_html(alerts, today_close, today_date):
    rows = ""
    for a in alerts:
        rows += f"""
        <tr>
          <td style="padding:8px 12px">{a['label']}</td>
          <td style="padding:8px 12px;text-align:right;color:#c0392b;font-weight:bold">{a['change']:+.2f}%</td>
          <td style="padding:8px 12px;text-align:right">{a['threshold']}%</td>
          <td style="padding:8px 12px">{a['ref_date']}</td>
          <td style="padding:8px 12px;text-align:right">{a['ref_close']:,.2f}</td>
        </tr>"""

    return f"""
    <html><body style="font-family:sans-serif;color:#222;max-width:600px;margin:40px auto">
      <h2 style="border-bottom:2px solid #c0392b;padding-bottom:8px">
        S&amp;P 500 Market Alert
      </h2>
      <table style="border-collapse:collapse;margin-bottom:24px">
        <tr>
          <td style="color:#666;padding-right:16px">Date</td>
          <td><strong>{today_date}</strong></td>
        </tr>
        <tr>
          <td style="color:#666;padding-right:16px">Close</td>
          <td><strong>{today_close:,.2f}</strong></td>
        </tr>
      </table>
      <h3 style="margin-bottom:8px">Thresholds Breached</h3>
      <table style="border-collapse:collapse;width:100%">
        <thead>
          <tr style="background:#f2f2f2;text-align:left">
            <th style="padding:8px 12px">Period</th>
            <th style="padding:8px 12px;text-align:right">Change</th>
            <th style="padding:8px 12px;text-align:right">Threshold</th>
            <th style="padding:8px 12px">Peak Date</th>
            <th style="padding:8px 12px;text-align:right">Peak Close</th>
          </tr>
        </thead>
        <tbody>{rows}
        </tbody>
      </table>
    </body></html>"""


def send_email(alerts, today_close, today_date):
    sender = os.environ["GMAIL_USER"]
    recipient = sender
    app_password = os.environ["GMAIL_APP_PASSWORD"]

    triggered = ", ".join(a["label"] for a in alerts)
    subject = f"Notable Decline in the S&P 500 [{today_date}]"

    msg = MIMEMultipart("alternative")
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.attach(MIMEText(build_email_html(alerts, today_close, today_date), "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, app_password)
        server.sendmail(sender, recipient, msg.as_string())

    print(f"Alert sent to {recipient}: {triggered}")


def main():
    # Confirm the market was open today (ET). Skip on holidays.
    et_today = datetime.now(ZoneInfo("America/New_York")).date()
    hist = get_sp500_history()
    last_trading_day = hist.index[-1].date()

    skip_market_check = os.environ.get("SKIP_MARKET_CHECK", "").lower() == "true"
    if not skip_market_check and last_trading_day != et_today:
        print(f"Market closed today ({et_today}). Last trading day: {last_trading_day}. Skipping.")
        sys.exit(0)

    alerts, today_close, today_date = check_thresholds(hist)

    if not alerts:
        print(f"No thresholds breached. S&P 500 closed at {today_close:,.2f} on {today_date}.")
        return

    send_email(alerts, today_close, today_date)


if __name__ == "__main__":
    main()
