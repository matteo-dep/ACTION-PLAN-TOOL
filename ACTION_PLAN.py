import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

# Configurazione Pagina
st.set_page_config(page_title="H2READY Action Plan Generator", layout="wide")

# Connessione al foglio tramite l'integrazione nativa
# Nota: Assicurati di aver configurato il link del foglio in .streamlit/secrets.toml
conn = st.connection("gsheets", type=GSheetsConnection)

st.title("📄 Generatore Automatico Action Plan H2READY")
st.markdown("Inserisci il codice identificativo del Comune per recuperare i dati dai Tool e generare il piano.")

# 1. Input dell'utente: Ricerca per ID_ISTAT
id_ricercato = st.text_input("Inserisci ID_ISTAT o Codice Univoco (es. 030043):", help="Il sistema cercherà questo codice nella Colonna A del foglio")

# Sostituisci l'URL qui sotto con il link del tuo foglio Google
URL_FOGLIO = "https://docs.google.com/spreadsheets/d/15oHezgxy09dC-1WQn7vfStYq67DQo3R09pFLvWBoFSk/edit#gid=0"

if id_ricercato:
    try:
        # Leggiamo il foglio passando direttamente l'URL
        df = conn.read(spreadsheet=URL_FOGLIO)
        
        # Pulizia nomi colonne
        df.columns = df.columns.str.strip()
        
        # ... resto del codice ...

#if id_ricercato:
    #try:
        # Leggiamo tutto il foglio TOOLKIT_RESULTS_TOTAL
        #df = conn.read()
        
        # Pulizia nomi colonne (rimuove spazi bianchi)
        #df.columns = df.columns.str.strip()

        # 2. Ricerca della riga corrispondente all'ID
        # Cerchiamo il valore nella colonna ID_ISTAT (che partiva dalla cella A2)
        riga_comune = df[df['ID_ISTAT'].astype(str) == str(id_ricercate)]

        if not riga_comune.empty:
            riga = riga_comune.iloc[0]
            st.success(f"Dati recuperati per il Comune di: **{riga['NOME_COMUNE']}**")
            
            # --- LOGICA DI ELABORAZIONE DATI (TOOL 1.1 e 1.2) ---
            livello_punteggio = int(riga['T11_LIVELLO_MATURITA'])
            
            # Classificazione Maturità [cite: 35, 42-51]
            if livello_punteggio < 3:
                livello_testo = "LIVELLO 0 - Non Idoneo"
                consiglio_maturita = "Il Comune deve prima investire in assistenza tecnica o personale [cite: 38-41]."
            elif 3 <= livello_punteggio <= 8:
                livello_testo = "LIVELLO 1 - Beginner"
                consiglio_maturita = "Ideale per la Mappatura Strategica. Il Comune deve restare nella fase di 'Inquadramento' [cite: 43-46]."
            elif 9 <= livello_punteggio <= 14:
                livello_testo = "LIVELLO 2 - Intermedio"
                consiglio_maturita = "Il Comune può iniziare a definire il Profilo di Progetto [cite: 48-50]."
            else:
                livello_testo = "LIVELLO 3 - Advanced"
                consiglio_maturita = "Il Comune è pronto per la Fase di Esecuzione e per la ricerca di finanziamenti immediati [cite: 51-54]."

            # --- COSTRUZIONE DEL DOCUMENTO ---
            if st.button("Genera Documento Action Plan"):
                
                # Header e Azione 1 [cite: 23, 59]
                md_plan = f"""
# ACTION PLAN PER L'IDROGENO: {riga['NOME_COMUNE']}
**Toolkit H2READY - Area Transfrontaliera Italia-Slovenia**

---

## 1. QUADRO STRATEGICO (AZIONE 1)
Il Comune ha completato la fase di autovalutazione e scouting.

* **Livello di Maturità:** {livello_testo} ({livello_punteggio}/18 pt)
* **Profilo Consigliato:** {riga['T12_PROFILO_STRATEGICO']}

**Analisi del Posizionamento:**
{consiglio_maturita}

---

## 2. ANALISI TECNICA (AZIONE 2)
In base al profilo **{riga['T12_PROFILO_STRATEGICO']}**, sono stati analizzati i seguenti percorsi:
"""
                
                # Sezione A - Domanda (HTA e Flotte) [cite: 133, 151]
                if "A" in str(riga['T12_PROFILO_STRATEGICO']):
                    md_plan += f"""
### Percorso A: Domanda e Decarbonizzazione
* **Industrie HTA:** Identificate {riga['T21_N_AZIENDE_IDONEE']} aziende target ({riga['T21_NOMI_AZIENDE']}). 
* **Fabbisogno Industriale:** {riga['T21_FABBISOGNO_H2_TON_ANNO']} t/anno[cite: 135].
* **Mobilità Pesante:** Analizzati {riga['T22_N_VEICOLI_ANALIZZATI']} veicoli. Esito prevalente: {riga['T22_ESITO_PREVALENTE']}.
* **Fabbisogno Flotta:** {riga['T22_FABBISOGNO_H2_TON_ANNO']} t/anno[cite: 154].
"""

                # Sezione B - Offerta (Produzione) [cite: 185, 202]
                if "B" in str(riga['T12_PROFILO_STRATEGICO']):
                    md_plan += f"""
### Percorso B: Offerta e Produzione Locale
* **Potenziale di Produzione:** {riga['T24_POTENZIALE_PRODUZIONE_H2_TON_ANNO']} t/anno.
* **Aree Idonee:** {riga['T24_AREE_IDONEE_MQ']} mq identificati.
* **Elettrolizzatore:** Taglia stimata {riga['T26_TAGLIA_ELETTROLIZZATORE_MW']} MW con LCOH di {riga['T26_LCOH_EURO_KG']} €/kg[cite: 204, 208].
"""

                # Sezione C - Logistica [cite: 223]
                if "C" in str(riga['T12_PROFILO_STRATEGICO']):
                    md_plan += f"""
### Percorso C: Hub Logistico
* **Verdetto Nodo:** {riga['T27_VERDETTO_NODO']}.
* **Priorità AFIR:** {riga['T27_PRiORiTA_AFIR']}.
* **Distanza Dorsale SNAM:** {riga['T27_DISTANZA_SNAM_KM']} km[cite: 228, 232].
"""

                # Bilancio Finale (Azione 3) [cite: 246]
                md_plan += f"""
---

## 3. BILANCIO E SINERGIE (AZIONE 3)
* **Fabbisogno Totale:** {riga['SYS_FABBISOGNO_TOTALE_TON_ANNO']} t/anno.
* **Bilancio Locale (Produzione - Consumo):** {riga['SYS_BILANCIO_PRODUZIONE_CONSUMO']} t/anno.

**Conclusione:** Il territorio di {riga['NOME_COMUNE']} si configura come un {riga['T27_VERDETTO_NODO']} con un profilo di {'autosufficienza' if float(riga['SYS_BILANCIO_PRODUZIONE_CONSUMO']) >= 0 else 'importazione necessaria'}.
"""
                
                st.markdown(md_plan)
                st.download_button("Scarica Action Plan (.md)", md_plan, file_name=f"H2READY_Plan_{riga['NOME_COMUNE']}.md")

        else:
            st.error(f"Nessun dato trovato per l'ID: {id_ricercato}. Assicurati che i tool siano stati compilati.")
            
    except Exception as e:
        st.error(f"Errore durante la lettura del foglio: {e}")
