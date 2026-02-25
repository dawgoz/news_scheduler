"""
LRT multi-topic RSS digest (morning + midday), OpenAI summaries, pretty HTML (LRT-like),
BREAKING badge, Top-3 highlights, and optional Vilnius weather block.
Sends separate emails to each recipient (Option 3).

Schedule idea (GitHub Actions, UTC):
- For 07:00 & 12:00 Vilnius with DST safe triggers run at: 04,05,09,10 UTC
  and this script will auto-decide whether it's "morning" (07) or "midday" (12).
"""

import os
import re
import html as html_lib
from datetime import datetime, timezone, time as dtime, timedelta
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
    "Sportas": "https://www.lrt.lt/naujienos/sportas?rss",
}

MAX_ARTICLES_PER_TOPIC_MORNING = int(os.getenv("MAX_ARTICLES_PER_TOPIC_MORNING", "6"))
MAX_ARTICLES_PER_TOPIC_MIDDAY = int(os.getenv("MAX_ARTICLES_PER_TOPIC_MIDDAY", "4"))

LOCAL_TZ = tz.gettz("Europe/Vilnius")

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")

# BREAKING if published within last N minutes
BREAKING_MINUTES = int(os.getenv("BREAKING_MINUTES", "90"))

# Optional: include weather block (Vilnius) in HTML/email
INCLUDE_WEATHER = os.getenv("INCLUDE_WEATHER", "1").strip() not in ("0", "false", "False")

# -------------------------
# HELPER METHODS
# -------------------------
def summary_to_html_list(summary: str) -> str:
    lines = [l.strip("-• ").strip() for l in summary.splitlines() if l.strip()]
    if not lines:
        return esc(summary)
    items = "".join(f"<li>{esc(line)}</li>" for line in lines)
    return f"<ul class='summary-list'>{items}</ul>"

# -------------------------
# TIME / DIGEST MODE
# -------------------------
def get_digest_type() -> str | None:
    """Return 'morning' at 07:xx, 'midday' at 12:xx Vilnius time, else None."""
    now = datetime.now(LOCAL_TZ)
    if now.hour == 7:
        return "morning"
    if now.hour == 12:
        return "midday"
    return None


def get_time_window_local(digest_type: str) -> tuple[datetime, datetime]:
    """
    Morning: today 00:00 -> now
    Midday:  today 07:00 -> now  (so it's 'only NEW since morning')
    """
    now = datetime.now(LOCAL_TZ)
    start_of_day = datetime.combine(now.date(), dtime(0, 0), tzinfo=LOCAL_TZ)
    if digest_type == "midday":
        start = datetime.combine(now.date(), dtime(7, 0), tzinfo=LOCAL_TZ)
    else:
        start = start_of_day
    return start, now


def titles_and_subject(date_str: str, digest_type: str) -> tuple[str, str, str]:
    """
    Returns (email_subject, html_title, header_title)
    """
    if digest_type == "morning":
        subject = f"[Ryto santrauka] LRT naujienos — {date_str}"
        header = f"LRT ryto naujienų santrauka — {date_str}"
        subtitle = "Svarbiausios šios dienos naujienos (nuo 00:00)."
    else:
        subject = f"[Vidurdienio atnaujinimas] LRT naujienos — {date_str}"
        header = f"LRT vidurdienio naujienų atnaujinimas — {date_str}"
        subtitle = "Naujos naujienos nuo 07:00 (ryto santraukos)."
    return subject, header, subtitle


def to_local_dt(struct_time_obj) -> datetime | None:
    """Convert feedparser struct_time (assumed UTC) to local datetime."""
    if struct_time_obj is None:
        return None
    dt_utc = datetime(*struct_time_obj[:6], tzinfo=timezone.utc)
    return dt_utc.astimezone(LOCAL_TZ)

# -------------------------
# FETCH / EXTRACT
# -------------------------
def fetch_html(url: str) -> str:
    r = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0 (lrt-digest)"} )
    r.raise_for_status()
    r.encoding = r.apparent_encoding or "utf-8"
    return r.text


def extract_text(article_html: str) -> str:
    text = trafilatura.extract(article_html, include_comments=False, include_tables=False)
    return (text or "").strip()

# -------------------------
# OPENAI: summarization + Top 3
# -------------------------
def summarize_lt(title: str, text: str) -> str:
    text = text[:12000]
    prompt = f"""
Tu esi profesionalus naujienų redaktorius Lietuvoje.

Užduotis: pateik šio straipsnio santrauką lietuvių kalba.

Reikalavimai:
- Rašyk tik lietuviškai.
- 3–5 punktai.
- 1 sakinys: "Kodėl tai svarbu Lietuvai?"
- Jokio clickbait.
- Jei trūksta faktų: "Neaišku iš straipsnio."

Pavadinimas: {title}

Straipsnio tekstas:
{text}
""".strip()

    resp = client.responses.create(model=MODEL, input=prompt)
    return resp.output_text.strip()


def pick_top3_highlights(items: list[dict], digest_type: str) -> list[str]:
    """
    One extra OpenAI call: select top 3 by importance.
    Returns 3 bullet strings.
    """
    if not items:
        return []

    # Keep it compact
    lines = []
    for i, it in enumerate(items[:30], 1):
        published = it.get("published_local_str", "")
        topic = it.get("topic", "")
        lines.append(f"{i}) [{topic}] {it['title']} ({published})")

    mode_hint = "Ryto santrauka" if digest_type == "morning" else "Vidurdienio atnaujinimas"
    prompt = f"""
Tu esi naujienų redaktorius. {mode_hint}.
Iš pateikto sąrašo parink 3 svarbiausias naujienas.

Taisyklės:
- Atsakyk tik 3 eilutėmis.
- Kiekviena eilutė: "• <antraštė> — <kodėl svarbu (iki 12 žodžių)>"
- Lietuviškai.

Sąrašas:
{chr(10).join(lines)}
""".strip()

    try:
        resp = client.responses.create(model=MODEL, input=prompt)
        out = resp.output_text.strip()
        bullets = [ln.strip() for ln in out.splitlines() if ln.strip()]
        # ensure 3-ish
        return bullets[:3]
    except Exception:
        return []


# -------------------------
# OPTIONAL: Weather (Vilnius) via Open-Meteo (no key)
# -------------------------
def get_vilnius_weather_summary() -> str | None:
    """
    Returns short LT text like: "Vilnius: dabar 2°C, vėjas 4 m/s, šiandien 0…4°C."
    Graceful failure: returns None if API fails.
    """
    if not INCLUDE_WEATHER:
        return None
    try:
        # Vilnius coords
        lat, lon = 54.6872, 25.2797
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            "&current=temperature_2m,wind_speed_10m"
            "&daily=temperature_2m_max,temperature_2m_min"
            "&timezone=Europe%2FVilnius"
        )
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        data = r.json()

        cur = data.get("current", {})
        daily = data.get("daily", {})
        t_now = cur.get("temperature_2m")
        w_now = cur.get("wind_speed_10m")
        tmin = (daily.get("temperature_2m_min") or [None])[0]
        tmax = (daily.get("temperature_2m_max") or [None])[0]

        parts = []
        if t_now is not None:
            parts.append(f"dabar {t_now}°C")
        if w_now is not None:
            parts.append(f"vėjas {w_now} m/s")
        if tmin is not None and tmax is not None:
            parts.append(f"šiandien {tmin}…{tmax}°C")

        if not parts:
            return None

        return "Vilnius: " + ", ".join(parts) + "."
    except Exception:
        return None


# -------------------------
# HTML helpers
# -------------------------
def esc(s: str) -> str:
    return html_lib.escape(s or "", quote=True)


def link_domain(url: str) -> str:
    m = re.match(r"^https?://([^/]+)/", url or "")
    return m.group(1) if m else ""


def build_html(date_str: str, header: str, subtitle: str, sections: dict[str, list[dict]], top3: list[str], weather_line: str | None) -> str:
    # Build sections with cards
    sections_html = []
    for topic, items in sections.items():
        if not items:
            continue
        cards = []
        for it in items:
            badge = ""
            if it.get("is_breaking"):
                badge = '<span class="badge breaking">NAUJA</span>'

            published = esc(it.get("published_local_str", ""))
            domain = esc(link_domain(it["url"]))
            cards.append(f"""
              <article class="card">
                <div class="card-top">
                  <h3 class="card-title">{badge}{esc(it['title'])}</h3>
                  <div class="meta">
                    <span class="meta-item">{published}</span>
                    <span class="dot">•</span>
                    <span class="meta-item">{esc(topic)}</span>
                    <span class="dot">•</span>
                    <a class="meta-link" href="{esc(it['url'])}" target="_blank" rel="noopener noreferrer">Skaityti {domain}</a>
                  </div>
                </div>
                <div class="card-body">{summary_to_html_list(it['summary'])}</div>
              </article>
            """)
        sections_html.append(f"""
          <section class="topic">
            <div class="topic-head">
              <h2 class="topic-title">{esc(topic)}</h2>
              <div class="topic-count">{len(items)} vnt.</div>
            </div>
            <div class="cards">
              {''.join(cards)}
            </div>
          </section>
        """)

    # Top 3 block
    top3_html = ""
    if top3:
        top3_lines = "".join(f"<li>{esc(line.lstrip('•').strip())}</li>" for line in top3)
        top3_html = f"""
          <section class="top3">
            <div class="top3-head">
              <div class="top3-kicker">Svarbiausia</div>
              <h2 class="top3-title">Top 3 šiandien</h2>
            </div>
            <ol class="top3-list">{top3_lines}</ol>
          </section>
        """

    weather_html = ""
    if weather_line:
        weather_html = f"""
          <div class="weather">
            <span class="weather-dot"></span>
            <span>{esc(weather_line)}</span>
          </div>
        """

    body_content = "".join(sections_html) if sections_html else """
      <div class="empty">
        Šiuo metu naujienų šiame lange nerasta. Bandyk vėliau.
      </div>
    """

    generated_at = datetime.now(LOCAL_TZ).strftime("%Y-%m-%d %H:%M")

    # A “LRT-like” feel: red accent, clean layout, light background, strong header
    return f"""<!doctype html>
<html lang="lt">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(header)}</title>
  <style>
    :root {{
      --bg: #f3f4f6;
      --panel: #ffffff;
      --text: #111827;
      --muted: #6b7280;
      --border: #e5e7eb;
      --shadow: 0 8px 24px rgba(17, 24, 39, 0.08);
      --accent: #0b3d91;          /* dark blue */
      --accent-soft: rgba(11, 61, 145, 0.10);
      --radius: 14px;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial;
      line-height: 1.55;
    }}
    .topbar {{
      background: var(--panel);
      border-bottom: 1px solid var(--border);
    }}
    .topbar-inner {{
      max-width: 980px;
      margin: 0 auto;
      padding: 12px 16px;
      display: flex;
      align-items: center;
      gap: 12px;
    }}
    .brand {{
      display: flex;
      align-items: center;
      gap: 10px;
      font-weight: 800;
      letter-spacing: 0.2px;
    }}
    .logo {{
      width: 34px;
      height: 34px;
      border-radius: 10px;
      background: var(--accent);
      color: #fff;
      display: grid;
      place-items: center;
      font-weight: 900;
    }}
    .brand small {{
      color: var(--muted);
      font-weight: 600;
    }}
    .wrap {{
      max-width: 980px;
      margin: 18px auto 48px;
      padding: 0 16px;
    }}
    .hero {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      padding: 18px 18px 14px;
    }}
    .hero h1 {{
      margin: 0 0 6px;
      font-size: 22px;
    }}
    .hero .sub {{
      margin: 0;
      color: var(--muted);
      font-size: 14px;
    }}
    .hero .meta2 {{
      margin-top: 10px;
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
      color: var(--muted);
      font-size: 13px;
    }}
    .pill {{
      border: 1px solid var(--border);
      background: #fff;
      padding: 6px 10px;
      border-radius: 999px;
      display: inline-flex;
      gap: 8px;
      align-items: center;
    }}
    .pill b {{ color: var(--text); }}
    .weather {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 6px 10px;
      border-radius: 999px;
      border: 1px solid var(--border);
      background: #fff;
    }}
    .weather-dot {{
      width: 8px; height: 8px;
      border-radius: 999px;
      background: var(--accent);
      display: inline-block;
    }}
    .top3 {{
      margin-top: 14px;
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      padding: 16px 18px;
    }}
    .top3-kicker {{
      display: inline-block;
      background: var(--accent-soft);
      color: var(--accent);
      padding: 4px 10px;
      border-radius: 999px;
      font-weight: 700;
      font-size: 12px;
    }}
    .top3-title {{
      margin: 10px 0 8px;
      font-size: 18px;
    }}
    .top3-list {{
      margin: 0;
      padding-left: 18px;
      color: var(--text);
    }}
    .top3-list li {{
      margin: 6px 0;
    }}

    .topic {{
      margin-top: 16px;
    }}
    .topic-head {{
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      padding: 0 2px;
      margin-bottom: 10px;
    }}
    .topic-title {{
      margin: 0;
      font-size: 16px;
    }}
    .topic-count {{
      color: var(--muted);
      font-size: 13px;
    }}
    .cards {{
      display: grid;
      grid-template-columns: 1fr;
      gap: 12px;
    }}
    @media (min-width: 860px) {{
      .cards {{ grid-template-columns: 1fr 1fr; }}
    }}
    .card {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      padding: 14px 14px 12px;
    }}
    .card-title {{
      margin: 0;
      font-size: 15px;
    }}
    .meta {{
      margin-top: 6px;
      color: var(--muted);
      font-size: 12.5px;
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      align-items: center;
    }}
    .dot {{ opacity: 0.6; }}
    .meta-link {{
      color: var(--muted);
      text-decoration: none;
      border-bottom: 1px dotted rgba(107,114,128,0.6);
    }}
    .meta-link:hover {{ color: var(--text); }}
    .card-body {{
      margin-top: 10px;
      font-size: 13.5px;
      color: var(--text);
    }}
    .card-actions {{
      margin-top: 12px;
      display: flex;
      justify-content: flex-end;
    }}
    .btn {{
      display: inline-block;
      background: #fff;
      border: 1px solid rgba(11, 61, 145, 0.10);
      color: var(--accent);
      padding: 8px 10px;
      border-radius: 10px;
      text-decoration: none;
      font-weight: 700;
      font-size: 13px;
    }}
    .btn:hover {{
      background: var(--accent-soft);
      border-color: rgba(208,2,27,0.55);
    }}

    .badge {{
      display: inline-block;
      margin-right: 8px;
      padding: 3px 8px;
      border-radius: 999px;
      font-size: 11px;
      font-weight: 900;
      vertical-align: middle;
      letter-spacing: 0.3px;
    }}
    .badge.breaking {{
      background: var(--accent);
      color: #fff;
    }}
    .summary-list {{
      margin: 8px 0 0 18px;
      padding: 0;
    }}

    .summary-list li {{
      margin-bottom: 6px;
    }}

    .empty {{
      margin-top: 16px;
      background: var(--panel);
      border: 1px dashed var(--border);
      border-radius: var(--radius);
      padding: 16px;
      color: var(--muted);
      text-align: center;
    }}
    .footer {{
      margin-top: 18px;
      text-align: center;
      color: var(--muted);
      font-size: 12px;
    }}
  </style>
</head>
<body>
  <div class="topbar">
    <div class="topbar-inner">
      <div class="brand">
        <div class="logo">LRT</div>
        <div>
          Naujienų santrauka <small>RSS + AI</small>
        </div>
      </div>
    </div>
  </div>

  <div class="wrap">
    <section class="hero">
      <h1>{esc(header)}</h1>
      <p class="sub">{esc(subtitle)}</p>
      <div class="meta2">
        <span class="pill"><b>Šaltinis:</b> LRT RSS</span>
        <span class="pill"><b>Data:</b> {esc(date_str)}</span>
        <span class="pill"><b>Sugeneruota:</b> {esc(generated_at)}</span>
        {weather_html}
      </div>
    </section>

    {top3_html}

    {body_content}

    <div class="footer">
      Pastaba: santraukos generuojamos automatiškai; detales tikrink pilnuose straipsniuose.
    </div>
  </div>
</body>
</html>
"""


# -------------------------
# EMAIL: (individual)
# -------------------------
def send_html_email_individual(subject: str, html_doc: str) -> None:
    to_emails_raw = os.getenv("NEWS_TO_EMAIL", "")
    recipients = [e.strip() for e in to_emails_raw.split(",") if e.strip()]

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
            # print(f"✅ Sent to {recipient}")


# -------------------------
# MAIN
# -------------------------
def main():
    digest_type = get_digest_type()
    if digest_type not in ("morning", "midday"):
        print("⏱ Not scheduled digest time (Vilnius 07:00 / 12:00) — exiting.")
        return

    window_start, window_end = get_time_window_local(digest_type)
    date_str = datetime.now(LOCAL_TZ).strftime("%Y-%m-%d")
    subject, header, subtitle = titles_and_subject(date_str, digest_type)

    max_per_topic = MAX_ARTICLES_PER_TOPIC_MORNING if digest_type == "morning" else MAX_ARTICLES_PER_TOPIC_MIDDAY

    # Collect items per topic with time-window filtering + de-dup across topics
    sections: dict[str, list[dict]] = {t: [] for t in TOPICS.keys()}
    global_seen_urls: set[str] = set()
    flat_items: list[dict] = []

    now_local = datetime.now(LOCAL_TZ)
    breaking_delta = timedelta(minutes=BREAKING_MINUTES)

    for topic_name, rss_url in TOPICS.items():
        feed = feedparser.parse(rss_url)
        count = 0

        for e in feed.entries:
            title = getattr(e, "title", None) or getattr(e, "link", "")
            url = getattr(e, "link", None)
            if not url:
                continue

            # Deduplicate across topics
            if url in global_seen_urls:
                continue

            st = getattr(e, "published_parsed", None) or getattr(e, "updated_parsed", None)
            published_local = to_local_dt(st)

            # Filter by time window if we have dates; if missing, include (conservative)
            if published_local is not None:
                if not (window_start <= published_local <= window_end):
                    continue

            # Fetch + extract + summarize
            try:
                article_html = fetch_html(url)
                text = extract_text(article_html)

                if len(text) < 200:
                    summary = "Nepavyko patikimai ištraukti teksto."
                else:
                    summary = summarize_lt(title, text)
            except Exception as ex:
                summary = f"Klaida: {ex}"

            published_str = published_local.strftime("%H:%M") if published_local else ""
            is_breaking = bool(published_local and (now_local - published_local) <= breaking_delta)

            item = {
                "topic": topic_name,
                "title": title,
                "url": url,
                "summary": summary,
                "published_local": published_local,
                "published_local_str": published_str,
                "is_breaking": is_breaking,
            }

            sections[topic_name].append(item)
            flat_items.append(item)
            global_seen_urls.add(url)

            count += 1
            if count >= max_per_topic:
                break

    # Top 3 highlights (based on list of collected items)
    # For midday, this will reflect "new since 07:00".
    top3 = pick_top3_highlights(flat_items, digest_type)

    # Optional weather
    weather_line = get_vilnius_weather_summary()

    # Build HTML + save
    html_doc = build_html(date_str, header, subtitle, sections, top3, weather_line)

    # file_name = f"lrt_digest_{digest_type}_{date_str}.html"
    # with open(file_name, "w", encoding="utf-8") as f:
    #     f.write(html_doc)
    # print(f"✅ Saved HTML: {file_name}")

    # Send (individual)
    send_html_email_individual(subject, html_doc)
    # print("✅ Done.")


if __name__ == "__main__":
    main()