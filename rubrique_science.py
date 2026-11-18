"""
Rubriques SCIENTIFIQUES : Management, GRH, Économie (macro et micro).
Chaque jour de semaine, un thème : synthèse de la recherche récente (articles trouvés via OpenAlex),
avec constats, nuances, implications pratiques et solutions. Mardi = management, mercredi = GRH,
jeudi = macroéconomie, vendredi = microéconomie.
Variables : GEMINI_API_KEY, OPENALEX_API_KEY (clé gratuite) ; FORCER=true pour tout lancer ; THEME=... pour un seul.
"""
import os
import json
import time
import datetime
import requests
import bulletin
from bulletin import e, page, secret

SORTIE = bulletin.SORTIE

EXTRA_CSS = """
.bloc{background:var(--carte);border:1px solid var(--bord);border-radius:14px;padding:18px 20px;margin-bottom:16px}
.bloc h3{margin:.1rem 0 .5rem;font-size:1.1rem}
.solutions{counter-reset:s;list-style:none;padding:0;margin:.4rem 0}
.solutions li{counter-increment:s;position:relative;padding:10px 12px;padding-inline-start:46px;margin:8px 0;border:1px solid var(--bord);border-radius:12px;line-height:1.55}
.solutions li::before{content:counter(s);position:absolute;inset-inline-start:12px;top:9px;width:24px;height:24px;border-radius:50%;
background:var(--c);color:#fff;font-size:.82rem;font-weight:700;display:flex;align-items:center;justify-content:center}
.refs{font-size:.88rem;padding-inline-start:1.3rem}
.refs li{margin:.5rem 0}
.note{font-size:.82rem;color:var(--doux)}
"""
bulletin.CSS = bulletin.CSS + EXTRA_CSS

THEMES = {
    "management": {
        "rubrique": "management", "nom": "Management", "niveau": "", "couleur": "#e8590c", "jour": 1,
        "description": "synthèses de la recherche récente sur les comportements managériaux, avec des solutions concrètes",
        "sujets": [
            "psychological safety in teams|La sécurité psychologique dans les équipes",
            "leadership style and employee performance|Styles de leadership et performance des salariés",
            "servant leadership|Le leadership serviteur",
            "managerial decision making under uncertainty|La décision managériale en situation d'incertitude",
            "organizational culture and change management|Culture d'entreprise et conduite du changement",
            "trust and delegation managers|Confiance et délégation chez les managers",
            "conflict management in teams|La gestion des conflits dans les équipes",
            "ethical leadership|Le leadership éthique",
            "managing remote and hybrid teams|Manager des équipes à distance et hybrides",
            "digital transformation and management|Transformation digitale et management",
            "innovation management small firms|Le management de l'innovation dans les PME",
            "managerial overconfidence|La surconfiance des dirigeants",
        ],
    },
    "grh": {
        "rubrique": "grh", "nom": "GRH", "niveau": "", "couleur": "#0b7285", "jour": 2,
        "description": "les préoccupations des entreprises en ressources humaines, éclairées par la recherche, avec des solutions",
        "sujets": [
            "employee turnover and retention|Rotation du personnel et fidélisation",
            "employee engagement|L'engagement des salariés",
            "artificial intelligence in recruitment|L'intelligence artificielle dans le recrutement",
            "performance appraisal fairness|L'équité des évaluations de performance",
            "pay transparency and compensation|Transparence et politique de rémunération",
            "training and development outcomes|Formation et développement des compétences",
            "burnout and work-life balance|Épuisement professionnel et équilibre vie privée-vie professionnelle",
            "diversity and inclusion in organizations|Diversité et inclusion en entreprise",
            "hybrid work human resource policy|Télétravail et politiques RH",
            "people analytics human resources|Le pilotage RH par les données",
            "employer branding and talent attraction|Marque employeur et attractivité des talents",
            "workplace well-being|Le bien-être au travail",
        ],
    },
    "economie_macro": {
        "rubrique": "economie", "nom": "Économie", "niveau": "macroéconomie", "couleur": "#2f9e44", "jour": 3,
        "description": "analyses macro et microéconomiques tirées d'articles scientifiques récents",
        "sujets": [
            "inflation expectations and monetary policy|Anticipations d'inflation et politique monétaire",
            "public debt and fiscal sustainability|Dette publique et soutenabilité budgétaire",
            "exchange rates in emerging markets|Les taux de change dans les pays émergents",
            "institutions and economic growth|Institutions et croissance économique",
            "tax policy and economic growth|Politique fiscale et croissance",
            "financial inclusion in developing countries|L'inclusion financière dans les pays en développement",
            "tariffs and trade effects|Droits de douane et effets sur le commerce",
            "foreign direct investment in emerging economies|Les investissements directs étrangers dans les pays émergents",
            "energy transition macroeconomic effects|Transition énergétique et effets macroéconomiques",
            "unemployment and labor market policy|Chômage et politiques du marché du travail",
        ],
    },
    "economie_micro": {
        "rubrique": "economie", "nom": "Économie", "niveau": "microéconomie", "couleur": "#2f9e44", "jour": 4,
        "description": "analyses macro et microéconomiques tirées d'articles scientifiques récents",
        "sujets": [
            "firm productivity|La productivité des entreprises",
            "pricing and consumer behavior|Prix et comportement des consommateurs",
            "market competition and regulation|Concurrence et régulation des marchés",
            "entrepreneurship and SME financing|Entrepreneuriat et financement des PME",
            "behavioral economics and decision making|Économie comportementale et décision",
            "wages and labor supply|Salaires et offre de travail",
            "supply chain resilience firms|La résilience des chaînes d'approvisionnement",
            "corporate governance and firm performance|Gouvernance d'entreprise et performance",
            "R&D and innovation in firms|Recherche-développement et innovation dans les entreprises",
            "microfinance and household welfare|Microfinance et bien-être des ménages",
        ],
    },
}

PROMPT = """Tu es un chercheur-rédacteur qui écrit pour des managers, des étudiants et des décideurs. Écris en français clair, avec un ton pédagogique et professionnel.
L'article doit être DÉTAILLÉ et utile : le lecteur doit apprendre des choses concrètes et pouvoir agir, pas lire un simple résumé.
Sujet du jour : « @SUJET@ » (rubrique : @NOM@ @NIVEAU@).

ARTICLES SCIENTIFIQUES (résumés fournis) :
@TRAVAUX@

Règles strictes :
- Pour la partie « etudes » : utilise UNIQUEMENT ce que disent les résumés ci-dessus ; n'invente aucun résultat, chiffre, auteur ou conclusion. Mentionne les limites quand elles apparaissent.
- Pour « introduction », « eclairage » et « mise_en_pratique » : tu peux t'appuyer sur des connaissances générales solides et reconnues (définitions, mécanismes, bonnes pratiques). N'invente aucun chiffre ni statistique, et ne présente jamais ces éléments comme des résultats des études citées.
- Réécris avec tes propres mots, explique les termes techniques, donne des exemples génériques (sans nommer de vraies entreprises ni inventer de cas réels).
- Réponds UNIQUEMENT avec un JSON valide de cette forme, en respectant les longueurs :
{"titre": "titre clair et attractif",
 "chapeau": "3 phrases",
 "introduction": "150 à 200 mots : pourquoi ce sujet compte, définition simple des notions clés",
 "eclairage": "150 à 200 mots : mécanismes et concepts à connaître pour comprendre le sujet",
 "etudes": [{"ref": 1, "titre_court": "intitulé court de l'étude", "apport": "70 à 100 mots : question étudiée, méthode si elle est connue, résultat principal, limites"}],
 "synthese": "150 à 200 mots : points de convergence, divergences, ce qui reste incertain",
 "mise_en_pratique": [{"etape": "titre court", "detail": "40 à 70 mots : action concrète, comment la mener, pièges à éviter"}],
 "indicateurs": ["4 à 5 indicateurs à suivre pour mesurer les progrès"],
 "erreurs_a_eviter": ["4 erreurs fréquentes, une phrase chacune"],
 "pour_reflechir": ["3 questions que le lecteur peut se poser dans son organisation"],
 "conclusion": "3 à 4 phrases"}
- « etudes » contient une entrée par article fourni ; « mise_en_pratique » contient 5 à 6 étapes.
"""


# --- 1. Recherche des articles (OpenAlex) -------------------------------------
def reconstruire(index):
    """OpenAlex fournit le résumé sous forme d'index inversé : on remet les mots dans l'ordre."""
    if not index:
        return ""
    mots = {}
    for mot, positions in index.items():
        for p in positions:
            mots[p] = mot
    return " ".join(mots[i] for i in sorted(mots))


def chercher(requete):
    cle = secret("OPENALEX_API_KEY")
    if not cle:
        raise SystemExit("Clé OPENALEX_API_KEY absente : créez-la (gratuite) sur openalex.org puis ajoutez-la dans les secrets GitHub.")
    depuis = f"{datetime.date.today().year - 2}-01-01"
    r = requests.get("https://api.openalex.org/works", params={
        "search": requete, "per_page": 12, "api_key": cle,
        "filter": f"from_publication_date:{depuis},has_abstract:true,type:article",
        "select": "id,doi,display_name,publication_year,authorships,primary_location,abstract_inverted_index",
    }, timeout=60)
    r.raise_for_status()
    travaux = []
    for w in r.json().get("results", []):
        resume = reconstruire(w.get("abstract_inverted_index"))
        if len(resume) < 250:
            continue
        auteurs = [a["author"]["display_name"] for a in w.get("authorships", [])[:3] if a.get("author")]
        if len(w.get("authorships", [])) > 3:
            auteurs.append("et al.")
        revue = ((w.get("primary_location") or {}).get("source") or {}).get("display_name") or ""
        travaux.append({"titre": w.get("display_name") or "", "annee": w.get("publication_year"),
                        "auteurs": ", ".join(auteurs), "revue": revue,
                        "lien": w.get("doi") or w.get("id") or "", "resume": resume[:2200]})
    return travaux[:6]


# --- 2. Mise en page ------------------------------------------------------------
def entete(theme, sujet_fr):
    titre = theme["nom"] + (f" · {theme['niveau']}" if theme["niveau"] else "")
    return (f'<h1 class="site">{e(titre)}</h1><p class="sous">Sujet du jour : {e(sujet_fr)}</p>'
            f'<div class="langues"><a href="index.html">Accueil</a><a href="{theme["rubrique"]}.html">Toutes les analyses</a></div>')


def liste_ul(items):
    items = [x for x in items if isinstance(x, str) and x.strip()]
    return "<ul>" + "".join(f"<li>{e(x)}</li>" for x in items) + "</ul>" if items else ""


def page_article(theme, sujet_fr, travaux, art, date):
    c = theme["couleur"]
    etiquette = theme["nom"] + (f" · {theme['niveau']}" if theme["niveau"] else "")
    refs = "".join(
        f'<li>[{i}] {e(w["titre"])}. {e(w["auteurs"])} ({e(w["annee"])}). <i>{e(w["revue"])}</i>. '
        + (f'<a href="{e(w["lien"])}" target="_blank" rel="noopener">Lire l\'article</a>' if w["lien"].startswith("http") else "")
        + "</li>" for i, w in enumerate(travaux, 1))
    etudes = "".join(
        f'<div class="sec"><b>[{e(x.get("ref", ""))}] {e(x.get("titre_court", ""))}</b><p>{e(x.get("apport", ""))}</p></div>'
        for x in art.get("etudes", []) if isinstance(x, dict))
    etapes = "".join(
        f'<li><b>{e(x.get("etape", ""))}</b><br>{e(x.get("detail", ""))}</li>'
        for x in art.get("mise_en_pratique", []) if isinstance(x, dict))
    main = (
        f'<span class="tag" style="--c:{c}">{e(etiquette)} · Recherche</span>'
        f'<h2 style="font-size:1.7rem;line-height:1.3;margin:.5rem 0">{e(art["titre"])}</h2>'
        f'<p class="chapeau">{e(art.get("chapeau", ""))}</p>'
        f'<div class="bloc"><h3>Pourquoi ce sujet compte</h3><p>{e(art.get("introduction", ""))}</p></div>'
        f'<div class="bloc"><h3>À savoir pour bien comprendre</h3><p>{e(art.get("eclairage", ""))}</p>'
        '<p class="note">Éclairage pédagogique fondé sur des connaissances générales, distinct des résultats des études ci-dessous.</p></div>'
        f'<div class="bloc"><h3>Ce que disent les études</h3>{etudes}</div>'
        f'<div class="bloc"><h3>Synthèse : convergences, divergences et incertitudes</h3><p>{e(art.get("synthese", ""))}</p></div>'
        f'<div class="bloc" style="--c:{c}"><h3>Mise en pratique : par où commencer</h3><ol class="solutions">{etapes}</ol></div>'
        f'<div class="bloc"><h3>Indicateurs à suivre</h3>{liste_ul(art.get("indicateurs", []))}</div>'
        f'<div class="bloc"><h3>Erreurs à éviter</h3>{liste_ul(art.get("erreurs_a_eviter", []))}</div>'
        f'<div class="bloc"><h3>Pour réfléchir dans votre organisation</h3>{liste_ul(art.get("pour_reflechir", []))}</div>'
        f'<div class="bloc"><h3>En conclusion</h3><p>{e(art.get("conclusion", ""))}</p></div>'
        f'<div class="bloc"><h3>Références (articles scientifiques analysés)</h3><ol class="refs" style="list-style:none;padding:0">{refs}</ol></div>'
        f'<p class="note">Article généré par IA à partir des résumés des études citées et de connaissances générales ; consultez les articles originaux avant toute décision. '
        f'Ne constitue pas un conseil professionnel. Édition du {e(date)}.</p>'
    )
    return page("fr", f"{etiquette} · {art['titre']}", entete(theme, sujet_fr), "", main, description=art.get("chapeau", ""))


def maj_liste(theme, date, fichier, art, sujet_fr):
    cle = theme["rubrique"]
    chemin = SORTIE / f"{cle}-articles.json"
    articles = json.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else []
    articles = [a for a in articles if a["fichier"] != fichier]
    articles.append({"fichier": fichier, "date": date, "sujet": sujet_fr, "titre": art["titre"], "chapeau": art.get("chapeau", "")})
    articles.sort(key=lambda a: a["date"], reverse=True)
    chemin.write_text(json.dumps(articles, ensure_ascii=False, indent=1), encoding="utf-8")
    cartes = "".join(
        f'<a class="carte lien" style="margin-bottom:12px" href="{e(a["fichier"])}"><span class="tag" style="--c:{theme["couleur"]}">{e(a["sujet"])}</span> '
        f'<span class="note">{e(a["date"])}</span><h3>{e(a["titre"])}</h3><p>{e(a["chapeau"])}</p></a>' for a in articles)
    main = f'<h2 class="rubrique" style="--c:{theme["couleur"]}">Toutes les analyses : {e(theme["nom"])}</h2>' + cartes
    entete_liste = f'<h1 class="site">{e(theme["nom"])}</h1><p class="sous">{e(theme["description"])}</p>'
    (SORTIE / f"{cle}.html").write_text(page("fr", f'{theme["nom"]} · Le Bulletin Économique', entete_liste, "", main), encoding="utf-8")


# --- 3. Programme principal -----------------------------------------------------
def themes_du_jour():
    force = os.getenv("THEME", "")
    if force in THEMES:
        return [force]
    if os.getenv("FORCER") == "true":
        return list(THEMES)
    jour = datetime.date.today().weekday()
    return [k for k, t in THEMES.items() if t["jour"] == jour]


def traiter(cle, date):
    theme = THEMES[cle]
    sujets = theme["sujets"]
    requete, sujet_fr = sujets[(datetime.date.today().toordinal() // 7) % len(sujets)].split("|")
    travaux = chercher(requete)
    if len(travaux) < 2:
        raise ValueError(f"trop peu d'articles trouvés pour « {requete} »")
    texte = "\n\n".join(f"[{i}] {w['titre']} ({w['annee']}) : {w['resume']}" for i, w in enumerate(travaux, 1))
    prompt = (PROMPT.replace("@SUJET@", sujet_fr).replace("@NOM@", theme["nom"])
              .replace("@NIVEAU@", theme["niveau"]).replace("@TRAVAUX@", texte))
    art = bulletin.appeler_gemini_json(prompt, minimum_mots=900)
    if not art.get("titre") or not art.get("introduction") or not art.get("etudes") or not art.get("mise_en_pratique"):
        raise ValueError("réponse de l'IA incomplète")
    print(f"  {theme['nom']} : article de {bulletin.compter_mots(art)} mots")
    SORTIE.mkdir(exist_ok=True)
    fichier = f"{theme['rubrique']}-{date}-{cle}.html"
    (SORTIE / fichier).write_text(page_article(theme, sujet_fr, travaux, art, date), encoding="utf-8")
    maj_liste(theme, date, fichier, art, sujet_fr)
    bulletin.enregistrer_rubrique(theme["rubrique"], theme["nom"], theme["description"], f"{theme['rubrique']}.html", theme["couleur"])
    print("Publié :", fichier)


def main():
    themes = themes_du_jour()
    if not themes:
        print("Rubriques scientifiques : rien à publier aujourd'hui (mardi à vendredi).")
        return
    date = datetime.date.today().isoformat()
    reussis = 0
    for n, cle in enumerate(themes):
        if n:
            time.sleep(20)  # respecte le quota gratuit
        try:
            traiter(cle, date)
            reussis += 1
        except Exception as erreur:
            print(f"Échec du thème {cle} : {erreur}")
    bulletin.construire_index()
    if not reussis:
        raise SystemExit("Aucune synthèse n'a pu être générée.")


if __name__ == "__main__":
    main()
