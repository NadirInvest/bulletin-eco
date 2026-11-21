"""
Panneaux de MARCHÉ : indices, taux, matières premières, devises, métaux précieux (données différées).
Écrit docs/data/marches.json (lu par toutes les pages) et docs/data/historique.json (historique quotidien).
Sources gratuites :
  - FRED, Réserve fédérale de St. Louis (clé gratuite FRED_API_KEY) : indices US/Nikkei, pétrole, gaz, cuivre, taux
  - Exchange Rate API (open.er-api.com, sans clé) : devises
  - gold-api.com (sans clé, meilleur effort) : or, argent, platine, palladium
Chaque cours est indépendant : si une source tombe en panne, les autres s'affichent quand même.
"""
import json
import datetime
import requests
from email.utils import parsedate_to_datetime
import bulletin

GROUPES = [
    ("indices", "Indices boursiers"),
    ("taux", "Taux"),
    ("matieres", "Matières premières"),
    ("metaux", "Métaux précieux"),
    ("devises", "Devises"),
]

# id FRED, nom, pays/précision, unité, décimales, bourse (pour la pastille ouvert/fermé), groupe
FRED_SPECS = [
    ("SP500", "S&P 500", "États-Unis", "", 2, "NY", "indices"),
    ("NASDAQCOM", "Nasdaq Composite", "États-Unis", "", 2, "NY", "indices"),
    ("DJIA", "Dow Jones", "États-Unis", "", 2, "NY", "indices"),
    ("NIKKEI225", "Nikkei 225", "Japon", "", 2, "TYO", "indices"),
    ("VIXCLS", "VIX (volatilité)", "États-Unis", "", 2, None, "indices"),
    ("DGS10", "Taux US à 10 ans", "États-Unis", "%", 2, None, "taux"),
    ("DCOILBRENTEU", "Pétrole Brent", "$ le baril", "$", 2, None, "matieres"),
    ("DCOILWTICO", "Pétrole WTI", "$ le baril", "$", 2, None, "matieres"),
    ("DHHNGSP", "Gaz naturel", "$ le MMBtu", "$", 2, None, "matieres"),
    ("PCOPPUSDM", "Cuivre (mensuel)", "$ la tonne", "$", 0, None, "matieres"),
]

# nom, précision, formule à partir des taux contre le dollar (rates[X] = nombre de X pour 1 USD), décimales
FX_SPECS = [
    ("EURUSD", "EUR / USD", "Euro", lambda r: 1 / r["EUR"], 4),
    ("USDMAD", "USD / MAD", "Dirham", lambda r: r["MAD"], 4),
    ("EURMAD", "EUR / MAD", "Euro-dirham", lambda r: r["MAD"] / r["EUR"], 4),
    ("GBPUSD", "GBP / USD", "Livre", lambda r: 1 / r["GBP"], 4),
    ("USDJPY", "USD / JPY", "Yen", lambda r: r["JPY"], 2),
    ("USDCNY", "USD / CNY", "Yuan", lambda r: r["CNY"], 4),
    ("USDINR", "USD / INR", "Roupie", lambda r: r["INR"], 2),
    ("USDZAR", "USD / ZAR", "Rand", lambda r: r["ZAR"], 3),
    ("USDBRL", "USD / BRL", "Real", lambda r: r["BRL"], 3),
]

METAUX = [("XAU", "Or", "$ l'once"), ("XAG", "Argent", "$ l'once"),
          ("XPT", "Platine", "$ l'once"), ("XPD", "Palladium", "$ l'once")]

SOURCES_GROUPES = {
    "indices": "FRED (Réserve fédérale de St. Louis) : valeurs de clôture",
    "taux": "FRED : valeur de clôture",
    "matieres": "FRED : valeurs de clôture (cuivre : mensuel)",
    "metaux": "gold-api.com",
    "devises": "Exchange Rate API (taux quotidiens)",
}
SOURCES = ("Sources : FRED (Réserve fédérale de St. Louis), Exchange Rate API (exchangerate-api.com), gold-api.com. "
           "Données différées ou de clôture, à titre informatif.")


def data_dir():
    d = bulletin.SORTIE / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d


def charger_historique():
    chemin = data_dir() / "historique.json"
    try:
        return json.loads(chemin.read_text(encoding="utf-8"))
    except Exception:
        return {}


def avec_historique(base, valeur, hist, aujourd, date_obs=None):
    """Variation calculée à partir de notre propre historique quotidien (sources sans variation fournie)."""
    h = hist.setdefault(base["id"], {})
    h[aujourd] = valeur
    for jour in sorted(h)[:-40]:
        del h[jour]
    precedents = [j for j in sorted(h) if j < aujourd]
    pct = pts = 0.0
    if precedents:
        p = h[precedents[-1]]
        pct = (valeur / p - 1) * 100 if p else 0.0
        pts = valeur - p
    serie = [h[j] for j in sorted(h)][-14:]
    return {**base, "valeur": valeur, "variation_pct": pct, "variation_pts": pts, "date": date_obs or aujourd,
            "serie": serie if len(serie) >= 2 else []}


def fred(serie_id):
    cle = bulletin.secret("FRED_API_KEY")
    if not cle:
        raise RuntimeError("clé FRED_API_KEY absente")
    r = requests.get("https://api.stlouisfed.org/fred/series/observations", params={
        "series_id": serie_id, "api_key": cle, "file_type": "json", "sort_order": "desc", "limit": 40}, timeout=30)
    r.raise_for_status()
    points = []
    for o in r.json().get("observations", []):
        try:
            points.append((o["date"], float(o["value"])))
        except (ValueError, KeyError):
            continue
    points.reverse()
    return points[-14:]


def collecter_fred(groupes):
    for sid, nom, pays, unite, dec, bourse, groupe in FRED_SPECS:
        try:
            pts = fred(sid)
            if len(pts) < 2:
                raise ValueError("moins de 2 observations")
            (date, v), (_, p) = pts[-1], pts[-2]
            groupes[groupe].append({"id": sid, "nom": nom, "pays": pays, "unite": unite, "dec": dec, "bourse": bourse,
                                    "valeur": v, "variation_pct": (v / p - 1) * 100 if p else 0.0, "variation_pts": v - p,
                                    "date": date, "serie": [x[1] for x in pts]})
        except Exception as erreur:
            print(f"  FRED {sid} : {erreur}")


def collecter_devises(groupes, hist, aujourd):
    try:
        r = requests.get("https://open.er-api.com/v6/latest/USD", timeout=30)
        r.raise_for_status()
        donnees = r.json()
        taux = donnees["rates"]
        date_obs = None
        try:  # date de publication des taux par la source
            date_obs = parsedate_to_datetime(donnees.get("time_last_update_utc", "")).date().isoformat()
        except Exception:
            pass
    except Exception as erreur:
        print(f"  Devises : {erreur}")
        return
    for sid, nom, pays, formule, dec in FX_SPECS:
        try:
            base = {"id": sid, "nom": nom, "pays": pays, "unite": "", "dec": dec, "bourse": None}
            groupes["devises"].append(avec_historique(base, float(formule(taux)), hist, aujourd, date_obs))
        except Exception as erreur:
            print(f"  Devise {sid} : {erreur}")


def collecter_metaux(groupes, hist, aujourd):
    for symbole, nom, unite in METAUX:
        try:
            r = requests.get(f"https://api.gold-api.com/price/{symbole}", timeout=30)
            r.raise_for_status()
            donnees = r.json()
            prix = float(donnees["price"])
            date_obs = str(donnees.get("updatedAt", ""))[:10] or None
            base = {"id": symbole, "nom": nom, "pays": unite, "unite": "$", "dec": 2, "bourse": None}
            groupes["metaux"].append(avec_historique(base, prix, hist, aujourd, date_obs))
        except Exception as erreur:
            print(f"  Métal {symbole} : {erreur}")


def main():
    maintenant = datetime.datetime.now(datetime.timezone.utc)
    aujourd = maintenant.date().isoformat()
    hist = charger_historique()
    groupes = {cle: [] for cle, _ in GROUPES}
    collecter_fred(groupes)
    collecter_devises(groupes, hist, aujourd)
    collecter_metaux(groupes, hist, aujourd)
    total = sum(len(v) for v in groupes.values())
    for cle, items in groupes.items():
        print(f"{cle} : {len(items)} cours")
    if not total:
        raise SystemExit("Aucun cours n'a pu être récupéré.")
    sortie = {"maj": maintenant.isoformat(timespec="minutes"), "sources": SOURCES,
              "groupes": [{"cle": cle, "titre": titre, "source": SOURCES_GROUPES.get(cle, ""), "items": groupes[cle]}
                   for cle, titre in GROUPES if groupes[cle]]}
    (data_dir() / "marches.json").write_text(json.dumps(sortie, ensure_ascii=False), encoding="utf-8")
    (data_dir() / "historique.json").write_text(json.dumps(hist, ensure_ascii=False), encoding="utf-8")
    print("Publié : data/marches.json")


if __name__ == "__main__":
    main()
