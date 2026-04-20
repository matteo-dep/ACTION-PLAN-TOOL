import streamlit as st
from streamlit_gsheets import GSheetsConnection
from fpdf import FPDF
import os

# --- 1. CONFIGURAZIONE STREAMLIT ---
st.set_page_config(page_title="H2READY Toolkit", layout="centered")

# --- 2. FUNZIONE DI PULIZIA CARATTERI ---
def clean_for_pdf(text):
    if not isinstance(text, str):
        text = str(text)
    replacements = {
        '“': '"', '”': '"', '‘': "'", '’': "'", 
        '–': '-', '—': '-', '…': '...',
        '€': 'Euro', 'CO₂': 'CO2', 'H₂': 'H2',
        '✅': '-', '•': '-', '·': '-'
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text.encode('latin-1', 'replace').decode('latin-1')

# --- 3. CLASSE PDF PROFESSIONALE ---
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

# --- 4. FUNZIONE PER PAGINE DI TITOLO (PASSI) ---
def add_step_page(pdf, title):
    pdf.add_page()
    pdf.set_fill_color(0, 51, 153) 
    pdf.rect(0, 0, 210, 297, 'F') 
    pdf.set_y(130)
    pdf.set_font('Arial', 'B', 20)
    pdf.set_text_color(255, 255, 255) 
    pdf.multi_cell(0, 15, clean_for_pdf(title), 0, 'C')

# --- 5. FUNZIONE PER SCRIVERE IL MARKDOWN NEL PDF ---
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

# --- 6. FUNZIONE DI GENERAZIONE DEL DOCUMENTO PDF ---
def generate_pdf(riga, intro_text, struttura_text, mat_intro, mat_dettaglio, profilo_intro, profilo_dettaglio, tecnico_text):
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

    # --- INTRODUZIONE E STRUTTURA ---
    pdf.add_page()
    write_markdown_to_pdf(pdf, intro_text)
    pdf.add_page()
    write_markdown_to_pdf(pdf, struttura_text)

    # --- PASSO 1: MATURITA E PROFILO IDENTIFICATO ---
    add_step_page(pdf, "PASSO 1: Determinazione del livello di maturità del comune e Profilo Identificato")
    
    pdf.add_page()
    # 1. Testo Intro Maturità
    write_markdown_to_pdf(pdf, mat_intro)
    pdf.ln(5)
    # 2. Testo Maturità Specifica (L1, L2 o L3)
    write_markdown_to_pdf(pdf, mat_dettaglio)
    pdf.ln(8)
    # 3. Testo Intro Profilo
    write_markdown_to_pdf(pdf, profilo_intro)
    pdf.ln(5)
    # 4. Testo Profilo Specifico (A, B, C, AB, ecc.)
    write_markdown_to_pdf(pdf, profilo_dettaglio)

    # --- PASSO 2: RISULTATO DEI PERCORSI IDENTIFICATI ---
    add_step_page(pdf, "PASSO 2: Risultato dei percorsi identificati")
    pdf.add_page()
    
    # Questo accoglierà i dati veri e propri che stiamo per creare
    write_markdown_to_pdf(pdf, tecnico_text)

    # --- PASSO 3: ANALISI INCROCIATA ---
    add_step_page(pdf, "PASSO 3: Analisi incrociata")
    pdf.add_page()
    pdf.set_font('Arial', 'I', 11)
    pdf.cell(0, 10, "Sezione in fase di elaborazione...", 0, 1)

    # --- PASSO 4: ELABORAZIONE FINALE ---
    add_step_page(pdf, "PASSO 4: Elaborazione finale su misura")
    pdf.add_page()
    pdf.set_font('Arial', 'I', 11)
    pdf.cell(0, 10, "Sezione in fase di elaborazione...", 0, 1)
    
    return bytes(pdf.output())

# --- 7. LOGICA E INTERFACCIA STREAMLIT ---
st.markdown('<div style="background-color:#003399;padding:20px;border-radius:10px;text-align:center"><h1 style="color:white;margin:0">H2READY TOOLKIT</h1></div>', unsafe_allow_html=True)
st.write("")

conn = st.connection("gsheets", type=GSheetsConnection)
id_ricercato = st.text_input("Inserisci ID_ISTAT:")

if id_ricercato:
    try:
        df = conn.read(ttl=0)
        df.columns = df.columns.str.strip()
        res = df[df['ID_ISTAT'].astype(str).str.strip() == str(id_ricercato).strip()]

        if not res.empty:
            riga = res.iloc[0]
            try:
                score = int(riga['T11_LIVELLO_MATURITA'])
            except:
                score = 0
            
            # Pulisce la stringa del profilo per caricare il file esatto (es. "AB")
            profilo_codice_raw = str(riga['T12_PROFILO_STRATEGICO']).strip()
            profilo_codice = profilo_codice_raw.replace("Profilo ", "").replace("PROFILO ", "")
            
            if score < 3:
                st.error("⚠️ Il Comune risulta in Livello 0. Action Plan non generabile.")
            else:
                st.success(f"Dati pronti per {riga['NOME_COMUNE']} (Profilo identificato: {profilo_codice})")

                def get_md(filename):
                    if os.path.exists(filename):
                        with open(filename, "r", encoding="utf-8") as f: return f.read()
                    return f"[File {filename} non trovato]"

                # File statici
                intro_md = get_md("1-intro_it.md")
                struttura_md = get_md("2-struttura_plan_it.md")
                
                # --- PASSO 1: File Dinamici ---
                mat_intro_md = get_md("3-maturita_intro_it.md")
                if 3 <= score <= 8: mat_file = "3-maturita_L1_it.md"
                elif 9 <= score <= 14: mat_file = "3-maturita_L2_it.md"
                else: mat_file = "3-maturita_L3_it.md"
                mat_dettaglio_md = get_md(mat_file)

                profilo_intro_md = get_md("4-profilo_intro_it.md")
                profilo_file = f"4-profilo_{profilo_codice}_it.md"
                profilo_dettaglio_md = get_md(profilo_file)

                # --- PASSO 2: Placeholder per l'analisi tecnica da popolare ---
                testo_tecnico = "# Sintesi dei Risultati Tecnici\nIn questa sezione verranno inseriti i dati quantitativi raccolti sui percorsi (Domanda, Offerta, Logistica)."

                if st.button("🚀 GENERA PDF"):
                    pdf_bytes = generate_pdf(riga, intro_md, struttura_md, mat_intro_md, mat_dettaglio_md, profilo_intro_md, profilo_dettaglio_md, testo_tecnico)
                    st.download_button(
                        label="⬇️ Scarica PDF",
                        data=pdf_bytes,
                        file_name=f"H2READY_{riga['NOME_COMUNE']}.pdf",
                        mime="application/pdf"
                    )
        else:
            st.warning("ID non trovato.")
            
    except Exception as e:
        st.error(f"Errore: {e}")
