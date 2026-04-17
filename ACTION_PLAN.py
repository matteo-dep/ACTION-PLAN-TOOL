import streamlit as st
import pandas as pd

# 1. Configurazione Pagina
st.set_page_config(page_title="H2Ready Action Plan Generator", layout="wide")

# 2. Funzione per caricare i dati dal tuo Google Sheet (versione CSV pubblicata)
@st.cache_data
def load_data(url):
    # Trasforma il link "edit" in un link "export?format=csv"
    csv_url = url.replace('/edit?gid=', '/export?format=csv&gid=')
    return pd.read_csv(csv_url)

SHEET_URL = "https://docs.google.com/spreadsheets/d/15oHezgxy09dC-1WQn7vfStYq67DQo3R09pFLvWBoFSk/edit?gid=0"

try:
    df = load_data(SHEET_URL)
    
    st.title("🚀 H2Ready: Generatore Action Plan")
    
    # 3. Selezione del Comune
    comune_selezionato = st.selectbox("Seleziona il Comune per generare il piano:", df['NOME_COMUNE'].unique())
    riga = df[df['NOME_COMUNE'] == comune_selezionato].iloc[0]

    if st.button("Genera Anteprima Action Plan"):
        
        # --- LOGICA DI TESTO DINAMICO ---
        
        # Determina il testo della visione in base al livello [cite: 43-54]
        livello = riga['T11_LIVELLO_MATURITA']
        if livello < 3:
            visione_testo = "Il Comune deve prima investire in assistenza tecnica o personale[cite: 41]."
            stato_colore = "red"
        elif 3 <= livello <= 8:
            visione_testo = "L'obiettivo primario è la mappatura delle potenzialità e la creazione di una cultura tecnica interna[cite: 46]."
            stato_colore = "orange"
        elif 9 <= livello <= 14:
            visione_testo = "Il territorio è pronto per definire un profilo di progetto concreto, agendo come aggregatore di domanda[cite: 50]."
            stato_colore = "blue"
        else:
            visione_testo = "Il focus è l'esecuzione immediata e la ricerca di finanziamenti immediati per impianti pilota[cite: 53, 54]."
            stato_colore = "green"

        # --- COMPOSIZIONE MARKDOWN ---
        
        md_output = f"""
# ACTION PLAN: IL FUTURO A IDROGENO DI {riga['NOME_COMUNE']}
**Progetto H2READY - Interreg Italia-Slovenia**

---

## 1. EXECUTIVE SUMMARY
Sulla base dell'analisi condotta, il Comune è stato identificato con un profilo di:

**PROFILO STRATEGICO:** `{riga['T12_PROFILO_STRATEGICO']}`  
**LIVELLO DI PRONTEZZA:** `{livello}/18`

### Sintesi della Visione
{visione_testo}

---

## 2. AZIONE 1: POSIZIONAMENTO STRATEGICO
Il punteggio di **{livello}/18** riflette lo stato attuale dell'amministrazione. 
Il Comune è stato classificato come **{riga['T12_PROFILO_STRATEGICO']}**. Questa classificazione suggerisce di:
        """
        
        # Logica per Profilo Strategico [cite: 76-84]
        profilo = riga['T12_PROFILO_STRATEGICO']
        if "A" in profilo:
            md_output += "\n* **Focus Consumo:** Concentrare gli sforzi sulla decarbonizzazione delle industrie locali e delle flotte[cite: 76]."
        if "B" in profilo:
            md_output += "\n* **Focus Produzione:** Sfruttare le aree idonee per impianti a fonti rinnovabili[cite: 79]."
        if "C" in profilo:
            md_output += "\n* **Focus Logistica:** Sviluppo di nodi per il rifornimento dei corridoi internazionali TEN-T[cite: 82]."

        st.markdown(md_output)
        
        # Opzione per download (semplice testo per ora)
        st.download_button("Scarica Action Plan (MD)", md_output, file_name=f"ActionPlan_{comune_selezionato}.md")

except Exception as e:
    st.error(f"Errore nel caricamento dei dati: {e}")
