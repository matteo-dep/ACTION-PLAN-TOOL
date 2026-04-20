import streamlit as st
from streamlit_gsheets import GSheetsConnection
from fpdf import FPDF
import os

# --- 1. FUNZIONE DI PULIZIA CARATTERI ---
def clean_for_pdf(text):
    replacements = {
        '“': '"', '”': '"', '‘': "'", '’': "'", 
        '–': '-', '—': '-', '…': '...',
        '€': 'Euro', 'CO₂': 'CO2', 'H₂': 'H2',
        '✅': '-', '•': '-', '·': '-'
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
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

# --- 3. FUNZIONE PER SCRIVERE IL MARKDOWN NEL PDF ---
def write_markdown_to_pdf(pdf, md_text):
    lines = md_text.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            pdf.ln(5) 
            continue
        
        if line.startswith('###'):
            pdf.set_font('Arial', 'B', 12)
            pdf.set_text_color(0, 51, 153)
            pdf.cell(0, 10, clean_for_pdf(line.replace('###', '').strip()), 0, 1)
            pdf.set_text_color(0, 0, 0) 
        elif line.startswith('##'):
            pdf.set_font('Arial', 'B', 14)
            pdf.set_text_color(0, 51, 153)
            pdf.cell(0, 10, clean_for_pdf(line.replace('##', '').strip()), 0, 1)
            pdf.set_text_color(0, 0, 0)
        elif line.startswith('#'):
            pdf.set_font('Arial', 'B', 16)
            pdf.set_text_color(0, 51, 153)
            pdf.cell(0, 10, clean_for_pdf(line.replace('#', '').strip()), 0, 1)
            pdf.set_text_color(0, 0, 0)
        else:
            pdf.set_font('Arial', '', 11)
            pdf.multi_cell(0, 7, clean_for_pdf(line))
            pdf.ln(2)

# --- 4. FUNZIONE DI GENERAZIONE DEL DOCUMENTO PDF ---
# ... (Parti precedenti: clean_for_pdf, H2ReadyPDF, write_markdown_to_pdf rimangono uguali)

def generate_pdf(riga, intro_text, struttura_text, mat_intro, mat_dettaglio, tecnico_text):
    pdf = H2ReadyPDF()
    
    # --- PAGINA 1: COPERTINA ---
    pdf.add_page()
    pdf.set_fill_color(0, 51, 153) 
    pdf.rect(0, 0, 10, 297, 'F') 
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

    # --- PAGINA 2: INTRODUZIONE E STRUTTURA ---
    pdf.add_page()
    write_markdown_to_pdf(pdf, intro_text)
    pdf.add_page()
    write_markdown_to_pdf(pdf, struttura_text)

    # --- PAGINA 3: ANALISI MATURITÀ (DINAMICA: INTRO + LIVELLO) ---
    pdf.add_page()
    write_markdown_to_pdf(pdf, mat_intro)
    pdf.ln(5)
    write_markdown_to_pdf(pdf, mat_dettaglio)

    # --- PAGINA 4: ANALISI TECNICA ---
    pdf.add_page()
    pdf.set_font('Arial', 'B', 16)
    pdf.set_text_color(0, 51, 153)
    pdf.cell(0, 10, "2. ANALISI TECNICA DEL TERRITORIO", 0, 1, 'L')
    pdf.ln(5)
    pdf.set_font('Arial', '', 11)
    pdf.set_text_color(0, 0, 0)
    pdf.multi_cell(0, 7, clean_for_pdf(tecnico_text))
    
    return bytes(pdf.output())

# --- LOGICA STREAMLIT ---
# ... (Codice connessione GSheet)

if id_ricercato:
    try:
        df = conn.read(ttl=0)
        df.columns = df.columns.str.strip()
        res = df[df['ID_ISTAT'].astype(str).str.strip() == str(id_ricercato).strip()]

        if not res.empty:
            riga = res.iloc[0]
            score = int(riga['T11_LIVELLO_MATURITA'])
            
            # --- GESTIONE LIVELLO 0 ---
            if score < 3:
                st.error("⚠️ Il Comune risulta in Livello 0. Per questo livello non è prevista la redazione di un Action Plan automatico. Si consiglia di procedere prima con attività di assistenza tecnica e formazione.")
            else:
                st.success(f"Dati pronti per {riga['NOME_COMUNE']} (Livello {score})")

                def get_md(filename):
                    if os.path.exists(filename):
                        with open(filename, "r", encoding="utf-8") as f: return f.read()
                    return f"[Errore: {filename} non trovato]"

                intro_md = get_md("1-intro_it.md")
                struttura_md = get_md("2-struttura_plan_it.md")
                mat_intro_md = get_md("3-maturita_intro_it.md")

                # LOGICA DINAMICA MATURITÀ
                if 3 <= score <= 8: mat_file = "3-maturita_L1_it.md"
                elif 9 <= score <= 14: mat_file = "3-maturita_L2_it.md"
                else: mat_file = "3-maturita_L3_it.md"
                
                mat_dettaglio_md = get_md(mat_file)

                # Testo Tecnico Temporaneo
                testo_tecnico = f"Profilo: {riga['T12_PROFILO_STRATEGICO']}\n\nAnalisi in corso..."

                if st.button("🚀 GENERA PDF"):
                    pdf_bytes = generate_pdf(riga, intro_md, struttura_md, mat_intro_md, mat_dettaglio_md, testo_tecnico)
                    st.download_button(
                        label="⬇️ Scarica PDF",
                        data=pdf_bytes,
                        file_name=f"H2READY_{riga['NOME_COMUNE']}.pdf",
                        mime="application/pdf"
                    )
        else:
            st.warning("ID non trovato.")
    except Exception as e:
        st.error(f"Errore tecnico: {e}")
