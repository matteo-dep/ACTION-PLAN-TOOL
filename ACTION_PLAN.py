import streamlit as st
from streamlit_gsheets import GSheetsConnection
from fpdf import FPDF

# --- 1. CONFIGURAZIONE PDF ISTITUZIONALE ---
class H2ReadyPDF(FPDF):
    def header(self):
        # Intestazione professionale
        self.set_font('Arial', 'B', 8)
        self.set_text_color(100)
        self.cell(0, 5, 'H2READY - TOOLKIT STRATEGICO IDROGENO', 0, 1, 'R')
        self.ln(10)

    def footer(self):
        # Piè di pagina con cofinanziamento UE
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(128)
        self.cell(0, 10, f'Pagina {self.page_no()} - Progetto cofinanziato dall\'Unione europea - Interreg Italia-Slovenia', 0, 0, 'C')

def generate_pdf(riga, testo_completo):
    pdf = H2ReadyPDF()
    pdf.add_page()
    
    # Titolo del Documento
    pdf.set_font('Arial', 'B', 22)
    pdf.set_text_color(0, 51, 153)
    pdf.cell(0, 20, "ACTION PLAN IDROGENO", 0, 1, 'C')
    
    pdf.set_font('Arial', '', 16)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 10, f"Comune di {riga['NOME_COMUNE']}", 0, 1, 'C')
    pdf.ln(10)

    # Pulizia caratteri per FPDF
    testo_pdf = (testo_completo
                 .replace('’', "'")
                 .replace('‘', "'")
                 .replace('✅', "-")
                 .replace('€', "Euro")
                 .replace('–', "-")
                 .replace('•', "-"))

    pdf.set_font('Arial', '', 11)
    pdf.multi_cell(0, 7, testo_pdf)
    
    # TRUCCO FINALE: Convertiamo il bytearray in bytes puri
    return bytes(pdf.output())


# --- 2. CONFIGURAZIONE INTERFACCIA STREAMLIT ---
st.set_page_config(page_title="H2READY Action Plan", layout="wide")

# Inizializzazione connessione (globale)
conn = st.connection("gsheets", type=GSheetsConnection)

st.title("📄 Generatore Automatico Action Plan H2READY")
st.markdown("Strumento di sintesi strategica basato sui dati dei Tool tecnici.")

# --- 3. LOGICA DI RICERCA ---
id_ricercato = st.text_input("Inserisci ID_ISTAT o Codice Univoco (es. 030043):")

if id_ricercato:
    try:
        # Lettura dati (ttl=0 per evitare cache di vecchi errori)
        df = conn.read(ttl=0)
        df.columns = df.columns.str.strip()
        
        # Ricerca riga
        riga_comune = df[df['ID_ISTAT'].astype(str).str.strip() == str(id_ricercato).strip()]

        if not riga_comune.empty:
            riga = riga_comune.iloc[0]
            st.success(f"✅ Dati recuperati per il Comune di: **{riga['NOME_COMUNE']}**")
            
            # --- AZIONE 1: MATURITÀ ---
            livello = int(riga['T11_LIVELLO_MATURITA'])
            if livello < 3:
                liv_testo, visione = "LIVELLO 0", "Investire prioritariamente in assistenza tecnica."
            elif 3 <= livello <= 8:
                liv_testo, visione = "LIVELLO 1 - Beginner", "Fase di Inquadramento e Mappatura Strategica."
            elif 9 <= livello <= 14:
                liv_testo, visione = "LIVELLO 2 - Intermedio", "Definizione del Profilo di Progetto."
            else:
                liv_testo, visione = "LIVELLO 3 - Advanced", "Fase esecutiva e ricerca finanziamenti immediati."

            # --- AZIONE 2: ANALISI PERCORSI ---
            profilo = str(riga['T12_PROFILO_STRATEGICO'])
            testo_percorsi = ""
            if "A" in profilo:
                testo_percorsi += f"\n- PERCORSO A (Domanda): Identificate {riga['T21_N_AZIENDE_IDONEE']} aziende idonee per un fabbisogno di {riga['T21_FABBISOGNO_H2_TON_ANNO']} t/anno."
            if "B" in profilo:
                testo_percorsi += f"\n- PERCORSO B (Offerta): Potenziale di produzione locale di {riga['T24_POTENZIALE_PRODUZIONE_H2_TON_ANNO']} t/anno a un costo LCOH di {riga['T26_LCOH_EURO_KG']} Euro/kg."
            if "C" in profilo:
                testo_percorsi += f"\n- PERCORSO C (Logistica): Il territorio è classificato come nodo {riga['T27_VERDETTO_NODO']} sui corridoi TEN-T."

            # --- AZIONE 3: BILANCIO E SINERGIE ---
            # Uso .get per evitare crash se mancano colonne
            fabb_tot = float(riga.get('T21_FABBISOGNO_H2_TON_ANNO', 0)) + \
                       float(riga.get('T22_FABBISOGNO_H2_TON_ANNO', 0)) + \
                       float(riga.get('T23_FABBISOGNO_H2_TON_ANNO', 0))
            prod_pot = float(riga.get('T24_POTENZIALE_PRODUZIONE_H2_TON_ANNO', 0))
            bilancio = prod_pot - fabb_tot

            testo_sinergie = f"\n- Fabbisogno Totale Stimato: {fabb_tot:.1f} t/anno\n- Produzione Potenziale Locale: {prod_pot:.1f} t/anno\n- Bilancio Netto: {bilancio:.1f} t/anno"
            
            if profilo == "AB":
                testo_sinergie += "\nSinergia H2 Valley: Possibilità di bilanciare domanda e offerta localmente."
            elif profilo == "AC":
                testo_sinergie += "\nSinergia Logistica-Industriale: Sfruttare i transiti per alimentare i consumi HTA."

            # --- AZIONE 4: ROADMAP ---
            if livello <= 8:
                roadmap = "1. Formazione tecnica; 2. Scouting stakeholder; 3. Studio di prefattibilità."
            else:
                roadmap = "1. Progettazione definitiva; 2. Candidatura Bandi PNRR; 3. Accordi di Off-take."

            # --- ASSEMBLAGGIO FINALE ---
            full_plan = f"""Punto di situazione per il Comune di {riga['NOME_COMUNE']}.

1. POSIZIONAMENTO STRATEGICO (AZIONE 1)
Livello Maturità: {liv_testo} ({livello}/18)
Strategia consigliata: {visione}

2. ANALISI TECNICA TERRITORIALE (AZIONE 2)
Profilo Strategico: {profilo}
{testo_percorsi}

3. QUANTIFICAZIONE E SINERGIE (AZIONE 3)
{testo_sinergie}

4. ROADMAP DI ATTUAZIONE (AZIONE 4)
Step prioritari: {roadmap}
"""

            # Visualizzazione a schermo
            st.divider()
            st.markdown(f"### Report Strategico: {riga['NOME_COMUNE']}")
            st.code(full_plan, language="text")

            # --- DOWNLOAD PDF ---
            # --- E nel blocco del tasto di download ---
            if st.button("PREPARA PDF ISTITUZIONALE"):
                try:
                    pdf_output = generate_pdf(riga, full_plan)
                    
                    # Ora pdf_output è un oggetto 'bytes' perfetto per Streamlit
                    st.success("Documento pronto!")
                    st.download_button(
                        label="⬇️ Scarica Action Plan (PDF)",
                        data=pdf_output,
                        file_name=f"H2READY_Plan_{riga['NOME_COMUNE']}.pdf",
                        mime="application/pdf"
                    )
                except Exception as e:
                    st.error(f"Errore durante la creazione del PDF: {e}")

        else:
            st.warning(f"Nessun dato trovato per l'ID: {id_ricercato}. Verifica nel Google Sheet.")
            
    except Exception as e:
        st.error(f"Errore tecnico: {e}")
