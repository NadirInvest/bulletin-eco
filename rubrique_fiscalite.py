"""
Rubrique FISCALITÉ : une analyse par semaine d'un pays (le lundi), à partir de données officielles
(Banque mondiale, séries issues du FMI) : lecture historique, points forts / faibles, comparaison.
Les chiffres sont calculés par le programme ; l'IA ne fait que commenter.
Fichier rubrique_*.py : lancé automatiquement par le workflow.
Variables : GEMINI_API_KEY (obligatoire) ; PAYS (optionnel, ex. MAR) ; FORCER=true pour ignorer le lundi.
"""
import os
import re
import json
import html
import datetime
import requests
import bulletin
from bulletin import e, page

SORTIE = bulletin.SORTIE
MODELE = bulletin.MODELE

PAYS = {
    "MAR": "Maroc", "FRA": "France", "DEU": "Allemagne", "ESP": "Espagne", "GBR": "Royaume-Uni",
    "USA": "États-Unis", "JPN": "Japon", "BRA": "Brésil", "TUR": "Turquie", "EGY": "Égypte",
    "SAU": "Arabie saoudite", "CHN": "Chine", "IND": "Inde", "ZAF": "Afrique du Sud",
    "TUN": "Tunisie", "SEN": "Sénégal", "CAN": "Canada", "ITA": "Italie",
    "IDN": "Indonésie", "MYS": "Malaisie", "NGA": "Nigeria", "CIV": "Côte d'Ivoire", "MEX": "Mexique",
    "KOR": "Corée du Sud", "AUS": "Australie", "NZL": "Nouvelle-Zélande", "CHE": "Suisse", "RUS": "Russie",
    "PRT": "Portugal", "NOR": "Norvège", "SWE": "Suède", "DNK": "Danemark", "FIN": "Finlande",
    "ARG": "Argentine", "URY": "Uruguay", "PHL": "Philippines", "THA": "Thaïlande",
}
REFERENCE = ["MAR", "FRA", "DEU", "USA"]  # pays de comparaison (les 3 premiers différents du pays étudié)
INDICATEURS = {
    "GC.TAX.TOTL.GD.ZS": "Recettes fiscales (% du PIB)",
    "GC.TAX.YPKG.RV.ZS": "Impôts sur revenus, bénéfices et plus-values (% des recettes)",
    "GC.TAX.GSRV.RV.ZS": "Impôts sur biens et services (% des recettes)",
    "GC.TAX.INTT.RV.ZS": "Droits sur le commerce international (% des recettes)",
}
PRINCIPAL = "GC.TAX.TOTL.GD.ZS"
COULEURS = ["#0d6efd", "#e8590c", "#2f9e44", "#7a3cff"]

EXTRA_CSS = """
.kpis{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:12px;margin:8px 0 22px}
.kpi{background:var(--carte);border:1px solid var(--bord);border-radius:14px;padding:14px 16px}
.kpi b{display:block;font-size:1.7rem;line-height:1.25}
.kpi span{font-size:.82rem;color:var(--doux)}
.bloc{background:var(--carte);border:1px solid var(--bord);border-radius:14px;padding:18px 20px;margin-bottom:16px}
.bloc h3{margin:.1rem 0 .5rem;font-size:1.1rem}
.deux{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px;margin-bottom:16px}
.deux .bloc{margin-bottom:0}
.fort{border-top:5px solid #2f9e44}.faible{border-top:5px solid #e8590c}
.bloc ul{margin:.3rem 0;padding-inline-start:1.2rem}
.scroll{overflow-x:auto}
table.comp{width:100%;border-collapse:collapse;font-size:.9rem}
table.comp th,table.comp td{padding:8px 10px;border-bottom:1px solid var(--bord);text-align:start}
.legende{display:flex;gap:14px;flex-wrap:wrap;font-size:.85rem;margin-top:6px}
.legende i{display:inline-block;width:12px;height:12px;border-radius:3px;margin-inline-end:6px}
.note{font-size:.82rem;color:var(--doux)}
"""
bulletin.CSS = bulletin.CSS + EXTRA_CSS


# --- 1. Données --------------------------------------------------------------
def serie(iso, indicateur):
    r = requests.get(f"https://api.worldbank.org/v2/country/{iso}/indicator/{indicateur}",
                     params={"format": "json", "per_page": 80, "date": "1990:2025"}, timeout=60)
    r.raise_for_status()
    donnees = r.json()
    if not isinstance(donnees, list) or len(donnees) < 2 or not donnees[1]:
        return {}
    return {int(d["date"]): float(d["value"]) for d in donnees[1] if d.get("value") is not None}


def charger(iso):
    return {ind: serie(iso, ind) for ind in INDICATEURS}


def dernier(s):
    if not s:
        return None
    a = max(s)
    return a, s[a]


def fmt(v):
    return f"{v:.1f}".replace(".", ",")


def resume_serie(s):
    if not s:
        return "données non disponibles"
    annees = sorted(s)
    amin = min(s, key=s.get)
    amax = max(s, key=s.get)
    sortie = f"première valeur {annees[0]} = {fmt(s[annees[0]])} ; dernière valeur {annees[-1]} = {fmt(s[annees[-1]])} ; "
    sortie += f"minimum {fmt(s[amin])} ({amin}) ; maximum {fmt(s[amax])} ({amax}) ; "
    sortie += "série : " + ", ".join(f"{a}:{fmt(s[a])}" for a in annees)
    return sortie


# --- 2. Rédaction par l'IA ---------------------------------------------------
PROMPT = """Tu es analyste en fiscalité publique et rédacteur d'un site d'information économique. Écris en français clair, avec un ton pédagogique et professionnel.
L'article doit être DÉTAILLÉ et utile à un lecteur qui veut comprendre la fiscalité de ce pays : pas un simple résumé de chiffres.
Sujet : analyse de la structure fiscale de @PAYS@, comparée à @PAIRS@.

DONNÉES OFFICIELLES (Banque mondiale, séries issues du FMI). Ce sont les SEULES données chiffrées que tu peux utiliser :
@FAITS@

Règles strictes :
- N'invente aucun chiffre, taux, loi, réforme, date ou événement propre au pays qui soit absent des données ci-dessus.
- Tu peux expliquer en termes généraux et reconnus ce que sont les grandes familles d'impôts (revenus et bénéfices, biens et services, commerce international) et ce que signifie un niveau de pression fiscale, sans attribuer au pays des règles précises que les données ne montrent pas.
- Si une donnée manque, écris « donnée non disponible » plutôt que de deviner.
- Les points faibles et les pistes sont formulés comme des hypothèses à examiner, jamais comme des certitudes.
- Réponds UNIQUEMENT avec un JSON valide de cette forme, en respectant les longueurs :
{"titre": "titre clair et attractif",
 "chapeau": "3 phrases",
 "introduction": "120 à 160 mots : pourquoi la structure fiscale compte et comment lire les indicateurs",
 "chiffres_cles": "150 à 200 mots : explication de chaque indicateur avec les valeurs fournies",
 "lecture_historique": "180 à 250 mots : évolution dans le temps, phases, ruptures visibles dans les séries",
 "structure_fiscale": "180 à 250 mots : répartition des recettes entre les familles d'impôts, expliquée simplement",
 "points_forts": ["3 à 4 points, chacun en 2 phrases avec explication"],
 "points_faibles": ["3 à 4 points, chacun en 2 phrases, formulés comme pistes à examiner"],
 "comparaison": "180 à 250 mots : comparaison détaillée avec les autres pays",
 "pistes_de_reforme": ["3 à 4 pistes générales à examiner, avec la logique économique de chacune"],
 "limites_des_donnees": "70 à 100 mots : ce que ces indicateurs ne montrent pas (taux précis, impôts locaux, économie informelle...)",
 "questions_a_approfondir": ["4 questions pour aller plus loin, à étudier dans les textes nationaux"],
 "conclusion": "3 à 4 phrases"}
"""


def rediger_article(pays, pairs, faits):
    prompt = PROMPT.replace("@PAYS@", pays).replace("@PAIRS@", pairs).replace("@FAITS@", faits)
    art = bulletin.appeler_gemini_json(prompt, minimum_mots=900)
    print(f"  Fiscalité : article de {bulletin.compter_mots(art)} mots")
    return art


def construire_faits(iso, donnees, pairs, donnees_pairs):
    lignes = [f"== {PAYS[iso]} (pays étudié) =="]
    for ind, nom in INDICATEURS.items():
        lignes.append(f"- {nom} : {resume_serie(donnees[ind])}")
    lignes.append("== Pays de comparaison : dernières valeurs disponibles ==")
    for p in pairs:
        for ind, nom in INDICATEURS.items():
            d = dernier(donnees_pairs[p][ind])
            lignes.append(f"- {PAYS[p]} : {nom} = " + (f"{fmt(d[1])} ({d[0]})" if d else "non disponible"))
    return "\n".join(lignes)


# --- 3. Mise en page ---------------------------------------------------------
def graphique(series, titre):
    """Courbes SVG (series : {nom: {annee: valeur}})."""
    pts = [(a, v) for s in series.values() for a, v in s.items()]
    if not pts:
        return ""
    a0, a1 = min(a for a, _ in pts), max(a for a, _ in pts)
    vmax = (max(v for _, v in pts) * 1.1) or 1
    W, H, ml, mr, mt, mb = 640, 280, 44, 14, 12, 30

    def X(a):
        return ml + (a - a0) / ((a1 - a0) or 1) * (W - ml - mr)

    def Y(v):
        return mt + (1 - v / vmax) * (H - mt - mb)

    p = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{e(titre)}" style="width:100%;height:auto;direction:ltr">']
    for i in range(5):
        v = vmax * i / 4
        p.append(f'<line x1="{ml}" x2="{W - mr}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" stroke="currentColor" opacity=".13"/>')
        p.append(f'<text x="{ml - 6}" y="{Y(v) + 4:.1f}" font-size="11" text-anchor="end" fill="currentColor" opacity=".65">{v:.0f}</text>')
    pas = max(1, round((a1 - a0) / 5))
    for a in range(a0, a1 + 1, pas):
        p.append(f'<text x="{X(a):.1f}" y="{H - 8}" font-size="11" text-anchor="middle" fill="currentColor" opacity=".65">{a}</text>')
    for i, (nom, s) in enumerate(series.items()):
        if not s:
            continue
        c = COULEURS[i % len(COULEURS)]
        coords = " ".join(f"{X(a):.1f},{Y(v):.1f}" for a, v in sorted(s.items()))
        p.append(f'<polyline fill="none" stroke="{c}" stroke-width="{3.2 if i == 0 else 2}" points="{coords}" stroke-linejoin="round"/>')
    p.append("</svg>")
    legende = "".join(f'<span><i style="background:{COULEURS[i % len(COULEURS)]}"></i>{e(n)}</span>' for i, n in enumerate(series))
    return "".join(p) + f'<div class="legende">{legende}</div>'


def liste(items):
    return "<ul>" + "".join(f"<li>{e(x)}</li>" for x in items) + "</ul>"


def page_article(iso, donnees, pairs, donnees_pairs, art, date):
    pays = PAYS[iso]
    kpis = ""
    for ind, nom in INDICATEURS.items():
        d = dernier(donnees[ind])
        valeur = f"{fmt(d[1])} %" if d else "n.d."
        annee = f" · {d[0]}" if d else ""
        kpis += f'<div class="kpi"><b>{valeur}</b><span>{e(nom)}{annee}</span></div>'
    series = {pays: donnees[PRINCIPAL]}
    for p in pairs:
        series[PAYS[p]] = donnees_pairs[p][PRINCIPAL]
    entetes = "".join(f"<th>{e(PAYS[c])}</th>" for c in [iso] + pairs)
    lignes = ""
    for ind, nom in INDICATEURS.items():
        cellules = ""
        for c in [iso] + pairs:
            d = dernier((donnees if c == iso else donnees_pairs[c])[ind])
            cellules += f"<td>{fmt(d[1]) + ' (' + str(d[0]) + ')' if d else 'n.d.'}</td>"
        lignes += f"<tr><td>{e(nom)}</td>{cellules}</tr>"
    def liste_riche(items):
        items = [x for x in items if isinstance(x, str) and x.strip()]
        return "<ul>" + "".join(f"<li>{e(x)}</li>" for x in items) + "</ul>" if items else ""

    main = (
        f'<span class="tag" style="--c:#7a3cff">Fiscalité · {e(pays)}</span>'
        f'<h2 style="font-size:1.7rem;line-height:1.3;margin:.5rem 0">{e(art["titre"])}</h2>'
        f'<p class="chapeau">{e(art.get("chapeau", ""))}</p>'
        f'<div class="kpis">{kpis}</div>'
        f'<div class="bloc"><h3>Pourquoi la structure fiscale compte</h3><p>{e(art.get("introduction", ""))}</p></div>'
        f'<div class="bloc"><h3>Les chiffres clés expliqués</h3><p>{e(art.get("chiffres_cles", ""))}</p></div>'
        f'<div class="bloc"><h3>Recettes fiscales (% du PIB) : {e(pays)} et pays de comparaison</h3>{graphique(series, "Recettes fiscales")}</div>'
        f'<div class="bloc"><h3>Lecture historique</h3><p>{e(art.get("lecture_historique", ""))}</p></div>'
        f'<div class="bloc"><h3>Structure des recettes fiscales</h3><p>{e(art.get("structure_fiscale", ""))}</p></div>'
        f'<div class="deux"><div class="bloc fort"><h3>Points forts</h3>{liste_riche(art.get("points_forts", []))}</div>'
        f'<div class="bloc faible"><h3>Points faibles et pistes à examiner</h3>{liste_riche(art.get("points_faibles", []))}</div></div>'
        f'<div class="bloc"><h3>Comparaison internationale</h3><p>{e(art.get("comparaison", ""))}</p>'
        f'<div class="scroll"><table class="comp"><tr><th></th>{entetes}</tr>{lignes}</table></div></div>'
        f'<div class="bloc"><h3>Pistes de réforme à examiner</h3>{liste_riche(art.get("pistes_de_reforme", []))}</div>'
        f'<div class="bloc"><h3>Limites de ces données</h3><p>{e(art.get("limites_des_donnees", ""))}</p></div>'
        f'<div class="bloc"><h3>Pour aller plus loin</h3>{liste_riche(art.get("questions_a_approfondir", []))}</div>'
        f'<div class="bloc"><h3>En conclusion</h3><p>{e(art.get("conclusion", ""))}</p></div>'
        f'<p class="note">Sources : Banque mondiale, Indicateurs du développement dans le monde (séries issues du FMI) : '
        f'<a href="https://data.worldbank.org/" target="_blank" rel="noopener">data.worldbank.org</a>. '
        f'Analyse générée par IA à partir de ces données ; elle ne remplace pas l\'étude de la législation nationale. '
        f'Édition du {e(date)}.</p>'
    )
    return page("fr", f"Fiscalité · {pays} · {date}", entete(f"Analyse fiscale : {pays}"), "", main)


def entete(sous):
    return ('<h1 class="site">Fiscalité</h1>' f'<p class="sous">{e(sous)}</p>'
            '<div class="langues"><a href="index.html">Accueil</a><a href="fiscalite.html">Toutes les analyses</a></div>')


def maj_liste(date, iso, art):
    chemin = SORTIE / "fiscalite-articles.json"
    articles = json.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else []
    articles = [a for a in articles if a["fichier"] != f"fiscalite-{date}-{iso}.html"]
    articles.append({"fichier": f"fiscalite-{date}-{iso}.html", "date": date, "pays": PAYS[iso],
                     "titre": art["titre"], "chapeau": art.get("chapeau", "")})
    articles.sort(key=lambda a: a["date"], reverse=True)
    chemin.write_text(json.dumps(articles, ensure_ascii=False, indent=1), encoding="utf-8")
    cartes = "".join(
        f'<a class="edition" style="text-decoration:none;display:block" href="{e(a["fichier"])}">'
        f'<span class="tag" style="--c:#7a3cff">{e(a["pays"])}</span> <span class="note">{e(a["date"])}</span>'
        f'<h3 style="margin:.4rem 0">{e(a["titre"])}</h3><p style="margin:0">{e(a["chapeau"])}</p></a>' for a in articles)
    main = '<h2 class="rubrique" style="--c:#7a3cff">Toutes les analyses fiscales</h2>' + cartes
    (SORTIE / "fiscalite.html").write_text(
        page("fr", "Fiscalité · Le Bulletin Économique", entete("Un pays à l'étude chaque semaine"), "", main), encoding="utf-8")


# --- 4. Programme principal --------------------------------------------------
def candidats():
    force = os.getenv("PAYS", "").upper()
    if force in PAYS:
        return [force]
    codes = list(PAYS)
    debut = (datetime.date.today().toordinal() // 7) % len(codes)
    return codes[debut:] + codes[:debut]


def main():
    aujourdhui = datetime.date.today()
    if aujourdhui.weekday() != 0 and os.getenv("FORCER") != "true":
        print("Rubrique Fiscalité : publiée le lundi uniquement.")
        return
    date = aujourdhui.isoformat()
    for iso in candidats():
        donnees = charger(iso)
        if not donnees[PRINCIPAL]:
            print(f"Pas de données pour {PAYS[iso]}, pays suivant.")
            continue
        pairs = [p for p in REFERENCE if p != iso][:3]
        donnees_pairs = {p: charger(p) for p in pairs}
        faits = construire_faits(iso, donnees, pairs, donnees_pairs)
        art = rediger_article(PAYS[iso], ", ".join(PAYS[p] for p in pairs), faits)
        SORTIE.mkdir(exist_ok=True)
        chemin = SORTIE / f"fiscalite-{date}-{iso}.html"
        chemin.write_text(page_article(iso, donnees, pairs, donnees_pairs, art, date), encoding="utf-8")
        maj_liste(date, iso, art)
        bulletin.enregistrer_rubrique("fiscalite", "Fiscalité",
            "une analyse par pays chaque semaine, avec lecture historique et comparaison internationale",
            "fiscalite.html", "#7a3cff")
        bulletin.construire_index()
        print("Publié :", chemin)
        return
    raise SystemExit("Aucun pays avec des données exploitables.")


if __name__ == "__main__":
    main()
