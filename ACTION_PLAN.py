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

# --- AZIONE 3: BILANCIO E SINERGIE ---
st.subheader("Bilancio Energetico e Sinergie")

# Calcoli di sistema [cite: 246]
fabbisogno_tot = float(riga['T21_FABBISOGNO_H2_TON_ANNO']) + float(riga['T22_FABBISOGNO_H2_TON_ANNO']) + float(riga['T23_FABBISOGNO_H2_TON_ANNO'])
potenziale_prod = float(riga['T24_POTENZIALE_PRODUZIONE_H2_TON_ANNO'])
bilancio = potenziale_prod - fabbisogno_tot

md_sinergie = f"""
## 3. QUANTIFICAZIONE E BILANCIO (AZIONE 3)
* **Fabbisogno Totale Stimato:** {fabbisogno_tot:.1f} t/anno [cite: 18]
* **Potenziale di Produzione Locale:** {potenziale_prod:.1f} t/anno [cite: 17]
* **Bilancio Netto:** {bilancio:.1f} t/anno
"""

# Logica Sinergie per Profili Misti 
profilo = str(riga['T12_PROFILO_STRATEGICO'])
if profilo == "AB":
    md_sinergie += "\n\n**Sinergia H2 Valley:** Il Comune può bilanciare domanda e offerta a KM zero. [cite: 84]"
elif profilo == "AC":
    md_sinergie += "\n\n**Sinergia Distretto Multimodale:** L'industria pesante fa da traino per la logistica. [cite: 88]"
elif profilo == "BC":
    md_sinergie += "\n\n**Sinergia Hub Mobilità:** La produzione è asservita ai corridoi TEN-T. [cite: 91]"

# --- AZIONE 4: ROADMAP ---
roadmap_testo = ""
if livello <= 8:
    roadmap_testo = "1. Formazione personale tecnico; 2. Scouting stakeholder locali; 3. Studio di prefattibilità. [cite: 27, 46]"
elif 9 <= livello <= 14:
    roadmap_testo = "1. Definizione Business Case; 2. Accordi di partenariato; 3. Individuazione aree di installazione. "
else:
    roadmap_testo = "1. Redazione progetto esecutivo; 2. Candidatura a bandi di finanziamento (PNRR/Interreg); 3. Avvio gara d'appalto. [cite: 54]"

md_sinergie += f"""
---
## 4. PIANO D'AZIONE E ROADMAP (AZIONE 4)
Sulla base della maturità di livello **{livello}**, si consigliano i seguenti step prioritari:
* {roadmap_testo}
"""

st.markdown(md_sinergie)
# Aggiorna il pulsante di download per includere tutto il md_plan + md_sinergie
