"""
H2READY Toolkit - configurazione dei dati e generazione dei testi.

Questo è il file da modificare per lavorare sui CONTENUTI:
mappatura delle colonne, etichette, testi dei percorsi e dell'analisi incrociata.
"""

import os
import re
import unicodedata

import pandas as pd

# =============================================================================
# COLONNE CHIAVE
# =============================================================================

COL_ID = "ID_ISTAT"
COL_NOME = "NOME_COMUNE"
COL_MATURITA = "T11_LIVELLO_MATURITA"
COL_SCORE = {"A": "T12_SCORE_A", "B": "T12_SCORE_B", "C": "T12_SCORE_C"}

SOGLIE_MATURITA = [(3, 8, "L1"), (9, 14, "L2"), (15, 999, "L3")]
SOGLIA_MINIMA = 3

# La lettera dominante entra sempre; le altre entrano se raggiungono almeno
# QUOTA_SECONDARIA del punteggio massimo.
QUOTA_SECONDARIA = 0.80
PUNTEGGIO_MINIMO = 0.0

NOMI_PROFILO = {
    "A": "Consumo - la domanda locale traina la transizione",
    "B": "Produzione - il territorio può generare idrogeno rinnovabile",
    "C": "Transito - il Comune si colloca su direttrici logistiche rilevanti",
}

# =============================================================================
# STRUTTURA DEL PASSO 2
# =============================================================================

PERCORSI = [
    {
        "codice": "A",
        "titolo": "Percorso A - Domanda di idrogeno",
        "blocchi": [
            ("Domanda industriale (Tool 2.1)", [
                "T21_N_AZIENDE_IDONEE", "T21_NOMI_AZIENDE", "T21_FABBISOGNO_H2_TON_ANNO"]),
            ("Flotte e mobilità (Tool 2.2)", [
                "T22_N_VEICOLI_ANALIZZATI", "T22_ESITO_PREVALENTE", "T22_BEV_FATTIBILE",
                "T22_FABBISOGNO_H2_TON_ANNO", "T22_FABBISOGNO_ELETTRICO_MWH_ANNO",
                "T22_ENERGIA_ELETTROLISI_MWH_ANNO", "T22_DELTA_TCO_EURO",
                "T22_EMISSIONI_EVITATE_TCO2"]),
            ("Usi di nicchia (Tool 2.3)", [
                "T23_FLAG_RIFUGI", "T23_FLAG_MEZZI_CRITICI", "T23_FLAG_COLD_STORAGE",
                "T23_FLAG_TRENI", "T23_FLAG_PORTI_AEROPORTI", "T23_FLAG_DEPURATORI",
                "T23_RIFUGI_ELETTRICO_KWH", "T23_GASOLIO_FLOTTA_LITRI_ANNO",
                "T23_N_CARRELLI", "T23_POTENZA_CARRELLI_KW",
                "T23_TRATTA_NON_ELETTRIFICATA_KM", "T23_CORSE_GIORNALIERE",
                "T23_AERAZIONE_KWH_ANNO"]),
            ("Fabbisogno termico (Tool 2.4)", [
                "T24_FABBISOGNO_TERMICO_KWH_ANNO", "T24_SOLUZIONE_OTTIMALE",
                "T24_SOLUZIONE_PIU_PULITA", "T24_EMISSIONI_EVITATE_KGCO2_ANNO"]),
        ],
    },
    {
        "codice": "B",
        "titolo": "Percorso B - Offerta e produzione",
        "blocchi": [
            ("Rinnovabili e aree disponibili (Tool 2.5)", [
                "T25_FER_INSTALLATA_MW", "T25_SAU_OCCUPATA_PERC", "T25_PIPELINE_ISTANZE",
                "T25_PROGETTI_AUTORIZZATI", "T25_FLAG_CONTESTAZIONI", "T25_AREE_IDONEE_MQ",
                "T25_SUP_BROWNFIELD_MQ", "T25_SUP_TETTI_IND_MQ", "T25_SUP_TETTI_CIV_MQ",
                "T25_SUP_INCOLTE_MQ", "T25_SUP_SAU_MQ", "T25_SUP_SERVITU_MQ",
                "T25_DISTANZA_CABINA_PRIMARIA_KM", "T25_CAPACITA_RESIDUA_MW",
                "T25_ENTRO_5KM_DORSALE"]),
            ("Dimensionamento dell'impianto (Tool 2.6)", [
                "T26_MODALITA", "T26_ZONA", "T26_TARGET_H2_TON", "T26_PV_TERRA_MW",
                "T26_PV_TETTI_MW", "T26_PV_CAPANNONI_MW", "T26_EOLICO_MW",
                "T26_TAGLIA_FER_INSTALLATA_MW", "T26_TAGLIA_ELETTROLIZZATORE_MW",
                "T26_CAPACITA_BESS_MWH", "T26_PRODUZIONE_H2_TON_ANNO",
                "T26_QUOTA_RFNBO_PERC", "T26_CURTAILMENT_PERC", "T26_COPERTURA_PERC"]),
            ("Sostenibilità economica della produzione", [
                "T26_CAPEX_CONNESSIONI_EURO", "T26_CAPEX_TOTALE_MLN", "T26_LCOH_EURO_KG",
                "T26_PAYBACK_ANNI", "T26_CO2_EVITATA_TON_ANNO"]),
            ("Superfici impegnate", [
                "T26B_SUP_TERRA_HA", "T26B_SUP_TETTI_M2", "T26B_SUP_CAPANNONI_M2"]),
        ],
    },
    {
        "codice": "C",
        "titolo": "Percorso C - Transito e rifornimento",
        "blocchi": [
            ("Vocazione al transito (Tool 2.7)", [
                "T27_TGM_CAMION", "T27_DISTANZA_SNAM_KM", "T27_SCORE_C1", "T27_SCORE_C2",
                "T27_SCORE_C3", "T27_SCORE_GOV", "T27_FLAG_AREE_700BAR"]),
            ("Stazione di rifornimento (Tool 2.8)", [
                "T28_TAGLIA_HRS", "T28_CONFIGURAZIONE", "T28_CAPACITA_KG_GIORNO",
                "T28_N_DISPENSER", "T28_STRATEGIA_SUPPLY", "T28_POTENZA_COMPRESSORE_KW",
                "T28_AREA_MINIMA_MQ", "T28_CAPEX_COMPLESSIVO_EURO",
                "T28_BREAK_EVEN_EURO_KG", "T28_ORIZZONTE", "T28_QUOTA_FCEV_PERC"]),
        ],
    },
]

ESCLUSE = {"T11_MAIL", COL_ID, COL_NOME, COL_MATURITA,
           "T12_SCORE_A", "T12_SCORE_B", "T12_SCORE_C"}

FLAG_GOVERNANCE = ["T12_FLAG_PIANIFICAZIONE", "T12_FLAG_NAHV",
                   "T12_FLAG_JOINT_PROCUREMENT"]

# =============================================================================
# FORMATTAZIONE AUTOMATICA
# =============================================================================

SUFFISSI = [
    ("_KGCO2_ANNO", ("num", "kgCO2/anno")),
    ("_TON_ANNO", ("num", "t/anno")),
    ("_LITRI_ANNO", ("num", "litri/anno")),
    ("_MWH_ANNO", ("num", "MWh/anno")),
    ("_KWH_ANNO", ("num", "kWh/anno")),
    ("_EURO_KG", ("num", "Euro/kg")),
    ("_KG_GIORNO", ("num", "kg/giorno")),
    ("_CABINA_PRIMARIA_KM", ("num", "km")),
    ("_TCO2", ("num", "tCO2")),
    ("_EURO", ("eur", "")),
    ("_MLN", ("num", "mln Euro")),
    ("_PERC", ("pct", "")),
    ("_ANNI", ("num", "anni")),
    ("_MWH", ("num", "MWh")),
    ("_MW", ("num", "MW")),
    ("_KWH", ("num", "kWh")),
    ("_KW", ("num", "kW")),
    ("_KM", ("num", "km")),
    ("_MQ", ("num", "m\u00b2")),
    ("_M2", ("num", "m\u00b2")),
    ("_HA", ("num", "ha")),
    ("_TON", ("num", "t")),
]

ETICHETTE = {
    "T21_N_AZIENDE_IDONEE": "Aziende idonee individuate",
    "T21_NOMI_AZIENDE": "Aziende individuate",
    "T21_FABBISOGNO_H2_TON_ANNO": "Fabbisogno H2 del comparto produttivo",
    "T22_N_VEICOLI_ANALIZZATI": "Veicoli analizzati",
    "T22_ESITO_PREVALENTE": "Esito prevalente dell'analisi",
    "T22_BEV_FATTIBILE": "Alternativa elettrica a batteria praticabile",
    "T22_FABBISOGNO_H2_TON_ANNO": "Fabbisogno H2 della flotta",
    "T22_FABBISOGNO_ELETTRICO_MWH_ANNO": "Fabbisogno elettrico equivalente",
    "T22_ENERGIA_ELETTROLISI_MWH_ANNO": "Energia richiesta dall'elettrolisi",
    "T22_DELTA_TCO_EURO": "Differenziale di costo totale di possesso",
    "T22_EMISSIONI_EVITATE_TCO2": "Emissioni evitate",
    "T23_FLAG_RIFUGI": "Rifugi o utenze isolate",
    "T23_FLAG_MEZZI_CRITICI": "Mezzi critici o di emergenza",
    "T23_FLAG_COLD_STORAGE": "Celle frigorifere e logistica del freddo",
    "T23_FLAG_TRENI": "Trasporto ferroviario",
    "T23_FLAG_PORTI_AEROPORTI": "Porti o aeroporti",
    "T23_FLAG_DEPURATORI": "Impianti di depurazione",
    "T23_RIFUGI_ELETTRICO_KWH": "Consumo elettrico dei rifugi",
    "T23_GASOLIO_FLOTTA_LITRI_ANNO": "Gasolio consumato dalla flotta",
    "T23_N_CARRELLI": "Carrelli elevatori",
    "T23_TRATTA_NON_ELETTRIFICATA_KM": "Tratta ferroviaria non elettrificata",
    "T23_CORSE_GIORNALIERE": "Corse giornaliere",
    "T23_AERAZIONE_KWH_ANNO": "Consumo per aerazione depuratori",
    "T24_FABBISOGNO_TERMICO_KWH_ANNO": "Fabbisogno termico degli edifici",
    "T24_SOLUZIONE_OTTIMALE": "Soluzione ottimale individuata",
    "T24_SOLUZIONE_PIU_PULITA": "Soluzione a minori emissioni",
    "T25_FER_INSTALLATA_MW": "Rinnovabili già installate",
    "T25_SAU_OCCUPATA_PERC": "Superficie agricola già occupata da impianti",
    "T25_PIPELINE_ISTANZE": "Istanze in corso di istruttoria",
    "T25_PROGETTI_AUTORIZZATI": "Progetti già autorizzati",
    "T25_FLAG_CONTESTAZIONI": "Contenziosi o opposizioni in corso",
    "T25_AREE_IDONEE_MQ": "Aree idonee complessive",
    "T25_SUP_BROWNFIELD_MQ": "Aree dismesse",
    "T25_SUP_TETTI_IND_MQ": "Coperture industriali",
    "T25_SUP_TETTI_CIV_MQ": "Coperture civili",
    "T25_SUP_INCOLTE_MQ": "Superfici incolte",
    "T25_SUP_SAU_MQ": "Superficie agricola utilizzata",
    "T25_SUP_SERVITU_MQ": "Aree gravate da servitù",
    "T25_DISTANZA_CABINA_PRIMARIA_KM": "Distanza dalla cabina primaria",
    "T25_CAPACITA_RESIDUA_MW": "Capacità residua di rete",
    "T25_ENTRO_5KM_DORSALE": "Entro 5 km dalla dorsale",
    "T26_MODALITA": "Modalità di simulazione",
    "T26_ZONA": "Zona di riferimento",
    "T26_TARGET_H2_TON": "Obiettivo di produzione",
    "T26_PV_TERRA_MW": "Fotovoltaico a terra",
    "T26_PV_TETTI_MW": "Fotovoltaico su coperture",
    "T26_PV_CAPANNONI_MW": "Fotovoltaico su capannoni",
    "T26_EOLICO_MW": "Eolico",
    "T26_TAGLIA_FER_INSTALLATA_MW": "Potenza rinnovabile complessiva",
    "T26_TAGLIA_ELETTROLIZZATORE_MW": "Taglia dell'elettrolizzatore",
    "T26_CAPACITA_BESS_MWH": "Accumulo elettrochimico",
    "T26_PRODUZIONE_H2_TON_ANNO": "Produzione di idrogeno",
    "T26_QUOTA_RFNBO_PERC": "Quota conforme RFNBO",
    "T26_CURTAILMENT_PERC": "Energia non utilizzabile",
    "T26_COPERTURA_PERC": "Copertura del fabbisogno",
    "T26_CAPEX_CONNESSIONI_EURO": "Costo delle connessioni",
    "T26_CAPEX_TOTALE_MLN": "Investimento complessivo",
    "T26_LCOH_EURO_KG": "Costo livellato dell'idrogeno (LCOH)",
    "T26_PAYBACK_ANNI": "Tempo di ritorno",
    "T26_CO2_EVITATA_TON_ANNO": "CO2 evitata",
    "T26B_SUP_TERRA_HA": "Suolo agricolo impegnato",
    "T26B_SUP_TETTI_M2": "Coperture impegnate",
    "T26B_SUP_CAPANNONI_M2": "Capannoni impegnati",
    "T27_TGM_CAMION": "Traffico giornaliero medio di mezzi pesanti",
    "T27_DISTANZA_SNAM_KM": "Distanza dalla rete di trasporto gas",
    "T27_SCORE_C1": "Punteggio flussi di traffico",
    "T27_SCORE_C2": "Punteggio infrastrutture",
    "T27_SCORE_C3": "Punteggio contesto",
    "T27_SCORE_GOV": "Punteggio di governance",
    "T27_FLAG_AREE_700BAR": "Aree compatibili con rifornimento a 700 bar",
    "T28_TAGLIA_HRS": "Taglia della stazione",
    "T28_CONFIGURAZIONE": "Configurazione impiantistica",
    "T28_CAPACITA_KG_GIORNO": "Capacità di erogazione",
    "T28_N_DISPENSER": "Erogatori previsti",
    "T28_STRATEGIA_SUPPLY": "Strategia di approvvigionamento",
    "T28_POTENZA_COMPRESSORE_KW": "Potenza di compressione",
    "T28_AREA_MINIMA_MQ": "Area minima richiesta",
    "T28_CAPEX_COMPLESSIVO_EURO": "Investimento complessivo",
    "T28_BREAK_EVEN_EURO_KG": "Prezzo di pareggio alla pompa",
    "T28_ORIZZONTE": "Orizzonte temporale",
    "T28_QUOTA_FCEV_PERC": "Quota di veicoli a celle a combustibile",
    "T12_FLAG_PIANIFICAZIONE": "Idrogeno negli strumenti di pianificazione",
    "T12_FLAG_NAHV": "Adesione alla North Adriatic Hydrogen Valley",
    "T12_FLAG_JOINT_PROCUREMENT": "Disponibilità ad appalti congiunti",
}

# =============================================================================
# UTILITY
# =============================================================================

def is_vuoto(v) -> bool:
    if v is None:
        return True
    try:
        if pd.isna(v):
            return True
    except (TypeError, ValueError):
        pass
    return str(v).strip().lower() in ("", "nan", "none", "n/a", "-", "na", "null")


def numero(v):
    if is_vuoto(v):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(" ", "").replace("\u00a0", "")
    s = re.sub(r"[^\d,.\-]", "", s)
    if not s:
        return None
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def formatta_numero(n: float) -> str:
    if abs(n - round(n)) < 1e-9 and abs(n) < 1e15:
        return f"{int(round(n)):,}".replace(",", ".")
    return f"{n:,.2f}".replace(",", "@").replace(".", ",").replace("@", ".")


def tipo_e_unita(colonna: str):
    up = colonna.upper()
    if "FLAG" in up or up.endswith("_FATTIBILE") or up.startswith("T25_ENTRO"):
        return "si_no", ""
    for suf, (tipo, unita) in SUFFISSI:
        if up.endswith(suf):
            return tipo, unita
    if up.startswith(("T27_SCORE", "T12_SCORE")) or "_N_" in up:
        return "num", ""
    return "testo", ""


def etichetta(colonna: str) -> str:
    if colonna in ETICHETTE:
        return ETICHETTE[colonna]
    testo = re.sub(r"^T\d+[A-Z]?_", "", colonna)
    for suf, _ in SUFFISSI:
        if testo.upper().endswith(suf):
            testo = testo[: -len(suf)]
            break
    testo = testo.replace("_", " ").strip().lower()
    return testo[:1].upper() + testo[1:]


def formatta(valore, colonna: str):
    tipo, unita = tipo_e_unita(colonna)
    if is_vuoto(valore):
        return None
    if tipo == "si_no":
        s = str(valore).strip().lower()
        if s in ("si", "sì", "yes", "y", "true", "vero", "1", "1.0", "x"):
            return "Sì"
        if s in ("no", "n", "false", "falso", "0", "0.0"):
            return "No"
        return str(valore).strip()
    if tipo in ("num", "eur", "pct"):
        n = numero(valore)
        if n is None:
            return str(valore).strip()
        testo = formatta_numero(n)
        if tipo == "eur":
            return f"Euro {testo}"
        if tipo == "pct":
            return f"{testo}%"
        return f"{testo} {unita}".strip()
    return str(valore).strip()


def vero(valore) -> bool:
    return str(valore).strip().lower() in ("si", "sì", "yes", "true", "vero", "1", "1.0", "x")


def livello_maturita(score: int) -> str:
    for lo, hi, lab in SOGLIE_MATURITA:
        if lo <= score <= hi:
            return lab
    return "L1"


def calcola_profilo(riga):
    punteggi = {}
    for lettera, col in COL_SCORE.items():
        if col in riga.index:
            n = numero(riga[col])
            if n is not None:
                punteggi[lettera] = n
    if not punteggi:
        return "", {}
    massimo = max(punteggi.values())
    if massimo <= PUNTEGGIO_MINIMO:
        return "", punteggi
    lettere = [l for l in ("A", "B", "C")
               if punteggi.get(l, 0) >= massimo * QUOTA_SECONDARIA
               and punteggi.get(l, 0) > PUNTEGGIO_MINIMO]
    return "".join(lettere), punteggi


def slug(testo: str) -> str:
    s = unicodedata.normalize("NFKD", str(testo)).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")


def leggi_md(filename: str) -> str:
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            return f.read()
    return f"> *[Contenuto non disponibile: manca il file `{filename}`]*"


def totale(riga, colonne):
    valori = [numero(riga[c]) for c in colonne if c in riga.index]
    valori = [v for v in valori if v is not None]
    return sum(valori) if valori else None

# =============================================================================
# TESTI
# =============================================================================

def testo_profilo(profilo: str, punteggi: dict) -> str:
    out = ["## Profilo strategico identificato"]
    if punteggi:
        out += ["| Dimensione | Punteggio |", "| --- | --- |"]
        nomi = {"A": "A - Consumo", "B": "B - Produzione", "C": "C - Transito"}
        for l in ("A", "B", "C"):
            if l in punteggi:
                out.append(f"| {nomi[l]} | {formatta_numero(punteggi[l])} |")
        out.append("")
    if not profilo:
        out.append("> Punteggi non disponibili: il profilo non è stato determinato.")
        return "\n".join(out)
    out.append(f"Il Comune ricade nel **profilo {profilo}**, con le seguenti vocazioni:")
    out += [f"- **{l}** - {NOMI_PROFILO[l]}" for l in profilo]
    if len(profilo) > 1:
        out += ["", "La compresenza di più vocazioni indica un territorio in cui le azioni "
                "vanno coordinate fra loro: la scala e la sequenza degli interventi contano "
                "quanto la loro natura."]
    return "\n".join(out)


def testo_passo2(riga) -> str:
    out = ["# Sintesi dei risultati tecnici",
           "I valori derivano dai questionari e dagli strumenti di calcolo del Toolkit "
           "H2READY. I campi non compilati non compaiono nelle tabelle.", ""]
    conteggio = 0

    for percorso in PERCORSI:
        blocchi_pieni = []
        for titolo_blocco, colonne in percorso["blocchi"]:
            righe = []
            for col in colonne:
                if col not in riga.index or col in ESCLUSE:
                    continue
                valore = formatta(riga[col], col)
                if valore is None:
                    continue
                righe.append(f"| {etichetta(col)} | {valore} |")
            if righe:
                blocchi_pieni.append((titolo_blocco, righe))
        if not blocchi_pieni:
            continue

        out.append(f"## {percorso['titolo']}")
        commento = commento_percorso(riga, percorso["codice"])
        if commento:
            out += [commento, ""]
        for titolo_blocco, righe in blocchi_pieni:
            conteggio += len(righe)
            out.append(f"### {titolo_blocco}")
            out += ["| Parametro | Valore |", "| --- | --- |"] + righe + [""]

    previste = {c for p in PERCORSI for _, cols in p["blocchi"] for c in cols}
    altre = [c for c in riga.index
             if c not in ESCLUSE and c not in FLAG_GOVERNANCE and c not in previste
             and not is_vuoto(riga[c])]
    if altre:
        out.append("## Altri dati disponibili")
        out += ["| Parametro | Valore |", "| --- | --- |"]
        out += [f"| {etichetta(c)} | {formatta(riga[c], c)} |" for c in altre]
        out.append("")

    if conteggio == 0:
        out.append("> Nessun dato tecnico disponibile: verificare la compilazione dei "
                   "questionari per questo Comune.")
    return "\n".join(out)


def commento_percorso(riga, codice: str) -> str:
    """Lettura sintetica del singolo percorso, prima delle tabelle."""
    if codice == "A":
        dom = totale(riga, ["T21_FABBISOGNO_H2_TON_ANNO", "T22_FABBISOGNO_H2_TON_ANNO"])
        parti = []
        if dom:
            parti.append(f"La domanda potenziale complessiva ammonta a "
                         f"**{formatta_numero(dom)} t/anno** di idrogeno.")
        nicchie = [etichetta(c) for c in
                   ("T23_FLAG_RIFUGI", "T23_FLAG_MEZZI_CRITICI", "T23_FLAG_COLD_STORAGE",
                    "T23_FLAG_TRENI", "T23_FLAG_PORTI_AEROPORTI", "T23_FLAG_DEPURATORI")
                   if c in riga.index and vero(riga[c])]
        if nicchie:
            parti.append("Sono presenti usi di nicchia rilevanti: " +
                         ", ".join(n.lower() for n in nicchie) + ".")
        if riga.get("T22_BEV_FATTIBILE") is not None and vero(riga.get("T22_BEV_FATTIBILE")):
            parti.append("Per una parte della flotta l'alternativa elettrica a batteria "
                         "risulta praticabile: l'idrogeno va riservato ai segmenti in cui "
                         "autonomia, tempi di ricarica o carichi la rendono inadeguata.")
        return " ".join(parti)

    if codice == "B":
        prod = numero(riga.get("T26_PRODUZIONE_H2_TON_ANNO"))
        lcoh = numero(riga.get("T26_LCOH_EURO_KG"))
        parti = []
        if prod:
            parti.append(f"La configurazione simulata produrrebbe **{formatta_numero(prod)} "
                         "t/anno** di idrogeno.")
        if lcoh:
            parti.append(f"Il costo livellato risultante è di Euro {formatta_numero(lcoh)}/kg.")
        rfnbo = numero(riga.get("T26_QUOTA_RFNBO_PERC"))
        if rfnbo is not None:
            if rfnbo >= 90:
                parti.append("La quota conforme ai criteri RFNBO è elevata: l'idrogeno "
                             "prodotto può accedere ai regimi di sostegno dedicati.")
            else:
                parti.append(f"La quota conforme ai criteri RFNBO si ferma al "
                             f"{formatta_numero(rfnbo)}%: va verificata l'ammissibilità "
                             "agli incentivi che richiedono la certificazione.")
        return " ".join(parti)

    if codice == "C":
        tgm = numero(riga.get("T27_TGM_CAMION"))
        cap = numero(riga.get("T28_CAPACITA_KG_GIORNO"))
        parti = []
        if tgm:
            parti.append(f"Il traffico pesante rilevato è di **{formatta_numero(tgm)} "
                         "mezzi al giorno**.")
        if cap:
            parti.append(f"La stazione ipotizzata erogherebbe {formatta_numero(cap)} kg "
                         "al giorno.")
        return " ".join(parti)
    return ""


def testo_passo3(riga, livello, profilo) -> str:
    dedicato = f"5-incrocio_{livello}_{profilo}_it.md"
    if os.path.exists(dedicato):
        return leggi_md(dedicato)

    out = ["# Analisi incrociata",
           "Il confronto fra i risultati dei tre percorsi verifica la coerenza interna "
           "dello scenario e individua i punti su cui concentrare le decisioni.", ""]

    domanda = totale(riga, ["T21_FABBISOGNO_H2_TON_ANNO", "T22_FABBISOGNO_H2_TON_ANNO"])
    offerta = numero(riga.get("T26_PRODUZIONE_H2_TON_ANNO"))
    hrs_kg = numero(riga.get("T28_CAPACITA_KG_GIORNO"))
    hrs_t = hrs_kg * 365 / 1000 if hrs_kg else None

    if domanda is not None or offerta is not None:
        out.append("## Bilancio fra domanda e offerta")
        out += ["| Voce | Valore |", "| --- | --- |"]
        if domanda is not None:
            out.append(f"| Domanda complessiva stimata | {formatta_numero(domanda)} t/anno |")
        if offerta is not None:
            out.append(f"| Produzione locale potenziale | {formatta_numero(offerta)} t/anno |")
        if hrs_t is not None:
            out.append(f"| Capacità della stazione di rifornimento | {formatta_numero(hrs_t)} t/anno |")
        if domanda and offerta:
            out.append(f"| Saldo | {formatta_numero(offerta - domanda)} t/anno |")
            out.append(f"| Copertura della domanda | {formatta_numero(offerta / domanda * 100)}% |")
        out.append("")

        if domanda and offerta:
            cop = offerta / domanda * 100
            if cop >= 110:
                out.append("La produzione potenziale **eccede la domanda locale**. Il surplus "
                           "può alimentare utenze di Comuni limitrofi o il traffico di "
                           "transito, ma prima di dimensionare l'impianto sul massimo teorico "
                           "occorre verificare l'esistenza di contratti di acquisto.")
            elif cop >= 80:
                out.append("Domanda e produzione potenziale sono **sostanzialmente in "
                           "equilibrio**: è la condizione più favorevole per un progetto "
                           "autoconsistente su scala comunale.")
            else:
                out.append("La produzione locale **non copre la domanda stimata**. Vanno "
                           "valutate l'estensione del bacino di approvvigionamento, "
                           "l'aggregazione con Comuni vicini o una fornitura esterna nella "
                           "prima fase.")
            out.append("")

    lcoh = numero(riga.get("T26_LCOH_EURO_KG"))
    breakeven = numero(riga.get("T28_BREAK_EVEN_EURO_KG"))
    if lcoh is not None and breakeven is not None:
        out.append("## Coerenza economica della filiera")
        out += ["| Voce | Valore |", "| --- | --- |",
                f"| Costo di produzione (LCOH) | Euro {formatta_numero(lcoh)}/kg |",
                f"| Prezzo di pareggio alla pompa | Euro {formatta_numero(breakeven)}/kg |",
                f"| Margine lordo teorico | Euro {formatta_numero(breakeven - lcoh)}/kg |", ""]
        if breakeven > lcoh:
            out.append("Il prezzo di pareggio della stazione resta sopra il costo di "
                       "produzione: la filiera locale regge sul piano economico, a "
                       "condizione che i volumi previsti si realizzino.")
        else:
            out.append("Il costo di produzione supera il prezzo di pareggio: senza "
                       "contributo in conto capitale o senza un aumento dei volumi la "
                       "configurazione non è sostenibile.")
        out.append("")

    vincoli = []
    if vero(riga.get("T25_FLAG_CONTESTAZIONI")):
        vincoli.append("Sono presenti contenziosi o opposizioni su impianti rinnovabili: "
                       "il percorso partecipativo va avviato prima della progettazione.")
    cap_rete = numero(riga.get("T25_CAPACITA_RESIDUA_MW"))
    taglia = numero(riga.get("T26_TAGLIA_ELETTROLIZZATORE_MW"))
    if cap_rete is not None and taglia is not None and taglia > cap_rete:
        vincoli.append(f"La taglia dell'elettrolizzatore ({formatta_numero(taglia)} MW) supera "
                       f"la capacità residua di rete ({formatta_numero(cap_rete)} MW): serve un "
                       "confronto preventivo con il distributore.")
    sau = numero(riga.get("T25_SAU_OCCUPATA_PERC"))
    if sau is not None and sau > 10:
        vincoli.append(f"La superficie agricola già occupata da impianti "
                       f"({formatta_numero(sau)}%) suggerisce di privilegiare coperture e aree "
                       "dismesse rispetto al fotovoltaico a terra.")
    if vincoli:
        out.append("## Vincoli e attenzioni")
        out += [f"- {v}" for v in vincoli] + [""]

    gov = [(etichetta(c), formatta(riga[c], c)) for c in FLAG_GOVERNANCE
           if c in riga.index and formatta(riga[c], c)]
    if gov:
        out.append("## Contesto di governance")
        out += ["| Elemento | Stato |", "| --- | --- |"]
        out += [f"| {e} | {v} |" for e, v in gov] + [""]

    priorita = {
        "L1": "consolidare le basi conoscitive e amministrative prima di impegnare capitale",
        "L2": "trasformare gli studi disponibili in progetti cantierabili e finanziabili",
        "L3": "passare alla realizzazione e all'aggregazione della domanda su scala sovracomunale",
    }
    out += ["## Lettura d'insieme",
            f"Con un livello di maturità **{livello}** e un profilo "
            f"**{profilo or 'non determinato'}**, la priorità operativa è "
            f"{priorita.get(livello, priorita['L1'])}."]
    return "\n".join(out)


def testo_passo4(riga, livello, profilo) -> str:
    dedicato = f"6-finale_{livello}_{profilo}_it.md"
    if os.path.exists(dedicato):
        return leggi_md(dedicato)

    base = {
        "L1": [("0-6 mesi", "Nomina di un referente interno per la transizione energetica"),
               ("6-12 mesi", "Completamento del bilancio energetico comunale"),
               ("12-24 mesi", "Inserimento dell'idrogeno negli strumenti di pianificazione"),
               ("24-36 mesi", "Studio di prefattibilità sul primo caso d'uso")],
        "L2": [("0-6 mesi", "Selezione del caso d'uso prioritario e perimetro tecnico"),
               ("6-12 mesi", "Studio di fattibilità tecnico-economica"),
               ("12-24 mesi", "Individuazione dell'area e avvio dell'iter autorizzativo"),
               ("24-36 mesi", "Candidatura a bandi regionali, nazionali o europei")],
        "L3": [("0-6 mesi", "Definizione del modello di business e della governance"),
               ("6-12 mesi", "Progettazione definitiva e chiusura del piano finanziario"),
               ("12-24 mesi", "Gara e affidamento, anche in forma aggregata"),
               ("24-36 mesi", "Realizzazione, messa in esercizio e monitoraggio")],
    }
    specifiche = {
        "A": "Aggregare la domanda dei soggetti individuati in un contratto di acquisto "
             "pluriennale, condizione per rendere bancabile qualunque impianto.",
        "B": "Mettere in sicurezza la disponibilità delle aree e la connessione di rete "
             "prima di procedere con la progettazione dell'elettrolizzatore.",
        "C": "Verificare con il gestore stradale e con gli operatori del trasporto pesante "
             "i volumi effettivamente intercettabili dalla stazione di rifornimento.",
    }

    out = ["# Roadmap operativa su misura",
           f"Percorso proposto per il Comune di **{riga[COL_NOME]}** "
           f"(livello {livello}, profilo {profilo or 'n.d.'}).", "",
           "## Cronoprogramma indicativo",
           "| Orizzonte | Azione |", "| --- | --- |"]
    out += [f"| {t} | {a} |" for t, a in base.get(livello, base["L1"])] + [""]

    if profilo:
        out.append("## Azioni specifiche del profilo")
        out += [f"- **Vocazione {l}**: {specifiche[l]}" for l in profilo if l in specifiche]
        out.append("")

    out += ["## Fattori abilitanti",
            "- **Competenze**: formazione del personale tecnico nel programma H2READY.",
            "- **Risorse**: capacità di cofinanziamento e ricorso alla finanza agevolata.",
            "- **Partenariato**: utility, trasporto pubblico locale, imprese del territorio.",
            "",
            "## Indicatori di monitoraggio",
            "| Indicatore | Unità |", "| --- | --- |",
            "| Idrogeno consumato sul territorio | t/anno |",
            "| Emissioni evitate | tCO2/anno |",
            "| Quota rinnovabile dell'idrogeno impiegato | % |",
            "| Investimento attivato | Euro |",
            "",
            "> Il presente Action Plan è un documento vivo: va aggiornato a ogni variazione "
            "rilevante del quadro normativo, tecnologico o finanziario."]
    return "\n".join(out)


def costruisci_contenuti(riga, livello, profilo, punteggi) -> dict:
    profilo_file = f"4-profilo_{profilo}_it.md" if profilo else ""
    return {
        "livello": livello,
        "profilo": profilo,
        "comune": str(riga[COL_NOME]),
        "intro": leggi_md("1-intro_it.md"),
        "struttura": leggi_md("2-struttura_plan_it.md"),
        "mat_intro": leggi_md("3-maturita_intro_it.md"),
        "mat_dettaglio": leggi_md(f"3-maturita_{livello}_it.md"),
        "profilo_intro": leggi_md("4-profilo_intro_it.md"),
        "profilo_calcolato": testo_profilo(profilo, punteggi),
        "profilo_dettaglio": leggi_md(profilo_file) if profilo else "",
        "passo2": testo_passo2(riga),
        "passo3": testo_passo3(riga, livello, profilo),
        "passo4": testo_passo4(riga, livello, profilo),
    }


def file_attesi(livello, profilo):
    attesi = ["1-intro_it.md", "2-struttura_plan_it.md", "3-maturita_intro_it.md",
              f"3-maturita_{livello}_it.md", "4-profilo_intro_it.md"]
    if profilo:
        attesi.append(f"4-profilo_{profilo}_it.md")
    return attesi

def genera_sezione_hta(riga_comune, df_aziende):
    """
    Genera il testo dinamico in Markdown per la Sezione 2.1 (HTA & RED III)
    riga_comune: la riga del foglio Google con le info generali del Comune
    df_aziende: il DataFrame con le aziende filtrate per quel codice ISTAT
    """
    
    # 1. PARTE TEORICA STATICA (Trattato HTA e RED III)
    testo_introduttivo = """
### 🏭 2.1 Mappatura della Domanda Industriale "Hard-to-Abate" e Normativa RED III

#### Perché l'Idrogeno nei Settori "Hard-to-Abate" (HTA)?
La transizione ecologica impone una gerarchia di intervento basata sulle leggi della termodinamica: laddove l'elettrificazione diretta è possibile (tramite pompe di calore, resistenze o induzione), essa rappresenta sempre la strada più efficiente e conveniente. Tuttavia, esistono comparti industriali definiti **Hard-to-Abate (HTA)** — come la siderurgia, la chimica, le raffinerie, le vetrerie e i cementifici — in cui l'elettrificazione incontra limiti fisici o chimici insuperabili:

* **Requisiti di materia prima chimica (*feedstock*):** In settori come la chimica dei fertilizzanti o la raffinazione, la molecola di idrogeno partecipa direttamente alle reazioni chimiche (es. agente riducente per la fabbricazione dell'acciaio DRI o per la sintesi dell'ammoniaca). L'elettricità non può sostituire una molecola.
* **Calore ad altissima temperatura (>800 - 1500°C):** Nei grandi forni fusori per il vetro o per la calcinazione del clinker, la densità di potenza richiesta e le caratteristiche della fiamma rendono l'elettrificazione totale complessa o rischiosa per gli impianti.
* **Competitività e Meccanismo CBAM:** Per queste industrie, sostituire i combustibili fossili con l'idrogeno verde è essenziale per evitare le sanzioni del meccanismo europeo di addebitamento del carbonio alle frontiere (CBAM).

#### Il Quadro Normativo RED III e gli Obblighi per l'Industria
La Direttiva Europea sulla Promozione delle Energie Rinnovabili (**RED III**) introduce un vincolo di svolta: entro il 2030, almeno il **42% dell'idrogeno utilizzato nell'industria** dovrà provenire da fonti rinnovabili di origine non biologica (**RFNBO**), quota che salirà al **60% entro il 2035**. Le aziende HTA presenti sul territorio non avranno la facoltà di scegliere se decarbonizzare: per legge dovranno sostituire l'idrogeno grigio/fossile con idrogeno verde RFNBO.
"""

    # 2. CONTROLLO PRESENZA AZIENDE E CALCOLI DINAMICI
    if df_aziende.empty or df_aziende['fabbisogno_ton'].sum() == 0:
        testo_dinamico = """
#### Analisi del Territorio Comunale
Lo screening condotto sul tessuto industriale locale tramite il **Tool 2.1** non ha rilevato la presenza di impianti classificabili nei settori prioritari *Hard-to-Abate*. Ne consegue che sul territorio comunale non sussiste attualmente una domanda industriale diretta in grado di giustificare la realizzazione di infrastrutture dedicate all'idrogeno ad uso di processo. La strategia comunale dovrà prioritariamente orientarsi verso l'elettrificazione diretta delle utenze termiche a bassa e media temperatura e verso l'efficienza energetica.
"""
        return testo_introduttivo + testo_dinamico

    # Se ci sono aziende, facciamo i calcoli fisici
    totale_h2_ton = df_aziende['fabbisogno_ton'].sum()
    n_aziende = len(df_aziende[df_aziende['fabbisogno_ton'] > 0])
    
    # Formula fisica: 1 kg H2 = 52 kWh el. -> 1 ton H2 = 52 MWh
    mwh_elettrici_req = totale_h2_ton * 52
    mwp_pv_req = mwh_elettrici_req / 1300  # 1300 MWh/MWp resa media Nord Italia
    ettari_pv_req = mwp_pv_req * 1.3       # 1.3 ettari per MWp a terra
    campi_calcio = int((ettari_pv_req * 10000) / 7140)

    # Costruzione della tabella delle aziende in Markdown
    righe_tabella = []
    for _, az in df_aziende.iterrows():
        if az['fabbisogno_ton'] > 0:
            righe_tabella.append(
                f"| **{az['nome']}** | `{az['ateco']}` | {az['desc_processo']} | {az['verdetto']} | {az['fabbisogno_ton']:,.1f} t/anno |"
            )
    tabella_md = "\n".join(righe_tabella)

    testo_dinamico = f"""
#### Mappatura delle Utenze e Fabbisogni Rilevati (Tool 2.1)
Attraverso lo screening condotto sul territorio comunale, sono state individuate **{n_aziende} aziende idonee** che esprimono una domanda industriale complessiva di **{totale_h2_ton:,.1f} tonnellate/anno di idrogeno verde**.

| Nome Azienda | Codice ATECO | Descrizione Processo & Temperatura | Verdetto Termodinamico | Fabbisogno Stimato |
| :--- | :--- | :--- | :--- | :--- |
{tabella_md}

#### Considerazioni di Scala: "Reality Check" Territoriale
Per comprendere l'impatto fisico e urbanistico di questa domanda, è necessario tradurre le tonnellate di idrogeno nel fabbisogno di energia elettrica e suolo necessari per produrlo in loco:

* **Energia Elettrica Richiesta:** Produrre **{totale_h2_ton:,.1f} t/anno** di H₂ (considerando un consumo specifico dell'elettrolisi di $52 \\text{{ kWh/kg}}$) richiede circa **{mwh_elettrici_req:,.0f} MWh/anno** ({mwh_elettrici_req/1000:,.1f} GWh/anno) di elettricità 100% rinnovabile.
* **Potenza Fotovoltaica Equivalente:** Se alimentato a fotovoltaico a terra, servirebbe un impianto dedicato di potenza pari a **{mwp_pv_req:,.1f} MWp**.
* **Occupazione di Suolo:** Un parco fotovoltaico di questa taglia richiederebbe circa **{ettari_pv_req:,.0f} ettari di terreno** (pari a circa **{campi_calcio} campi da calcio**).

> **💡 Implicazione Strategica per l'Amministrazione:** > L'estensione di suolo richiesta dimostra che il Comune non potrà coprire l'intero fabbisogno industriale con la sola produzione solare locale a chilometro zero. La strategia comunale dovrà quindi combinare la generazione locale su tetti/brownfield con l'importazione di molecole da reti di trasporto sovracomunali (*SoutH2 Corridor* / dorsali Snam).
"""

    return testo_introduttivo + testo_dinamico
