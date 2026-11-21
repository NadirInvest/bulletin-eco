"""
INDICATEURS MACROÉCONOMIQUES : croissance, inflation, chômage, dette publique, solde budgétaire, PIB.
Source : FMI, Perspectives de l'économie mondiale, via l'interface publique DataMapper (gratuite, sans clé).
Écrit docs/data/macro.json (bandeau défilant en haut de toutes les pages) et docs/macro.html (tableau de bord).
Aucun appel à l'IA. Les chiffres de l'année en cours sont des estimations ou des prévisions du FMI.
"""
import json
import datetime
import requests
import bulletin
import rubrique_fiscalite as rf
from bulletin import e, page

SORTIE = bulletin.SORTIE
SOURCE = "FMI, Perspectives de l'économie mondiale (DataMapper)"
URL = "https://www.imf.org/external/datamapper/api/v1/{ind}"

# code FMI, clé interne
INDICATEURS = [("NGDP_RPCH", "croissance"), ("PCPIPCH", "inflation"), ("LUR", "chomage"),
               ("GGXWDG_NGDP", "dette"), ("GGXCNL_NGDP", "solde"), ("BCA_NGDPD", "compte"), ("NGDPD", "pib")]
# Balance commerciale (biens et services, % du PIB) : Banque mondiale, dernière année disponible
WB_COMMERCE = "NE.RSB.GNFS.ZS"
PAYS = {"WEOWORLD": "Monde", **rf.PAYS}

EXTRA_CSS = """
table.mac{width:100%;border-collapse:collapse;font-size:.9rem}
table.mac th,table.mac td{padding:9px 8px;border-bottom:1px solid var(--bord);text-align:end;white-space:nowrap}
table.mac th:first-child,table.mac td:first-child{text-align:start;position:sticky;inset-inline-start:0;background:var(--carte)}
table.mac th{cursor:pointer;font-size:.78rem;text-transform:uppercase;letter-spacing:.04em;color:var(--doux)}
table.mac td.ok{color:var(--hausse);font-weight:600}table.mac td.warn{color:#c77700;font-weight:600}table.mac td.bad{color:var(--baisse);font-weight:600}
.scroll{overflow-x:auto}
.an{color:var(--doux);font-size:.68rem;font-weight:400}
.note{font-size:.82rem;color:var(--doux)}
.kg{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:10px;margin:8px 0 18px}
.kc{background:var(--carte);border:1px solid var(--bord);border-radius:12px;padding:12px 14px}
.kc small{display:block;color:var(--doux);font-size:.76rem}.kc b{display:block;font-size:1.3rem}
"""
bulletin.CSS = bulletin.CSS + EXTRA_CSS


def fetch(indicateur, annees):
    r = requests.get(URL.format(ind=indicateur), params={"periods": ",".join(str(a) for a in annees)}, timeout=60)
    r.raise_for_status()
    return r.json().get("values", {}).get(indicateur, {})


def choisir(serie, annee):
    """Valeur de l'année en cours si elle existe, sinon la plus récente disponible avant."""
    for a in (annee, annee - 1, annee - 2):
        v = serie.get(str(a))
        if isinstance(v, (int, float)):
            return {"v": float(v), "a": a}
    return None


def fetch_commerce():
    """Balance commerciale (% du PIB) : dernière valeur disponible par pays (Banque mondiale)."""
    isos = ";".join(i for i in PAYS if i != "WEOWORLD")
    r = requests.get(f"https://api.worldbank.org/v2/country/{isos}/indicator/{WB_COMMERCE}",
                     params={"format": "json", "per_page": 3000, "date": "2018:2026"}, timeout=60)
    r.raise_for_status()
    donnees = r.json()
    dernier = {}
    if isinstance(donnees, list) and len(donnees) > 1 and donnees[1]:
        for o in donnees[1]:
            if o.get("value") is None:
                continue
            iso, a = o.get("countryiso3code"), int(o["date"])
            if iso and (iso not in dernier or a > dernier[iso]["a"]):
                dernier[iso] = {"v": float(o["value"]), "a": a}
    return dernier


def signe(v, d=1):
    return ("+" if v > 0 else "") + fmt(v, d)


def segments(l):
    """Textes prêts à afficher dans le bandeau. L'année de chaque donnée est indiquée : celle du pays en titre,
    et entre parenthèses uniquement pour les données d'une autre année."""
    cles = ["croissance", "inflation", "chomage", "dette", "solde", "commerce"]
    annees = [l[k]["a"] for k in cles if k in l]
    base = max(set(annees), key=annees.count) if annees else None
    l["libelle"] = f"{l['nom']} ({base})" if base else l["nom"]

    def an(k):
        return f" ({l[k]['a']})" if base and l[k]["a"] != base else ""

    seg = []
    if "croissance" in l:
        seg.append({"t": f"Croissance {signe(l['croissance']['v'])} %{an('croissance')}", "c": "up" if l["croissance"]["v"] >= 0 else "down"})
    if "inflation" in l:
        seg.append({"t": f"Inflation {fmt(l['inflation']['v'])} %{an('inflation')}", "c": ""})
    if "chomage" in l:
        seg.append({"t": f"Chômage {fmt(l['chomage']['v'])} %{an('chomage')}", "c": ""})
    if "dette" in l:
        seg.append({"t": f"Dette publique {fmt(l['dette']['v'], 0)} % du PIB{an('dette')}", "c": ""})
    if "solde" in l:
        seg.append({"t": f"Solde budgétaire {signe(l['solde']['v'])} % du PIB{an('solde')}", "c": "up" if l["solde"]["v"] >= 0 else "down"})
    if "commerce" in l:
        seg.append({"t": f"Balance commerciale {signe(l['commerce']['v'])} % du PIB{an('commerce')}",
                    "c": "up" if l["commerce"]["v"] >= 0 else "down"})
    return seg


def charger_anciens():
    """Dernières valeurs publiées : elles sont conservées si une source ne répond pas lors d'une mise à jour."""
    try:
        d = json.loads((SORTIE / "data" / "macro.json").read_text(encoding="utf-8"))
        return {l["iso"]: l for l in d.get("lignes", [])}
    except Exception:
        return {}


def collecter(annee):
    donnees = {iso: {"iso": iso, "nom": nom} for iso, nom in PAYS.items()}
    for code, cle in INDICATEURS:
        try:
            valeurs = fetch(code, [annee - 2, annee - 1, annee])
        except Exception as erreur:
            print(f"  FMI {code} : {erreur}")
            continue
        trouves = 0
        for iso in PAYS:
            choix = choisir(valeurs.get(iso, {}), annee)
            if choix:
                donnees[iso][cle] = choix
                trouves += 1
        print(f"  {cle} : {trouves} pays")
    try:
        for iso, valeur in fetch_commerce().items():
            if iso in donnees:
                donnees[iso]["commerce"] = valeur
        print(f"  commerce : {sum('commerce' in d for d in donnees.values())} pays")
    except Exception as erreur:
        print(f"  Banque mondiale (balance commerciale) : {erreur}")
    anciens = charger_anciens()
    conserves = 0
    for iso, d in donnees.items():
        for cle in [k for _, k in INDICATEURS] + ["commerce"]:
            if cle not in d and cle in anciens.get(iso, {}):
                d[cle] = anciens[iso][cle]  # source muette : on garde la dernière valeur connue
                conserves += 1
    if conserves:
        print(f"  {conserves} valeur(s) conservée(s) de la mise à jour précédente (source indisponible)")
    lignes = [d for d in donnees.values() if any(k in d for _, k in INDICATEURS) or "commerce" in d]
    for l in lignes:
        l["segments"] = segments(l)
    return lignes


def classe(cle, v):
    seuils = {"croissance": (3, 1, False), "inflation": (3, 8, True), "chomage": (6, 12, True),
              "dette": (60, 90, True), "solde": (-3, -6, False), "commerce": (0, -5, False), "compte": (0, -4, False)}
    if cle not in seuils:
        return ""
    ok, warn, inverse = seuils[cle]
    if inverse:
        return "ok" if v <= ok else ("warn" if v <= warn else "bad")
    return "ok" if v >= ok else ("warn" if v >= warn else "bad")


def fmt(v, d=1):
    return f"{v:,.{d}f}".replace(",", " ").replace(".", ",")


def cellule(l, cle, d=1, signe=False, suffixe=" %"):
    x = l.get(cle)
    if not x:
        return '<td data-v="-1e9">n.d.</td>'
    txt = (("+" if signe and x["v"] > 0 else "") + fmt(x["v"], d)) + suffixe
    return f'<td class="{classe(cle, x["v"])}" data-v="{x["v"]}">{txt} <small class="an">{x["a"]}</small></td>'


def construire(lignes, annee):
    monde = next((l for l in lignes if l["iso"] == "WEOWORLD"), None)
    kpis = ""
    if monde:
        for cle, titre, suf, signe in (("croissance", "Croissance mondiale", " %", True), ("inflation", "Inflation mondiale", " %", False)):
            if cle in monde:
                kpis += f'<div class="kc"><small>{titre} ({monde[cle]["a"]})</small><b>{("+" if signe and monde[cle]["v"] > 0 else "") + fmt(monde[cle]["v"])}{suf}</b></div>'
    corps = ""
    for l in sorted(lignes, key=lambda x: (x["iso"] != "WEOWORLD", x["nom"])):
        pib = l.get("pib")
        pib_txt = f'<td data-v="{pib["v"]}">{fmt(pib["v"], 0)}</td>' if pib else '<td data-v="-1e9">n.d.</td>'
        corps += (f'<tr><td><b>{e(l["nom"])}</b></td>{pib_txt}{cellule(l, "croissance", 1, True)}{cellule(l, "inflation")}'
                  f'{cellule(l, "chomage")}{cellule(l, "dette", 0)}{cellule(l, "solde", 1, True)}'
                  f'{cellule(l, "commerce", 1, True)}{cellule(l, "compte", 1, True)}</tr>')
    script = ("<script>document.querySelectorAll('table.mac th').forEach(function(th,i){var asc=false;th.addEventListener('click',function(){"
              "var tb=th.closest('table').tBodies[0],rows=Array.prototype.slice.call(tb.rows);asc=!asc;"
              "rows.sort(function(a,b){if(i===0){return asc?a.cells[0].textContent.localeCompare(b.cells[0].textContent):b.cells[0].textContent.localeCompare(a.cells[0].textContent)}"
              "var x=parseFloat(a.cells[i].dataset.v),y=parseFloat(b.cells[i].dataset.v);return asc?x-y:y-x});"
              "rows.forEach(function(r){tb.appendChild(r)})})})</script>")
    main = (
        '<span class="tag" style="--c:#f08c00">Indicateurs</span>'
        '<h2 style="font-size:1.7rem;line-height:1.3;margin:.5rem 0">Le monde en chiffres</h2>'
        f'<p class="chapeau">Croissance, inflation, chômage, dette publique et solde budgétaire : les grands indicateurs de {len(lignes) - 1} pays, comparés en un coup d\'œil.</p>'
        f'<div class="kg">{kpis}</div>'
        '<div class="bloc"><div class="scroll"><table class="mac"><thead><tr><th>Pays</th><th>PIB (Md $)</th><th>Croissance</th>'
        '<th>Inflation</th><th>Chômage</th><th>Dette publique (% PIB)</th><th>Solde budgétaire (% PIB)</th>'
        '<th>Balance commerciale (% PIB)</th><th>Compte courant (% PIB)</th></tr></thead>'
        f'<tbody>{corps}</tbody></table></div>'
        '<p class="note">Touchez un titre de colonne pour trier. Couleurs indicatives : '
        'vert = niveau confortable, orange = vigilance, rouge = niveau préoccupant (repères usuels : inflation au plus 3 %, '
        'dette au plus 60 % du PIB, déficit au plus 3 % du PIB).</p></div>'
        '<div class="bloc"><h3>Comment lire ces chiffres</h3><ul>'
        '<li><b>Croissance</b> : variation annuelle du PIB réel (hors inflation).</li>'
        '<li><b>Inflation</b> : hausse annuelle moyenne des prix à la consommation.</li>'
        '<li><b>Chômage</b> : part des actifs sans emploi (non disponible pour tous les pays).</li>'
        '<li><b>Dette publique</b> : dette brute des administrations publiques, en pourcentage du PIB.</li>'
        '<li><b>Solde budgétaire</b> : excédent (+) ou déficit (-) des administrations publiques, en pourcentage du PIB.</li>'
        '<li><b>Balance commerciale</b> : exportations moins importations de biens et de services, en pourcentage du PIB ; positive, c\'est un excédent, négative un déficit.</li>'
        '<li><b>Compte courant</b> : solde des échanges de biens, de services, de revenus et de transferts avec le reste du monde, en pourcentage du PIB.</li></ul>'
        f'<p class="note">Sources : {e(SOURCE)} ; Banque mondiale pour la balance commerciale. '
        'Chaque valeur correspond à la dernière année disponible chez la source : l\'année est indiquée à côté de la valeur. '
        'Les données les plus récentes peuvent être des estimations, révisées régulièrement. Données à titre informatif.</p></div>'
        + script
    )
    entete = ('<h1 class="site">Indicateurs</h1><p class="sous">Les chiffres clés de l\'économie mondiale et de chaque pays</p>'
              '<div class="langues"><a href="index.html">Accueil</a><a href="programme.html">Programme</a></div>')
    (SORTIE / "macro.html").write_text(
        page("fr", "Indicateurs macroéconomiques · Le Bulletin Économique", entete, "", main,
             description="Croissance, inflation, chômage, dette publique et solde budgétaire par pays, d'après le FMI."),
        encoding="utf-8")


def main():
    annee = datetime.date.today().year
    lignes = collecter(annee)
    if len(lignes) < 3:
        raise SystemExit("Données du FMI indisponibles.")
    data = SORTIE / "data"
    data.mkdir(parents=True, exist_ok=True)
    sortie = {"maj": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="minutes"), "annee": annee,
              "source": SOURCE, "lignes": sorted(lignes, key=lambda x: (x["iso"] != "WEOWORLD", x["nom"]))}
    (data / "macro.json").write_text(json.dumps(sortie, ensure_ascii=False), encoding="utf-8")
    construire(lignes, annee)
    bulletin.enregistrer_rubrique("macro", "Indicateurs", "les chiffres clés de l'économie mondiale et de chaque pays",
                                  "macro.html", "#f08c00")
    bulletin.construire_index()
    print(f"Publié : data/macro.json et macro.html ({len(lignes)} lignes)")


if __name__ == "__main__":
    main()
