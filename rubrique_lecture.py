"""
COIN DE LECTURE : bibliothèque de livres gratuits et légaux (domaine public ou licence libre),
classés par sujet : économie, fiscalité, management, finance, GRH, comptabilité, contrôle de gestion,
droit des affaires, droit social, psychologie des acteurs, sociologie des entreprises.
Le site ne copie aucun livre : le bouton « Lire » mène à la source officielle.
Chaque lien est vérifié à chaque mise à jour ; s'il est cassé, il est remplacé par la page d'accueil de la source.
Aucun appel à l'IA, aucune clé nécessaire.
"""
import json
import concurrent.futures
import requests
import bulletin
from bulletin import e, page

SORTIE = bulletin.SORTIE

SUJETS = {
    "economie": ("Économie", "economics", "économie", "#2f9e44"),
    "fiscalite": ("Fiscalité", "taxation", "fiscalité", "#7a3cff"),
    "management": ("Management", "management", "management", "#e8590c"),
    "finance": ("Finance", "finance", "finance", "#0d6efd"),
    "grh": ("GRH", "human resource management", "ressources humaines", "#0b7285"),
    "comptabilite": ("Comptabilité", "accounting", "comptabilité", "#364fc7"),
    "controle": ("Contrôle de gestion", "management accounting", "contrôle de gestion", "#5f3dc4"),
    "droit_affaires": ("Droit des affaires", "business law", "droit des affaires", "#a61e4d"),
    "droit_social": ("Droit social", "labour law", "droit du travail", "#c2255c"),
    "psychologie": ("Psychologie des acteurs", "organizational psychology", "psychologie sociale", "#d9480f"),
    "sociologie": ("Sociologie des entreprises", "sociology of organizations", "sociologie du travail", "#087f5b"),
}

OS = "https://openstax.org/details/books/"
OS_HOME = "https://openstax.org/subjects"
OS_LIC = "Licence libre Creative Commons (voir la page du livre)"
PD = "Domaine public"
GUT = "https://www.gutenberg.org/ebooks/search/?query="
GUT_HOME = "https://www.gutenberg.org/"

# titre, auteur/éditeur, sujets, langue, licence, source, url, page d'accueil de repli, description
LIVRES = [
    ("Principles of Economics 3e", "OpenStax", ["economie"], "EN", OS_LIC, "OpenStax", OS + "principles-economics-3e", OS_HOME,
     "Manuel d'introduction couvrant la microéconomie et la macroéconomie, avec exemples et exercices."),
    ("Principles of Microeconomics 3e", "OpenStax", ["economie"], "EN", OS_LIC, "OpenStax", OS + "principles-microeconomics-3e", OS_HOME,
     "Les choix des consommateurs et des entreprises, les marchés et leurs défaillances."),
    ("Principles of Macroeconomics 3e", "OpenStax", ["economie"], "EN", OS_LIC, "OpenStax", OS + "principles-macroeconomics-3e", OS_HOME,
     "Croissance, chômage, inflation, politique budgétaire et monétaire, économie ouverte."),
    ("Principles of Management", "OpenStax", ["management"], "EN", OS_LIC, "OpenStax", OS + "principles-management", OS_HOME,
     "Planification, organisation, direction et contrôle ; introduction au management des équipes et des ressources humaines."),
    ("Organizational Behavior", "OpenStax", ["management", "psychologie", "grh"], "EN", OS_LIC, "OpenStax", OS + "organizational-behavior", OS_HOME,
     "Comportements individuels et collectifs en organisation : motivation, leadership, communication, culture."),
    ("Introduction to Business 2e", "OpenStax", ["management"], "EN", OS_LIC, "OpenStax", OS + "introduction-business", OS_HOME,
     "Panorama de l'entreprise : fonctions, environnement, ressources humaines, marketing, finance."),
    ("Entrepreneurship", "OpenStax", ["management", "finance"], "EN", OS_LIC, "OpenStax", OS + "entrepreneurship", OS_HOME,
     "De l'idée au lancement : opportunités, modèle économique, financement et croissance d'une entreprise."),
    ("Business Ethics", "OpenStax", ["management", "droit_affaires"], "EN", OS_LIC, "OpenStax", OS + "business-ethics", OS_HOME,
     "Éthique et responsabilité des entreprises, gouvernance et conformité."),
    ("Principles of Accounting, Volume 1: Financial Accounting", "OpenStax", ["comptabilite"], "EN", OS_LIC, "OpenStax",
     OS + "principles-accounting-volume-1-financial-accounting", OS_HOME,
     "Comptabilité financière : enregistrement des opérations, états financiers, analyse."),
    ("Principles of Accounting, Volume 2: Managerial Accounting", "OpenStax", ["controle", "comptabilite"], "EN", OS_LIC, "OpenStax",
     OS + "principles-accounting-volume-2-managerial-accounting", OS_HOME,
     "Comptabilité de gestion : coûts, budgets, tableaux de bord et aide à la décision."),
    ("Principles of Finance 2e", "OpenStax", ["finance"], "EN", OS_LIC, "OpenStax", OS + "principles-finance", OS_HOME,
     "Valeur temps de l'argent, risque et rendement, décisions d'investissement et de financement."),
    ("Introductory Business Statistics 2e", "OpenStax", ["controle", "finance"], "EN", OS_LIC, "OpenStax", OS + "introductory-business-statistics-2e", OS_HOME,
     "Statistiques appliquées à la gestion : estimation, tests, régression."),
    ("Business Law I Essentials 2e", "OpenStax", ["droit_affaires"], "EN", OS_LIC, "OpenStax", OS + "business-law-i-essentials", OS_HOME,
     "Contrats, responsabilité, formes juridiques d'entreprise et environnement juridique des affaires (droit américain)."),
    ("Psychology 2e", "OpenStax", ["psychologie"], "EN", OS_LIC, "OpenStax", OS + "psychology-2e", OS_HOME,
     "Introduction à la psychologie : cognition, motivation, personnalité, psychologie sociale."),
    ("Introduction to Sociology 3e", "OpenStax", ["sociologie"], "EN", OS_LIC, "OpenStax", OS + "introduction-sociology-3e", OS_HOME,
     "Concepts de la sociologie : groupes, organisations, stratification, travail et institutions."),
    ("An Inquiry into the Nature and Causes of the Wealth of Nations", "Adam Smith", ["economie", "fiscalite"], "EN", PD, "Project Gutenberg",
     GUT + "wealth+of+nations", GUT_HOME, "Texte fondateur de l'économie classique : division du travail, marché, richesse, impôts."),
    ("Principles of Political Economy", "John Stuart Mill", ["economie"], "EN", PD, "Project Gutenberg",
     GUT + "principles+of+political+economy+mill", GUT_HOME, "Synthèse de l'économie classique du XIXe siècle : production, distribution, échange."),
    ("On the Principles of Political Economy and Taxation", "David Ricardo", ["economie", "fiscalite"], "EN", PD, "Project Gutenberg",
     GUT + "ricardo+political+economy+taxation", GUT_HOME, "Valeur, rente, salaires, profits et effets de l'impôt : un classique de la pensée fiscale."),
    ("The Principles of Scientific Management", "Frederick W. Taylor", ["management", "controle"], "EN", PD, "Project Gutenberg",
     GUT + "principles+of+scientific+management", GUT_HOME, "Le texte qui a lancé l'organisation scientifique du travail."),
    ("The Protestant Ethic and the Spirit of Capitalism", "Max Weber", ["sociologie"], "EN", PD, "Project Gutenberg",
     GUT + "protestant+ethic+spirit+of+capitalism", GUT_HOME, "Étude classique des liens entre valeurs, travail et capitalisme."),
    ("The Theory of the Leisure Class", "Thorstein Veblen", ["sociologie", "economie"], "EN", PD, "Project Gutenberg",
     GUT + "theory+of+the+leisure+class", GUT_HOME, "Analyse critique de la consommation ostentatoire et des institutions économiques."),
    ("The Crowd: A Study of the Popular Mind", "Gustave Le Bon", ["psychologie"], "EN", PD, "Project Gutenberg",
     GUT + "the+crowd+le+bon", GUT_HOME, "Classique de la psychologie des foules et des comportements collectifs."),
    ("The Principles of Psychology", "William James", ["psychologie"], "EN", PD, "Project Gutenberg",
     GUT + "principles+of+psychology+james", GUT_HOME, "Grand traité fondateur de la psychologie moderne."),
]

BIBLIOTHEQUES = [
    ("Les Classiques des sciences sociales", "FR", "Bibliothèque numérique francophone (Québec) en accès libre : œuvres tombées dans le domaine public ou diffusées avec l'accord des auteurs.",
     "http://classiques.uqac.ca/", "Sociologie, économie, psychologie, droit, gestion"),
    ("Gallica (BnF)", "FR", "Bibliothèque numérique de la Bibliothèque nationale de France : livres anciens et du domaine public à lire en ligne.",
     "https://gallica.bnf.fr/", "Tous sujets"),
    ("OpenEdition Books", "FR", "Plateforme de livres de sciences humaines et sociales ; une partie est en accès ouvert (lecture en ligne), vérifiez le statut de chaque livre.",
     "https://books.openedition.org/", "Sociologie, droit, économie, gestion"),
    ("OpenStax", "EN", "Manuels universitaires gratuits sous licence libre, relus par des pairs.", "https://openstax.org/", "Économie, gestion, comptabilité, finance, droit, psychologie, sociologie"),
    ("Open Textbook Library", "EN", "Catalogue de manuels universitaires libres (Université du Minnesota), avec évaluations.", "https://open.umn.edu/opentextbooks/", "Gestion, RH, comptabilité, droit, économie"),
    ("OAPEN Library", "EN", "Livres académiques en accès libre (monographies évaluées par des pairs).", "https://library.oapen.org/", "Droit, économie, sociologie, gestion"),
    ("Directory of Open Access Books (DOAB)", "EN", "Annuaire de livres académiques en libre accès, avec leur licence.", "https://directory.doabooks.org/", "Tous sujets"),
    ("World Bank Open Knowledge Repository", "EN", "Rapports et livres de la Banque mondiale, souvent sous licence libre.", "https://openknowledge.worldbank.org/", "Économie, fiscalité, finance, développement"),
    ("Project Gutenberg", "EN", "Plus de 70 000 livres du domaine public, à lire en ligne ou à télécharger.", "https://www.gutenberg.org/", "Économie, psychologie, sociologie, gestion (classiques)"),
]

# recherches proposées par sujet : (nom de la source, modèle d'URL avec {q})
RECHERCHES = [
    ("Project Gutenberg", "https://www.gutenberg.org/ebooks/search/?query={q}", GUT_HOME),
    ("OAPEN", "https://library.oapen.org/discover?query={q}", "https://library.oapen.org/"),
    ("DOAB", "https://directory.doabooks.org/discover?query={q}", "https://directory.doabooks.org/"),
    ("Wikibooks", "https://en.wikibooks.org/w/index.php?search={q}", "https://en.wikibooks.org/"),
]

CSS_LECTURE = """
.outils{position:sticky;top:46px;z-index:6;background:var(--bg);padding:10px 0 4px}
.rech{width:100%;padding:12px 16px;border-radius:12px;border:1px solid var(--bord);background:var(--carte);color:var(--texte);font-size:1rem}
.puces{display:flex;gap:8px;overflow-x:auto;padding:10px 0 6px;white-space:nowrap}
.puce{cursor:pointer;border:1px solid var(--bord);background:var(--carte);color:var(--texte);padding:6px 14px;border-radius:999px;font-size:.86rem}
.puce.actif{background:#15508a;color:#fff;border-color:#15508a}
.livre{display:flex;flex-direction:column;gap:6px;border-top:6px solid var(--c)}
.livre h3{margin:0;font-size:1.02rem;line-height:1.35}
.livre .aut{font-size:.84rem;color:var(--doux)}
.livre .desc{font-size:.9rem;margin:.2rem 0}
.meta{display:flex;gap:6px;flex-wrap:wrap}
.pastille2{font-size:.72rem;border:1px solid var(--bord);border-radius:999px;padding:2px 9px;color:var(--doux)}
.lic{color:var(--hausse);border-color:var(--hausse)}
.act{display:flex;gap:8px;margin-top:auto;padding-top:6px}
.lire{flex:1;text-align:center;text-decoration:none;background:#15508a;color:#fff;border-radius:10px;padding:8px 12px;font-size:.9rem}
.fav{cursor:pointer;border:1px solid var(--bord);background:var(--carte);color:var(--texte);border-radius:10px;padding:8px 12px;font-size:1rem}
.fav.on{background:#f5c542;border-color:#f5c542;color:#000}
.cachee{display:none!important}
.bib{border-top:5px solid #15508a}
.liste-sujets a{display:inline-block;margin:3px 8px 3px 0;font-size:.86rem}
"""

JS = r"""
(function(){
var cles='coin_favoris',favs=[];try{favs=JSON.parse(localStorage.getItem(cles)||'[]')}catch(x){}
var etat={sujet:'tous',q:''},cartes=[].slice.call(document.querySelectorAll('.livre'));
function sauver(){try{localStorage.setItem(cles,JSON.stringify(favs))}catch(x){}}
function appliquer(){var q=etat.q.toLowerCase(),n=0;cartes.forEach(function(c){
 var ok=(etat.sujet==='tous'||(etat.sujet==='favoris'?favs.indexOf(c.dataset.id)>-1:c.dataset.sujets.split(' ').indexOf(etat.sujet)>-1))&&(!q||c.textContent.toLowerCase().indexOf(q)>-1);
 c.classList.toggle('cachee',!ok);if(ok)n++});
 document.getElementById('compte').textContent=n+' livre'+(n>1?'s':'');
 document.getElementById('vide').hidden=n>0}
document.querySelectorAll('.puce').forEach(function(p){p.addEventListener('click',function(){
 document.querySelectorAll('.puce').forEach(function(x){x.classList.remove('actif')});p.classList.add('actif');etat.sujet=p.dataset.s;appliquer()})});
document.getElementById('rech').addEventListener('input',function(ev){etat.q=ev.target.value;appliquer()});
cartes.forEach(function(c){var b=c.querySelector('.fav');if(favs.indexOf(c.dataset.id)>-1)b.classList.add('on');
 b.addEventListener('click',function(){var i=favs.indexOf(c.dataset.id);if(i>-1){favs.splice(i,1);b.classList.remove('on')}else{favs.push(c.dataset.id);b.classList.add('on')}sauver();if(etat.sujet==='favoris')appliquer()})});
appliquer();
})();
"""


def verifier(url, repli):
    """Renvoie (url à utiliser, vérifiée). Remplace par le repli seulement si la page n'existe pas (404 ou introuvable)."""
    try:
        r = requests.head(url, allow_redirects=True, timeout=12, headers={"User-Agent": "Mozilla/5.0 (compatible; BulletinEco/1.0)"})
        if r.status_code in (405, 501, 403):  # le site refuse HEAD : on réessaie en GET
            r = requests.get(url, allow_redirects=True, timeout=12, stream=True, headers={"User-Agent": "Mozilla/5.0 (compatible; BulletinEco/1.0)"})
        if r.status_code in (404, 410):
            return repli, False
        return url, True
    except requests.exceptions.Timeout:
        return url, True  # lenteur : on garde le lien
    except Exception:
        return repli, False


def verifier_tout(liens):
    """liens : liste de (url, repli) -> liste de (url, ok), vérifiés en parallèle."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        return list(pool.map(lambda x: verifier(*x), liens))


def construire():
    # 1) vérification des liens
    liens = [(l[6], l[7]) for l in LIVRES]
    nb = len(liens)
    for _, patron, accueil in RECHERCHES:
        for _cle, (_n, en, fr, _c) in SUJETS.items():
            liens.append((patron.format(q=en.replace(" ", "+")), accueil))
    resultats = verifier_tout(liens)
    for (url, repli), (final, ok) in zip(liens, resultats):
        if not ok:
            print(f"  Lien remplacé : {url}")
    urls_livres = [r[0] for r in resultats[:nb]]
    urls_recherche = iter([r[0] for r in resultats[nb:]])

    # 2) cartes de livres
    cartes = ""
    for i, (titre, auteur, sujets, langue, licence, source, _u, _r, desc) in enumerate(LIVRES):
        couleur = SUJETS[sujets[0]][3]
        tags = "".join(f'<span class="pastille2">{e(SUJETS[s][0])}</span>' for s in sujets)
        cartes += (
            f'<article class="carte livre" style="--c:{couleur}" data-id="l{i}" data-sujets="{" ".join(sujets)}">'
            f'<h3>{e(titre)}</h3><div class="aut">{e(auteur)} · {e(source)}</div><p class="desc">{e(desc)}</p>'
            f'<div class="meta">{tags}<span class="pastille2">{e(langue)}</span><span class="pastille2 lic">{e(licence)}</span></div>'
            f'<div class="act"><a class="lire" href="{e(urls_livres[i])}" target="_blank" rel="noopener">Lire chez la source</a>'
            '<button class="fav" type="button" title="Ajouter à ma liste de lecture" aria-label="Ajouter à ma liste de lecture">&#9733;</button></div></article>')

    puces = '<button class="puce actif" data-s="tous">Tous</button><button class="puce" data-s="favoris">&#9733; Ma liste</button>'
    puces += "".join(f'<button class="puce" data-s="{k}">{e(v[0])}</button>' for k, v in SUJETS.items())

    bibs = "".join(
        f'<a class="carte lien bib" href="{e(u)}" target="_blank" rel="noopener"><h3>{e(n)}</h3>'
        f'<p>{e(d)}</p><p class="note">{e(l)} · {e(s)}</p></a>' for n, l, d, u, s in BIBLIOTHEQUES)

    par_sujet = ""
    for cle, (nom, en, fr, couleur) in SUJETS.items():
        liens_s = ""
        for (nom_src, _patron, _acc) in RECHERCHES:
            liens_s += f'<a href="{e(next(urls_recherche))}" target="_blank" rel="noopener">{e(nom_src)}</a>'
        par_sujet += (f'<div class="bloc"><h3 style="color:{couleur}">{e(nom)}</h3><div class="liste-sujets">'
                      f'<span class="note">Chercher « {e(en)} » :</span> {liens_s}</div></div>')

    main = (
        '<span class="tag" style="--c:#a61e4d">Bibliothèque</span>'
        '<h2 style="font-size:1.7rem;line-height:1.3;margin:.5rem 0">Coin de lecture</h2>'
        '<p class="chapeau">Des livres gratuits et légaux pour apprendre : économie, fiscalité, management, finance, ressources humaines, '
        'comptabilité, contrôle de gestion, droit, psychologie et sociologie des organisations.</p>'
        '<p class="note">Seuls des ouvrages du domaine public ou sous licence libre sont référencés. Le site ne copie aucun livre : '
        'le bouton « Lire chez la source » vous mène au site officiel, où la licence s\'applique. Selon les pays, le domaine public peut varier : '
        'vérifiez les conditions indiquées par la source. La plupart des manuels sont en anglais ; les bibliothèques francophones sont listées plus bas.</p>'
        '<div class="outils"><input id="rech" class="rech" type="search" placeholder="Rechercher un titre, un auteur, un sujet...">'
        f'<div class="puces">{puces}</div><div class="note" id="compte"></div></div>'
        f'<div class="grille" id="grille">{cartes}</div>'
        '<p class="vide" id="vide" hidden>Aucun livre ne correspond. Essayez un autre mot, ou consultez les bibliothèques ci-dessous.</p>'
        '<h2 class="rubrique" style="--c:#15508a">Bibliothèques libres à explorer</h2>'
        f'<div class="grille">{bibs}</div>'
        '<h2 class="rubrique" style="--c:#7a3cff">Chercher d\'autres livres par sujet</h2>'
        '<p class="note">Certains sujets (fiscalité, droit social, GRH, contrôle de gestion) comptent peu de manuels libres : ces recherches '
        'ouvrent les catalogues des bibliothèques libres sur le thème choisi.</p>'
        f'{par_sujet}'
        f'<script>{JS}</script>'
    )
    entete = ('<h1 class="site">Coin de lecture</h1><p class="sous">Livres gratuits et légaux, classés par sujet</p>'
              '<div class="langues"><a href="index.html">Accueil</a><a href="programme.html">Programme</a></div>')
    (SORTIE / "coin-de-lecture.html").write_text(
        page("fr", "Coin de lecture · Le Bulletin Économique", entete, "", main,
             description="Bibliothèque de livres gratuits et légaux : économie, fiscalité, management, finance, GRH, comptabilité, droit, psychologie, sociologie."),
        encoding="utf-8")


def main():
    SORTIE.mkdir(exist_ok=True)
    bulletin.CSS = bulletin.CSS + CSS_LECTURE
    construire()
    bulletin.enregistrer_rubrique("lecture", "Coin de lecture", "des livres gratuits et légaux, classés par sujet : économie, gestion, droit, psychologie, sociologie",
                                  "coin-de-lecture.html", "#a61e4d")
    bulletin.construire_index()
    print(f"Publié : coin-de-lecture.html ({len(LIVRES)} livres, {len(BIBLIOTHEQUES)} bibliothèques)")


if __name__ == "__main__":
    main()
