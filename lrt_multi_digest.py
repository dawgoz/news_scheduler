import os
from datetime import datetime, timezone
from dateutil import tz
import feedparser
import requests
import trafilatura
from dotenv import load_dotenv
from openai import OpenAI
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# -------------------------
# CONFIG
# -------------------------
load_dotenv()

TOPICS = {
    "Lietuvoje": "https://www.lrt.lt/naujienos/lietuvoje?rss",
    "Pasaulyje": "https://www.lrt.lt/naujienos/pasaulyje?rss",
    "Mokslas ir IT": "https://www.lrt.lt/naujienos/mokslas-ir-it?rss",
    "Verslas": "https://www.lrt.lt/naujienos/verslas?rss",
    "Sportas": "https://www.lrt.lt/naujienos/sportas?rss"
}

MAX_ARTICLES_PER_TOPIC = 5
LOCAL_TZ = tz.gettz("Europe/Vilnius")

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")

# -------------------------
# HELPERS
# -------------------------

def is_target_time(hour=7):
    local_tz = tz.gettz("Europe/Vilnius")
    now = datetime.now(local_tz)
    return now.hour == hour

def is_today(st):
    if st is None:
        return True
    dt_utc = datetime(*st[:6], tzinfo=timezone.utc)
    dt_local = dt_utc.astimezone(LOCAL_TZ)
    return dt_local.date() == datetime.now(LOCAL_TZ).date()


def fetch_html(url):
    r = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    r.encoding = r.apparent_encoding or "utf-8"
    return r.text


def extract_text(html):
    text = trafilatura.extract(html)
    return (text or "").strip()


def summarize_lt(title, text):
    text = text[:12000]
    prompt = f"""
Tu esi profesionalus naujienų redaktorius Lietuvoje.

Pateik šio straipsnio santrauką lietuvių kalba.

Reikalavimai:
- 3–5 punktai
- 1 sakinys: "Kodėl tai svarbu Lietuvai?"
- Jei trūksta informacijos: "Neaišku iš straipsnio."

Pavadinimas: {title}

Straipsnis:
{text}
"""
    resp = client.responses.create(model=MODEL, input=prompt)
    return resp.output_text.strip()


# -------------------------
# HTML GENERATION
# -------------------------
def build_html(date_str, sections):
    content = ""
    for topic, items in sections.items():
        if not items:
            continue

        content += f"<h2>{topic}</h2>"
        for it in items:
            content += f"""
            <div class="card">
                <h3>{it['title']}</h3>
                <div class="summary">{it['summary'].replace("\n", "<br>")}</div>
                <a href="{it['url']}" target="_blank">Skaityti pilną straipsnį →</a>
            </div>
            """

    return f"""<!DOCTYPE html>
<html lang="lt">
<head>
<meta charset="UTF-8">
<title>LRT santrauka — {date_str}</title>
<style>
body {{
    font-family: Arial, sans-serif;
    background: #f4f6f8;
    padding: 20px;
}}
.container {{
    max-width: 900px;
    margin: auto;
}}
.card {{
    background: white;
    padding: 18px;
    margin-bottom: 14px;
    border-radius: 10px;
    box-shadow: 0 3px 10px rgba(0,0,0,0.08);
}}
h1 {{ text-align: center; }}
h2 {{ margin-top: 40px; }}
a {{ color: #1a73e8; text-decoration: none; }}
</style>
</head>
<body>
<div class="container">
<h1>LRT dienos santrauka — {date_str}</h1>
{content}
</div>
</body>
</html>
"""


# -------------------------
# EMAIL
# -------------------------
def send_email(subject, html):
    to_email = os.getenv("NEWS_TO_EMAIL").strip()
    from_email = os.getenv("NEWS_FROM_EMAIL").strip()
    user = os.getenv("NEWS_SMTP_USER").strip()
    password = os.getenv("NEWS_SMTP_PASS").strip().replace(" ", "")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to_email
    msg.attach(MIMEText("Peržiūrėkite HTML režimu.", "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    ctx = ssl.create_default_context()
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls(context=ctx)
        server.login(user, password)
        server.sendmail(from_email, [to_email], msg.as_string())


# -------------------------
# MAIN
# -------------------------
def main():
    sections = {}

    for topic_name, rss_url in TOPICS.items():
        feed = feedparser.parse(rss_url)
        items = []

        for e in feed.entries:
            st = getattr(e, "published_parsed", None) or getattr(e, "updated_parsed", None)
            if not is_today(st):
                continue

            title = e.title
            link = e.link

            try:
                html = fetch_html(link)
                text = extract_text(html)

                if len(text) < 200:
                    summary = "Nepavyko ištraukti teksto."
                else:
                    summary = summarize_lt(title, text)

                items.append({"title": title, "summary": summary, "url": link})

            except Exception as ex:
                items.append({"title": title, "summary": f"Klaida: {ex}", "url": link})

            if len(items) >= MAX_ARTICLES_PER_TOPIC:
                break

        sections[topic_name] = items

    date_str = datetime.now(LOCAL_TZ).strftime("%Y-%m-%d")
    html_doc = build_html(date_str, sections)

    file_name = f"lrt_digest_{date_str}.html"
    # with open(file_name, "w", encoding="utf-8") as f:
    #     f.write(html_doc)

    send_email(f"LRT santrauka — {date_str}", html_doc)

    # if is_target_time(7):
    #     send_email(f"LRT santrauka — {date_str}", html_doc)
    #     print("✅ Email sent")
    # else:
    #     print("⏱ Not 07:00 Vilnius time — skipping email")

    print("✅ Multi-topic digest created and emailed!")


if __name__ == "__main__":
    main()