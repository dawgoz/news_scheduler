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
    items = "".join(f"<li style='margin-bottom: 6px;'>{esc(line)}</li>" for line in lines)
    return f"<ul style='margin: 8px 0 0 18px; padding: 0;'>{items}</ul>"


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
    sections_html: list[str] = []
    for topic, items in sections.items():
        if not items:
            continue
        cards: list[str] = []
        for i, it in enumerate(items):
            badge = ""
            if it.get("is_breaking"):
                badge = f"<span style='background: #0b3d91; color: #fff; padding: 3px 8px; font-size: 11px; font-weight: bold; border-radius: 999px; margin-right: 8px;'>NAUJA</span>"

            published = esc(it.get("published_local_str", ""))
            domain = esc(link_domain(it["url"]))
            summary = summary_to_html_list(it["summary"])
            
            card_bg = "#ffffff"
            cards.append(
                f"""
                <td style="background: {card_bg}; border: 1px solid #e5e7eb; padding: 16px; vertical-align: top; border-radius:14px;">
                  <div style="margin: 0; font-size: 17px; font-weight: bold; color: #111827; line-height: 1.4;">
                    {badge}{esc(it['title'])}
                  </div>
                  <div style="margin-top: 6px; color: #6b7280; font-size: 13px; line-height: 1.5;">
                    {published} &bull; {esc(topic)} &bull; <a href="{esc(it['url'])}" style="color: #6b7280; text-decoration: none; border-bottom: 1px dotted #6b7280;">Skaityti {domain}</a>
                  </div>
                  <div style="margin-top: 10px; font-size: 15px; color: #111827; line-height: 1.6;">
                    {summary}
                  </div>
                </td>
                """
            )
        
        cards_row = "".join(cards)
        sections_html.append(
            f"""
            <tr>
              <td style="padding: 16px 16px 0 16px;">
                <table width="100%" cellpadding="0" cellspacing="0" border="0" >
                  <tr>
                    <td style="padding-bottom: 10px;">
                      <span style="font-size: 16px; font-weight: bold; color: #111827;">{esc(topic)}</span>
                      <span style="color: #6b7280; font-size: 13px; margin-left: 8px;">{len(items)} vnt.</span>
                    </td>
                  </tr>
                  <tr>
                    <td>
                      <table width="100%" cellpadding="0" cellspacing="0" border="0">
                        <tr>
                          {cards_row}
                        </tr>
                      </table>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
            """
        )

    top3_html = ""
    if top3:
        top3_items = "".join(
            f"""
            <tr>
              <td style='width: 24px; padding: 0 8px 8px 0; vertical-align: top; font-size: 15px; font-weight: bold; color: #111827;'>
                {i}.
              </td>
              <td style='padding: 0 0 8px 0; vertical-align: top; font-size: 15px; line-height: 1.6; color: #111827;'>
                {esc(line.lstrip('•').strip())}
              </td>
            </tr>
            """
            for i, line in enumerate(top3, start=1)
        )
        top3_html = f"""
        <tr>
          <td style="padding: 14px 16px 0 16px;">
            <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background: #ffffff; border: 1px solid #e5e7eb; border-radius:14px;">
              <tr>
                <td style="padding: 16px;">
                  <span style="background: rgba(11,61,145,0.1); color: #0b3d91; padding: 4px 10px; border-radius: 999px; font-weight: bold; font-size: 12px;">Svarbiausia</span>
                  <div style="margin-top: 10px; font-size: 18px; font-weight: bold; color: #111827;">Top 3 šiandien</div>
                  <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-top: 8px;">
                    {top3_items}
                  </table>
                </td>
              </tr>
            </table>
          </td>
        </tr>
        """

    weather_td = ""
    if weather_line:
        weather_td = f"""<span style="display: inline-block; background: #fff; border: 1px solid #e5e7eb; padding: 6px 10px; border-radius: 999px; margin-top: 8px;">
          {esc(weather_line)}
        </span>"""

    body_content = (
        "".join(sections_html)
        if sections_html
        else """
        <tr>
          <td style="padding-top: 16px; text-align: center; color: #6b7280; background: #fff; border: 1px dashed #e5e7eb; padding: 16px;">
            Šiuo metu naujienų šiame lange nerasta. Bandyk vėliau.
          </td>
        </tr>
        """
    )

    generated_at = datetime.now(LOCAL_TZ).strftime("%Y-%m-%d %H:%M")

    return f"""<!DOCTYPE html>
<html lang="lt">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(header)}</title>
  <!--[if mso]>
  <style type="text/css">
    body, table, td {{ font-family: Arial, Helvetica, sans-serif !important; }}
  </style>
  <![endif]-->
</head>
<body style="margin: 0; padding: 0; background: #f3f4f6; font-family: Arial, Helvetica, sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background: #f3f4f6;">
    <tr>
      <td align="center">
        <table width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width: 600px; background: #ffffff;">
          <!-- Header -->
          <tr>
            <td style="background: #ffffff; border-bottom: 1px solid #e5e7eb; padding: 12px 16px;">
              <table width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td>
                    <span style="display: inline-block; width: 34px; height: 34px; background: #0b3d91; color: #fff; text-align: center; line-height: 34px; font-weight: bold; border-radius: 10px; margin-right: 10px;">LRT</span>
                    <span style="font-weight: bold; font-size: 16px; color: #111827;">Naujienų santrauka</span>
                    <span style="color: #6b7280; font-size: 14px; font-weight: 600;">RSS + AI</span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          
          <!-- Hero -->
          <tr>
            <td style="padding: 18px 16px;">
              <table width="100%" cellpadding="0" cellspacing="0" border="0" style="border: 1px solid #e5e7eb; border-radius: 14px;">
                <tr>
                  <td style="padding: 18px;">
                    <div style="font-size: 22px; font-weight: bold; color: #111827; margin-bottom: 6px;">{esc(header)}</div>
                    <p style="margin: 0; color: #6b7280; font-size: 14px;">{esc(subtitle)}</p>
                    <div style="margin-top: 10px;">
                      <span style="display: inline-block; background: #fff; border: 1px solid #e5e7eb; padding: 6px 10px; border-radius: 999px; font-size: 13px; margin-right: 8px; margin-top: 8px;">
                        <b style="color: #111827;">Šaltinis:</b> LRT RSS
                      </span>
                      <span style="display: inline-block; background: #fff; border: 1px solid #e5e7eb; padding: 6px 10px; border-radius: 999px; font-size: 13px; margin-right: 8px; margin-top: 8px;">
                        <b style="color: #111827;">Data:</b> {esc(date_str)}
                      </span>
                      <span style="display: inline-block; background: #fff; border: 1px solid #e5e7eb; padding: 6px 10px; border-radius: 999px; font-size: 13px; margin-right: 8px; margin-top: 8px;">
                        <b style="color: #111827;">Sugeneruota:</b> {esc(generated_at)}
                      </span>
                      {weather_td}
                    </div>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Top 3 -->
          {top3_html}

          <!-- Content -->
          {body_content}

          <!-- Footer -->
          <tr>
            <td style="padding: 18px; text-align: center; color: #6b7280; font-size: 12px;">
              Pastaba: santraukos generuojamos automatiškai; detales tikrink pilnuose straipsniuose.
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""
