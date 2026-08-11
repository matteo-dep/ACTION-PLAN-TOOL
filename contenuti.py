"""
H2READY Toolkit - configurazione dei dati e generazione dei testi.

Questo è il file da modificare per lavorare sui CONTENUTI:
mappatura delle colonne, etichette, testi dei percorsi e dell'analisi incrociata.
"""

import os
import re
import unicodedata

import pandas as pd

import ateco as AT

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

# -----------------------------------------------------------------------------
# PARAMETRI DI RIFERIMENTO DEL PERCORSO A
# Fonte: "Modelli di Business per l'utilizzo dell'H2 e lo sviluppo della Filiera
# in Italia" (2024) e "Camion a idrogeno" (Roland Berger, 2021).
# Sono i valori su cui si tarano i giudizi qualitativi: modificarli qui.
# -----------------------------------------------------------------------------

# Flotta minima ritenuta sostenibile: 10 bus x 26 kg/giorno x 300 giorni ~ 78 t/anno
SOGLIA_MASSA_CRITICA_TON = 78.0
# Sotto questa soglia la domanda è troppo frammentata per un progetto autonomo
SOGLIA_DOMANDA_MINIMA_TON = 25.0

CONSUMO_BUS_KG_GIORNO = 26.0        # bus urbano da 12 m, 250 km/giorno
GIORNI_OPERATIVI = 300              # giorni di servizio in un anno
EFFICIENZA_H2_KM_KG = 11.4          # mezzo pesante stradale
EFFICIENZA_DIESEL_KM_LITRO = 3.5    # mezzo pesante stradale
EMISSIONI_DIESEL_KG_LITRO = 2.7     # kgCO2 per litro di gasolio

# 1 kg di H2 sostituisce EFFICIENZA_H2_KM_KG / EFFICIENZA_DIESEL_KM_LITRO litri
LITRI_DIESEL_PER_KG_H2 = EFFICIENZA_H2_KM_KG / EFFICIENZA_DIESEL_KM_LITRO
CO2_EVITATA_KG_PER_KG_H2 = LITRI_DIESEL_PER_KG_H2 * EMISSIONI_DIESEL_KG_LITRO

# Reality check: quanta energia e quanto suolo serve per produrre l'idrogeno
CONSUMO_ELETTROLISI_KWH_KG = 52.0   # consumo specifico di sistema
RESA_PV_KWH_KWP = 1250.0            # producibilità media in Friuli Venezia Giulia
SUPERFICIE_PV_HA_MWP = 1.3          # fotovoltaico a terra
SUPERFICIE_CAMPO_CALCIO_MQ = 7140.0

NICCHIE = {
    "T23_FLAG_RIFUGI":
        "rifugi e utenze isolate, dove l'idrogeno compete con il generatore diesel "
        "e con la logistica di rifornimento in quota",
    "T23_FLAG_MEZZI_CRITICI":
        "mezzi di emergenza e protezione civile, per i quali la continuità operativa "
        "conta più del costo del carburante",
    "T23_FLAG_COLD_STORAGE":
        "logistica del freddo e movimentazione in magazzino, dove i carrelli a celle a "
        "combustibile evitano la sostituzione delle batterie fra i turni",
    "T23_FLAG_TRENI":
        "trasporto ferroviario su tratte non elettrificate, alternativa all'elettrificazione "
        "quando i volumi di traffico non la giustificano",
    "T23_FLAG_PORTI_AEROPORTI":
        "movimentazione portuale o aeroportuale, con mezzi a ciclo continuo e rifornimento "
        "concentrato in pochi punti",
    "T23_FLAG_DEPURATORI":
        "impianti di depurazione, dove il consumo per aerazione è costante e prevedibile "
        "e può essere accoppiato a produzione locale",
}

# =============================================================================
# STRUTTURA DEL PASSO 2
# =============================================================================

PERCORSI = [
    {
        "codice": "A",
        "titolo": "Percorso A - Domanda di idrogeno",
        "blocchi": [
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

# T21_*: già trattate per esteso nella sezione 2.1, non si ripetono in tabella
ESCLUSE = {"T11_MAIL", COL_ID, COL_NOME, COL_MATURITA,
           "T12_SCORE_A", "T12_SCORE_B", "T12_SCORE_C",
           "T21_N_AZIENDE_IDONEE", "T21_NOMI_AZIENDE", "T21_FABBISOGNO_H2_TON_ANNO",
           "T21_ATECO_AZIENDE", "T21_FABBISOGNI_AZIENDE"}

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
            return ripulisci_md(f.read())
    return f"> *[Contenuto non disponibile: manca il file `{filename}`]*"


def ripulisci_md(testo: str) -> str:
    """Toglie dai .md i residui di esportazione: marcatori di citazione e LaTeX."""
    testo = re.sub(r"\[cite_start\]", "", testo)
    testo = re.sub(r"\[cite:[^\]]*\]", "", testo)
    testo = re.sub(r"\$+\\?text\{([^}]*)\}\$*", r"\1", testo)
    testo = re.sub(r"\$([^$]*)\$", r"\1", testo)
    testo = re.sub(r"[ \t]+([.,;:])", r"\1", testo)
    return testo.strip()


def applica_valori(testo: str, valori: dict) -> str:
    """Sostituisce i segnaposto {nome} con i valori calcolati.

    I segnaposto non previsti restano nel testo, così un refuso in un .md si vede
    subito nel documento invece di far fallire la generazione.
    """
    def sostituisci(match):
        chiave = match.group(1).strip()
        if chiave in valori:
            return str(valori[chiave])
        return match.group(0)
    return re.sub(r"\{([A-Za-z0-9_]+)\}", sostituisci, testo)


def testo_da_template(filename: str, valori: dict, predefinito: str = "") -> str:
    """Carica un .md e ne compila i segnaposto; se manca usa il testo predefinito."""
    if os.path.exists(filename):
        return applica_valori(leggi_md(filename), valori)
    return applica_valori(predefinito, valori)


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
    intro = ""
    for nome in ("5-percorsi_intro_it.md", "Intro Percorsi.md"):
        if os.path.exists(nome):
            intro = leggi_md(nome)
            break
    out = [intro, ""] if intro else []
    out += ["# Sintesi dei risultati tecnici",
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


def costruisci_aziende(riga) -> list:
    """Ricava l'elenco delle aziende dal foglio, in qualunque forma sia scritto.

    Formati riconosciuti in T21_NOMI_AZIENDE (separatore ';' oppure a capo):
        Ferriere Isontine S.p.A.
        Ferriere Isontine S.p.A. (24.10)
        Ferriere Isontine S.p.A. | 24.10 | 3200
    In alternativa, se il foglio contiene le colonne parallele
    T21_ATECO_AZIENDE e T21_FABBISOGNI_AZIENDE (liste separate da ';'),
    queste hanno la precedenza.

    Restituisce una lista di dizionari con nome, ateco, fabbisogno (t/anno o None).
    """
    grezzo = riga.get("T21_NOMI_AZIENDE")
    if is_vuoto(grezzo):
        return []

    voci = [v.strip() for v in re.split(r"[;\n]+", str(grezzo)) if v.strip()]
    ateco_paralleli = []
    fabb_paralleli = []
    if not is_vuoto(riga.get("T21_ATECO_AZIENDE")):
        ateco_paralleli = [v.strip() for v in
                           re.split(r"[;\n]+", str(riga["T21_ATECO_AZIENDE"]))]
    if not is_vuoto(riga.get("T21_FABBISOGNI_AZIENDE")):
        fabb_paralleli = [v.strip() for v in
                          re.split(r"[;\n]+", str(riga["T21_FABBISOGNI_AZIENDE"]))]

    aziende = []
    for i, voce in enumerate(voci):
        nome, codice, fabbisogno = voce, "", None

        if "|" in voce:
            pezzi = [p.strip() for p in voce.split("|")]
            nome = pezzi[0]
            if len(pezzi) > 1:
                codice = pezzi[1]
            if len(pezzi) > 2:
                fabbisogno = numero(pezzi[2])
        else:
            trovato = re.search(r"[\(\[]\s*([0-9]{2}[.,]?[0-9.,]*)\s*[\)\]]", voce)
            if trovato:
                codice = trovato.group(1)
                nome = voce[: trovato.start()].strip()

        if i < len(ateco_paralleli) and ateco_paralleli[i]:
            codice = ateco_paralleli[i]
        if i < len(fabb_paralleli):
            valore = numero(fabb_paralleli[i])
            if valore is not None:
                fabbisogno = valore

        aziende.append({"nome": nome.strip(" -"), "ateco": codice,
                        "fabbisogno": fabbisogno})
    return aziende


def ripartisci_fabbisogno(aziende: list, totale_ton):
    """Se manca il fabbisogno per singola azienda lo stima pro quota.

    La ripartizione è pesata sull'intensità di idrogeno tipica del settore ATECO.
    Restituisce True se almeno un valore è stato stimato anziché rilevato.
    """
    if not aziende or not totale_ton:
        return False
    noti = sum(a["fabbisogno"] for a in aziende if a["fabbisogno"] is not None)
    mancanti = [a for a in aziende if a["fabbisogno"] is None]
    if not mancanti:
        return False

    residuo = max(totale_ton - noti, 0.0)
    pesi = [AT.peso(a["ateco"]) for a in mancanti]
    somma = sum(pesi) or len(mancanti)
    for azienda, p in zip(mancanti, pesi):
        azienda["fabbisogno"] = residuo * p / somma
        azienda["stimato"] = True
    return True


TESTO_HTA_PREDEFINITO = """### Domanda industriale Hard-to-Abate (Tool 2.1)

La transizione impone una gerarchia di intervento fondata sulla termodinamica:
dove l'elettrificazione diretta è possibile, tramite pompe di calore, resistenze o
induzione, essa resta sempre la strada più efficiente. Esistono però comparti
definiti **Hard-to-Abate** nei quali l'elettrificazione incontra limiti fisici o
chimici insuperabili: settori in cui la molecola di idrogeno partecipa direttamente
alla reazione, come la sintesi dell'ammoniaca o la riduzione diretta del minerale
di ferro, e processi che richiedono calore oltre gli 800 °C, come i forni fusori
del vetro o la calcinazione del clinker.

A questo si aggiunge un vincolo normativo: la direttiva **RED III** impone che
entro il 2030 almeno il 42% dell'idrogeno impiegato nell'industria provenga da
fonti rinnovabili di origine non biologica (RFNBO), quota che sale al 60% entro il
2035. Per le imprese Hard-to-Abate la decarbonizzazione non è una scelta ma un
obbligo di legge, e il meccanismo CBAM ne rafforza l'urgenza sul piano competitivo.
"""

TESTO_REALITY_CHECK_PREDEFINITO = """#### Che cosa significa produrre questa quantità

Tradurre le tonnellate di idrogeno in energia e suolo serve a fissare l'ordine di
grandezza dell'impegno richiesto al territorio.

| Grandezza | Valore |
| --- | --- |
| Idrogeno richiesto dall'industria | {h2_ton} t/anno |
| Energia elettrica necessaria | {mwh} MWh/anno ({gwh} GWh/anno) |
| Potenza fotovoltaica equivalente | {mwp} MWp |
| Superficie a terra occupata | {ettari} ettari, pari a circa {campi} campi da calcio |

> Calcolo condotto con un consumo specifico di elettrolisi di {kwh_kg} kWh per kg
> di idrogeno, una producibilità fotovoltaica di {resa} kWh per kWp installato e
> un'occupazione di {ha_mwp} ettari per MWp a terra.

{giudizio_suolo}
"""


def sezione_hta(riga) -> str:
    """Sezione 2.1: mappatura delle utenze industriali Hard-to-Abate."""
    ind = numero(riga.get("T21_FABBISOGNO_H2_TON_ANNO"))
    aziende = costruisci_aziende(riga)

    testo = testo_da_template("A21-hta_intro_it.md", {}, TESTO_HTA_PREDEFINITO)
    out = [testo, ""]

    if not aziende and not ind:
        out.append("Lo screening del tessuto industriale locale non ha rilevato impianti "
                   "classificabili nei settori prioritari Hard-to-Abate. Sul territorio "
                   "comunale non sussiste quindi una domanda industriale diretta capace "
                   "di giustificare da sola un'infrastruttura dedicata: la strategia va "
                   "orientata all'elettrificazione delle utenze termiche a bassa e media "
                   "temperatura e all'efficienza energetica, riservando l'idrogeno agli "
                   "altri percorsi.")
        return "\n".join(out)

    stimato = ripartisci_fabbisogno(aziende, ind)

    if aziende:
        out.append(f"Lo screening ha individuato "
                   f"{'una sola azienda idonea' if len(aziende) == 1 else str(len(aziende)) + ' aziende idonee'} "
                   "sul territorio comunale. Per ciascuna, il codice ATECO determina il "
                   "processo produttivo e quindi se l'impiego di idrogeno sia "
                   "tecnicamente fondato o meno.")
        out.append("")
        out += ["| Azienda | ATECO | Processo | Valutazione | Fabbisogno |",
                "| --- | --- | --- | --- | --- |"]
        for a in aziende:
            codice = AT.normalizza(a["ateco"]) or "n.d."
            processo = AT.descrizione(a["ateco"])
            giudizio = AT.verdetto(a["ateco"])
            if a["fabbisogno"] is None:
                quantita = "n.d."
            else:
                quantita = f"{formatta_numero(a['fabbisogno'])} t/anno"
                if a.get("stimato"):
                    quantita += " *"
            out.append(f"| {a['nome']} | {codice} | {processo} | {giudizio} | {quantita} |")
        out.append("")

        if stimato:
            out.append("> I valori contrassegnati con l'asterisco sono una ripartizione "
                       "indicativa del fabbisogno complessivo fra le aziende individuate, "
                       "pesata sull'intensità di idrogeno tipica di ciascun settore. Non "
                       "sostituiscono la rilevazione puntuale presso le singole imprese, "
                       "che resta il passo successivo.")
            out.append("")

        # legenda dei verdetti effettivamente comparsi
        presenti = []
        for a in aziende:
            v = AT.verdetto(a["ateco"])
            if v in AT.VERDETTI and v not in presenti:
                presenti.append(v)
        if presenti:
            out.append("Criteri di valutazione applicati:")
            out += [f"- **{v}** - {AT.VERDETTI[v].replace('**', '')}" for v in presenti]
            out.append("")

    # --- reality check su energia e suolo
    if ind:
        mwh = ind * 1000 * CONSUMO_ELETTROLISI_KWH_KG / 1000
        mwp = mwh * 1000 / RESA_PV_KWH_KWP / 1000
        ettari = mwp * SUPERFICIE_PV_HA_MWP
        campi = ettari * 10000 / SUPERFICIE_CAMPO_CALCIO_MQ

        idonee = numero(riga.get("T25_AREE_IDONEE_MQ"))
        if idonee:
            quota = ettari * 10000 / idonee * 100
            if quota > 100:
                giudizio = (f"La superficie necessaria eccede le aree idonee censite sul "
                            f"territorio comunale: il fabbisogno industriale **non è "
                            f"copribile con la sola produzione locale a terra**. La "
                            "strategia dovrà combinare generazione su coperture e aree "
                            "dismesse con l'approvvigionamento da reti sovracomunali.")
            elif quota > 30:
                giudizio = (f"L'impianto occuperebbe circa il {formatta_numero(quota)}% "
                            "delle aree idonee censite: una quota rilevante, che impone "
                            "di valutare il consumo di suolo rispetto agli altri usi "
                            "possibili prima di procedere.")
            else:
                giudizio = (f"L'impianto occuperebbe circa il {formatta_numero(quota)}% "
                            "delle aree idonee censite: il territorio dispone del margine "
                            "necessario, e la scelta si sposta sulla qualità delle aree "
                            "più che sulla loro estensione.")
        else:
            giudizio = ("L'estensione richiesta mostra che difficilmente il fabbisogno "
                        "industriale sarà coperto dalla sola produzione locale a terra: "
                        "la pianificazione dovrà combinare generazione su coperture e "
                        "aree dismesse con l'approvvigionamento da reti sovracomunali, "
                        "in particolare il SoutH2 Corridor e le dorsali di trasporto.")

        valori = {
            "h2_ton": formatta_numero(ind),
            "mwh": formatta_numero(mwh),
            "gwh": formatta_numero(mwh / 1000),
            "mwp": formatta_numero(mwp),
            "ettari": formatta_numero(ettari),
            "campi": formatta_numero(round(campi)),
            "kwh_kg": formatta_numero(CONSUMO_ELETTROLISI_KWH_KG),
            "resa": formatta_numero(RESA_PV_KWH_KWP),
            "ha_mwp": formatta_numero(SUPERFICIE_PV_HA_MWP),
            "giudizio_suolo": giudizio,
        }
        out.append(testo_da_template("A21-realitycheck_it.md", valori,
                                     TESTO_REALITY_CHECK_PREDEFINITO))

    return "\n".join(out)


def testo_percorso_a(riga) -> str:
    """Lettura discorsiva del percorso A - domanda di idrogeno."""
    ind = numero(riga.get("T21_FABBISOGNO_H2_TON_ANNO"))
    flotta = numero(riga.get("T22_FABBISOGNO_H2_TON_ANNO"))
    dom = totale(riga, ["T21_FABBISOGNO_H2_TON_ANNO", "T22_FABBISOGNO_H2_TON_ANNO"])
    out = []

    # --- 1. quadro d'insieme e equivalenze
    if dom:
        kg_giorno = dom * 1000 / GIORNI_OPERATIVI
        bus_eq = kg_giorno / CONSUMO_BUS_KG_GIORNO
        litri = dom * 1000 * LITRI_DIESEL_PER_KG_H2
        co2 = dom * CO2_EVITATA_KG_PER_KG_H2      # t/anno (kg per kg = t per t)
        out.append(f"La domanda potenziale complessiva individuata sul territorio comunale "
                   f"ammonta a **{formatta_numero(dom)} tonnellate di idrogeno all'anno**, "
                   f"pari a circa {formatta_numero(kg_giorno)} kg al giorno su "
                   f"{GIORNI_OPERATIVI} giorni operativi.")
        out.append("")
        out.append("### Ordini di grandezza")
        out += ["| Riferimento | Valore |", "| --- | --- |",
                f"| Domanda complessiva | {formatta_numero(dom)} t/anno |",
                f"| Erogazione media giornaliera | {formatta_numero(kg_giorno)} kg/giorno |",
                f"| Equivalente in autobus urbani alimentabili | {formatta_numero(bus_eq)} mezzi |",
                f"| Gasolio sostituito | {formatta_numero(litri)} litri/anno |",
                f"| Emissioni evitate allo scarico | {formatta_numero(co2)} tCO2/anno |", ""]
        out.append("> Equivalenze calcolate con i parametri di riferimento nazionali: "
                   f"{formatta_numero(CONSUMO_BUS_KG_GIORNO)} kg/giorno per autobus urbano, "
                   f"{formatta_numero(EFFICIENZA_H2_KM_KG)} km/kg per il mezzo pesante a "
                   f"idrogeno contro {formatta_numero(EFFICIENZA_DIESEL_KM_LITRO)} km/litro "
                   "per il corrispondente diesel.")
        out.append("")

        # --- 2. giudizio sulla massa critica
        out.append("### Massa critica")
        if dom >= SOGLIA_MASSA_CRITICA_TON:
            out.append(f"Il volume supera le {formatta_numero(SOGLIA_MASSA_CRITICA_TON)} "
                       "t/anno assunte come soglia di sostenibilità economica per un "
                       "progetto di conversione autonomo, corrispondenti a una flotta di "
                       "una decina di mezzi pesanti in servizio continuo. **La domanda "
                       "locale è di per sé sufficiente** a giustificare un'infrastruttura "
                       "dedicata: la questione diventa la sua contrattualizzazione, non "
                       "la sua esistenza.")
        elif dom >= SOGLIA_DOMANDA_MINIMA_TON:
            out.append(f"Il volume si colloca fra le {formatta_numero(SOGLIA_DOMANDA_MINIMA_TON)} "
                       f"e le {formatta_numero(SOGLIA_MASSA_CRITICA_TON)} t/anno: **una "
                       "fascia intermedia**, in cui un progetto autonomo resta fragile ma "
                       "l'aggregazione con utenze di Comuni limitrofi, o con il traffico "
                       "di transito, può portare rapidamente il bacino sopra la soglia di "
                       "sostenibilità. È la situazione in cui la cooperazione "
                       "sovracomunale produce il maggior beneficio marginale.")
        else:
            out.append(f"Il volume resta sotto le {formatta_numero(SOGLIA_DOMANDA_MINIMA_TON)} "
                       "t/anno: **la domanda locale non basta** a sostenere una filiera "
                       "dedicata. Questo non esclude l'idrogeno dal futuro del Comune, ma "
                       "sposta il baricentro dell'azione: nel breve periodo conviene "
                       "puntare su una fornitura esterna per usi dimostrativi, e nel medio "
                       "periodo lavorare sull'aggregazione della domanda a scala d'ambito.")
        out.append("")
    else:
        out.append("Per questo Comune non è stato quantificato un fabbisogno di idrogeno. "
                   "L'analisi dei percorsi resta parziale finché i questionari sulla domanda "
                   "industriale e sulle flotte non vengono completati.")
        out.append("")

    # --- 3. composizione della domanda
    if ind and flotta:
        quota_ind = ind / (ind + flotta) * 100
        out.append("### Composizione della domanda")
        out.append(f"Il comparto produttivo pesa per il {formatta_numero(quota_ind)}% del "
                   f"totale ({formatta_numero(ind)} t/anno), la flotta per il "
                   f"{formatta_numero(100 - quota_ind)}% ({formatta_numero(flotta)} t/anno).")
        if quota_ind >= 70:
            out.append("La domanda è **trainata dall'industria**: il progetto va costruito "
                       "attorno agli utilizzatori privati, con il Comune nel ruolo di "
                       "facilitatore autorizzativo e di garante del percorso partecipativo, "
                       "più che di investitore diretto.")
        elif quota_ind <= 30:
            out.append("La domanda è **trainata dalla flotta pubblica**: il Comune ha "
                       "controllo diretto sull'utenza principale, quindi può impegnare "
                       "volumi certi in fase di gara. È la configurazione che rende più "
                       "semplice la bancabilità, perché elimina il rischio di mercato.")
        else:
            out.append("Domanda pubblica e privata si equivalgono: la configurazione più "
                       "adatta è un accordo di programma che vincoli entrambe le componenti "
                       "prima dell'investimento infrastrutturale.")
        out.append("")

    # --- 4. comparto industriale (Tool 2.1)
    industriale = sezione_hta(riga)
    if industriale:
        out.append(industriale)
        out.append("")

    # --- 4bis. concentrazione del rischio
    n_az = numero(riga.get("T21_N_AZIENDE_IDONEE")) or len(costruisci_aziende(riga))
    if n_az:
        if n_az == 1:
            out.append("La presenza di un solo utilizzatore industriale concentra tutto "
                       "il rischio di mercato su una controparte: prima di qualunque "
                       "investimento serve un impegno contrattuale di lungo periodo, "
                       "oppure l'individuazione di utenze alternative.")
            out.append("")
        elif n_az >= 3:
            out.append("La pluralità di utilizzatori distribuisce il rischio e rende "
                       "credibile un contratto di fornitura aggregato. Il passo "
                       "successivo è verificare la contiguità territoriale delle "
                       "aziende, che determina se convenga una rete locale o un "
                       "rifornimento su strada.")
            out.append("")

    # --- 5. flotte
    esito = riga.get("T22_ESITO_PREVALENTE")
    n_veicoli = numero(riga.get("T22_N_VEICOLI_ANALIZZATI"))
    delta_tco = numero(riga.get("T22_DELTA_TCO_EURO"))
    bev = riga.get("T22_BEV_FATTIBILE")
    if n_veicoli or not is_vuoto(esito):
        out.append("### Flotte e mobilità")
        if n_veicoli:
            out.append(f"L'analisi ha riguardato {formatta_numero(n_veicoli)} veicoli.")
        if not is_vuoto(esito):
            out.append(f"L'esito prevalente è: *{str(esito).strip()}*.")
        if bev is not None and not is_vuoto(bev):
            if vero(bev):
                out.append("Per una parte dei mezzi **l'alternativa elettrica a batteria "
                           "risulta praticabile**. L'idrogeno va quindi riservato ai "
                           "segmenti in cui autonomia, tempi di rifornimento o carichi "
                           "rendono la batteria inadeguata: destinarlo a usi che la "
                           "batteria copre meglio peggiora sia i costi sia il bilancio "
                           "energetico complessivo.")
            else:
                out.append("L'alternativa elettrica a batteria non risulta praticabile sui "
                           "mezzi analizzati: **l'idrogeno è l'unica opzione a zero "
                           "emissioni allo scarico** per questo segmento di flotta, il che "
                           "rafforza la solidità del caso d'uso.")
        if delta_tco is not None:
            if delta_tco > 0:
                out.append(f"Il costo totale di possesso resta superiore a quello dei mezzi "
                           f"convenzionali di Euro {formatta_numero(delta_tco)} sull'intero "
                           "ciclo di vita: il divario va colmato con contributi in conto "
                           "capitale, e va monitorato perché si riduce con la discesa dei "
                           "costi di produzione dell'idrogeno.")
            else:
                out.append(f"Il costo totale di possesso risulta **inferiore** a quello dei "
                           f"mezzi convenzionali di Euro {formatta_numero(abs(delta_tco))} "
                           "sul ciclo di vita: la conversione si regge senza contributo, "
                           "purché il prezzo dell'idrogeno alla pompa rimanga entro le "
                           "ipotesi assunte.")
        out.append("")

    # --- 6. usi di nicchia
    attive = [NICCHIE[c] for c in NICCHIE if c in riga.index and vero(riga[c])]
    if attive:
        out.append("### Usi di nicchia")
        out.append("Il territorio presenta impieghi specifici in cui l'idrogeno compete su "
                   "requisiti diversi dal solo costo:")
        out += [f"- {a}" for a in attive]
        out.append("")
        out.append("Questi impieghi hanno volumi contenuti ma alto valore dimostrativo: "
                   "sono i candidati naturali per la prima fase, perché rendono visibile "
                   "la tecnologia a costi contenuti e costruiscono consenso.")
        out.append("")

    # --- 7. fabbisogno termico
    termico = numero(riga.get("T24_FABBISOGNO_TERMICO_KWH_ANNO"))
    ottimale = riga.get("T24_SOLUZIONE_OTTIMALE")
    pulita = riga.get("T24_SOLUZIONE_PIU_PULITA")
    if termico or not is_vuoto(ottimale):
        out.append("### Fabbisogno termico degli edifici pubblici")
        if termico:
            out.append(f"Il fabbisogno termico rilevato è di {formatta_numero(termico)} "
                       "kWh/anno.")
        if not is_vuoto(ottimale) and not is_vuoto(pulita):
            if str(ottimale).strip().lower() == str(pulita).strip().lower():
                out.append(f"La soluzione ottimale coincide con quella a minori emissioni "
                           f"(*{str(ottimale).strip()}*): non vi è conflitto fra convenienza "
                           "economica e obiettivo ambientale.")
            else:
                out.append(f"La soluzione economicamente ottimale (*{str(ottimale).strip()}*) "
                           f"non coincide con quella a minori emissioni "
                           f"(*{str(pulita).strip()}*). È una scelta politica prima che "
                           "tecnica: va esplicitata nel piano, indicando quale criterio "
                           "prevale e perché.")
        elif not is_vuoto(ottimale):
            out.append(f"La soluzione individuata come ottimale è: *{str(ottimale).strip()}*.")
        out.append("")

    return "\n".join(out).strip()


def commento_percorso(riga, codice: str) -> str:
    """Lettura del singolo percorso, prima delle tabelle."""
    if codice == "A":
        return testo_percorso_a(riga)

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
              f"3-maturita_{livello}_it.md", "4-profilo_intro_it.md",
              "5-percorsi_intro_it.md"]
    if profilo:
        attesi.append(f"4-profilo_{profilo}_it.md")
    return attesi
