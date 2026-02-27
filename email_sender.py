import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def send_html_email_individual(subject: str, html_doc: str) -> None:
    to_emails_raw = os.getenv("NEWS_TO_EMAIL", "")
    recipients = [e.strip() for e in to_emails_raw.split(",") if e.strip()]
    recipients = list(dict.fromkeys(recipients))  # preserve order, remove duplicates

    from_email = (os.getenv("NEWS_FROM_EMAIL") or "").strip()
    host = (os.getenv("NEWS_SMTP_HOST") or "smtp.gmail.com").strip()
    port = int((os.getenv("NEWS_SMTP_PORT") or "587").strip())
    user = (os.getenv("NEWS_SMTP_USER") or "").strip()

    password = (os.getenv("NEWS_SMTP_PASS") or "")
    password = password.strip().replace(" ", "").replace("\u00a0", "")

    if not recipients:
        raise RuntimeError("NEWS_TO_EMAIL is empty. Provide comma-separated recipients.")
    if not all([from_email, user, password]):
        raise RuntimeError("Missing NEWS_FROM_EMAIL / NEWS_SMTP_USER / NEWS_SMTP_PASS env vars.")
    if from_email != user:
        raise RuntimeError("For Gmail SMTP, set NEWS_FROM_EMAIL equal to NEWS_SMTP_USER.")

    ctx = ssl.create_default_context()

    with smtplib.SMTP(host, port, timeout=30) as server:
        server.ehlo()
        server.starttls(context=ctx)
        server.ehlo()
        server.login(user, password)

        for recipient in recipients:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = from_email
            msg["To"] = recipient

            msg.attach(MIMEText("Peržiūrėkite šį laišką HTML režimu.", "plain", "utf-8"))
            msg.attach(MIMEText(html_doc, "html", "utf-8"))

            server.sendmail(from_email, [recipient], msg.as_string())
            print(f"✅ Sent to {recipient}")

