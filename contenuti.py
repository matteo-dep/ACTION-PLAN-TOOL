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

SOGLIE_MATURITA = [(5, 8, "L1"), (9, 14, "L2"), (15, 999, "L3")]
SOGLIA_MINIMA = 5

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

# --- Soglie sulla domanda complessiva (processo + mobilità) ------------------
# Flotta minima ritenuta sostenibile: 10 mezzi pesanti x 26 kg/giorno x 300
# giorni, cioè circa 78 t/anno. È il riferimento per un progetto autonomo.
SOGLIA_MASSA_CRITICA_TON = 78.0
# Sotto questa soglia la domanda è troppo frammentata per un progetto autonomo
SOGLIA_DOMANDA_MINIMA_TON = 25.0

# --- Soglie sulla sola mobilità ---------------------------------------------
# Una flotta comunale non si misura con il metro del trasporto pesante: uno
# scuolabus percorre 80-100 km al giorno per circa 190 giorni di servizio, un
# camion a lungo raggio molti di più per 300 giorni. Le soglie qui sotto non
# derivano dal numero di mezzi ma dal minimo tecnico di erogazione, che è ciò
# che davvero determina la fattibilità del rifornimento.
#   30 t/anno = 100 kg/giorno: minimo per una stazione dedicata, anche piccola
#    8 t/anno =  27 kg/giorno: un solo mezzo pesante in servizio continuo
SOGLIA_MOBILITA_AUTONOMA_TON = 30.0
SOGLIA_MOBILITA_MINIMA_TON = 8.0

CONSUMO_BUS_KG_GIORNO = 26.0        # bus urbano da 12 m, 250 km/giorno
GIORNI_OPERATIVI = 300              # giorni di servizio in un anno
EFFICIENZA_H2_KM_KG = 11.4          # mezzo pesante stradale
EFFICIENZA_DIESEL_KM_LITRO = 3.5    # mezzo pesante stradale
EMISSIONI_DIESEL_KG_LITRO = 2.7     # kgCO2 per litro di gasolio

# 1 kg di H2 sostituisce EFFICIENZA_H2_KM_KG / EFFICIENZA_DIESEL_KM_LITRO litri
LITRI_DIESEL_PER_KG_H2 = EFFICIENZA_H2_KM_KG / EFFICIENZA_DIESEL_KM_LITRO
CO2_EVITATA_KG_PER_KG_H2 = LITRI_DIESEL_PER_KG_H2 * EMISSIONI_DIESEL_KG_LITRO

# Reality check: quanta energia e quanto suolo serve per produrre l'idrogeno
CONSUMO_ELETTROLISI_KWH_KG = 55.0   # consumo specifico di sistema,
                                    # elettrolisi piu' ausiliari e compressione
RESA_PV_KWH_KWP = 1200.0            # producibilità media in Friuli Venezia Giulia
                                    # valore unico condiviso con i tool 2.4 e 2.6
SUPERFICIE_PV_HA_MWP = 1.3          # fotovoltaico a terra
SUPERFICIE_CAMPO_CALCIO_MQ = 7140.0


# --- Parametri per la stima dei fabbisogni di nicchia (Tool 2.3) -------------
# Conversioni usate per tradurre i driver fisici raccolti dal questionario in
# chilogrammi di idrogeno. Sono ordini di grandezza dichiarati, non valori di
# progetto: servono a capire se una nicchia pesa quanto un mezzo o quanto una
# flotta, non a dimensionare un impianto.
RESA_FUEL_CELL_KWH_KG = 17.0     # kWh elettrici da 1 kg di H2 (PEMFC, ~50%)
CONSUMO_TRENO_KG_KM = 0.25       # automotrice a idrogeno su tratta regionale
ORE_CARRELLO_GIORNO = 8.0        # turno tipico di un carrello elevatore
GIORNI_LOGISTICA = 250           # giorni operativi di un magazzino

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
                "T25_ENTRO_5KM_DORSALE", "T25_SUP_PUBBLICA_MQ",
                "T25_PV_TERRA_INSTALLATO_MW", "T25_PROGRAMMABILI_MW",
                "T25_FLAG_EOLICO_IDONEO", "T25_FLAG_DISPACCIAMENTO"]),
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
                "T27_SCORE_C3", "T27_SCORE_GOV", "T27_FLAG_AREE_700BAR",
                "T27_FLAG_AFIR_GAP", "T27_FLAG_HUB_MERCI", "T27_FLAG_SINERGIA_HTA",
                "T27_FLAG_ACCORDI_FILIERA", "T27_FLAG_PUMS"]),
            ("Stazione di rifornimento (Tool 2.8)", [
                "T28_TAGLIA_HRS", "T28_CONFIGURAZIONE", "T28_CAPACITA_KG_GIORNO",
                "T28_N_DISPENSER", "T28_STRATEGIA_SUPPLY", "T28_POTENZA_COMPRESSORE_KW",
                "T28_AREA_MINIMA_MQ", "T28_CAPEX_COMPLESSIVO_EURO",
                "T28_BREAK_EVEN_EURO_KG", "T28_ORIZZONTE", "T28_QUOTA_FCEV_PERC"]),
        ],
    },
]

# T21_*: già trattate per esteso nella sezione 2.1, non si ripetono in tabella
# I dati dei tool 2.1, 2.2 e 2.3 sono discussi per esteso nel testo del percorso A:
# ripeterli in tabella allungherebbe il documento senza aggiungere nulla.
ESCLUSE = {"T11_MAIL", COL_ID, COL_NOME, COL_MATURITA,
           "T12_SCORE_A", "T12_SCORE_B", "T12_SCORE_C",
           "T21_N_AZIENDE_IDONEE", "T21_NOMI_AZIENDE", "T21_FABBISOGNO_H2_TON_ANNO",
           "T21_ATECO_AZIENDE", "T21_FABBISOGNI_AZIENDE", "T21_FAMIGLIE_AZIENDE",
           "T22_N_VEICOLI_ANALIZZATI", "T22_ESITO_PREVALENTE", "T22_BEV_FATTIBILE",
           "T22_FABBISOGNO_H2_TON_ANNO", "T22_FABBISOGNO_ELETTRICO_MWH_ANNO",
           "T22_ENERGIA_ELETTROLISI_MWH_ANNO", "T22_DELTA_TCO_EURO",
           "T22_EMISSIONI_EVITATE_TCO2",
           "T23_FLAG_RIFUGI", "T23_FLAG_MEZZI_CRITICI", "T23_FLAG_COLD_STORAGE",
           "T23_FLAG_TRENI", "T23_FLAG_PORTI_AEROPORTI", "T23_FLAG_DEPURATORI",
           "T23_RIFUGI_ELETTRICO_KWH", "T23_GASOLIO_FLOTTA_LITRI_ANNO",
           "T23_N_CARRELLI", "T23_POTENZA_CARRELLI_KW",
           "T23_TRATTA_NON_ELETTRIFICATA_KM", "T23_CORSE_GIORNALIERE",
           "T23_AERAZIONE_KWH_ANNO"}

FLAG_GOVERNANCE = ["T12_FLAG_PIANIFICAZIONE", "T12_FLAG_NAHV",
                   "T12_FLAG_JOINT_PROCUREMENT", "T23_FLAG_HYDROGEN_VALLEY"]

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
    "T23_N_MEZZI_SPECIALI": "Mezzi speciali censiti",
    "T23_MEZZI_FUEL_CELL": "Mezzi convertibili a celle a combustibile",
    "T23_FLAG_HYDROGEN_VALLEY": "Hydrogen Valley già finanziata nell'area",
    "T25_SUP_PUBBLICA_MQ": "Superfici di proprietà pubblica",
    "T25_PV_TERRA_INSTALLATO_MW": "Fotovoltaico a terra già installato",
    "T25_PROGRAMMABILI_MW": "Fonti programmabili in esercizio",
    "T25_FLAG_EOLICO_IDONEO": "Aree con ventosità adeguata",
    "T25_FLAG_DISPACCIAMENTO": "Interesse ai mercati di dispacciamento",
    "T27_FLAG_AFIR_GAP": "Colma un vuoto della rete AFIR",
    "T27_FLAG_HUB_MERCI": "Hub merci o interporti entro 5 km",
    "T27_FLAG_SINERGIA_HTA": "Sinergia con distretti Hard-to-Abate",
    "T27_FLAG_ACCORDI_FILIERA": "Accordi di filiera già attivi",
    "T27_FLAG_PUMS": "Idrogeno nella pianificazione della mobilità",
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


def contestazioni(riga) -> str:
    """Il questionario 2.5 non chiede 'ci sono contestazioni?' ma QUALI tecnologie
    le hanno generate: il campo contiene 'Eolico', 'Reti Elettriche', 'BESS /
    Accumuli', 'Idroelettrico'... Trattarlo come un sì/no lo rende sempre falso.
    Restituisce il testo se indica una contestazione reale, stringa vuota altrimenti.
    """
    valore = riga.get("T25_FLAG_CONTESTAZIONI")
    if is_vuoto(valore):
        return ""
    testo = str(valore).strip()
    if testo.lower() in ("no", "n", "nessuna", "none", "false", "0", "ne"):
        return ""
    return testo


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
    fam_parallele = []
    if not is_vuoto(riga.get("T21_FAMIGLIE_AZIENDE")):
        fam_parallele = [v.strip() for v in
                         re.split(r"[;\n]+", str(riga["T21_FAMIGLIE_AZIENDE"]))]

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

        famiglia = fam_parallele[i] if i < len(fam_parallele) else ""
        aziende.append({"nome": nome.strip(" -"), "ateco": codice,
                        "fabbisogno": fabbisogno, "famiglia": famiglia})
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
            dal_tool = AT.da_famiglia(a.get("famiglia"))
            if dal_tool:
                giudizio, processo = dal_tool[0], dal_tool[1]
            else:
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
            dal_tool = AT.da_famiglia(a.get("famiglia"))
            v = dal_tool[0] if dal_tool else AT.verdetto(a["ateco"])
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



TESTO_FLOTTE_PREDEFINITO = """### Flotte e mobilità (Tool 2.2)

Nel trasporto la gerarchia di intervento è la stessa dell'industria, ma i confini
sono più netti. Per i mezzi leggeri e per le percorrenze urbane la batteria è oggi
più efficiente, più economica e più matura: l'idrogeno vi sarebbe uno spreco di
energia primaria, perché per ogni kilowattora impiegato alla ruota ne servono circa
tre alla produzione. Il vantaggio dell'idrogeno emerge dove la batteria incontra
limiti fisici — autonomie elevate senza soste lunghe, carichi utili che il peso
delle celle eroderebbe, mezzi in servizio continuo su più turni, temperature rigide
che riducono la capacità disponibile.

La valutazione che segue si fonda sul costo totale di possesso, che considera
insieme l'acquisto del mezzo, il carburante, la manutenzione e il valore residuo:
è il solo criterio che permette di confrontare tecnologie con costi iniziali e
costi di esercizio tanto diversi.
"""


def sezione_flotte(riga) -> str:
    """Sezione 2.2: analisi della flotta e del costo totale di possesso."""
    n_veicoli = numero(riga.get("T22_N_VEICOLI_ANALIZZATI"))
    fabbisogno = numero(riga.get("T22_FABBISOGNO_H2_TON_ANNO"))
    esito = riga.get("T22_ESITO_PREVALENTE")
    bev = riga.get("T22_BEV_FATTIBILE")
    delta_tco = numero(riga.get("T22_DELTA_TCO_EURO"))
    elettrico = numero(riga.get("T22_FABBISOGNO_ELETTRICO_MWH_ANNO"))
    elettrolisi = numero(riga.get("T22_ENERGIA_ELETTROLISI_MWH_ANNO"))
    co2 = numero(riga.get("T22_EMISSIONI_EVITATE_TCO2"))

    if not any(v is not None for v in (n_veicoli, fabbisogno, delta_tco)) and is_vuoto(esito):
        return ""

    out = [testo_da_template("A22-flotte_intro_it.md", {}, TESTO_FLOTTE_PREDEFINITO), ""]

    # --- quadro dell'analisi
    righe = []
    if n_veicoli:
        righe.append(f"| Veicoli analizzati | {formatta_numero(n_veicoli)} |")
    if not is_vuoto(esito):
        righe.append(f"| Esito prevalente | {str(esito).strip()} |")
    if fabbisogno:
        kg_giorno = fabbisogno * 1000 / GIORNI_OPERATIVI
        righe.append(f"| Fabbisogno di idrogeno | {formatta_numero(fabbisogno)} t/anno |")
        righe.append(f"| Erogazione media richiesta | {formatta_numero(kg_giorno)} kg/giorno |")
    if co2:
        righe.append(f"| Emissioni evitate | {formatta_numero(co2)} tCO2/anno |")
    if righe:
        out += ["| Parametro | Valore |", "| --- | --- |"] + righe + [""]

    # --- massa critica della sola mobilità
    if fabbisogno:
        kg_giorno = fabbisogno * 1000 / GIORNI_OPERATIVI
        out.append("#### Sostenibilità del rifornimento")
        bus_eq = kg_giorno / CONSUMO_BUS_KG_GIORNO
        if fabbisogno >= SOGLIA_MASSA_CRITICA_TON:
            out.append(f"Con {formatta_numero(kg_giorno)} kg al giorno — l'equivalente di "
                       f"circa {formatta_numero(bus_eq)} autobus urbani in servizio — la "
                       "flotta raggiunge la scala che rende sostenibile **un impianto di "
                       "rifornimento presso il proprio deposito**. È la configurazione più "
                       "favorevole: i mezzi rientrano ogni sera, il rifornimento avviene in "
                       "orario notturno e la domanda è interamente sotto il controllo "
                       "dell'amministrazione, il che elimina il rischio di mercato che "
                       "grava su qualunque stazione aperta al pubblico.")
        elif fabbisogno >= SOGLIA_MOBILITA_AUTONOMA_TON:
            out.append(f"Con {formatta_numero(kg_giorno)} kg al giorno la flotta supera la "
                       f"soglia tecnica di {formatta_numero(SOGLIA_MOBILITA_AUTONOMA_TON)} "
                       "t/anno, sotto la quale una stazione non ammortizza i costi fissi di "
                       "compressione e preraffreddamento. Resta però **al di sotto della "
                       f"scala di {formatta_numero(SOGLIA_MASSA_CRITICA_TON)} t/anno** — "
                       "l'equivalente di una decina di mezzi pesanti — che i modelli di "
                       "business individuano come punto di pareggio per un impianto "
                       "dedicato al solo deposito comunale. L'infrastruttura è quindi "
                       "tecnicamente possibile ma economicamente fragile se resta isolata: "
                       "conviene dimensionarla per servire anche utenze esterne, oppure "
                       "condividerla con Comuni limitrofi e operatori privati.")
        elif fabbisogno >= SOGLIA_MOBILITA_MINIMA_TON:
            out.append(f"Con {formatta_numero(kg_giorno)} kg al giorno la flotta si colloca "
                       "**sotto la soglia di una stazione dedicata**, pur restando sopra il "
                       "minimo operativo. È la situazione tipica di chi avvia una flotta "
                       "sperimentale di due o tre mezzi. Le strade praticabili sono due: "
                       "aggregare la domanda con quella di Comuni vicini o di operatori "
                       "privati fino a raggiungere la massa critica, oppure rifornirsi "
                       "presso stazioni pubbliche esistenti lungo le direttrici TEN-T, "
                       "verificando che la distanza sia compatibile con le percorrenze "
                       "quotidiane dei mezzi.")
        else:
            out.append(f"Con {formatta_numero(kg_giorno)} kg al giorno il fabbisogno "
                       "comunale resta **inferiore al consumo di un solo autobus di linea**, "
                       f"che si attesta attorno ai {formatta_numero(CONSUMO_BUS_KG_GIORNO)} kg "
                       "al giorno. Progettare un'infrastruttura fissa per rifornire meno di "
                       "un mezzo sarebbe un paradosso economico. La conversione resta "
                       "praticabile solo in forma dimostrativa, con approvvigionamento "
                       "tramite carro bombolaio o stazione mobile: soluzioni che riducono "
                       "l'investimento iniziale a una frazione di quello di un impianto "
                       "fisso, al prezzo di un costo per chilogrammo più alto.")
        out.append("")

    # --- alternativa elettrica
    if not is_vuoto(bev):
        out.append("#### Confronto con l'alternativa elettrica")
        if vero(bev):
            frase = ("Per una parte dei mezzi analizzati **l'alternativa a batteria risulta "
                     "praticabile**. È un risultato che va preso sul serio: dove la batteria "
                     "arriva, arriva meglio, perché l'efficienza dalla presa alla ruota è "
                     "circa tre volte superiore. L'idrogeno va quindi riservato ai segmenti "
                     "in cui la batteria non basta, e destinare risorse pubbliche a "
                     "convertire mezzi che potrebbero essere elettrici peggiora sia il "
                     "bilancio economico sia quello energetico.")
        else:
            frase = ("Sui mezzi analizzati **l'alternativa a batteria non risulta "
                     "praticabile**, per autonomia richiesta, carichi o continuità di "
                     "servizio. L'idrogeno resta l'unica opzione a zero emissioni allo "
                     "scarico per questo segmento, il che rafforza la solidità del caso "
                     "d'uso: non si sta scegliendo fra due strade, se ne sta percorrendo "
                     "l'unica disponibile.")
        out += [frase, ""]

    # --- confronto energetico
    if elettrico and elettrolisi:
        rapporto = elettrolisi / elettrico if elettrico else None
        out.append("#### Energia richiesta dalle due strade")
        out += ["| Voce | Valore |", "| --- | --- |",
                f"| Elettrificazione diretta della flotta | {formatta_numero(elettrico)} MWh/anno |",
                f"| Produzione dell'idrogeno equivalente | {formatta_numero(elettrolisi)} MWh/anno |"]
        if rapporto:
            out.append(f"| Rapporto fra le due | {formatta_numero(rapporto)} volte |")
        out.append("")
        if rapporto and rapporto > 1.5:
            out.append(f"La via dell'idrogeno richiede {formatta_numero(rapporto)} volte "
                       "l'energia della via elettrica diretta. È il costo termodinamico "
                       "della conversione, e va messo in conto: si accetta dove la batteria "
                       "non è praticabile, non come scelta di preferenza.")
            out.append("")

    # --- costo totale di possesso
    if delta_tco is not None:
        out.append("#### Costo totale di possesso")
        if delta_tco > 0:
            per_mezzo = delta_tco / n_veicoli if n_veicoli else None
            frase = (f"La conversione costa **Euro {formatta_numero(delta_tco)} in più** "
                     "rispetto ai mezzi convenzionali sull'intero ciclo di vita")
            if per_mezzo:
                frase += f", pari a circa Euro {formatta_numero(per_mezzo)} per veicolo"
            frase += (". Il divario va colmato con contributi in conto capitale — i bandi "
                      "regionali e il PNRR coprono in genere il differenziale d'acquisto — "
                      "e va rivalutato periodicamente, perché si riduce con la discesa del "
                      "prezzo dell'idrogeno e con la scala di produzione dei veicoli.")
            out.append(frase)
        else:
            out.append(f"La conversione risulta **conveniente di Euro "
                       f"{formatta_numero(abs(delta_tco))}** sul ciclo di vita rispetto ai "
                       "mezzi convenzionali. È un risultato favorevole ma condizionato: "
                       "dipende dal prezzo dell'idrogeno alla pompa assunto nella "
                       "simulazione, che è la variabile più incerta dell'intero calcolo. "
                       "Prima di deliberare l'investimento conviene verificare che quel "
                       "prezzo sia coerente con l'offerta effettivamente disponibile sul "
                       "territorio.")
        out.append("")

    return "\n".join(out).strip()



TESTO_NICCHIE_PREDEFINITO = """### Usi di nicchia (Tool 2.3)

Accanto all'industria e alle flotte esistono impieghi in cui l'idrogeno compete su
requisiti diversi dal solo costo: la continuità del servizio, l'assenza di rete
elettrica adeguata, il tempo di rifornimento fra un turno e l'altro. Sono volumi
contenuti, ma hanno un valore che il conto economico non cattura: rendono la
tecnologia visibile alla comunità e costruiscono le competenze tecniche
dell'amministrazione a costi contenuti.

Per questo motivo gli usi di nicchia sono spesso i candidati naturali della prima
fase di un percorso comunale, anche quando il grosso della domanda sta altrove.
"""

# Per ogni nicchia: descrizione, colonna del driver fisico, e come si converte
# quel driver in un fabbisogno annuo di idrogeno.
DETTAGLIO_NICCHIE = {
    "T23_FLAG_RIFUGI": {
        "titolo": "Rifugi e utenze isolate",
        "testo": "Sono utenze fuori rete, oggi alimentate da generatori diesel il cui "
                 "combustibile va portato in quota. Una cella a combustibile alimentata "
                 "da idrogeno prodotto a valle elimina il rumore, le emissioni locali e "
                 "il rischio di sversamento, ma la logistica di rifornimento resta il "
                 "vincolo principale: va confrontata con quella attuale del gasolio "
                 "prima di considerarla un vantaggio.",
        "driver": "T23_RIFUGI_ELETTRICO_KWH",
        "unita": "kWh/anno",
        "kg": lambda v: v / RESA_FUEL_CELL_KWH_KG,
    },
    "T23_FLAG_MEZZI_CRITICI": {
        "titolo": "Mezzi critici e comprensori",
        "testo": "Battipista, mezzi di soccorso e di protezione civile hanno un requisito "
                 "che il costo non esprime: devono funzionare quando serve, spesso a "
                 "temperature rigide e senza possibilità di soste lunghe. È la condizione "
                 "in cui la batteria perde capacità proprio quando è più necessaria, e in "
                 "cui il rifornimento rapido dell'idrogeno diventa un requisito operativo "
                 "prima che una scelta ambientale.",
        "driver": "T23_GASOLIO_FLOTTA_LITRI_ANNO",
        "unita": "litri di gasolio/anno",
        "kg": lambda v: v / LITRI_DIESEL_PER_KG_H2,
    },
    "T23_FLAG_COLD_STORAGE": {
        "titolo": "Logistica del freddo e movimentazione",
        "testo": "Nei magazzini a ciclo continuo i carrelli elevatori elettrici impongono "
                 "la sostituzione delle batterie fra un turno e l'altro, con spazi "
                 "dedicati alla ricarica e tempi morti. La cella a combustibile si "
                 "rifornisce in pochi minuti e mantiene prestazioni costanti anche in "
                 "cella frigorifera, dove le batterie perdono capacità. È l'applicazione "
                 "in cui l'idrogeno ha la storia commerciale più lunga.",
        "driver": "T23_POTENZA_CARRELLI_KW",
        "unita": "kW installati",
        "kg": lambda v: v * ORE_CARRELLO_GIORNO * GIORNI_LOGISTICA * 0.5
                        / RESA_FUEL_CELL_KWH_KG,
    },
    "T23_FLAG_TRENI": {
        "titolo": "Trasporto ferroviario su tratte non elettrificate",
        "testo": "Elettrificare una linea costa fra uno e due milioni di euro al "
                 "chilometro e richiede anni di cantiere. Dove i volumi di traffico non "
                 "giustificano quell'investimento, l'automotrice a idrogeno consente di "
                 "eliminare il gasolio senza toccare l'infrastruttura, con un unico punto "
                 "di rifornimento in deposito. Il confronto va fatto sul costo "
                 "complessivo di ciclo di vita, non sul solo prezzo del mezzo.",
        "driver": "T23_TRATTA_NON_ELETTRIFICATA_KM",
        "unita": "km di tratta",
        "kg": None,     # serve anche il numero di corse: calcolato a parte
    },
    "T23_FLAG_PORTI_AEROPORTI": {
        "titolo": "Movimentazione portuale e aeroportuale",
        "testo": "I mezzi di piazzale lavorano a ciclo continuo su percorsi brevi e "
                 "ripetitivi, rientrando in aree ristrette: è la configurazione ideale "
                 "per un rifornimento concentrato in pochi punti. La domanda è "
                 "prevedibile e contrattualizzabile, il che rende questi impianti fra i "
                 "più facili da finanziare.",
        "driver": None,
        "unita": "",
        "kg": None,
    },
    "T23_FLAG_DEPURATORI": {
        "titolo": "Impianti di depurazione",
        "testo": "L'aerazione delle vasche assorbe energia in modo costante tutto l'anno, "
                 "senza le punte tipiche di altre utenze: è un carico di base ideale da "
                 "accoppiare a una produzione locale. Alcuni impianti producono inoltre "
                 "biogas, dal quale si può ricavare idrogeno senza passare "
                 "dall'elettrolisi — una strada che va valutata prima di dimensionare "
                 "qualunque elettrolizzatore.",
        "driver": "T23_AERAZIONE_KWH_ANNO",
        "unita": "kWh/anno",
        "kg": lambda v: v / RESA_FUEL_CELL_KWH_KG,
    },
}


def sezione_nicchie(riga) -> str:
    """Sezione 2.3: usi di nicchia, con stima del fabbisogno dove i driver ci sono."""
    attive = [c for c in DETTAGLIO_NICCHIE if c in riga.index and vero(riga[c])]
    if not attive:
        return ""

    out = [testo_da_template("A23-nicchie_intro_it.md", {}, TESTO_NICCHIE_PREDEFINITO), ""]
    totale_kg = 0.0
    stimate = []

    for colonna in attive:
        info = DETTAGLIO_NICCHIE[colonna]
        out.append(f"#### {info['titolo']}")
        out.append(info["testo"])

        kg = None
        driver = numero(riga.get(info["driver"])) if info["driver"] else None

        if colonna == "T23_FLAG_TRENI":
            km = numero(riga.get("T23_TRATTA_NON_ELETTRIFICATA_KM"))
            corse = numero(riga.get("T23_CORSE_GIORNALIERE"))
            if km and corse:
                kg = km * corse * 2 * 365 * CONSUMO_TRENO_KG_KM
                out.append("")
                out.append(f"La tratta misura {formatta_numero(km)} km e ospita "
                           f"{formatta_numero(corse)} corse al giorno: considerando il "
                           "percorso di andata e ritorno, il servizio richiederebbe circa "
                           f"**{formatta_numero(kg / 1000)} tonnellate di idrogeno all'anno**.")
        elif driver is not None and info["kg"]:
            kg = info["kg"](driver)
            out.append("")
            out.append(f"Il questionario riporta {formatta_numero(driver)} "
                       f"{info['unita']}, che corrispondono a circa "
                       f"**{formatta_numero(kg / 1000)} tonnellate di idrogeno all'anno**.")

        if kg:
            totale_kg += kg
            stimate.append((info["titolo"], kg))
        out.append("")

    if len(stimate) > 1:
        out.append("#### Peso complessivo degli usi di nicchia")
        out += ["| Impiego | Fabbisogno stimato |", "| --- | --- |"]
        out += [f"| {t} | {formatta_numero(k / 1000)} t/anno |" for t, k in stimate]
        out.append(f"| **Totale** | **{formatta_numero(totale_kg / 1000)} t/anno** |")
        out.append("")

    if totale_kg:
        tot_ton = totale_kg / 1000
        if tot_ton >= SOGLIA_MOBILITA_AUTONOMA_TON:
            out.append(f"Con {formatta_numero(tot_ton)} t/anno gli usi di nicchia non sono "
                       "più un contorno: da soli raggiungono la scala di una piccola "
                       "stazione di rifornimento, e vanno considerati parte della domanda "
                       "principale.")
        else:
            out.append(f"Il totale di {formatta_numero(tot_ton)} t/anno conferma la natura "
                       "dimostrativa di questi impieghi. Il loro valore sta nell'essere "
                       "primi passi realizzabili: costruiscono competenza tecnica e "
                       "consenso, che sono i prerequisiti dei progetti più impegnativi.")
        out.append("")
        out.append("> Le stime sopra derivano dai driver fisici dichiarati nel questionario "
                   f"con parametri di conversione dichiarati: {formatta_numero(RESA_FUEL_CELL_KWH_KG)} "
                   "kWh elettrici per kg di idrogeno in cella a combustibile, "
                   f"{formatta_numero(CONSUMO_TRENO_KG_KM)} kg/km per l'automotrice "
                   "ferroviaria. Sono ordini di grandezza per orientare le priorità, non "
                   "valori di progetto.")

    return "\n".join(out).strip()


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
        # le due componenti misurano cose diverse e non si sovrappongono:
        # senza dirlo, il lettore sospetta un doppio conteggio
        if ind and flotta:
            out.append("Il valore somma due domande di natura diversa, che non si "
                       "sovrappongono. La **domanda di processo** riguarda l'idrogeno "
                       "impiegato dentro il ciclo produttivo delle imprese, come materia "
                       "prima o come combustibile per il calore ad alta temperatura: non "
                       "comprende i mezzi di quelle stesse aziende. La **domanda di "
                       "mobilità** riguarda i veicoli, pubblici e privati, censiti "
                       "separatamente. Sommarle è corretto, ma le due componenti "
                       "rispondono a logiche distinte: la prima dipende dagli obblighi di "
                       "decarbonizzazione industriale, la seconda dal ricambio delle "
                       "flotte.")
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
        out += ["| Componente | Fabbisogno | Quota |", "| --- | --- | --- |",
                f"| Processi industriali (Tool 2.1) | {formatta_numero(ind)} t/anno | "
                f"{formatta_numero(quota_ind)}% |",
                f"| Mobilità e flotte (Tool 2.2) | {formatta_numero(flotta)} t/anno | "
                f"{formatta_numero(100 - quota_ind)}% |", ""]
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

    # --- 5. flotte e mobilità (Tool 2.2)
    out.append(sezione_flotte(riga))
    out.append("")

    # --- 6. usi di nicchia (Tool 2.3)
    out.append(sezione_nicchie(riga))
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
    contestato = contestazioni(riga)
    if contestato:
        vincoli.append(f"Sul territorio risultano contestazioni riferite a: "
                       f"{contestato}. Il percorso partecipativo va avviato prima "
                       "della progettazione, non dopo.")
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
