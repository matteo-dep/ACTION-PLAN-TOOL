"""
H2READY TOOLKIT - Generatore Action Plan comunali
Progetto Interreg VI-A Italia-Slovenia ITA-SI0800335

app.py        interfaccia e lettura dati
contenuti.py  mappatura colonne e testi
documenti.py  generazione PDF e Word
"""

import os

import streamlit as st
from streamlit_gsheets import GSheetsConnection

import contenuti as C
import documenti as D

SPREADSHEET_URL = ""      # usato solo se manca nei secrets

st.set_page_config(page_title="H2READY Toolkit", page_icon="🔷", layout="centered")


@st.cache_data(ttl=120, show_spinner="Lettura del foglio dati in corso...")
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

mancanti = [c for c in (C.COL_ID, C.COL_NOME, C.COL_MATURITA) if c not in df.columns]
if mancanti:
    st.error(f"Colonne obbligatorie assenti: {', '.join(mancanti)}")
    st.stop()

id_ricercato = st.text_input("Codice ID_ISTAT del Comune", placeholder="es. 030025")

if not id_ricercato.strip():
    st.info("Inserisci il codice ID_ISTAT per accedere ai dati del Comune.")
    st.stop()

res = df[df[C.COL_ID].astype(str).str.strip() == id_ricercato.strip()]
if res.empty:
    st.warning("Nessun Comune corrispondente a questo codice.")
    st.stop()

riga = res.iloc[0]
score = int(C.numero(riga[C.COL_MATURITA]) or 0)
livello = C.livello_maturita(score)
profilo, punteggi = C.calcola_profilo(riga)

m1, m2, m3 = st.columns(3)
m1.metric("Comune", str(riga[C.COL_NOME]))
m2.metric("Maturità", f"{score} ({livello})")
m3.metric("Profilo", profilo or "n.d.")

if punteggi:
    st.caption("Punteggi di profilo: " +
               "   ".join(f"{l} = {C.formatta_numero(v)}" for l, v in punteggi.items()))

if score < C.SOGLIA_MINIMA:
    st.error("Comune in Livello 0: Action Plan non generabile.")
    st.stop()

contenuti = C.costruisci_contenuti(riga, livello, profilo, punteggi)

assenti = [f for f in C.file_attesi(livello, profilo) if not os.path.exists(f)]
if assenti:
    st.warning("File di testo mancanti (verranno inseriti dei segnaposto): "
               + ", ".join(assenti))

with st.expander("Anteprima Passo 2 - risultati dei percorsi"):
    st.markdown(contenuti["passo2"])
with st.expander("Anteprima Passo 3 - analisi incrociata"):
    st.markdown(contenuti["passo3"])
with st.expander("Diagnostica colonne"):
    previste = {c for p in C.PERCORSI for _, cols in p["blocchi"] for c in cols}
    st.write("**Previste ma assenti nel foglio:**",
             sorted(previste - set(df.columns)) or "nessuna")
    st.write("**Nel foglio ma non collocate nei percorsi:**",
             sorted(set(df.columns) - previste - C.ESCLUSE - set(C.FLAG_GOVERNANCE)) or "nessuna")

st.write("")
if st.button("Genera Action Plan", type="primary", use_container_width=True):
    with st.spinner("Composizione dei documenti..."):
        st.session_state["pdf"] = D.genera_pdf(contenuti)
        st.session_state["docx"] = D.genera_docx(contenuti)
        st.session_state["nome"] = f"H2READY_ActionPlan_{C.slug(riga[C.COL_NOME])}"

if "pdf" in st.session_state:
    nome = st.session_state.get("nome", "action_plan")
    c1, c2 = st.columns(2)
    c1.download_button("Scarica PDF", data=st.session_state["pdf"],
                       file_name=f"{nome}.pdf", mime="application/pdf",
                       use_container_width=True)
    c2.download_button("Scarica Word", data=st.session_state["docx"],
                       file_name=f"{nome}.docx", use_container_width=True,
                       mime="application/vnd.openxmlformats-officedocument."
                            "wordprocessingml.document")
