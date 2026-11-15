"""
Bulletin économique quotidien (version 2 : articles par rubrique + design).
Collecte RSS -> articles IA (JSON) -> pages HTML dans docs/ (+ Telegram optionnel).
Dépendances gratuites : pip install feedparser requests
Variables d'environnement : GEMINI_API_KEY (obligatoire), TELEGRAM_TOKEN et TELEGRAM_CHAT_ID (optionnels)
"""
import os
import re
import json
import time
import html
import pathlib
import datetime
import feedparser
import requests

# --- Configuration -----------------------------------------------------------
SOURCES = {
    "BCE": "https://www.ecb.europa.eu/rss/press.html",
    "Fed": "https://www.federalreserve.gov/feeds/press_all.xml",
}
LANGUES = {"fr": "Français", "en": "English", "ar": "العربية"}
LANGUE_PROMPT = {"fr": "français", "en": "English", "ar": "arabe (العربية)"}
MAX_ITEMS_PAR_SOURCE = 8
MAX_ARTICLES = 7
MODELE = "gemini-3.1-flash-lite"  # vérifiez le nom du modèle gratuit actuellement disponible
PAUSE_ENTRE_LANGUES = 20  # secondes, pour respecter le quota gratuit
SORTIE = pathlib.Path("docs")

RUBRIQUES = {
    "marches": {"fr": "Marchés", "en": "Markets", "ar": "الأسواق", "couleur": "#0d6efd"},
    "banques_centrales": {"fr": "Banques centrales", "en": "Central banks", "ar": "البنوك المركزية", "couleur": "#7a3cff"},
    "economie": {"fr": "Économie mondiale", "en": "World economy", "ar": "الاقتصاد العالمي", "couleur": "#13a89e"},
    "entreprises": {"fr": "Entreprises", "en": "Business", "ar": "الشركات", "couleur": "#e8590c"},
    "commerce": {"fr": "Commerce et échanges", "en": "Trade", "ar": "التجارة", "couleur": "#c2255c"},
    "autre": {"fr": "Autres actualités", "en": "Other news", "ar": "أخبار أخرى", "couleur": "#6c757d"},
}

TEXTES = {
    "fr": {"site": "Le Bulletin Économique", "sous": "L'essentiel de l'actualité économique du jour",
           "une": "À la une", "sources": "Sources", "accueil": "Accueil", "edition": "Édition du",
           "avert": "Contenu généré par IA, ne constitue pas un conseil en investissement.",
           "derniere": "Dernière édition", "precedentes": "Éditions précédentes"},
    "en": {"site": "The Economic Bulletin", "sous": "The day's economic news, in brief",
           "une": "Top story", "sources": "Sources", "accueil": "Home", "edition": "Edition of",
           "avert": "AI-generated content, not investment advice.",
           "derniere": "Latest edition", "precedentes": "Previous editions"},
    "ar": {"site": "النشرة الاقتصادية", "sous": "خلاصة أخبار الاقتصاد لهذا اليوم",
           "une": "الخبر الرئيسي", "sources": "المصادر", "accueil": "الرئيسية", "edition": "عدد",
           "avert": "محتوى مُنشأ بالذكاء الاصطناعي ولا يُعد نصيحة استثمارية.",
           "derniere": "آخر عدد", "precedentes": "الأعداد السابقة"},
}

PROMPT = """Tu es rédacteur en chef d'un journal économique. Écris en {langue}.
À partir UNIQUEMENT des éléments numérotés ci-dessous, produis entre 4 et {max_articles} courts articles distincts.
Règles strictes :
- N'invente aucun fait ni aucun chiffre ; utilise seulement ce qui figure dans les éléments.
- Rédige avec tes propres mots (ne recopie pas les phrases des sources).
- Classe les articles par importance : le premier est l'article « à la une ».
- Chaque article contient :
  "rubrique" : une valeur parmi {rubriques},
  "titre" : un titre clair et court,
  "chapeau" : 1 à 2 phrases qui résument l'essentiel,
  "texte" : un paragraphe de 3 à 4 phrases simples,
  "sources" : la liste des numéros des éléments utilisés (entiers).
- Réponds UNIQUEMENT avec un JSON valide de la forme : {{"articles": [ {{...}}, {{...}} ]}}

Éléments :
{elements}
"""


# --- 1. Collecte -------------------------------------------------------------
def nettoyer(texte):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(texte or ""))).strip()


def collecter():
    elements = []
    for nom, url in SOURCES.items():
        flux = feedparser.parse(url)
        for e in flux.entries[:MAX_ITEMS_PAR_SOURCE]:
            elements.append({
                "id": len(elements) + 1,
                "source": nom,
                "titre": nettoyer(e.get("title", "")),
                "resume": nettoyer(e.get("summary", ""))[:500],
                "lien": e.get("link", ""),
            })
    return elements


# --- 2. Rédaction ------------------------------------------------------------
def rediger(elements, code_langue):
    texte_elements = "\n".join(f"{e['id']}. [{e['source']}] {e['titre']} : {e['resume']}" for e in elements)
    prompt = PROMPT.format(langue=LANGUE_PROMPT[code_langue], max_articles=MAX_ARTICLES,
                           rubriques=", ".join(RUBRIQUES), elements=texte_elements)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODELE}:generateContent"
    corps = {"contents": [{"parts": [{"text": prompt}]}],
             "generationConfig": {"responseMimeType": "application/json"}}
    r = requests.post(url, params={"key": os.environ["GEMINI_API_KEY"]}, json=corps, timeout=180)
    r.raise_for_status()
    brut = r.json()["candidates"][0]["content"]["parts"][0]["text"]
    brut = re.sub(r"^```(?:json)?|```$", "", brut.strip(), flags=re.MULTILINE).strip()
    articles = json.loads(brut)["articles"]
    return [a for a in articles if a.get("titre") and a.get("texte")]


# --- 3. Mise en page ---------------------------------------------------------
CSS = """
:root{--bg:#f4f6fa;--carte:#fff;--texte:#1b2430;--doux:#5b6678;--marque:#0b2545;--bord:#e3e8ef}
@media (prefers-color-scheme:dark){:root{--bg:#0e141b;--carte:#17202a;--texte:#e8edf3;--doux:#9aa7b8;--marque:#0a1a2f;--bord:#263341}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--texte);line-height:1.7;
font-family:system-ui,-apple-system,"Segoe UI",Tahoma,"Noto Naskh Arabic",sans-serif}
a{color:inherit}
.wrap{max-width:980px;margin:0 auto;padding:0 16px}
header{background:linear-gradient(135deg,var(--marque),#15508a);color:#fff;padding:30px 0 22px}
.site{margin:0;font-size:1.9rem;letter-spacing:-.5px}
.sous{margin:.3rem 0 1.1rem;opacity:.85}
.langues{display:flex;gap:8px;flex-wrap:wrap}
.langues a{color:#fff;text-decoration:none;border:1px solid rgba(255,255,255,.55);padding:6px 16px;border-radius:999px;font-size:.92rem}
.langues a.actif{background:#fff;color:var(--marque);font-weight:700}
.date{margin:.9rem 0 0;font-size:.9rem;opacity:.8}
nav.rub{position:sticky;top:0;z-index:5;background:var(--bg);border-bottom:1px solid var(--bord);padding:10px 0}
nav.rub .wrap{display:flex;gap:8px;overflow-x:auto;white-space:nowrap}
nav.rub a{text-decoration:none;font-size:.88rem;padding:5px 14px;border-radius:999px;border:1px solid var(--bord);background:var(--carte)}
main{padding:22px 0 10px}
.une{background:var(--carte);border:1px solid var(--bord);border-radius:18px;padding:26px;margin-bottom:28px;
border-inline-start:8px solid var(--c)}
.une h2{font-size:1.7rem;line-height:1.3;margin:.4rem 0 .6rem}
.chapeau{font-size:1.08rem;font-weight:600;margin:0 0 .8rem}
.tag{display:inline-block;font-size:.78rem;font-weight:700;color:#fff;background:var(--c);padding:3px 11px;border-radius:999px}
h2.rubrique{font-size:1.25rem;margin:30px 0 14px;padding-inline-start:12px;border-inline-start:6px solid var(--c)}
.grille{display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:16px}
.carte{background:var(--carte);border:1px solid var(--bord);border-radius:14px;padding:18px}
.carte h3{font-size:1.12rem;line-height:1.35;margin:.1rem 0 .5rem}
.carte p,.une p{margin:.4rem 0}
.src{font-size:.82rem;color:var(--doux);margin-top:.8rem}
.src a{color:var(--doux)}
footer{padding:26px 0 40px;color:var(--doux);font-size:.85rem;text-align:center}
.edition{display:block;background:var(--carte);border:1px solid var(--bord);border-radius:14px;padding:18px 20px;margin-bottom:12px}
.edition .liens{display:flex;gap:8px;flex-wrap:wrap;margin-top:8px}
.edition .liens a{text-decoration:none;border:1px solid var(--bord);padding:5px 14px;border-radius:999px;font-size:.9rem}
.edition.grand{border-inline-start:8px solid #15508a;padding:24px}
.edition.grand .liens a{background:#15508a;color:#fff;border-color:#15508a;padding:8px 20px}
"""


def e(texte):
    return html.escape(str(texte))


def page(code, titre_onglet, contenu_header, contenu_nav, contenu_main):
    t = TEXTES[code]
    sens = "rtl" if code == "ar" else "ltr"
    return (
        f'<!DOCTYPE html><html lang="{code}" dir="{sens}"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{e(titre_onglet)}</title><style>{CSS}</style></head><body>"
        f'<header><div class="wrap">{contenu_header}</div></header>{contenu_nav}'
        f'<main><div class="wrap">{contenu_main}</div></main>'
        f'<footer><div class="wrap">{e(t["avert"])}</div></footer></body></html>'
    )


def entete(code, date, actif=None, lien_langues=True):
    t = TEXTES[code]
    h = f'<h1 class="site">{e(t["site"])}</h1><p class="sous">{e(t["sous"])}</p>'
    if lien_langues:
        liens = "".join(
            f'<a class="{"actif" if c == actif else ""}" href="{date}-{c}.html">{e(nom)}</a>'
            for c, nom in LANGUES.items())
        h += f'<div class="langues">{liens}</div>'
    h += f'<p class="date">{e(t["edition"])} {e(date)}</p>'
    return h


def liens_sources(article, elements, code):
    par_id = {x["id"]: x for x in elements}
    vus, liens = set(), []
    for i in article.get("sources", []):
        x = par_id.get(i) if isinstance(i, int) else None
        if x and x["source"] not in vus and x["lien"].startswith("http"):
            vus.add(x["source"])
            liens.append(f'<a href="{e(x["lien"])}" target="_blank" rel="noopener">{e(x["source"])}</a>')
    if not liens:
        return ""
    return f'<div class="src">{e(TEXTES[code]["sources"])} : {" · ".join(liens)}</div>'


def rubrique_de(article):
    r = article.get("rubrique")
    return r if r in RUBRIQUES else "autre"


def page_edition(articles, elements, code, date):
    t = TEXTES[code]
    une, reste = articles[0], articles[1:]
    r_une = rubrique_de(une)
    html_main = (
        f'<section class="une" style="--c:{RUBRIQUES[r_une]["couleur"]}">'
        f'<span class="tag">{e(t["une"])} · {e(RUBRIQUES[r_une][code])}</span>'
        f'<h2>{e(une["titre"])}</h2><p class="chapeau">{e(une.get("chapeau", ""))}</p>'
        f'<p>{e(une["texte"])}</p>{liens_sources(une, elements, code)}</section>'
    )
    groupes = {}
    for a in reste:
        groupes.setdefault(rubrique_de(a), []).append(a)
    chips = []
    for cle, infos in RUBRIQUES.items():
        if cle not in groupes:
            continue
        chips.append(f'<a href="#{cle}">{e(infos[code])}</a>')
        cartes = "".join(
            f'<article class="carte"><h3>{e(a["titre"])}</h3>'
            f'<p><strong>{e(a.get("chapeau", ""))}</strong></p><p>{e(a["texte"])}</p>'
            f'{liens_sources(a, elements, code)}</article>' for a in groupes[cle])
        html_main += (
            f'<h2 class="rubrique" id="{cle}" style="--c:{infos["couleur"]}">{e(infos[code])}</h2>'
            f'<div class="grille">{cartes}</div>')
    nav = f'<nav class="rub"><div class="wrap">{"".join(chips)}</div></nav>' if chips else ""
    return page(code, f'{t["site"]} · {date}', entete(code, date, actif=code), nav, html_main)


def publier(articles, elements, code, date):
    SORTIE.mkdir(exist_ok=True)
    chemin = SORTIE / f"{date}-{code}.html"
    chemin.write_text(page_edition(articles, elements, code, date), encoding="utf-8")
    return chemin


def lire_rubriques():
    chemin = SORTIE / "rubriques.json"
    return json.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else []


def enregistrer_rubrique(cle, nom, description, page_liste, couleur):
    """Chaque rubrique s'inscrit ici : elle apparaît automatiquement sur la page d'accueil."""
    SORTIE.mkdir(exist_ok=True)
    rubriques = [r for r in lire_rubriques() if r["cle"] != cle]
    rubriques.append({"cle": cle, "nom": nom, "description": description, "page": page_liste, "couleur": couleur})
    (SORTIE / "rubriques.json").write_text(json.dumps(rubriques, ensure_ascii=False, indent=1), encoding="utf-8")


def construire_index():
    par_date = {}
    for f in SORTIE.glob("*.html"):
        m = re.match(r"^(\d{4}-\d{2}-\d{2})-([a-z]{2})\.html$", f.name)
        if m:
            par_date.setdefault(m.group(1), {})[m.group(2)] = f.name
    t = TEXTES["fr"]
    dates = sorted(par_date, reverse=True)
    contenu = ""
    rubriques = lire_rubriques()
    if rubriques:
        contenu += '<h2 class="rubrique" style="--c:#7a3cff">Rubriques</h2>'
        for r in rubriques:
            contenu += (f'<div class="edition grand" style="border-inline-start-color:{e(r["couleur"])}">'
                        f'<strong>{e(r["nom"])}</strong> : {e(r["description"])}'
                        f'<div class="liens"><a href="{e(r["page"])}" style="background:{e(r["couleur"])};'
                        f'border-color:{e(r["couleur"])};color:#fff">Voir les analyses</a></div></div>')
    for i, d in enumerate(dates):
        liens = "".join(f'<a href="{nom}">{e(LANGUES.get(c, c))}</a>' for c, nom in sorted(par_date[d].items()))
        if i == 0:
            contenu += (f'<h2 class="rubrique" style="--c:#15508a">{e(t["derniere"])}</h2>'
                        f'<div class="edition grand"><strong>{e(d)}</strong><div class="liens">{liens}</div></div>')
            if len(dates) > 1:
                contenu += f'<h2 class="rubrique" style="--c:#6c757d">{e(t["precedentes"])}</h2>'
        else:
            contenu += f'<div class="edition"><strong>{e(d)}</strong><div class="liens">{liens}</div></div>'
    h = f'<h1 class="site">{e(t["site"])}</h1><p class="sous">{e(t["sous"])}</p>'
    (SORTIE / "index.html").write_text(page("fr", t["site"], h, "", contenu), encoding="utf-8")


def envoyer_telegram(articles, code, date):
    token, chat = os.getenv("TELEGRAM_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if token and chat:
        texte = f"📰 {TEXTES[code]['site']} · {date}\n\n" + "\n".join(f"• {a['titre']}" for a in articles)
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      json={"chat_id": chat, "text": texte[:4000]}, timeout=30)


def main():
    date = datetime.date.today().isoformat()
    elements = collecter()
    if not elements:
        print("Aucune actualité collectée.")
        return
    reussies = 0
    for n, code in enumerate(LANGUES):
        if n:
            time.sleep(PAUSE_ENTRE_LANGUES)
        try:
            articles = rediger(elements, code)
            if not articles:
                raise ValueError("aucun article exploitable")
            print("Publié :", publier(articles, elements, code, date))
            envoyer_telegram(articles, code, date)
            reussies += 1
        except Exception as erreur:  # une langue en échec ne bloque pas les autres
            print(f"Échec pour la langue {code} : {erreur}")
    construire_index()
    if not reussies:
        raise SystemExit("Aucun bulletin n'a pu être généré.")


if __name__ == "__main__":
    main()
