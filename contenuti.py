"""
H2READY Toolkit - configurazione dei dati e generazione dei testi.

Questo è il file da modificare per lavorare sui CONTENUTI:
mappatura delle colonne, etichette, testi dei percorsi e dell'analisi incrociata.
"""

import os
import re
import unicodedata

import pandas as pd

import ateco as AT

# =============================================================================
# COLONNE CHIAVE
# =============================================================================

COL_ID = "ID_ISTAT"
COL_NOME = "NOME_COMUNE"
COL_MATURITA = "T11_LIVELLO_MATURITA"
COL_SCORE = {"A": "T12_SCORE_A", "B": "T12_SCORE_B", "C": "T12_SCORE_C"}

SOGLIE_MATURITA = [(5, 8, "L1"), (9, 14, "L2"), (15, 999, "L3")]
SOGLIA_MINIMA = 5

# La lettera dominante entra sempre; le altre entrano se raggiungono almeno
# QUOTA_SECONDARIA del punteggio massimo.
QUOTA_SECONDARIA = 0.80
PUNTEGGIO_MINIMO = 0.0

NOMI_PROFILO = {
    "A": "Consumo - la domanda locale traina la transizione",
    "B": "Produzione - il territorio può generare idrogeno rinnovabile",
    "C": "Transito - il Comune si colloca su direttrici logistiche rilevanti",
}

# -----------------------------------------------------------------------------
# PARAMETRI DI RIFERIMENTO DEL PERCORSO A
# Fonte: "Modelli di Business per l'utilizzo dell'H2 e lo sviluppo della Filiera
# in Italia" (2024) e "Camion a idrogeno" (Roland Berger, 2021).
# Sono i valori su cui si tarano i giudizi qualitativi: modificarli qui.
# -----------------------------------------------------------------------------

# --- Soglie sulla domanda complessiva (processo + mobilità) ------------------
# Flotta minima ritenuta sostenibile: 10 mezzi pesanti x 26 kg/giorno x 300
# giorni, cioè circa 78 t/anno. È il riferimento per un progetto autonomo.
SOGLIA_MASSA_CRITICA_TON = 78.0
# Sotto questa soglia la domanda è troppo frammentata per un progetto autonomo
SOGLIA_DOMANDA_MINIMA_TON = 25.0

# --- Soglie sulla sola mobilità ---------------------------------------------
# Una flotta comunale non si misura con il metro del trasporto pesante: uno
# scuolabus percorre 80-100 km al giorno per circa 190 giorni di servizio, un
# camion a lungo raggio molti di più per 300 giorni. Le soglie qui sotto non
# derivano dal numero di mezzi ma dal minimo tecnico di erogazione, che è ciò
# che davvero determina la fattibilità del rifornimento.
#   30 t/anno = 100 kg/giorno: minimo per una stazione dedicata, anche piccola
#    8 t/anno =  27 kg/giorno: un solo mezzo pesante in servizio continuo
SOGLIA_MOBILITA_AUTONOMA_TON = 30.0
SOGLIA_MOBILITA_MINIMA_TON = 8.0

CONSUMO_BUS_KG_GIORNO = 26.0        # bus urbano da 12 m, 250 km/giorno

# I giorni di esercizio cambiano radicalmente da un'utenza all'altra: usarne uno
# solo sovrastima le scuole del 60% e sottostima l'industria continua del 15%.
GIORNI_OPERATIVI = 300              # trasporto pubblico e flotte comunali
GIORNI_INDUSTRIA_CONTINUA = 340     # vetro, acciaio, raffinazione: ciclo continuo
GIORNI_SCUOLE = 190                 # riscaldamento scolastico in zona climatica E/F
GIORNI_LOGISTICA = 250              # magazzini e movimentazione
EFFICIENZA_H2_KM_KG = 11.4          # mezzo pesante stradale
EFFICIENZA_DIESEL_KM_LITRO = 3.5    # mezzo pesante stradale
EMISSIONI_DIESEL_KG_LITRO = 2.7     # kgCO2 per litro di gasolio

# 1 kg di H2 sostituisce EFFICIENZA_H2_KM_KG / EFFICIENZA_DIESEL_KM_LITRO litri
LITRI_DIESEL_PER_KG_H2 = EFFICIENZA_H2_KM_KG / EFFICIENZA_DIESEL_KM_LITRO
CO2_DIESEL_SOSTITUITO_KG_KG_H2 = LITRI_DIESEL_PER_KG_H2 * EMISSIONI_DIESEL_KG_LITRO

# --- Emissioni dell'idrogeno prodotto ---------------------------------------
# Un chilogrammo di idrogeno non è mai a zero emissioni: dipende da come viene
# prodotto. Con elettricità di rete non certificata servono circa 55 kWh, che
# alle emissioni medie del sistema elettrico italiano valgono più di 14 kg di
# CO2 — peggio dell'idrogeno grigio da metano. Solo la quota certificata RFNBO
# rientra nella soglia europea.
FATTORE_RETE_KG_CO2_KWH = 0.26        # mix elettrico nazionale
SOGLIA_RFNBO_KG_CO2_KG_H2 = 3.38      # limite RED III per l'idrogeno rinnovabile


def emissioni_h2(quota_rfnbo_perc=None) -> float:
    """kg di CO2 per kg di idrogeno prodotto, secondo la quota certificata.

    Se la quota non è nota si assume il caso peggiore, cioè produzione da rete
    non certificata: è la sola ipotesi prudente quando manca il dato.
    """
    quota = (quota_rfnbo_perc or 0.0) / 100.0
    quota = min(max(quota, 0.0), 1.0)
    da_rete = FATTORE_RETE_KG_CO2_KWH * CONSUMO_ELETTROLISI_KWH_KG
    return quota * SOGLIA_RFNBO_KG_CO2_KG_H2 + (1 - quota) * da_rete


def co2_evitata_kg_per_kg_h2(riga=None) -> float:
    """Emissioni realmente evitate sostituendo gasolio con idrogeno.

    È la differenza fra ciò che si smette di emettere e ciò che si emette per
    produrre l'idrogeno: può essere negativa, e in quel caso la sostituzione
    peggiora il bilancio invece di migliorarlo.
    """
    quota = numero(riga.get("T26_QUOTA_RFNBO_PERC")) if riga is not None else None
    return CO2_DIESEL_SOSTITUITO_KG_KG_H2 - emissioni_h2(quota)

# Reality check: quanta energia e quanto suolo serve per produrre l'idrogeno
CONSUMO_ELETTROLISI_KWH_KG = 55.0   # consumo specifico di sistema,
                                    # elettrolisi piu' ausiliari e compressione
RESA_PV_KWH_KWP = 1200.0            # producibilità media in Friuli Venezia Giulia
                                    # valore unico condiviso con i tool 2.4 e 2.6
SUPERFICIE_PV_HA_MWP = 1.3          # fotovoltaico a terra
SUPERFICIE_CAMPO_CALCIO_MQ = 7140.0



# --- Parametri del confronto termico (Tool 2.4) -----------------------------
# Servono a mettere a confronto, sulla stessa unità di energia utile, la caldaia
# a idrogeno e la pompa di calore. Sono valori d'uso corrente, dichiarati nel
# documento perché il risultato dipende quasi solo da questi tre numeri.
PCI_H2_KWH_KG = 33.3             # potere calorifico inferiore dell'idrogeno
RENDIMENTO_CALDAIA_H2 = 0.90     # caldaia a condensazione alimentata a idrogeno
# Il coefficiente di prestazione di una pompa di calore ad aria dipende dal clima:
# in pianura la media stagionale si attesta attorno a 3,5, ma in zona climatica F
# con temperature di progetto sotto i -5 °C scende a 2,0-2,2. La differenza non
# cambia il confronto con l'idrogeno, ma cambia molto il picco di carico che la
# rete elettrica locale deve reggere nelle giornate più fredde.
COP_POMPA_CALORE = 3.5           # media stagionale in pianura
COP_POMPA_CALORE_MONTAGNA = 2.2  # zona climatica F, giornate di progetto

# --- Parametri per la stima dei fabbisogni di nicchia (Tool 2.3) -------------
# Conversioni usate per tradurre i driver fisici raccolti dal questionario in
# chilogrammi di idrogeno. Sono ordini di grandezza dichiarati, non valori di
# progetto: servono a capire se una nicchia pesa quanto un mezzo o quanto una
# flotta, non a dimensionare un impianto.
RESA_FUEL_CELL_KWH_KG = 17.0     # kWh elettrici da 1 kg di H2 (PEMFC, ~50%)
CONSUMO_TRENO_KG_KM = 0.25       # automotrice a idrogeno su tratta regionale
# Carrello elevatore a celle a combustibile: si misura in ore di servizio, non
# in potenza installata. Nella logistica del freddo i mezzi restano in moto anche
# a vuoto, per evitare il congelamento di impianti idraulici e ausiliari.
ORE_CARRELLO_GIORNO = 8.0        # turno tipico
CONSUMO_CARRELLO_KG_ORA = 0.20   # consumo medio di un carrello FC in esercizio
FATTORE_CARICO_FREDDO = 0.80     # quota del turno effettivamente in movimento

# Mezzi a ciclo di lavoro gravoso (battipista, soccorso): il confronto va fatto
# sui litri consumati, non sui chilometri, perché lavorano ad alta coppia e con
# lunghi stazionamenti a motore acceso.
LITRI_DIESEL_PER_KG_H2_GRAVOSO = 3.2

# Sinergia depuratore-elettrolizzatore. L'elettrolisi produce 8 kg di ossigeno
# per ogni kg di idrogeno: è il reagente che il depuratore oggi ottiene
# comprimendo aria, la sua voce di consumo elettrico maggiore.
RAPPORTO_O2_H2 = 8.0             # kg di ossigeno per kg di idrogeno
# Valore prudenziale: 1,2 kg di ossigeno trasferito per kWh assorbito dai
# compressori. È la resa che si ricava dal caso di riferimento (100.000 AE,
# 70 g O2 per abitante equivalente al giorno) e tiene conto del rendimento
# reale di trasferimento in vasca, sensibilmente inferiore a quello nominale
# dei diffusori a bolle fini.
RESA_AERAZIONE_KG_O2_KWH = 1.2
QUOTA_CALORE_ELETTROLISI = 0.35  # frazione dell'energia dissipata come calore

NICCHIE = {
    "T23_FLAG_RIFUGI":
        "rifugi e utenze isolate, dove l'idrogeno compete con il generatore diesel "
        "e con la logistica di rifornimento in quota",
    "T23_FLAG_MEZZI_CRITICI":
        "mezzi di emergenza e protezione civile, per i quali la continuità operativa "
        "conta più del costo del carburante",
    "T23_FLAG_COLD_STORAGE":
        "logistica del freddo e movimentazione in magazzino, dove i carrelli a celle a "
        "combustibile evitano la sostituzione delle batterie fra i turni",
    "T23_FLAG_TRENI":
        "trasporto ferroviario su tratte non elettrificate, alternativa all'elettrificazione "
        "quando i volumi di traffico non la giustificano",
    "T23_FLAG_PORTI_AEROPORTI":
        "movimentazione portuale o aeroportuale, con mezzi a ciclo continuo e rifornimento "
        "concentrato in pochi punti",
    "T23_FLAG_DEPURATORI":
        "impianti di depurazione, dove il consumo per aerazione è costante e prevedibile "
        "e può essere accoppiato a produzione locale",
}

# =============================================================================
# STRUTTURA DEL PASSO 2
# =============================================================================

PERCORSI = [
    {
        "codice": "A",
        "titolo": "Percorso A - Domanda di idrogeno",
        "blocchi": [
        ],
    },
    {
        "codice": "B",
        "titolo": "Percorso B - Offerta e produzione",
        "blocchi": [
            ("Altri parametri di produzione", [
                "T26_ZONA", "T26_TARGET_H2_TON", "T26_CO2_EVITATA_TON_ANNO",
                "T26B_SUP_TETTI_M2", "T26B_SUP_CAPANNONI_M2"]),
        ],
    },
    {
        "codice": "C",
        "titolo": "Percorso C - Transito e rifornimento",
        "blocchi": [
            ("Vocazione al transito (Tool 2.7)", [
                "T27_TGM_CAMION", "T27_DISTANZA_SNAM_KM", "T27_SCORE_C1", "T27_SCORE_C2",
                "T27_SCORE_C3", "T27_SCORE_GOV", "T27_FLAG_AREE_700BAR",
                "T27_FLAG_AFIR_GAP", "T27_FLAG_HUB_MERCI", "T27_FLAG_SINERGIA_HTA",
                "T27_FLAG_ACCORDI_FILIERA", "T27_FLAG_PUMS"]),
            ("Stazione di rifornimento (Tool 2.8)", [
                "T28_TAGLIA_HRS", "T28_CONFIGURAZIONE", "T28_CAPACITA_KG_GIORNO",
                "T28_N_DISPENSER", "T28_STRATEGIA_SUPPLY", "T28_POTENZA_COMPRESSORE_KW",
                "T28_AREA_MINIMA_MQ", "T28_CAPEX_COMPLESSIVO_EURO",
                "T28_BREAK_EVEN_EURO_KG", "T28_ORIZZONTE", "T28_QUOTA_FCEV_PERC"]),
        ],
    },
]

# T21_*: già trattate per esteso nella sezione 2.1, non si ripetono in tabella
# I dati dei tool 2.1, 2.2 e 2.3 sono discussi per esteso nel testo del percorso A:
# ripeterli in tabella allungherebbe il documento senza aggiungere nulla.
ESCLUSE = {"T11_MAIL", COL_ID, COL_NOME, COL_MATURITA,
           "T12_SCORE_A", "T12_SCORE_B", "T12_SCORE_C",
           "T21_N_AZIENDE_IDONEE", "T21_NOMI_AZIENDE", "T21_FABBISOGNO_H2_TON_ANNO",
           "T21_ATECO_AZIENDE", "T21_FABBISOGNI_AZIENDE", "T21_FAMIGLIE_AZIENDE",
           "T22_N_VEICOLI_ANALIZZATI", "T22_ESITO_PREVALENTE", "T22_BEV_FATTIBILE",
           "T22_FABBISOGNO_H2_TON_ANNO", "T22_FABBISOGNO_ELETTRICO_MWH_ANNO",
           "T22_ENERGIA_ELETTROLISI_MWH_ANNO", "T22_DELTA_TCO_EURO",
           "T22_EMISSIONI_EVITATE_TCO2",
           "T23_FLAG_RIFUGI", "T23_FLAG_MEZZI_CRITICI", "T23_FLAG_COLD_STORAGE",
           "T23_FLAG_TRENI", "T23_FLAG_PORTI_AEROPORTI", "T23_FLAG_DEPURATORI",
           "T23_RIFUGI_ELETTRICO_KWH", "T23_GASOLIO_FLOTTA_LITRI_ANNO",
           "T23_N_CARRELLI", "T23_POTENZA_CARRELLI_KW",
           "T23_TRATTA_NON_ELETTRIFICATA_KM", "T23_CORSE_GIORNALIERE",
           "T23_AERAZIONE_KWH_ANNO", "T23_N_MEZZI_SPECIALI", "T23_MEZZI_FUEL_CELL",
           "T24_FABBISOGNO_TERMICO_KWH_ANNO", "T24_SOLUZIONE_OTTIMALE",
           "T24_SOLUZIONE_PIU_PULITA", "T24_EMISSIONI_EVITATE_KGCO2_ANNO",
           "T25_FER_INSTALLATA_MW", "T25_SAU_OCCUPATA_PERC", "T25_PIPELINE_ISTANZE",
           "T25_PROGETTI_AUTORIZZATI", "T25_FLAG_CONTESTAZIONI",
           "T25_SUP_BROWNFIELD_MQ", "T25_SUP_TETTI_IND_MQ", "T25_SUP_TETTI_CIV_MQ",
           "T25_SUP_INCOLTE_MQ", "T25_SUP_SAU_MQ", "T25_SUP_SERVITU_MQ",
           "T25_DISTANZA_CABINA_PRIMARIA_KM", "T25_CAPACITA_RESIDUA_MW",
           "T25_ENTRO_5KM_DORSALE", "T25_SUP_PUBBLICA_MQ", "T25_PROGRAMMABILI_MW",
           "T26_MODALITA", "T26_PV_TERRA_MW", "T26_PV_TETTI_MW", "T26_PV_CAPANNONI_MW",
           "T26_EOLICO_MW", "T26_TAGLIA_FER_INSTALLATA_MW",
           "T26_TAGLIA_ELETTROLIZZATORE_MW", "T26_CAPACITA_BESS_MWH",
           "T26_PRODUZIONE_H2_TON_ANNO", "T26_QUOTA_RFNBO_PERC", "T26_CURTAILMENT_PERC",
           "T26_COPERTURA_PERC", "T26_CAPEX_CONNESSIONI_EURO", "T26_CAPEX_TOTALE_MLN",
           "T26_LCOH_EURO_KG", "T26_PAYBACK_ANNI", "T26B_SUP_TERRA_HA"}

FLAG_GOVERNANCE = ["T12_FLAG_PIANIFICAZIONE", "T12_FLAG_NAHV",
                   "T12_FLAG_JOINT_PROCUREMENT", "T23_FLAG_HYDROGEN_VALLEY"]

# =============================================================================
# FORMATTAZIONE AUTOMATICA
# =============================================================================

SUFFISSI = [
    ("_KGCO2_ANNO", ("num", "kgCO2/anno")),
    ("_TON_ANNO", ("num", "t/anno")),
    ("_LITRI_ANNO", ("num", "litri/anno")),
    ("_MWH_ANNO", ("num", "MWh/anno")),
    ("_KWH_ANNO", ("num", "kWh/anno")),
    ("_EURO_KG", ("num", "Euro/kg")),
    ("_KG_GIORNO", ("num", "kg/giorno")),
    ("_CABINA_PRIMARIA_KM", ("num", "km")),
    ("_TCO2", ("num", "tCO2")),
    ("_EURO", ("eur", "")),
    ("_MLN", ("num", "mln Euro")),
    ("_PERC", ("pct", "")),
    ("_ANNI", ("num", "anni")),
    ("_MWH", ("num", "MWh")),
    ("_MW", ("num", "MW")),
    ("_KWH", ("num", "kWh")),
    ("_KW", ("num", "kW")),
    ("_KM", ("num", "km")),
    ("_MQ", ("num", "m\u00b2")),
    ("_M2", ("num", "m\u00b2")),
    ("_HA", ("num", "ha")),
    ("_TON", ("num", "t")),
]

ETICHETTE = {
    "T21_N_AZIENDE_IDONEE": "Aziende idonee individuate",
    "T21_NOMI_AZIENDE": "Aziende individuate",
    "T21_FABBISOGNO_H2_TON_ANNO": "Fabbisogno H2 del comparto produttivo",
    "T22_N_VEICOLI_ANALIZZATI": "Veicoli analizzati",
    "T22_ESITO_PREVALENTE": "Esito prevalente dell'analisi",
    "T22_BEV_FATTIBILE": "Alternativa elettrica a batteria praticabile",
    "T22_FABBISOGNO_H2_TON_ANNO": "Fabbisogno H2 della flotta",
    "T22_FABBISOGNO_ELETTRICO_MWH_ANNO": "Fabbisogno elettrico equivalente",
    "T22_ENERGIA_ELETTROLISI_MWH_ANNO": "Energia richiesta dall'elettrolisi",
    "T22_DELTA_TCO_EURO": "Differenziale di costo totale di possesso",
    "T22_EMISSIONI_EVITATE_TCO2": "Emissioni evitate",
    "T23_FLAG_RIFUGI": "Rifugi o utenze isolate",
    "T23_FLAG_MEZZI_CRITICI": "Mezzi critici o di emergenza",
    "T23_FLAG_COLD_STORAGE": "Celle frigorifere e logistica del freddo",
    "T23_FLAG_TRENI": "Trasporto ferroviario",
    "T23_FLAG_PORTI_AEROPORTI": "Porti o aeroporti",
    "T23_FLAG_DEPURATORI": "Impianti di depurazione",
    "T23_RIFUGI_ELETTRICO_KWH": "Consumo elettrico dei rifugi",
    "T23_GASOLIO_FLOTTA_LITRI_ANNO": "Gasolio consumato dalla flotta",
    "T23_N_CARRELLI": "Carrelli elevatori",
    "T23_TRATTA_NON_ELETTRIFICATA_KM": "Tratta ferroviaria non elettrificata",
    "T23_CORSE_GIORNALIERE": "Corse giornaliere",
    "T23_AERAZIONE_KWH_ANNO": "Consumo per aerazione depuratori",
    "T24_FABBISOGNO_TERMICO_KWH_ANNO": "Fabbisogno termico degli edifici",
    "T24_SOLUZIONE_OTTIMALE": "Soluzione ottimale individuata",
    "T24_SOLUZIONE_PIU_PULITA": "Soluzione a minori emissioni",
    "T25_FER_INSTALLATA_MW": "Rinnovabili già installate",
    "T25_SAU_OCCUPATA_PERC": "Superficie agricola già occupata da impianti",
    "T25_PIPELINE_ISTANZE": "Istanze in corso di istruttoria",
    "T25_PROGETTI_AUTORIZZATI": "Progetti già autorizzati",
    "T25_FLAG_CONTESTAZIONI": "Contenziosi o opposizioni in corso",
    "T25_AREE_IDONEE_MQ": "Aree idonee complessive",
    "T25_SUP_BROWNFIELD_MQ": "Aree dismesse",
    "T25_SUP_TETTI_IND_MQ": "Coperture industriali",
    "T25_SUP_TETTI_CIV_MQ": "Coperture civili",
    "T25_SUP_INCOLTE_MQ": "Superfici incolte",
    "T25_SUP_SAU_MQ": "Superficie agricola utilizzata",
    "T25_SUP_SERVITU_MQ": "Aree gravate da servitù",
    "T25_DISTANZA_CABINA_PRIMARIA_KM": "Distanza dalla cabina primaria",
    "T25_CAPACITA_RESIDUA_MW": "Capacità residua di rete",
    "T25_ENTRO_5KM_DORSALE": "Entro 5 km dalla dorsale",
    "T26_MODALITA": "Modalità di simulazione",
    "T26_ZONA": "Zona di riferimento",
    "T26_TARGET_H2_TON": "Obiettivo di produzione",
    "T26_PV_TERRA_MW": "Fotovoltaico a terra",
    "T26_PV_TETTI_MW": "Fotovoltaico su coperture",
    "T26_PV_CAPANNONI_MW": "Fotovoltaico su capannoni",
    "T26_EOLICO_MW": "Eolico",
    "T26_TAGLIA_FER_INSTALLATA_MW": "Potenza rinnovabile complessiva",
    "T26_TAGLIA_ELETTROLIZZATORE_MW": "Taglia dell'elettrolizzatore",
    "T26_CAPACITA_BESS_MWH": "Accumulo elettrochimico",
    "T26_PRODUZIONE_H2_TON_ANNO": "Produzione di idrogeno",
    "T26_QUOTA_RFNBO_PERC": "Quota conforme RFNBO",
    "T26_CURTAILMENT_PERC": "Energia non utilizzabile",
    "T26_COPERTURA_PERC": "Copertura del fabbisogno",
    "T26_CAPEX_CONNESSIONI_EURO": "Costo delle connessioni",
    "T26_CAPEX_TOTALE_MLN": "Investimento complessivo",
    "T26_LCOH_EURO_KG": "Costo livellato dell'idrogeno (LCOH)",
    "T26_PAYBACK_ANNI": "Tempo di ritorno",
    "T26_CO2_EVITATA_TON_ANNO": "CO2 evitata",
    "T26B_SUP_TERRA_HA": "Suolo agricolo impegnato",
    "T26B_SUP_TETTI_M2": "Coperture impegnate",
    "T26B_SUP_CAPANNONI_M2": "Capannoni impegnati",
    "T27_TGM_CAMION": "Traffico giornaliero medio di mezzi pesanti",
    "T27_DISTANZA_SNAM_KM": "Distanza dalla rete di trasporto gas",
    "T27_SCORE_C1": "Punteggio flussi di traffico",
    "T27_SCORE_C2": "Punteggio infrastrutture",
    "T27_SCORE_C3": "Punteggio contesto",
    "T27_SCORE_GOV": "Punteggio di governance",
    "T27_FLAG_AREE_700BAR": "Aree compatibili con rifornimento a 700 bar",
    "T28_TAGLIA_HRS": "Taglia della stazione",
    "T28_CONFIGURAZIONE": "Configurazione impiantistica",
    "T28_CAPACITA_KG_GIORNO": "Capacità di erogazione",
    "T28_N_DISPENSER": "Erogatori previsti",
    "T28_STRATEGIA_SUPPLY": "Strategia di approvvigionamento",
    "T28_POTENZA_COMPRESSORE_KW": "Potenza di compressione",
    "T28_AREA_MINIMA_MQ": "Area minima richiesta",
    "T28_CAPEX_COMPLESSIVO_EURO": "Investimento complessivo",
    "T28_BREAK_EVEN_EURO_KG": "Prezzo di pareggio alla pompa",
    "T28_ORIZZONTE": "Orizzonte temporale",
    "T28_QUOTA_FCEV_PERC": "Quota di veicoli a celle a combustibile",
    "T23_N_MEZZI_SPECIALI": "Mezzi speciali censiti",
    "T23_MEZZI_FUEL_CELL": "Mezzi convertibili a celle a combustibile",
    "T23_FLAG_HYDROGEN_VALLEY": "Hydrogen Valley già finanziata nell'area",
    "T25_SUP_PUBBLICA_MQ": "Superfici di proprietà pubblica",
    "T25_PV_TERRA_INSTALLATO_MW": "Fotovoltaico a terra già installato",
    "T25_PROGRAMMABILI_MW": "Fonti programmabili in esercizio",
    "T25_FLAG_EOLICO_IDONEO": "Aree con ventosità adeguata",
    "T25_FLAG_DISPACCIAMENTO": "Interesse ai mercati di dispacciamento",
    "T27_FLAG_AFIR_GAP": "Colma un vuoto della rete AFIR",
    "T27_FLAG_HUB_MERCI": "Hub merci o interporti entro 5 km",
    "T27_FLAG_SINERGIA_HTA": "Sinergia con distretti Hard-to-Abate",
    "T27_FLAG_ACCORDI_FILIERA": "Accordi di filiera già attivi",
    "T27_FLAG_PUMS": "Idrogeno nella pianificazione della mobilità",
    "T12_FLAG_PIANIFICAZIONE": "Idrogeno negli strumenti di pianificazione",
    "T12_FLAG_NAHV": "Adesione alla North Adriatic Hydrogen Valley",
    "T12_FLAG_JOINT_PROCUREMENT": "Disponibilità ad appalti congiunti",
}


# =============================================================================
# PARAMETRI DEL PERCORSO B
# Soglie di giudizio sulla produzione. Sono valori di riferimento dichiarati:
# cambiarli qui cambia i commenti in tutti i documenti.
# =============================================================================

# Costo livellato dell'idrogeno. Il riferimento non è il costo dell'idrogeno
# grigio da metano (2-3 Euro/kg) ma il prezzo che un utilizzatore accetta di
# pagare per un prodotto conforme RFNBO, oggi fra 6 e 9 Euro/kg in Europa.
LCOH_COMPETITIVO = 6.0        # sotto questa soglia il progetto regge senza aiuti
LCOH_CRITICO = 9.0            # sopra, serve un contributo strutturale

PAYBACK_ACCETTABILE_ANNI = 12.0   # orizzonte compatibile con la finanza pubblica
CURTAILMENT_ACCETTABILE_PERC = 10.0   # energia rinnovabile non utilizzabile
QUOTA_RFNBO_MINIMA_PERC = 90.0        # sotto, l'accesso agli incentivi è a rischio

# Quota delle aree idonee oltre la quale il consumo di suolo diventa un tema
# politico prima che tecnico.
QUOTA_SUOLO_ATTENZIONE_PERC = 30.0

# =============================================================================
# UTILITY
# =============================================================================

def is_vuoto(v) -> bool:
    if v is None:
        return True
    try:
        if pd.isna(v):
            return True
    except (TypeError, ValueError):
        pass
    return str(v).strip().lower() in ("", "nan", "none", "n/a", "-", "na", "null")


def numero(v):
    if is_vuoto(v):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(" ", "").replace("\u00a0", "")
    s = re.sub(r"[^\d,.\-]", "", s)
    if not s:
        return None
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def formatta_numero(n: float) -> str:
    if abs(n - round(n)) < 1e-9 and abs(n) < 1e15:
        return f"{int(round(n)):,}".replace(",", ".")
    return f"{n:,.2f}".replace(",", "@").replace(".", ",").replace("@", ".")


def tipo_e_unita(colonna: str):
    up = colonna.upper()
    if "FLAG" in up or up.endswith("_FATTIBILE") or up.startswith("T25_ENTRO"):
        return "si_no", ""
    for suf, (tipo, unita) in SUFFISSI:
        if up.endswith(suf):
            return tipo, unita
    if up.startswith(("T27_SCORE", "T12_SCORE")) or "_N_" in up:
        return "num", ""
    return "testo", ""


def etichetta(colonna: str) -> str:
    if colonna in ETICHETTE:
        return ETICHETTE[colonna]
    testo = re.sub(r"^T\d+[A-Z]?_", "", colonna)
    for suf, _ in SUFFISSI:
        if testo.upper().endswith(suf):
            testo = testo[: -len(suf)]
            break
    testo = testo.replace("_", " ").strip().lower()
    return testo[:1].upper() + testo[1:]


def formatta(valore, colonna: str):
    tipo, unita = tipo_e_unita(colonna)
    if is_vuoto(valore):
        return None
    if tipo == "si_no":
        s = str(valore).strip().lower()
        if s in ("si", "sì", "yes", "y", "true", "vero", "1", "1.0", "x"):
            return "Sì"
        if s in ("no", "n", "false", "falso", "0", "0.0"):
            return "No"
        return str(valore).strip()
    if tipo in ("num", "eur", "pct"):
        n = numero(valore)
        if n is None:
            return str(valore).strip()
        testo = formatta_numero(n)
        if tipo == "eur":
            return f"Euro {testo}"
        if tipo == "pct":
            return f"{testo}%"
        return f"{testo} {unita}".strip()
    return str(valore).strip()


def contestazioni(riga) -> str:
    """Il questionario 2.5 non chiede 'ci sono contestazioni?' ma QUALI tecnologie
    le hanno generate: il campo contiene 'Eolico', 'Reti Elettriche', 'BESS /
    Accumuli', 'Idroelettrico'... Trattarlo come un sì/no lo rende sempre falso.
    Restituisce il testo se indica una contestazione reale, stringa vuota altrimenti.
    """
    valore = riga.get("T25_FLAG_CONTESTAZIONI")
    if is_vuoto(valore):
        return ""
    testo = str(valore).strip()
    if testo.lower() in ("no", "n", "nessuna", "none", "false", "0", "ne"):
        return ""
    return testo


def vero(valore) -> bool:
    return str(valore).strip().lower() in ("si", "sì", "yes", "true", "vero", "1", "1.0", "x")


def livello_maturita(score: int) -> str:
    for lo, hi, lab in SOGLIE_MATURITA:
        if lo <= score <= hi:
            return lab
    return "L1"


def calcola_profilo(riga):
    punteggi = {}
    for lettera, col in COL_SCORE.items():
        if col in riga.index:
            n = numero(riga[col])
            if n is not None:
                punteggi[lettera] = n
    if not punteggi:
        return "", {}
    massimo = max(punteggi.values())
    if massimo <= PUNTEGGIO_MINIMO:
        return "", punteggi
    lettere = [l for l in ("A", "B", "C")
               if punteggi.get(l, 0) >= massimo * QUOTA_SECONDARIA
               and punteggi.get(l, 0) > PUNTEGGIO_MINIMO]
    return "".join(lettere), punteggi


def slug(testo: str) -> str:
    s = unicodedata.normalize("NFKD", str(testo)).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")


def leggi_md(filename: str) -> str:
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            return ripulisci_md(f.read())
    return f"> *[Contenuto non disponibile: manca il file `{filename}`]*"


def ripulisci_md(testo: str) -> str:
    """Toglie dai .md i residui di esportazione: marcatori di citazione e LaTeX."""
    testo = re.sub(r"\[cite_start\]", "", testo)
    testo = re.sub(r"\[cite:[^\]]*\]", "", testo)
    testo = re.sub(r"\$+\\?text\{([^}]*)\}\$*", r"\1", testo)
    testo = re.sub(r"\$([^$]*)\$", r"\1", testo)
    testo = re.sub(r"[ \t]+([.,;:])", r"\1", testo)
    return testo.strip()


def applica_valori(testo: str, valori: dict) -> str:
    """Sostituisce i segnaposto {nome} con i valori calcolati.

    I segnaposto non previsti restano nel testo, così un refuso in un .md si vede
    subito nel documento invece di far fallire la generazione.
    """
    def sostituisci(match):
        chiave = match.group(1).strip()
        if chiave in valori:
            return str(valori[chiave])
        return match.group(0)
    return re.sub(r"\{([A-Za-z0-9_]+)\}", sostituisci, testo)


def testo_da_template(filename: str, valori: dict, predefinito: str = "") -> str:
    """Carica un .md e ne compila i segnaposto; se manca usa il testo predefinito."""
    if os.path.exists(filename):
        return applica_valori(leggi_md(filename), valori)
    return applica_valori(predefinito, valori)


def totale(riga, colonne):
    valori = [numero(riga[c]) for c in colonne if c in riga.index]
    valori = [v for v in valori if v is not None]
    return sum(valori) if valori else None

# =============================================================================
# TESTI
# =============================================================================

def testo_profilo(profilo: str, punteggi: dict) -> str:
    out = ["## Profilo strategico identificato"]
    if punteggi:
        out += ["| Dimensione | Punteggio |", "| --- | --- |"]
        nomi = {"A": "A - Consumo", "B": "B - Produzione", "C": "C - Transito"}
        for l in ("A", "B", "C"):
            if l in punteggi:
                out.append(f"| {nomi[l]} | {formatta_numero(punteggi[l])} |")
        out.append("")
    if not profilo:
        out.append("> Punteggi non disponibili: il profilo non è stato determinato.")
        return "\n".join(out)
    out.append(f"Il Comune ricade nel **profilo {profilo}**, con le seguenti vocazioni:")
    out += [f"- **{l}** - {NOMI_PROFILO[l]}" for l in profilo]
    if len(profilo) > 1:
        out += ["", "La compresenza di più vocazioni indica un territorio in cui le azioni "
                "vanno coordinate fra loro: la scala e la sequenza degli interventi contano "
                "quanto la loro natura."]
    return "\n".join(out)


def testo_passo2(riga) -> str:
    intro = ""
    for nome in ("5-percorsi_intro_it.md", "Intro Percorsi.md"):
        if os.path.exists(nome):
            intro = leggi_md(nome)
            break
    out = [intro, ""] if intro else []
    out.append(testo_da_template("5-premessa_it.md", {}, TESTO_PREMESSA_PERCORSI))
    out.append("")
    out += ["# Sintesi dei risultati tecnici",
            "I valori derivano dai questionari e dagli strumenti di calcolo del Toolkit "
            "H2READY. I campi non compilati non compaiono nelle tabelle.", ""]
    conteggio = 0

    for percorso in PERCORSI:
        blocchi_pieni = []
        for titolo_blocco, colonne in percorso["blocchi"]:
            righe = []
            for col in colonne:
                if col not in riga.index or col in ESCLUSE:
                    continue
                valore = formatta(riga[col], col)
                if valore is None:
                    continue
                righe.append(f"| {etichetta(col)} | {valore} |")
            if righe:
                blocchi_pieni.append((titolo_blocco, righe))
        # un percorso puo' non avere blocchi tabellari e avere comunque molto da
        # dire: e' il caso del percorso A, i cui dati sono discussi per esteso
        commento = commento_percorso(riga, percorso["codice"])
        if not blocchi_pieni and not commento:
            continue

        # ogni percorso è un capitolo a sé: comincia su pagina nuova
        out.append("<<<PAGINA>>>")
        if commento:
            out += [commento, ""]
        for titolo_blocco, righe in blocchi_pieni:
            conteggio += len(righe)
            out.append(f"### {titolo_blocco}")
            out += ["| Parametro | Valore |", "| --- | --- |"] + righe + [""]

    previste = {c for p in PERCORSI for _, cols in p["blocchi"] for c in cols}
    altre = [c for c in riga.index
             if c not in ESCLUSE and c not in FLAG_GOVERNANCE and c not in previste
             and not is_vuoto(riga[c])]
    if altre:
        out.append("## Altri dati disponibili")
        out += ["| Parametro | Valore |", "| --- | --- |"]
        out += [f"| {etichetta(c)} | {formatta(riga[c], c)} |" for c in altre]
        out.append("")

    if conteggio == 0:
        out.append("> Nessun dato tecnico disponibile: verificare la compilazione dei "
                   "questionari per questo Comune.")
    return "\n".join(out)


def costruisci_aziende(riga) -> list:
    """Ricava l'elenco delle aziende dal foglio, in qualunque forma sia scritto.

    Formati riconosciuti in T21_NOMI_AZIENDE (separatore ';' oppure a capo):
        Ferriere Isontine S.p.A.
        Ferriere Isontine S.p.A. (24.10)
        Ferriere Isontine S.p.A. | 24.10 | 3200
    In alternativa, se il foglio contiene le colonne parallele
    T21_ATECO_AZIENDE e T21_FABBISOGNI_AZIENDE (liste separate da ';'),
    queste hanno la precedenza.

    Restituisce una lista di dizionari con nome, ateco, fabbisogno (t/anno o None).
    """
    grezzo = riga.get("T21_NOMI_AZIENDE")
    if is_vuoto(grezzo):
        return []

    voci = [v.strip() for v in re.split(r"[;\n]+", str(grezzo)) if v.strip()]
    ateco_paralleli = []
    fabb_paralleli = []
    if not is_vuoto(riga.get("T21_ATECO_AZIENDE")):
        ateco_paralleli = [v.strip() for v in
                           re.split(r"[;\n]+", str(riga["T21_ATECO_AZIENDE"]))]
    if not is_vuoto(riga.get("T21_FABBISOGNI_AZIENDE")):
        fabb_paralleli = [v.strip() for v in
                          re.split(r"[;\n]+", str(riga["T21_FABBISOGNI_AZIENDE"]))]
    fam_parallele = []
    if not is_vuoto(riga.get("T21_FAMIGLIE_AZIENDE")):
        fam_parallele = [v.strip() for v in
                         re.split(r"[;\n]+", str(riga["T21_FAMIGLIE_AZIENDE"]))]

    aziende = []
    for i, voce in enumerate(voci):
        nome, codice, fabbisogno = voce, "", None

        if "|" in voce:
            pezzi = [p.strip() for p in voce.split("|")]
            nome = pezzi[0]
            if len(pezzi) > 1:
                codice = pezzi[1]
            if len(pezzi) > 2:
                fabbisogno = numero(pezzi[2])
        else:
            trovato = re.search(r"[\(\[]\s*([0-9]{2}[.,]?[0-9.,]*)\s*[\)\]]", voce)
            if trovato:
                codice = trovato.group(1)
                nome = voce[: trovato.start()].strip()

        if i < len(ateco_paralleli) and ateco_paralleli[i]:
            codice = ateco_paralleli[i]
        if i < len(fabb_paralleli):
            valore = numero(fabb_paralleli[i])
            if valore is not None:
                fabbisogno = valore

        famiglia = fam_parallele[i] if i < len(fam_parallele) else ""
        aziende.append({"nome": nome.strip(" -"), "ateco": codice,
                        "fabbisogno": fabbisogno, "famiglia": famiglia})
    return aziende


def ripartisci_fabbisogno(aziende: list, totale_ton):
    """Se manca il fabbisogno per singola azienda lo stima pro quota.

    La ripartizione è pesata sull'intensità di idrogeno tipica del settore ATECO.
    Restituisce True se almeno un valore è stato stimato anziché rilevato.
    """
    if not aziende or not totale_ton:
        return False
    noti = sum(a["fabbisogno"] for a in aziende if a["fabbisogno"] is not None)
    mancanti = [a for a in aziende if a["fabbisogno"] is None]
    if not mancanti:
        return False

    residuo = max(totale_ton - noti, 0.0)
    pesi = [AT.peso(a["ateco"]) for a in mancanti]
    somma = sum(pesi) or len(mancanti)
    for azienda, p in zip(mancanti, pesi):
        azienda["fabbisogno"] = residuo * p / somma
        azienda["stimato"] = True
    return True


TESTO_HTA_PREDEFINITO = """### Domanda industriale Hard-to-Abate (Tool 2.1)

La transizione impone una gerarchia di intervento fondata sulla termodinamica: dove
l'elettrificazione diretta è possibile, tramite pompe di calore, resistenze o
induzione, essa resta sempre la strada più efficiente. Esistono però comparti
definiti **Hard-to-Abate** nei quali l'elettrificazione incontra limiti fisici o
chimici insuperabili: settori in cui la molecola di idrogeno partecipa direttamente
alla reazione, come la sintesi dell'ammoniaca o la riduzione diretta del minerale di
ferro, e processi che richiedono calore oltre gli 800 °C, come i forni fusori del
vetro o la calcinazione del clinker.

A questi limiti tecnici si somma un vincolo normativo. La direttiva **RED III**
impone che entro il 2030 almeno il 42% dell'idrogeno impiegato nell'industria
provenga da fonti rinnovabili di origine non biologica, quota che sale al 60% entro
il 2035, e il meccanismo CBAM ne rafforza l'urgenza sul piano della competitività.
"""

TESTO_OFFTAKE_PREDEFINITO = """#### Perché la domanda industriale conta più di ogni altra

La ragione per cui questa rilevazione apre il percorso non è il volume in sé, ma la
sua natura. Un impianto di produzione di idrogeno ha costi quasi interamente fissi:
una volta costruito, produrre poco o produrre molto cambia poco la spesa, mentre
cambia moltissimo il costo di ogni singolo chilogrammo. Ne consegue che la variabile
decisiva non è la capacità installata ma **la continuità della domanda**.

Un'utenza industriale offre esattamente ciò che manca a tutte le altre: un consumo
prevedibile, distribuito su tutto l'anno, indipendente dalla stagione e dalle
vacanze scolastiche. È per questo che i modelli di business dell'idrogeno ruotano
attorno al contratto di acquisto pluriennale, il cosiddetto *off-take*: senza un
volume impegnato per almeno dieci anni nessun istituto finanzia un elettrolizzatore,
e la Strategia Nazionale individua proprio nella creazione di una domanda vincolata
la prima delle azioni necessarie a far partire la filiera.

Per l'amministrazione questo si traduce in un compito preciso e diverso da quello
che ci si aspetterebbe: non costruire un impianto, ma **mettere attorno a un tavolo
gli utilizzatori prima che l'impianto esista**, e far sì che l'impegno reciproco
preceda l'investimento.

#### Il costo che non compete al Comune

Va detto con chiarezza, perché è la causa più frequente di aspettative mal riposte.
Convertire un processo industriale all'idrogeno non significa cambiare fornitore di
combustibile: significa sostituire bruciatori, tubazioni, valvole, sistemi di
regolazione e talvolta l'intero forno, con investimenti che nei comparti energivori
si misurano in milioni di euro e con fermi impianto che valgono quanto i lavori.

**Questo costo è dell'impresa, non del Comune**, e nessuna amministrazione può né
deve accollarselo. Ma va conosciuto, per tre ragioni. La prima è che determina i
tempi reali: un'azienda cambia il forno quando il forno arriva a fine vita, non
quando arriva l'idrogeno, e le finestre di sostituzione si aprono ogni dieci o
quindici anni. La seconda è che spiega perché un'impresa possa dichiararsi
interessata e poi non firmare: l'interesse è sul vettore, l'ostacolo è sulla
macchina. La terza è che indica dove il sostegno pubblico serve davvero — non tanto
sul capitale dell'elettrolizzatore quanto sulla conversione degli impianti
utilizzatori e sul differenziale di costo del combustibile, che sono le due voci su
cui la Strategia Nazionale chiede misure dedicate.

Il compito del Comune resta quindi quello di conoscere il ciclo di vita degli
impianti delle aziende del proprio territorio, e di far coincidere la disponibilità
di idrogeno con le finestre in cui quegli impianti vanno comunque rinnovati.
"""

TESTO_REALITY_CHECK_PREDEFINITO = """#### Che cosa significa produrre questa quantità

Tradurre le tonnellate di idrogeno in energia elettrica e in suolo serve a fissare
l'ordine di grandezza dell'impegno richiesto al territorio, prima ancora di
discutere di tecnologie e di costi.

| Grandezza | Valore |
| --- | --- |
| Idrogeno richiesto dall'industria | {h2_ton} t/anno |
| Energia elettrica necessaria | {mwh} MWh/anno ({gwh} GWh/anno) |
| Potenza fotovoltaica equivalente | {mwp} MWp |
| Superficie a terra occupata | {ettari} ettari, pari a circa {campi} campi da calcio |

> Calcolo condotto con un consumo specifico di elettrolisi di {kwh_kg} kWh per kg di
> idrogeno, una producibilità fotovoltaica di {resa} kWh per kWp installato e
> un'occupazione di {ha_mwp} ettari per MWp a terra.

{giudizio_suolo}
"""


def sezione_hta(riga) -> str:
    """Sezione 2.1: mappatura delle utenze industriali Hard-to-Abate."""
    ind = numero(riga.get("T21_FABBISOGNO_H2_TON_ANNO"))
    aziende = costruisci_aziende(riga)

    testo = testo_da_template("A21-hta_intro_it.md", {}, TESTO_HTA_PREDEFINITO)
    out = [testo, ""]

    if not aziende and not ind:
        out.append("Lo screening del tessuto industriale locale non ha rilevato impianti "
                   "classificabili nei settori prioritari Hard-to-Abate. Sul territorio "
                   "comunale non sussiste quindi una domanda industriale diretta capace "
                   "di giustificare da sola un'infrastruttura dedicata: la strategia va "
                   "orientata all'elettrificazione delle utenze termiche a bassa e media "
                   "temperatura e all'efficienza energetica, riservando l'idrogeno agli "
                   "altri percorsi.")
        return "\n".join(out)

    stimato = ripartisci_fabbisogno(aziende, ind)

    if aziende:
        out.append(f"Lo screening ha individuato "
                   f"{'una sola azienda idonea' if len(aziende) == 1 else str(len(aziende)) + ' aziende idonee'} "
                   "sul territorio comunale. Per ciascuna, il codice ATECO determina il "
                   "processo produttivo e quindi se l'impiego di idrogeno sia "
                   "tecnicamente fondato o meno.")
        out.append("")
        out += ["| Azienda | ATECO | Processo | Valutazione | Fabbisogno |",
                "| --- | --- | --- | --- | --- |"]
        for a in aziende:
            codice = AT.normalizza(a["ateco"]) or "n.d."
            dal_tool = AT.da_famiglia(a.get("famiglia"))
            if dal_tool:
                giudizio, processo = dal_tool[0], dal_tool[1]
            else:
                processo = AT.descrizione(a["ateco"])
                giudizio = AT.verdetto(a["ateco"])
            if a["fabbisogno"] is None:
                quantita = "n.d."
            else:
                quantita = f"{formatta_numero(a['fabbisogno'])} t/anno"
                if a.get("stimato"):
                    quantita += " *"
            out.append(f"| {a['nome']} | {codice} | {processo} | {giudizio} | {quantita} |")
        out.append("")

        if stimato:
            out.append("> I valori contrassegnati con l'asterisco sono una ripartizione "
                       "indicativa del fabbisogno complessivo fra le aziende individuate, "
                       "pesata sull'intensità di idrogeno tipica di ciascun settore. Non "
                       "sostituiscono la rilevazione puntuale presso le singole imprese, "
                       "che resta il passo successivo.")
            out.append("")

        # legenda dei verdetti effettivamente comparsi
        presenti = []
        for a in aziende:
            dal_tool = AT.da_famiglia(a.get("famiglia"))
            v = dal_tool[0] if dal_tool else AT.verdetto(a["ateco"])
            if v in AT.VERDETTI and v not in presenti:
                presenti.append(v)
        if presenti:
            out.append("Criteri di valutazione applicati:")
            out += [f"- **{v}** - {AT.VERDETTI[v].replace('**', '')}" for v in presenti]
            out.append("")

    # --- perché la domanda industriale è quella che conta
    out.append(testo_da_template("A21-offtake_it.md", {}, TESTO_OFFTAKE_PREDEFINITO))
    out.append("")

    # --- reality check su energia e suolo
    if ind:
        mwh = ind * 1000 * CONSUMO_ELETTROLISI_KWH_KG / 1000
        mwp = mwh * 1000 / RESA_PV_KWH_KWP / 1000
        ettari = mwp * SUPERFICIE_PV_HA_MWP
        campi = ettari * 10000 / SUPERFICIE_CAMPO_CALCIO_MQ

        idonee = numero(riga.get("T25_AREE_IDONEE_MQ"))
        if idonee:
            quota = ettari * 10000 / idonee * 100
            if quota > 100:
                giudizio = (f"La superficie necessaria eccede le aree idonee censite sul "
                            f"territorio comunale: il fabbisogno industriale **non è "
                            f"copribile con la sola produzione locale a terra**. La "
                            "strategia dovrà combinare generazione su coperture e aree "
                            "dismesse con l'approvvigionamento da reti sovracomunali.")
            elif quota > 30:
                giudizio = (f"L'impianto occuperebbe circa il {formatta_numero(quota)}% "
                            "delle aree idonee censite: una quota rilevante, che impone "
                            "di valutare il consumo di suolo rispetto agli altri usi "
                            "possibili prima di procedere.")
            else:
                giudizio = (f"L'impianto occuperebbe circa il {formatta_numero(quota)}% "
                            "delle aree idonee censite: il territorio dispone del margine "
                            "necessario, e la scelta si sposta sulla qualità delle aree "
                            "più che sulla loro estensione.")
        else:
            giudizio = ("L'estensione richiesta mostra che difficilmente il fabbisogno "
                        "industriale sarà coperto dalla sola produzione locale a terra: "
                        "la pianificazione dovrà combinare generazione su coperture e "
                        "aree dismesse con l'approvvigionamento da reti sovracomunali, "
                        "in particolare il SoutH2 Corridor e le dorsali di trasporto.")

        valori = {
            "h2_ton": formatta_numero(ind),
            "mwh": formatta_numero(mwh),
            "gwh": formatta_numero(mwh / 1000),
            "mwp": formatta_numero(mwp),
            "ettari": formatta_numero(ettari),
            "campi": formatta_numero(round(campi)),
            "kwh_kg": formatta_numero(CONSUMO_ELETTROLISI_KWH_KG),
            "resa": formatta_numero(RESA_PV_KWH_KWP),
            "ha_mwp": formatta_numero(SUPERFICIE_PV_HA_MWP),
            "giudizio_suolo": giudizio,
        }
        out.append(testo_da_template("A21-realitycheck_it.md", valori,
                                     TESTO_REALITY_CHECK_PREDEFINITO))

    return "\n".join(out)



TESTO_FLOTTE_PREDEFINITO = """### Flotte e mobilità (Tool 2.2)

Nel trasporto la gerarchia di intervento è la stessa dell'industria, ma i confini
sono più netti. Per i mezzi leggeri e per le percorrenze urbane la batteria è oggi
più efficiente, più economica e più matura: l'idrogeno vi sarebbe uno spreco di
energia primaria, perché per ogni kilowattora impiegato alla ruota ne servono circa
tre alla produzione. Il vantaggio dell'idrogeno emerge dove la batteria incontra
limiti fisici — autonomie elevate senza soste lunghe, carichi utili che il peso
delle celle eroderebbe, mezzi in servizio continuo su più turni, temperature rigide
che riducono la capacità disponibile.

La valutazione che segue si fonda sul costo totale di possesso, che considera
insieme l'acquisto del mezzo, il carburante, la manutenzione e il valore residuo:
è il solo criterio che permette di confrontare tecnologie con costi iniziali e
costi di esercizio tanto diversi.
"""


def sezione_flotte(riga) -> str:
    """Sezione 2.2: analisi della flotta e del costo totale di possesso."""
    n_veicoli = numero(riga.get("T22_N_VEICOLI_ANALIZZATI"))
    fabbisogno = numero(riga.get("T22_FABBISOGNO_H2_TON_ANNO"))
    esito = riga.get("T22_ESITO_PREVALENTE")
    bev = riga.get("T22_BEV_FATTIBILE")
    delta_tco = numero(riga.get("T22_DELTA_TCO_EURO"))
    elettrico = numero(riga.get("T22_FABBISOGNO_ELETTRICO_MWH_ANNO"))
    elettrolisi = numero(riga.get("T22_ENERGIA_ELETTROLISI_MWH_ANNO"))
    co2 = numero(riga.get("T22_EMISSIONI_EVITATE_TCO2"))

    if not any(v is not None for v in (n_veicoli, fabbisogno, delta_tco)) and is_vuoto(esito):
        return ""

    out = [testo_da_template("A22-flotte_intro_it.md", {}, TESTO_FLOTTE_PREDEFINITO), ""]

    # --- quadro dell'analisi
    righe = []
    if n_veicoli:
        righe.append(f"| Veicoli analizzati | {formatta_numero(n_veicoli)} |")
    if not is_vuoto(esito):
        righe.append(f"| Esito prevalente | {str(esito).strip()} |")
    if fabbisogno:
        kg_giorno = fabbisogno * 1000 / GIORNI_OPERATIVI
        righe.append(f"| Fabbisogno di idrogeno | {formatta_numero(fabbisogno)} t/anno |")
        righe.append(f"| Erogazione media richiesta | {formatta_numero(kg_giorno)} kg/giorno |")
    if co2:
        righe.append(f"| Emissioni evitate | {formatta_numero(co2)} tCO2/anno |")
    if righe:
        out += ["| Parametro | Valore |", "| --- | --- |"] + righe + [""]

    # --- massa critica della sola mobilità
    if fabbisogno:
        kg_giorno = fabbisogno * 1000 / GIORNI_OPERATIVI
        out.append("#### Sostenibilità del rifornimento")
        bus_eq = kg_giorno / CONSUMO_BUS_KG_GIORNO
        if fabbisogno >= SOGLIA_MASSA_CRITICA_TON:
            out.append(f"Con {formatta_numero(kg_giorno)} kg al giorno — l'equivalente di "
                       f"circa {formatta_numero(bus_eq)} autobus urbani in servizio — la "
                       "flotta raggiunge la scala che rende sostenibile **un impianto di "
                       "rifornimento presso il proprio deposito**. È la configurazione più "
                       "favorevole: i mezzi rientrano ogni sera, il rifornimento avviene in "
                       "orario notturno e la domanda è interamente sotto il controllo "
                       "dell'amministrazione, il che elimina il rischio di mercato che "
                       "grava su qualunque stazione aperta al pubblico.")
        elif fabbisogno >= SOGLIA_MOBILITA_AUTONOMA_TON:
            out.append(f"Con {formatta_numero(kg_giorno)} kg al giorno la flotta supera la "
                       f"soglia tecnica di {formatta_numero(SOGLIA_MOBILITA_AUTONOMA_TON)} "
                       "t/anno, sotto la quale una stazione non ammortizza i costi fissi di "
                       "compressione e preraffreddamento. Resta però **al di sotto della "
                       f"scala di {formatta_numero(SOGLIA_MASSA_CRITICA_TON)} t/anno** — "
                       "l'equivalente di una decina di mezzi pesanti — che i modelli di "
                       "business individuano come punto di pareggio per un impianto "
                       "dedicato al solo deposito comunale. L'infrastruttura è quindi "
                       "tecnicamente possibile ma economicamente fragile se resta isolata: "
                       "conviene dimensionarla per servire anche utenze esterne, oppure "
                       "condividerla con Comuni limitrofi e operatori privati.")
        elif fabbisogno >= SOGLIA_MOBILITA_MINIMA_TON:
            out.append(f"Con {formatta_numero(kg_giorno)} kg al giorno la flotta si colloca "
                       "**sotto la soglia di una stazione dedicata**, pur restando sopra il "
                       "minimo operativo. È la situazione tipica di chi avvia una flotta "
                       "sperimentale di due o tre mezzi. Le strade praticabili sono due: "
                       "aggregare la domanda con quella di Comuni vicini o di operatori "
                       "privati fino a raggiungere la massa critica, oppure rifornirsi "
                       "presso stazioni pubbliche esistenti lungo le direttrici TEN-T, "
                       "verificando che la distanza sia compatibile con le percorrenze "
                       "quotidiane dei mezzi.")
        else:
            out.append(f"Con {formatta_numero(kg_giorno)} kg al giorno il fabbisogno "
                       "comunale resta **inferiore al consumo di un solo autobus di linea**, "
                       f"che si attesta attorno ai {formatta_numero(CONSUMO_BUS_KG_GIORNO)} kg "
                       "al giorno. Progettare un'infrastruttura fissa per rifornire meno di "
                       "un mezzo sarebbe un paradosso economico. La conversione resta "
                       "praticabile solo in forma dimostrativa, con approvvigionamento "
                       "tramite carro bombolaio o stazione mobile: soluzioni che riducono "
                       "l'investimento iniziale a una frazione di quello di un impianto "
                       "fisso, al prezzo di un costo per chilogrammo più alto.")
        out.append("")

    # --- alternativa elettrica
    if not is_vuoto(bev):
        out.append("#### Confronto con l'alternativa elettrica")
        if vero(bev):
            frase = ("Per una parte dei mezzi analizzati **l'alternativa a batteria risulta "
                     "praticabile**. È un risultato che va preso sul serio: dove la batteria "
                     "arriva, arriva meglio, perché l'efficienza dalla presa alla ruota è "
                     "circa tre volte superiore. L'idrogeno va quindi riservato ai segmenti "
                     "in cui la batteria non basta, e destinare risorse pubbliche a "
                     "convertire mezzi che potrebbero essere elettrici peggiora sia il "
                     "bilancio economico sia quello energetico.")
        else:
            frase = ("Sui mezzi analizzati **l'alternativa a batteria non risulta "
                     "praticabile**, per autonomia richiesta, carichi o continuità di "
                     "servizio. L'idrogeno resta l'unica opzione a zero emissioni allo "
                     "scarico per questo segmento, il che rafforza la solidità del caso "
                     "d'uso: non si sta scegliendo fra due strade, se ne sta percorrendo "
                     "l'unica disponibile.")
        out += [frase, ""]

    # --- confronto energetico
    if elettrico and elettrolisi:
        rapporto = elettrolisi / elettrico if elettrico else None
        out.append("#### Energia richiesta dalle due strade")
        out += ["| Voce | Valore |", "| --- | --- |",
                f"| Elettrificazione diretta della flotta | {formatta_numero(elettrico)} MWh/anno |",
                f"| Produzione dell'idrogeno equivalente | {formatta_numero(elettrolisi)} MWh/anno |"]
        if rapporto:
            out.append(f"| Rapporto fra le due | {formatta_numero(rapporto)} volte |")
        out.append("")
        if rapporto and rapporto > 1.2:
            extra_mwh = elettrolisi - elettrico
            mwp_extra = extra_mwh * 1000 / RESA_PV_KWH_KWP / 1000
            out.append(f"La via dell'idrogeno richiede **{formatta_numero(rapporto)} volte "
                       "l'energia** della via elettrica diretta. Il divario nasce da tre "
                       "perdite in sequenza, nessuna delle quali dipende dalla qualità "
                       "delle macchine: l'elettrolisi restituisce in idrogeno circa i due "
                       "terzi dell'elettricità che assorbe, la compressione a 350 o 700 bar "
                       "ne consuma un'altra frazione, e la cella a combustibile a bordo del "
                       "mezzo riconverte in movimento poco più della metà dell'energia "
                       "chimica che riceve. Ogni passaggio è vincolato dalla termodinamica, "
                       "non dallo stato dell'arte.")
            out.append("")
            out.append(f"Tradotto in termini concreti per il territorio: coprire questa "
                       f"flotta con idrogeno richiede {formatta_numero(extra_mwh)} MWh "
                       "all'anno **in più** rispetto alla stessa flotta elettrificata, "
                       f"l'equivalente della produzione di circa {formatta_numero(mwp_extra)} "
                       "MWp di fotovoltaico aggiuntivo, con il suolo e gli investimenti che "
                       "questo comporta. È una quantità che va confrontata con le superfici "
                       "rilevate nel percorso B, perché è lì che quel divario si traduce in "
                       "ettari.")
            out.append("")
            out.append("Nulla di tutto ciò rende l'idrogeno una scelta sbagliata: significa "
                       "che è una scelta **costosa in energia**, e che come tale va riservata "
                       "ai casi in cui l'alternativa non esiste. Destinarlo a mezzi che la "
                       "batteria servirebbe altrettanto bene sottrae energia rinnovabile ai "
                       "segmenti che non hanno altra strada, e nel bilancio complessivo del "
                       "territorio è un peggioramento, non un progresso.")
            out.append("")

    # --- costo totale di possesso
    if delta_tco is not None:
        out.append("#### Costo totale di possesso")
        if delta_tco > 0:
            per_mezzo = delta_tco / n_veicoli if n_veicoli else None
            frase = (f"La conversione costa **Euro {formatta_numero(delta_tco)} in più** "
                     "rispetto ai mezzi convenzionali sull'intero ciclo di vita")
            if per_mezzo:
                frase += f", pari a circa Euro {formatta_numero(per_mezzo)} per veicolo"
            frase += (". Il divario va colmato con contributi in conto capitale — i bandi "
                      "regionali e il PNRR coprono in genere il differenziale d'acquisto — "
                      "e va rivalutato periodicamente, perché si riduce con la discesa del "
                      "prezzo dell'idrogeno e con la scala di produzione dei veicoli.")
            out.append(frase)
        else:
            out.append(f"La conversione risulta **conveniente di Euro "
                       f"{formatta_numero(abs(delta_tco))}** sul ciclo di vita rispetto ai "
                       "mezzi convenzionali. È un risultato favorevole ma condizionato: "
                       "dipende dal prezzo dell'idrogeno alla pompa assunto nella "
                       "simulazione, che è la variabile più incerta dell'intero calcolo. "
                       "Prima di deliberare l'investimento conviene verificare che quel "
                       "prezzo sia coerente con l'offerta effettivamente disponibile sul "
                       "territorio.")
        out.append("")

    return "\n".join(out).strip()



TESTO_NICCHIE_PREDEFINITO = """### Usi di nicchia (Tool 2.3)

Accanto all'industria e alle flotte esistono impieghi in cui l'idrogeno compete su
requisiti diversi dal solo costo: la continuità del servizio, l'assenza di rete
elettrica adeguata, il tempo di rifornimento fra un turno e l'altro. Sono volumi
contenuti, ma hanno un valore che il conto economico non cattura: rendono la
tecnologia visibile alla comunità e costruiscono le competenze tecniche
dell'amministrazione a costi contenuti.

Per questo motivo gli usi di nicchia sono spesso i candidati naturali della prima
fase di un percorso comunale, anche quando il grosso della domanda sta altrove.
"""

# Per ogni nicchia: descrizione, colonna del driver fisico, e come si converte
# quel driver in un fabbisogno annuo di idrogeno.
DETTAGLIO_NICCHIE = {
    "T23_FLAG_RIFUGI": {
        "titolo": "Rifugi e utenze isolate",
        "testo": "Sono utenze fuori rete, alimentate da generatori diesel il cui "
                 "combustibile arriva in quota con elicottero o con mezzi cingolati, a un "
                 "costo di trasporto che spesso supera quello del carburante stesso. Una "
                 "cella a combustibile elimina il rumore — che in un rifugio d'alta quota "
                 "non è un dettaglio ma la ragione per cui il generatore viene spento la "
                 "notte — azzera le emissioni locali e toglie il rischio di sversamento in "
                 "aree di pregio ambientale, dove una perdita comporta bonifiche costose e "
                 "danni reputazionali.\n\n"
                 "Il vincolo si sposta però tutto sulla logistica: le bombole a 200 bar "
                 "hanno una densità energetica per volume molto inferiore al gasolio, "
                 "quindi a parità di autonomia servono più viaggi. Prima di considerare la "
                 "conversione un vantaggio va confrontato il numero di rotazioni annue "
                 "necessarie con quelle attuali, e valutata l'alternativa di un impianto "
                 "fotovoltaico con accumulo, che in molti rifugi copre già gran parte del "
                 "fabbisogno estivo, quando la frequentazione è massima.",
        "driver": "T23_RIFUGI_ELETTRICO_KWH",
        "unita": "kWh/anno",
        "kg": lambda v: v / RESA_FUEL_CELL_KWH_KG,
    },
    "T23_FLAG_MEZZI_CRITICI": {
        "titolo": "Mezzi critici e comprensori",
        "testo": "Battipista, mezzi di soccorso e di protezione civile hanno un "
                 "requisito che il costo non esprime: devono funzionare quando serve, e "
                 "quando serve è quasi sempre la condizione peggiore. Le batterie perdono "
                 "capacità proprio sotto zero, e un mezzo che deve garantire otto ore di "
                 "lavoro continuo a meno dieci gradi non può permettersi una riserva "
                 "incerta.\n\n"
                 "A questo si aggiunge il ciclo di lavoro. Un battipista non percorre "
                 "chilometri, eroga coppia in salita su neve per l'intero turno, con "
                 "consumi che si misurano in litri all'ora e non in litri per cento "
                 "chilometri. I mezzi di soccorso alternano lunghi stazionamenti a motore "
                 "acceso — per alimentare apparecchiature e riscaldamento — a picchi di "
                 "potenza improvvisi. In entrambi i casi il rifornimento in pochi minuti "
                 "vale più dell'efficienza, perché il mezzo deve tornare operativo, non "
                 "restare in ricarica.\n\n"
                 "Sono impieghi a volume contenuto ma ad altissima visibilità: un mezzo "
                 "comunale a idrogeno che opera durante un'emergenza fa per la percezione "
                 "pubblica della tecnologia più di qualunque campagna informativa.",
        "driver": "T23_GASOLIO_FLOTTA_LITRI_ANNO",
        "unita": "litri di gasolio/anno",
        "kg": lambda v: v / LITRI_DIESEL_PER_KG_H2_GRAVOSO,
    },
    "T23_FLAG_COLD_STORAGE": {
        "titolo": "Logistica del freddo e movimentazione",
        "testo": "Nei magazzini a ciclo continuo i carrelli elevatori elettrici "
                 "impongono la sostituzione delle batterie fra un turno e l'altro: servono "
                 "batterie di scorta, un locale dedicato alla ricarica con la ventilazione "
                 "prescritta, e il tempo che l'operatore impiega nel cambio. La cella a "
                 "combustibile si rifornisce in tre minuti alla stessa colonnina, senza "
                 "batterie di riserva e senza locale tecnico: lo spazio recuperato è "
                 "superficie di magazzino che torna a produrre reddito.\n\n"
                 "Nella logistica del freddo il vantaggio si amplifica. Le batterie al "
                 "piombo perdono fino a un terzo della capacità in cella frigorifera, "
                 "mentre la cella a combustibile mantiene tensione costante fino a "
                 "esaurimento e produce calore che giova alla cabina dell'operatore. È il "
                 "motivo per cui questa è l'applicazione con la storia commerciale più "
                 "lunga: decine di migliaia di carrelli a idrogeno operano da anni nei "
                 "centri di distribuzione, in configurazioni che non hanno più nulla di "
                 "sperimentale.\n\n"
                 "Il caso d'uso è però quasi sempre privato: il ruolo dell'amministrazione "
                 "è mettere in contatto l'operatore logistico con il progetto di "
                 "produzione, non realizzare l'impianto.",
        "driver": "T23_N_CARRELLI",
        "unita": "carrelli",
        "kg": lambda v: v * CONSUMO_CARRELLO_KG_ORA * ORE_CARRELLO_GIORNO
                        * FATTORE_CARICO_FREDDO * GIORNI_LOGISTICA,
    },
    "T23_FLAG_TRENI": {
        "titolo": "Trasporto ferroviario su tratte non elettrificate",
        "testo": "Elettrificare una linea ferroviaria costa fra uno e due milioni di euro "
                 "al chilometro e richiede anni di cantiere, con interruzioni del servizio "
                 "e opere civili su ponti e gallerie. Dove i volumi di traffico non "
                 "giustificano quell'investimento, l'automotrice a idrogeno consente di "
                 "eliminare il gasolio senza toccare l'infrastruttura: un unico punto di "
                 "rifornimento in deposito sostituisce centinaia di chilometri di linea "
                 "aerea.\n\n"
                 "È anche la nicchia con i volumi più alti fra quelle qui considerate. Un "
                 "servizio regionale su una tratta di media lunghezza consuma quantità di "
                 "idrogeno paragonabili a quelle di un'intera flotta di autobus urbani, e "
                 "lo fa con una domanda concentrata in un solo punto e prevedibile "
                 "sull'intero orario di servizio. Per un progetto di produzione locale è la "
                 "condizione migliore possibile: un cliente unico, contrattualizzabile, che "
                 "ritira ogni giorno la stessa quantità.\n\n"
                 "Il confronto va comunque condotto sul costo di ciclo di vita completo, "
                 "considerando che il materiale rotabile a idrogeno costa oggi "
                 "sensibilmente più di quello diesel e che la decisione compete al gestore "
                 "del servizio, non al Comune. Il ruolo dell'amministrazione è segnalare la "
                 "disponibilità di idrogeno locale nel momento in cui la Regione programma "
                 "il rinnovo della flotta.",
        "driver": "T23_TRATTA_NON_ELETTRIFICATA_KM",
        "unita": "km di tratta",
        "kg": None,     # serve anche il numero di corse: calcolato a parte
    },
    "T23_FLAG_PORTI_AEROPORTI": {
        "titolo": "Movimentazione portuale e aeroportuale",
        "testo": "I mezzi di piazzale lavorano a ciclo continuo su percorsi "
                 "brevi e ripetitivi, rientrando ogni sera in aree ristrette e sorvegliate: "
                 "è la configurazione ideale per un rifornimento concentrato in pochi punti, "
                 "senza bisogno di una rete distributiva. La domanda è prevedibile giorno "
                 "per giorno e appartiene a un unico soggetto, quindi è "
                 "contrattualizzabile: sono le due condizioni che rendono un impianto "
                 "finanziabile.\n\n"
                 "In ambito portuale si aggiunge la prospettiva del *cold ironing* e "
                 "dell'alimentazione delle navi all'ormeggio, che sposta il fabbisogno su "
                 "un ordine di grandezza superiore, e la possibilità di ricevere idrogeno "
                 "via nave o via ammoniaca. Un porto non è quindi solo un consumatore ma "
                 "un potenziale nodo di importazione, il che cambia la natura del progetto: "
                 "da locale a infrastrutturale.\n\n"
                 "L'interlocutore è l'autorità portuale o il gestore aeroportuale, e i "
                 "tempi decisionali seguono i piani regolatori di quegli enti, non quelli "
                 "comunali.",
        "driver": None,
        "unita": "",
        "kg": None,
    },
    "T23_FLAG_DEPURATORI": {
        "titolo": "Impianti di depurazione",
        "testo": "Il depuratore non è un consumatore di idrogeno ma un possibile "
                 "sito di produzione, e per ragioni che nessun altro impianto comunale "
                 "offre. L'elettrolisi genera otto chilogrammi di ossigeno puro per ogni "
                 "chilogrammo di idrogeno, e l'ossigeno è esattamente il reagente che le "
                 "vasche a fanghi attivi consumano: oggi lo si ottiene comprimendo aria, "
                 "operazione che rappresenta la voce di consumo elettrico più alta "
                 "dell'intero impianto, spesso oltre la metà del totale. Sostituire l'aria "
                 "con ossigeno puro migliora inoltre la resa del processo biologico, "
                 "perché aumenta la concentrazione disponibile ai batteri.\n\n"
                 "La seconda sinergia è l'acqua. L'elettrolisi richiede acqua "
                 "demineralizzata in quantità modeste — circa undici litri per chilogrammo "
                 "di idrogeno — mentre un depuratore ne tratta ogni giorno migliaia di "
                 "metri cubi e dispone già di prelievo, pompaggio e competenze per "
                 "gestirli. Il prelievo dell'elettrolizzatore resta nell'ordine di un "
                 "millesimo della portata trattata: una risorsa di fatto illimitata e "
                 "senza costo aggiuntivo.\n\n"
                 "La terza è il calore. Lo stack dissipa in calore circa un terzo "
                 "dell'energia assorbita, disponibile a 55-60 °C: è la temperatura giusta "
                 "per mantenere i digestori anaerobici in regime mesofilo, intorno ai 37 "
                 "gradi. Recuperarlo evita di bruciare parte del biogas autoprodotto per "
                 "riscaldare i fanghi, lasciandolo interamente disponibile per la "
                 "trasformazione in biometano — che a sua volta può diventare idrogeno a "
                 "basse emissioni senza passare dall'elettrolisi.\n\n"
                 "Infine il profilo di carico. Un depuratore assorbe energia in modo "
                 "pressoché costante tutto l'anno, senza le punte tipiche di altre utenze: "
                 "accoppiato a un elettrolizzatore diventa un punto di flessibilità per la "
                 "rete locale, capace di assorbire i surplus di produzione rinnovabile nei "
                 "momenti in cui verrebbero altrimenti dispersi.",
        "driver": None,          # trattato a parte: è produzione, non consumo
        "unita": "",
        "kg": None,
    },
}



def sinergia_depuratore(riga) -> str:
    """Dimensiona l'elettrolizzatore che il depuratore potrebbe ospitare.

    Il criterio non è la domanda di idrogeno ma il fabbisogno di ossigeno delle
    vasche: si taglia l'elettrolizzatore su quello, e l'idrogeno diventa il
    prodotto principale di un impianto nato per un'altra ragione.
    """
    kwh = numero(riga.get("T23_AERAZIONE_KWH_ANNO"))
    if not kwh:
        return ""

    o2_anno = kwh * RESA_AERAZIONE_KG_O2_KWH
    h2_anno = o2_anno / RAPPORTO_O2_H2
    energia_mwh = h2_anno * CONSUMO_ELETTROLISI_KWH_KG / 1000
    potenza_mw = energia_mwh * 1000 / 8000 / 1000      # esercizio quasi continuo
    calore_kw = potenza_mw * 1000 * QUOTA_CALORE_ELETTROLISI
    bus = h2_anno / (CONSUMO_BUS_KG_GIORNO * GIORNI_OPERATIVI)

    out = ["", "| Grandezza | Valore |", "| --- | --- |",
           f"| Consumo per aerazione | {formatta_numero(kwh)} kWh/anno |",
           f"| Ossigeno oggi richiesto dalle vasche | {formatta_numero(round(o2_anno / 1000))} t/anno |",
           f"| Idrogeno associato a quell'ossigeno | {formatta_numero(round(h2_anno / 1000))} t/anno |",
           f"| Taglia dell'elettrolizzatore | {formatta_numero(potenza_mw)} MW |",
           f"| Calore di scarto recuperabile | {formatta_numero(round(calore_kw))} kW termici |", ""]

    out.append(f"Dimensionando l'elettrolizzatore sul fabbisogno di ossigeno delle vasche "
               f"si otterrebbero circa **{formatta_numero(round(h2_anno / 1000))} tonnellate "
               f"di idrogeno all'anno**, sufficienti ad alimentare l'equivalente di "
               f"{formatta_numero(bus)} autobus urbani. L'ossigeno smetterebbe di essere un "
               "sottoprodotto da disperdere e diventerebbe il reagente che oggi si paga "
               "sotto forma di energia per la compressione dell'aria.")
    out.append("")
    out.append("> Stima costruita su una resa di trasferimento di "
               f"{formatta_numero(RESA_AERAZIONE_KG_O2_KWH)} kg di ossigeno per kWh e sul "
               "rapporto di massa fisso 1:8 dell'elettrolisi. È un ordine di grandezza per "
               "capire se la sinergia meriti uno studio dedicato: il dimensionamento reale "
               "richiede il carico organico effettivo dell'impianto, espresso in abitanti "
               "equivalenti, e la verifica della compatibilità fra il profilo di produzione "
               "dell'ossigeno e quello del consumo delle vasche.")
    return "\n".join(out)


def sezione_nicchie(riga) -> str:
    """Sezione 2.3: usi di nicchia, con stima del fabbisogno dove i driver ci sono."""
    attive = [c for c in DETTAGLIO_NICCHIE if c in riga.index and vero(riga[c])]
    if not attive:
        return ""

    out = [testo_da_template("A23-nicchie_intro_it.md", {}, TESTO_NICCHIE_PREDEFINITO), ""]

    speciali = numero(riga.get("T23_N_MEZZI_SPECIALI"))
    convertibili = numero(riga.get("T23_MEZZI_FUEL_CELL"))
    if speciali or convertibili:
        frase = []
        if speciali:
            frase.append(f"Il censimento ha individuato {formatta_numero(speciali)} mezzi "
                         "speciali sul territorio")
        if convertibili:
            frase.append(f"di cui {formatta_numero(convertibili)} tecnicamente convertibili "
                         "a celle a combustibile" if speciali else
                         f"Risultano {formatta_numero(convertibili)} mezzi convertibili a "
                         "celle a combustibile")
        out += [", ".join(frase) + ".", ""]

    totale_kg = 0.0
    stimate = []

    for colonna in attive:
        info = DETTAGLIO_NICCHIE[colonna]
        out.append(f"#### {info['titolo']}")
        out.append(info["testo"])

        kg = None
        driver = numero(riga.get(info["driver"])) if info["driver"] else None

        if colonna == "T23_FLAG_TRENI":
            km = numero(riga.get("T23_TRATTA_NON_ELETTRIFICATA_KM"))
            corse = numero(riga.get("T23_CORSE_GIORNALIERE"))
            if km and corse:
                kg = km * corse * 2 * 365 * CONSUMO_TRENO_KG_KM
                out.append("")
                out.append(f"La tratta misura {formatta_numero(km)} km e ospita "
                           f"{formatta_numero(corse)} corse al giorno: considerando il "
                           "percorso di andata e ritorno, il servizio richiederebbe circa "
                           f"**{formatta_numero(kg / 1000)} tonnellate di idrogeno all'anno**.")
        elif driver is not None and info["kg"]:
            kg = info["kg"](driver)
            out.append("")
            out.append(f"Il questionario riporta {formatta_numero(driver)} "
                       f"{info['unita']}, che corrispondono a circa "
                       f"**{formatta_numero(kg / 1000)} tonnellate di idrogeno all'anno**.")

        if colonna == "T23_FLAG_DEPURATORI":
            out.append(sinergia_depuratore(riga))

        if kg:
            totale_kg += kg
            stimate.append((info["titolo"], kg))
        out.append("")

    if len(stimate) > 1:
        out.append("#### Peso complessivo degli usi di nicchia")
        out += ["| Impiego | Fabbisogno stimato |", "| --- | --- |"]
        out += [f"| {t} | {formatta_numero(k / 1000)} t/anno |" for t, k in stimate]
        out.append(f"| **Totale** | **{formatta_numero(totale_kg / 1000)} t/anno** |")
        out.append("")

    if totale_kg:
        tot_ton = totale_kg / 1000
        if tot_ton >= SOGLIA_MOBILITA_AUTONOMA_TON:
            out.append(f"Con {formatta_numero(tot_ton)} t/anno gli usi di nicchia non sono "
                       "più un contorno: da soli raggiungono la scala di una piccola "
                       "stazione di rifornimento, e vanno considerati parte della domanda "
                       "principale.")
        else:
            out.append(f"Il totale di {formatta_numero(tot_ton)} t/anno conferma la natura "
                       "dimostrativa di questi impieghi. Il loro valore sta nell'essere "
                       "primi passi realizzabili: costruiscono competenza tecnica e "
                       "consenso, che sono i prerequisiti dei progetti più impegnativi.")
        out.append("")
        out.append("> Le stime sopra derivano dai driver fisici dichiarati nel questionario "
                   f"con parametri di conversione dichiarati: {formatta_numero(RESA_FUEL_CELL_KWH_KG)} "
                   "kWh elettrici per kg di idrogeno in cella a combustibile, "
                   f"{formatta_numero(CONSUMO_TRENO_KG_KM)} kg/km per l'automotrice "
                   "ferroviaria. Sono ordini di grandezza per orientare le priorità, non "
                   "valori di progetto.")

    return "\n".join(out).strip()



TESTO_TERMICO_PREDEFINITO = """### Fabbisogno termico degli edifici pubblici (Tool 2.4)

Il riscaldamento degli edifici è il caso in cui la gerarchia termodinamica si vede
con più chiarezza, ed è anche quello in cui l'idrogeno viene proposto più spesso a
sproposito. La ragione è che il calore richiesto da una scuola o da un municipio si
attesta fra i 40 e i 70 gradi: temperature che una pompa di calore raggiunge
prelevando energia dall'ambiente, moltiplicando per tre o quattro ogni kilowattora
elettrico consumato.

Bruciare idrogeno per ottenere lo stesso calore significa invece percorrere una
catena di trasformazioni — elettricità, elettrolisi, compressione, combustione — in
cui ogni passaggio disperde energia. Il confronto che segue quantifica questa
differenza sui consumi reali del patrimonio comunale.
"""


def sezione_termico(riga) -> str:
    """Sezione 2.4: fabbisogno termico e confronto fra le soluzioni."""
    termico = numero(riga.get("T24_FABBISOGNO_TERMICO_KWH_ANNO"))
    ottimale = riga.get("T24_SOLUZIONE_OTTIMALE")
    pulita = riga.get("T24_SOLUZIONE_PIU_PULITA")
    co2 = numero(riga.get("T24_EMISSIONI_EVITATE_KGCO2_ANNO"))

    if not termico and is_vuoto(ottimale):
        return ""

    out = [testo_da_template("A24-termico_intro_it.md", {}, TESTO_TERMICO_PREDEFINITO), ""]

    if termico:
        # stessa energia utile, due strade: quanta elettricità serve a ciascuna
        kg_h2 = termico / RENDIMENTO_CALDAIA_H2 / PCI_H2_KWH_KG
        elettrico_h2 = kg_h2 * CONSUMO_ELETTROLISI_KWH_KG
        elettrico_pdc = termico / COP_POMPA_CALORE
        rapporto = elettrico_h2 / elettrico_pdc if elettrico_pdc else None

        out.append("#### Le due strade a confronto")
        out += ["| Voce | Caldaia a idrogeno | Pompa di calore |", "| --- | --- | --- |",
                f"| Calore utile richiesto | {formatta_numero(termico)} kWh/anno | "
                f"{formatta_numero(termico)} kWh/anno |",
                f"| Idrogeno necessario | {formatta_numero(round(kg_h2))} kg/anno | — |",
                f"| Elettricità necessaria | {formatta_numero(round(elettrico_h2))} kWh/anno | "
                f"{formatta_numero(round(elettrico_pdc))} kWh/anno |", ""]

        elettrico_pdc_freddo = termico / COP_POMPA_CALORE_MONTAGNA
        rapporto_freddo = elettrico_h2 / elettrico_pdc_freddo if elettrico_pdc_freddo else None
        maggiorazione = (elettrico_pdc_freddo / elettrico_pdc - 1) * 100 if elettrico_pdc else 0

        if rapporto:
            out.append(f"A parità di calore prodotto, la via dell'idrogeno consuma "
                       f"**{formatta_numero(rapporto)} volte l'energia elettrica** della "
                       "pompa di calore. Non è una differenza marginale che il progresso "
                       "tecnologico possa colmare: discende dal fatto che la pompa di "
                       "calore sposta calore già presente nell'ambiente, mentre "
                       "l'elettrolisi lo produce da capo passando per la molecola.")
            out.append("")
            out.append("#### Effetto del clima")
            out.append(f"Il confronto sopra assume un coefficiente di prestazione stagionale "
                       f"di {formatta_numero(COP_POMPA_CALORE)}, valore corrente in pianura. "
                       f"In zona climatica F, con temperature di progetto sotto i -5 °C, la "
                       f"stessa macchina scende attorno a "
                       f"{formatta_numero(COP_POMPA_CALORE_MONTAGNA)}: il vantaggio "
                       f"sull'idrogeno resta netto ({formatta_numero(rapporto_freddo)} volte), "
                       f"ma il fabbisogno elettrico sale a "
                       f"{formatta_numero(round(elettrico_pdc_freddo))} kWh/anno, con una "
                       f"maggiorazione del {formatta_numero(maggiorazione)}%.")
            out.append("")
            out.append("È il dato che conta davvero per l'amministrazione: non l'efficienza "
                       "in sé, ma il picco di potenza che la rete elettrica locale deve "
                       "reggere proprio nei giorni in cui è più sollecitata. Prima di "
                       "elettrificare un patrimonio edilizio in quota va verificata con il "
                       "distributore la capacità disponibile nelle ore critiche.")
            out.append("")
            out.append("> Confronto condotto con un potere calorifico di "
                       f"{formatta_numero(PCI_H2_KWH_KG)} kWh/kg, un rendimento di caldaia "
                       f"del {formatta_numero(RENDIMENTO_CALDAIA_H2 * 100)}%, un consumo di "
                       f"elettrolisi di {formatta_numero(CONSUMO_ELETTROLISI_KWH_KG)} kWh/kg "
                       f"e un coefficiente di prestazione stagionale di "
                       f"{formatta_numero(COP_POMPA_CALORE)} per la pompa di calore.")
            out.append("")

    # --- esito dello strumento
    if not is_vuoto(ottimale) or not is_vuoto(pulita):
        out.append("#### Esito dell'analisi")
        righe = []
        if not is_vuoto(ottimale):
            righe.append(f"| Soluzione economicamente ottimale | {str(ottimale).strip()} |")
        if not is_vuoto(pulita):
            righe.append(f"| Soluzione a minori emissioni | {str(pulita).strip()} |")
        if co2:
            righe.append(f"| Emissioni evitate | {formatta_numero(co2 / 1000)} tCO2/anno |")
        out += ["| Voce | Esito |", "| --- | --- |"] + righe + [""]

        testo_ott = str(ottimale).strip().lower()
        testo_pul = str(pulita).strip().lower()
        h2_ottimale = "idrogeno" in testo_ott
        h2_piu_pulito = "idrogeno" in testo_pul
        pdc_ottimale = "pompa" in testo_ott or "calore" in testo_ott

        # Controllo di plausibilità: una caldaia a idrogeno non può risultare meno
        # emissiva di una pompa di calore, perché la prima consuma diverse volte
        # l'energia della seconda per lo stesso calore utile. Se l'esito lo afferma,
        # il dato è sbagliato e va segnalato invece di essere commentato.
        if h2_piu_pulito and pdc_ottimale:
            out.append("> **Esito da verificare.** Il confronto energetico riportato sopra "
                       "mostra che la caldaia a idrogeno consuma diverse volte l'energia "
                       "della pompa di calore per produrre lo stesso calore: non può quindi "
                       "risultare la soluzione a minori emissioni, a meno che l'idrogeno "
                       "impiegato non provenga da un surplus altrimenti inutilizzato. "
                       "Prima di procedere occorre rivedere le ipotesi inserite nel Tool "
                       "2.4, in particolare il fattore di emissione attribuito "
                       "all'elettricità di rete e la provenienza dell'idrogeno.")
            out.append("")

        implausibile = h2_piu_pulito and pdc_ottimale

        if implausibile:
            pass
        elif not is_vuoto(ottimale) and not is_vuoto(pulita) and testo_ott == testo_pul:
            out.append("La soluzione più conveniente coincide con quella a minori "
                       "emissioni: non vi è alcun conflitto fra sostenibilità economica e "
                       "obiettivo ambientale, e la decisione non richiede compromessi.")
        elif not is_vuoto(ottimale) and not is_vuoto(pulita):
            out.append(f"La soluzione economicamente ottimale (*{str(ottimale).strip()}*) "
                       f"non coincide con quella a minori emissioni "
                       f"(*{str(pulita).strip()}*). È una scelta politica prima che "
                       "tecnica, e come tale va esplicitata nel piano: bisogna dichiarare "
                       "quale criterio prevale, con quali risorse si copre l'eventuale "
                       "differenza e su quale orizzonte la si recupera. Lasciare implicita "
                       "questa decisione è il modo più rapido per trovarsi con un impianto "
                       "che nessuno difende quando arriva il momento di finanziarlo.")

        if h2_ottimale:
            out.append("")
            out.append("L'idrogeno risulta la soluzione ottimale per il fabbisogno termico: "
                       "è un esito raro, che vale la pena verificare. Di norma si verifica "
                       "solo in presenza di condizioni particolari — edifici storici in cui "
                       "non è possibile intervenire sugli impianti di distribuzione, "
                       "temperature di processo elevate, o disponibilità di idrogeno di "
                       "scarto già presente sul territorio. Se nessuna di queste ricorre, "
                       "conviene rivedere le ipotesi di calcolo prima di procedere.")
        elif termico:
            out.append("")
            out.append("Prima di destinare idrogeno al riscaldamento conviene esaurire le "
                       "misure che riducono il fabbisogno stesso: isolamento "
                       "dell'involucro, sostituzione dei serramenti, regolazione degli "
                       "impianti. Un edificio che consuma meno richiede una macchina più "
                       "piccola, qualunque essa sia, e l'intervento sull'involucro ha una "
                       "vita utile doppia rispetto a quella di qualsiasi generatore.")
        out.append("")

    return "\n".join(out).strip()




TESTO_PERCORSO_B_INTRO = """## Percorso B - L'offerta di idrogeno

Il percorso B risponde alla domanda speculare rispetto al precedente: il territorio
è in grado di produrre l'idrogeno di cui c'è bisogno, e a quali condizioni?

La risposta non dipende dalla tecnologia, che è disponibile e matura, ma da tre
risorse che il Comune possiede o non possiede: la superficie su cui installare
generazione rinnovabile, la capacità della rete elettrica di accogliere quella
potenza, e il consenso necessario perché entrambe si traducano in impianti
realizzati. Nessuna delle tre si compra, e la prima è quella che determina la scala
di tutto il resto.

L'analisi procede in due passaggi. Il primo censisce ciò che il territorio ha già —
superfici, rinnovabili installate, margini di rete — distinguendo ciò su cui
l'amministrazione decide da sola da ciò che dipende da terzi. Il secondo simula un
impianto su quella base, ora per ora lungo un anno intero, e ne restituisce
produzione, costo e conformità normativa.
"""

TESTO_AREE_PREDEFINITO = """### Aree e potenziale rinnovabile (Tool 2.5)

Produrre idrogeno significa prima di tutto produrre elettricità rinnovabile, e
questo richiede superficie. È il vincolo che decide la scala di qualunque progetto,
prima ancora del capitale disponibile: un elettrolizzatore si compra, un ettaro di
terreno idoneo no.

La ricognizione che segue distingue le superfici per tipologia, perché differiscono
per resa, costo di connessione e soprattutto per accettabilità sociale. Una
copertura industriale non toglie suolo a nessuno; un impianto a terra su superficie
agricola apre una discussione che va affrontata prima della progettazione, non dopo.
"""


def sezione_aree(riga) -> str:
    """Sezione 2.5: superfici, rete elettrica e attrito territoriale."""
    aree = {
        "Aree dismesse (brownfield)": "T25_SUP_BROWNFIELD_MQ",
        "Coperture industriali": "T25_SUP_TETTI_IND_MQ",
        "Coperture civili": "T25_SUP_TETTI_CIV_MQ",
        "Superfici incolte": "T25_SUP_INCOLTE_MQ",
        "Superficie agricola utilizzata": "T25_SUP_SAU_MQ",
        "Aree gravate da servitù": "T25_SUP_SERVITU_MQ",
    }
    disponibili = {n: (numero(riga.get(col)) or 0) for n, col in aree.items()}
    totale_mq = sum(disponibili.values())
    pubblica_mq = numero(riga.get("T25_SUP_PUBBLICA_MQ")) or 0
    fer = numero(riga.get("T25_FER_INSTALLATA_MW"))
    programmabili = numero(riga.get("T25_PROGRAMMABILI_MW"))
    cap_rete = numero(riga.get("T25_CAPACITA_RESIDUA_MW"))
    distanza = numero(riga.get("T25_DISTANZA_CABINA_PRIMARIA_KM"))
    sau_occupata = numero(riga.get("T25_SAU_OCCUPATA_PERC"))
    istanze = numero(riga.get("T25_PIPELINE_ISTANZE"))
    autorizzati = numero(riga.get("T25_PROGETTI_AUTORIZZATI"))

    if totale_mq == 0 and fer is None and cap_rete is None:
        return ""

    out = [testo_da_template("B25-aree_intro_it.md", {}, TESTO_AREE_PREDEFINITO), ""]

    # --- superfici
    if totale_mq > 0:
        out.append("#### Superfici disponibili")
        out += ["| Tipologia | Superficie | Quota |", "| --- | --- | --- |"]
        for nome, mq in sorted(disponibili.items(), key=lambda x: -x[1]):
            if mq <= 0:
                continue
            out.append(f"| {nome} | {formatta_numero(mq / 10000)} ha | "
                       f"{formatta_numero(mq / totale_mq * 100)}% |")
        out.append(f"| **Totale** | **{formatta_numero(totale_mq / 10000)} ha** | |")
        out.append("")

        # la leva vera: cosa il Comune controlla davvero
        if pubblica_mq > 0:
            quota_pub = pubblica_mq / totale_mq * 100
            out.append(f"Di queste superfici, **{formatta_numero(pubblica_mq / 10000)} "
                       f"ettari sono di proprietà pubblica**, pari al "
                       f"{formatta_numero(quota_pub)}% del totale.")
            if quota_pub >= 50:
                out.append("È la condizione più favorevole che un Comune possa avere: la "
                           "disponibilità delle aree non dipende da trattative con "
                           "privati, e l'amministrazione può mettere a bando un diritto "
                           "di superficie senza attendere nessuno. È anche la leva che "
                           "rende un progetto attrattivo per un investitore, perché "
                           "elimina il rischio più difficile da quantificare.")
            elif quota_pub >= 15:
                out.append("La quota pubblica consente di avviare un primo lotto in "
                           "autonomia, dimostrando la fattibilità prima di coinvolgere i "
                           "proprietari privati. È una sequenza che riduce il rischio "
                           "negoziale: si tratta da una posizione di progetto avviato, "
                           "non di ipotesi.")
            else:
                out.append("La quota pubblica è marginale: la realizzazione dipende quasi "
                           "interamente dalla disponibilità dei proprietari privati. È il "
                           "vincolo da affrontare per primo, perché nessun altro passaggio "
                           "ha senso finché le aree non sono nella disponibilità del "
                           "progetto.")
            out.append("")

    # --- rete elettrica
    if cap_rete is not None or distanza is not None:
        out.append("#### Connessione alla rete")
        righe = []
        if fer is not None:
            righe.append(f"| Rinnovabili già installate | {formatta_numero(fer)} MW |")
        if programmabili:
            righe.append(f"| di cui fonti programmabili | {formatta_numero(programmabili)} MW |")
        if cap_rete is not None:
            righe.append(f"| Capacità residua di rete | {formatta_numero(cap_rete)} MW |")
        if distanza is not None:
            righe.append(f"| Distanza dalla cabina primaria | {formatta_numero(distanza)} km |")
        if not is_vuoto(riga.get("T25_ENTRO_5KM_DORSALE")):
            righe.append(f"| Entro 5 km dalla dorsale | {formatta(riga['T25_ENTRO_5KM_DORSALE'], 'T25_ENTRO_5KM_DORSALE')} |")
        out += ["| Parametro | Valore |", "| --- | --- |"] + righe + [""]

        if distanza is not None:
            if distanza <= 3:
                out.append(f"Con {formatta_numero(distanza)} km dalla cabina primaria la "
                           "linea diretta è quasi sempre la scelta migliore: si paga il "
                           "cavidotto una volta e si evita il pedaggio di trasporto per "
                           "vent'anni.")
            elif distanza >= 10:
                out.append(f"I {formatta_numero(distanza)} km che separano il sito dalla "
                           "cabina primaria rendono improbabile la convenienza di una "
                           "linea diretta: il costo del cavidotto supererebbe quello del "
                           "pedaggio. Conviene ipotizzare la connessione alla rete "
                           "pubblica e verificarne il costo nel Tool 2.6.")
            else:
                out.append(f"La distanza di {formatta_numero(distanza)} km colloca il "
                           "progetto nella fascia in cui linea diretta e rete pubblica si "
                           "equivalgono: la scelta dipende dalla potenza installata, e va "
                           "confrontata caso per caso nel Tool 2.6.")
            out.append("")

        if programmabili:
            out.append(f"La presenza di {formatta_numero(programmabili)} MW di fonti "
                       "programmabili — idroelettrico, biomasse, recupero energetico — è "
                       "una risorsa che il fotovoltaico da solo non offre: producono anche "
                       "di notte e in inverno, quindi alzano le ore di funzionamento "
                       "dell'elettrolizzatore e abbassano il costo dell'idrogeno. Vanno "
                       "considerate nella simulazione del percorso B, caricandone il "
                       "profilo orario reale.")
            out.append("")

    # --- attrito territoriale
    attriti = []
    if vero(riga.get("T25_FLAG_CONTESTAZIONI")):
        attriti.append("Sul territorio si sono già registrate **contestazioni** su impianti "
                       "rinnovabili. È l'informazione più importante di questa sezione: un "
                       "progetto che non affronta il tema del consenso prima della "
                       "progettazione rischia di fermarsi in fase autorizzativa, quando i "
                       "costi sostenuti sono già rilevanti e le posizioni irrigidite.")
    if sau_occupata is not None and sau_occupata > 10:
        attriti.append(f"Il {formatta_numero(sau_occupata)}% della superficie agricola "
                       "comunale è già occupato da impianti. È una quota che rende il "
                       "fotovoltaico a terra difficile da difendere politicamente: "
                       "conviene concentrarsi su coperture e aree dismesse, che non "
                       "sottraggono suolo produttivo.")
    if istanze:
        attriti.append(f"Risultano {formatta_numero(istanze)} istanze in istruttoria"
                       + (f" e {formatta_numero(autorizzati)} progetti già autorizzati"
                          if autorizzati else "") +
                       ". Vanno verificate prima di ipotizzare nuove installazioni: "
                       "potrebbero occupare la capacità di rete residua, che è la risorsa "
                       "più contesa e meno visibile del territorio.")
    if attriti:
        out.append("#### Vincoli di contesto")
        out += [f"- {a}" for a in attriti] + [""]

    return "\n".join(out).strip()



TESTO_PRODUZIONE_PREDEFINITO = """### Dimensionamento della produzione (Tool 2.6)

La simulazione ricostruisce ora per ora un anno intero di esercizio: ottomilasettecentosessanta
valori di produzione rinnovabile, di assorbimento dell'elettrolizzatore, di carica e
scarica dell'accumulo. Non è un dettaglio metodologico, è la sola scala a cui il
problema esiste davvero, perché l'idrogeno si produce quando c'è sole o vento, e non
quando serve.

Da quella simulazione discendono le tre grandezze che decidono la sostenibilità del
progetto: quanto idrogeno esce, quanto costa, e quanta parte è certificabile come
rinnovabile ai sensi della normativa europea.
"""


def sezione_produzione(riga) -> str:
    """Sezione 2.6: esito della simulazione di produzione."""
    prod = numero(riga.get("T26_PRODUZIONE_H2_TON_ANNO"))
    taglia_ely = numero(riga.get("T26_TAGLIA_ELETTROLIZZATORE_MW"))
    taglia_fer = numero(riga.get("T26_TAGLIA_FER_INSTALLATA_MW"))
    bess = numero(riga.get("T26_CAPACITA_BESS_MWH"))
    rfnbo = numero(riga.get("T26_QUOTA_RFNBO_PERC"))
    curtail = numero(riga.get("T26_CURTAILMENT_PERC"))
    copertura = numero(riga.get("T26_COPERTURA_PERC"))
    lcoh = numero(riga.get("T26_LCOH_EURO_KG"))
    capex = numero(riga.get("T26_CAPEX_TOTALE_MLN"))
    payback = numero(riga.get("T26_PAYBACK_ANNI"))
    modalita = riga.get("T26_MODALITA")
    cap_rete = numero(riga.get("T25_CAPACITA_RESIDUA_MW"))

    if prod is None and taglia_ely is None:
        return ""

    out = [testo_da_template("B26-produzione_intro_it.md", {},
                             TESTO_PRODUZIONE_PREDEFINITO), ""]

    if not is_vuoto(modalita):
        out.append(f"La simulazione è stata condotta in modalità *{str(modalita).strip()}*.")
        out.append("")

    # --- configurazione
    righe = []
    for etichetta, valore_, unita in (
            ("Fotovoltaico a terra", numero(riga.get("T26_PV_TERRA_MW")), "MW"),
            ("Fotovoltaico su coperture", numero(riga.get("T26_PV_TETTI_MW")), "MW"),
            ("Fotovoltaico su capannoni", numero(riga.get("T26_PV_CAPANNONI_MW")), "MW"),
            ("Eolico", numero(riga.get("T26_EOLICO_MW")), "MW"),
            ("Potenza rinnovabile complessiva", taglia_fer, "MW"),
            ("Elettrolizzatore", taglia_ely, "MW"),
            ("Accumulo elettrochimico", bess, "MWh")):
        if valore_:
            righe.append(f"| {etichetta} | {formatta_numero(valore_)} {unita} |")
    if righe:
        out.append("#### Configurazione dell'impianto")
        out += ["| Componente | Taglia |", "| --- | --- |"] + righe + [""]

    if taglia_ely and taglia_fer:
        rapporto = taglia_ely / taglia_fer * 100
        out.append(f"L'elettrolizzatore è dimensionato al {formatta_numero(rapporto)}% "
                   "della potenza rinnovabile installata. È il parametro che governa il "
                   "compromesso centrale dell'impianto: una macchina piccola lavora molte "
                   "ore ma lascia perdere i picchi di produzione, una grande li cattura "
                   "tutti ma resta ferma per gran parte dell'anno, e il capitale immobilizzato "
                   "pesa sul costo di ogni chilogrammo prodotto.")
        out.append("")

    # --- esito produttivo
    if prod:
        kg_giorno = prod * 1000 / 365
        out.append("#### Esito della simulazione")
        righe = [f"| Produzione di idrogeno | {formatta_numero(prod)} t/anno |",
                 f"| Erogazione media | {formatta_numero(kg_giorno)} kg/giorno |"]
        if rfnbo is not None:
            righe.append(f"| Quota conforme RFNBO | {formatta_numero(rfnbo)}% |")
        if curtail is not None:
            righe.append(f"| Energia rinnovabile non utilizzata | {formatta_numero(curtail)}% |")
        if copertura is not None:
            righe.append(f"| Copertura del fabbisogno | {formatta_numero(copertura)}% |")
        out += ["| Grandezza | Valore |", "| --- | --- |"] + righe + [""]

    # --- conformità RFNBO
    if rfnbo is not None:
        out.append("#### Conformità ai criteri RFNBO")
        if rfnbo >= 99.5:
            out.append("L'intera produzione risulta conforme ai criteri dell'Atto Delegato "
                       "(UE) 2023/1184. È la condizione che apre l'accesso ai regimi di "
                       "sostegno dedicati e che consente alle imprese utilizzatrici di "
                       "computare l'idrogeno nelle quote obbligatorie della direttiva "
                       "RED III: senza certificazione, per un'impresa Hard-to-Abate quel "
                       "chilogrammo non vale nulla ai fini normativi.")
        elif rfnbo >= QUOTA_RFNBO_MINIMA_PERC:
            out.append(f"Il {formatta_numero(rfnbo)}% della produzione è conforme ai criteri "
                       "RFNBO. La quota restante, prodotta con energia non certificabile, "
                       "va venduta come idrogeno ordinario a un prezzo sensibilmente "
                       "inferiore: è un ricavo che il piano economico deve considerare "
                       "separatamente, non mediare con il resto.")
        else:
            emissioni = emissioni_h2(rfnbo)
            out.append(f"Solo il {formatta_numero(rfnbo)}% della produzione è conforme ai "
                       "criteri RFNBO. **È una quota che mette a rischio l'intero impianto "
                       "del progetto**: gran parte dell'idrogeno non sarebbe computabile "
                       "nelle quote RED III né ammissibile agli incentivi dedicati, e sul "
                       "piano ambientale l'insieme della produzione arriva a "
                       f"{formatta_numero(emissioni)} kg di CO2 per kg di idrogeno. Prima "
                       "di procedere occorre rivedere la configurazione: aumentare la "
                       "potenza rinnovabile dedicata, l'accumulo, oppure ridurre la taglia "
                       "dell'elettrolizzatore.")
        out.append("")

    # --- curtailment
    if curtail is not None and curtail > CURTAILMENT_ACCETTABILE_PERC:
        out.append(f"Il {formatta_numero(curtail)}% dell'energia rinnovabile prodotta non "
                   "viene utilizzato, perché eccede la capacità di assorbimento "
                   "dell'elettrolizzatore nei momenti di massima generazione. È energia "
                   "pagata e non trasformata: vale la pena verificare se un accumulo "
                   "maggiore, o una taglia superiore dell'elettrolizzatore, la recuperino "
                   "a un costo inferiore a quello che la loro installazione comporta.")
        out.append("")

    # --- economia
    if lcoh is not None or capex is not None:
        out.append("#### Sostenibilità economica")
        righe = []
        if capex:
            righe.append(f"| Investimento complessivo | {formatta_numero(capex)} milioni di Euro |")
        connessioni = numero(riga.get("T26_CAPEX_CONNESSIONI_EURO"))
        if connessioni:
            righe.append(f"| di cui connessioni elettriche | Euro {formatta_numero(connessioni)} |")
        if lcoh is not None:
            righe.append(f"| Costo livellato dell'idrogeno | Euro {formatta_numero(lcoh)}/kg |")
        if payback is not None:
            righe.append(f"| Tempo di ritorno | {formatta_numero(payback)} anni |")
        out += ["| Voce | Valore |", "| --- | --- |"] + righe + [""]

        if lcoh is not None:
            if lcoh <= LCOH_COMPETITIVO:
                out.append(f"Un costo di produzione di Euro {formatta_numero(lcoh)} al "
                           "chilogrammo colloca il progetto nella fascia competitiva del "
                           "mercato europeo dell'idrogeno rinnovabile. La sostenibilità "
                           "non dipende quindi da un contributo permanente, ma dalla "
                           "capacità di contrattualizzare i volumi: senza acquirenti "
                           "impegnati, un buon costo di produzione non basta.")
            elif lcoh <= LCOH_CRITICO:
                out.append(f"Il costo di Euro {formatta_numero(lcoh)} al chilogrammo si "
                           "colloca nella fascia intermedia. Il progetto regge se assistito "
                           "da un contributo in conto capitale che riduca il peso "
                           "dell'ammortamento, oppure se l'idrogeno viene venduto a "
                           "utilizzatori che ne hanno un obbligo normativo e per i quali "
                           "l'alternativa è una sanzione, non un combustibile più economico.")
            else:
                out.append(f"Il costo di Euro {formatta_numero(lcoh)} al chilogrammo è "
                           "**fuori mercato** rispetto ai riferimenti europei attuali. La "
                           "configurazione va rivista prima di procedere: nella maggior "
                           "parte dei casi la causa è un elettrolizzatore che lavora poche "
                           "ore l'anno, quindi la strada è aumentare la potenza rinnovabile "
                           "dedicata o ridurre la taglia della macchina.")
            out.append("")

        if payback is not None and payback > PAYBACK_ACCETTABILE_ANNI:
            out.append(f"Il tempo di ritorno di {formatta_numero(payback)} anni eccede "
                       "l'orizzonte che un'amministrazione può assumere senza un partner "
                       "industriale. È il segnale che il progetto va costruito come "
                       "partenariato pubblico-privato, con il Comune che conferisce aree e "
                       "autorizzazioni e un operatore che porta capitale e gestione.")
            out.append("")

    # --- verifiche incrociate con il territorio
    verifiche = []
    if cap_rete and taglia_ely and taglia_ely > cap_rete:
        verifiche.append(f"L'elettrolizzatore ({formatta_numero(taglia_ely)} MW) supera la "
                         f"capacità residua di rete dichiarata nel questionario 2.5 "
                         f"({formatta_numero(cap_rete)} MW). È il vincolo che più spesso "
                         "determina i tempi di un progetto: va verificato con il "
                         "distributore prima di qualunque altra cosa.")

    sup_terra = numero(riga.get("T26B_SUP_TERRA_HA"))
    disponibile_mq = sum(numero(riga.get(c)) or 0 for c in
                         ("T25_SUP_BROWNFIELD_MQ", "T25_SUP_INCOLTE_MQ",
                          "T25_SUP_SAU_MQ", "T25_SUP_SERVITU_MQ"))
    if sup_terra and disponibile_mq:
        quota = sup_terra * 10000 / disponibile_mq * 100
        if quota > 100:
            verifiche.append(f"L'impianto richiede {formatta_numero(sup_terra)} ettari a "
                             "terra, più di quanti ne risultino disponibili dal "
                             "questionario 2.5. La configurazione non è realizzabile così "
                             "com'è: va ridotta la quota a terra a favore delle coperture, "
                             "oppure esteso il perimetro oltre i confini comunali.")
        elif quota > QUOTA_SUOLO_ATTENZIONE_PERC:
            verifiche.append(f"L'impianto occuperebbe il {formatta_numero(quota)}% delle "
                             "superfici a terra disponibili. È una quota che rende il "
                             "consumo di suolo un tema di discussione pubblica: conviene "
                             "affrontarlo nel percorso partecipativo prima che diventi "
                             "un'opposizione in fase autorizzativa.")

    if verifiche:
        out.append("#### Verifiche di coerenza con il territorio")
        out += [f"- {v}" for v in verifiche] + [""]

    return "\n".join(out).strip()



TESTO_PREMESSA_PERCORSI = """## Premessa: che cosa stiamo davvero misurando

L'idrogeno non è un obiettivo, è uno strumento. L'obiettivo è ridurre le emissioni
del territorio, e rispetto a quell'obiettivo l'idrogeno occupa una posizione precisa
e circoscritta.

La gerarchia degli interventi di decarbonizzazione è ormai consolidata e non è
opinabile. Al primo posto sta la riduzione dei consumi — isolare gli edifici,
efficientare i processi, evitare gli sprechi — perché l'energia che non si consuma
non va né prodotta né trasportata. Al secondo posto sta l'**elettrificazione
diretta**: pompe di calore per il riscaldamento, veicoli a batteria per la mobilità
urbana, forni elettrici e a induzione per i processi industriali che lo consentono.
È la strada più efficiente, la più matura e quasi sempre la meno costosa.

L'idrogeno viene dopo, e serve a coprire quello che resta: il **tratto finale della
decarbonizzazione**, i settori in cui l'elettrificazione incontra limiti fisici o
chimici insuperabili. Sono una minoranza dei consumi complessivi, ma sono anche i
più difficili da abbattere, ed è per questo che meritano uno strumento dedicato.
Impiegare idrogeno dove la batteria o la pompa di calore arrivano altrettanto bene
non accelera la transizione: la rallenta, perché consuma energia rinnovabile
preziosa per ottenere un risultato che si sarebbe ottenuto con un terzo di quella
stessa energia.

### Perché questa analisi vale anche se l'idrogeno non serve

C'è una conseguenza di questo ragionamento che conviene rendere esplicita fin
dall'inizio, perché cambia il senso di tutto il documento.

L'idrogeno rinnovabile si produce con elettricità rinnovabile: non esiste idrogeno
verde senza un impianto fotovoltaico, eolico o idroelettrico che lo alimenti, e in
quantità considerevoli, dato che ogni chilogrammo ne richiede una cinquantina di
kilowattora. Ne discende che **misurare la capacità di un territorio di produrre
idrogeno equivale a misurare la sua capacità di produrre energia rinnovabile**, e
quindi la sua possibilità di decarbonizzarsi con qualunque tecnologia.

Le rilevazioni che seguono censiscono superfici disponibili, capacità residua della
rete elettrica, consumi termici degli edifici pubblici, percorrenze e costi delle
flotte comunali, processi industriali energivori. Sono esattamente le informazioni
che servono per un piano di elettrificazione, per un Piano d'Azione per l'Energia
Sostenibile e il Clima, per una comunità energetica rinnovabile o per la
programmazione degli interventi sul patrimonio edilizio.

Se al termine dell'analisi risulterà che sul territorio l'idrogeno non ha un impiego
sensato — esito legittimo e in molti casi corretto — il Comune non si troverà con un
documento inutile, ma con la mappa della propria capacità di produrre energia pulita
e con l'ordine di priorità degli interventi che la rendono realizzabile. Il valore
di questo Action Plan non dipende dal fatto che l'idrogeno risulti conveniente:
dipende dal fatto che la risposta, qualunque sia, poggi su dati verificabili anziché
su aspettative.
"""

TESTO_PERCORSO_A_INTRO = """## Percorso A - La domanda di idrogeno

Il percorso A risponde a una sola domanda: sul territorio comunale esiste qualcuno
che ha bisogno di idrogeno, e per ragioni che nessuna altra tecnologia soddisfa?

È una domanda meno ovvia di quanto sembri. L'idrogeno non è un combustibile
migliore degli altri: è un vettore costoso da produrre, difficile da stoccare e
soggetto a perdite di efficienza a ogni passaggio. Ha senso esattamente dove le
alternative non arrivano, e non ha senso da nessun'altra parte. Cercare la domanda
significa quindi separare i casi in cui l'idrogeno è necessario da quelli in cui
sarebbe solo una scelta costosa, e il criterio di separazione non è l'ambizione
dell'amministrazione ma la termodinamica.

L'analisi si articola in quattro rilevazioni, condotte con altrettanti strumenti
del Toolkit:

| Strumento | Oggetto | Domanda a cui risponde |
| --- | --- | --- |
| Tool 2.1 | Industria Hard-to-Abate | quali processi non possono fare a meno della molecola |
| Tool 2.2 | Flotte e mobilità | quali mezzi la batteria non riesce a servire |
| Tool 2.3 | Usi di nicchia | dove contano continuità e tempi più del costo |
| Tool 2.4 | Fabbisogno termico | se il riscaldamento pubblico rientri fra gli usi sensati |

Le quattro rilevazioni restituiscono volumi molto diversi fra loro, e il confronto
finale fra le componenti dice quale sarà la vera natura del progetto comunale.
"""


def testo_percorso_a(riga) -> str:
    """Percorso A: introduzione, quattro rilevazioni, bilancio finale."""
    ind = numero(riga.get("T21_FABBISOGNO_H2_TON_ANNO"))
    flotta = numero(riga.get("T22_FABBISOGNO_H2_TON_ANNO"))
    dom = totale(riga, ["T21_FABBISOGNO_H2_TON_ANNO", "T22_FABBISOGNO_H2_TON_ANNO"])

    out = [testo_da_template("A00-percorso_intro_it.md", {}, TESTO_PERCORSO_A_INTRO), ""]

    # --- le quattro rilevazioni
    for sezione in (sezione_hta(riga), sezione_flotte(riga),
                    sezione_nicchie(riga), sezione_termico(riga)):
        if sezione:
            out += [sezione, ""]

    # --- bilancio complessivo, in chiusura
    out.append(bilancio_domanda(riga, ind, flotta, dom))
    return "\n".join(p for p in out if p is not None).strip()


def bilancio_domanda(riga, ind, flotta, dom) -> str:
    """Sintesi finale del percorso A: quanto pesa la domanda e cosa comporta."""
    if not dom:
        return ("### Bilancio della domanda\n\n"
                "Per questo Comune non è stato quantificato alcun fabbisogno di idrogeno. "
                "L'analisi dei percorsi resta parziale finché i questionari sulla domanda "
                "industriale e sulle flotte non vengono completati: senza un volume, "
                "nessuna delle valutazioni successive su produzione e logistica può essere "
                "dimensionata.")

    kg_giorno = dom * 1000 / GIORNI_OPERATIVI
    bus_eq = kg_giorno / CONSUMO_BUS_KG_GIORNO
    litri = dom * 1000 * LITRI_DIESEL_PER_KG_H2
    co2_unit = co2_evitata_kg_per_kg_h2(riga)
    co2 = dom * co2_unit
    quota_rfnbo = numero(riga.get("T26_QUOTA_RFNBO_PERC"))

    out = ["### Bilancio della domanda", ""]
    out.append(f"Sommando le rilevazioni, la domanda potenziale complessiva del territorio "
               f"ammonta a **{formatta_numero(dom)} tonnellate di idrogeno all'anno**, pari "
               f"a circa {formatta_numero(kg_giorno)} kg al giorno su {GIORNI_OPERATIVI} "
               "giorni operativi.")
    out.append("")

    if ind and flotta:
        quota_ind = ind / (ind + flotta) * 100
        out.append("Il valore somma due domande di natura diversa, che non si "
                   "sovrappongono. La **domanda di processo** riguarda l'idrogeno impiegato "
                   "dentro il ciclo produttivo delle imprese, come materia prima o come "
                   "combustibile per il calore ad alta temperatura: non comprende i mezzi "
                   "di quelle stesse aziende. La **domanda di mobilità** riguarda i "
                   "veicoli, pubblici e privati, censiti separatamente.")
        out.append("")
        out += ["| Componente | Fabbisogno | Quota |", "| --- | --- | --- |",
                f"| Processi industriali (Tool 2.1) | {formatta_numero(ind)} t/anno | "
                f"{formatta_numero(quota_ind)}% |",
                f"| Mobilità e flotte (Tool 2.2) | {formatta_numero(flotta)} t/anno | "
                f"{formatta_numero(100 - quota_ind)}% |", ""]

        if quota_ind >= 70:
            out.append("La domanda è **trainata dall'industria**: il progetto va costruito "
                       "attorno agli utilizzatori privati, con il Comune nel ruolo di "
                       "facilitatore autorizzativo e garante del percorso partecipativo "
                       "più che di investitore diretto.")
        elif quota_ind <= 30:
            out.append("La domanda è **trainata dalla flotta pubblica**: il Comune ha "
                       "controllo diretto sull'utenza principale e può quindi impegnare "
                       "volumi certi in sede di gara. È la configurazione che rende più "
                       "semplice la bancabilità, perché elimina il rischio di mercato.")
        else:
            out.append("Domanda pubblica e privata si equivalgono: la configurazione più "
                       "adatta è un accordo di programma che vincoli entrambe le componenti "
                       "prima dell'investimento infrastrutturale.")
        out.append("")

    # --- ordini di grandezza
    out.append("#### Che cosa significano questi volumi")
    out += ["| Riferimento | Valore |", "| --- | --- |",
            f"| Domanda complessiva | {formatta_numero(dom)} t/anno |",
            f"| Erogazione media giornaliera | {formatta_numero(kg_giorno)} kg/giorno |",
            f"| Equivalente in autobus urbani alimentabili | {formatta_numero(bus_eq)} mezzi |",
            f"| Gasolio sostituito | {formatta_numero(litri)} litri/anno |",
            f"| Emissioni evitate al netto della produzione | {formatta_numero(co2)} tCO2/anno |", ""]

    if quota_rfnbo is None:
        out.append("> **Le emissioni evitate sono calcolate nell'ipotesi peggiore**, cioè "
                   "idrogeno prodotto con elettricità di rete non certificata: in quel caso "
                   f"ogni chilogrammo ne costa {formatta_numero(emissioni_h2(None))} di CO2, "
                   "più dell'idrogeno da metano. Il percorso B, se sviluppato, restituisce "
                   "la quota effettivamente conforme ai criteri RFNBO e il bilancio va "
                   "ricalcolato su quella.")
        out.append("")
    elif quota_rfnbo < 100:
        out.append(f"> Il calcolo tiene conto che solo il {formatta_numero(quota_rfnbo)}% "
                   "dell'idrogeno risulta conforme ai criteri RFNBO: la parte restante viene "
                   "prodotta con elettricità di rete e porta con sé "
                   f"{formatta_numero(FATTORE_RETE_KG_CO2_KWH * CONSUMO_ELETTROLISI_KWH_KG)} "
                   "kg di CO2 per kg di idrogeno.")
        out.append("")

    if co2_unit <= 0:
        out.append("**La sostituzione peggiora il bilancio delle emissioni.** Con l'idrogeno "
                   "prodotto nelle condizioni ipotizzate, ogni chilogrammo emette più CO2 "
                   "del gasolio che sostituisce. Non è un difetto della tecnologia ma della "
                   "sua alimentazione: finché l'elettrolisi non è certificata rinnovabile, "
                   "la conversione non produce alcun beneficio climatico.")
        out.append("")

    # --- massa critica
    out.append("#### Massa critica")
    if dom >= SOGLIA_MASSA_CRITICA_TON:
        out.append(f"Il volume supera le {formatta_numero(SOGLIA_MASSA_CRITICA_TON)} t/anno "
                   "assunte come soglia di sostenibilità economica per un progetto di "
                   "conversione autonomo, corrispondenti a una flotta di una decina di mezzi "
                   "pesanti in servizio continuo. **La domanda locale è di per sé "
                   "sufficiente** a giustificare un'infrastruttura dedicata: la questione "
                   "diventa la sua contrattualizzazione, non la sua esistenza.")
    elif dom >= SOGLIA_DOMANDA_MINIMA_TON:
        out.append(f"Il volume si colloca fra le {formatta_numero(SOGLIA_DOMANDA_MINIMA_TON)} "
                   f"e le {formatta_numero(SOGLIA_MASSA_CRITICA_TON)} t/anno: **una fascia "
                   "intermedia**, in cui un progetto autonomo resta fragile ma l'aggregazione "
                   "con utenze di Comuni limitrofi, o con il traffico di transito, può "
                   "portare rapidamente il bacino sopra la soglia di sostenibilità. È la "
                   "situazione in cui la cooperazione sovracomunale produce il maggior "
                   "beneficio marginale.")
    else:
        out.append(f"Il volume resta sotto le {formatta_numero(SOGLIA_DOMANDA_MINIMA_TON)} "
                   "t/anno: **la domanda locale non basta** a sostenere una filiera "
                   "dedicata. Questo non esclude l'idrogeno dal futuro del Comune, ma sposta "
                   "il baricentro dell'azione: nel breve periodo conviene puntare su una "
                   "fornitura esterna per usi dimostrativi, e nel medio periodo lavorare "
                   "sull'aggregazione della domanda a scala d'ambito.")
    out.append("")
    out.append("> Equivalenze calcolate con i parametri di riferimento nazionali: "
               f"{formatta_numero(CONSUMO_BUS_KG_GIORNO)} kg/giorno per autobus urbano, "
               f"{formatta_numero(EFFICIENZA_H2_KM_KG)} km/kg per il mezzo pesante a "
               f"idrogeno contro {formatta_numero(EFFICIENZA_DIESEL_KM_LITRO)} km/litro per "
               "il corrispondente diesel.")

    return "\n".join(out)


def commento_percorso(riga, codice: str) -> str:
    """Lettura del singolo percorso, prima delle tabelle."""
    if codice == "A":
        return testo_percorso_a(riga)

    if codice == "B":
        parti = [testo_da_template("B00-percorso_intro_it.md", {},
                                   TESTO_PERCORSO_B_INTRO),
                 sezione_aree(riga), sezione_produzione(riga)]
        return "\n\n".join(p for p in parti if p)

    if codice == "C":
        tgm = numero(riga.get("T27_TGM_CAMION"))
        cap = numero(riga.get("T28_CAPACITA_KG_GIORNO"))
        parti = []
        if tgm:
            parti.append(f"Il traffico pesante rilevato è di **{formatta_numero(tgm)} "
                         "mezzi al giorno**.")
        if cap:
            parti.append(f"La stazione ipotizzata erogherebbe {formatta_numero(cap)} kg "
                         "al giorno.")
        return " ".join(parti)
    return ""


def testo_passo3(riga, livello, profilo) -> str:
    dedicato = f"5-incrocio_{livello}_{profilo}_it.md"
    if os.path.exists(dedicato):
        return leggi_md(dedicato)

    out = ["# Analisi incrociata",
           "Il confronto fra i risultati dei tre percorsi verifica la coerenza interna "
           "dello scenario e individua i punti su cui concentrare le decisioni.", ""]

    domanda = totale(riga, ["T21_FABBISOGNO_H2_TON_ANNO", "T22_FABBISOGNO_H2_TON_ANNO"])
    offerta = numero(riga.get("T26_PRODUZIONE_H2_TON_ANNO"))
    hrs_kg = numero(riga.get("T28_CAPACITA_KG_GIORNO"))
    hrs_t = hrs_kg * 365 / 1000 if hrs_kg else None

    if domanda is not None or offerta is not None:
        out.append("## Bilancio fra domanda e offerta")
        out += ["| Voce | Valore |", "| --- | --- |"]
        if domanda is not None:
            out.append(f"| Domanda complessiva stimata | {formatta_numero(domanda)} t/anno |")
        if offerta is not None:
            out.append(f"| Produzione locale potenziale | {formatta_numero(offerta)} t/anno |")
        if hrs_t is not None:
            out.append(f"| Capacità della stazione di rifornimento | {formatta_numero(hrs_t)} t/anno |")
        if domanda and offerta:
            out.append(f"| Saldo | {formatta_numero(offerta - domanda)} t/anno |")
            out.append(f"| Copertura della domanda | {formatta_numero(offerta / domanda * 100)}% |")
        out.append("")

        if domanda and offerta:
            cop = offerta / domanda * 100
            if cop >= 110:
                out.append("La produzione potenziale **eccede la domanda locale**. Il surplus "
                           "può alimentare utenze di Comuni limitrofi o il traffico di "
                           "transito, ma prima di dimensionare l'impianto sul massimo teorico "
                           "occorre verificare l'esistenza di contratti di acquisto.")
            elif cop >= 80:
                out.append("Domanda e produzione potenziale sono **sostanzialmente in "
                           "equilibrio**: è la condizione più favorevole per un progetto "
                           "autoconsistente su scala comunale.")
            else:
                out.append("La produzione locale **non copre la domanda stimata**. Vanno "
                           "valutate l'estensione del bacino di approvvigionamento, "
                           "l'aggregazione con Comuni vicini o una fornitura esterna nella "
                           "prima fase.")
            out.append("")

    lcoh = numero(riga.get("T26_LCOH_EURO_KG"))
    breakeven = numero(riga.get("T28_BREAK_EVEN_EURO_KG"))
    if lcoh is not None and breakeven is not None:
        out.append("## Coerenza economica della filiera")
        out += ["| Voce | Valore |", "| --- | --- |",
                f"| Costo di produzione (LCOH) | Euro {formatta_numero(lcoh)}/kg |",
                f"| Prezzo di pareggio alla pompa | Euro {formatta_numero(breakeven)}/kg |",
                f"| Margine lordo teorico | Euro {formatta_numero(breakeven - lcoh)}/kg |", ""]
        if breakeven > lcoh:
            out.append("Il prezzo di pareggio della stazione resta sopra il costo di "
                       "produzione: la filiera locale regge sul piano economico, a "
                       "condizione che i volumi previsti si realizzino.")
        else:
            out.append("Il costo di produzione supera il prezzo di pareggio: senza "
                       "contributo in conto capitale o senza un aumento dei volumi la "
                       "configurazione non è sostenibile.")
        out.append("")

    vincoli = []
    contestato = contestazioni(riga)
    if contestato:
        vincoli.append(f"Sul territorio risultano contestazioni riferite a: "
                       f"{contestato}. Il percorso partecipativo va avviato prima "
                       "della progettazione, non dopo.")
    cap_rete = numero(riga.get("T25_CAPACITA_RESIDUA_MW"))
    taglia = numero(riga.get("T26_TAGLIA_ELETTROLIZZATORE_MW"))
    if cap_rete is not None and taglia is not None and taglia > cap_rete:
        vincoli.append(f"La taglia dell'elettrolizzatore ({formatta_numero(taglia)} MW) supera "
                       f"la capacità residua di rete ({formatta_numero(cap_rete)} MW): serve un "
                       "confronto preventivo con il distributore.")
    sau = numero(riga.get("T25_SAU_OCCUPATA_PERC"))
    if sau is not None and sau > 10:
        vincoli.append(f"La superficie agricola già occupata da impianti "
                       f"({formatta_numero(sau)}%) suggerisce di privilegiare coperture e aree "
                       "dismesse rispetto al fotovoltaico a terra.")
    if vincoli:
        out.append("## Vincoli e attenzioni")
        out += [f"- {v}" for v in vincoli] + [""]

    gov = [(etichetta(c), formatta(riga[c], c)) for c in FLAG_GOVERNANCE
           if c in riga.index and formatta(riga[c], c)]
    if gov:
        out.append("## Contesto di governance")
        out += ["| Elemento | Stato |", "| --- | --- |"]
        out += [f"| {e} | {v} |" for e, v in gov] + [""]

    priorita = {
        "L1": "consolidare le basi conoscitive e amministrative prima di impegnare capitale",
        "L2": "trasformare gli studi disponibili in progetti cantierabili e finanziabili",
        "L3": "passare alla realizzazione e all'aggregazione della domanda su scala sovracomunale",
    }
    out += ["## Lettura d'insieme",
            f"Con un livello di maturità **{livello}** e un profilo "
            f"**{profilo or 'non determinato'}**, la priorità operativa è "
            f"{priorita.get(livello, priorita['L1'])}."]
    return "\n".join(out)


def testo_passo4(riga, livello, profilo) -> str:
    dedicato = f"6-finale_{livello}_{profilo}_it.md"
    if os.path.exists(dedicato):
        return leggi_md(dedicato)

    base = {
        "L1": [("0-6 mesi", "Nomina di un referente interno per la transizione energetica"),
               ("6-12 mesi", "Completamento del bilancio energetico comunale"),
               ("12-24 mesi", "Inserimento dell'idrogeno negli strumenti di pianificazione"),
               ("24-36 mesi", "Studio di prefattibilità sul primo caso d'uso")],
        "L2": [("0-6 mesi", "Selezione del caso d'uso prioritario e perimetro tecnico"),
               ("6-12 mesi", "Studio di fattibilità tecnico-economica"),
               ("12-24 mesi", "Individuazione dell'area e avvio dell'iter autorizzativo"),
               ("24-36 mesi", "Candidatura a bandi regionali, nazionali o europei")],
        "L3": [("0-6 mesi", "Definizione del modello di business e della governance"),
               ("6-12 mesi", "Progettazione definitiva e chiusura del piano finanziario"),
               ("12-24 mesi", "Gara e affidamento, anche in forma aggregata"),
               ("24-36 mesi", "Realizzazione, messa in esercizio e monitoraggio")],
    }
    specifiche = {
        "A": "Aggregare la domanda dei soggetti individuati in un contratto di acquisto "
             "pluriennale, condizione per rendere bancabile qualunque impianto.",
        "B": "Mettere in sicurezza la disponibilità delle aree e la connessione di rete "
             "prima di procedere con la progettazione dell'elettrolizzatore.",
        "C": "Verificare con il gestore stradale e con gli operatori del trasporto pesante "
             "i volumi effettivamente intercettabili dalla stazione di rifornimento.",
    }

    out = ["# Roadmap operativa su misura",
           f"Percorso proposto per il Comune di **{riga[COL_NOME]}** "
           f"(livello {livello}, profilo {profilo or 'n.d.'}).", "",
           "## Cronoprogramma indicativo",
           "| Orizzonte | Azione |", "| --- | --- |"]
    out += [f"| {t} | {a} |" for t, a in base.get(livello, base["L1"])] + [""]

    if profilo:
        out.append("## Azioni specifiche del profilo")
        out += [f"- **Vocazione {l}**: {specifiche[l]}" for l in profilo if l in specifiche]
        out.append("")

    out += ["## Fattori abilitanti",
            "- **Competenze**: formazione del personale tecnico nel programma H2READY.",
            "- **Risorse**: capacità di cofinanziamento e ricorso alla finanza agevolata.",
            "- **Partenariato**: utility, trasporto pubblico locale, imprese del territorio.",
            "",
            "## Indicatori di monitoraggio",
            "| Indicatore | Unità |", "| --- | --- |",
            "| Idrogeno consumato sul territorio | t/anno |",
            "| Emissioni evitate | tCO2/anno |",
            "| Quota rinnovabile dell'idrogeno impiegato | % |",
            "| Investimento attivato | Euro |",
            "",
            "> Il presente Action Plan è un documento vivo: va aggiornato a ogni variazione "
            "rilevante del quadro normativo, tecnologico o finanziario."]
    return "\n".join(out)


def costruisci_contenuti(riga, livello, profilo, punteggi) -> dict:
    profilo_file = f"4-profilo_{profilo}_it.md" if profilo else ""
    return {
        "livello": livello,
        "profilo": profilo,
        "comune": str(riga[COL_NOME]),
        "intro": leggi_md("1-intro_it.md"),
        "struttura": leggi_md("2-struttura_plan_it.md"),
        "mat_intro": leggi_md("3-maturita_intro_it.md"),
        "mat_dettaglio": leggi_md(f"3-maturita_{livello}_it.md"),
        "profilo_intro": leggi_md("4-profilo_intro_it.md"),
        "profilo_calcolato": testo_profilo(profilo, punteggi),
        "profilo_dettaglio": leggi_md(profilo_file) if profilo else "",
        "passo2": testo_passo2(riga),
        "passo3": testo_passo3(riga, livello, profilo),
        "passo4": testo_passo4(riga, livello, profilo),
    }


def file_attesi(livello, profilo):
    attesi = ["1-intro_it.md", "2-struttura_plan_it.md", "3-maturita_intro_it.md",
              f"3-maturita_{livello}_it.md", "4-profilo_intro_it.md",
              "5-percorsi_intro_it.md"]
    if profilo:
        attesi.append(f"4-profilo_{profilo}_it.md")
    return attesi
