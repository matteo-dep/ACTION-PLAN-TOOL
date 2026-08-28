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
        ],
    },
]

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
           "T26_LCOH_EURO_KG", "T26_PAYBACK_ANNI", "T26B_SUP_TERRA_HA",
           "T27_TGM_CAMION", "T27_DISTANZA_SNAM_KM", "T27_SCORE_C1", "T27_SCORE_C2",
           "T27_SCORE_C3", "T27_SCORE_GOV", "T27_FLAG_AREE_700BAR",
           "T27_FLAG_AFIR_GAP", "T27_FLAG_HUB_MERCI", "T27_FLAG_SINERGIA_HTA",
           "T27_FLAG_ACCORDI_FILIERA", "T27_FLAG_PUMS",
           "T28_CAPACITA_KG_GIORNO", "T28_TAGLIA_HRS", "T28_STRATEGIA_SUPPLY",
           "T28_POTENZA_COMPRESSORE_KW", "T28_AREA_MINIMA_MQ",
           "T28_CAPEX_COMPLESSIVO_EURO", "T28_BREAK_EVEN_EURO_KG",
           "T28_CONFIGURAZIONE", "T28_N_DISPENSER", "T28_ORIZZONTE",
           "T28_QUOTA_FCEV_PERC"}

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
# PARAMETRI DEL PERCORSO C
# =============================================================================

# Traffico pesante giornaliero sul nodo. Le soglie servono a distinguere una
# direttrice di attraversamento da una viabilità locale.
TGM_DIRETTRICE = 1000.0       # oltre: nodo di transito vero e proprio
TGM_MINIMO = 200.0            # sotto: il traffico non regge da solo una stazione

# Taglia minima prevista dal regolamento AFIR per le stazioni della rete TEN-T.
CAPACITA_AFIR_KG_GIORNO = 1000.0
DISTANZA_AFIR_KM = 200.0

# Prezzo alla pompa. Il riferimento non è il gasolio ma ciò che un operatore di
# trasporto accetta di pagare a parità di costo chilometrico: con un mezzo a
# celle a combustibile che percorre circa 11,4 km/kg contro 3,5 km/litro del
# diesel, un chilogrammo di idrogeno vale poco più di tre litri di gasolio.
PREZZO_POMPA_SOSTENIBILE = 9.0    # sotto: competitivo con il diesel odierno
PREZZO_POMPA_CRITICO = 14.0       # sopra: fuori mercato senza obblighi normativi


# Punteggi massimi delle quattro dimensioni del questionario 2.7. Servono a
# leggere ogni punteggio come quota del proprio massimo: i valori assoluti non
# sono confrontabili fra loro, perché le scale hanno ampiezze diverse.
SCORE_MAX_C = {"T27_SCORE_C1": 17.0,    # flussi di traffico
               "T27_SCORE_C2": 18.0,    # infrastrutture di supporto
               "T27_SCORE_C3": 11.0,    # contesto territoriale
               "T27_SCORE_GOV": 20.0}   # governance e pianificazione

# Soglie di lettura, espresse in quota del massimo.
QUOTA_SCORE_FORTE = 0.65
QUOTA_SCORE_DEBOLE = 0.35

# Area minima di un lotto per una stazione, dal DM 23/10/2018.
AREA_HRS_ATTENZIONE_MQ = 5000.0

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



TESTO_PERCORSO_C_INTRO = """## Percorso C - Il transito e la logistica

I primi due percorsi guardano dentro i confini comunali: chi consuma, chi può
produrre. Il terzo guarda a chi passa.

Un nodo logistico non deve avere né industrie energivore né grandi superfici per
avere un ruolo nella filiera dell'idrogeno: gli basta trovarsi lungo una direttrice
percorsa da mezzi pesanti che, per obbligo normativo, dovranno rifornirsi da
qualche parte. È una domanda che non appartiene al territorio ma lo attraversa, e
che si cattura soltanto se c'è una stazione dove fermarsi.

La differenza rispetto ai percorsi precedenti è sostanziale. La domanda locale si
conosce, si contratta e si pianifica; quella di transito si stima, dipende da come
altri costruiscono la propria rete e va contesa. Il regolamento europeo **AFIR**
impone una stazione di rifornimento a idrogeno ogni duecento chilometri lungo la
rete centrale TEN-T entro il 2030: chi si colloca in un vuoto di quella maglia ha
un vantaggio che nessun altro fattore locale può replicare, ma è un vantaggio che
si esaurisce nel momento in cui qualcun altro lo colma per primo.

L'analisi procede in due passaggi: la valutazione della vocazione del nodo, e il
dimensionamento della stazione che quella vocazione giustificherebbe.
"""

TESTO_TRANSITO_PREDEFINITO = """### Vocazione al transito (Tool 2.7)

La posizione di un Comune lungo le direttrici di traffico non è un dato che
l'amministrazione può modificare: è una condizione data, che si sfrutta o si
ignora. Quello che l'amministrazione può fare è riconoscerla per tempo e
predisporre gli strumenti urbanistici perché, quando un operatore cercherà un sito,
il territorio sia pronto e non debba avviare una variante.
"""



def _verifica_potenziale(riga) -> str:
    """Confronta lo screening del 1.2 con la verifica di merito del 2.7.

    I due questionari rispondono a domande diverse: il 1.2 stima un potenziale
    sulla base di caratteristiche generali del territorio, il 2.7 verifica se
    quel potenziale regga l'esame dei dati puntuali. Il secondo può smentire il
    primo, ed è esattamente ciò che deve poter fare: uno screening che nessuna
    verifica successiva possa contraddire non è uno screening.
    """
    punteggio_12 = numero(riga.get("T12_SCORE_C"))
    tgm = numero(riga.get("T27_TGM_CAMION"))
    if punteggio_12 is None:
        return ""

    # elementi oggettivi rilevati dal 2.7, non punteggi
    conferme, smentite = [], []

    if tgm is not None:
        if tgm >= TGM_DIRETTRICE:
            conferme.append(f"il traffico rilevato ({formatta_numero(tgm)} mezzi pesanti al "
                            "giorno) colloca il nodo su una direttrice di attraversamento")
        elif tgm < TGM_MINIMO:
            smentite.append(f"il traffico effettivamente rilevato è di "
                            f"{formatta_numero(tgm)} mezzi pesanti al giorno, sotto la "
                            "soglia che sostiene una stazione di rifornimento")

    if vero(riga.get("T27_FLAG_AFIR_GAP")):
        conferme.append("il sito colma un vuoto della rete AFIR, quindi la domanda è "
                        "sostenuta da un obbligo normativo e non solo dal mercato")
    if vero(riga.get("T27_FLAG_HUB_MERCI")):
        conferme.append("la presenza di hub merci entro cinque chilometri rende la domanda "
                        "concentrata e contrattualizzabile")
    if vero(riga.get("T27_FLAG_SINERGIA_HTA")):
        conferme.append("la contiguità con un distretto Hard-to-Abate consente di "
                        "condividere produzione e stoccaggio con l'utenza industriale")

    if not is_vuoto(riga.get("T27_FLAG_AREE_700BAR")) and not vero(riga.get("T27_FLAG_AREE_700BAR")):
        smentite.append("il piano regolatore non individua aree compatibili con lo "
                        "stoccaggio ad alta pressione, e senza quelle nessun progetto "
                        "arriva in fondo all'iter autorizzativo")

    if not conferme and not smentite:
        return ""

    out = ["#### Verifica del potenziale stimato", "",
           f"Il questionario 1.2 ha attribuito al percorso C un punteggio di "
           f"{formatta_numero(punteggio_12)}, sufficiente ad aprirlo. Quel punteggio "
           "misura però un potenziale, stimato su caratteristiche generali del "
           "territorio; il questionario 2.7 verifica se quel potenziale regga l'esame "
           "dei dati puntuali, e può contraddirlo.", ""]

    if conferme:
        out.append("**La verifica conferma il potenziale** per le seguenti ragioni:")
        out += [f"- {c}" for c in conferme]
        out.append("")
    if smentite:
        out.append("**La verifica solleva però questi rilievi:**")
        out += [f"- {s}" for s in smentite]
        out.append("")

    if smentite and not conferme:
        out.append("Nessun elemento rilevato dal 2.7 sostiene il potenziale stimato in fase "
                   "di screening. **Il percorso C va considerato chiuso**, nonostante il "
                   "punteggio iniziale: proseguire significherebbe dimensionare "
                   "un'infrastruttura su una domanda che i dati non confermano. Le risorse "
                   "vanno indirizzate sugli altri percorsi.")
    elif smentite and conferme:
        out.append("Il quadro è misto: esistono ragioni fondate per proseguire, ma anche "
                   "ostacoli che vanno rimossi prima di impegnare risorse. Nessuno dei "
                   "rilievi è insuperabile, tutti richiedono però un'azione preventiva "
                   "dell'amministrazione, che è precisamente ciò che il piano d'azione "
                   "deve programmare.")
    else:
        out.append("La verifica di merito conferma quanto stimato in fase di screening: il "
                   "percorso può procedere al dimensionamento senza riserve preliminari.")
    out.append("")
    return "\n".join(out)


def sezione_transito(riga) -> str:
    """Sezione 2.7: vocazione logistica del nodo."""
    tgm = numero(riga.get("T27_TGM_CAMION"))
    snam = numero(riga.get("T27_DISTANZA_SNAM_KM"))
    scores = {c: numero(riga.get(c)) for c in
              ("T27_SCORE_C1", "T27_SCORE_C2", "T27_SCORE_C3", "T27_SCORE_GOV")}
    if tgm is None and all(v is None for v in scores.values()):
        return ""

    out = [testo_da_template("C27-transito_intro_it.md", {},
                             TESTO_TRANSITO_PREDEFINITO), ""]

    verifica = _verifica_potenziale(riga)
    if verifica:
        out += [verifica, ""]

    # --- flussi
    if tgm is not None:
        annui = tgm * 365
        out.append("#### Flussi di traffico")
        out += ["| Parametro | Valore |", "| --- | --- |",
                f"| Traffico giornaliero medio di mezzi pesanti | {formatta_numero(tgm)} mezzi/giorno |",
                f"| Transiti annui | {formatta_numero(annui)} mezzi/anno |"]
        if snam is not None:
            out.append(f"| Distanza dalla dorsale di trasporto | {formatta_numero(snam)} km |")
        out.append("")

        if tgm >= TGM_DIRETTRICE:
            out.append(f"Con {formatta_numero(tgm)} mezzi pesanti al giorno il nodo si "
                       "colloca su una **direttrice di attraversamento**, non su viabilità "
                       "locale. È il presupposto perché una stazione di rifornimento abbia "
                       "senso: il volume c'è, e la questione diventa quanta parte di quel "
                       "flusso si riesce effettivamente a intercettare.")
        elif tgm >= TGM_MINIMO:
            out.append(f"I {formatta_numero(tgm)} mezzi al giorno collocano il nodo in una "
                       "**fascia intermedia**. Il traffico da solo non basta a giustificare "
                       "una stazione, ma può concorrere insieme ad altre componenti: una "
                       "flotta locale, un'utenza industriale, un hub logistico. La "
                       "stazione, se si farà, non sarà di puro transito.")
        else:
            out.append(f"Con {formatta_numero(tgm)} mezzi al giorno **il traffico non "
                       "sostiene una stazione di rifornimento**. Non è un limite del "
                       "territorio ma una sua caratteristica: la vocazione al transito "
                       "richiede volumi che qui non ci sono, e le risorse rendono di più "
                       "sugli altri due percorsi.")
        out.append("")

    # --- fattori qualificanti
    fattori = [
        ("T27_FLAG_AFIR_GAP", "Colma un vuoto della rete AFIR",
         "È il fattore singolo più rilevante di questa sezione. Il regolamento "
         f"europeo impone una stazione ogni {formatta_numero(DISTANZA_AFIR_KM)} km "
         "lungo la rete centrale TEN-T entro il 2030: dove quella maglia ha un "
         "vuoto, la domanda non dipende dalle scelte commerciali degli operatori "
         "ma da un obbligo di legge. È anche la condizione che rende accessibili i "
         "canali di finanziamento europei dedicati alle infrastrutture di "
         "rifornimento."),
        ("T27_FLAG_HUB_MERCI", "Hub merci o interporti entro 5 km",
         "Cambia la natura della domanda: i mezzi che fanno capo a un interporto "
         "rientrano in deposito con regolarità, quindi la quota catturabile è molto "
         "più alta di quella di un nodo attraversato da traffico occasionale. Una "
         "domanda che rientra è una domanda contrattualizzabile."),
        ("T27_FLAG_SINERGIA_HTA", "Distretto Hard-to-Abate confinante",
         "Apre la possibilità di condividere produzione e stoccaggio con l'utenza "
         "industriale invece di costruirli per la sola stazione. È la "
         "configurazione economicamente più solida, perché ripartisce i costi fissi "
         "su due domande diverse e complementari: l'industria consuma in modo "
         "costante, il transito a picchi."),
        ("T27_FLAG_ACCORDI_FILIERA", "Accordi di filiera già attivi",
         "Indica che gli operatori del territorio si parlano già. È un capitale "
         "relazionale che accorcia i tempi: la parte più lenta di questi progetti "
         "non è la costruzione ma la costruzione del consenso fra chi dovrà usarli."),
        ("T27_FLAG_PUMS", "Idrogeno nella pianificazione della mobilità",
         "Se i corridoi e le aree per il rifornimento sono già negli strumenti "
         "urbanistici, l'iter autorizzativo si accorcia di anni. In caso contrario "
         "è il primo intervento da programmare, perché non costa nulla e va fatto "
         "comunque prima di qualunque investimento."),
    ]
    presenti = [(et, testo) for col, et, testo in fattori
                if col in riga.index and vero(riga[col])]
    assenti = [(et, testo) for col, et, testo in fattori
               if col in riga.index and not is_vuoto(riga[col]) and not vero(riga[col])]

    if presenti:
        out.append("#### Fattori favorevoli rilevati")
        for et, testo in presenti:
            out.append(f"**{et}.** {testo}")
            out.append("")

    if assenti:
        out.append("#### Fattori non presenti")
        out.append("Le condizioni che seguono non ricorrono sul territorio. Non sono "
                   "preclusive, ma la loro assenza va messa in conto quando si valuta "
                   "quanta parte del traffico la stazione riuscirà a catturare.")
        out += [f"- {et}" for et, _ in assenti]
        out.append("")

    # --- punteggi, letti come quota del rispettivo massimo
    out.append(_lettura_punteggi(scores))

    return "\n".join(out).strip()



ETICHETTE_SCORE = {
    "T27_SCORE_C1": "Flussi di traffico",
    "T27_SCORE_C2": "Infrastrutture di supporto",
    "T27_SCORE_C3": "Contesto territoriale",
    "T27_SCORE_GOV": "Governance e pianificazione",
}


def _quota_score(colonna, valore_):
    """Punteggio espresso come quota del massimo della propria scala."""
    massimo = SCORE_MAX_C.get(colonna)
    if not massimo or valore_ is None:
        return None
    return min(max(valore_ / massimo, 0.0), 1.0)


def _lettura_punteggi(scores) -> str:
    """Tabella dei punteggi e loro interpretazione.

    I quattro valori hanno scale di ampiezza diversa (17, 18, 11 e 20): letti in
    valore assoluto sarebbero incomparabili, e un 9 su contesto territoriale
    sembrerebbe uguale a un 9 su governance pur valendo quasi il doppio.
    """
    validi = {k: v for k, v in scores.items() if v is not None}
    if not validi:
        return ""

    out = ["#### Punteggi di valutazione", "",
           "Ogni dimensione è misurata su una scala propria: la colonna della quota "
           "riporta il punteggio come percentuale del massimo ottenibile, ed è quella da "
           "leggere per confrontarle fra loro.", ""]
    out += ["| Dimensione | Punteggio | Quota del massimo |", "| --- | --- | --- |"]
    quote = {}
    for colonna, valore_ in validi.items():
        massimo = SCORE_MAX_C.get(colonna)
        quota = _quota_score(colonna, valore_)
        quote[colonna] = quota
        out.append(f"| {ETICHETTE_SCORE[colonna]} | {formatta_numero(valore_)} su "
                   f"{formatta_numero(massimo)} | {formatta_numero(quota * 100)}% |")
    out.append("")

    # --- lettura d'insieme
    forti = [ETICHETTE_SCORE[k] for k, q in quote.items() if q >= QUOTA_SCORE_FORTE]
    deboli = [ETICHETTE_SCORE[k] for k, q in quote.items() if q <= QUOTA_SCORE_DEBOLE]

    if forti:
        out.append("Le dimensioni che raggiungono almeno i due terzi del punteggio "
                   "ottenibile sono: " + ", ".join(f.lower() for f in forti) + ".")
        out.append("")
    if deboli:
        out.append("Restano sotto un terzo del massimo: " +
                   ", ".join(d.lower() for d in deboli) + ". Su queste dimensioni le "
                   "conclusioni della sezione successiva vanno prese con cautela, perché "
                   "poggiano su condizioni che l'analisi non ha trovato pienamente "
                   "verificate.")
        out.append("")

    # --- confronto fra capacità tecnica e capacità amministrativa
    gov = quote.get("T27_SCORE_GOV")
    tecniche = [q for k, q in quote.items() if k != "T27_SCORE_GOV"]
    if gov is not None and tecniche:
        media_tec = sum(tecniche) / len(tecniche)
        if gov < media_tec - 0.2:
            out.append(f"La governance si ferma al {formatta_numero(gov * 100)}% del "
                       f"massimo, contro il {formatta_numero(media_tec * 100)}% medio "
                       "delle dimensioni tecniche. **Il territorio ha le caratteristiche "
                       "fisiche adatte ma non ancora gli strumenti amministrativi per "
                       "valorizzarle.** È lo scarto più facile da colmare fra quelli "
                       "possibili, perché dipende interamente da decisioni dell'ente e non "
                       "richiede investimenti: inserire l'idrogeno negli strumenti di "
                       "pianificazione e individuare le aree costa tempo, non denaro.")
        elif media_tec < gov - 0.2:
            out.append(f"La governance raggiunge il {formatta_numero(gov * 100)}% del "
                       f"massimo mentre le dimensioni tecniche si fermano al "
                       f"{formatta_numero(media_tec * 100)}%. **L'amministrazione è pronta, "
                       "il territorio meno.** È una capacità che conviene indirizzare sugli "
                       "altri percorsi, dove le condizioni fisiche sono più favorevoli, "
                       "oppure sulla cooperazione con i Comuni limitrofi: la preparazione "
                       "amministrativa è la risorsa più scarsa di questi progetti e "
                       "sprecarla su un nodo debole sarebbe un peccato.")
        else:
            out.append("Capacità tecnica e capacità amministrativa sono allineate: il "
                       "territorio e l'ente procedono allo stesso passo, che è la "
                       "condizione in cui i progetti arrivano in fondo.")
        out.append("")
    return "\n".join(out)


def verifica_coerenza_configurazione(riga) -> str:
    """Controlla che la configurazione scelta nel 2.8 regga i dati del 2.7.

    Il Tool 2.8 propone una configurazione ma l'utente può cambiarla: questo
    controllo verifica che la scelta finale non poggi su una dimensione che il
    questionario ha valutato debole.
    """
    config = str(riga.get("T28_CONFIGURAZIONE") or "").strip().lower()
    if not config:
        return ""

    rilievi = []
    q_flussi = _quota_score("T27_SCORE_C1", numero(riga.get("T27_SCORE_C1")))
    q_infra = _quota_score("T27_SCORE_C2", numero(riga.get("T27_SCORE_C2")))
    q_gov = _quota_score("T27_SCORE_GOV", numero(riga.get("T27_SCORE_GOV")))

    if "transito" in config and q_flussi is not None and q_flussi <= QUOTA_SCORE_DEBOLE:
        rilievi.append(f"La configurazione scelta è di **puro transito**, ma il punteggio "
                       f"sui flussi di traffico raggiunge solo il "
                       f"{formatta_numero(q_flussi * 100)}% del massimo. La stazione "
                       "sarebbe dimensionata su una domanda di attraversamento che il "
                       "questionario non conferma: conviene verificare i dati di traffico "
                       "con il gestore stradale prima di procedere.")

    if ("hub" in config or "intermodale" in config) and q_infra is not None \
            and q_infra <= QUOTA_SCORE_DEBOLE:
        rilievi.append(f"La configurazione **hub intermodale** presuppone un contorno "
                       f"logistico che il punteggio sulle infrastrutture non rileva "
                       f"({formatta_numero(q_infra * 100)}% del massimo). Va verificato "
                       "che gli operatori a cui la stazione si rivolge esistano davvero "
                       "sul territorio.")

    if ("valley" in config or "integrata" in config):
        prod = numero(riga.get("T26_PRODUZIONE_H2_TON_ANNO"))
        hta = vero(riga.get("T27_FLAG_SINERGIA_HTA"))
        if not prod and not hta:
            rilievi.append("La configurazione **valley integrata** presuppone una "
                           "produzione locale o un distretto industriale con cui "
                           "condividere gli impianti: nessuna delle due condizioni risulta "
                           "dai questionari. Senza, la stazione sostiene da sola costi "
                           "dimensionati per essere ripartiti.")

    if q_gov is not None and q_gov <= QUOTA_SCORE_DEBOLE:
        rilievi.append(f"Il punteggio di governance si ferma al "
                       f"{formatta_numero(q_gov * 100)}% del massimo. Qualunque sia la "
                       "configurazione, il primo intervento da programmare è "
                       "l'adeguamento degli strumenti di pianificazione: senza, il "
                       "progetto si arena in fase autorizzativa a prescindere dai suoi "
                       "meriti tecnici.")

    if not rilievi:
        return ""
    out = ["#### Coerenza fra configurazione e dati rilevati", ""]
    out += [f"- {r}" for r in rilievi]
    out.append("")
    return "\n".join(out)


TESTO_HRS_PREDEFINITO = """### Dimensionamento della stazione (Tool 2.8)

Una stazione di rifornimento a idrogeno non è un distributore con un serbatoio
diverso. È un impianto in pressione, con compressori che portano il gas fino a
settecento bar, sistemi di preraffreddamento che lo raffreddano a meno quaranta
gradi prima dell'erogazione, e stoccaggi che devono garantire il rifornimento anche
quando la fornitura si interrompe.

Ne discende che i costi sono in larga parte fissi e indipendenti dai volumi
erogati: la stessa stazione che serve dieci mezzi al giorno ne può servire trenta
con un aumento marginale di spesa. È la ragione per cui il parametro che decide
tutto non è il costo dell'impianto ma la sua saturazione.
"""


def sezione_hrs(riga) -> str:
    """Sezione 2.8: dimensionamento e sostenibilità della stazione."""
    capacita = numero(riga.get("T28_CAPACITA_KG_GIORNO"))
    taglia = riga.get("T28_TAGLIA_HRS")
    config = riga.get("T28_CONFIGURAZIONE")
    supply = riga.get("T28_STRATEGIA_SUPPLY")
    potenza = numero(riga.get("T28_POTENZA_COMPRESSORE_KW"))
    dispenser = numero(riga.get("T28_N_DISPENSER"))
    area = numero(riga.get("T28_AREA_MINIMA_MQ"))
    capex = numero(riga.get("T28_CAPEX_COMPLESSIVO_EURO"))
    breakeven = numero(riga.get("T28_BREAK_EVEN_EURO_KG"))
    orizzonte = riga.get("T28_ORIZZONTE")
    quota_fcev = numero(riga.get("T28_QUOTA_FCEV_PERC"))

    if capacita is None and capex is None:
        return ""

    out = [testo_da_template("C28-hrs_intro_it.md", {}, TESTO_HRS_PREDEFINITO), ""]

    if not is_vuoto(orizzonte) and str(orizzonte).strip().lower() != "attuale":
        testo_quota = (f", con una quota di veicoli a celle a combustibile del "
                       f"{formatta_numero(quota_fcev)}% sul circolante pesante"
                       if quota_fcev else "")
        out.append(f"Il dimensionamento è riferito all'orizzonte **{str(orizzonte).strip()}**"
                   + testo_quota + ".")
        out.append("")

    # --- configurazione
    righe = []
    if not is_vuoto(config):
        righe.append(f"| Configurazione | {str(config).strip()} |")
    if not is_vuoto(taglia):
        righe.append(f"| Taglia | {str(taglia).strip()} |")
    if capacita:
        righe.append(f"| Capacità di erogazione | {formatta_numero(capacita)} kg/giorno |")
        righe.append(f"| Su base annua | {formatta_numero(capacita * 365 / 1000)} t/anno |")
    if dispenser:
        righe.append(f"| Punti di erogazione | {formatta_numero(dispenser)} |")
    if potenza:
        righe.append(f"| Potenza di compressione | {formatta_numero(potenza)} kW |")
    if not is_vuoto(supply):
        righe.append(f"| Approvvigionamento | {str(supply).strip()} |")
    if righe:
        out.append("#### Configurazione della stazione")
        out += ["| Parametro | Valore |", "| --- | --- |"] + righe + [""]

    # --- conformità AFIR
    if capacita:
        if capacita >= CAPACITA_AFIR_KG_GIORNO:
            out.append(f"Con {formatta_numero(capacita)} kg al giorno la stazione **soddisfa "
                       "il requisito di capacità previsto dal regolamento AFIR** per le "
                       "stazioni della rete centrale TEN-T, fissato a una tonnellata "
                       "giornaliera. È la condizione per concorrere ai canali di "
                       "finanziamento europei dedicati e per essere computata nella rete "
                       "obbligatoria.")
        else:
            out.append(f"La capacità di {formatta_numero(capacita)} kg al giorno resta sotto "
                       f"la tonnellata prevista dal regolamento AFIR per la rete centrale "
                       "TEN-T. La stazione può servire una domanda locale, ma non concorre "
                       "alla rete obbligatoria né ai canali di finanziamento a essa "
                       "collegati: è una scelta legittima, purché consapevole.")
        out.append("")

    # --- economia
    if capex is not None or breakeven is not None:
        out.append("#### Sostenibilità economica")
        righe = []
        if capex:
            righe.append(f"| Investimento complessivo | Euro {formatta_numero(capex)} |")
            if capacita:
                per_kg = capex / (capacita * 365)
                righe.append(f"| Investimento per kg erogato all'anno | Euro {formatta_numero(per_kg)} |")
        if breakeven is not None:
            righe.append(f"| Prezzo minimo alla pompa | Euro {formatta_numero(breakeven)}/kg |")
        out += ["| Voce | Valore |", "| --- | --- |"] + righe + [""]

        if breakeven is not None:
            litri = LITRI_DIESEL_PER_KG_H2
            equiv = breakeven / litri
            out.append(f"Un chilogrammo di idrogeno percorre quanto circa "
                       f"{formatta_numero(litri)} litri di gasolio: il prezzo di "
                       f"{formatta_numero(breakeven)} Euro/kg equivale quindi a "
                       f"{formatta_numero(equiv)} Euro per litro equivalente di gasolio.")
            out.append("")
            if breakeven <= PREZZO_POMPA_SOSTENIBILE:
                out.append("È un valore **competitivo**: a queste condizioni un operatore di "
                           "trasporto non paga la conversione più di quanto pagherebbe il "
                           "diesel, e la scelta smette di dipendere dagli incentivi.")
            elif breakeven <= PREZZO_POMPA_CRITICO:
                out.append("È un valore **sostenibile solo per chi ha un obbligo**: le "
                           "imprese soggette a vincoli di decarbonizzazione lo accettano "
                           "perché l'alternativa è una sanzione, gli altri no. La stazione "
                           "regge se la clientela è prevalentemente vincolata, e va "
                           "verificato che lo sia.")
            else:
                out.append("È un valore **fuori mercato**. Nella maggior parte dei casi la "
                           "causa non è il costo dell'impianto ma la sua saturazione: pochi "
                           "mezzi al giorno spalmano i costi fissi su volumi troppo piccoli. "
                           "Prima di rivedere la tecnologia conviene rivedere la domanda, "
                           "cercando utenze aggiuntive o una collocazione diversa.")
            out.append("")

    # --- vincoli fisici e coerenza con il territorio
    verifiche = []
    if area:
        verifiche.append(f"Il decreto ministeriale 23 ottobre 2018 impone distanze di "
                         f"sicurezza che si traducono in un lotto di almeno "
                         f"**{formatta_numero(area)} m²**"
                         + (". È una superficie che in ambito urbano è raramente "
                            "disponibile senza una variante urbanistica: va individuata "
                            "prima di ogni altra cosa."
                            if area >= AREA_HRS_ATTENZIONE_MQ else
                            ", superficie compatibile con un'area di servizio ordinaria."))
    if not is_vuoto(riga.get("T27_FLAG_AREE_700BAR")) and not vero(riga.get("T27_FLAG_AREE_700BAR")):
        verifiche.append("Dal questionario 2.7 non risultano aree a piano regolatore "
                         "compatibili con lo stoccaggio a 700 bar. È il vincolo che più "
                         "spesso blocca questi progetti in fase autorizzativa, e va "
                         "affrontato con l'ufficio urbanistica prima di qualunque "
                         "investimento progettuale.")

    prod_locale = numero(riga.get("T26_PRODUZIONE_H2_TON_ANNO"))
    if prod_locale and capacita:
        annuo = capacita * 365 / 1000
        if prod_locale >= annuo:
            verifiche.append(f"La produzione locale prevista dal percorso B "
                             f"({formatta_numero(prod_locale)} t/anno) copre interamente il "
                             f"fabbisogno della stazione ({formatta_numero(annuo)} t/anno): "
                             "la filiera si chiude sul territorio, senza trasporto della "
                             "molecola e senza dipendenza da fornitori esterni.")
        else:
            verifiche.append(f"La produzione locale ({formatta_numero(prod_locale)} t/anno) "
                             f"copre il {formatta_numero(prod_locale / annuo * 100)}% del "
                             "fabbisogno della stazione: la quota restante va acquistata "
                             "all'esterno, con il costo di trasporto che ne consegue.")

    if verifiche:
        out.append("#### Vincoli e verifiche")
        out += [f"- {v}" for v in verifiche] + [""]

    coerenza = verifica_coerenza_configurazione(riga)
    if coerenza:
        out += [coerenza]

    return "\n".join(out).strip()


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
        parti = [testo_da_template("C00-percorso_intro_it.md", {},
                                   TESTO_PERCORSO_C_INTRO),
                 sezione_transito(riga), sezione_hrs(riga)]
        return "\n\n".join(p for p in parti if p)

    return ""



# =============================================================================
# PASSO 3 - IL PIANO D'AZIONE
# Struttura richiesta dall'Application Form del progetto (WP 2.3):
#   1. valutazione delle infrastrutture attuali e delle lacune
#   2. cronoprogramma con traguardi intermedi
#   3. attività specifiche di competenza comunale
#   4. sostenibilità economica e impatto climatico
# =============================================================================

TESTO_PIANO_INTRO = """## Il piano d'azione

Le sezioni precedenti hanno risposto a tre domande: chi consuma, chi può produrre,
chi transita. Questa risponde alla quarta, che è l'unica che riguarda direttamente
l'amministrazione: che cosa fare, in che ordine e con quali risorse.

Il piano che segue è articolato secondo i quattro elementi che il progetto H2READY
richiede a ciascun Action Plan comunale: la ricognizione delle infrastrutture
esistenti e delle lacune da colmare, il cronoprogramma con i traguardi intermedi,
le attività specifiche di competenza comunale e la valutazione di sostenibilità
economica e climatica.

Non è un elenco di intenti. Ogni azione discende da un dato rilevato nelle sezioni
precedenti, e dove il dato manca l'azione è la sua raccolta.
"""


def _stato_infrastrutture(riga):
    """Ricognizione delle infrastrutture esistenti, per ambito."""
    voci = []

    # produzione
    fer = numero(riga.get("T25_FER_INSTALLATA_MW"))
    progr = numero(riga.get("T25_PROGRAMMABILI_MW"))
    if fer:
        testo = f"{formatta_numero(fer)} MW di rinnovabili in esercizio"
        if progr:
            testo += (f", di cui {formatta_numero(progr)} MW programmabili, "
                      "utilizzabili anche nelle ore senza sole")
        voci.append(("Generazione rinnovabile", testo, "presente"))
    else:
        voci.append(("Generazione rinnovabile",
                     "nessun impianto rilevante censito sul territorio", "lacuna"))

    # rete
    cap = numero(riga.get("T25_CAPACITA_RESIDUA_MW"))
    dist = numero(riga.get("T25_DISTANZA_CABINA_PRIMARIA_KM"))
    if cap is not None:
        testo = f"{formatta_numero(cap)} MW di capacità residua"
        if dist is not None:
            testo += f", a {formatta_numero(dist)} km dalla cabina primaria"
        stato = "presente" if cap >= 1 else "lacuna"
        voci.append(("Rete elettrica", testo, stato))
    else:
        voci.append(("Rete elettrica",
                     "capacità residua non verificata con il distributore", "lacuna"))

    # produzione di idrogeno
    prod = numero(riga.get("T26_PRODUZIONE_H2_TON_ANNO"))
    if prod:
        voci.append(("Produzione di idrogeno",
                     f"nessun impianto esistente; il percorso B ne ipotizza uno da "
                     f"{formatta_numero(prod)} t/anno", "da realizzare"))
    else:
        voci.append(("Produzione di idrogeno",
                     "nessun impianto esistente né dimensionato", "lacuna"))

    # rifornimento
    hrs = numero(riga.get("T28_CAPACITA_KG_GIORNO"))
    if hrs:
        voci.append(("Stazione di rifornimento",
                     f"nessuna stazione esistente; il percorso C ne dimensiona una da "
                     f"{formatta_numero(hrs)} kg/giorno", "da realizzare"))
    else:
        voci.append(("Stazione di rifornimento",
                     "nessuna stazione esistente né dimensionata", "lacuna"))

    # stoccaggio e trasporto
    snam = numero(riga.get("T27_DISTANZA_SNAM_KM"))
    if snam is not None:
        stato = "presente" if snam <= 10 else "lacuna"
        voci.append(("Trasporto della molecola",
                     f"dorsale di trasporto a {formatta_numero(snam)} km; "
                     + ("distanza compatibile con un allacciamento futuro"
                        if snam <= 10 else
                        "distanza che rende improbabile un collegamento diretto nel "
                        "breve periodo"), stato))

    # aree
    area = numero(riga.get("T28_AREA_MINIMA_MQ"))
    if area and not vero(riga.get("T27_FLAG_AREE_700BAR")):
        voci.append(("Aree urbanisticamente compatibili",
                     f"servono almeno {formatta_numero(area)} m² per la stazione, ma il "
                     "piano regolatore non individua aree idonee allo stoccaggio ad alta "
                     "pressione", "lacuna"))

    # competenze e strumenti
    if vero(riga.get("T12_FLAG_PIANIFICAZIONE")):
        voci.append(("Strumenti di pianificazione",
                     "l'idrogeno è già richiamato negli strumenti dell'ente", "presente"))
    else:
        voci.append(("Strumenti di pianificazione",
                     "l'idrogeno non compare negli strumenti di pianificazione "
                     "energetica dell'ente", "lacuna"))

    return voci


def testo_piano(riga, livello, profilo) -> str:
    """Passo 3: il piano d'azione nei quattro elementi richiesti."""
    dedicato = f"6-piano_{livello}_{profilo}_it.md"
    if os.path.exists(dedicato):
        return leggi_md(dedicato)

    out = [testo_da_template("6-piano_intro_it.md", {}, TESTO_PIANO_INTRO), ""]
    out += [_sezione_infrastrutture(riga), ""]
    out += [_sezione_cronoprogramma(riga, livello, profilo), ""]
    out += [_sezione_attivita(riga, profilo), ""]
    out += [_sezione_investimento(riga, livello), ""]
    out += [_sezione_sostenibilita(riga), ""]
    return "\n".join(p for p in out if p).strip()


def _sezione_infrastrutture(riga) -> str:
    """Elemento 1: stato delle infrastrutture e lacune da colmare."""
    voci = _stato_infrastrutture(riga)
    out = ["### Stato delle infrastrutture e lacune da colmare", "",
           "La ricognizione distingue ciò che esiste da ciò che manca. È la base del "
           "cronoprogramma: le lacune diventano azioni, nell'ordine in cui si "
           "condizionano l'una con l'altra.", ""]
    out += ["| Ambito | Situazione rilevata | Stato |", "| --- | --- | --- |"]
    etichette = {"presente": "Presente", "lacuna": "Lacuna",
                 "da realizzare": "Da realizzare"}
    for ambito, testo, stato in voci:
        out.append(f"| {ambito} | {testo} | {etichettatura(etichette[stato])} |")
    out.append("")

    lacune = [a for a, _, s in voci if s == "lacuna"]
    if lacune:
        out.append(f"Le lacune riguardano {len(lacune)} ambiti su {len(voci)}: "
                   + ", ".join(l.lower() for l in lacune) + ".")
        out.append("")
        if "Rete elettrica" in lacune:
            out.append("Fra queste, la verifica della capacità di rete va affrontata per "
                       "prima: è l'unica che può rendere irrealizzabile l'intero progetto "
                       "e non dipende da risorse dell'ente, ma dai tempi del distributore. "
                       "Richiederla costa una lettera.")
        elif "Strumenti di pianificazione" in lacune:
            out.append("Fra queste, l'inserimento dell'idrogeno negli strumenti di "
                       "pianificazione è la sola che non richieda risorse economiche e che "
                       "condizioni tutte le altre: senza, ogni intervento successivo passa "
                       "da una variante.")
        out.append("")
    return "\n".join(out)


def etichettatura(testo):
    """Le celle non interpretano il grassetto: si restituisce il testo semplice."""
    return testo



def _sezione_cronoprogramma(riga, livello, profilo) -> str:
    """Elemento 2: cronoprogramma con traguardi intermedi, per fase della filiera."""
    out = ["### Cronoprogramma di sviluppo", "",
           "Le fasi seguono l'ordine in cui si condizionano: non si dimensiona un "
           "impianto senza conoscere la capacità di rete, non si autorizza senza aree "
           "individuate, non si costruisce senza contratti di acquisto. Ogni traguardo "
           "è la condizione del successivo.", ""]

    # orizzonti derivati dai dati, se ci sono
    avvio_flotta = numero(riga.get("T22_ANNO_AVVIO"))
    completa_flotta = numero(riga.get("T22_ANNO_FLOTTA_CONVERTITA"))
    orizzonte_hrs = riga.get("T28_ORIZZONTE")

    fasi = {
        "L1": [
            ("0-6 mesi", "Impostazione",
             "Nomina del referente interno per la transizione energetica e richiesta "
             "formale al distributore della capacità residua di rete."),
            ("6-12 mesi", "Conoscenza",
             "Completamento del bilancio energetico comunale e del catasto delle flotte, "
             "con le percorrenze reali dei mezzi."),
            ("12-24 mesi", "Pianificazione",
             "Inserimento dell'idrogeno negli strumenti di pianificazione energetica e "
             "individuazione preliminare delle aree idonee."),
            ("24-36 mesi", "Prefattibilità",
             "Studio di prefattibilità sul primo caso d'uso e verifica dell'interesse "
             "degli utilizzatori individuati."),
        ],
        "L2": [
            ("0-6 mesi", "Selezione",
             "Scelta del caso d'uso prioritario e definizione del perimetro tecnico, "
             "con verifica della capacità di rete disponibile."),
            ("6-12 mesi", "Fattibilità",
             "Studio di fattibilità tecnico-economica con analisi degli investimenti e "
             "dei costi di esercizio, e prima manifestazione di interesse degli "
             "utilizzatori."),
            ("12-24 mesi", "Autorizzazioni",
             "Individuazione dell'area, variante urbanistica se necessaria e avvio "
             "dell'iter autorizzativo."),
            ("24-36 mesi", "Finanziamento",
             "Candidatura a bandi regionali, nazionali o europei, con i contratti di "
             "acquisto preliminari come allegato."),
        ],
        "L3": [
            ("0-6 mesi", "Governance",
             "Definizione del modello di business, della forma societaria e degli "
             "impegni reciproci fra i soggetti coinvolti."),
            ("6-12 mesi", "Progettazione",
             "Progettazione definitiva, chiusura del piano finanziario e sottoscrizione "
             "dei contratti di acquisto pluriennali."),
            ("12-24 mesi", "Affidamento",
             "Gara e affidamento, anche in forma aggregata con i Comuni limitrofi."),
            ("24-36 mesi", "Realizzazione",
             "Costruzione, messa in esercizio e avvio del monitoraggio delle prestazioni."),
        ],
    }
    out += ["| Orizzonte | Fase | Traguardo |", "| --- | --- | --- |"]
    for orizzonte, fase, azione in fasi.get(livello, fasi["L1"]):
        out.append(f"| {orizzonte} | {fase} | {azione} |")
    out.append("")

    # --- sviluppo per segmento della filiera
    segmenti = []
    prod = numero(riga.get("T26_PRODUZIONE_H2_TON_ANNO"))
    if prod and "B" in (profilo or ""):
        segmenti.append(("Approvvigionamento",
                         f"Realizzazione dell'impianto di produzione da "
                         f"{formatta_numero(prod)} t/anno. È il segmento con i tempi "
                         "autorizzativi più lunghi e va avviato per primo, anche se "
                         "entrerà in esercizio per ultimo."))
    elif "A" in (profilo or "") or "C" in (profilo or ""):
        segmenti.append(("Approvvigionamento",
                         "In assenza di produzione locale, l'idrogeno va acquistato da "
                         "fornitori esterni. Il primo passo è una manifestazione di "
                         "interesse sul mercato, per conoscere prezzi e condizioni reali "
                         "invece di stimarli."))

    hrs = numero(riga.get("T28_CAPACITA_KG_GIORNO"))
    if hrs:
        segmenti.append(("Distribuzione",
                         f"Stazione di rifornimento da {formatta_numero(hrs)} kg/giorno"
                         + (f", riferita all'orizzonte {str(orizzonte_hrs).strip()}"
                            if not is_vuoto(orizzonte_hrs)
                            and str(orizzonte_hrs).strip().lower() != "attuale" else "")
                         + ". Va realizzata prima dei mezzi che deve servire: un veicolo "
                         "senza rifornimento resta fermo, una stazione senza veicoli "
                         "resta sottoutilizzata ma funziona."))

    stocc = numero(riga.get("T28_AREA_MINIMA_MQ"))
    if stocc:
        segmenti.append(("Stoccaggio",
                         f"Lo stoccaggio è parte della stazione e ne determina l'ingombro: "
                         f"il lotto deve misurare almeno {formatta_numero(stocc)} m². "
                         "L'individuazione dell'area è il primo atto di competenza "
                         "esclusivamente comunale dell'intera filiera."))

    if avvio_flotta and completa_flotta:
        segmenti.append(("Utilizzo finale",
                         f"Conversione della flotta comunale a partire dal "
                         f"{formatta_numero(avvio_flotta)}, seguendo il fine vita dei "
                         f"mezzi, con completamento previsto entro il "
                         f"{formatta_numero(completa_flotta)}. La sostituzione anticipata "
                         "di mezzi ancora efficienti non è né economica né sostenibile."))
    else:
        flotta = numero(riga.get("T22_FABBISOGNO_H2_TON_ANNO"))
        if flotta:
            segmenti.append(("Utilizzo finale",
                             f"Conversione progressiva della flotta comunale, per un "
                             f"fabbisogno a regime di {formatta_numero(flotta)} t/anno. "
                             "Il ritmo va allineato al fine vita dei mezzi."))

    if segmenti:
        out.append("#### Sviluppo per segmento della filiera")
        for nome, testo in segmenti:
            out.append(f"**{nome}.** {testo}")
            out.append("")

    return "\n".join(out)


def _sezione_attivita(riga, profilo) -> str:
    """Elemento 3: attività specifiche di competenza comunale.

    Ogni raccomandazione passa prima da una verifica di elettrificabilità: se la
    batteria o la pompa di calore coprono il fabbisogno, l'idrogeno non va
    raccomandato, e il piano deve dirlo invece di tacerlo.
    """
    out = ["### Attività di competenza comunale", "",
           "Molto di ciò che precede dipende da soggetti terzi: distributori, imprese, "
           "operatori del trasporto. Le attività che seguono no: sono interamente nella "
           "disponibilità dell'amministrazione, e per questo sono quelle da cui conviene "
           "cominciare.", "",
           "Prima di elencarle va però ribadito il criterio che le governa. Un'attività "
           "entra in questo piano **come intervento a idrogeno solo se l'elettrificazione "
           "diretta non è praticabile**. Dove lo è, l'attività resta nel piano ma cambia "
           "natura: diventa un intervento di elettrificazione, che il Comune deve "
           "realizzare comunque e prima. Raccomandare idrogeno dove la batteria arriva "
           "significa spendere di più per ottenere meno, e sottrarre energia rinnovabile "
           "ai settori che non hanno alternative.", ""]

    attivita = []
    bev = riga.get("T22_BEV_FATTIBILE")
    esito = riga.get("T22_ESITO_PREVALENTE")
    n_veicoli = numero(riga.get("T22_N_VEICOLI_ANALIZZATI"))

    # --- flotta comunale: la raccomandazione dipende dall'esito del Tool 2.2
    if not is_vuoto(bev) or not is_vuoto(esito):
        if vero(bev):
            testo = (
                "L'analisi del Tool 2.2 indica che per i mezzi comunali analizzati "
                "**l'alternativa a batteria è praticabile**"
                + (f" ({formatta_numero(n_veicoli)} veicoli esaminati)" if n_veicoli else "")
                + ". Non è un esito negativo: è la conferma che il Comune può "
                "decarbonizzare la propria flotta senza attendere alcuna infrastruttura a "
                "idrogeno, con mezzi già disponibili sul mercato e a un costo di esercizio "
                "inferiore.\n\n"
                "Il trasporto scolastico ne è il caso più chiaro. Uno scuolabus percorre "
                "fra gli ottanta e i cento chilometri al giorno, rientra ogni sera in "
                "deposito e resta fermo tutta la notte: sono esattamente le condizioni in "
                "cui la batteria dà il meglio, perché la ricarica lenta notturna costa "
                "poco, non richiede colonnine ad alta potenza e non consuma il pacco. "
                "Convertire quei mezzi a idrogeno costerebbe circa tre volte l'energia e "
                "un investimento superiore, per un servizio identico.\n\n"
                "**L'azione da inserire nel piano è quindi l'elettrificazione del "
                "trasporto scolastico e dei servizi urbani**, con l'installazione di punti "
                "di ricarica al deposito. L'idrogeno resta riservato ai mezzi che il Tool "
                "2.2 ha indicato come non elettrificabili, se ce ne sono.")
        else:
            testo = (
                "L'analisi del Tool 2.2 indica che per i mezzi comunali analizzati "
                "**l'alternativa a batteria non è praticabile**"
                + (f": {str(esito).strip().lower()}" if not is_vuoto(esito) else "")
                + ". È la condizione che rende l'idrogeno una scelta fondata e non una "
                "preferenza, e va documentata negli atti: sarà la motivazione tecnica da "
                "allegare a qualunque richiesta di finanziamento.\n\n"
                "La conversione va programmata sul fine vita dei mezzi, non anticipata. "
                "Rottamare un veicolo ancora efficiente per accelerare la transizione "
                "produce più emissioni di quante ne eviti, perché la costruzione del mezzo "
                "sostitutivo pesa più dei consumi risparmiati nei pochi anni guadagnati.")
        attivita.append(("Flotta comunale e trasporto scolastico", testo))

    # --- edifici pubblici
    termico = numero(riga.get("T24_FABBISOGNO_TERMICO_KWH_ANNO"))
    if termico:
        ottimale = riga.get("T24_SOLUZIONE_OTTIMALE")
        h2_ottimale = "idrogeno" in str(ottimale).strip().lower()
        testo = (f"Il patrimonio edilizio comunale richiede {formatta_numero(termico)} kWh "
                 "termici all'anno. ")
        if h2_ottimale:
            testo += ("Il Tool 2.4 individua l'idrogeno come soluzione ottimale: è un esito "
                      "raro, che va verificato prima di trasformarlo in un'azione. Ricorre "
                      "solo in presenza di condizioni particolari, come edifici vincolati "
                      "in cui non è possibile intervenire sugli impianti di distribuzione.")
        else:
            testo += ("Il Tool 2.4 mostra però che per scuole, uffici e palestre l'idrogeno "
                      "consuma diverse volte l'energia di una pompa di calore a parità di "
                      "calore prodotto. **L'intervento sugli edifici resta nel piano, ma "
                      "come elettrificazione**, non come conversione a idrogeno")
            if not is_vuoto(ottimale):
                testo += f": la soluzione individuata è {str(ottimale).strip().lower()}"
            testo += (". È una precisazione che vale la pena mettere per iscritto, perché "
                      "è la richiesta che più spesso arriva agli uffici tecnici e che più "
                      "spesso va respinta con una motivazione tecnica.\n\n"
                      "Va inoltre ricordato che prima di sostituire il generatore conviene "
                      "ridurre il fabbisogno: l'intervento sull'involucro ha una vita "
                      "utile doppia rispetto a quella di qualunque impianto e riduce la "
                      "taglia della macchina da installare, qualunque essa sia.")
        attivita.append(("Edifici pubblici ad alto fabbisogno", testo))

    # --- usi di nicchia: solo quelli non elettrificabili
    nicchie_attive = [DETTAGLIO_NICCHIE[c]["titolo"] for c in DETTAGLIO_NICCHIE
                      if c in riga.index and vero(riga[c])
                      and c != "T23_FLAG_DEPURATORI"]
    if nicchie_attive:
        attivita.append((
            "Impieghi dimostrativi",
            "Il territorio presenta impieghi in cui l'idrogeno compete su requisiti che "
            "l'elettrificazione non soddisfa — continuità di servizio, assenza di rete, "
            "tempi di rifornimento, prestazioni a basse temperature: "
            + ", ".join(n.lower() for n in nicchie_attive) + ". "
            "Sono volumi contenuti ma ad alta visibilità, e servono a costruire le "
            "competenze tecniche dell'ente prima di affrontare investimenti maggiori. "
            "Anche qui la verifica va rifatta caso per caso al momento della "
            "progettazione: le prestazioni delle batterie migliorano, e un impiego che "
            "oggi non è elettrificabile potrebbe esserlo fra cinque anni."))

    if vero(riga.get("T23_FLAG_DEPURATORI")):
        attivita.append((
            "Depuratore come sito di produzione",
            "Il depuratore comunale non è un consumatore di idrogeno ma un possibile sito "
            "di produzione, ed è l'unico impianto di proprietà pubblica che offra "
            "simultaneamente acqua di processo, un utilizzo diretto dell'ossigeno prodotto "
            "dall'elettrolisi e un impiego per il calore di scarto. È l'attività con il "
            "maggior contenuto di innovazione fra quelle qui elencate, e merita uno studio "
            "di fattibilità dedicato prima di essere inserita in un programma di spesa."))

    # --- urbanistica
    if not vero(riga.get("T27_FLAG_PUMS")) and not is_vuoto(riga.get("T27_FLAG_PUMS")):
        attivita.append((
            "Adeguamento degli strumenti urbanistici",
            "Individuare nelle previsioni di piano le aree compatibili con lo stoccaggio e "
            "il rifornimento di idrogeno. Non comporta spesa, non impegna "
            "l'amministrazione a realizzare nulla, e accorcia di anni l'iter di qualunque "
            "progetto futuro, anche di iniziativa privata. È l'azione con il miglior "
            "rapporto fra costo ed effetto dell'intero piano."))

    # --- aggregazione
    if vero(riga.get("T12_FLAG_JOINT_PROCUREMENT")) or vero(riga.get("T23_FLAG_HYDROGEN_VALLEY")):
        attivita.append((
            "Aggregazione della domanda",
            "Il Comune ha già dichiarato disponibilità ad appalti congiunti o partecipa a "
            "un progetto di Hydrogen Valley. È la leva che trasforma una domanda "
            "insufficiente in una domanda finanziabile: nessun singolo Comune di medie "
            "dimensioni raggiunge da solo la scala che rende sostenibile un impianto, e "
            "quasi tutti la raggiungono insieme ai vicini."))

    if not attivita:
        out.append("Non emergono attività di competenza esclusivamente comunale: le "
                   "informazioni raccolte non sono sufficienti a individuarle. È il segnale "
                   "che i questionari sui consumi e sulle flotte vanno completati prima di "
                   "procedere.")
        return "\n".join(out)

    for titolo, testo in attivita:
        out.append(f"#### {titolo}")
        out.append(testo)
        out.append("")
    return "\n".join(out)



# --- Strumenti di finanziamento noti al momento della stesura -----------------
# Non sostituiscono la verifica dei bandi aperti: servono a indicare dove
# cercare, con quale ordine di priorità e per quale componente.
STRUMENTI_FINANZIAMENTO = [
    ("Produzione",
     "PNRR Hydrogen Valleys e successivi bandi nazionali sulla produzione di idrogeno "
     "rinnovabile; FER X per la componente rinnovabile dell'impianto; Innovation Fund "
     "europeo per le configurazioni di taglia industriale."),
    ("Rifornimento",
     "CEF Transport e AFIF (Alternative Fuels Infrastructure Facility) per le stazioni "
     "sulla rete TEN-T; bandi PNRR dedicati alle stazioni di rifornimento a idrogeno."),
    ("Flotte",
     "Bandi regionali e nazionali per il rinnovo del trasporto pubblico locale, che "
     "coprono in genere il differenziale rispetto al mezzo convenzionale; Conto Termico "
     "e fondi per la mobilità sostenibile per i mezzi di servizio."),
    ("Edifici e efficienza",
     "Conto Termico 3.0 per gli interventi sull'involucro e sui generatori del patrimonio "
     "pubblico; PREPAC per gli immobili della pubblica amministrazione centrale e i "
     "programmi regionali collegati."),
    ("Studi e progettazione",
     "Fondi di assistenza tecnica regionali ed europei, spesso trascurati e invece "
     "decisivi: coprono studi di fattibilità e progettazione, che sono la spesa che un "
     "Comune fatica di più a mettere a bilancio."),
]


def _sezione_investimento(riga, livello) -> str:
    """Piano finanziario: chi paga cosa, con quali strumenti e in quali anni."""
    capex_prod = numero(riga.get("T26_CAPEX_TOTALE_MLN"))
    capex_hrs = numero(riga.get("T28_CAPEX_COMPLESSIVO_EURO"))
    delta_tco = numero(riga.get("T22_DELTA_TCO_EURO"))
    connessioni = numero(riga.get("T26_CAPEX_CONNESSIONI_EURO"))

    out = ["### Piano di investimento", "",
           "Gli importi delle sezioni precedenti sono costi di realizzazione, non impegni "
           "di bilancio del Comune. Questa sezione li ripartisce per soggetto, indica gli "
           "strumenti di finanziamento a cui ciascuna componente può accedere e li "
           "colloca nel tempo.", ""]

    # --- ripartizione per soggetto
    componenti = []
    if capex_prod:
        componenti.append(("Impianto di produzione", capex_prod * 1e6,
                           "Operatore privato o società mista",
                           "Il Comune conferisce aree, autorizzazioni e domanda; "
                           "l'investimento è di norma a carico di un partner industriale."))
    if connessioni:
        componenti.append(("Connessioni elettriche", connessioni,
                           "Titolare dell'impianto",
                           "Costo a carico di chi realizza l'impianto, ma soggetto ai "
                           "tempi del distributore: va verificato prima di ogni impegno."))
    if capex_hrs:
        componenti.append(("Stazione di rifornimento", capex_hrs,
                           "Operatore del settore carburanti",
                           "Raramente realizzata direttamente da un Comune. Il ruolo "
                           "dell'ente è mettere a disposizione l'area e garantire i tempi "
                           "autorizzativi."))
    if delta_tco and delta_tco > 0:
        componenti.append(("Differenziale sulla flotta", delta_tco,
                           "Comune",
                           "È l'unica voce interamente pubblica, e quella su cui si "
                           "concentrano i contributi in conto capitale."))

    if componenti:
        out.append("#### Ripartizione per soggetto")
        out += ["| Componente | Importo | A carico di |", "| --- | --- | --- |"]
        for nome, importo, soggetto, _ in componenti:
            out.append(f"| {nome} | Euro {formatta_numero(importo)} | {soggetto} |")
        out.append("")
        quota_comune = sum(i for n, i, s, _ in componenti if s == "Comune")
        totale = sum(i for _, i, _, _ in componenti)
        if totale:
            out.append(f"Sul totale di Euro {formatta_numero(totale)}, la quota "
                       f"riconducibile direttamente al bilancio comunale è di Euro "
                       f"{formatta_numero(quota_comune)}, pari al "
                       f"{formatta_numero(quota_comune / totale * 100)}%. "
                       "È il numero da portare in Consiglio: il resto misura la dimensione "
                       "del progetto, non l'impegno dell'ente.")
            out.append("")
        for nome, _, _, nota in componenti:
            out.append(f"**{nome}.** {nota}")
            out.append("")

    # --- strumenti di finanziamento
    out.append("#### Strumenti di finanziamento")
    out.append("L'elenco indica dove cercare, non quanto si otterrà: le dotazioni e le "
               "aliquote cambiano a ogni edizione, e vanno verificate al momento della "
               "candidatura.")
    out.append("")
    out += ["| Componente | Strumenti |", "| --- | --- |"]
    out += [f"| {n} | {s} |" for n, s in STRUMENTI_FINANZIAMENTO]
    out.append("")

    if livello == "L1":
        out.append("Al livello di maturità rilevato, la voce più utile della tabella è "
                   "l'ultima. I fondi di assistenza tecnica coprono studi e progettazione, "
                   "che sono la spesa che precede tutte le altre e quella che più spesso "
                   "blocca i progetti prima ancora che comincino.")
    else:
        out.append("La sequenza consigliata è: prima i fondi per studi e progettazione, che "
                   "producono i documenti richiesti dagli altri bandi; poi la candidatura "
                   "sulle infrastrutture, allegando i contratti di acquisto come prova "
                   "della domanda; infine i contributi sulle flotte, che vanno richiesti "
                   "quando il rifornimento è certo e non prima.")
    out.append("")

    # --- scaglionamento
    out.append("#### Scaglionamento della spesa")
    out.append("La spesa non si concentra in un esercizio. La ripartizione indicativa che "
               "segue serve alla programmazione di bilancio pluriennale, ed è la ragione "
               "per cui il cronoprogramma va approvato prima e non dopo il piano "
               "finanziario.")
    out.append("")
    fasi_spesa = [
        ("Primo biennio", "Studi di fattibilità, progettazione preliminare, verifiche di "
                          "rete e adeguamenti urbanistici. È la quota minore in valore ma "
                          "quella che sblocca tutto il resto, e va coperta con risorse "
                          "proprie o con fondi di assistenza tecnica."),
        ("Secondo biennio", "Progettazione definitiva, iter autorizzativi e candidature ai "
                            "bandi. La spesa resta contenuta, ma richiede continuità: un "
                            "iter interrotto va quasi sempre ricominciato."),
        ("Terzo biennio", "Realizzazione delle infrastrutture e primi acquisti di mezzi. È "
                          "qui che si concentra la spesa, ed è qui che i contributi "
                          "ottenuti nella fase precedente devono essere già acquisiti."),
    ]
    out += ["| Periodo | Contenuto |", "| --- | --- |"]
    out += [f"| {p} | {t} |" for p, t in fasi_spesa]
    out.append("")
    out.append("> Gli importi per periodo non sono qui quantificati perché dipendono dalle "
               "scelte progettuali e dall'esito delle candidature. La quantificazione è il "
               "primo prodotto atteso dallo studio di fattibilità, e va inserita in questo "
               "piano al suo aggiornamento.")
    return "\n".join(out)


def _sezione_sostenibilita(riga) -> str:
    """Elemento 4: sostenibilità economica e impatto climatico."""
    out = ["### Sostenibilità economica e impatto climatico", ""]

    capex_prod = numero(riga.get("T26_CAPEX_TOTALE_MLN"))
    capex_hrs = numero(riga.get("T28_CAPEX_COMPLESSIVO_EURO"))
    lcoh = numero(riga.get("T26_LCOH_EURO_KG"))
    payback = numero(riga.get("T26_PAYBACK_ANNI"))
    breakeven = numero(riga.get("T28_BREAK_EVEN_EURO_KG"))
    delta_tco = numero(riga.get("T22_DELTA_TCO_EURO"))

    # --- investimento complessivo
    voci_capex = []
    totale = 0.0
    if capex_prod:
        voci_capex.append(("Impianto di produzione (percorso B)", capex_prod * 1e6))
        totale += capex_prod * 1e6
    if capex_hrs:
        voci_capex.append(("Stazione di rifornimento (percorso C)", capex_hrs))
        totale += capex_hrs
    if delta_tco and delta_tco > 0:
        voci_capex.append(("Differenziale sulla flotta (percorso A)", delta_tco))
        totale += delta_tco

    if voci_capex:
        out.append("#### Investimento complessivo")
        out += ["| Componente | Importo |", "| --- | --- |"]
        out += [f"| {n} | Euro {formatta_numero(v)} |" for n, v in voci_capex]
        if len(voci_capex) > 1:
            out.append(f"| **Totale** | **Euro {formatta_numero(totale)}** |")
        out.append("")
        out.append("Gli importi non sono tutti a carico dell'amministrazione: la produzione "
                   "e la stazione sono investimenti che nella maggior parte dei casi "
                   "vengono realizzati da operatori privati o da società miste, con il "
                   "Comune che conferisce aree, autorizzazioni e domanda garantita. Il "
                   "differenziale sulla flotta è invece interamente pubblico, ed è la voce "
                   "su cui si concentrano i contributi in conto capitale.")
        out.append("")

    # --- costi di esercizio e ritorno
    righe = []
    if lcoh is not None:
        righe.append(f"| Costo di produzione dell'idrogeno | Euro {formatta_numero(lcoh)}/kg |")
    if breakeven is not None:
        righe.append(f"| Prezzo minimo alla pompa | Euro {formatta_numero(breakeven)}/kg |")
    if payback is not None:
        righe.append(f"| Tempo di ritorno dell'impianto di produzione | {formatta_numero(payback)} anni |")
    if righe:
        out.append("#### Ritorno dell'investimento")
        out += ["| Indicatore | Valore |", "| --- | --- |"] + righe + [""]
        if payback is not None:
            if payback <= PAYBACK_ACCETTABILE_ANNI:
                out.append(f"Un ritorno in {formatta_numero(payback)} anni rientra "
                           "nell'orizzonte di un investimento infrastrutturale ordinario "
                           "ed è compatibile con la durata delle concessioni e dei "
                           "contratti di acquisto pluriennali.")
            else:
                out.append(f"Un ritorno in {formatta_numero(payback)} anni eccede "
                           "l'orizzonte che un'amministrazione può assumere da sola. Non "
                           "rende il progetto irrealizzabile, ma ne determina la forma: "
                           "serve un partner industriale che porti capitale e gestione, "
                           "oppure un contributo in conto capitale che riduca la quota da "
                           "ammortizzare.")
            out.append("")

    # --- impatto climatico
    co2_voci = []
    co2_prod = numero(riga.get("T26_CO2_EVITATA_TON_ANNO"))
    co2_flotta = numero(riga.get("T22_EMISSIONI_EVITATE_TCO2"))
    co2_termico = numero(riga.get("T24_EMISSIONI_EVITATE_KGCO2_ANNO"))
    if co2_flotta:
        co2_voci.append(("Conversione della flotta", co2_flotta))
    if co2_termico:
        co2_voci.append(("Interventi sugli edifici pubblici", co2_termico / 1000))
    if co2_prod:
        co2_voci.append(("Produzione locale rinnovabile", co2_prod))

    if co2_voci:
        totale_co2 = sum(v for _, v in co2_voci)
        out.append("#### Impatto sulle emissioni")
        out += ["| Intervento | Emissioni evitate |", "| --- | --- |"]
        out += [f"| {n} | {formatta_numero(v)} tCO2/anno |" for n, v in co2_voci]
        if len(co2_voci) > 1:
            out.append(f"| **Totale** | **{formatta_numero(totale_co2)} tCO2/anno** |")
        out.append("")

        # costo della tonnellata evitata: il metro con cui si confrontano le misure
        if totale and totale_co2 > 0:
            anni = 20
            costo_ton = totale / (totale_co2 * anni)
            out.append(f"Rapportando l'investimento complessivo alle emissioni evitate su "
                       f"un orizzonte di {anni} anni, il costo della tonnellata di CO2 "
                       f"evitata risulta di **Euro {formatta_numero(costo_ton)}**.")
            out.append("")
            if costo_ton <= 100:
                out.append("È un valore che regge il confronto con qualunque altra misura "
                           "di decarbonizzazione: sotto i cento euro a tonnellata "
                           "l'intervento è efficiente in senso assoluto, non solo "
                           "rispetto alle alternative a idrogeno.")
            elif costo_ton <= 500:
                out.append("È un valore nella media degli interventi su settori "
                           "difficili da abbattere. Va confrontato con quanto costerebbe "
                           "evitare la stessa CO2 con altre misure sul territorio: se "
                           "l'efficienza energetica degli edifici o l'elettrificazione "
                           "della mobilità leggera costano meno, quelle vanno fatte prima.")
            else:
                out.append("È un valore alto. Non significa che l'intervento sia sbagliato "
                           "— i settori Hard-to-Abate costano di più proprio perché non "
                           "hanno alternative — ma significa che va motivato con la "
                           "necessità tecnica, non con l'efficienza climatica. Le stesse "
                           "risorse impiegate altrove eviterebbero più emissioni.")
            out.append("")
            out.append("> Il calcolo rapporta l'intero investimento alle emissioni evitate "
                       f"in {anni} anni di esercizio, senza attualizzazione e senza "
                       "considerare i contributi pubblici: è un ordine di grandezza per "
                       "confrontare misure alternative, non un indicatore finanziario.")
            out.append("")

    # --- coerenza con gli obiettivi climatici
    out.append("#### Coerenza con gli obiettivi di lungo periodo")
    obiettivi = ["La **Legge regionale 4/2023** fissa la neutralità climatica del Friuli "
                 "Venezia Giulia al 2045: gli interventi di questo piano vanno "
                 "programmati perché siano in esercizio, non in progetto, entro quella "
                 "data."]
    if vero(riga.get("T12_FLAG_NAHV")):
        obiettivi.append("Il Comune aderisce alla **North Adriatic Hydrogen Valley**, che "
                         "punta a 5.000 tonnellate annue di idrogeno rinnovabile su scala "
                         "transfrontaliera: il fabbisogno locale rilevato va letto come "
                         "quota di quel target, non come progetto isolato.")
    if vero(riga.get("T23_FLAG_HYDROGEN_VALLEY")):
        obiettivi.append("Sul territorio insiste già un progetto di Hydrogen Valley "
                         "finanziato: le azioni di questo piano vanno coordinate con "
                         "quelle, per evitare che due infrastrutture si contendano la "
                         "stessa domanda.")
    obiettivi.append("Il **PNIEC** assegna all'idrogeno rinnovabile un ruolo circoscritto "
                     "ai settori senza alternative: la coerenza con quel quadro non si "
                     "misura dalla quantità di idrogeno impiegata, ma dalla correttezza "
                     "degli impieghi scelti.")
    out += [f"- {o}" for o in obiettivi]
    out.append("")
    out.append("> Il presente Action Plan è un documento vivo: va aggiornato a ogni "
               "variazione rilevante del quadro normativo, tecnologico o finanziario, e "
               "riesaminato comunque prima di ogni candidatura a finanziamento.")
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
        "passo3": testo_piano(riga, livello, profilo),
    }


def file_attesi(livello, profilo):
    attesi = ["1-intro_it.md", "2-struttura_plan_it.md", "3-maturita_intro_it.md",
              f"3-maturita_{livello}_it.md", "4-profilo_intro_it.md",
              "5-percorsi_intro_it.md"]
    if profilo:
        attesi.append(f"4-profilo_{profilo}_it.md")
    return attesi
