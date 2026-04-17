import streamlit as st
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="H2READY Action Plan", layout="wide")

# Crea la connessione
conn = st.connection("gsheets", type=GSheetsConnection)

# --- INSERISCI QUI IL TUO LINK ---
# Copia l'URL del tuo foglio Google dalla barra degli indirizzi del browser
URL_IL_TUO_FOGLIO = "https://docs.google.com/spreadsheets/d/IL_TUO_ID_FOGLIO_QUI/edit#gid=0"

st.title("📄 Generatore Automatico Action Plan H2READY")

id_ricercato = st.text_input("Inserisci ID_ISTAT o Codice Univoco:")

if id_ricercato:
    try:
        # Specifichiamo l'URL direttamente qui per evitare l'errore "must be specified"
        # ttl=0 serve per leggere i dati aggiornati in tempo reale
        df = conn.read(spreadsheet=URL_IL_TUO_FOGLIO, ttl=0)
        
        # Pulizia colonne
        df.columns = df.columns.str.strip()

        # Ricerca esatta basata sulla stringa inserita
        riga_comune = df[df['ID_ISTAT'].astype(str).str.strip() == str(id_ricercato).strip()]

        if not riga_comune.empty:
            riga = riga_comune.iloc[0]
            st.success(f"✅ Dati recuperati per il Comune di: **{riga['NOME_COMUNE']}**")
            
            # Anteprima rapida per vedere se i dati sono corretti
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Livello Maturità", f"{riga['T11_LIVELLO_MATURITA']}/18")
            with col2:
                st.metric("Profilo", riga['T12_PROFILO_STRATEGICO'])
            
            # Qui poi aggiungeremo il tasto per generare tutto il testo dell'Action Plan
            
        else:
            st.warning(f"⚠️ Nessuna corrispondenza trovata per l'ID: {id_ricercato}")
            
    except Exception as e:
        st.error(f"Errore durante la lettura: {e}")
