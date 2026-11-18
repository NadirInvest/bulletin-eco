"""
Bulletin économique quotidien (version 3) :
collecte RSS + texte des communiqués -> articles d'analyse riches (JSON) -> pages HTML dans docs/
Menu, archives avec recherche, accueil, plan du site. Les rubriques (rubrique_*.py) s'ajoutent toutes seules.
Dépendances gratuites : pip install feedparser requests
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
MAX_ITEMS_PAR_SOURCE = 6
MAX_ARTICLES = 5
MODELE = "gemini-3.1-flash-lite"  # vérifiez le nom du modèle gratuit actuellement disponible
PAUSE_ENTRE_LANGUES = 20  # secondes, pour respecter le quota gratuit
SORTIE = pathlib.Path("docs")
SITE_URL = os.getenv("SITE_URL", "https://nadirinvest.github.io/bulletin-eco/")

RUBRIQUES = {
    "marches": {"fr": "Marchés", "en": "Markets", "ar": "الأسواق", "couleur": "#0d6efd"},
    "banques_centrales": {"fr": "Banques centrales", "en": "Central banks", "ar": "البنوك المركزية", "couleur": "#7a3cff"},
    "economie": {"fr": "Économie mondiale", "en": "World economy", "ar": "الاقتصاد العالمي", "couleur": "#13a89e"},
    "entreprises": {"fr": "Entreprises", "en": "Business", "ar": "الشركات", "couleur": "#e8590c"},
    "commerce": {"fr": "Commerce et échanges", "en": "Trade", "ar": "التجارة", "couleur": "#c2255c"},
    "autre": {"fr": "Autres actualités", "en": "Other news", "ar": "أخبار أخرى", "couleur": "#6c757d"},
}

TEXTES = {
    "fr": {"site": "Le Bulletin Économique", "sous": "L'essentiel de l'actualité économique, analysé et expliqué",
           "une": "À la une", "sources": "Sources", "accueil": "Accueil", "edition": "Édition du",
           "actualite": "Actualité du jour", "archives": "Archives",
           "analyse": "Analyse", "critique": "Regard critique", "pistes": "Pistes de solution", "retenir": "À retenir",
           "avert": "Contenu généré par IA à partir de sources officielles ; ne constitue pas un conseil en investissement."},
    "en": {"site": "The Economic Bulletin", "sous": "Economic news, analysed and explained",
           "une": "Top story", "sources": "Sources", "accueil": "Home", "edition": "Edition of",
           "actualite": "Today's news", "archives": "Archives",
           "analyse": "Analysis", "critique": "Critical view", "pistes": "Possible solutions", "retenir": "Key takeaways",
           "avert": "AI-generated content based on official sources; not investment advice."},
    "ar": {"site": "النشرة الاقتصادية", "sous": "أخبار الاقتصاد، محلّلة ومشروحة",
           "une": "الخبر الرئيسي", "sources": "المصادر", "accueil": "الرئيسية", "edition": "عدد",
           "actualite": "أخبار اليوم", "archives": "الأرشيف",
           "analyse": "التحليل", "critique": "نظرة نقدية", "pistes": "حلول مقترحة", "retenir": "أهم النقاط",
           "avert": "محتوى مُنشأ بالذكاء الاصطناعي من مصادر رسمية ولا يُعد نصيحة استثمارية."},
}

PROMPT = """Tu es rédacteur en chef et analyste d'un journal économique. Écris en {langue}.
À partir des éléments numérotés ci-dessous (communiqués officiels), produis entre 3 et {max_articles} articles d'analyse DÉTAILLÉS et distincts, du plus important au moins important.
Un lecteur doit apprendre des choses concrètes : explique les termes techniques en mots simples, replace l'événement dans son contexte, détaille les conséquences. Ce n'est pas un résumé.
Règles strictes :
- Les faits et les chiffres viennent UNIQUEMENT des éléments fournis ; n'invente aucun fait ni aucun chiffre.
- Tu peux t'appuyer sur des connaissances économiques générales et solides pour expliquer les mécanismes, sans inventer de chiffres.
- Rédige avec tes propres mots (ne recopie pas les phrases des sources).
- Ton neutre et factuel : aucune opinion politique, aucune polémique ; la critique porte sur les limites, les risques et les points non précisés.
- Chaque article contient :
  "rubrique" : une valeur parmi {rubriques},
  "titre" : un titre clair et attractif,
  "chapeau" : 2 à 3 phrases qui donnent l'essentiel,
  "contexte" : 6 à 8 phrases expliquant ce qui s'est passé, pourquoi, et pourquoi c'est important,
  "analyse" : 6 à 8 phrases sur les causes, les mécanismes et les conséquences probables pour l'économie, les entreprises et les ménages,
  "regard_critique" : 3 à 4 phrases sur les limites, les risques ou ce que la source ne dit pas,
  "pistes" : 3 à 4 phrases de solutions ou d'actions concrètes envisageables, formulées comme des pistes,
  "a_retenir" : une liste de 3 points courts à retenir,
  "sources" : la liste des numéros des éléments utilisés (entiers).
- Réponds UNIQUEMENT avec un JSON valide de la forme : {{"articles": [ {{...}}, {{...}} ]}}

Éléments :
{elements}
"""


# --- Utilitaires ---------------------------------------------------------------
def secret(nom):
    """Lit un secret : variable d'environnement, ou liste de secrets transmise par le workflow."""
    if os.getenv(nom):
        return os.getenv(nom)
    try:
        return json.loads(os.getenv("ALL_SECRETS", "{}")).get(nom, "")
    except Exception:
        return ""


def nettoyer(texte):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(texte or ""))).strip()


def e(texte):
    return html.escape(str(texte))


def appeler_gemini(prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODELE}:generateContent"
    corps = {"contents": [{"parts": [{"text": prompt}]}],
             "generationConfig": {"responseMimeType": "application/json", "maxOutputTokens": 8192, "temperature": 0.4}}
    r = requests.post(url, params={"key": os.environ["GEMINI_API_KEY"]}, json=corps, timeout=240)
    r.raise_for_status()
    brut = r.json()["candidates"][0]["content"]["parts"][0]["text"]
    brut = re.sub(r"^```(?:json)?|```$", "", brut.strip(), flags=re.MULTILINE).strip()
    return json.loads(brut)


def compter_mots(x):
    if isinstance(x, str):
        return len(x.split())
    if isinstance(x, dict):
        return sum(compter_mots(v) for v in x.values())
    if isinstance(x, list):
        return sum(compter_mots(v) for v in x)
    return 0


def appeler_gemini_json(prompt, minimum_mots=0, essais=2):
    """Demande un JSON ; si la réponse est trop courte ou tronquée, redemande une fois en insistant."""
    consigne, dernier = "", None
    for n in range(essais):
        try:
            res = appeler_gemini(prompt + consigne)
        except (ValueError, KeyError):  # JSON invalide ou tronqué
            if n == essais - 1:
                if dernier is not None:
                    return dernier
                raise
            consigne = "\n\nATTENTION : réponds avec un JSON complet et valide, sans le tronquer."
            continue
        dernier = res
        if compter_mots(res) >= minimum_mots or n == essais - 1:
            return res
        consigne = (f"\n\nATTENTION : ta réponse précédente était trop courte. Développe davantage chaque section "
                    f"(explications, exemples, détails concrets) pour atteindre au moins {minimum_mots} mots au total.")
    return dernier


# --- 1. Collecte ---------------------------------------------------------------
def texte_page(url):
    """Extrait les paragraphes de la page du communiqué (meilleur effort, sans bloquer en cas d'échec)."""
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (compatible; BulletinEco/1.0)"}, timeout=20)
        r.raise_for_status()
        h = re.sub(r"(?is)<(script|style|nav|header|footer|noscript)[^>]*>.*?</\1>", " ", r.text)
        paragraphes = [nettoyer(p) for p in re.findall(r"(?is)<p[^>]*>(.*?)</p>", h)]
        return " ".join(p for p in paragraphes if len(p) > 60)[:2500]
    except Exception:
        return ""


def collecter():
    elements = []
    for nom, url in SOURCES.items():
        flux = feedparser.parse(url)
        for entree in flux.entries[:MAX_ITEMS_PAR_SOURCE]:
            lien = entree.get("link", "")
            elements.append({
                "id": len(elements) + 1,
                "source": nom,
                "titre": nettoyer(entree.get("title", "")),
                "resume": nettoyer(entree.get("summary", ""))[:500],
                "extrait": texte_page(lien) if lien.startswith("http") else "",
                "lien": lien,
            })
    return elements


# --- 2. Rédaction --------------------------------------------------------------
def rediger(elements, code_langue):
    texte_elements = "\n".join(
        f"{x['id']}. [{x['source']}] {x['titre']} : {x['resume']} {x['extrait']}".strip() for x in elements)
    prompt = PROMPT.format(langue=LANGUE_PROMPT[code_langue], max_articles=MAX_ARTICLES,
                           rubriques=", ".join(RUBRIQUES), elements=texte_elements)
    articles = appeler_gemini_json(prompt, minimum_mots=900)["articles"]
    return [a for a in articles if a.get("titre") and (a.get("contexte") or a.get("texte"))]


# --- 3. Mise en page -----------------------------------------------------------
CSS = """
:root{--bg:#f4f6fa;--carte:#fff;--texte:#1b2430;--doux:#5b6678;--marque:#0b2545;--bord:#e3e8ef}
@media (prefers-color-scheme:dark){:root{--bg:#0e141b;--carte:#17202a;--texte:#e8edf3;--doux:#9aa7b8;--marque:#0a1a2f;--bord:#263341}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--texte);line-height:1.7;
font-family:system-ui,-apple-system,"Segoe UI",Tahoma,"Noto Naskh Arabic",sans-serif}
a{color:inherit}
.wrap{max-width:980px;margin:0 auto;padding:0 16px}
.menu{background:#071a33;position:sticky;top:0;z-index:10}
.menu .wrap{display:flex;align-items:center;gap:2px;overflow-x:auto;white-space:nowrap}
.menu a{color:#dbe7f5;text-decoration:none;padding:13px 12px;font-size:.92rem}
.menu a:hover{background:rgba(255,255,255,.12)}
.menu a.marque{font-weight:800;color:#fff;margin-inline-end:10px}
header{background:linear-gradient(135deg,var(--marque),#15508a);color:#fff;padding:30px 0 22px}
.site{margin:0;font-size:1.9rem;letter-spacing:-.5px}
.sous{margin:.3rem 0 1.1rem;opacity:.85}
.langues{display:flex;gap:8px;flex-wrap:wrap}
.langues a{color:#fff;text-decoration:none;border:1px solid rgba(255,255,255,.55);padding:6px 16px;border-radius:999px;font-size:.92rem}
.langues a.actif{background:#fff;color:var(--marque);font-weight:700}
.date{margin:.9rem 0 0;font-size:.9rem;opacity:.8}
nav.rub{position:sticky;top:46px;z-index:5;background:var(--bg);border-bottom:1px solid var(--bord);padding:10px 0}
nav.rub .wrap{display:flex;gap:8px;overflow-x:auto;white-space:nowrap}
nav.rub a{text-decoration:none;font-size:.88rem;padding:5px 14px;border-radius:999px;border:1px solid var(--bord);background:var(--carte)}
main{padding:22px 0 10px}
.une{background:var(--carte);border:1px solid var(--bord);border-radius:18px;padding:26px;margin-bottom:28px;border-inline-start:8px solid var(--c)}
.une h2{font-size:1.7rem;line-height:1.3;margin:.4rem 0 .6rem}
.chapeau{font-size:1.08rem;font-weight:600;margin:0 0 .8rem}
.tag{display:inline-block;font-size:.78rem;font-weight:700;color:#fff;background:var(--c);padding:3px 11px;border-radius:999px}
h2.rubrique{font-size:1.25rem;margin:30px 0 14px;padding-inline-start:12px;border-inline-start:6px solid var(--c)}
.grille{display:grid;grid-template-columns:repeat(auto-fill,minmax(310px,1fr));gap:16px}
.carte{background:var(--carte);border:1px solid var(--bord);border-radius:14px;padding:18px}
.carte h3{font-size:1.12rem;line-height:1.35;margin:.1rem 0 .5rem}
.carte p,.une p{margin:.4rem 0}
.carte.lien{display:block;text-decoration:none;transition:box-shadow .15s,transform .15s}
.carte.lien:hover{box-shadow:0 6px 18px rgba(0,0,0,.12);transform:translateY(-2px)}
.sec{border-inline-start:3px solid var(--bord);padding-inline-start:12px;margin:.8rem 0}
.sec b{font-size:.78rem;text-transform:uppercase;letter-spacing:.05em;color:var(--doux)}
.sec p{margin:.2rem 0}
.src{font-size:.82rem;color:var(--doux);margin-top:.8rem}
.src a{color:var(--doux)}
.note{font-size:.82rem;color:var(--doux)}
footer{padding:26px 0 40px;color:var(--doux);font-size:.85rem;text-align:center}
.edition{display:block;background:var(--carte);border:1px solid var(--bord);border-radius:14px;padding:18px 20px;margin-bottom:12px}
.edition .liens{display:flex;gap:8px;flex-wrap:wrap;margin-top:8px}
.edition .liens a{text-decoration:none;border:1px solid var(--bord);padding:5px 14px;border-radius:999px;font-size:.9rem}
.edition.grand{border-inline-start:8px solid #15508a;padding:24px}
.edition.grand .liens a{background:#15508a;color:#fff;border-color:#15508a;padding:8px 20px}
.recherche{width:100%;padding:12px 16px;border-radius:12px;border:1px solid var(--bord);background:var(--carte);color:var(--texte);font-size:1rem;margin-bottom:16px}

:root{--hausse:#1b7f3b;--hausse-bg:#e6f4ea;--baisse:#c0272d;--baisse-bg:#fdeaea}
@media (prefers-color-scheme:dark){:root{--hausse:#5fd38a;--hausse-bg:#12301f;--baisse:#ff8a8a;--baisse-bg:#3a1517}}
.up{--t:var(--hausse);--b:var(--hausse-bg)}
.down{--t:var(--baisse);--b:var(--baisse-bg)}
.flat{--t:var(--doux);--b:var(--carte)}
.mise{max-width:1400px;margin:0 auto;padding:0 12px}
.cote{display:none}
@media (min-width:1180px){
.mise{display:grid;grid-template-columns:245px minmax(0,1fr) 245px;gap:20px;align-items:start}
.cote{display:block;position:sticky;top:56px;max-height:calc(100vh - 70px);overflow:auto;padding-top:22px}
.ticker,.panneau-mobile{display:none!important}}
.ticker{overflow:hidden;background:var(--carte);border-bottom:1px solid var(--bord);white-space:nowrap}
.ticker .piste{display:inline-flex;gap:28px;padding:8px 14px;animation:defile 70s linear infinite}
.ticker:hover .piste{animation-play-state:paused}
@keyframes defile{to{transform:translateX(-50%)}}
@media (prefers-reduced-motion:reduce){.ticker{overflow-x:auto}.ticker .piste{animation:none}}
.tk{font-size:.85rem;color:var(--t)}.tk b{color:var(--texte);font-weight:600}
.panneau-mobile{margin:12px 12px 0;background:var(--carte);border:1px solid var(--bord);border-radius:12px;padding:10px 14px}
.panneau-mobile summary{cursor:pointer;font-weight:600}
.cote h4{margin:18px 0 6px;font-size:.76rem;text-transform:uppercase;letter-spacing:.06em;color:var(--doux)}
.lig{display:flex;align-items:center;gap:8px;padding:8px 0;border-bottom:1px solid var(--bord)}
.lig .nm{flex:1;min-width:0;font-size:.88rem;font-weight:600}
.lig small{display:block;font-weight:400;color:var(--doux);font-size:.74rem}
.lig svg{color:var(--t);flex:none}
.lig .vl{text-align:right;font-size:.88rem;font-weight:600}
.lig .vr{display:block;font-size:.8rem;color:var(--t);font-weight:600}
.tuiles{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.tuile{background:var(--b);border-radius:10px;padding:8px 10px;color:var(--t)}
.tuile.flat{border:1px solid var(--bord)}
.tuile small{display:block;font-size:.72rem}
.tuile b{display:block;font-size:.95rem}
.tuile span{font-size:.78rem;font-weight:600}
.pastille{display:inline-block;width:8px;height:8px;border-radius:50%;margin-inline-end:5px;background:#9aa7b8}
.pastille.ouvert{background:var(--hausse)}
.maj{font-size:.72rem;color:var(--doux);margin-top:12px;line-height:1.4}
"""

SCRIPT_MARCHES = """<script>
(function(){
function esc(t){return String(t).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
function f(v,d){return Number(v).toLocaleString('fr-FR',{minimumFractionDigits:d,maximumFractionDigits:d})}
function ouvert(b){var z={NY:['America/New_York',570,960],TYO:['Asia/Tokyo',540,900]}[b];if(!z)return null;
var o={};new Intl.DateTimeFormat('en-US',{timeZone:z[0],weekday:'short',hour:'numeric',minute:'numeric',hour12:false}).formatToParts(new Date()).forEach(function(x){o[x.type]=x.value});
var m=(parseInt(o.hour,10)%24)*60+parseInt(o.minute,10);return ['Sat','Sun'].indexOf(o.weekday)<0&&m>=z[1]&&m<z[2]}
function spark(s){if(!s||s.length<2)return '';var mn=Math.min.apply(null,s),mx=Math.max.apply(null,s),r=(mx-mn)||1,p=s.map(function(v,i){return (i*56/(s.length-1)).toFixed(1)+','+(18-(v-mn)/r*16).toFixed(1)}).join(' ');
return '<svg width="56" height="20" viewBox="0 0 56 20" aria-hidden="true"><polyline points="'+p+'" fill="none" stroke="currentColor" stroke-width="1.5"/></svg>'}
function info(it){var pts=it.unite==='%',v=pts?it.variation_pts:it.variation_pct,c=Math.abs(v)<0.005?'flat':(v>0?'up':'down'),a=c==='up'?'\\u25B2':(c==='down'?'\\u25BC':'\\u2013'),
t=(v>0?'+':'')+f(v,2)+(pts?' pt':' %');return {c:c,a:a,t:t,val:f(it.valeur,it.dec)+(it.unite==='%'?' %':'')}}
function ligne(it){var i=info(it),o=ouvert(it.bourse),p=o===null?'':'<span class="pastille'+(o?' ouvert':'')+'" title="'+(o?'Séance en cours':'Marché fermé')+'"></span>';
return '<div class="lig '+i.c+'"><div class="nm">'+p+esc(it.nom)+'<small>'+esc(it.pays)+'</small></div>'+spark(it.serie)+'<div class="vl">'+i.val+'<span class="vr"><span aria-hidden="true">'+i.a+'</span> '+i.t+'</span></div></div>'}
function tuile(it){var i=info(it);return '<div class="tuile '+i.c+'"><small>'+esc(it.nom)+'</small><b>'+i.val+'</b><span><span aria-hidden="true">'+i.a+'</span> '+i.t+'</span></div>'}
function bloc(g,mode){return '<h4>'+esc(g.titre)+'</h4>'+(mode==='liste'?g.items.map(ligne).join(''):'<div class="tuiles">'+g.items.map(tuile).join('')+'</div>')}
fetch('data/marches.json',{cache:'no-cache'}).then(function(r){return r.ok?r.json():null}).then(function(d){
if(!d||!d.groupes)return;var G={};d.groupes.forEach(function(g){G[g.cle]=g});
var m=new Date(d.maj),h=isNaN(m)?'':m.toLocaleString('fr-FR',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'}),vieux=!isNaN(m)&&(Date.now()-m)>36*3600*1000;
var pied='<div class="maj">'+(vieux?'Données anciennes. ':'')+'Mise à jour : '+h+'. '+esc(d.sources||'')+'</div>';
var gauche=['indices','taux'].filter(function(k){return G[k]}).map(function(k){return bloc(G[k],'liste')}).join('');
var droite=['matieres','metaux','devises'].filter(function(k){return G[k]}).map(function(k){return bloc(G[k],'tuiles')}).join('');
var cg=document.getElementById('cg'),cd=document.getElementById('cd'),pm=document.getElementById('pm'),tk=document.getElementById('tk');
if(cg)cg.innerHTML=gauche+pied;if(cd)cd.innerHTML=droite+pied;
if(pm){pm.innerHTML='<summary>Marchés : indices, matières premières, devises</summary>'+gauche+droite+pied;pm.hidden=false}
var tous=[];d.groupes.forEach(function(g){tous=tous.concat(g.items)});
var seg=tous.map(function(it){var i=info(it);return '<span class="tk '+i.c+'"><b>'+esc(it.nom)+'</b> '+i.val+' <span aria-hidden="true">'+i.a+'</span> '+i.t+'</span>'}).join('');
if(tk&&seg){tk.innerHTML='<div class="piste">'+seg+seg+'</div>';tk.hidden=false}
}).catch(function(){});
})();
</script>"""


def lire_rubriques():
    chemin = SORTIE / "rubriques.json"
    return json.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else []


def enregistrer_rubrique(cle, nom, description, page_liste, couleur):
    """Chaque rubrique s'inscrit ici : elle apparaît automatiquement dans le menu et sur l'accueil."""
    SORTIE.mkdir(exist_ok=True)
    rubriques = [r for r in lire_rubriques() if r["cle"] != cle]
    rubriques.append({"cle": cle, "nom": nom, "description": description, "page": page_liste, "couleur": couleur})
    (SORTIE / "rubriques.json").write_text(json.dumps(rubriques, ensure_ascii=False, indent=1), encoding="utf-8")


def derniere_edition(code):
    dates = sorted(m.group(1) for f in SORTIE.glob("*.html")
                   if (m := re.match(rf"^(\d{{4}}-\d{{2}}-\d{{2}})-{code}\.html$", f.name)))
    return f"{dates[-1]}-{code}.html" if dates else None


def menu(code):
    t = TEXTES[code]
    liens = [(t["accueil"], "index.html")]
    edition = derniere_edition(code)
    if edition:
        liens.append((t["actualite"], edition))
    liens += [(r["nom"], r["page"]) for r in lire_rubriques()]
    liens.append((t["archives"], "archives.html"))
    corps = "".join(f'<a href="{e(h)}">{e(n)}</a>' for n, h in liens)
    return f'<div class="menu"><div class="wrap"><a class="marque" href="index.html">{e(t["site"])}</a>{corps}</div></div>'


def page(code, titre_onglet, contenu_header, contenu_nav, contenu_main, description=""):
    t = TEXTES[code]
    sens = "rtl" if code == "ar" else "ltr"
    desc = description or t["sous"]
    meta = (f'<meta name="description" content="{e(desc)}"><meta property="og:title" content="{e(titre_onglet)}">'
            f'<meta property="og:description" content="{e(desc)}"><meta property="og:type" content="website">'
            f'<meta property="og:site_name" content="{e(t["site"])}">')
    return (
        f'<!DOCTYPE html><html lang="{code}" dir="{sens}"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">' + meta +
        f"<title>{e(titre_onglet)}</title><style>{CSS}</style></head><body>" + menu(code) +
        '<div class="ticker" id="tk" hidden></div>'
        f'<header><div class="wrap">{contenu_header}</div></header>{contenu_nav}'
        '<details class="panneau-mobile" id="pm" hidden></details>'
        '<div class="mise"><aside class="cote" id="cg"></aside>'
        f'<main><div class="wrap">{contenu_main}</div></main>'
        '<aside class="cote" id="cd"></aside></div>'
        f'<footer><div class="wrap">{e(t["avert"])}</div></footer>' + SCRIPT_MARCHES + "</body></html>"
    )


def entete(code, date, actif=None):
    t = TEXTES[code]
    liens = "".join(f'<a class="{"actif" if c == actif else ""}" href="{date}-{c}.html">{e(nom)}</a>' for c, nom in LANGUES.items())
    return (f'<h1 class="site">{e(t["site"])}</h1><p class="sous">{e(t["sous"])}</p>'
            f'<div class="langues">{liens}</div><p class="date">{e(t["edition"])} {e(date)}</p>')


def liens_sources(article, elements, code):
    par_id = {x["id"]: x for x in elements}
    vus, liens = set(), []
    for i in article.get("sources", []):
        x = par_id.get(i) if isinstance(i, int) else None
        if x and x["source"] not in vus and x["lien"].startswith("http"):
            vus.add(x["source"])
            liens.append(f'<a href="{e(x["lien"])}" target="_blank" rel="noopener">{e(x["source"])}</a>')
    return f'<div class="src">{e(TEXTES[code]["sources"])} : {" · ".join(liens)}</div>' if liens else ""


def rubrique_de(article):
    r = article.get("rubrique")
    return r if r in RUBRIQUES else "autre"


def sections(article, code):
    t = TEXTES[code]
    sortie = f'<p>{e(article.get("contexte") or article.get("texte", ""))}</p>'
    for cle, libelle in (("analyse", t["analyse"]), ("regard_critique", t["critique"]), ("pistes", t["pistes"])):
        if article.get(cle):
            sortie += f'<div class="sec"><b>{e(libelle)}</b><p>{e(article[cle])}</p></div>'
    points = [p for p in article.get("a_retenir", []) if isinstance(p, str) and p.strip()]
    if points:
        sortie += (f'<div class="sec"><b>{e(t["retenir"])}</b><ul style="margin:.3rem 0;padding-inline-start:1.2rem">'
                   + "".join(f"<li>{e(p)}</li>" for p in points) + "</ul></div>")
    return sortie


def page_edition(articles, elements, code, date):
    t = TEXTES[code]
    une, reste = articles[0], articles[1:]
    r_une = rubrique_de(une)
    main = (
        f'<section class="une" style="--c:{RUBRIQUES[r_une]["couleur"]}">'
        f'<span class="tag">{e(t["une"])} · {e(RUBRIQUES[r_une][code])}</span>'
        f'<h2>{e(une["titre"])}</h2><p class="chapeau">{e(une.get("chapeau", ""))}</p>'
        f'{sections(une, code)}{liens_sources(une, elements, code)}</section>'
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
            f'<article class="carte"><h3>{e(a["titre"])}</h3><p><strong>{e(a.get("chapeau", ""))}</strong></p>'
            f'{sections(a, code)}{liens_sources(a, elements, code)}</article>' for a in groupes[cle])
        main += (f'<h2 class="rubrique" id="{cle}" style="--c:{infos["couleur"]}">{e(infos[code])}</h2>'
                 f'<div class="grille">{cartes}</div>')
    nav = f'<nav class="rub"><div class="wrap">{"".join(chips)}</div></nav>' if chips else ""
    return page(code, f'{t["site"]} · {date}', entete(code, date, actif=code), nav, main, description=une.get("chapeau", ""))


def publier(articles, elements, code, date):
    SORTIE.mkdir(exist_ok=True)
    chemin = SORTIE / f"{date}-{code}.html"
    chemin.write_text(page_edition(articles, elements, code, date), encoding="utf-8")
    return chemin


# --- 4. Accueil, archives, plan du site ---------------------------------------
def editions_par_date():
    par_date = {}
    for f in SORTIE.glob("*.html"):
        m = re.match(r"^(\d{4}-\d{2}-\d{2})-([a-z]{2})\.html$", f.name)
        if m:
            par_date.setdefault(m.group(1), {})[m.group(2)] = f.name
    return par_date


def tous_les_articles():
    """Tous les articles des rubriques (fichiers *-articles.json), du plus récent au plus ancien."""
    rub = {r["cle"]: r for r in lire_rubriques()}
    items = []
    for f in SORTIE.glob("*-articles.json"):
        cle = f.name[: -len("-articles.json")]
        r = rub.get(cle, {"nom": cle.capitalize(), "couleur": "#6c757d"})
        try:
            donnees = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        items += [{**a, "rubrique": r["nom"], "couleur": r["couleur"]} for a in donnees]
    return sorted(items, key=lambda a: a["date"], reverse=True)


def carte_analyse(a):
    etiquette = a.get("pays") or a.get("sujet") or ""
    suite = f" · {e(etiquette)}" if etiquette else ""
    return (f'<a class="carte lien item" href="{e(a["fichier"])}"><span class="tag" style="--c:{e(a["couleur"])}">'
            f'{e(a["rubrique"])}{suite}</span><h3>{e(a["titre"])}</h3><p>{e(a.get("chapeau", ""))}</p>'
            f'<span class="note">{e(a["date"])}</span></a>')


def liens_langues(fichiers):
    ordre = [c for c in LANGUES if c in fichiers] + sorted(c for c in fichiers if c not in LANGUES)
    return "".join(f'<a href="{fichiers[c]}">{e(LANGUES.get(c, c))}</a>' for c in ordre)


def construire_index():
    t = TEXTES["fr"]
    par_date = editions_par_date()
    dates = sorted(par_date, reverse=True)
    analyses = tous_les_articles()
    contenu = ""
    if dates:
        contenu += (f'<h2 class="rubrique" style="--c:#15508a">Dernière édition du bulletin</h2>'
                    f'<div class="edition grand"><strong>{e(dates[0])}</strong>'
                    f'<div class="liens">{liens_langues(par_date[dates[0]])}</div></div>')
    if analyses:
        contenu += ('<h2 class="rubrique" style="--c:#e8590c">Dernières analyses</h2><div class="grille">'
                    + "".join(carte_analyse(a) for a in analyses[:6]) + "</div>")
    rubriques = lire_rubriques()
    if rubriques:
        contenu += '<h2 class="rubrique" style="--c:#7a3cff">Explorer les rubriques</h2><div class="grille">'
        for r in rubriques:
            contenu += (f'<a class="carte lien" style="border-top:5px solid {e(r["couleur"])}" href="{e(r["page"])}">'
                        f'<h3>{e(r["nom"])}</h3><p>{e(r["description"])}</p></a>')
        contenu += "</div>"
    contenu += f'<p style="margin-top:28px"><a href="archives.html">{e(t["archives"])} : toutes les éditions et analyses &rarr;</a></p>'
    entete_index = f'<h1 class="site">{e(t["site"])}</h1><p class="sous">{e(t["sous"])}</p>'
    (SORTIE / "index.html").write_text(page("fr", t["site"], entete_index, "", contenu), encoding="utf-8")
    construire_archives(par_date, analyses)
    ecrire_sitemap()


def construire_archives(par_date, analyses):
    t = TEXTES["fr"]
    lignes = []
    for d, fichiers in par_date.items():
        lignes.append((d, 0, f'<div class="edition item"><span class="tag" style="--c:#15508a">Bulletin du jour</span> '
                             f'<strong>{e(d)}</strong><div class="liens">{liens_langues(fichiers)}</div></div>'))
    for a in analyses:
        lignes.append((a["date"], 1, carte_analyse(a).replace('class="carte lien item"', 'class="carte lien item" style="margin-bottom:12px"')))
    lignes.sort(key=lambda x: (x[0], x[1]), reverse=True)
    script = ("<script>var q=document.getElementById('q');q.oninput=function(){var v=q.value.toLowerCase();"
              "document.querySelectorAll('.item').forEach(function(x){x.style.display="
              "x.textContent.toLowerCase().indexOf(v)>-1?'':'none'})}</script>")
    main = ('<h2 class="rubrique" style="--c:#15508a">Archives</h2>'
            '<input id="q" class="recherche" type="search" placeholder="Rechercher un pays, un sujet, une date...">'
            + "".join(x[2] for x in lignes) + script)
    entete_arch = f'<h1 class="site">{e(t["archives"])}</h1><p class="sous">Toutes les éditions et toutes les analyses publiées</p>'
    (SORTIE / "archives.html").write_text(page("fr", f'{t["archives"]} · {t["site"]}', entete_arch, "", main), encoding="utf-8")


def ecrire_sitemap():
    base = SITE_URL.rstrip("/") + "/"
    pages = sorted(f.name for f in SORTIE.glob("*.html"))
    xml = ('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
           + "".join(f"<url><loc>{base}{'' if n == 'index.html' else n}</loc></url>" for n in pages) + "</urlset>")
    (SORTIE / "sitemap.xml").write_text(xml, encoding="utf-8")
    (SORTIE / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {base}sitemap.xml\n", encoding="utf-8")


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
