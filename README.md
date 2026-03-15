# Stock Market Alert

A GitHub Actions workflow that monitors the S&P 500 for notable declines and sends an email alert when configurable thresholds are breached.

## How it works

The script runs automatically after NYSE market close (4:30 PM ET) on weekdays. It fetches the latest S&P 500 data via `yfinance` and checks if the current closing price has dropped beyond any of the following thresholds from its recent peak:

| Period    | Threshold |
|-----------|-----------|
| Daily     | -2%       |
| Weekly    | -5%       |
| Monthly   | -10%      |
| Quarterly | -15%      |

If any threshold is breached, an HTML email is sent summarizing all period changes, with breached rows highlighted in red.

The script automatically skips non-trading days (weekends and market holidays) by comparing the last available trading day to today's date in ET.

## Setup

### 1. Add GitHub Secrets

In your repository settings, add the following secrets:

- `GMAIL_USER` — your Gmail address
- `GMAIL_APP_PASSWORD` — a [Gmail App Password](https://support.google.com/accounts/answer/185833) (not your regular password)

### 2. That's it

The workflow runs on a schedule via `.github/workflows/market_check.yml`. No further configuration is needed.

## Manual trigger

You can trigger the workflow manually from the **Actions** tab in GitHub. There's an optional `force_email` input — set it to `true` to send the email even if no thresholds were breached (useful for testing).

## Running locally

```bash
pip install -r requirements.txt
GMAIL_USER=you@gmail.com GMAIL_APP_PASSWORD=your_app_password python check_market.py
```

Set `FORCE_EMAIL=true` to send an email regardless of thresholds:

```bash
FORCE_EMAIL=true GMAIL_USER=you@gmail.com GMAIL_APP_PASSWORD=your_app_password python check_market.py
```

## Dependencies

- [yfinance](https://github.com/ranaroussi/yfinance) — S&P 500 price data
- [pandas](https://pandas.pydata.org/) — date windowing and data manipulation
