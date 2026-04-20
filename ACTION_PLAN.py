import streamlit as st
from streamlit_gsheets import GSheetsConnection
from fpdf import FPDF
import os

# --- 1. CLASSE PDF PROFESSIONALE ---
class H2ReadyPDF(FPDF):
    def header(self):
        # Logo piccolo in alto a sinistra (solo dalle pagine successive alla copertina)
        if self.page_no() > 1:
            if os.path.exists("logo_h2ready.png"):
                self.image("logo_h2ready.png", 10, 8, 25)
            self.set_font('Arial', 'B', 8)
            self.set_text_color(150)
            self.set_x(40) # Sposta il testo per non sovrapporsi al logo
            self.cell(0, 5, 'H2READY - Progetto Interreg Italia-Slovenia', 0, 1, 'L')
            self.line(10, 18, 200, 18)
            self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(128)
        self.cell(0, 10, f'Pagina {self.page_no()} - Documento generato dal Toolkit H2READY', 0, 0, 'C')

def generate_pdf(riga, intro_text, plan_text, lang_code):
    pdf = H2ReadyPDF()
    
    # --- PAGINA 1: COPERTINA ---
    pdf.add_page()
    # Fascia Blu Laterale (Stile moderno)
    pdf.set_fill_color(0, 51, 153)
    pdf.rect(0, 0, 10, 297, 'F')
    
    # Logo centrato in copertina
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
    pdf.cell(0, 15, f"COMUNE DI {riga['NOME_COMUNE'].upper()}", 0, 1, 'C')
    
    pdf.set_y(-50)
    pdf.set_font('Arial', '', 12)
    pdf.cell(0, 10, "Documento Strategico di Transizione Energetica", 0, 1, 'C')
    pdf.cell(0, 10, "Progetto cofinanziato dall'Unione Europea", 0, 1, 'C')

    # --- PAGINA 2: INTRODUZIONE (Testo 1-intro_...) ---
    pdf.add_page()
    pdf.set_font('Arial', 'B', 16)
    pdf.set_text_color(0, 51, 153)
    pdf.cell(0, 10, "1. CONTESTO E OBIETTIVI", 0, 1, 'L')
    pdf.ln(5)
    
    pdf.set_font('Arial', '', 11)
    pdf.set_text_color(0, 0, 0)
    # Pulizia caratteri speciali
    clean_intro = intro_text.replace('’', "'").replace('✅', "-").replace('€', "Euro").replace('•', "-")
    pdf.multi_cell(0, 7, clean_intro)

    # --- PAGINA 3: ANALISI TECNICA (Dati GSheet) ---
    pdf.add_page()
    pdf.set_font('Arial', 'B', 16)
    pdf.set_text_color(0, 51, 153)
    pdf.cell(0, 10, "2. ANALISI DEL TERRITORIO", 0, 1, 'L')
    pdf.ln(5)
    
    pdf.set_font('Arial', '', 11)
    pdf.set_text_color(0, 0, 0)
    clean_plan = plan_text.replace('’', "'").replace('✅', "-").replace('€', "Euro")
    pdf.multi_cell(0, 7, clean_plan)
    
    return bytes(pdf.output())

# --- 2. FUNZIONI DI CARICAMENTO ---
def load_markdown(num, tag, lang):
    filename = f"{num}-{tag}_{lang}.md"
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            return f.read()
    return "Contenuto non disponibile."

# --- 3. INTERFACCIA STREAMLIT ---
st.set_page_config(page_title="H2READY Toolkit", layout="wide")

# Sidebar lingua
lingua = st.sidebar.selectbox("Seleziona Lingua", ["Italiano", "English", "Slovenščina"])
lang_code = {"Italiano": "it", "English": "en", "Slovenščina": "sl"}[lingua]

# Hero Header Streamlit
st.markdown('<div style="background-color:#003399;padding:20px;border-radius:10px"><h1 style="color:white;text-align:center">H2READY TOOLKIT</h1></div>', unsafe_allow_html=True)

# Caricamento dinamico col nuovo sistema numerato
intro_md = load_markdown(1, "intro", lang_code)
st.markdown(intro_md)

st.divider()

# Logica GSheet
conn = st.connection("gsheets", type=GSheetsConnection)
id_ricercato = st.text_input("Inserisci ID_ISTAT del Comune:")

if id_ricercato:
    try:
        df = conn.read(ttl=0)
        df.columns = df.columns.str.strip()
        res = df[df['ID_ISTAT'].astype(str).str.strip() == str(id_ricercato).strip()]

        if not res.empty:
            riga = res.iloc[0]
            st.success(f"Dati caricati per: {riga['NOME_COMUNE']}")

            # Costruzione testo tecnico
            testo_tecnico = f"POSIZIONAMENTO (AZIONE 1)\n- Maturità: {riga['T11_LIVELLO_MATURITA']}/18\n- Profilo: {riga['T12_PROFILO_STRATEGICO']}\n\n"
            testo_tecnico += f"ANALISI TECNICA (AZIONE 2)\n"
            testo_tecnico += f"- Percorso: {riga.get('T12_NOTE_SINERGIE', 'Dati tecnici in elaborazione.')}"

            # TASTO PDF
            if st.button("🚀 GENERA PDF ISTITUZIONALE"):
                pdf_bytes = generate_pdf(riga, intro_md, testo_tecnico, lang_code)
                st.download_button(
                    label="⬇️ Scarica Action Plan",
                    data=pdf_bytes,
                    file_name=f"ActionPlan_{riga['NOME_COMUNE']}.pdf",
                    mime="application/pdf"
                )
    except Exception as e:
        st.error(f"Errore: {e}")
