import streamlit as st
from streamlit_gsheets import GSheetsConnection

# 1. Configurazione Pagina
st.set_page_config(page_title="H2READY Action Plan", layout="wide")

# 2. Inizializzazione della Connessione (IL "CONN" MANCANTE)
# Questa riga deve stare fuori dai blocchi 'if' o 'try' per essere vista da tutto lo script
conn = st.connection("gsheets", type=GSheetsConnection)

st.title("📄 Generatore Automatico Action Plan H2READY")
st.markdown("Inserisci il codice identificativo del Comune per generare il piano basato sui dati dei Tool.")

# 3. Input dell'utente
id_ricercato = st.text_input("Inserisci ID_ISTAT o Codice Univoco:")

if id_ricercato:
    try:
        # 4. Lettura dati con ttl=0 per ignorare la cache
        df = conn.read(ttl=0)
        
        # Pulizia nomi colonne
        df.columns = df.columns.str.strip()

        # 5. Ricerca esatta del Comune
        riga_comune = df[df['ID_ISTAT'].astype(str).str.strip() == str(id_ricercato).strip()]

        if not riga_comune.empty:
            riga = riga_comune.iloc[0]
            st.success(f"✅ Dati recuperati per il Comune di: **{riga['NOME_COMUNE']}**")
            
            # --- LOGICA MATURITÀ (Azione 1) ---
            livello = int(riga['T11_LIVELLO_MATURITA'])
            if livello < 3:
                livello_testo = "LIVELLO 0 - Non Idoneo"
                visione = "Investire prioritariamente in assistenza tecnica o personale. [cite: 38-41]"
            elif 3 <= livello <= 8:
                livello_testo = "LIVELLO 1 - Beginner"
                visione = "Fase di Inquadramento e Mappatura Strategica. [cite: 43-46]"
            elif 9 <= livello <= 14:
                livello_testo = "LIVELLO 2 - Intermedio"
                visione = "Definizione del Profilo di Progetto. [cite: 48-50]"
            else:
                livello_testo = "LIVELLO 3 - Advanced"
                visione = "Fase esecutiva e ricerca finanziamenti immediati. [cite: 51-54]"

            # --- GENERAZIONE TESTO ACTION PLAN ---
            st.divider()
            
            md_plan = f"""
# ACTION PLAN: {riga['NOME_COMUNE']}
**Profilo:** {riga['T12_PROFILO_STRATEGICO']} | **Maturità:** {livello_testo}

## 1. POSIZIONAMENTO (AZIONE 1)
Il Comune ha un punteggio di **{livello}/18**.  
**Strategia:** {visione}

## 2. ANALISI TECNICA (AZIONE 2)
"""
            # Logica profili 
            profilo = str(riga['T12_PROFILO_STRATEGICO'])
            
            if "A" in profilo:
                md_plan += f"\n### Percorso A: Domanda\n* **HTA:** {riga['T21_N_AZIENDE_IDONEE']} aziende ({riga['T21_NOMI_AZIENDE']}). [cite: 134-142]"
                md_plan += f"\n* **Fabbisogno H2:** {riga['T21_FABBISOGNO_H2_TON_ANNO']} t/anno."
            
            if "B" in profilo:
                md_plan += f"\n### Percorso B: Offerta\n* **Produzione:** Potenziale di {riga['T24_POTENZIALE_PRODUZIONE_H2_TON_ANNO']} t/anno. [cite: 187-193]"
                md_plan += f"\n* **Costo (LCOH):** {riga['T26_LCOH_EURO_KG']} €/kg. [cite: 208]"

            if "C" in profilo:
                md_plan += f"\n### Percorso C: Logistica\n* **Nodo:** {riga['T27_VERDETTO_NODO']} su corridoi TEN-T. [cite: 224-233]"

            # Visualizzazione finale
            st.markdown(md_plan)
            st.download_button("Scarica Action Plan", md_plan, file_name=f"Plan_{riga['NOME_COMUNE']}.md")

        else:
            st.warning(f"Nessun dato trovato per l'ID: {id_ricercato}")
            
    except Exception as e:
        st.error(f"Errore durante la lettura: {e}")
