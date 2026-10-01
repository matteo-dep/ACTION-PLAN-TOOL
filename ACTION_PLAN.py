"""
H2READY TOOLKIT - Generatore Action Plan comunali
Progetto Interreg VI-A Italia-Slovenia ITA-SI0800335

ACTION_PLAN.py  interfaccia e lettura dati
contenuti.py    mappatura colonne e testi
documenti.py    generazione PDF e Word

LINGUA
L'interfaccia e' trilingue. La lingua si sceglie, in quest'ordine:
  1. query string  ?lang=sl   -> cosi' il link che arriva dalla pagina 1.3
                                 apre gia' la pagina nella lingua giusta
  2. selettore nella barra laterale
  3. italiano, come ripiego

ATTENZIONE: la lingua riguarda SOLO l'interfaccia. Il documento generato
nasce dai modelli di testo di contenuti.py, che oggi esistono nella sola
versione italiana (i file *_it.md): l'Action Plan esce in italiano anche se
la pagina e' in inglese o in sloveno. Il messaggio sotto il pulsante lo dice
all'utente, cosi' nessuno scarica un PDF aspettandosene un altro.

CODICE DEL COMUNE
Arriva da ?id=... quando si entra dal toolkit; resta modificabile a mano per
chi apre il generatore direttamente.
"""

import os

import streamlit as st
from streamlit_gsheets import GSheetsConnection

import contenuti as C
import documenti as D

SPREADSHEET_URL = ""      # usato solo se manca nei secrets

st.set_page_config(page_title="H2READY Toolkit", page_icon="🔷", layout="centered")


# ==========================================================================
# LINGUA
# ==========================================================================
ETICHETTE = {"Italiano": "it", "English": "en", "Slovenščina": "sl"}

_da_url = ""
try:
    _da_url = str(st.query_params.get("lang", "")).strip().lower()
except Exception:
    _da_url = ""

# La query string vale al primo caricamento: dopo comanda il selettore,
# altrimenti chi entra con ?lang=sl non riuscirebbe piu' a cambiare lingua.
if _da_url in ETICHETTE.values() and not st.session_state.get("ap_lang_da_url"):
    st.session_state["ap_lang"] = _da_url
    st.session_state["ap_lang_da_url"] = True

_iniziale = st.session_state.get("ap_lang", "it")
_scelta = st.sidebar.selectbox(
    "🌐 Lingua / Language / Jezik",
    list(ETICHETTE.keys()),
    index=list(ETICHETTE.values()).index(_iniziale) if _iniziale in ETICHETTE.values() else 0,
)
LANG = ETICHETTE[_scelta]
st.session_state["ap_lang"] = LANG


T = {
    "sottotitolo": {
        "it": "Generatore di Action Plan comunali",
        "en": "Municipal Action Plan generator",
        "sl": "Generator občinskih akcijskih načrtov",
    },
    "err_foglio": {
        "it": "Impossibile leggere il foglio dati.",
        "en": "Unable to read the data sheet.",
        "sl": "Podatkovnega lista ni mogoče prebrati.",
    },
    "err_colonne": {
        "it": "Colonne obbligatorie assenti: {c}",
        "en": "Required columns missing: {c}",
        "sl": "Manjkajo obvezni stolpci: {c}",
    },
    "campo_id": {
        "it": "Codice identificativo del Comune",
        "en": "Municipality identification code",
        "sl": "Identifikacijska koda občine",
    },
    "chiedi_id": {
        "it": "Inserisci il codice identificativo per accedere ai dati del Comune.",
        "en": "Enter the identification code to access the municipality's data.",
        "sl": "Vnesite identifikacijsko kodo za dostop do podatkov občine.",
    },
    "non_trovato": {
        "it": "Nessun Comune corrispondente a questo codice.",
        "en": "No municipality matches this code.",
        "sl": "Nobena občina ne ustreza tej kodi.",
    },
    "m_comune": {"it": "Comune", "en": "Municipality", "sl": "Občina"},
    "m_maturita": {"it": "Maturità", "en": "Maturity", "sl": "Zrelost"},
    "m_profilo": {"it": "Profilo", "en": "Profile", "sl": "Profil"},
    "punteggi": {
        "it": "Punteggi di profilo: ",
        "en": "Profile scores: ",
        "sl": "Ocene profila: ",
    },
    "livello0": {
        "it": "Comune in Livello 0: l'Action Plan non è generabile. Va prima completato "
              "il questionario 1.1.",
        "en": "Municipality at Level 0: the Action Plan cannot be generated. "
              "Questionnaire 1.1 must be completed first.",
        "sl": "Občina na ravni 0: akcijskega načrta ni mogoče ustvariti. Najprej je "
              "treba izpolniti vprašalnik 1.1.",
    },
    "file_mancanti": {
        "it": "File di testo mancanti (verranno inseriti dei segnaposto): {f}",
        "en": "Missing text files (placeholders will be inserted): {f}",
        "sl": "Manjkajoče besedilne datoteke (vstavljena bodo nadomestna mesta): {f}",
    },
    "anteprima2": {
        "it": "Anteprima - risultati dei percorsi",
        "en": "Preview - pathway results",
        "sl": "Predogled - rezultati poti",
    },
    "diagnostica": {
        "it": "Diagnostica colonne",
        "en": "Column diagnostics",
        "sl": "Diagnostika stolpcev",
    },
    "diag_assenti": {
        "it": "**Previste ma assenti nel foglio:**",
        "en": "**Expected but missing from the sheet:**",
        "sl": "**Pričakovani, a manjkajo v listu:**",
    },
    "diag_non_collocate": {
        "it": "**Nel foglio ma non collocate nei percorsi:**",
        "en": "**In the sheet but not placed in any pathway:**",
        "sl": "**V listu, a niso umeščeni v nobeno pot:**",
    },
    "nessuna": {"it": "nessuna", "en": "none", "sl": "nobeden"},
    "genera": {
        "it": "Genera l'Action Plan",
        "en": "Generate the Action Plan",
        "sl": "Ustvari akcijski načrt",
    },
    "in_corso": {
        "it": "Composizione dei documenti...",
        "en": "Composing the documents...",
        "sl": "Sestavljanje dokumentov...",
    },
    "scarica_pdf": {"it": "Scarica il PDF", "en": "Download the PDF",
                    "sl": "Prenesi PDF"},
    "scarica_word": {"it": "Scarica il Word", "en": "Download the Word file",
                     "sl": "Prenesi datoteko Word"},
    "nota_lingua": {
        "it": "",
        "en": "⚠️ The generated document is produced in Italian: the content templates "
              "exist in Italian only for now. The interface language does not change "
              "the language of the Action Plan.",
        "sl": "⚠️ Ustvarjeni dokument nastane v italijanščini: predloge vsebine zaenkrat "
              "obstajajo samo v italijanščini. Jezik vmesnika ne spremeni jezika "
              "akcijskega načrta.",
    },
}


def TT(chiave, **valori):
    voce = T[chiave]
    testo = voce.get(LANG) or voce["it"]
    return testo.format(**valori) if valori else testo


# ==========================================================================
# LETTURA DEL FOGLIO
# ==========================================================================
@st.cache_data(ttl=120, show_spinner=True)
def carica_dati():
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
            raise RuntimeError("Foglio non configurato: manca la chiave 'spreadsheet' "
                               "nella sezione [connections.gsheets] dei secrets.")
        kwargs["spreadsheet"] = SPREADSHEET_URL
    df = conn.read(**kwargs)
    df.columns = [str(c).strip() for c in df.columns]
    return df.dropna(how="all")


# ==========================================================================
# PAGINA
# ==========================================================================
st.markdown(
    '<div style="background:linear-gradient(90deg,#003399,#0057c2);padding:22px;'
    'border-radius:12px;text-align:center">'
    '<h1 style="color:white;margin:0;letter-spacing:1px">H2READY TOOLKIT</h1>'
    f'<p style="color:#cddafc;margin:4px 0 0">{TT("sottotitolo")}</p></div>',
    unsafe_allow_html=True)
st.write("")

try:
    df = carica_dati()
except Exception as e:
    st.error(f"{TT('err_foglio')}\n\n{e}")
    st.stop()

mancanti = [c for c in (C.COL_ID, C.COL_NOME, C.COL_MATURITA) if c not in df.columns]
if mancanti:
    st.error(TT("err_colonne", c=", ".join(mancanti)))
    st.stop()

# Il codice arriva dal toolkit via ?id=..., e resta modificabile a mano.
preimpostato = ""
try:
    preimpostato = str(st.query_params.get("id", "")).strip()
except Exception:
    preimpostato = ""

id_ricercato = st.text_input(TT("campo_id"), value=preimpostato, placeholder="es. 030025")

if not id_ricercato.strip():
    st.info(TT("chiedi_id"))
    st.stop()

res = df[df[C.COL_ID].astype(str).str.strip() == id_ricercato.strip()]
if res.empty:
    st.warning(TT("non_trovato"))
    st.stop()

riga = res.iloc[0]
score = int(C.numero(riga[C.COL_MATURITA]) or 0)
livello = C.livello_maturita(score)
profilo, punteggi = C.calcola_profilo(riga)

m1, m2, m3 = st.columns(3)
m1.metric(TT("m_comune"), str(riga[C.COL_NOME]))
m2.metric(TT("m_maturita"), f"{score} ({livello})")
m3.metric(TT("m_profilo"), profilo or "n.d.")

if punteggi:
    st.caption(TT("punteggi") +
               "   ".join(f"{l} = {C.formatta_numero(v)}" for l, v in punteggi.items()))

if score < C.SOGLIA_MINIMA:
    st.error(TT("livello0"))
    st.stop()

contenuti = C.costruisci_contenuti(riga, livello, profilo, punteggi)

assenti = [f for f in C.file_attesi(livello, profilo) if not os.path.exists(f)]
if assenti:
    st.warning(TT("file_mancanti", f=", ".join(assenti)))

with st.expander(TT("anteprima2")):
    st.markdown(contenuti["passo2"])

with st.expander(TT("diagnostica")):
    previste = {c for p in C.PERCORSI for _, cols in p["blocchi"] for c in cols}
    st.write(TT("diag_assenti"),
             sorted(previste - set(df.columns)) or TT("nessuna"))
    st.write(TT("diag_non_collocate"),
             sorted(set(df.columns) - previste - C.ESCLUSE - set(C.FLAG_GOVERNANCE))
             or TT("nessuna"))

st.write("")
if st.button(TT("genera"), type="primary", use_container_width=True):
    with st.spinner(TT("in_corso")):
        st.session_state["pdf"] = D.genera_pdf(contenuti)
        st.session_state["docx"] = D.genera_docx(contenuti)
        st.session_state["nome"] = f"H2READY_ActionPlan_{C.slug(riga[C.COL_NOME])}"

if "pdf" in st.session_state:
    nome = st.session_state.get("nome", "action_plan")
    c1, c2 = st.columns(2)
    c1.download_button(TT("scarica_pdf"), data=st.session_state["pdf"],
                       file_name=f"{nome}.pdf", mime="application/pdf",
                       use_container_width=True)
    c2.download_button(TT("scarica_word"), data=st.session_state["docx"],
                       file_name=f"{nome}.docx", use_container_width=True,
                       mime="application/vnd.openxmlformats-officedocument."
                            "wordprocessingml.document")
    if TT("nota_lingua"):
        st.caption(TT("nota_lingua"))
