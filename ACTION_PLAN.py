"""
H2READY TOOLKIT - Generatore Action Plan comunali
Progetto Interreg VI-A Italia-Slovenia ITA-SI0800335

PASSO 1: livello di maturità (T11) + profilo strategico calcolato da T12_SCORE_A/B/C
PASSO 2: risultati dei percorsi (T21-T28), letti e formattati automaticamente
PASSO 3: analisi incrociata (bilancio domanda/offerta, coerenza economica)
PASSO 4: roadmap su misura
"""

import os
import re
import unicodedata
from datetime import date

import pandas as pd
import streamlit as st
from streamlit_gsheets import GSheetsConnection
from fpdf import FPDF

# =============================================================================
# 0. CONFIGURAZIONE
# =============================================================================

SPREADSHEET_URL = ""          # usato solo se manca nei secrets
LOGO = "logo_h2ready.png"
FONT_DIR = "fonts"            # opzionale: DejaVuSans.ttf, -Bold, -Oblique
BLU = (0, 51, 153)
GRIGIO = (110, 110, 110)

COL_ID = "ID_ISTAT"
COL_NOME = "NOME_COMUNE"
COL_MATURITA = "T11_LIVELLO_MATURITA"
COL_SCORE = {"A": "T12_SCORE_A", "B": "T12_SCORE_B", "C": "T12_SCORE_C"}

SOGLIE_MATURITA = [(3, 8, "L1"), (9, 14, "L2"), (15, 999, "L3")]
SOGLIA_MINIMA = 3

# Profilo: la lettera dominante entra sempre; le altre entrano se raggiungono
# almeno QUOTA_SECONDARIA del punteggio massimo e superano PUNTEGGIO_MINIMO.
QUOTA_SECONDARIA = 0.80
PUNTEGGIO_MINIMO = 0.0

NOMI_PROFILO = {
    "A": "Consumo - la domanda locale traina la transizione",
    "B": "Produzione - il territorio può generare idrogeno rinnovabile",
    "C": "Transito - il Comune si colloca su direttrici logistiche rilevanti",
}

# --- Struttura del PASSO 2 ----------------------------------------------------
# Ogni blocco elenca le colonne nell'ordine in cui devono comparire.
# Etichette e unità di misura vengono dedotte dal nome (vedi SUFFISSI/ETICHETTE).
PERCORSI = [
    {
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
        "titolo": "Percorso B - Offerta e produzione",
        "blocchi": [
            ("Stato delle rinnovabili e aree disponibili (Tool 2.5)", [
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
        "titolo": "Percorso C - Transito e infrastruttura di rifornimento",
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

# Colonne escluse dalle tabelle (dato personale o già usato altrove)
ESCLUSE = {"T11_MAIL", COL_ID, COL_NOME, COL_MATURITA,
           "T12_SCORE_A", "T12_SCORE_B", "T12_SCORE_C"}

# Suffisso della colonna -> (tipo, unità). Il primo che combacia vince.
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

# Etichette leggibili: solo dove la deduzione automatica non basta.
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
    "T12_FLAG_PIANIFICAZIONE": "Idrogeno presente negli strumenti di pianificazione",
    "T12_FLAG_NAHV": "Adesione alla North Adriatic Hydrogen Valley",
    "T12_FLAG_JOINT_PROCUREMENT": "Disponibilità ad appalti congiunti",
}

FLAG_GOVERNANCE = ["T12_FLAG_PIANIFICAZIONE", "T12_FLAG_NAHV",
                   "T12_FLAG_JOINT_PROCUREMENT"]

st.set_page_config(page_title="H2READY Toolkit", page_icon="🔷", layout="centered")

# =============================================================================
# 1. UTILITY DATI
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
    """Converte in float gestendo separatori italiani. None se non numerico."""
    if is_vuoto(v):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(" ", "").replace("\u00a0", "")
    s = re.sub(r"[^\d,.\-]", "", s)
    if not s:
        return None
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")      # 1.234,56
    elif "," in s:
        s = s.replace(",", ".")                        # 1234,56
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
    if up.startswith(("T27_SCORE", "T12_SCORE")) or "_N_" in up or up.startswith("T23_N_"):
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


def formatta(valore, colonna: str) -> str | None:
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


def livello_maturita(score: int) -> str:
    for lo, hi, lab in SOGLIE_MATURITA:
        if lo <= score <= hi:
            return lab
    return "L1"


def calcola_profilo(riga):
    """Deriva il profilo strategico dai punteggi T12_SCORE_A/B/C."""
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

# =============================================================================
# 2. LETTURA GOOGLE SHEET
# =============================================================================

@st.cache_data(ttl=120, show_spinner="Lettura del foglio dati in corso...")
def carica_dati() -> pd.DataFrame:
    conn = st.connection("gsheets", type=GSheetsConnection)
    kwargs = {"ttl": 0}
    try:
        cfg = st.secrets["connections"]["gsheets"]
        ha_spreadsheet = "spreadsheet" in cfg
        if "worksheet" in cfg:
            kwargs["worksheet"] = cfg["worksheet"]
    except Exception:
        ha_spreadsheet = False

    if not ha_spreadsheet:
        if not SPREADSHEET_URL:
            raise RuntimeError(
                "Foglio non configurato: aggiungi la chiave 'spreadsheet' nella "
                "sezione [connections.gsheets] dei secrets."
            )
        kwargs["spreadsheet"] = SPREADSHEET_URL

    df = conn.read(**kwargs)
    df.columns = [str(c).strip() for c in df.columns]
    return df.dropna(how="all")


@st.cache_data(show_spinner=False)
def leggi_md(filename: str) -> str:
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            return f.read()
    return f"> *[Contenuto non disponibile: manca il file `{filename}`]*"

# =============================================================================
# 3. MOTORE PDF
# =============================================================================

def pulisci(testo) -> str:
    if not isinstance(testo, str):
        testo = str(testo)
    sost = {
        "\u201c": '"', "\u201d": '"', "\u2018": "'", "\u2019": "'",
        "\u2013": "-", "\u2014": "-", "\u2026": "...", "\u20ac": "Euro",
        "\u2082": "2", "\u2083": "3", "\u2705": "-", "\u2022": "-",
        "\u00b7": "-", "\u2192": "->", "\u2264": "<=", "\u2265": ">=",
    }
    for a, b in sost.items():
        testo = testo.replace(a, b)
    return testo.encode("latin-1", "replace").decode("latin-1")


class H2ReadyPDF(FPDF):
    def __init__(self):
        super().__init__()
        self.pagina_piena = False
        self.pagine_piene = set()
        self.set_auto_page_break(True, margin=22)
        self.set_margins(20, 20, 20)
        self.unicode = False
        self._carica_font()

    def _carica_font(self):
        reg = os.path.join(FONT_DIR, "DejaVuSans.ttf")
        bol = os.path.join(FONT_DIR, "DejaVuSans-Bold.ttf")
        ita = os.path.join(FONT_DIR, "DejaVuSans-Oblique.ttf")
        if os.path.exists(reg) and os.path.exists(bol):
            self.add_font("DejaVu", "", reg)
            self.add_font("DejaVu", "B", bol)
            self.italico = os.path.exists(ita)
            if self.italico:
                self.add_font("DejaVu", "I", ita)
            self.unicode = True
        else:
            self.italico = True

    @property
    def famiglia(self):
        return "DejaVu" if self.unicode else "Arial"

    def txt(self, testo):
        return str(testo) if self.unicode else pulisci(testo)

    def font(self, stile="", size=11):
        if stile == "I" and not getattr(self, "italico", True):
            stile = ""
        self.set_font(self.famiglia, stile, size)

    def header(self):
        if self.page_no() == 1 or self.pagina_piena:
            return
        self.pagine_piene.discard(self.page_no())
        if os.path.exists(LOGO):
            self.image(LOGO, 20, 8, 22)
        self.font("B", 8)
        self.set_text_color(*GRIGIO)
        self.set_xy(45, 10)
        self.cell(0, 5, self.txt("H2READY - Interreg VI-A Italia-Slovenia"),
                  new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*BLU)
        self.line(20, 18, 190, 18)
        self.set_y(28)
        self.set_text_color(0, 0, 0)

    def footer(self):
        if self.page_no() in self.pagine_piene:
            return
        self.set_y(-15)
        self.font("I", 8)
        self.set_text_color(*GRIGIO)
        self.cell(0, 10, self.txt(f"Pagina {self.page_no()}  |  Action Plan H2READY"),
                  align="C")


def _inline(pdf, testo, size, h):
    for parte in re.split(r"(\*\*.+?\*\*)", testo):
        if parte.startswith("**") and parte.endswith("**"):
            pdf.font("B", size)
            pdf.write(h, pdf.txt(parte[2:-2]))
        else:
            pdf.font("", size)
            pdf.write(h, pdf.txt(parte))
    pdf.ln(h)


def _tabella(pdf, righe):
    dati = []
    for r in righe:
        celle = [c.strip() for c in r.strip().strip("|").split("|")]
        if all(re.fullmatch(r":?-{2,}:?", c) for c in celle if c):
            continue
        dati.append(celle)
    if not dati:
        return

    larghezza = pdf.w - pdf.l_margin - pdf.r_margin
    n = max(len(r) for r in dati)
    w = [larghezza * 0.60] + [(larghezza * 0.40) / max(n - 1, 1)] * (n - 1)

    for i, riga in enumerate(dati):
        testa = i == 0
        pdf.font("B" if testa else "", 9.5)
        if testa:
            pdf.set_fill_color(*BLU)
            pdf.set_text_color(255, 255, 255)
        else:
            pdf.set_fill_color(*((246, 248, 252) if i % 2 == 0 else (255, 255, 255)))
            pdf.set_text_color(0, 0, 0)

        alt = 7
        for j in range(n):
            testo = riga[j] if j < len(riga) else ""
            if pdf.get_string_width(pdf.txt(testo)) > w[j] - 4:
                alt = 11
        if pdf.get_y() + alt > pdf.h - 25:
            pdf.add_page()

        for j in range(n):
            testo = pdf.txt(riga[j] if j < len(riga) else "")
            if alt > 7 and pdf.get_string_width(testo) > w[j] - 4:
                x, y = pdf.get_x(), pdf.get_y()
                pdf.multi_cell(w[j], alt / 2, testo, border=1, fill=True,
                               align="L" if j == 0 else "R", max_line_height=alt / 2)
                pdf.set_xy(x + w[j], y)
            else:
                pdf.cell(w[j], alt, testo, border=1, fill=True,
                         align="L" if j == 0 else "R")
        pdf.ln(alt)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(3)


def scrivi_markdown(pdf, md: str):
    righe = md.split("\n")
    i = 0
    while i < len(righe):
        stripped = righe[i].strip()

        if not stripped:
            pdf.ln(4); i += 1; continue

        if stripped.startswith("|"):
            blocco = []
            while i < len(righe) and righe[i].strip().startswith("|"):
                blocco.append(righe[i]); i += 1
            _tabella(pdf, blocco)
            continue

        if re.fullmatch(r"-{3,}|_{3,}|\*{3,}", stripped):
            pdf.ln(2); pdf.set_draw_color(200, 205, 215)
            pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
            pdf.ln(4); i += 1; continue

        if stripped.startswith("####"):
            pdf.ln(2); pdf.font("B", 11); pdf.set_text_color(40, 40, 40)
            pdf.multi_cell(0, 7, pdf.txt(stripped.lstrip("#").strip()))
            pdf.set_text_color(0, 0, 0); pdf.ln(1)
        elif stripped.startswith("###"):
            pdf.ln(3); pdf.font("B", 12); pdf.set_text_color(*BLU)
            pdf.multi_cell(0, 8, pdf.txt(stripped.lstrip("#").strip()))
            pdf.set_text_color(0, 0, 0); pdf.ln(1)
        elif stripped.startswith("##"):
            pdf.ln(4); pdf.font("B", 14); pdf.set_text_color(*BLU)
            pdf.multi_cell(0, 9, pdf.txt(stripped.lstrip("#").strip()))
            pdf.set_draw_color(*BLU)
            pdf.line(pdf.l_margin, pdf.get_y() + 1, pdf.l_margin + 35, pdf.get_y() + 1)
            pdf.set_text_color(0, 0, 0); pdf.ln(4)
        elif stripped.startswith("#"):
            pdf.ln(2); pdf.font("B", 17); pdf.set_text_color(*BLU)
            pdf.multi_cell(0, 11, pdf.txt(stripped.lstrip("#").strip()))
            pdf.set_text_color(0, 0, 0); pdf.ln(3)

        elif stripped.startswith(">"):
            testo = stripped.lstrip(">").strip()
            y0 = pdf.get_y()
            pdf.set_fill_color(240, 243, 250); pdf.font("I", 10)
            pdf.set_x(pdf.l_margin + 4)
            pdf.multi_cell(pdf.w - pdf.l_margin - pdf.r_margin - 4, 6,
                           pdf.txt(testo), fill=True)
            pdf.set_draw_color(*BLU); pdf.set_line_width(1)
            pdf.line(pdf.l_margin + 1, y0, pdf.l_margin + 1, pdf.get_y())
            pdf.set_line_width(0.2); pdf.ln(3)

        elif re.match(r"^([-*+]|\d+[.)])\s+", stripped):
            marc = re.match(r"^([-*+]|\d+[.)])\s+", stripped).group(1)
            testo = re.sub(r"^([-*+]|\d+[.)])\s+", "", stripped)
            pdf.font("B", 11)
            pdf.cell(7, 6, pdf.txt("-" if marc in "-*+" else marc))
            pdf.set_x(pdf.l_margin + 7)
            pdf.set_left_margin(pdf.get_x())
            _inline(pdf, testo, 11, 6)
            pdf.set_left_margin(20); pdf.ln(1)

        else:
            _inline(pdf, stripped, 11, 6.5)
            pdf.ln(2)
        i += 1


def pagina_divisoria(pdf, occhiello, titolo, sottotitolo=""):
    pdf.pagina_piena = True
    pdf.add_page()
    pdf.pagine_piene.add(pdf.page_no())
    pdf.set_fill_color(*BLU)
    pdf.rect(0, 0, 210, 297, "F")
    pdf.set_text_color(255, 255, 255)
    pdf.set_y(110)
    pdf.font("B", 13)
    pdf.cell(0, 8, pdf.txt(occhiello.upper()), align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    pdf.set_draw_color(255, 255, 255)
    pdf.line(85, pdf.get_y(), 125, pdf.get_y())
    pdf.ln(10)
    pdf.font("B", 22)
    pdf.multi_cell(0, 12, pdf.txt(titolo), align="C")
    if sottotitolo:
        pdf.ln(6); pdf.font("", 12)
        pdf.multi_cell(0, 7, pdf.txt(sottotitolo), align="C")
    pdf.set_text_color(0, 0, 0)
    pdf.pagina_piena = False


def copertina(pdf, comune, livello, profilo):
    pdf.pagina_piena = True
    pdf.add_page()
    pdf.pagine_piene.add(pdf.page_no())
    pdf.set_fill_color(*BLU)
    pdf.rect(0, 0, 12, 297, "F")
    pdf.rect(0, 250, 210, 47, "F")
    if os.path.exists(LOGO):
        pdf.image(LOGO, x=75, y=32, w=60)

    pdf.set_y(105); pdf.font("", 16); pdf.set_text_color(*GRIGIO)
    pdf.cell(0, 10, pdf.txt("ACTION PLAN"), align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.font("B", 38); pdf.set_text_color(*BLU)
    pdf.cell(0, 20, pdf.txt("H2READY"), align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(18); pdf.font("B", 24); pdf.set_text_color(20, 20, 20)
    pdf.multi_cell(0, 13, pdf.txt(f"COMUNE DI {str(comune).upper()}"), align="C")
    pdf.ln(6); pdf.font("", 12); pdf.set_text_color(*GRIGIO)
    pdf.cell(0, 7, pdf.txt(f"Livello di maturità: {livello}   |   Profilo strategico: {profilo}"),
             align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, pdf.txt(f"Documento generato il {date.today().strftime('%d/%m/%Y')}"),
             align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.set_y(262); pdf.set_text_color(255, 255, 255); pdf.font("B", 11)
    pdf.cell(0, 6, pdf.txt("Documento strategico di transizione energetica"),
             align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.font("", 10)
    pdf.cell(0, 6, pdf.txt("Progetto cofinanziato dall'Unione Europea - Interreg VI-A Italia-Slovenia"),
             align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.pagina_piena = False

# =============================================================================
# 4. CONTENUTI DINAMICI
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
        out.append("")
        out.append("La compresenza di più vocazioni indica un territorio in cui le azioni "
                   "vanno coordinate fra loro: la scala e la sequenza degli interventi "
                   "contano quanto la loro natura.")
    return "\n".join(out)


def testo_passo2(riga) -> str:
    out = ["# Sintesi dei risultati tecnici",
           "I valori derivano dai questionari e dagli strumenti di calcolo del Toolkit "
           "H2READY. I campi non compilati non compaiono nelle tabelle.", ""]
    totale = 0

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
        for titolo_blocco, righe in blocchi_pieni:
            totale += len(righe)
            out.append(f"### {titolo_blocco}")
            out += ["| Parametro | Valore |", "| --- | --- |"] + righe + [""]

    # Colonne presenti nel foglio ma non previste nei percorsi
    note = [c for c in riga.index
            if c not in ESCLUSE and c not in FLAG_GOVERNANCE
            and not any(c in cols for p in PERCORSI for _, cols in p["blocchi"])
            and not is_vuoto(riga[c])]
    if note:
        out.append("## Altri dati disponibili")
        out += ["| Parametro | Valore |", "| --- | --- |"]
        out += [f"| {etichetta(c)} | {formatta(riga[c], c)} |" for c in note]
        out.append("")

    if totale == 0:
        out.append("> Nessun dato tecnico disponibile: verificare la compilazione dei "
                   "questionari per questo Comune.")
    return "\n".join(out)


def _tot(riga, colonne):
    valori = [numero(riga[c]) for c in colonne if c in riga.index]
    valori = [v for v in valori if v is not None]
    return sum(valori) if valori else None


def testo_passo3(riga, livello, profilo) -> str:
    dedicato = f"5-incrocio_{livello}_{profilo}_it.md"
    if os.path.exists(dedicato):
        return leggi_md(dedicato)

    out = ["# Analisi incrociata",
           "Il confronto fra i risultati dei tre percorsi verifica la coerenza interna "
           "dello scenario e individua i punti su cui concentrare le decisioni.", ""]

    domanda = _tot(riga, ["T21_FABBISOGNO_H2_TON_ANNO", "T22_FABBISOGNO_H2_TON_ANNO"])
    offerta = numero(riga.get("T26_PRODUZIONE_H2_TON_ANNO"))
    hrs_kg = numero(riga.get("T28_CAPACITA_KG_GIORNO"))
    hrs_t = hrs_kg * 365 / 1000 if hrs_kg else None

    # --- bilancio domanda / offerta
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
            saldo = offerta - domanda
            cop = offerta / domanda * 100
            out.append(f"| Saldo | {formatta_numero(saldo)} t/anno |")
            out.append(f"| Copertura della domanda | {formatta_numero(cop)}% |")
        out.append("")

        if domanda and offerta:
            cop = offerta / domanda * 100
            if cop >= 110:
                out.append("La produzione potenziale **eccede la domanda locale**. Il "
                           "surplus può alimentare utenze di Comuni limitrofi o il "
                           "traffico di transito, ma richiede di verificare l'esistenza "
                           "di contratti di acquisto prima di dimensionare l'impianto "
                           "sul massimo teorico.")
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

    # --- coerenza economica
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
                       "contributo pubblico in conto capitale o senza un aumento dei "
                       "volumi la configurazione non è sostenibile.")
        out.append("")

    # --- vincoli territoriali
    vincoli = []
    if str(riga.get("T25_FLAG_CONTESTAZIONI", "")).strip().lower() in ("si", "sì", "true", "1"):
        vincoli.append("Sono presenti contenziosi o opposizioni su impianti rinnovabili: "
                       "il percorso partecipativo va avviato prima della progettazione.")
    cap = numero(riga.get("T25_CAPACITA_RESIDUA_MW"))
    tag = numero(riga.get("T26_TAGLIA_ELETTROLIZZATORE_MW"))
    if cap is not None and tag is not None and tag > cap:
        vincoli.append(f"La taglia dell'elettrolizzatore ({formatta_numero(tag)} MW) supera "
                       f"la capacità residua di rete ({formatta_numero(cap)} MW): serve un "
                       "confronto preventivo con il distributore.")
    sau = numero(riga.get("T25_SAU_OCCUPATA_PERC"))
    if sau is not None and sau > 10:
        vincoli.append(f"La quota di superficie agricola già occupata da impianti "
                       f"({formatta_numero(sau)}%) suggerisce di privilegiare coperture e "
                       "aree dismesse rispetto al fotovoltaico a terra.")
    if vincoli:
        out.append("## Vincoli e attenzioni")
        out += [f"- {v}" for v in vincoli]
        out.append("")

    # --- governance
    gov = [(etichetta(c), formatta(riga[c], c)) for c in FLAG_GOVERNANCE
           if c in riga.index and formatta(riga[c], c)]
    if gov:
        out.append("## Contesto di governance")
        out += ["| Elemento | Stato |", "| --- | --- |"]
        out += [f"| {e} | {v} |" for e, v in gov]
        out.append("")

    priorita = {
        "L1": "consolidare le basi conoscitive e amministrative prima di impegnare capitale",
        "L2": "trasformare gli studi disponibili in progetti cantierabili e finanziabili",
        "L3": "passare alla realizzazione e all'aggregazione della domanda su scala sovracomunale",
    }
    out.append("## Lettura d'insieme")
    out.append(f"Con un livello di maturità **{livello}** e un profilo **{profilo or 'non determinato'}**, "
               f"la priorità operativa è {priorita.get(livello, priorita['L1'])}.")
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
             "pluriennale, che è la condizione per rendere bancabile qualunque impianto.",
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
    out += [f"| {t} | {a} |" for t, a in base.get(livello, base["L1"])]
    out.append("")

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
            "> Il presente Action Plan è un documento vivo: va aggiornato a ogni "
            "variazione rilevante del quadro normativo, tecnologico o finanziario."]
    return "\n".join(out)

# =============================================================================
# 5. ASSEMBLAGGIO PDF
# =============================================================================

def genera_pdf(riga, c: dict) -> bytes:
    pdf = H2ReadyPDF()
    comune = str(riga[COL_NOME])

    copertina(pdf, comune, c["livello"], c["profilo"] or "n.d.")
    pdf.add_page(); scrivi_markdown(pdf, c["intro"])
    pdf.add_page(); scrivi_markdown(pdf, c["struttura"])

    pagina_divisoria(pdf, "Passo 1", "Livello di maturità e profilo strategico",
                     f"Comune di {comune}")
    pdf.add_page()
    scrivi_markdown(pdf, c["mat_intro"]); pdf.ln(4)
    scrivi_markdown(pdf, c["mat_dettaglio"]); pdf.ln(6)
    scrivi_markdown(pdf, c["profilo_intro"]); pdf.ln(4)
    scrivi_markdown(pdf, c["profilo_calcolato"]); pdf.ln(4)
    scrivi_markdown(pdf, c["profilo_dettaglio"])

    pagina_divisoria(pdf, "Passo 2", "Risultato dei percorsi identificati")
    pdf.add_page(); scrivi_markdown(pdf, c["passo2"])

    pagina_divisoria(pdf, "Passo 3", "Analisi incrociata")
    pdf.add_page(); scrivi_markdown(pdf, c["passo3"])

    pagina_divisoria(pdf, "Passo 4", "Elaborazione finale su misura")
    pdf.add_page(); scrivi_markdown(pdf, c["passo4"])

    return bytes(pdf.output())

# =============================================================================
# 6. INTERFACCIA
# =============================================================================

st.markdown(
    '<div style="background:linear-gradient(90deg,#003399,#0057c2);padding:22px;'
    'border-radius:12px;text-align:center">'
    '<h1 style="color:white;margin:0;letter-spacing:1px">H2READY TOOLKIT</h1>'
    '<p style="color:#cddafc;margin:4px 0 0">Generatore di Action Plan comunali</p></div>',
    unsafe_allow_html=True)
st.write("")

try:
    df = carica_dati()
except Exception as e:
    st.error(f"Impossibile leggere il foglio dati.\n\n{e}")
    st.stop()

mancanti = [c for c in (COL_ID, COL_NOME, COL_MATURITA) if c not in df.columns]
if mancanti:
    st.error(f"Colonne obbligatorie assenti: {', '.join(mancanti)}")
    st.write(list(df.columns)); st.stop()

col_a, col_b = st.columns(2)
with col_a:
    id_ricercato = st.text_input("ID_ISTAT", placeholder="es. 093001")
with col_b:
    elenco = ["-"] + sorted(df[COL_NOME].dropna().astype(str).unique().tolist())
    scelta = st.selectbox("oppure seleziona il Comune", elenco)

if scelta != "-":
    res = df[df[COL_NOME].astype(str).str.strip() == scelta]
elif id_ricercato.strip():
    res = df[df[COL_ID].astype(str).str.strip() == id_ricercato.strip()]
else:
    st.info("Inserisci un ID_ISTAT o seleziona un Comune."); st.stop()

if res.empty:
    st.warning("Nessun Comune corrispondente."); st.stop()

riga = res.iloc[0]
score = int(numero(riga[COL_MATURITA]) or 0)
livello = livello_maturita(score)
profilo, punteggi = calcola_profilo(riga)

m1, m2, m3 = st.columns(3)
m1.metric("Comune", str(riga[COL_NOME]))
m2.metric("Maturità", f"{score} ({livello})")
m3.metric("Profilo", profilo or "n.d.")

if punteggi:
    st.caption("Punteggi di profilo: " +
               "  ".join(f"{l} = {formatta_numero(v)}" for l, v in punteggi.items()))

if score < SOGLIA_MINIMA:
    st.error("Comune in Livello 0: Action Plan non generabile.")
    st.stop()

profilo_file = f"4-profilo_{profilo}_it.md" if profilo else ""
contenuti = {
    "livello": livello,
    "profilo": profilo,
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

attesi = ["1-intro_it.md", "2-struttura_plan_it.md", "3-maturita_intro_it.md",
          f"3-maturita_{livello}_it.md", "4-profilo_intro_it.md"]
if profilo:
    attesi.append(profilo_file)
assenti = [f for f in attesi if not os.path.exists(f)]
if assenti:
    st.warning("File di testo mancanti (verranno inseriti dei segnaposto): " + ", ".join(assenti))

with st.expander("Anteprima Passo 2 - dati tecnici"):
    st.markdown(contenuti["passo2"])
with st.expander("Anteprima Passo 3 - analisi incrociata"):
    st.markdown(contenuti["passo3"])
with st.expander("Diagnostica colonne"):
    previste = {c for p in PERCORSI for _, cols in p["blocchi"] for c in cols}
    st.write("**Previste ma assenti nel foglio:**", sorted(previste - set(df.columns)) or "nessuna")
    st.write("**Nel foglio ma non collocate nei percorsi:**",
             sorted(set(df.columns) - previste - ESCLUSE - set(FLAG_GOVERNANCE)) or "nessuna")

if st.button("Genera Action Plan", type="primary", use_container_width=True):
    with st.spinner("Composizione del documento..."):
        st.session_state["pdf"] = genera_pdf(riga, contenuti)
        st.session_state["nome"] = f"H2READY_ActionPlan_{slug(riga[COL_NOME])}.pdf"

if "pdf" in st.session_state:
    st.download_button("Scarica il PDF", data=st.session_state["pdf"],
                       file_name=st.session_state.get("nome", "action_plan.pdf"),
                       mime="application/pdf", use_container_width=True)
