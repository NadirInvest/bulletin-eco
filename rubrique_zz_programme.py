"""
Onglet PROGRAMME : menu du jour, programme de la semaine et du mois.
Aucun appel à l'IA : le programme est calculé à partir du rythme de publication des autres rubriques.
(Le nom commence par « rubrique_zz » pour qu'il s'exécute en dernier, après les autres rubriques.)
"""
import datetime
import calendar
import bulletin
import rubrique_science as rs
import rubrique_fiscalite as rf
from bulletin import e, page

SORTIE = bulletin.SORTIE
JOURS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
COULEUR_BULLETIN = "#15508a"

EXTRA_CSS = """
.jour{background:var(--carte);border:1px solid var(--bord);border-radius:14px;padding:14px 18px;margin-bottom:10px}
.jour.auj{border:2px solid #15508a}
.jour h3{margin:0 0 6px;font-size:1rem}
.lignes{display:flex;flex-direction:column;gap:6px}
.ligne{display:flex;align-items:center;gap:8px;flex-wrap:wrap;text-decoration:none;font-size:.92rem}
a.ligne:hover b{text-decoration:underline}
.pt{width:10px;height:10px;border-radius:50%;background:var(--c);flex:none}
.etat{font-size:.74rem;color:var(--doux);border:1px solid var(--bord);border-radius:999px;padding:1px 9px}
.etat.ok{color:var(--hausse);border-color:var(--hausse)}
details.semaine{background:var(--carte);border:1px solid var(--bord);border-radius:14px;padding:10px 16px;margin-bottom:10px}
details.semaine summary{cursor:pointer;font-weight:600}
.cal{display:grid;grid-template-columns:1fr;gap:12px}
@media (min-width:700px){.cal{grid-template-columns:1fr 1fr}}
"""
bulletin.CSS = bulletin.CSS + EXTRA_CSS


def programme_du_jour(d):
    """Liste (étiquette, sujet, couleur, fichier) des publications prévues ce jour-là."""
    semaine = d.toordinal() // 7  # même formule que les rubriques : un sujet par semaine
    items = [("Bulletin du jour", "L'actualité économique mondiale, analysée", COULEUR_BULLETIN, f"{d.isoformat()}-fr.html")]
    if d.weekday() == 0:
        codes = list(rf.PAYS)
        iso = codes[semaine % len(codes)]
        items.append(("Fiscalité", f"Analyse fiscale : {rf.PAYS[iso]}", "#7a3cff", f"fiscalite-{d.isoformat()}-{iso}.html"))
    for cle, theme in rs.THEMES.items():
        if theme["jour"] == d.weekday():
            sujet = theme["sujets"][semaine % len(theme["sujets"])].split("|")[1]
            etiquette = theme["nom"] + (f" · {theme['niveau']}" if theme["niveau"] else "")
            items.append((etiquette, sujet, theme["couleur"], f"{theme['rubrique']}-{d.isoformat()}-{cle}.html"))
    return items


def ligne(item, moment):
    etiquette, sujet, couleur, fichier = item
    publie = (SORTIE / fichier).exists()
    contenu = f'<span class="pt" style="--c:{couleur}"></span><b>{e(etiquette)}</b><span>{e(sujet)}</span>'
    if publie:
        return f'<a class="ligne" href="{e(fichier)}">{contenu}<span class="etat ok">Lire</span></a>'
    return f'<div class="ligne">{contenu}<span class="etat">{ {"passe": "Non publié", "auj": "En préparation", "futur": "Prévu"}[moment] }</span></div>'


def bloc_jour(d, aujourd_hui):
    est_auj = d == aujourd_hui
    moment = "auj" if est_auj else ("passe" if d < aujourd_hui else "futur")
    titre = f"{JOURS[d.weekday()]} {d.day} {MOIS[d.month - 1]}" + (" (aujourd'hui)" if est_auj else "")
    lignes = "".join(ligne(it, moment) for it in programme_du_jour(d))
    return f'<div class="jour{" auj" if est_auj else ""}"><h3>{e(titre)}</h3><div class="lignes">{lignes}</div></div>'


def construire(aujourd_hui):
    lundi = aujourd_hui - datetime.timedelta(days=aujourd_hui.weekday())
    semaine = [lundi + datetime.timedelta(days=i) for i in range(7)]

    menu_du_jour = bloc_jour(aujourd_hui, aujourd_hui)
    bloc_semaine = "".join(bloc_jour(d, aujourd_hui) for d in semaine)

    mois = ""
    for sem in calendar.Calendar(0).monthdatescalendar(aujourd_hui.year, aujourd_hui.month):
        jours = [d for d in sem if d.month == aujourd_hui.month]
        ouvert = " open" if aujourd_hui in sem else ""
        titre = f"Semaine du {jours[0].day} au {jours[-1].day} {MOIS[aujourd_hui.month - 1]}"
        mois += f'<details class="semaine"{ouvert}><summary>{e(titre)}</summary><div style="margin-top:10px">' + \
                "".join(bloc_jour(d, aujourd_hui) for d in jours) + "</div></details>"

    main = (
        f'<h2 class="rubrique" style="--c:{COULEUR_BULLETIN}">Menu du jour</h2>{menu_du_jour}'
        f'<div class="bloc"><h3>Les cours de marché</h3><p>Indices, matières premières, devises et métaux précieux sont actualisés '
        f'toutes les heures dans les colonnes du site (données différées ou de clôture).</p></div>'
        f'<h2 class="rubrique" style="--c:#7a3cff">Programme de la semaine</h2>{bloc_semaine}'
        f'<h2 class="rubrique" style="--c:#e8590c">Programme de {e(MOIS[aujourd_hui.month - 1])} {aujourd_hui.year}</h2>{mois}'
        '<h2 class="rubrique" style="--c:#6c757d">Notre rythme de publication</h2>'
        '<div class="bloc"><ul>'
        '<li><b>Chaque jour</b> : le bulletin d\'actualité économique, avec analyse, regard critique et pistes de solution.</li>'
        '<li><b>Lundi</b> : fiscalité, un pays à l\'étude chaque semaine.</li>'
        '<li><b>Mardi</b> : management ; <b>mercredi</b> : gestion des ressources humaines.</li>'
        '<li><b>Jeudi</b> : économie, angle macroéconomique ; <b>vendredi</b> : économie, angle microéconomique.</li>'
        '<li><b>Toutes les heures</b> : cours de marché.</li></ul>'
        '<p class="note">Les rubriques de recherche s\'appuient sur des articles scientifiques récents ; chaque sujet change chaque semaine. '
        'Le programme peut évoluer au fil des nouvelles rubriques.</p></div>'
        '<h2 class="rubrique" style="--c:#c2255c">En préparation</h2>'
        '<div class="bloc"><ul><li>Introductions en bourse et augmentations de capital</li>'
        '<li>Analyseur financier en ligne et analyses d\'entreprises cotées</li>'
        '<li>Actualité économique par pays</li>'
        '<li>Nouvelles langues : espagnol, portugais, allemand, chinois</li></ul></div>'
    )
    entete = ('<h1 class="site">Programme éditorial</h1>'
              '<p class="sous">Ce que vous lirez aujourd\'hui, cette semaine et ce mois-ci</p>'
              '<div class="langues"><a href="index.html">Accueil</a><a href="archives.html">Archives</a></div>')
    (SORTIE / "programme.html").write_text(
        page("fr", "Programme éditorial · Le Bulletin Économique", entete, "", main,
             description="Le menu du jour, le programme de la semaine et du mois : fiscalité, management, GRH, économie."),
        encoding="utf-8")


def main():
    SORTIE.mkdir(exist_ok=True)
    construire(datetime.date.today())
    bulletin.enregistrer_rubrique("programme", "Programme", "le menu du jour et les sujets de la semaine et du mois",
                                  "programme.html", "#c2255c")
    bulletin.construire_index()
    print("Publié : programme.html")


if __name__ == "__main__":
    main()
