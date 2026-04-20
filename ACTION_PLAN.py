import streamlit as st
from streamlit_gsheets import GSheetsConnection
from fpdf import FPDF
import os

# --- 1. FUNZIONE DI PULIZIA CARATTERI PER PDF ---
def clean_for_pdf(text):
    """Sostituisce i caratteri Unicode non supportati dai font standard PDF"""
    replacements = {
        '“': '"', '”': '"', '‘': "'", '’': "'", 
        '–': '-', '—': '-', '…': '...',
        '€': 'Euro', 'CO₂': 'CO2', 'H₂': 'H2',
        '✅': '-', '•': '-', '·': '-'
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    # Rimuove eventuali altri caratteri non latin-1 per sicurezza
    return text.encode('latin-1', 'replace').decode('latin-1')

# --- 2. CLASSE PDF PROFESSIONALE ---
class H2ReadyPDF(FPDF):
    def header(self):
        if self.page_no() > 1:
            if os.path.exists("logo_h2ready.png"):
                self.image("logo_h2ready.png", 10, 8, 25)
            self.set_font('Arial', 'B', 8)
            self.set_text_color(150)
            self.set_x(40)
            self.cell(0, 5, 'H2READY - Progetto Interreg Italia-Slovenia', 0, 1, 'L')
            self.line(10, 18, 200, 18)
            self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(128)
        self.cell(0, 10, f'Pagina {self.page_no()} - Documento generato dal Toolkit H2READY', 0, 0, 'C')

def generate_pdf(riga, intro_text, tecnico_text):
    pdf = H2ReadyPDF()
    
    # --- PAGINA 1: COPERTINA ---
    pdf.add_page()
    pdf.set_fill_color(0, 51, 153) # Blu Interreg
    pdf.rect(0, 0, 10, 297, 'F') # Fascia laterale
    
    if os.path.exists("logo_h2ready.png"):
        pdf.image("logo_h2ready.png", x=75, y=30, w=60)
    
    pdf.set_y(100)
    pdf.set_font('Arial', 'B', 32)
    pdf.set_text_color(0, 51, 153)
    pdf.cell(0, 20, "ACTION PLAN", 0, 1, 'C')
    pdf.set_font('Arial', 'B', 40)
    pdf.cell(0, 20, "H2READY", 0, 1, 'C')
    
    pdf.ln(30)
    pdf.set_font('Arial', 'B', 24)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 15, f"COMUNE DI {clean_for_pdf(riga['NOME_COMUNE']).upper()}", 0, 1, 'C')
    
    pdf.set_y(-50)
    pdf.set_font('Arial', '', 12)
    pdf.cell(0, 10, "Documento Strategico di Transizione Energetica", 0, 1, 'C')
    pdf.cell(0, 10, "Progetto cofinanziato dall'Unione Europea", 0, 1, 'C')

    # --- PAGINA 2: INTRODUZIONE (Dal file .md) ---
    pdf.add_page()
    pdf.set_font('Arial', 'B', 16)
    pdf.set_text_color(0, 51, 153)
    pdf.cell(0, 10, "1. CONTESTO E OBIETTIVI", 0, 1, 'L')
    pdf.ln(5)
    
    pdf.set_font('Arial', '', 11)
    pdf.set_text_color(0, 0, 0)
    pdf.multi_cell(0, 7, clean_for_pdf(intro_text))

    # --- PAGINA 3: ANALISI TECNICA (Dal GSheet) ---
    pdf.add_page()
    pdf.set_font('Arial', 'B', 16)
    pdf.set_text_color(0, 51, 153)
    pdf.cell(0, 10, "2. ANALISI DEL TERRITORIO", 0, 1, 'L')
    pdf.ln(5)
    
    pdf.set_font('Arial', '', 11)
    pdf.multi_cell(0, 7, clean_for_pdf(tecnico_text))
    
    return bytes(pdf.output())

# --- 3. LOGICA STREAMLIT ---
st.set_page_config(page_title="H2READY Toolkit", layout="centered")

# Header Estetico
st.markdown('<div style="background-color:#003399;padding:20px;border-radius:10px;text-align:center"><h1 style="color:white;margin:0">H2READY TOOLKIT</h1></div>', unsafe_allow_html=True)
st.write("")

# Ricerca
conn = st.connection("gsheets", type=GSheetsConnection)
id_ricercato = st.text_input("Inserisci ID_ISTAT del Comune per generare il PDF:")

if id_ricercato:
    try:
        df = conn.read(ttl=0)
        df.columns = df.columns.str.strip()
        res = df[df['ID_ISTAT'].astype(str).str.strip() == str(id_ricercato).strip()]

        if not res.empty:
            riga = res.iloc[0]
            st.success(f"Dati pronti per il Comune di {riga['NOME_COMUNE']}")

            # 1. Carichiamo il testo dal file .md (che NON mostriamo a video)
            intro_path = "1-intro_it.md"
            intro_md = ""
            if os.path.exists(intro_path):
                with open(intro_path, "r", encoding="utf-8") as f:
                    intro_md = f.read()

            # 2. Prepariamo il testo tecnico dai dati GSheet
            testo_tecnico = f"POSIZIONAMENTO STRATEGICO\n- Livello di Maturità: {riga['T11_LIVELLO_MATURITA']}/18\n- Profilo Identificato: {riga['T12_PROFILO_STRATEGICO']}\n\n"
            testo_tecnico += f"SINTESI TECNICA:\n{riga.get('T12_NOTE_SINERGIE', 'Analisi dei flussi energetici e sinergie territoriali.')}"

            # 3. Bottone per il PDF
            if st.button("🚀 GENERA E SCARICA ACTION PLAN"):
                pdf_bytes = generate_pdf(riga, intro_md, testo_tecnico)
                st.download_button(
                    label="⬇️ Clicca qui per il Download",
                    data=pdf_bytes,
                    file_name=f"H2READY_ActionPlan_{riga['NOME_COMUNE']}.pdf",
                    mime="application/pdf"
                )
        else:
            st.warning("ID non trovato nel database.")
    except Exception as e:
        st.error(f"Errore: {e}")
