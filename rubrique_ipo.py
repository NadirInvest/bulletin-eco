"""
INTRODUCTIONS EN BOURSE ET AUGMENTATIONS DE CAPITAL : aide aux investisseurs pour repérer des opérations dans le monde.
 1) Veille automatique des dépôts d'introduction en bourse et des prospectus aux États-Unis (flux officiels de la SEC, EDGAR).
 2) Annuaire des bourses et régulateurs officiels dans le monde (où trouver les opérations, les prospectus et les visas).
 3) Guide pédagogique : types d'opérations, déroulement, lecture d'un prospectus, risques, questions à se poser.
Le site informe : il ne recommande aucune opération et ne propose aucune souscription.
Aucun appel à l'IA, aucune clé nécessaire. Les liens de l'annuaire sont vérifiés à chaque mise à jour.
"""
import re
import json
import time
import datetime
import xml.etree.ElementTree as ET
import requests
import bulletin
import rubrique_lecture as rl
from bulletin import e, page

SORTIE = bulletin.SORTIE
# La SEC exige que les programmes automatiques s'identifient : nom + adresse e-mail de contact.
# Remplacez l'adresse ci-dessous par la vôtre si vous le souhaitez (elle n'est utilisée que pour s'identifier auprès de la SEC).
NOM = "BulletinEco"
EMAIL = "nadirinvest@users.noreply.github.com"
IDENTITES = [f"{NOM} {EMAIL}", f"{NOM}/1.0 ({EMAIL})"]  # formats « Nom adresse » puis « nom/version (adresse) »
FLUX = [
    ("S-1", "Dépôt d'enregistrement (projet d'introduction ou d'émission)"),
    ("F-1", "Dépôt d'enregistrement d'un émetteur étranger"),
    ("424B4", "Prospectus définitif (conditions de l'opération fixées)"),
]
URL_FLUX = ("https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type={t}&company=&dateb=&owner=include&start=0&count=100&output=atom")
CONSERVATION_JOURS = 90
NS = {"a": "http://www.w3.org/2005/Atom"}

# Pays, bourse, site, régulateur, site (liens vérifiés à chaque mise à jour)
REGIONS = [
    ("Amérique du Nord", [
        ("États-Unis", "NYSE", "https://www.nyse.com/", "SEC", "https://www.sec.gov/"),
        ("États-Unis", "Nasdaq", "https://www.nasdaq.com/", "SEC", "https://www.sec.gov/"),
        ("Canada", "TSX", "https://www.tsx.com/", "Autorités canadiennes en valeurs mobilières", "https://www.securities-administrators.ca/"),
        ("Mexique", "BMV", "https://www.bmv.com.mx/", "CNBV", "https://www.gob.mx/cnbv")]),
    ("Amérique du Sud", [
        ("Brésil", "B3", "https://www.b3.com.br/", "CVM", "https://www.gov.br/cvm/"),
        ("Argentine", "BYMA", "https://www.byma.com.ar/", "CNV", "https://www.argentina.gob.ar/cnv"),
        ("Uruguay", "Bolsa de Valores de Montevideo", "https://www.bvm.com.uy/", "Banque centrale d'Uruguay", "https://www.bcu.gub.uy/")]),
    ("Europe", [
        ("France, Portugal, Pays-Bas, Belgique, Norvège...", "Euronext", "https://www.euronext.com/", "AMF (France)", "https://www.amf-france.org/"),
        ("Portugal", "Euronext Lisbonne", "https://www.euronext.com/", "CMVM", "https://www.cmvm.pt/"),
        ("Allemagne", "Deutsche Börse", "https://www.deutsche-boerse.com/", "BaFin", "https://www.bafin.de/"),
        ("Royaume-Uni", "London Stock Exchange", "https://www.londonstockexchange.com/", "FCA", "https://www.fca.org.uk/"),
        ("Suisse", "SIX Swiss Exchange", "https://www.six-group.com/", "FINMA", "https://www.finma.ch/"),
        ("Espagne", "Bolsas y Mercados Españoles", "https://www.bolsasymercados.es/", "CNMV", "https://www.cnmv.es/"),
        ("Italie", "Borsa Italiana", "https://www.borsaitaliana.it/", "Consob", "https://www.consob.it/"),
        ("Suède, Danemark, Finlande", "Nasdaq Nordic", "https://www.nasdaqomxnordic.com/", "Autorités nationales", "https://www.esma.europa.eu/"),
        ("Russie", "Moscow Exchange", "https://www.moex.com/", "Banque de Russie", "https://www.cbr.ru/eng/"),
        ("Turquie", "Borsa Istanbul", "https://www.borsaistanbul.com/", "SPK", "https://www.spk.gov.tr/")]),
    ("Afrique et Moyen-Orient", [
        ("Maroc", "Bourse de Casablanca", "https://www.casablanca-bourse.com/", "AMMC", "https://www.ammc.ma/"),
        ("Tunisie", "Bourse de Tunis", "https://www.bvmt.com.tn/", "CMF", "https://www.cmf.tn/"),
        ("Égypte", "EGX", "https://www.egx.com.eg/", "FRA", "https://www.fra.gov.eg/"),
        ("Afrique de l'Ouest (UEMOA)", "BRVM", "https://www.brvm.org/", "CREPMF", "https://www.crepmf.org/"),
        ("Nigeria", "NGX", "https://ngxgroup.com/", "SEC Nigeria", "https://sec.gov.ng/"),
        ("Afrique du Sud", "JSE", "https://www.jse.co.za/", "FSCA", "https://www.fsca.co.za/"),
        ("Arabie saoudite", "Saudi Exchange (Tadawul)", "https://www.saudiexchange.sa/", "CMA", "https://cma.org.sa/"),
        ("Émirats arabes unis", "ADX et DFM", "https://www.adx.ae/", "SCA", "https://www.sca.gov.ae/")]),
    ("Asie-Pacifique", [
        ("Inde", "NSE", "https://www.nseindia.com/", "SEBI", "https://www.sebi.gov.in/"),
        ("Inde", "BSE", "https://www.bseindia.com/", "SEBI", "https://www.sebi.gov.in/"),
        ("Chine", "Bourse de Shanghai", "https://english.sse.com.cn/", "CSRC", "http://www.csrc.gov.cn/"),
        ("Chine", "Bourse de Shenzhen", "https://www.szse.cn/English/", "CSRC", "http://www.csrc.gov.cn/"),
        ("Hong Kong", "HKEX", "https://www.hkex.com.hk/", "SFC", "https://www.sfc.hk/"),
        ("Japon", "Japan Exchange Group", "https://www.jpx.co.jp/english/", "FSA", "https://www.fsa.go.jp/en/"),
        ("Corée du Sud", "Korea Exchange", "https://global.krx.co.kr/", "FSS", "https://english.fss.or.kr/"),
        ("Indonésie", "IDX", "https://www.idx.co.id/", "OJK", "https://www.ojk.go.id/"),
        ("Malaisie", "Bursa Malaysia", "https://www.bursamalaysia.com/", "Securities Commission", "https://www.sc.com.my/"),
        ("Thaïlande", "SET", "https://www.set.or.th/", "SEC Thaïlande", "https://www.sec.or.th/"),
        ("Philippines", "PSE", "https://www.pse.com.ph/", "SEC Philippines", "https://www.sec.gov.ph/"),
        ("Australie", "ASX", "https://www.asx.com.au/", "ASIC", "https://asic.gov.au/"),
        ("Nouvelle-Zélande", "NZX", "https://www.nzx.com/", "FMA", "https://www.fma.govt.nz/")]),
]

GUIDE = [
    ("Qu'est-ce qu'une introduction en bourse ?",
     "Une introduction en bourse (IPO, pour Initial Public Offering) est la première mise en vente des actions d'une entreprise au public, sur une bourse. "
     "L'entreprise cherche en général à lever des capitaux pour se développer, à donner de la liquidité à ses actionnaires, à gagner en notoriété ou à permettre "
     "à d'anciens investisseurs de sortir. Une fois cotée, elle doit publier régulièrement des informations financières."),
    ("Les principaux types d'opérations",
     "• Introduction en bourse (IPO) : offre d'actions au public, avec ou sans émission d'actions nouvelles.\n"
     "• Introduction directe : cotation des actions existantes, sans offre ni levée de fonds nouvelle.\n"
     "• Augmentation de capital avec droit préférentiel de souscription : les actionnaires actuels peuvent souscrire en priorité aux actions nouvelles, "
     "ce qui limite la dilution de leur participation (selon les règles de chaque pays).\n"
     "• Augmentation de capital sans droit préférentiel (placement privé ou accéléré) : actions nouvelles proposées à des investisseurs choisis, souvent institutionnels.\n"
     "• Offre secondaire : des actionnaires existants vendent leurs actions ; l'entreprise ne reçoit pas l'argent.\n"
     "• Émission obligataire ou obligations convertibles : emprunt pouvant se transformer en actions."),
    ("Déroulement type d'une opération",
     "1. L'entreprise choisit ses banques conseil et prépare ses comptes audités.\n"
     "2. Un projet de prospectus est déposé auprès du régulateur du marché.\n"
     "3. Le régulateur examine le document puis l'approuve ou lui accorde son visa, selon les pays.\n"
     "4. Une fourchette de prix est annoncée, puis les investisseurs expriment leur demande (constitution du livre d'ordres).\n"
     "5. Le prix définitif est fixé et les actions sont attribuées ; l'attribution peut être inférieure à la demande.\n"
     "6. Les actions commencent à être négociées. Les anciens actionnaires sont souvent soumis à une période de blocage de leurs titres (lock-up)."),
    ("Comment lire un prospectus",
     "Le prospectus est le document officiel de l'opération. Parcourez en priorité : le résumé de l'opération ; les facteurs de risque ; l'utilisation prévue des fonds levés ; "
     "les comptes historiques et leur évolution ; l'actionnariat avant et après l'opération (mesure de la dilution) ; la gouvernance et la rémunération des dirigeants ; "
     "les conflits d'intérêts éventuels ; la politique de dividendes ; les conditions de l'offre (prix ou fourchette, calendrier, règles d'attribution)."),
    ("Comment participer à une opération",
     "La souscription passe par un intermédiaire autorisé (banque ou courtier) dans le pays de la bourse concernée. Certaines opérations sont réservées aux investisseurs "
     "institutionnels ; d'autres sont ouvertes au public avec une période de souscription et des règles d'attribution. Avant d'investir à l'étranger, vérifiez : "
     "les règles de change, la fiscalité des dividendes et des plus-values, les retenues à la source et les conventions fiscales, les frais et la protection offerte par le régulateur local."),
    ("Les risques à garder en tête",
     "• Une forte volatilité du cours, surtout les premiers mois.\n"
     "• Un prix d'introduction qui peut être trop élevé ou trop bas par rapport à la valeur réelle de l'entreprise.\n"
     "• Peu d'historique de cotation et parfois des comptes récents ou en forte croissance difficiles à comparer.\n"
     "• La dilution lors d'une augmentation de capital si vous ne souscrivez pas.\n"
     "• Le risque de liquidité, de change et de pays pour les marchés étrangers.\n"
     "• Un actionnaire de contrôle qui peut conserver l'essentiel du pouvoir.\n"
     "Les performances passées ne préjugent pas des performances futures."),
    ("Dix questions à se poser avant de souscrire",
     "1. Que fait l'entreprise, et comment gagne-t-elle de l'argent ?\n"
     "2. À quoi serviront les fonds levés ?\n"
     "3. Les comptes sont-ils audités et cohérents sur plusieurs années ?\n"
     "4. Quelle est la valorisation implicite, comparée à des entreprises similaires ?\n"
     "5. Qui sont les actionnaires avant et après l'opération ?\n"
     "6. Quelle dilution l'opération entraîne-t-elle ?\n"
     "7. Quels sont les trois principaux risques cités par l'entreprise ?\n"
     "8. Quelle est la durée de blocage des anciens actionnaires ?\n"
     "9. Quels sont les frais, les impôts et les contraintes de change pour moi ?\n"
     "10. Quelle part de mon épargne suis-je prêt à exposer à cette opération ?"),
]

CSS_IPO = """
.ligne-ipo{display:flex;gap:10px;align-items:flex-start;flex-wrap:wrap;text-decoration:none;border-bottom:1px solid var(--bord);padding:10px 0}
.ligne-ipo .forme{font-size:.74rem;font-weight:700;color:#fff;background:#15508a;border-radius:6px;padding:2px 8px;white-space:nowrap}
.ligne-ipo .forme.def{background:#2f9e44}.ligne-ipo .forme.etr{background:#7a3cff}
.ligne-ipo .soc{flex:1;min-width:180px}.ligne-ipo .soc b{display:block}.ligne-ipo .soc small{color:var(--doux)}
.ligne-ipo .dt2{font-size:.8rem;color:var(--doux);white-space:nowrap}
.cachee{display:none!important}
table.dir{width:100%;border-collapse:collapse;font-size:.88rem}
table.dir td,table.dir th{padding:8px 6px;border-bottom:1px solid var(--bord);text-align:start;vertical-align:top}
.avertissement{background:var(--baisse-bg);color:var(--baisse);border-radius:12px;padding:12px 16px;font-size:.92rem;margin:12px 0}
.guide p{white-space:pre-line}
"""


# --- 1. Veille SEC -----------------------------------------------------------------
def telecharger(forme):
    """Télécharge le flux Atom : essaie chaque format d'identification jusqu'à obtenir une réponse valide."""
    derniere = ""
    for identite in IDENTITES:
        r = requests.get(URL_FLUX.format(t=forme), timeout=60,
                         headers={"User-Agent": identite, "Accept-Encoding": "gzip, deflate", "Accept": "application/atom+xml, application/xml;q=0.9, */*;q=0.8"})
        if r.status_code == 200:
            return r.content
        derniere = f"HTTP {r.status_code} ({identite.split()[0]}) : {re.sub(r'<[^>]+>', ' ', str(r.text))[:140].strip()}"
        time.sleep(2)
    raise RuntimeError(derniere)


def lire_flux(forme):
    racine = ET.fromstring(telecharger(forme))
    items = []
    for entree in racine.findall("a:entry", NS):
        titre = (entree.findtext("a:title", default="", namespaces=NS) or "").strip()
        lien = ""
        for l in entree.findall("a:link", NS):
            lien = l.get("href", lien)
        date = (entree.findtext("a:updated", default="", namespaces=NS) or "")[:10]
        m = re.match(r"^(\S+)\s+-\s+(.*?)\s+\((\d{6,10})\)\s+\((.*?)\)\s*$", titre)
        if not m or not lien:
            continue
        items.append({"forme": m.group(1), "societe": m.group(2).strip(), "cik": m.group(3), "lien": lien, "date": date})
    return items


def charger_stock():
    try:
        return json.loads((SORTIE / "data" / "ipo-us.json").read_text(encoding="utf-8"))
    except Exception:
        return []


def collecter():
    stock = {x["lien"]: x for x in charger_stock()}
    nouveaux = 0
    for forme, _ in FLUX:
        try:
            for it in lire_flux(forme):
                if it["lien"] not in stock:
                    nouveaux += 1
                stock[it["lien"]] = it
            print(f"  {forme} : flux lu")
        except Exception as erreur:
            print(f"  SEC {forme} : {erreur}")
        time.sleep(1)  # politesse envers le serveur de la SEC
    limite = (datetime.date.today() - datetime.timedelta(days=CONSERVATION_JOURS)).isoformat()
    items = sorted((x for x in stock.values() if x.get("date", "") >= limite), key=lambda x: x["date"], reverse=True)[:500]
    (SORTIE / "data").mkdir(parents=True, exist_ok=True)
    (SORTIE / "data" / "ipo-us.json").write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
    print(f"  {len(items)} dépôts conservés, {nouveaux} nouveau(x)")
    return items


# --- 2. Page -----------------------------------------------------------------------
def categorie(forme):
    if forme.startswith("424B"):
        return "def", "Prospectus définitif"
    if forme.startswith("F-1"):
        return "etr", "Émetteur étranger"
    return "", "Dépôt d'enregistrement"


def bloc_us(items, maj):
    if not items:
        return ('<div class="bloc"><p class="note">Les données de la SEC sont momentanément indisponibles. Consultez directement le site de la '
                '<a href="https://www.sec.gov/edgar/search/" target="_blank" rel="noopener">recherche EDGAR</a>.</p></div>')
    lignes = ""
    for it in items:
        cls, libelle = categorie(it["forme"])
        lignes += (f'<a class="ligne-ipo item" href="{e(it["lien"])}" target="_blank" rel="noopener" data-c="{"def" if cls == "def" else "dep"}">'
                   f'<span class="forme {cls}">{e(it["forme"])}</span><span class="soc"><b>{e(it["societe"])}</b><small>{e(libelle)}</small></span>'
                   f'<span class="dt2">{e(it["date"])}</span></a>')
    return (
        '<div class="bloc"><div class="outils" style="position:static"><input id="rech" class="rech" type="search" placeholder="Rechercher une société...">'
        '<div class="puces"><button class="puce actif" data-c="tous">Tout</button><button class="puce" data-c="dep">Dépôts d\'enregistrement (S-1, F-1)</button>'
        '<button class="puce" data-c="def">Prospectus définitifs (424B4)</button></div><div class="note" id="compte"></div></div>'
        f'<div id="liste">{lignes}</div>'
        '<p class="note"><b>À savoir :</b> un dépôt S-1 ou F-1 ne signifie pas qu\'une introduction aura lieu : la société peut renoncer, retarder, ou le dépôt peut concerner '
        'une autre opération (revente d\'actions par des actionnaires, par exemple). Un prospectus définitif (424B4) indique que les conditions d\'une opération ont été fixées. '
        f'Source : SEC, base EDGAR (flux officiels). Dernière collecte : {e(maj)}. Le lien mène au dépôt original sur le site de la SEC.</p></div>')


def bloc_annuaire(liens_verifies):
    html = ""
    n = 0
    for region, lignes in REGIONS:
        corps = ""
        for pays, bourse, u1, regul, u2 in lignes:
            (a1, ok1), (a2, ok2) = liens_verifies[n], liens_verifies[n + 1]
            n += 2
            l1 = f'<a href="{e(a1)}" target="_blank" rel="noopener">{e(bourse)}</a>' if ok1 else e(bourse)
            l2 = f'<a href="{e(a2)}" target="_blank" rel="noopener">{e(regul)}</a>' if ok2 else e(regul)
            corps += f"<tr><td>{e(pays)}</td><td>{l1}</td><td>{l2}</td></tr>"
        html += (f'<div class="bloc"><h3>{e(region)}</h3><div class="scroll"><table class="dir"><tr><th>Pays</th><th>Bourse</th><th>Régulateur</th></tr>{corps}</table></div></div>')
    return html


def bloc_guide():
    return "".join(f'<div class="bloc guide"><h3>{e(t)}</h3><p>{e(c)}</p></div>' for t, c in GUIDE)


JS = r"""
(function(){var etat={c:'tous',q:''},items=[].slice.call(document.querySelectorAll('.ligne-ipo'));
function ap(){var n=0,q=etat.q.toLowerCase();items.forEach(function(i){var ok=(etat.c==='tous'||i.dataset.c===etat.c)&&(!q||i.textContent.toLowerCase().indexOf(q)>-1);i.classList.toggle('cachee',!ok);if(ok)n++});
var c=document.getElementById('compte');if(c)c.textContent=document.documentElement.lang==='en'?(n+' filing'+(n>1?'s':'')):(n+' dépôt'+(n>1?'s':''))}
document.querySelectorAll('.puce').forEach(function(p){p.addEventListener('click',function(){document.querySelectorAll('.puce').forEach(function(x){x.classList.remove('actif')});p.classList.add('actif');etat.c=p.dataset.c;ap()})});
var r=document.getElementById('rech');if(r)r.addEventListener('input',function(ev){etat.q=ev.target.value;ap()});ap()})();
"""


def construire(items, liens_verifies):
    maj = datetime.datetime.now(datetime.timezone.utc).strftime("%d/%m/%Y à %H:%M UTC")
    main = (
        '<span class="tag" style="--c:#c2255c">Marchés financiers</span>'
        '<h2 style="font-size:1.7rem;line-height:1.3;margin:.5rem 0">Introductions en bourse et augmentations de capital</h2>'
        '<p class="chapeau">Repérez les opérations en cours dans le monde, trouvez les sources officielles et apprenez à lire un prospectus avant d\'investir.</p>'
        '<div class="avertissement"><b>Information uniquement.</b> Ce site ne recommande aucune opération, ne propose aucune souscription et ne constitue pas un conseil en investissement. '
        'Investir dans une introduction en bourse ou une augmentation de capital comporte un risque de perte en capital. Lisez toujours le prospectus officiel et renseignez-vous '
        'auprès d\'un intermédiaire agréé de votre pays.</div>'
        '<h2 class="rubrique" style="--c:#15508a">Aux États-Unis : dépôts et prospectus récents (SEC)</h2>'
        f'{bloc_us(items, maj)}'
        '<h2 class="rubrique" style="--c:#7a3cff">Dans le monde : où trouver les opérations officielles</h2>'
        '<p class="note">Pour chaque pays, voici la bourse et le régulateur qui publient les introductions en bourse, les nouvelles cotations, les augmentations de capital et les prospectus approuvés. '
        'Cherchez sur leur site des mots comme « IPO », « nouvelles cotations », « prospectus » ou « augmentation de capital ». '
        'Nous automatisons progressivement leur suivi, place par place, après vérification de chaque source.</p>'
        f'{bloc_annuaire(liens_verifies)}'
        '<h2 class="rubrique" style="--c:#2f9e44">Guide de l\'investisseur</h2>'
        f'{bloc_guide()}'
        '<h2 class="rubrique" style="--c:#e8590c">Nos outils pour analyser une opération</h2>'
        '<div class="grille"><a class="carte lien" href="analyseur.html"><h3>Analyseur financier</h3><p>Importez les comptes de l\'entreprise : ratios, équilibre financier et valorisation indicative.</p></a>'
        '<a class="carte lien" href="fiscalite.html"><h3>Fiscalité</h3><p>Comprenez la fiscalité du pays où vous envisagez d\'investir.</p></a>'
        '<a class="carte lien" href="macro.html"><h3>Indicateurs</h3><p>Croissance, inflation, dette, balance commerciale : mesurez le contexte économique du pays.</p></a>'
        '<a class="carte lien" href="coin-de-lecture.html"><h3>Coin de lecture</h3><p>Des livres gratuits pour approfondir la finance, la comptabilité et le droit.</p></a></div>'
        f'<script>{JS}</script>'
    )
    entete = ('<h1 class="site">Opérations en bourse</h1><p class="sous">Introductions en bourse et augmentations de capital dans le monde</p>'
              '<div class="langues"><a href="index.html">Accueil</a><a href="programme.html">Programme</a></div>')
    (SORTIE / "ipo.html").write_text(
        page("fr", "Introductions en bourse et augmentations de capital · Le Bulletin Économique", entete, "", main,
             description="Introductions en bourse et augmentations de capital : dépôts récents, bourses et régulateurs du monde, guide de l'investisseur."),
        encoding="utf-8")


def main():
    SORTIE.mkdir(exist_ok=True)
    bulletin.CSS = bulletin.CSS + rl.CSS_LECTURE + CSS_IPO
    items = collecter()
    liens = []
    for _region, lignes in REGIONS:
        for _p, _b, u1, _r, u2 in lignes:
            liens += [(u1, u1), (u2, u2)]
    resultats = rl.verifier_tout(liens)
    print(f"  Annuaire : {len(liens)} liens, {sum(1 for _u, ok in resultats if not ok)} indisponible(s)")
    for (url, _), (_u, ok) in zip(liens, resultats):
        if not ok:
            print(f"    lien indisponible : {url}")
    construire(items, resultats)
    bulletin.enregistrer_rubrique("ipo", "Opérations en bourse", "introductions en bourse et augmentations de capital dans le monde : veille, sources officielles et guide",
                                  "ipo.html", "#c2255c")
    bulletin.construire_index()
    print("Publié : ipo.html")


if __name__ == "__main__":
    main()
