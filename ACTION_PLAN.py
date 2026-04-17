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
        # QUESTA È LA RIGA DA AGGIORNARE:
        # Legge il foglio in tempo reale (ttl=0) usando i segreti del Service Account
        df = conn.read(ttl=0) 
        
        # Pulizia standard delle colonne
        df.columns = df.columns.str.strip()

        # Ricerca della riga basata sull'ID inserito dall'utente
        riga_comune = df[df['ID_ISTAT'].astype(str).str.strip() == str(id_ricercato).strip()]

        if not riga_comune.empty:
            riga = riga_comune.iloc[0]
            st.success(f"✅ Dati recuperati per il Comune di: **{riga['NOME_COMUNE']}**")
            
            # Da qui in poi il codice genera l'Action Plan basandosi sui dati tecnici:
            # - Livello (Beginner, Intermedio o Advanced) [cite: 43, 48, 52]
            # - Profilo (A, B, C o misti) [cite: 76-82]
            
            # (Resto del codice per la visualizzazione...)
            
        else:
            st.warning(f"⚠️ Nessuna corrispondenza trovata per l'ID: {id_ricercato}")
            
    except Exception as e:
        # Se ricevi ancora 401 qui, controlla di aver condiviso il foglio con l'email del Service Account
        st.error(f"Errore durante la lettura: {e}")
