import html as html_lib
import re
from datetime import datetime
from typing import Any

from config import LOCAL_TZ


def esc(s: str) -> str:
    return html_lib.escape(s or "", quote=True)


def summary_to_html_list(summary: str) -> str:
    lines = [l.strip("-• ").strip() for l in summary.splitlines() if l.strip()]
    if not lines:
        return esc(summary)
    items = "".join(f"<li>{esc(line)}</li>" for line in lines)
    return f"<ul class='summary-list'>{items}</ul>"


def link_domain(url: str) -> str:
    m = re.match(r"^https?://([^/]+)/", url or "")
    return m.group(1) if m else ""


def build_html(
    date_str: str,
    header: str,
    subtitle: str,
    sections: dict[str, list[dict[str, Any]]],
    top3: list[str],
    weather_line: str | None,
) -> str:
    # Build sections with cards
    sections_html: list[str] = []
    for topic, items in sections.items():
        if not items:
            continue
        cards: list[str] = []
        for it in items:
            badge = ""
            if it.get("is_breaking"):
                badge = '<span class="badge breaking">NAUJA</span>'

            published = esc(it.get("published_local_str", ""))
            domain = esc(link_domain(it["url"]))
            cards.append(
                f"""
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
            """
            )
        sections_html.append(
            f"""
          <section class="topic">
            <div class="topic-head">
              <h2 class="topic-title">{esc(topic)}</h2>
              <div class="topic-count">{len(items)} vnt.</div>
            </div>
            <div class="cards">
              {''.join(cards)}
            </div>
          </section>
        """
        )

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

    body_content = (
        "".join(sections_html)
        if sections_html
        else """
      <div class="empty">
        Šiuo metu naujienų šiame lange nerasta. Bandyk vėliau.
      </div>
    """
    )

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

