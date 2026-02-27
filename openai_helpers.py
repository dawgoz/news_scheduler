from typing import Any

from config import MODEL, client


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


def pick_top3_highlights(items: list[dict[str, Any]], digest_type: str) -> list[str]:
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
        return bullets[:3]
    except Exception:
        return []

