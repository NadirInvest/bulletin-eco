"""
ANALYSEUR FINANCIER EN LIGNE : le visiteur saisit son bilan et son compte de résultat ;
la page calcule les soldes de gestion, l'équilibre financier, les ratios, un diagnostic et une valorisation indicative.
Tout se calcule dans le navigateur : aucune donnée n'est envoyée ni enregistrée.
Page générée : docs/analyseur.html (aucun appel à l'IA, aucune clé nécessaire).
"""
import bulletin
from bulletin import e, page

SORTIE = bulletin.SORTIE

ACTIF = [("a_immo", "Actif immobilisé net (immobilisations)"), ("a_stocks", "Stocks"), ("a_clients", "Créances clients"),
         ("a_autres", "Autres créances et régularisations"), ("a_treso", "Trésorerie-actif (banque, caisse, placements)")]
PASSIF = [("p_cp", "Capitaux propres"), ("p_dfin", "Dettes financières (emprunts à moyen et long terme)"),
          ("p_fourn", "Dettes fournisseurs"), ("p_autres", "Autres dettes à court terme (fiscales, sociales...)"),
          ("p_tresop", "Trésorerie-passif (découverts, crédits de trésorerie)")]
CPC = [("c_ca", "Chiffre d'affaires"), ("c_achats", "Achats consommés (marchandises, matières)"), ("c_ext", "Autres charges externes"),
       ("c_impots", "Impôts et taxes"), ("c_perso", "Charges de personnel"),
       ("c_dot", "Dotations d'exploitation (amortissements, provisions)"),
       ("c_autres", "Autres produits d'exploitation, nets (optionnel)"), ("c_cfin", "Charges financières"),
       ("c_pfin", "Produits financiers"), ("c_nc", "Résultat non courant (+ ou -)"), ("c_is", "Impôt sur les résultats")]
VAL = [("v_plus", "Plus-values latentes nettes (actifs sous-évalués au bilan)", "0"),
       ("v_benef", "Bénéfice normatif (vide = résultat net)", ""),
       ("v_cap", "Taux de capitalisation du bénéfice (%)", "10"),
       ("v_pond", "Pondération patrimoniale (%) de la méthode mixte", "50"),
       ("v_i", "Taux de rémunération des capitaux investis (%)", "6"),
       ("v_n", "Durée du superbénéfice (années)", "5"),
       ("v_mult", "Multiple de l'EBE (valeur d'entreprise / EBE)", "5"),
       ("v_g", "Croissance annuelle des flux sur 5 ans (%)", "3"),
       ("v_r", "Taux d'actualisation (%)", "10"),
       ("v_gt", "Croissance à l'infini (%)", "2"),
       ("v_inv", "Investissements annuels normatifs (vide = dotations d'exploitation)", "")]

CSS_ANALYSEUR = """
.champs{display:grid;grid-template-columns:1fr;gap:10px}
@media (min-width:700px){.champs{grid-template-columns:1fr 1fr}}
.champ label{display:block;font-size:.82rem;color:var(--doux);margin-bottom:2px}
.champ input{width:100%;padding:9px 10px;border-radius:10px;border:1px solid var(--bord);background:var(--bg);color:var(--texte);font-size:1rem}
.deuxcol{display:grid;grid-template-columns:1fr;gap:16px}
@media (min-width:900px){.deuxcol{grid-template-columns:1fr 1fr}}
.actions{display:flex;gap:8px;flex-wrap:wrap;margin:6px 0 16px}
.btn{cursor:pointer;border:1px solid var(--bord);background:var(--carte);color:var(--texte);padding:9px 16px;border-radius:999px;font-size:.92rem}
.btn.pri{background:#15508a;color:#fff;border-color:#15508a}
.kg{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:10px;margin:8px 0 6px}
.kc{background:var(--bg);border:1px solid var(--bord);border-radius:12px;padding:10px 12px}
.kc small{display:block;color:var(--doux);font-size:.74rem}
.kc b{display:block;font-size:1.05rem}
.barre{margin:8px 0}
.barre .t{display:flex;justify-content:space-between;font-size:.86rem}
.barre .b{height:10px;border-radius:6px;background:var(--bord);overflow:hidden;margin-top:3px}
.barre .b i{display:block;height:100%;background:#15508a}
.barre.neg .t span:last-child{color:var(--baisse)}
table.r{width:100%;border-collapse:collapse;font-size:.9rem}
table.r td,table.r th{padding:8px 6px;border-bottom:1px solid var(--bord);text-align:start;vertical-align:top}
table.r td:last-child,table.r th:last-child{text-align:end}
.d{display:inline-block;width:10px;height:10px;border-radius:50%;margin-inline-end:7px;background:#9aa7b8}
.d.ok{background:var(--hausse)}.d.warn{background:#e8a317}.d.bad{background:var(--baisse)}
.diag h4{margin:.8rem 0 .2rem;font-size:.95rem}
.alerte{background:var(--baisse-bg);color:var(--baisse);border-radius:10px;padding:8px 12px;font-size:.9rem;margin:8px 0}
.vide{color:var(--doux);font-style:italic}
@media print{.menu,.ticker,.cote,.panneau-mobile,header,.actions,footer,.champs,.saisie{display:none!important}
.mise{display:block}body{background:#fff;color:#000}}
"""

JS = r"""
(function(){
var $=function(i){return document.getElementById(i)};
function n(i){var v=parseFloat(($(i)||{}).value);return isNaN(v)?0:v}
function has(i){return $(i)&&$(i).value!==''}
function F(v,d){return isFinite(v)?Number(v).toLocaleString('fr-FR',{minimumFractionDigits:d||0,maximumFractionDigits:d||0}):'n.d.'}
function dev(){return ($('devise').value||'').trim()}
function M(v){return isFinite(v)?F(v,0)+' '+dev():'n.d.'}
function P(v,d){return isFinite(v)?F(v*100,d===undefined?1:d)+' %':'n.d.'}
function D(a,b){return b===0?NaN:a/b}
function st(v,ok,warn,inv){if(!isFinite(v))return 'na';if(!inv)return v>=ok?'ok':(v>=warn?'warn':'bad');return v<=ok?'ok':(v<=warn?'warn':'bad')}
function calc(){
 var ca=n('c_ca'),ach=n('c_achats'),ext=n('c_ext'),imp=n('c_impots'),per=n('c_perso'),dot=n('c_dot'),aut=n('c_autres'),cf=n('c_cfin'),pf=n('c_pfin'),nc=n('c_nc'),is=n('c_is');
 var mb=ca-ach,va=mb-ext,ebe=va-imp-per,re=ebe-dot+aut,rf=pf-cf,rc=re+rf,rav=rc+nc,rn=rav-is,caf=rn+dot;
 var immo=n('a_immo'),sto=n('a_stocks'),cl=n('a_clients'),ao=n('a_autres'),trA=n('a_treso');
 var cp=n('p_cp'),df=n('p_dfin'),fo=n('p_fourn'),ap=n('p_autres'),trP=n('p_tresop');
 var TA=immo+sto+cl+ao+trA,TP=cp+df+fo+ap+trP,ecart=TA-TP;
 var dct=fo+ap+trP,fr=cp+df-immo,bfr=sto+cl+ao-fo-ap,tn=trA-trP;
 if(!ca&&!TA){['res_kpi','res_sig','res_eq','res_ratios','res_diag','res_val'].forEach(function(i){$(i).innerHTML=''});
  $('res_kpi').innerHTML='<p class="vide">Saisissez vos chiffres ci-dessus, ou cliquez sur « Charger un exemple » : les résultats s\'affichent ici en temps réel.</p>';return}
 var kp=[['Chiffre d\'affaires',M(ca)],['EBE',M(ebe)],['Résultat net',M(rn)],['CAF (approximative)',M(caf)],['Fonds de roulement',M(fr)],['Besoin en fonds de roulement',M(bfr)],['Trésorerie nette',M(tn)]];
 $('res_kpi').innerHTML=(Math.abs(ecart)>0.5?'<div class="alerte">Le bilan n\'est pas équilibré : l\'actif total ('+M(TA)+') diffère du passif total ('+M(TP)+') de '+M(ecart)+'. Vérifiez vos saisies.</div>':'')
  +'<div class="kg">'+kp.map(function(k){return '<div class="kc"><small>'+k[0]+'</small><b>'+k[1]+'</b></div>'}).join('')+'</div>';
 var sig=[['Chiffre d\'affaires',ca],['Marge brute',mb],['Valeur ajoutée',va],['Excédent brut d\'exploitation (EBE)',ebe],['Résultat d\'exploitation',re],['Résultat financier',rf],['Résultat courant',rc],['Résultat avant impôt',rav],['Résultat net',rn]];
 $('res_sig').innerHTML=sig.map(function(s){var w=ca>0?Math.max(0,Math.min(100,s[1]/ca*100)):0;
  return '<div class="barre'+(s[1]<0?' neg':'')+'"><div class="t"><span>'+s[0]+'</span><span>'+M(s[1])+(ca>0?' · '+P(s[1]/ca):'')+'</span></div><div class="b"><i style="width:'+w+'%"></i></div></div>'}).join('');
 $('res_eq').innerHTML='<table class="r"><tr><td>Capitaux permanents (capitaux propres + dettes financières)</td><td>'+M(cp+df)+'</td></tr>'
  +'<tr><td>Fonds de roulement net global (FRNG)</td><td><b>'+M(fr)+'</b></td></tr>'
  +'<tr><td>Besoin en fonds de roulement (BFR)</td><td><b>'+M(bfr)+'</b></td></tr>'
  +'<tr><td>Trésorerie nette (trésorerie-actif - trésorerie-passif)</td><td><b>'+M(tn)+'</b></td></tr></table>'
  +'<p class="note">Lecture : le fonds de roulement finance le besoin en fonds de roulement ; ce qui reste, positif ou négatif, forme la trésorerie nette.</p>';
 var dc=D(cl,ca)*360,dfo=D(fo,ach+ext)*360,dst=D(sto,ach)*360;
 var cap=caf>0?D(df,caf):(df>0?Infinity:0);
 var R=[
  ['Liquidité générale',D(sto+cl+ao+trA,dct),F(D(sto+cl+ao+trA,dct),2),st(D(sto+cl+ao+trA,dct),1.2,1),'Repère usuel : au moins 1,2'],
  ['Liquidité réduite',D(cl+ao+trA,dct),F(D(cl+ao+trA,dct),2),st(D(cl+ao+trA,dct),0.8,0.5),'Repère usuel : environ 0,8 à 1'],
  ['Liquidité immédiate',D(trA,dct),F(D(trA,dct),2),st(D(trA,dct),0.2,0.1),'Repère usuel : au moins 0,2'],
  ['Autonomie financière (capitaux propres / total)',D(cp,TP),P(D(cp,TP)),st(D(cp,TP),0.33,0.2),'Repère usuel : au moins 33 %'],
  ['Endettement financier (dettes financières / capitaux propres)',cp>0?D(df,cp):Infinity,cp>0?F(D(df,cp),2):'n.d.',cp>0?st(D(df,cp),1,2,true):'bad','Repère usuel : au plus 1'],
  ['Capacité de remboursement (dettes financières / CAF, en années)',cap,isFinite(cap)?F(cap,1):'n.d.',df===0?'ok':(isFinite(cap)?st(cap,4,7,true):'bad'),'Repère usuel : au plus 4 ans'],
  ['Marge nette',D(rn,ca),P(D(rn,ca)),st(D(rn,ca),0.05,0),'Variable selon le secteur'],
  ['Marge d\'exploitation',D(re,ca),P(D(re,ca)),st(D(re,ca),0.08,0),'Variable selon le secteur'],
  ['EBE / chiffre d\'affaires',D(ebe,ca),P(D(ebe,ca)),st(D(ebe,ca),0.10,0.05),'Variable selon le secteur'],
  ['Taux de valeur ajoutée',D(va,ca),P(D(va,ca)),'na','Informatif'],
  ['Rentabilité financière (résultat net / capitaux propres)',D(rn,cp),P(D(rn,cp)),st(D(rn,cp),0.10,0.05),'Repère usuel : au moins 10 %'],
  ['Rentabilité économique (résultat d\'exploitation / total actif)',D(re,TA),P(D(re,TA)),st(D(re,TA),0.08,0.04),'Repère usuel : au moins 8 %'],
  ['Couverture des charges financières (résultat d\'exploitation / charges financières)',cf>0?D(re,cf):NaN,cf>0?F(D(re,cf),1)+' fois':'n.d.',cf>0?st(D(re,cf),3,1.5):'na','Repère usuel : au moins 3 fois'],
  ['Délai moyen de paiement des clients (jours, indicatif)',dc,isFinite(dc)?F(dc,0):'n.d.','na','Calculé hors TVA'],
  ['Délai moyen de paiement des fournisseurs (jours)',dfo,isFinite(dfo)?F(dfo,0):'n.d.','na','Sur achats et charges externes'],
  ['Durée de rotation des stocks (jours)',dst,isFinite(dst)?F(dst,0):'n.d.','na','Stocks / achats consommés']];
 $('res_ratios').innerHTML='<table class="r">'+R.map(function(r){return '<tr><td><span class="d '+r[3]+'"></span>'+r[0]+'<br><span class="note">'+r[4]+'</span></td><td><b>'+r[2]+'</b></td></tr>'}).join('')+'</table>'
  +'<p class="note">Les repères sont des seuils usuels et varient selon le secteur d\'activité : ils servent à orienter l\'analyse, pas à la conclure.</p>';
 // diagnostic
 var F1=[],V=[],S=[];
 if(fr>0&&tn>=0)F1.push('Équilibre financier sain : le fonds de roulement couvre le besoin en fonds de roulement et la trésorerie nette est positive.');
 if(fr<0){V.push('Fonds de roulement négatif : des actifs durables sont financés par des ressources à court terme.');S.push('Renforcer les capitaux permanents (augmentation de capital, dette à plus long terme) ou alléger les immobilisations.')}
 if(tn<0&&bfr>0){V.push('Trésorerie nette négative : l\'entreprise dépend de concours bancaires pour financer son cycle d\'exploitation.');S.push('Réduire le besoin en fonds de roulement (recouvrement des créances, gestion des stocks) ou renégocier le financement.')}
 if(isFinite(dc)&&isFinite(dfo)&&dc>dfo+10){V.push('Les clients paient plus lentement ('+F(dc,0)+' jours) que l\'entreprise ne paie ses fournisseurs ('+F(dfo,0)+' jours) : la trésorerie est sous pression.');S.push('Accélérer le recouvrement (relances, escompte, assurance-crédit) et négocier des délais fournisseurs plus longs.')}
 if(isFinite(dst)&&dst>120){V.push('La rotation des stocks est lente ('+F(dst,0)+' jours) : du capital est immobilisé.');S.push('Revoir la politique d\'achats et d\'approvisionnement, écouler les stocks dormants.')}
 var lg=D(sto+cl+ao+trA,dct);if(isFinite(lg)){if(lg<1){V.push('Liquidité générale inférieure à 1 : les actifs à court terme ne couvrent pas les dettes à court terme.')}else if(lg>=1.2)F1.push('Bonne liquidité générale ('+F(lg,2)+') : les dettes à court terme sont couvertes.')}
 var au=D(cp,TP);if(isFinite(au)){if(au<0.2){V.push('Autonomie financière faible ('+P(au)+') : l\'entreprise est très dépendante de ses créanciers.');S.push('Consolider les fonds propres : mise en réserve des bénéfices, augmentation de capital, comptes courants d\'associés.')}else if(au>=0.33)F1.push('Autonomie financière correcte ('+P(au)+').')}
 if(df>0){if(!isFinite(cap)||cap>7){V.push('Capacité de remboursement insuffisante : les dettes financières représentent plus de 7 années de CAF.');S.push('Rééchelonner la dette ou améliorer la capacité d\'autofinancement avant de s\'endetter davantage.')}else if(cap<=4)F1.push('Endettement soutenable : les dettes financières représentent '+F(cap,1)+' année(s) de CAF.')}
 var mn=D(rn,ca);if(isFinite(mn)){if(rn<0){V.push('Résultat net négatif : l\'entreprise perd de l\'argent sur la période.');S.push('Analyser les postes de charges les plus lourds et la politique de prix pour restaurer la marge.')}else if(mn>=0.05)F1.push('Rentabilité nette satisfaisante ('+P(mn)+' du chiffre d\'affaires).')}
 var me=D(re,ca);if(isFinite(me)&&me<0.03&&rn>=0){V.push('Marge d\'exploitation faible ('+P(me)+') : peu de marge de sécurité face à un choc sur les prix ou les coûts.');S.push('Travailler la marge brute (prix, mix produits, achats) et maîtriser les charges fixes.')}
 if(cf>0&&D(re,cf)<1.5){V.push('Les charges financières absorbent l\'essentiel du résultat d\'exploitation.');S.push('Renégocier les conditions de financement ou réduire l\'endettement coûteux.')}
 function L(a,vide){return a.length?'<ul>'+a.map(function(x){return '<li>'+x+'</li>'}).join('')+'</ul>':'<p class="vide">'+vide+'</p>'}
 $('res_diag').innerHTML='<div class="diag"><h4>Points forts</h4>'+L(F1,'Aucun point fort net détecté avec ces données.')+'<h4>Points de vigilance</h4>'+L(V,'Aucun point de vigilance majeur détecté avec ces données.')+'<h4>Pistes d\'amélioration</h4>'+L(S,'Pas de piste prioritaire détectée.')+'</div>'
  +'<p class="note">Diagnostic automatique et indicatif, fondé sur des règles générales. Il ne remplace pas l\'analyse d\'un expert-comptable.</p>';
 // valorisation
 var ancc=cp+n('v_plus'),B=has('v_benef')?n('v_benef'):rn,tc=n('v_cap')/100,w=n('v_pond')/100,ti=n('v_i')/100,N=Math.max(1,Math.round(n('v_n'))||5),mult=n('v_mult'),g=n('v_g')/100,r=n('v_r')/100,gt=n('v_gt')/100,inv=has('v_inv')?n('v_inv'):dot,dn=df+trP-trA;
 var vr=tc>0?B/tc:NaN,an=tc>0?(1-Math.pow(1+tc,-N))/tc:NaN;
 var f0=caf-inv,pv=0,fl=0;for(var t=1;t<=5;t++){fl=f0*Math.pow(1+g,t);pv+=fl/Math.pow(1+r,t)}
 var tv=r>gt?fl*(1+gt)/(r-gt)/Math.pow(1+r,5):NaN,dcf=isFinite(tv)?pv+tv-dn:NaN;
 var V2=[['Patrimoniale (actif net comptable corrigé)',ancc,'Capitaux propres + plus-values latentes nettes.'],
  ['Rendement (bénéfice capitalisé)',vr,'Bénéfice normatif divisé par le taux de capitalisation.'],
  ['Mixte pondérée (patrimoine et rendement)',isFinite(vr)?w*ancc+(1-w)*vr:NaN,'Pondération au choix ; 50 / 50 correspond à la méthode dite des praticiens.'],
  ['Experts-comptables (superbénéfice actualisé, version simplifiée)',isFinite(an)?ancc+an*(B-ti*ancc):NaN,'Patrimoine corrigé + superbénéfice actualisé sur la durée choisie.'],
  ['Multiple de l\'EBE',ebe*mult-dn,'EBE x multiple, moins la dette financière nette ('+M(dn)+').'],
  ['Flux de trésorerie actualisés (simplifié)',dcf,'Flux de départ = CAF - investissements (par défaut : les dotations), projetés sur 5 ans avec valeur terminale, moins la dette nette.']];
 var ok=V2.map(function(x){return x[1]}).filter(isFinite).sort(function(a,b){return a-b});
 var resume=ok.length?'<div class="kg"><div class="kc"><small>Fourchette basse</small><b>'+M(ok[0])+'</b></div><div class="kc"><small>Valeur centrale (médiane)</small><b>'+M(ok.length%2?ok[(ok.length-1)/2]:(ok[ok.length/2-1]+ok[ok.length/2])/2)+'</b></div><div class="kc"><small>Fourchette haute</small><b>'+M(ok[ok.length-1])+'</b></div></div>':'';
 $('res_val').innerHTML=resume+'<table class="r"><tr><th>Méthode</th><th>Valeur des capitaux propres</th></tr>'+V2.map(function(x){return '<tr><td>'+x[0]+'<br><span class="note">'+x[2]+'</span></td><td><b>'+M(x[1])+'</b></td></tr>'}).join('')+'</table>'
  +'<p class="note">Estimation indicative et pédagogique : les résultats dépendent fortement des hypothèses saisies. Une évaluation réelle (levée de fonds, cession, fusion) exige un évaluateur indépendant et une analyse détaillée.</p>';
}
var EX={a_immo:4200000,a_stocks:1500000,a_clients:2300000,a_autres:400000,a_treso:600000,p_cp:3600000,p_dfin:2400000,p_fourn:1900000,p_autres:600000,p_tresop:500000,
 c_ca:14000000,c_achats:8100000,c_ext:1500000,c_impots:150000,c_perso:2300000,c_dot:600000,c_autres:0,c_cfin:220000,c_pfin:40000,c_nc:-30000,c_is:280000};
var DEF={v_plus:0,v_benef:'',v_cap:10,v_pond:50,v_i:6,v_n:5,v_mult:5,v_g:3,v_r:10,v_gt:2,v_inv:''};
function fill(o,vide){Object.keys(EX).forEach(function(k){$(k).value=vide?'':o[k]});Object.keys(DEF).forEach(function(k){$(k).value=DEF[k]});calc()}
document.querySelectorAll('.champ input').forEach(function(el){el.addEventListener('input',calc)});
$('b_ex').addEventListener('click',function(){fill(EX,false)});
$('b_clr').addEventListener('click',function(){fill(EX,true)});
$('b_pr').addEventListener('click',function(){window.print()});
calc();
})();
"""


def champs(liste):
    html = ""
    for item in liste:
        cle, libelle = item[0], item[1]
        defaut = item[2] if len(item) > 2 else ""
        html += (f'<div class="champ"><label for="{cle}">{e(libelle)}</label>'
                 f'<input id="{cle}" type="number" step="any" inputmode="decimal" value="{e(defaut)}"></div>')
    return html


def construire():
    main = (
        '<span class="tag" style="--c:#364fc7">Outil en ligne</span>'
        '<h2 style="font-size:1.7rem;line-height:1.3;margin:.5rem 0">Analyseur financier d\'entreprise</h2>'
        '<p class="chapeau">Saisissez vos états de synthèse : le site calcule les soldes de gestion, l\'équilibre financier, '
        'les ratios, un diagnostic et une valorisation indicative.</p>'
        '<p class="note">Vos données restent dans votre navigateur : rien n\'est envoyé ni enregistré, et elles disparaissent à la fermeture de la page. '
        'Outil pédagogique et indicatif, il ne remplace pas l\'avis d\'un expert-comptable ou d\'un évaluateur.</p>'
        '<div class="actions"><button class="btn pri" id="b_ex" type="button">Charger un exemple</button>'
        '<button class="btn" id="b_clr" type="button">Tout effacer</button>'
        '<button class="btn" id="b_pr" type="button">Imprimer ou enregistrer en PDF</button></div>'
        '<div class="bloc saisie"><h3>1. Vos données</h3>'
        '<div class="champs" style="margin-bottom:12px"><div class="champ"><label for="devise">Devise</label>'
        '<input id="devise" type="text" value="MAD" maxlength="8"></div></div>'
        f'<div class="deuxcol"><div><h4>Bilan : actif</h4><div class="champs">{champs(ACTIF)}</div></div>'
        f'<div><h4>Bilan : passif</h4><div class="champs">{champs(PASSIF)}</div></div></div>'
        f'<h4 style="margin-top:16px">Compte de résultat</h4><div class="champs">{champs(CPC)}</div>'
        '<p class="note">Saisissez les montants de la dernière année, tous dans la même unité. Les charges sont saisies en positif.</p></div>'
        '<div class="bloc"><h3>2. Synthèse</h3><div id="res_kpi"></div></div>'
        '<div class="bloc"><h3>3. Soldes intermédiaires de gestion</h3><div id="res_sig"></div></div>'
        '<div class="bloc"><h3>4. Équilibre financier</h3><div id="res_eq"></div></div>'
        '<div class="bloc"><h3>5. Ratios</h3><div id="res_ratios"></div></div>'
        '<div class="bloc"><h3>6. Diagnostic</h3><div id="res_diag"></div></div>'
        f'<div class="bloc saisie"><h3>7. Hypothèses de valorisation</h3><div class="champs">{champs(VAL)}</div></div>'
        '<div class="bloc"><h3>8. Valorisation indicative</h3><div id="res_val"></div></div>'
        f'<script>{JS}</script>'
    )
    entete = ('<h1 class="site">Analyseur financier</h1>'
              '<p class="sous">Diagnostic et valorisation de votre entreprise, en ligne et gratuit</p>'
              '<div class="langues"><a href="index.html">Accueil</a><a href="programme.html">Programme</a></div>')
    (SORTIE / "analyseur.html").write_text(
        page("fr", "Analyseur financier · Le Bulletin Économique", entete, "", main,
             description="Outil gratuit : ratios, équilibre financier, diagnostic et valorisation indicative d'une entreprise."),
        encoding="utf-8")


def main():
    SORTIE.mkdir(exist_ok=True)
    bulletin.CSS = bulletin.CSS + CSS_ANALYSEUR
    construire()
    bulletin.enregistrer_rubrique("analyseur", "Analyseur financier",
                                  "outil en ligne : ratios, équilibre financier, diagnostic et valorisation de votre entreprise",
                                  "analyseur.html", "#364fc7")
    bulletin.construire_index()
    print("Publié : analyseur.html")


if __name__ == "__main__":
    main()
