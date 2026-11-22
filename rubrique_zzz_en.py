"""
VERSION ANGLAISE DU SITE : traduction automatique (IA) des pages françaises, rangées dans docs/en/.
 - Le menu, les titres, les articles, les tableaux, les avertissements et les attributs (champs de recherche, descriptions) sont traduits.
 - Chaque phrase n'est traduite qu'une fois : les traductions sont mémorisées dans docs/data/i18n-en.json (coût très faible ensuite).
 - Les pages sont traitées par ordre de priorité (pages principales d'abord, puis les plus récentes), dans la limite d'un budget par exécution.
   Les pages restantes sont traduites aux exécutions suivantes ; en attendant, un lien vers une page pas encore traduite ouvre l'original français.
 - Les chiffres sont contrôlés : si une traduction modifie un nombre, elle est refaite, puis le texte français est conservé.
Ce fichier s'exécute en dernier (son nom commence par « rubrique_zzz »). Clé nécessaire : GEMINI_API_KEY (déjà en place).
"""
import re
import json
import html
import time
import bulletin
from bulletin import page

SORTIE = bulletin.SORTIE
BUDGET = 700      # nouvelles phrases traduites par exécution
LOT_CAR = 5000    # caractères maximum par appel à l'IA
PRIORITE = ["index.html", "programme.html", "archives.html", "macro.html", "ipo.html", "coin-de-lecture.html", "analyseur.html",
            "fiscalite.html", "management.html", "grh.html", "economie.html"]

# Traductions imposées (cohérence du menu et de la marque)
SEED = {
    "Le Bulletin Économique": "The Economic Bulletin", "Accueil": "Home", "Actualité du jour": "Today's news", "Archives": "Archives",
    "English": "Français", "Fiscalité": "Taxation", "Management": "Management", "GRH": "HRM", "Économie": "Economics",
    "Indicateurs": "Indicators", "Analyseur financier": "Financial analyzer", "Programme": "Schedule", "Coin de lecture": "Reading corner",
    "Opérations en bourse": "Stock market offerings", "Marchés": "Markets", "Banques centrales": "Central banks",
    "Économie mondiale": "World economy", "Entreprises": "Business", "Commerce et échanges": "Trade", "Autres actualités": "Other news",
    "À la une": "Top story", "Analyse": "Analysis", "Regard critique": "Critical view", "Pistes de solution": "Possible solutions",
    "À retenir": "Key takeaways",
    "L'essentiel de l'actualité économique, analysé et expliqué": "Economic news, analysed and explained",
}

SPLIT = re.compile(r"(<!--.*?-->|<script\b.*?</script>|<style\b.*?</style>|<[^>]+>)", re.S | re.I)
ATTRS = re.compile(r'(\b(?:placeholder|title|aria-label|alt)=")([^"]*)(")', re.I)
META = re.compile(r'<meta\b[^>]*(?:name="description"|property="og:(?:title|description|site_name)")[^>]*>', re.I)
LETTRES = re.compile(r"[A-Za-zÀ-ÿ]{2}")

PROMPT = """Translate the following French texts, taken from a French economics, finance and management website, into natural and precise English (professional register).
Rules:
- Keep numbers, dates' digits, currency codes, symbols, acronyms, company names, proper names and URLs unchanged.
- Keep line breaks (\\n) if present. Do not add or remove information. No commentary.
- Return ONLY a valid JSON object with the same ids as keys and the English translations as string values.

Texts (JSON):
@JSON@
"""


def transformer(src, f):
    """Applique f(texte_français) -> texte à chaque texte visible et à chaque attribut traduisible d'une page HTML."""
    morceaux = SPLIT.split(src)
    for i, p in enumerate(morceaux):
        if i % 2 == 0:
            if not p.strip():
                continue
            core = " ".join(html.unescape(p).split())
            if not LETTRES.search(core):
                continue
            lead = re.match(r"\s*", p).group(0)
            trail = re.search(r"\s*$", p).group(0)
            morceaux[i] = lead + html.escape(f(core), quote=False) + trail
        else:
            low = p.lower()
            if low.startswith("<script") or low.startswith("<style") or p.startswith("<!--"):
                continue

            def sub(m):
                core = " ".join(html.unescape(m.group(2)).split())
                if not LETTRES.search(core):
                    return m.group(0)
                return m.group(1) + html.escape(f(core), quote=True) + m.group(3)

            tag = ATTRS.sub(sub, p)
            if META.match(tag):
                tag = re.sub(r'(content=")([^"]*)(")', sub, tag, flags=re.I)
            morceaux[i] = tag
    return "".join(morceaux)


def cles_de(src):
    cles = []
    transformer(src, lambda c: (cles.append(c), c)[1])
    return list(dict.fromkeys(cles))


def chiffres(t):
    return sorted(re.findall(r"\d+", t))


def charger_cache():
    try:
        cache = json.loads((SORTIE / "data" / "i18n-en.json").read_text(encoding="utf-8"))
    except Exception:
        cache = {}
    cache.update({k: v for k, v in SEED.items()})
    return cache


def sauver_cache(cache):
    (SORTIE / "data").mkdir(parents=True, exist_ok=True)
    (SORTIE / "data" / "i18n-en.json").write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")


def appeler(lot):
    res = bulletin.appeler_gemini_json(PROMPT.replace("@JSON@", json.dumps(lot, ensure_ascii=False)), minimum_mots=0)
    return res if isinstance(res, dict) else {}


def traduire(cles, cache):
    """Traduit les phrases absentes du cache, par lots ; contrôle les chiffres."""
    lots, cur, n = [], {}, 0
    for c in cles:
        if cur and n + len(c) > LOT_CAR:
            lots.append(cur)
            cur, n = {}, 0
        cur[str(len(cur) + 1)] = c
        n += len(c)
    if cur:
        lots.append(cur)
    suspectes = []
    for lot in lots:
        try:
            res = appeler(lot)
        except Exception as erreur:
            print(f"  Lot de traduction ignoré : {erreur}")
            continue
        for i, fr in lot.items():
            en = res.get(i)
            if not isinstance(en, str) or not en.strip():
                continue
            if chiffres(fr) != chiffres(en):
                suspectes.append(fr)
            else:
                cache[fr] = en.strip()
        time.sleep(5)
    for fr in suspectes[:12]:  # seconde chance, une par une
        try:
            en = appeler({"1": fr}).get("1")
        except Exception:
            en = None
        if isinstance(en, str) and chiffres(fr) == chiffres(en):
            cache[fr] = en.strip()
        else:
            cache[fr] = fr  # on garde le français plutôt qu'un chiffre modifié
            print(f"  Chiffres différents, texte français conservé : {fr[:60]}")
        time.sleep(3)


def finaliser(h):
    h = h.replace('<html lang="fr"', '<html lang="en"', 1)
    return h.replace('<footer><div class="wrap">',
                     '<footer><div class="wrap"><p>Automatic English translation (AI) of the French original; the French version prevails.</p>', 1)


def page_analyseur():
    main = ('<span class="tag" style="--c:#364fc7">Outil en ligne</span>'
            '<h2 style="font-size:1.7rem;line-height:1.3;margin:.5rem 0">Analyseur financier d\'entreprise</h2>'
            '<p class="chapeau">L\'analyseur financier est disponible en français uniquement pour le moment.</p>'
            '<p>Il calcule les soldes de gestion, l\'équilibre financier, les ratios et une valorisation indicative à partir de vos états de synthèse.</p>'
            '<p><a href="../analyseur.html" style="display:inline-block;background:#15508a;color:#fff;padding:10px 18px;border-radius:10px;text-decoration:none">'
            'Ouvrir l\'analyseur (version française)</a></p>')
    entete = '<h1 class="site">Analyseur financier</h1><p class="sous">Diagnostic et valorisation de votre entreprise, en ligne et gratuit</p>'
    return page("fr", "Analyseur financier · Le Bulletin Économique", entete, "", main)


def main():
    if not getattr(bulletin, "EN_ACTIVE", False):
        print("Version anglaise désactivée.")
        return
    dest = SORTIE / "en"
    dest.mkdir(parents=True, exist_ok=True)
    pages = {f.name: f.read_text(encoding="utf-8") for f in SORTIE.glob("*.html")}
    pages["analyseur.html"] = page_analyseur()
    ordre = [n for n in PRIORITE if n in pages] + sorted((n for n in pages if n not in PRIORITE),
                                                         key=lambda n: (SORTIE / n).stat().st_mtime if (SORTIE / n).exists() else 0, reverse=True)
    cache = charger_cache()
    budget, ecrites, reportees = BUDGET, 0, 0
    for nom in ordre:
        src = pages[nom]
        cles = cles_de(src)
        manquantes = [c for c in cles if c not in cache]
        if len(manquantes) > budget:
            reportees += 1
            continue
        if manquantes:
            traduire(manquantes, cache)
            budget -= len(manquantes)
            sauver_cache(cache)
        if any(c not in cache for c in cles):
            reportees += 1
            continue
        (dest / nom).write_text(finaliser(transformer(src, lambda c: cache[c])), encoding="utf-8")
        ecrites += 1
    sauver_cache(cache)
    print(f"Version anglaise : {ecrites} page(s) écrite(s), {reportees} reportée(s) à la prochaine exécution, {len(cache)} phrases en mémoire")


if __name__ == "__main__":
    main()
