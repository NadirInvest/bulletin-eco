"""
Bulletin économique quotidien : collecte RSS -> article IA -> fichiers Markdown (+ Telegram optionnel).
Dépendances gratuites : pip install feedparser requests
Variables d'environnement : GEMINI_API_KEY (obligatoire), TELEGRAM_TOKEN et TELEGRAM_CHAT_ID (optionnels)
"""
import os
import datetime
import pathlib
import html
import re
import feedparser
import requests

# --- Configuration -----------------------------------------------------------
# Ajoutez ici vos sources officielles (vérifiez que chaque URL fonctionne).
SOURCES = {
    "BCE": "https://www.ecb.europa.eu/rss/press.html",
    "Fed": "https://www.federalreserve.gov/feeds/press_all.xml",
}
LANGUES = {"fr": "français", "en": "English", "ar": "العربية"}
MAX_ITEMS_PAR_SOURCE = 5
MODELE = "gemini-3.1-flash-lite"  # vérifiez le nom du modèle gratuit actuellement disponible
SORTIE = pathlib.Path("docs")  # dossier publié par GitHub Pages

PROMPT = """Tu es rédacteur en chef d'un journal économique.
À partir UNIQUEMENT des éléments ci-dessous, rédige un bulletin d'actualité en {langue}.
Règles strictes :
- N'invente aucun fait ni aucun chiffre ; n'utilise que ce qui figure dans les éléments.
- Rédige avec tes propres mots (ne recopie pas les phrases des sources).
- Un titre accrocheur, puis 3 à 5 courts paragraphes, puis une ligne « Sources : » avec les noms des sources.
- Termine par : « Contenu généré par IA, ne constitue pas un conseil en investissement. »

Éléments :
{elements}
"""


# --- 1. Collecte -------------------------------------------------------------
def collecter():
    elements = []
    for nom, url in SOURCES.items():
        flux = feedparser.parse(url)
        for e in flux.entries[:MAX_ITEMS_PAR_SOURCE]:
            elements.append(
                f"[{nom}] {e.get('title', '')} — {e.get('summary', '')[:500]} ({e.get('link', '')})"
            )
    return elements


# --- 2. Rédaction ------------------------------------------------------------
def rediger(elements, langue):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODELE}:generateContent"
    corps = {"contents": [{"parts": [{"text": PROMPT.format(langue=langue, elements="\n".join(elements))}]}]}
    r = requests.post(url, params={"key": os.environ["GEMINI_API_KEY"]}, json=corps, timeout=120)
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]


# --- 3. Publication ----------------------------------------------------------
PAGE = """<!DOCTYPE html>
<html lang="{lang}" dir="{dir}">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{titre}</title>
<style>
body{{font-family:Georgia,serif;max-width:720px;margin:2rem auto;padding:0 1rem;line-height:1.6;color:#222}}
a{{color:#0a58ca}} h1{{line-height:1.2}} .meta{{color:#666;font-size:.9rem}}
li{{margin:.4rem 0}}
</style></head>
<body>{corps}</body></html>"""


def md_vers_html(texte):
    """Conversion minimale : titres, gras, paragraphes."""
    blocs = []
    for bloc in re.split(r"\n\s*\n", html.escape(texte.strip())):
        bloc = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", bloc)
        if bloc.startswith("#"):
            blocs.append("<h1>" + bloc.lstrip("# ").strip() + "</h1>")
        else:
            blocs.append("<p>" + bloc.replace("\n", "<br>") + "</p>")
    return "\n".join(blocs)


def publier(texte, code_langue, date):
    SORTIE.mkdir(exist_ok=True)
    chemin = SORTIE / f"{date}-{code_langue}.html"
    corps = '<p class="meta"><a href="index.html">&larr; Accueil</a> · ' + date + "</p>" + md_vers_html(texte)
    page = PAGE.format(lang=code_langue, dir="rtl" if code_langue == "ar" else "ltr", titre=f"Bulletin {date}", corps=corps)
    chemin.write_text(page, encoding="utf-8")
    return chemin


def construire_index():
    """Page d'accueil : liste des bulletins par date (récent en premier) et par langue."""
    par_date = {}
    for f in SORTIE.glob("*-*-*-*.html"):
        date, code = f.stem.rsplit("-", 1)
        par_date.setdefault(date, {})[code] = f.name
    lignes = ["<h1>Bulletin économique quotidien</h1>",
              "<p class=\"meta\">Contenu généré par IA, ne constitue pas un conseil en investissement.</p><ul>"]
    for date in sorted(par_date, reverse=True):
        liens = " · ".join(f'<a href="{nom}">{LANGUES.get(code, code)}</a>' for code, nom in sorted(par_date[date].items()))
        lignes.append(f"<li><strong>{date}</strong> : {liens}</li>")
    lignes.append("</ul>")
    page = PAGE.format(lang="fr", dir="ltr", titre="Bulletin économique quotidien", corps="\n".join(lignes))
    (SORTIE / "index.html").write_text(page, encoding="utf-8")


def envoyer_telegram(texte):
    token, chat = os.getenv("TELEGRAM_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if token and chat:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat, "text": texte[:4000]},
            timeout=30,
        )


def main():
    date = datetime.date.today().isoformat()
    elements = collecter()
    if not elements:
        print("Aucune actualité collectée.")
        return
    for code, nom in LANGUES.items():
        texte = rediger(elements, nom)
        print("Publié :", publier(texte, code, date))
        envoyer_telegram(texte)
    construire_index()


if __name__ == "__main__":
    main()
