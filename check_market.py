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

    rows = []
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
        breached = change <= threshold
        row = {
            "label": label,
            "change": change,
            "threshold": threshold,
            "ref_close": ref_close,
            "ref_date": ref_date,
            "breached": breached,
        }
        rows.append(row)
        if breached:
            alerts.append(row)

    return rows, alerts, today_close, today_date


def build_email_html(rows, today_close, today_date):
    table_rows = ""
    for i, r in enumerate(rows):
        row_bg = "#FFF8F8" if r["breached"] else ("#FFFFFF" if i % 2 == 0 else "#FAFAFA")
        if r["breached"]:
            change_color = "#C5221F"
            change_weight = "bold"
        elif r["change"] < 0:
            change_color = "#C5221F"
            change_weight = "normal"
        else:
            change_color = "#137333"
            change_weight = "normal"

        alert_badge = (
            '<span style="display:inline-block;background:#FDECEA;color:#C5221F;'
            'font-size:11px;font-weight:600;padding:2px 8px;border-radius:12px;'
            'margin-left:8px;vertical-align:middle">ALERT</span>'
            if r["breached"] else ""
        )

        table_rows += f"""
        <tr style="background:{row_bg};border-bottom:1px solid #EEEEEE">
          <td style="padding:12px 16px;color:#202124;font-size:14px">{r['label']}{alert_badge}</td>
          <td style="padding:12px 16px;text-align:right;color:{change_color};font-weight:{change_weight};font-size:14px">{r['change']:+.2f}%</td>
          <td style="padding:12px 16px;text-align:right;color:#5F6368;font-size:14px">{r['threshold']}%</td>
          <td style="padding:12px 16px;color:#5F6368;font-size:14px">{r['ref_date']}</td>
          <td style="padding:12px 16px;text-align:right;color:#202124;font-size:14px">{r['ref_close']:,.2f}</td>
        </tr>"""

    return f"""
    <html>
    <body style="margin:0;padding:0;background:#F1F3F4;font-family:'Google Sans',Roboto,Arial,sans-serif">
      <table width="100%" cellpadding="0" cellspacing="0" style="background:#F1F3F4;padding:40px 16px">
        <tr><td align="center">
          <table width="600" cellpadding="0" cellspacing="0" style="background:#FFFFFF;border-radius:8px;overflow:hidden;border:1px solid #DADCE0">

            <!-- Header -->
            <tr>
              <td style="background:#1A73E8;padding:24px 32px">
                <p style="margin:0;font-size:11px;font-weight:600;color:rgba(255,255,255,0.75);letter-spacing:0.8px;text-transform:uppercase">Market Alert</p>
                <h1 style="margin:4px 0 0;font-size:22px;font-weight:400;color:#FFFFFF">S&amp;P 500 Notable Decline</h1>
              </td>
            </tr>

            <!-- Summary bar -->
            <tr>
              <td style="padding:20px 32px;border-bottom:1px solid #EEEEEE">
                <table cellpadding="0" cellspacing="0">
                  <tr>
                    <td style="padding-right:40px">
                      <p style="margin:0;font-size:11px;color:#5F6368;letter-spacing:0.4px;text-transform:uppercase">Date</p>
                      <p style="margin:4px 0 0;font-size:16px;font-weight:500;color:#202124">{today_date}</p>
                    </td>
                    <td>
                      <p style="margin:0;font-size:11px;color:#5F6368;letter-spacing:0.4px;text-transform:uppercase">S&amp;P 500 Close</p>
                      <p style="margin:4px 0 0;font-size:16px;font-weight:500;color:#202124">{today_close:,.2f}</p>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>

            <!-- Table -->
            <tr>
              <td style="padding:0">
                <p style="margin:0;padding:16px 32px 8px;font-size:11px;font-weight:600;color:#5F6368;letter-spacing:0.8px;text-transform:uppercase">Performance by Period</p>
                <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse">
                  <thead>
                    <tr style="background:#F8F9FA;border-bottom:2px solid #EEEEEE">
                      <th style="padding:10px 16px;text-align:left;font-size:12px;font-weight:600;color:#5F6368;letter-spacing:0.4px">Period</th>
                      <th style="padding:10px 16px;text-align:right;font-size:12px;font-weight:600;color:#5F6368;letter-spacing:0.4px">Change</th>
                      <th style="padding:10px 16px;text-align:right;font-size:12px;font-weight:600;color:#5F6368;letter-spacing:0.4px">Threshold</th>
                      <th style="padding:10px 16px;text-align:left;font-size:12px;font-weight:600;color:#5F6368;letter-spacing:0.4px">Peak Date</th>
                      <th style="padding:10px 16px;text-align:right;font-size:12px;font-weight:600;color:#5F6368;letter-spacing:0.4px">Peak Close</th>
                    </tr>
                  </thead>
                  <tbody>{table_rows}
                  </tbody>
                </table>
              </td>
            </tr>

            <!-- Footer -->
            <tr>
              <td style="padding:16px 32px;border-top:1px solid #EEEEEE">
                <p style="margin:0;font-size:12px;color:#9AA0A6">This is an automated alert. Data sourced from Yahoo Finance.</p>
              </td>
            </tr>

          </table>
        </td></tr>
      </table>
    </body>
    </html>"""


def send_email(rows, alerts, today_close, today_date):
    sender = os.environ["GMAIL_USER"]
    recipient = sender
    app_password = os.environ["GMAIL_APP_PASSWORD"]

    subject = f"Notable Decline in the S&P 500 [{today_date}]"

    msg = MIMEMultipart("alternative")
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.attach(MIMEText(build_email_html(rows, today_close, today_date), "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, app_password)
        server.sendmail(sender, recipient, msg.as_string())

    print(f"Alert sent to {recipient}")


def main():
    # Confirm the market was open today (ET). Skip on holidays.
    et_today = datetime.now(ZoneInfo("America/New_York")).date()
    hist = get_sp500_history()
    last_trading_day = hist.index[-1].date()

    force_email = os.environ.get("FORCE_EMAIL", "").lower() == "true"
    if not force_email and last_trading_day != et_today:
        print(f"Market closed today ({et_today}). Last trading day: {last_trading_day}. Skipping.")
        sys.exit(0)

    rows, alerts, today_close, today_date = check_thresholds(hist)

    if not alerts and not force_email:
        print(f"No thresholds breached. S&P 500 closed at {today_close:,.2f} on {today_date}.")
        return

    send_email(rows, alerts, today_close, today_date)


if __name__ == "__main__":
    main()
