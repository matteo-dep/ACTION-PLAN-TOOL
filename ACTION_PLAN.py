"""
H2READY TOOLKIT - Generatore Action Plan comunali
Progetto Interreg VI-A Italia-Slovenia ITA-SI0800335

Struttura documento:
  Copertina -> Introduzione -> Struttura del Piano
  PASSO 1: Maturità + Profilo strategico   (testi statici da file .md)
  PASSO 2: Risultati dei percorsi           (dati dinamici dal foglio)
  PASSO 3: Analisi incrociata               (regole maturità x profilo)
  PASSO 4: Elaborazione finale su misura    (roadmap + prossimi passi)
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

# Fallback: se non usi secrets.toml, incolla qui l'URL del foglio.
SPREADSHEET_URL = ""

#SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1AbCdEf.../edit#gid=0"

LOGO = "logo_h2ready.png"
FONT_DIR = "fonts"                       # opzionale: DejaVuSans.ttf / -Bold / -Oblique
BLU = (0, 51, 153)
GRIGIO = (110, 110, 110)

COL_ID = "ID_ISTAT"
COL_NOME = "NOME_COMUNE"
COL_MATURITA = "T11_LIVELLO_MATURITA"
COL_PROFILO = "T12_PROFILO_STRATEGICO"

SOGLIE_MATURITA = [(3, 8, "L1"), (9, 14, "L2"), (15, 99, "L3")]
SOGLIA_MINIMA = 3

# --- Mappa dei dati tecnici (PASSO 2) -----------------------------------------
# Adatta i nomi delle colonne a quelli reali dell'"excelone".
# tipo: "testo" | "num" | "eur" | "pct" | "si_no"
# I campi assenti nel foglio o vuoti vengono semplicemente saltati.
SEZIONI_TECNICHE = [
    {
        "titolo": "Inquadramento territoriale",
        "campi": [
            ("NOME_COMUNE",        "Comune",                          "testo", ""),
            ("PROVINCIA",          "Provincia",                       "testo", ""),
            ("POPOLAZIONE",        "Popolazione residente",           "num",   "ab."),
            ("SUPERFICIE_KMQ",     "Superficie",                      "num",   "km2"),
            ("ALTITUDINE",         "Altitudine",                      "num",   "m s.l.m."),
        ],
    },
    {
        "titolo": "Percorso 1 - Domanda di idrogeno",
        "campi": [
            ("T21_FLOTTA_TOT",     "Veicoli flotta comunale",         "num",   "mezzi"),
            ("T21_BUS",            "Autobus / scuolabus",             "num",   "mezzi"),
            ("T21_MEZZI_PESANTI",  "Mezzi pesanti e servizi",         "num",   "mezzi"),
            ("T21_KM_ANNUI",       "Percorrenza annua flotta",        "num",   "km/anno"),
            ("T21_H2_DOMANDA",     "Fabbisogno stimato di H2",        "num",   "kg/anno"),
            ("T21_EDIFICI_ENERG",  "Edifici pubblici energivori",     "num",   "edifici"),
        ],
    },
    {
        "titolo": "Percorso 2 - Offerta e produzione",
        "campi": [
            ("T22_FER_INSTALLATA", "Potenza FER installata",          "num",   "kW"),
            ("T22_FV_POTENZIALE",  "Potenziale fotovoltaico su tetti","num",   "kW"),
            ("T22_CER",            "Comunità energetica attiva",     "si_no", ""),
            ("T22_ELETTROLIZZ",    "Elettrolizzatore ipotizzato",     "num",   "kW"),
            ("T22_H2_PRODUCIBILE", "Produzione potenziale di H2",     "num",   "kg/anno"),
        ],
    },
    {
        "titolo": "Percorso 3 - Logistica e infrastrutture",
        "campi": [
            ("T23_AREA_DISP",      "Area disponibile per impianto",   "num",   "m2"),
            ("T23_DIST_RETE",      "Distanza da cabina primaria",     "num",   "km"),
            ("T23_CORRIDOIO_TEN",  "Prossimità a corridoio TEN-T",   "si_no", ""),
            ("T23_HRS_ESISTENTI",  "HRS esistenti entro 50 km",       "num",   "impianti"),
            ("T23_CAPEX",          "CAPEX preliminare stimato",       "eur",   ""),
        ],
    },
    {
        "titolo": "Governance e strumenti di pianificazione",
        "campi": [
            ("T24_PAESC",          "PAESC approvato",                 "si_no", ""),
            ("T24_UFFICIO_ENERGIA","Ufficio energia / energy manager","si_no", ""),
            ("T24_PROGETTI_UE",    "Progetti UE già realizzati",     "num",   "progetti"),
            ("T24_BUDGET",         "Capacità di cofinanziamento",    "eur",   ""),
        ],
    },
]

st.set_page_config(page_title="H2READY Toolkit", page_icon="🔷", layout="centered")

# =============================================================================
# 1. UTILITY DATI
# =============================================================================

def is_vuoto(v) -> bool:
    if v is None:
        return True
    if isinstance(v, float) and pd.isna(v):
        return True
    return str(v).strip().lower() in ("", "nan", "none", "n/a", "-", "na")


def fmt_valore(v, tipo, unita=""):
    """Formatta un valore secondo il tipo dichiarato. Ritorna None se vuoto."""
    if is_vuoto(v):
        return None
    s = str(v).strip()

    if tipo == "si_no":
        pos = {"si", "sì", "yes", "y", "true", "1", "vero", "x"}
        neg = {"no", "n", "false", "0", "falso"}
        low = s.lower()
        if low in pos:
            return "Si"
        if low in neg:
            return "No"
        return s

    if tipo in ("num", "eur", "pct"):
        try:
            num = float(s.replace(".", "").replace(",", ".")) if "," in s else float(s)
        except ValueError:
            return s
        if abs(num - round(num)) < 1e-9:
            testo = f"{int(round(num)):,}".replace(",", ".")
        else:
            testo = f"{num:,.2f}".replace(",", "@").replace(".", ",").replace("@", ".")
        if tipo == "eur":
            return f"Euro {testo}"
        if tipo == "pct":
            return f"{testo}%"
        return f"{testo} {unita}".strip()

    return s


def livello_maturita(score: int) -> str:
    for lo, hi, lab in SOGLIE_MATURITA:
        if lo <= score <= hi:
            return lab
    return "L1"


def normalizza_profilo(raw: str) -> str:
    """'Profilo A+B' / 'PROFILO a-b' -> 'AB'"""
    s = str(raw).upper()
    s = re.sub(r"PROFILO", "", s)
    s = re.sub(r"[^A-Z0-9]", "", s)
    return s.strip()


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

    # Se i secrets non contengono lo spreadsheet, usa la costante di fallback.
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
                "Foglio non configurato. Aggiungi in .streamlit/secrets.toml:\n\n"
                '[connections.gsheets]\n'
                'spreadsheet = "https://docs.google.com/spreadsheets/d/.../edit"\n\n'
                "oppure valorizza la costante SPREADSHEET_URL in cima al file."
            )
        kwargs["spreadsheet"] = SPREADSHEET_URL

    df = conn.read(**kwargs)
    df.columns = [str(c).strip() for c in df.columns]
    df = df.dropna(how="all")
    return df


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
    """Sostituisce i caratteri non latin-1 (necessario con i font core di FPDF)."""
    if not isinstance(testo, str):
        testo = str(testo)
    sost = {
        "\u201c": '"', "\u201d": '"', "\u2018": "'", "\u2019": "'",
        "\u2013": "-", "\u2014": "-", "\u2026": "...",
        "\u20ac": "Euro", "\u2082": "2", "\u2083": "3",
        "\u2705": "-", "\u2022": "-", "\u00b7": "-", "\u2192": "->",
        "\u2264": "<=", "\u2265": ">=", "\u00b2": "2", "\u00b3": "3",
    }
    for a, b in sost.items():
        testo = testo.replace(a, b)
    return testo.encode("latin-1", "replace").decode("latin-1")


class H2ReadyPDF(FPDF):
    """PDF con intestazione/piè di pagina, disattivabili sulle pagine divisorie."""

    def __init__(self):
        super().__init__()
        self.pagina_piena = False          # True mentre si compone una pagina blu
        self.pagine_piene = set()          # numeri delle pagine a fondo pieno
        self.set_auto_page_break(True, margin=22)
        self.set_margins(20, 20, 20)
        self.unicode = False
        self._carica_font()

    def _carica_font(self):
        """Se sono presenti i TTF DejaVu usa Unicode (H₂, €, caratteri sloveni)."""
        regular = os.path.join(FONT_DIR, "DejaVuSans.ttf")
        bold = os.path.join(FONT_DIR, "DejaVuSans-Bold.ttf")
        italic = os.path.join(FONT_DIR, "DejaVuSans-Oblique.ttf")
        if os.path.exists(regular) and os.path.exists(bold):
            self.add_font("DejaVu", "", regular)
            self.add_font("DejaVu", "B", bold)
            if os.path.exists(italic):
                self.add_font("DejaVu", "I", italic)
            self.unicode = True

    @property
    def famiglia(self):
        return "DejaVu" if self.unicode else "Arial"

    def txt(self, testo):
        return str(testo) if self.unicode else pulisci(testo)

    def font(self, stile="", size=11):
        if self.unicode and stile == "I" and not os.path.exists(
            os.path.join(FONT_DIR, "DejaVuSans-Oblique.ttf")
        ):
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


# --- Rendering Markdown -> PDF ------------------------------------------------

def _inline(pdf: H2ReadyPDF, testo: str, size: int, h: float):
    """Scrive un paragrafo gestendo il grassetto **testo**."""
    parti = re.split(r"(\*\*.+?\*\*)", testo)
    for parte in parti:
        if parte.startswith("**") and parte.endswith("**"):
            pdf.font("B", size)
            pdf.write(h, pdf.txt(parte[2:-2]))
        else:
            pdf.font("", size)
            pdf.write(h, pdf.txt(parte))
    pdf.ln(h)


def _tabella(pdf: H2ReadyPDF, righe):
    """Rende un blocco di righe markdown '| a | b |' come tabella a due colonne."""
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
    w_col = [larghezza * 0.55] + [(larghezza * 0.45) / max(n - 1, 1)] * (n - 1)

    for i, riga in enumerate(dati):
        intestazione = i == 0
        pdf.font("B" if intestazione else "", 9.5)
        if intestazione:
            pdf.set_fill_color(*BLU)
            pdf.set_text_color(255, 255, 255)
        else:
            pdf.set_fill_color(245, 247, 252) if i % 2 == 0 else pdf.set_fill_color(255, 255, 255)
            pdf.set_text_color(0, 0, 0)
        for j in range(n):
            testo = riga[j] if j < len(riga) else ""
            pdf.cell(w_col[j], 8, pdf.txt(testo), border=1, fill=True,
                     align="L" if j == 0 else "R")
        pdf.ln(8)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(3)


def scrivi_markdown(pdf: H2ReadyPDF, md: str):
    righe = md.split("\n")
    i = 0
    while i < len(righe):
        riga = righe[i].rstrip()
        stripped = riga.strip()

        if not stripped:
            pdf.ln(4)
            i += 1
            continue

        # Tabella
        if stripped.startswith("|"):
            blocco = []
            while i < len(righe) and righe[i].strip().startswith("|"):
                blocco.append(righe[i])
                i += 1
            _tabella(pdf, blocco)
            continue

        # Linea orizzontale
        if re.fullmatch(r"-{3,}|_{3,}|\*{3,}", stripped):
            pdf.ln(2)
            pdf.set_draw_color(200, 205, 215)
            pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
            pdf.ln(4)
            i += 1
            continue

        # Titoli
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

        # Citazione / nota
        elif stripped.startswith(">"):
            testo = stripped.lstrip(">").strip()
            y0 = pdf.get_y()
            pdf.set_fill_color(240, 243, 250)
            pdf.font("I", 10)
            pdf.set_x(pdf.l_margin + 4)
            pdf.multi_cell(pdf.w - pdf.l_margin - pdf.r_margin - 4, 6,
                           pdf.txt(testo), fill=True)
            pdf.set_draw_color(*BLU)
            pdf.set_line_width(1)
            pdf.line(pdf.l_margin + 1, y0, pdf.l_margin + 1, pdf.get_y())
            pdf.set_line_width(0.2)
            pdf.ln(3)

        # Elenchi
        elif re.match(r"^([-*+]|\d+[.)])\s+", stripped):
            marcatore = re.match(r"^([-*+]|\d+[.)])\s+", stripped).group(1)
            testo = re.sub(r"^([-*+]|\d+[.)])\s+", "", stripped)
            bullet = "-" if marcatore in "-*+" else marcatore
            pdf.font("B", 11)
            pdf.cell(7, 6, pdf.txt(bullet))
            pdf.set_x(pdf.l_margin + 7)
            x_start = pdf.get_x()
            pdf.font("", 11)
            pdf.set_left_margin(x_start)
            _inline(pdf, testo, 11, 6)
            pdf.set_left_margin(20)
            pdf.ln(1)

        # Paragrafo
        else:
            _inline(pdf, stripped, 11, 6.5)
            pdf.ln(2)

        i += 1


def pagina_divisoria(pdf: H2ReadyPDF, occhiello: str, titolo: str, sottotitolo: str = ""):
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
        pdf.ln(6)
        pdf.font("", 12)
        pdf.multi_cell(0, 7, pdf.txt(sottotitolo), align="C")

    pdf.set_text_color(0, 0, 0)
    pdf.pagina_piena = False


def copertina(pdf: H2ReadyPDF, comune: str, livello: str, profilo: str):
    pdf.pagina_piena = True
    pdf.add_page()
    pdf.pagine_piene.add(pdf.page_no())
    pdf.set_fill_color(*BLU)
    pdf.rect(0, 0, 12, 297, "F")
    pdf.rect(0, 250, 210, 47, "F")

    if os.path.exists(LOGO):
        pdf.image(LOGO, x=75, y=32, w=60)

    pdf.set_y(105)
    pdf.font("", 16)
    pdf.set_text_color(*GRIGIO)
    pdf.cell(0, 10, pdf.txt("ACTION PLAN"), align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.font("B", 38)
    pdf.set_text_color(*BLU)
    pdf.cell(0, 20, pdf.txt("H2READY"), align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(18)
    pdf.font("B", 24)
    pdf.set_text_color(20, 20, 20)
    pdf.multi_cell(0, 13, pdf.txt(f"COMUNE DI {comune.upper()}"), align="C")

    pdf.ln(6)
    pdf.font("", 12)
    pdf.set_text_color(*GRIGIO)
    pdf.cell(0, 7, pdf.txt(f"Livello di maturità: {livello}   |   Profilo strategico: {profilo}"),
             align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, pdf.txt(f"Documento generato il {date.today().strftime('%d/%m/%Y')}"),
             align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.set_y(262)
    pdf.set_text_color(255, 255, 255)
    pdf.font("B", 11)
    pdf.cell(0, 6, pdf.txt("Documento strategico di transizione energetica"),
             align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.font("", 10)
    pdf.cell(0, 6, pdf.txt("Progetto cofinanziato dall'Unione Europea - Interreg VI-A Italia-Slovenia"),
             align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.set_text_color(0, 0, 0)
    pdf.pagina_piena = False

# =============================================================================
# 4. COSTRUZIONE DEI CONTENUTI DINAMICI
# =============================================================================

def testo_passo2(riga) -> str:
    """Costruisce il PASSO 2 leggendo i valori reali dal foglio."""
    out = ["# Sintesi dei risultati tecnici",
           "I dati riportati derivano dai questionari e dagli strumenti di calcolo del "
           "Toolkit H2READY. I campi non compilati non compaiono in tabella.", ""]
    trovati = 0

    for sezione in SEZIONI_TECNICHE:
        righe = []
        for col, etichetta, tipo, unita in sezione["campi"]:
            if col not in riga.index:
                continue
            valore = fmt_valore(riga[col], tipo, unita)
            if valore is None:
                continue
            righe.append(f"| {etichetta} | {valore} |")
        if righe:
            trovati += len(righe)
            out.append(f"## {sezione['titolo']}")
            out.append("| Parametro | Valore |")
            out.append("| --- | --- |")
            out.extend(righe)
            out.append("")

    if trovati == 0:
        out.append("> Nessun dato tecnico disponibile per questo Comune: verificare la "
                   "compilazione dei questionari e la mappatura delle colonne nel toolkit.")
    return "\n".join(out)


def testo_passo3(livello: str, profilo: str) -> str:
    """Analisi incrociata maturità x profilo. Prova prima il file dedicato."""
    dedicato = f"5-incrocio_{livello}_{profilo}_it.md"
    if os.path.exists(dedicato):
        return leggi_md(dedicato)

    priorita = {
        "L1": "consolidare le basi conoscitive e amministrative prima di impegnare capitale.",
        "L2": "trasformare gli studi già disponibili in progetti cantierabili e finanziabili.",
        "L3": "passare alla realizzazione e all'aggregazione della domanda su scala sovracomunale.",
    }
    vocazione = {
        "A": "consumo (utilizzo finale nella flotta e negli edifici pubblici)",
        "B": "produzione (generazione locale di idrogeno da fonti rinnovabili)",
        "C": "transito (hub logistico lungo le direttrici di traffico)",
    }
    lettere = [vocazione.get(c) for c in profilo if vocazione.get(c)]
    if not lettere:
        lettere = ["vocazione da confermare in sede di approfondimento"]

    return "\n".join([
        "# Analisi incrociata",
        "L'incrocio tra il livello di maturità e il profilo strategico definisce "
        "l'ordine di priorità delle azioni proposte nel Passo 4.",
        "",
        f"## Livello {livello}",
        f"La priorità operativa e' {priorita.get(livello, priorita['L1'])}",
        "",
        f"## Profilo {profilo}",
        "Il Comune presenta una vocazione prevalente di:",
        *[f"- {x}" for x in lettere],
        "",
        "## Implicazioni",
        "- **Sequenza temporale**: le azioni del livello superiore restano valide come "
        "traguardo, ma vanno attivate solo dopo il completamento delle azioni abilitanti.",
        "- **Aggregazione**: dove il fabbisogno locale non raggiunge la massa critica, "
        "si valuta la cooperazione con i Comuni limitrofi e con il partenariato transfrontaliero.",
        "- **Finanziabilità**: la coerenza con PAESC e con la Strategia Regionale Idrogeno "
        "è condizione per l'accesso ai principali strumenti di sostegno.",
    ])


def testo_passo4(riga, livello: str, profilo: str) -> str:
    dedicato = f"6-finale_{livello}_{profilo}_it.md"
    if os.path.exists(dedicato):
        return leggi_md(dedicato)

    azioni = {
        "L1": [
            ("0-6 mesi",  "Nomina di un referente interno per la transizione energetica"),
            ("6-12 mesi", "Completamento del bilancio energetico comunale e del catasto flotte"),
            ("12-24 mesi","Adesione o aggiornamento del PAESC con un capitolo dedicato all'idrogeno"),
            ("24-36 mesi","Studio di prefattibilita' su un primo caso d'uso dimostrativo"),
        ],
        "L2": [
            ("0-6 mesi",  "Selezione del caso d'uso prioritario e definizione del perimetro tecnico"),
            ("6-12 mesi", "Studio di fattibilita' tecnico-economica con analisi CAPEX/OPEX"),
            ("12-24 mesi","Individuazione dell'area idonea e avvio dell'iter autorizzativo"),
            ("24-36 mesi","Candidatura a bandi regionali, nazionali o europei"),
        ],
        "L3": [
            ("0-6 mesi",  "Definizione del modello di business e della struttura di governance"),
            ("6-12 mesi", "Progettazione definitiva e chiusura del piano finanziario"),
            ("12-24 mesi","Gara e affidamento, anche in forma aggregata tra Comuni"),
            ("24-36 mesi","Realizzazione, messa in esercizio e monitoraggio delle prestazioni"),
        ],
    }
    lista = azioni.get(livello, azioni["L1"])
    return "\n".join([
        "# Roadmap operativa su misura",
        f"Percorso proposto per il Comune di **{riga[COL_NOME]}** "
        f"(livello {livello}, profilo {profilo}).",
        "",
        "## Cronoprogramma indicativo",
        "| Orizzonte | Azione |",
        "| --- | --- |",
        *[f"| {t} | {a} |" for t, a in lista],
        "",
        "## Fattori abilitanti",
        "- **Competenze**: formazione del personale tecnico attraverso il programma H2READY.",
        "- **Risorse**: capacita' di cofinanziamento e ricorso a strumenti di finanza agevolata.",
        "- **Partenariato**: coinvolgimento di utility, trasporto pubblico locale e imprese del territorio.",
        "",
        "## Indicatori di monitoraggio",
        "| Indicatore | Unità |",
        "| --- | --- |",
        "| Idrogeno consumato dai servizi comunali | kg/anno |",
        "| Emissioni di CO2 evitate | t/anno |",
        "| Quota rinnovabile dell'idrogeno impiegato | % |",
        "| Investimento attivato sul territorio | Euro |",
        "",
        "> Il presente Action Plan è un documento vivo: va aggiornato a ogni variazione "
        "significativa del quadro normativo, tecnologico o finanziario.",
    ])

# =============================================================================
# 5. ASSEMBLAGGIO DEL PDF
# =============================================================================

def genera_pdf(riga, contenuti: dict) -> bytes:
    pdf = H2ReadyPDF()
    comune = str(riga[COL_NOME])

    copertina(pdf, comune, contenuti["livello"], contenuti["profilo"])

    pdf.add_page()
    scrivi_markdown(pdf, contenuti["intro"])

    pdf.add_page()
    scrivi_markdown(pdf, contenuti["struttura"])

    pagina_divisoria(pdf, "Passo 1",
                     "Livello di maturità e profilo strategico",
                     f"Comune di {comune}")
    pdf.add_page()
    scrivi_markdown(pdf, contenuti["mat_intro"])
    pdf.ln(4)
    scrivi_markdown(pdf, contenuti["mat_dettaglio"])
    pdf.ln(6)
    scrivi_markdown(pdf, contenuti["profilo_intro"])
    pdf.ln(4)
    scrivi_markdown(pdf, contenuti["profilo_dettaglio"])

    pagina_divisoria(pdf, "Passo 2", "Risultato dei percorsi identificati")
    pdf.add_page()
    scrivi_markdown(pdf, contenuti["passo2"])

    pagina_divisoria(pdf, "Passo 3", "Analisi incrociata")
    pdf.add_page()
    scrivi_markdown(pdf, contenuti["passo3"])

    pagina_divisoria(pdf, "Passo 4", "Elaborazione finale su misura")
    pdf.add_page()
    scrivi_markdown(pdf, contenuti["passo4"])

    return bytes(pdf.output())

# =============================================================================
# 6. INTERFACCIA
# =============================================================================

st.markdown(
    '<div style="background:linear-gradient(90deg,#003399,#0057c2);padding:22px;'
    'border-radius:12px;text-align:center">'
    '<h1 style="color:white;margin:0;letter-spacing:1px">H2READY TOOLKIT</h1>'
    '<p style="color:#cddafc;margin:4px 0 0">Generatore di Action Plan comunali</p></div>',
    unsafe_allow_html=True,
)
st.write("")

try:
    df = carica_dati()
except Exception as e:
    st.error(f"Impossibile leggere il foglio dati.\n\n{e}")
    st.stop()

mancanti = [c for c in (COL_ID, COL_NOME, COL_MATURITA, COL_PROFILO) if c not in df.columns]
if mancanti:
    st.error(f"Colonne obbligatorie assenti nel foglio: {', '.join(mancanti)}")
    st.write("Colonne disponibili:", list(df.columns))
    st.stop()

col_a, col_b = st.columns([1, 1])
with col_a:
    id_ricercato = st.text_input("ID_ISTAT", placeholder="es. 093001")
with col_b:
    elenco = ["-"] + sorted(df[COL_NOME].dropna().astype(str).unique().tolist())
    scelta_nome = st.selectbox("oppure seleziona il Comune", elenco)

if scelta_nome != "-":
    res = df[df[COL_NOME].astype(str).str.strip() == scelta_nome]
elif id_ricercato.strip():
    res = df[df[COL_ID].astype(str).str.strip() == id_ricercato.strip()]
else:
    st.info("Inserisci un ID_ISTAT o seleziona un Comune per iniziare.")
    st.stop()

if res.empty:
    st.warning("Nessun Comune corrispondente trovato.")
    st.stop()

riga = res.iloc[0]

try:
    score = int(float(riga[COL_MATURITA]))
except (ValueError, TypeError):
    score = 0

livello = livello_maturita(score)
profilo = normalizza_profilo(riga[COL_PROFILO])

m1, m2, m3 = st.columns(3)
m1.metric("Comune", str(riga[COL_NOME]))
m2.metric("Punteggio maturità", score)
m3.metric("Profilo", profilo or "n.d.")

if score < SOGLIA_MINIMA:
    st.error("Il Comune risulta in Livello 0: l'Action Plan non è generabile. "
             "Occorre completare la fase di assessment preliminare.")
    st.stop()

if not profilo:
    st.warning("Profilo strategico non valorizzato: la sezione dedicata resterà incompleta.")

# --- Caricamento dei testi ----------------------------------------------------
mat_file = f"3-maturita_{livello}_it.md"
profilo_file = f"4-profilo_{profilo}_it.md"

contenuti = {
    "livello": livello,
    "profilo": profilo or "n.d.",
    "intro": leggi_md("1-intro_it.md"),
    "struttura": leggi_md("2-struttura_plan_it.md"),
    "mat_intro": leggi_md("3-maturita_intro_it.md"),
    "mat_dettaglio": leggi_md(mat_file),
    "profilo_intro": leggi_md("4-profilo_intro_it.md"),
    "profilo_dettaglio": leggi_md(profilo_file),
    "passo2": testo_passo2(riga),
    "passo3": testo_passo3(livello, profilo),
    "passo4": testo_passo4(riga, livello, profilo),
}

assenti = [f for f in ("1-intro_it.md", "2-struttura_plan_it.md", "3-maturita_intro_it.md",
                       mat_file, "4-profilo_intro_it.md", profilo_file)
           if not os.path.exists(f)]
if assenti:
    st.warning("File di testo mancanti (il PDF verrà generato con segnaposto): "
               + ", ".join(assenti))

with st.expander("Anteprima dei dati tecnici (Passo 2)"):
    st.markdown(contenuti["passo2"])

with st.expander("Diagnostica colonne"):
    mappate = {c for s in SEZIONI_TECNICHE for c, *_ in s["campi"]}
    st.write("**Mappate e presenti:**", sorted(mappate & set(df.columns)) or "nessuna")
    st.write("**Mappate ma assenti nel foglio:**", sorted(mappate - set(df.columns)) or "nessuna")
    st.write("**Nel foglio ma non mappate:**", sorted(set(df.columns) - mappate))

if st.button("Genera Action Plan", type="primary", use_container_width=True):
    with st.spinner("Composizione del documento..."):
        st.session_state["pdf"] = genera_pdf(riga, contenuti)
        st.session_state["pdf_nome"] = f"H2READY_ActionPlan_{slug(riga[COL_NOME])}.pdf"

if "pdf" in st.session_state:
    st.download_button(
        "Scarica il PDF",
        data=st.session_state["pdf"],
        file_name=st.session_state.get("pdf_nome", "action_plan.pdf"),
        mime="application/pdf",
        use_container_width=True,
    )
