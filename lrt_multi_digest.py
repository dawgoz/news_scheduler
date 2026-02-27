"""
LRT multi-topic RSS digest (morning + midday), OpenAI summaries, pretty HTML (LRT-like),
BREAKING badge, Top-3 highlights, and optional Vilnius weather block.
Sends separate emails to each recipient (Option 3).

Schedule idea (GitHub Actions, UTC):
- For 07:00 & 12:00 Vilnius with DST safe triggers run at: 04,05,09,10 UTC
  and this script will auto-decide whether it's "morning" (07) or "midday" (12).
"""

from datetime import datetime, timedelta

import feedparser

from config import (
    BREAKING_MINUTES,
    LOCAL_TZ,
    MAX_ARTICLES_PER_TOPIC_EVENING,
    MAX_ARTICLES_PER_TOPIC_MIDDAY,
    MAX_ARTICLES_PER_TOPIC_MORNING,
    TOPICS,
)
from email_sender import send_html_email_individual
from fetcher import extract_text, fetch_html
from html_builder import build_html
from openai_helpers import pick_top3_highlights, summarize_lt
from time_utils import get_digest_type, get_time_window_local, titles_and_subject, to_local_dt
from weather import get_vilnius_weather_summary


# -------------------------
# MAIN
# -------------------------
def main():
    digest_type = get_digest_type()
    # if digest_type not in ("morning", "midday"):
    #     print("Not scheduled digest time (Vilnius 07:00 / 12:00) — exiting.")
    #     return

    window_start, window_end = get_time_window_local(digest_type)
    date_str = datetime.now(LOCAL_TZ).strftime("%Y-%m-%d")
    subject, header, subtitle = titles_and_subject(date_str, digest_type)

    match digest_type:
        case "morning":
            max_per_topic = MAX_ARTICLES_PER_TOPIC_MORNING
        case "midday":
            max_per_topic = MAX_ARTICLES_PER_TOPIC_MIDDAY
        case "evening":
            max_per_topic = MAX_ARTICLES_PER_TOPIC_EVENING
        case _:
            print("Not scheduled digest time (Vilnius 07:00 / 12:00) — exiting.")
            return

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