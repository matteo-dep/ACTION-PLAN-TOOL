import streamlit as st
import pandas as pd

st.set_page_config(page_title="H2READY Action Plan", layout="wide")

# Costruiamo il link diretto per il download del CSV (metodo infallibile per fogli pubblici)
SHEET_ID = "15oHezgxy09dC-1WQn7vfStYq67DQo3R09pFLvWBoFSk"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0"

st.title("📄 Generatore Automatico Action Plan H2READY")

id_ricercato = st.text_input("Inserisci ID_ISTAT o Codice Univoco:")

if id_ricercato:
    try:
        # Leggiamo direttamente il CSV dal web
        df = pd.read_csv(CSV_URL)
        
        # Pulizia colonne per sicurezza
        df.columns = df.columns.str.strip()

        # Ricerca esatta basata sulla stringa inserita
        riga_comune = df[df['ID_ISTAT'].astype(str).str.strip() == str(id_ricercato).strip()]

        if not riga_comune.empty:
            riga = riga_comune.iloc[0]
            st.success(f"✅ Dati recuperati per il Comune di: **{riga['NOME_COMUNE']}**")
            
            # Anteprima rapida
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Livello Maturità", f"{riga['T11_LIVELLO_MATURITA']}/18")
            with col2:
                st.metric("Profilo", riga['T12_PROFILO_STRATEGICO'])
            
        else:
            st.warning(f"⚠️ Nessuna corrispondenza trovata per l'ID: {id_ricercato}")
            
    except Exception as e:
        st.error(f"Errore durante la lettura: {e}")
