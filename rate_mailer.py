import os
import json
import smtplib
import requests
from datetime import date, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ── Config (set these as GitHub Secrets) ─────────────────────────────────────
SENDER_EMAIL   = os.environ["SENDER_EMAIL"]    # your Gmail address
SENDER_PASS    = os.environ["SENDER_PASS"]     # Gmail App Password
RECEIVER_EMAIL = os.environ["RECEIVER_EMAIL"]  # email to send report to
RATE_FILE      = "last_rate.json"              # persisted between runs via git
# ─────────────────────────────────────────────────────────────────────────────


def fetch_rate(on_date: date) -> float:
    """Fetch GBP→INR rate for a given date from Frankfurter (free, no key)."""
    url = f"https://api.frankfurter.dev/v2/rates?date={on_date}&base=GBP&quotes=INR"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    # Handle both dict and list response formats
    rates = data["rates"]
    if isinstance(rates, list):
        return next(r["value"] for r in rates if r["code"] == "INR")
    return rates["INR"]


def load_yesterday_rate() -> float | None:
    """Load the previously saved rate from the JSON file (committed to repo)."""
    if os.path.exists(RATE_FILE):
        with open(RATE_FILE) as f:
            saved = json.load(f)
        return saved.get("rate")
    return None


def save_rate(rate: float):
    """Save today's rate so tomorrow's run can compare."""
    with open(RATE_FILE, "w") as f:
        json.dump({"date": str(date.today()), "rate": rate}, f)


def build_email(today_rate: float, yesterday_rate: float | None) -> tuple[str, str]:
    """Return (subject, HTML body) for the email."""
    today_str = date.today().strftime("%d %B %Y")

    if yesterday_rate is None:
        change_line = "<p>📊 No previous rate on record — this is the first run.</p>"
        arrow = "📊"
        subject = f"GBP→INR Rate | {today_str} | £1 = ₹{today_rate:.4f}"
    else:
        diff = today_rate - yesterday_rate
        pct  = (diff / yesterday_rate) * 100

        if diff > 0:
            arrow = "📈"
            direction = f"<span style='color:#2e7d32'>▲ UP by ₹{diff:.4f} (+{pct:.2f}%) vs yesterday</span>"
        elif diff < 0:
            arrow = "📉"
            direction = f"<span style='color:#c62828'>▼ DOWN by ₹{abs(diff):.4f} ({pct:.2f}%) vs yesterday</span>"
        else:
            arrow = "➡️"
            direction = "<span style='color:#555'>No change from yesterday</span>"

        change_line = f"<p style='font-size:18px'>{direction}</p>"
        subject = f"{arrow} GBP→INR | {today_str} | £1 = ₹{today_rate:.4f}"

    html = f"""
    <html><body style="font-family:Arial,sans-serif;max-width:480px;margin:auto">
      <h2 style="color:#1a237e">💷 GBP → INR Daily Rate</h2>
      <p style="color:#555">{today_str}</p>
      <div style="background:#f5f5f5;border-radius:8px;padding:20px;text-align:center">
        <p style="font-size:14px;color:#555;margin:0">£1 (British Pound) =</p>
        <p style="font-size:42px;font-weight:bold;color:#1a237e;margin:8px 0">
          ₹{today_rate:.4f}
        </p>
        <p style="font-size:13px;color:#777">Indian Rupee</p>
      </div>
      {change_line}
      {'<p style="font-size:13px;color:#999">Yesterday: ₹' + f'{yesterday_rate:.4f}</p>' if yesterday_rate else ''}
      <hr style="border:none;border-top:1px solid #eee">
      <p style="font-size:11px;color:#aaa">
        Rate source: Frankfurter (ECB blended) · Automated daily email
      </p>
    </body></html>
    """
    return subject, html


def send_email(subject: str, html_body: str):
    """Send the email via Gmail SMTP."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = SENDER_EMAIL
    msg["To"]      = RECEIVER_EMAIL
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(SENDER_EMAIL, SENDER_PASS)
        server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
    print(f"✅ Email sent: {subject}")


def main():
    today         = date.today()
    today_rate    = fetch_rate(today)
    yesterday_rate = load_yesterday_rate()

    subject, html = build_email(today_rate, yesterday_rate)
    send_email(subject, html)
    save_rate(today_rate)  # saved so GitHub Actions commits it back


if __name__ == "__main__":
    main()
