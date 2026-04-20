import streamlit as st
from streamlit_gsheets import GSheetsConnection
from fpdf import FPDF

# --- 1. CONFIGURAZIONE PDF CON COPERTINA ---
class H2ReadyPDF(FPDF):
    def header(self):
        if self.page_no() > 1:  # Header solo dalle pagine successive alla copertina
            self.set_font('Arial', 'B', 8)
            self.set_text_color(100)
            self.cell(0, 5, 'H2READY - TOOLKIT STRATEGICO TRANSFRONTALIERA', 0, 1, 'R')
            self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(128)
        self.cell(0, 10, f'Pagina {self.page_no()} - Progetto cofinanziato dall\'Unione europea - Interreg Italia-Slovenia', 0, 0, 'C')

def generate_pdf(riga, full_text, lingua_selezionata):
    pdf = H2ReadyPDF()
    
    # --- PAGINA 1: COPERTINA ---
    pdf.add_page()
    # Spazio per logo (se disponibile localmente)
    # pdf.image("logo_h2ready.png", x=80, y=20, w=50)
    
    pdf.set_y(100)
    pdf.set_font('Arial', 'B', 28)
    pdf.set_text_color(0, 51, 153) # Blu Interreg
    pdf.cell(0, 15, "ACTION PLAN IDROGENO", 0, 1, 'C')
    
    pdf.set_font('Arial', '', 18)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 15, f"Comune di {riga['NOME_COMUNE']}", 0, 1, 'C')
    
    pdf.set_y(-60)
    pdf.set_font('Arial', 'I', 12)
    pdf.cell(0, 10, f"Generato tramite il Toolkit H2READY", 0, 1, 'C')
    pdf.cell(0, 10, f"Lingua: {lingua_selezionata}", 0, 1, 'C')

    # --- PAGINA 2 E SUCCESSIVE: CONTENUTO ---
    pdf.add_page()
    pdf.set_y(20)
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, "SINTESI STRATEGICA", 0, 1, 'L')
    pdf.ln(5)
    
    # Pulizia caratteri per FPDF
    testo_pulito = (full_text
                 .replace('’', "'").replace('‘', "'")
                 .replace('✅', "-").replace('€', "Euro")
                 .replace('–', "-").replace('•', "-"))

    pdf.set_font('Arial', '', 11)
    pdf.multi_cell(0, 7, testo_pulito)
    
    return bytes(pdf.output())

# --- 2. FUNZIONI DI UTILITÀ ---
def load_markdown(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "Contenuto in fase di redazione (intro_it.md non trovato)..."

# --- 3. CONFIGURAZIONE PAGINA STREAMLIT ---
st.set_page_config(page_title="H2READY - Toolkit", layout="wide")

# Sidebar
st.sidebar.title("Impostazioni")
lingua = st.sidebar.selectbox("Lingua / Language / Jezik", ["Italiano", "English", "Slovenščina"])
lang_code = {"Italiano": "it", "English": "en", "Slovenščina": "sl"}[lingua]

# Hero Header (Stile Sito Web)
st.markdown(
    """
    <div style="background-color: #f8f9fa; padding: 30px; border-radius: 15px; border-bottom: 8px solid #003399; margin-bottom: 20px;">
        <h1 style="color: #003399; margin-bottom: 0; font-family: 'Arial';">H2READY</h1>
        <p style="font-size: 1.2rem; font-style: italic; color: #555;">Potenziare la resilienza dell'area transfrontaliera tramite l'uso dell'idrogeno</p>
    </div>
    """, 
    unsafe_allow_html=True
)

# Loghi
col_logo1, col_logo2 = st.columns([1, 4])
with col_logo1:
    st.image("https://www.ita-slo.eu/sites/default/files/styles/medium/public/logo_progetto_h2ready.png", width=220)

# --- 4. INTRODUZIONE AL KIT ---
st.write("")
intro_file = f"intro_{lang_code}.md"
if lingua == "Italiano":
    st.markdown(load_markdown(intro_file))
else:
    st.info(f"The {lingua} version is coming soon. Using Italian as reference.")
    st.markdown(load_markdown("intro_it.md"))

st.divider()

# --- 5. LOGICA DI CALCOLO E GENERAZIONE (GSheets) ---
conn = st.connection("gsheets", type=GSheetsConnection)

st.subheader("📊 Generatore Action Plan Personalizzato")
id_ricercato = st.text_input("Inserisci ID_ISTAT o Codice Univoco (es. 030043):")

if id_ricercato:
    try:
        df = conn.read(ttl=0)
        df.columns = df.columns.str.strip()
        riga_comune = df[df['ID_ISTAT'].astype(str).str.strip() == str(id_ricercato).strip()]

        if not riga_comune.empty:
            riga = riga_comune.iloc[0]
            st.success(f"✅ Comune identificato: **{riga['NOME_COMUNE']}**")

            # --- A. CALCOLI TECNICI ---
            livello = int(riga['T11_LIVELLO_MATURITA'])
            profilo = str(riga['T12_PROFILO_STRATEGICO'])
            
            # Bilancio Energetico (Azione 3)
            fabb_tot = sum([float(riga.get(c, 0)) for c in ['T21_FABBISOGNO_H2_TON_ANNO', 'T22_FABBISOGNO_H2_TON_ANNO', 'T23_FABBISOGNO_H2_TON_ANNO']])
            prod_pot = float(riga.get('T24_POTENZIALE_PRODUZIONE_H2_TON_ANNO', 0))
            bilancio = prod_pot - fabb_tot

            # --- B. COSTRUZIONE TESTO ---
            full_plan = f"REPORT PER IL COMUNE DI {riga['NOME_COMUNE']}\n\n"
            full_plan += f"1. POSIZIONAMENTO (AZIONE 1)\n- Maturità: Livello {livello}/18\n- Profilo: {profilo}\n\n"
            
            full_plan += f"2. ANALISI TECNICA (AZIONE 2)\n"
            if "A" in profilo: full_plan += f"- Percorso A (Domanda): {riga['T21_FABBISOGNO_H2_TON_ANNO']} t/anno.\n"
            if "B" in profilo: full_plan += f"- Percorso B (Offerta): {prod_pot} t/anno (LCOH: {riga['T26_LCOH_EURO_KG']} Euro/kg).\n"
            if "C" in profilo: full_plan += f"- Percorso C (Logistica): Nodo {riga['T27_VERDETTO_NODO']}.\n"
            
            full_plan += f"\n3. BILANCIO E SINERGIE (AZIONE 3)\n"
            full_plan += f"- Bilancio Netto: {bilancio:.1f} t/anno.\n"
            if "AB" in profilo: full_plan += "- Sinergia identificata: H2 Valley Integrata (Domanda+Offerta).\n"

            full_plan += f"\n4. ROADMAP (AZIONE 4)\n"
            full_plan += "Step 1: Mappatura stakeholder; Step 2: Studio fattibilità; Step 3: Finanziamenti." if livello < 9 else "Step 1: Progettazione; Step 2: Bandi PNRR; Step 3: Cantierizzazione."

            # --- C. VISUALIZZAZIONE E PDF ---
            st.code(full_plan, language="text")

            if st.button("🚀 PREPARA PDF ISTITUZIONALE"):
                pdf_output = generate_pdf(riga, full_plan, lingua)
                st.download_button(
                    label="⬇️ SCARICA ACTION PLAN (PDF)",
                    data=pdf_output,
                    file_name=f"H2READY_ActionPlan_{riga['NOME_COMUNE']}.pdf",
                    mime="application/pdf"
                )

        else:
            st.warning("Nessun dato trovato per questo ID.")
    except Exception as e:
        st.error(f"Errore: {e}")
