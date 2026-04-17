import streamlit as st
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="H2READY Action Plan", layout="wide")

# Si connette usando i tuoi Secrets nascosti
conn = st.connection("gsheets", type=GSheetsConnection)

st.title("📄 Generatore Automatico Action Plan H2READY")

# L'utente inserisce l'ID
id_ricercato = st.text_input("Inserisci ID_ISTAT o Codice Univoco:")

if id_ricercato:
    try:
        # Legge il foglio. ttl="0" forza la lettura in tempo reale senza usare vecchi dati in memoria
        df = conn.read(ttl="0")
        
        # Pulizia base per evitare che spazi vuoti accidentali blocchino la ricerca
        df.columns = df.columns.str.strip()

        # LOGICA DI RICERCA ESATTA:
        # Prende la colonna ID_ISTAT, la converte in testo puro, toglie eventuali spazi
        # e fa la stessa cosa con l'input che hai digitato. Se sono uguali, prende la riga.
        riga_comune = df[df['ID_ISTAT'].astype(str).str.strip() == str(id_ricercato).strip()]

        if not riga_comune.empty:
            riga = riga_comune.iloc[0]
            st.success(f"✅ Dati recuperati con successo per il Comune di: **{riga['NOME_COMUNE']}**")
            
            # Stampiamo giusto due dati per verificare che legga correttamente le celle
            st.write(f"**Profilo Strategico:** {riga['T12_PROFILO_STRATEGICO']}")
            st.write(f"**Livello Maturità:** {riga['T11_LIVELLO_MATURITA']}")
            
        else:
            st.warning("⚠️ Nessun dato trovato per questo ID. Verifica la corrispondenza esatta con il foglio.")
            
    except Exception as e:
        st.error(f"Errore di connessione: {e}")
