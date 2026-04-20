import streamlit as st
from streamlit_gsheets import GSheetsConnection
from fpdf import FPDF
import os

# --- 1. CONFIGURAZIONE PDF PROFESSIONALE ---
class H2ReadyPDF(FPDF):
    def header(self):
        if self.page_no() > 1:
            self.set_font('Arial', 'B', 8)
            self.set_text_color(150)
            self.cell(0, 5, 'H2READY - Action Plan Transfrontaliero', 0, 1, 'R')
            self.line(10, 15, 200, 15) # Linea sotto header
            self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(128)
        self.cell(0, 10, f'Pagina {self.page_no()} - Progetto cofinanziato dall\'Unione europea - Interreg Italia-Slovenia', 0, 0, 'C')

def generate_pdf(riga, intro_text, plan_text, lingua):
    pdf = H2ReadyPDF()
    
    # --- PAGINA 1: COPERTINA ISTITUZIONALE ---
    pdf.add_page()
    
    # Sfondo Blu per fascia superiore (stile sito)
    pdf.set_fill_color(0, 51, 153)
    pdf.rect(0, 0, 210, 100, 'F')
    
    # Titolo in Bianco su fondo Blu
    pdf.set_y(40)
    pdf.set_font('Arial', 'B', 32)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 20, "ACTION PLAN", 0, 1, 'C')
    pdf.set_font('Arial', 'B', 40)
    pdf.cell(0, 20, "H2READY", 0, 1, 'C')
    
    # Dettagli Comune (sotto la fascia blu)
    pdf.set_y(120)
    pdf.set_font('Arial', 'B', 24)
    pdf.set_text_color(0, 51, 153)
    pdf.cell(0, 15, f"COMUNE DI {riga['NOME_COMUNE'].upper()}", 0, 1, 'C')
    
    pdf.set_y(150)
    pdf.set_font('Arial', '', 14)
    pdf.set_text_color(50, 50, 50)
    data_gen = "Aprile 2024" # O dinamica
    pdf.cell(0, 10, f"Strategia per lo sviluppo di ecosistemi a idrogeno verde", 0, 1, 'C')
    pdf.cell(0, 10, f"Documento Tecnico Strategico", 0, 1, 'C')

    # --- PAGINA 2: INTRODUZIONE E CONTESTO (AMETHyST Style) ---
    pdf.add_page()
    pdf.set_font('Arial', 'B', 16)
    pdf.set_text_color(0, 51, 153)
    titolo_intro = {"it": "1. CONTESTO E OBIETTIVI", "en": "1. CONTEXT AND OBJECTIVES", "sl": "1. KONTEKST IN CILJI"}
    pdf.cell(0, 10, titolo_intro.get(lang_code, titolo_intro["it"]), 0, 1, 'L')
    pdf.ln(5)
    
    pdf.set_font('Arial', '', 11)
    pdf.set_text_color(0, 0, 0)
    # Pulizia caratteri per FPDF
    intro_pulita = intro_text.replace('’', "'").replace('✅', "-").replace('€', "Euro").replace('•', "-")
    pdf.multi_cell(0, 7, intro_pulita)

    # --- PAGINA 3+: PIANO D'AZIONE TECNICO ---
    pdf.add_page()
    pdf.set_font('Arial', 'B', 16)
    pdf.set_text_color(0, 51, 153)
    titolo_plan = {"it": "2. ANALISI E ROADMAP", "en": "2. ANALYSIS AND ROADMAP", "sl": "2. ANALIZA IN NAČRT"}
    pdf.cell(0, 10, titolo_plan.get(lang_code, titolo_plan["it"]), 0, 1, 'L')
    pdf.ln(5)

    pdf.set_font('Arial', '', 11)
    pdf.set_text_color(0, 0, 0)
    plan_pulito = plan_text.replace('’', "'").replace('✅', "-").replace('€', "Euro").replace('•', "-")
    pdf.multi_cell(0, 7, plan_pulito)
    
    return bytes(pdf.output())

# --- 2. FUNZIONI DI CARICAMENTO ---
def load_markdown(file_path):
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    return "Contenuto non disponibile."

# --- 3. INTERFACCIA STREAMLIT ---
st.set_page_config(page_title="H2READY Toolkit", layout="wide")

# Sidebar lingua
lingua = st.sidebar.selectbox("Seleziona Lingua", ["Italiano", "English", "Slovenščina"])
lang_code = {"Italiano": "it", "English": "en", "Slovenščina": "sl"}[lingua]

# UI Streamlit (Sito Style)
st.markdown('<div style="background-color:#003399;padding:20px;border-radius:10px"><h1 style="color:white;text-align:center">H2READY TOOLKIT</h1></div>', unsafe_allow_html=True)

# Caricamento testi intro
intro_md = load_markdown(f"intro_{lang_code}.md")
st.markdown(intro_md)

st.divider()

# Logica di ricerca
conn = st.connection("gsheets", type=GSheetsConnection)
id_ricercato = st.text_input("Inserisci ID_ISTAT:")

if id_ricercato:
    try:
        df = conn.read(ttl=0)
        df.columns = df.columns.str.strip()
        res = df[df['ID_ISTAT'].astype(str).str.strip() == str(id_ricercato).strip()]

        if not res.empty:
            riga = res.iloc[0]
            st.success(f"Generazione piano per: {riga['NOME_COMUNE']}")

            # Costruiamo il testo tecnico del piano
            testo_tecnico = f"Profilo Strategico: {riga['T12_PROFILO_STRATEGICO']}\n"
            testo_tecnico += f"Maturità: {riga['T11_LIVELLO_MATURITA']}/18\n\n"
            testo_tecnico += f"Sinergie: {riga.get('T12_NOTE_SINERGIE', 'In fase di analisi.')}"

            # TASTO PDF
            if st.button("🚀 GENERA PDF ISTITUZIONALE"):
                # PASSIAMO SIA L'INTRO CHE IL PIANO
                pdf_bytes = generate_pdf(riga, intro_md, testo_tecnico, lingua)
                st.download_button(
                    label="⬇️ Scarica PDF",
                    data=pdf_bytes,
                    file_name=f"H2READY_{riga['NOME_COMUNE']}.pdf",
                    mime="application/pdf"
                )
    except Exception as e:
        st.error(f"Errore: {e}")
