"""
H2READY Toolkit - base di conoscenza ATECO.

Associa a ogni codice ATECO il processo produttivo, la temperatura di esercizio,
il ruolo che l'idrogeno può avere e il verdetto termodinamico.

Il verdetto segue la gerarchia H2READY:
  FEEDSTOCK   l'idrogeno è materia prima chimica, l'elettricità non lo sostituisce
  ALTA_TEMP   calore di processo oltre gli 800 °C, elettrificazione difficile
  MARGINALE   temperature medie, l'elettrificazione diretta è quasi sempre migliore
  ELETTRIFICA bassa temperatura, l'idrogeno sarebbe uno spreco di energia primaria

Per aggiungere un settore basta inserire una riga in ATECO: la ricerca avviene
per prefisso, quindi "24.10" copre 24.10.00, 24.10.10 e così via.

`peso` è usato solo per ripartire in modo indicativo un fabbisogno aggregato fra
più aziende quando il dato per singola impresa non è disponibile: è un ordine di
grandezza relativo dell'intensità di idrogeno, non un consumo specifico.
"""

FEEDSTOCK = "Feedstock chimico"
ALTA_TEMP = "Calore ad alta temperatura"
MARGINALE = "Marginale"
ELETTRIFICA = "Elettrificazione diretta"

# -----------------------------------------------------------------------------
# FAMIGLIE PROVENIENTI DAL TOOL 2.1
# Il Tool 2.1 classifica ogni azienda in una "family" tenendo conto sia del codice
# sia della descrizione del processo (per esempio distingue un'acciaieria DRI da
# un forno elettrico ad arco). Quando il foglio riporta quel dato in
# T21_FAMIGLIE_AZIENDE, l'Action Plan lo usa così com'è invece di riclassificare:
# è il 2.1 la fonte di verità, questo modulo resta la rete di sicurezza.
# -----------------------------------------------------------------------------

FAMIGLIE = {
    "feedstock": (FEEDSTOCK,
                  "L'idrogeno entra come materia prima chimica, nella sintesi "
                  "dell'ammoniaca o nell'idrotrattamento di raffineria: serve alla "
                  "reazione, non al calore, e nessuna alternativa elettrica può "
                  "sostituirlo."),
    "dri": (FEEDSTOCK,
            "Nella riduzione diretta del minerale di ferro l'idrogeno sostituisce il "
            "carbonio come agente riducente, lasciando acqua al posto della CO2: è la "
            "via principale per l'acciaio primario a zero emissioni."),
    "glass": (ALTA_TEMP,
              "I forni fusori del vetro lavorano in continuo attorno ai 1.500 °C: oltre "
              "una certa taglia l'elettrificazione totale è limitata dalla durata degli "
              "elettrodi e dalla densità di potenza."),
    "calcination": (MARGINALE,
                    "La calcinazione di cemento, calce e refrattari può usare idrogeno, "
                    "ma compete con biometano e combustibili solidi secondari; inoltre "
                    "gran parte delle emissioni è di processo e non si elimina cambiando "
                    "il solo combustibile."),
    "heattreat": (MARGINALE,
                  "Trattamenti termici e rivestimenti metallici stanno fra i 500 e i "
                  "1.200 °C: forni a induzione o a resistenza sono spesso più efficienti, "
                  "e l'idrogeno si giustifica dove serve un'atmosfera chimica specifica."),
    "borderline": (MARGINALE,
                   "Processo termico a media temperatura in un settore non prioritario: "
                   "va verificato caso per caso, ma di norma l'elettrificazione diretta "
                   "resta preferibile."),
    "cracking": (ELETTRIFICA,
                 "Lo steam cracking genera idrogeno come sottoprodotto: non è un "
                 "fabbisogno da pianificare ed è escluso dalle quote RED III."),
    "smr": (ELETTRIFICA,
            "Lo steam methane reforming produce idrogeno grigio: non è un consumatore da "
            "convertire, ma un impianto da sostituire con l'elettrolisi."),
    "byproduct": (ELETTRIFICA,
                  "Qui l'idrogeno è un sottoprodotto industriale, spesso già recuperato "
                  "in loco e non computabile ai fini delle quote RED III."),
    "energy_waste": (ELETTRIFICA,
                     "Vapore, generazione elettrica, edilizia e data center richiedono "
                     "calore a bassa temperatura o sola elettricità: bruciare idrogeno "
                     "qui è uno spreco termodinamico."),
    "none": (ELETTRIFICA,
             "Codice non prioritario o processo a bassa temperatura facilmente "
             "elettrificabile."),
}


def da_famiglia(famiglia):
    """Traduce la family del Tool 2.1 in (verdetto, descrizione). None se ignota."""
    if not famiglia:
        return None
    return FAMIGLIE.get(str(famiglia).strip().lower())


VERDETTI = {
    FEEDSTOCK: "**Idoneo** - l'idrogeno entra nella reazione chimica: nessuna "
               "alternativa elettrica è possibile.",
    ALTA_TEMP: "**Idoneo** - il calore richiesto supera i limiti pratici "
               "dell'elettrificazione diretta.",
    MARGINALE: "**Da verificare** - le temperature in gioco sono aggredibili anche "
               "per via elettrica: l'idrogeno va giustificato caso per caso.",
    ELETTRIFICA: "**Non prioritario** - il fabbisogno termico è a bassa temperatura, "
                 "dove pompe di calore e resistenze sono nettamente più efficienti.",
}

# (prefisso ATECO, settore, descrizione del processo, temperatura, categoria, peso)
ATECO = [
    # --- Siderurgia e metallurgia
    ("24.10", "Siderurgia primaria",
     "riduzione del minerale di ferro; l'idrogeno sostituisce il carbone come agente "
     "riducente nel processo DRI",
     "1.100-1.500 °C", FEEDSTOCK, 5.0),
    ("24.20", "Tubi e profilati in acciaio",
     "riscaldo dei semilavorati e trattamenti termici in forno",
     "900-1.250 °C", ALTA_TEMP, 2.0),
    ("24.3", "Prima trasformazione dell'acciaio",
     "ricottura e zincatura a caldo, con forni a fiamma diretta",
     "700-1.100 °C", ALTA_TEMP, 1.5),
    ("24.42", "Produzione di alluminio",
     "fusione e mantenimento del bagno metallico",
     "700-960 °C", ALTA_TEMP, 2.0),
    ("24.4", "Metallurgia dei metalli non ferrosi",
     "fusione e affinazione di rame, piombo, zinco e leghe",
     "700-1.200 °C", ALTA_TEMP, 2.0),
    ("24.5", "Fonderie",
     "fusione di ghisa, acciaio o leghe leggere in forno",
     "700-1.500 °C", ALTA_TEMP, 2.0),

    # --- Chimica e raffinazione
    ("19.20", "Raffinazione del petrolio",
     "idrotrattamento e desolforazione, dove l'idrogeno è reagente di processo",
     "300-400 °C", FEEDSTOCK, 5.0),
    ("20.11", "Gas industriali",
     "produzione e liquefazione di gas tecnici, fra cui l'idrogeno stesso",
     "processo", FEEDSTOCK, 4.0),
    ("20.15", "Fertilizzanti e composti azotati",
     "sintesi dell'ammoniaca: l'idrogeno è il reagente principale del processo "
     "Haber-Bosch",
     "400-500 °C", FEEDSTOCK, 5.0),
    ("20.14", "Chimica organica di base",
     "sintesi di metanolo e intermedi organici a partire da gas di sintesi",
     "200-400 °C", FEEDSTOCK, 4.0),
    ("20.1", "Chimica di base",
     "processi di sintesi che impiegano idrogeno come reagente o come vettore termico",
     "200-500 °C", FEEDSTOCK, 3.5),
    ("20.5", "Altri prodotti chimici",
     "idrogenazione di oli e grassi e sintesi di specialità chimiche",
     "150-250 °C", MARGINALE, 2.0),
    ("21.", "Farmaceutica",
     "idrogenazione catalitica nella sintesi di principi attivi",
     "100-250 °C", MARGINALE, 1.5),

    # --- Minerali non metalliferi
    ("23.11", "Vetro piano",
     "forno fusorio a bacino in esercizio continuo",
     "1.500-1.600 °C", ALTA_TEMP, 3.5),
    ("23.13", "Vetro cavo",
     "fusione della miscela vetrificabile e condizionamento del vetro fuso",
     "1.400-1.550 °C", ALTA_TEMP, 3.5),
    ("23.1", "Industria del vetro",
     "fusione in forno con fiamma diretta sul bagno di vetro",
     "1.400-1.600 °C", ALTA_TEMP, 3.5),
    ("23.20", "Materiali refrattari",
     "cottura di prodotti refrattari in forno a tunnel",
     "1.300-1.700 °C", ALTA_TEMP, 2.5),
    ("23.3", "Laterizi e materiali per l'edilizia",
     "essiccazione e cottura di laterizi in forno continuo",
     "900-1.100 °C", ALTA_TEMP, 2.0),
    ("23.4", "Ceramica e porcellana",
     "cottura di prodotti ceramici e smaltatura",
     "1.000-1.250 °C", ALTA_TEMP, 2.0),
    ("23.51", "Cemento",
     "calcinazione del clinker in forno rotativo; resta la quota di CO2 di processo, "
     "che l'idrogeno non elimina",
     "1.400-1.500 °C", ALTA_TEMP, 3.0),
    ("23.52", "Calce e gesso",
     "calcinazione del carbonato di calcio in forno verticale o rotativo",
     "900-1.100 °C", ALTA_TEMP, 2.5),

    # --- Carta, legno, tessile, alimentare
    ("17.1", "Pasta-carta e cartiere",
     "produzione di vapore di processo e essiccazione del foglio",
     "150-250 °C", MARGINALE, 1.5),
    ("17.2", "Articoli di carta e cartone",
     "essiccazione e trasformazione, con calore a media temperatura",
     "100-200 °C", ELETTRIFICA, 0.8),
    ("13.", "Industria tessile",
     "tintura, finissaggio e essiccazione con vapore",
     "100-200 °C", ELETTRIFICA, 0.8),
    ("16.", "Industria del legno",
     "essiccazione del legname in cella",
     "60-120 °C", ELETTRIFICA, 0.5),
    ("10.", "Industria alimentare",
     "cottura, pastorizzazione ed essiccazione",
     "80-180 °C", ELETTRIFICA, 0.6),
    ("11.", "Industria delle bevande",
     "processi di cottura e sterilizzazione",
     "80-150 °C", ELETTRIFICA, 0.6),

    # --- Meccanica e trasformazione
    ("25.6", "Trattamento e rivestimento dei metalli",
     "trattamenti termici in atmosfera controllata, dove l'idrogeno è già impiegato "
     "come gas di processo",
     "700-1.100 °C", FEEDSTOCK, 2.0),
    ("25.", "Prodotti in metallo",
     "lavorazioni meccaniche con fabbisogno termico limitato",
     "variabile", MARGINALE, 1.0),
    ("28.", "Fabbricazione di macchinari",
     "assemblaggio e lavorazioni a freddo",
     "ambiente", ELETTRIFICA, 0.4),
    ("22.", "Gomma e materie plastiche",
     "estrusione e stampaggio con riscaldamento elettrico prevalente",
     "150-300 °C", ELETTRIFICA, 0.6),

    # --- Servizi e logistica
    ("49.4", "Trasporto merci su strada",
     "trazione di mezzi pesanti su lunga percorrenza",
     "n.a.", ALTA_TEMP, 2.0),
    ("52.", "Magazzinaggio e logistica",
     "movimentazione con carrelli elevatori a ciclo continuo",
     "n.a.", MARGINALE, 1.0),
    ("35.", "Fornitura di energia",
     "generazione elettrica di bilanciamento e accumulo stagionale",
     "n.a.", MARGINALE, 1.5),
    ("38.", "Trattamento dei rifiuti",
     "termovalorizzazione e trattamento con recupero energetico",
     "800-1.100 °C", MARGINALE, 1.0),
]


def normalizza(codice) -> str:
    """'24.10.00' / '241000' / '24,10' -> '24.10.00' con separatori uniformi."""
    if codice is None:
        return ""
    testo = str(codice).strip().replace(",", ".").replace(" ", "")
    if not testo:
        return ""
    if "." not in testo and testo.isdigit() and len(testo) > 2:
        testo = testo[:2] + "." + testo[2:]
    return testo


def cerca(codice):
    """Restituisce (settore, processo, temperatura, categoria, peso) o None."""
    testo = normalizza(codice)
    if not testo:
        return None
    migliore = None
    for prefisso, settore, processo, temperatura, categoria, peso in ATECO:
        if testo.startswith(prefisso):
            if migliore is None or len(prefisso) > len(migliore[0]):
                migliore = (prefisso, settore, processo, temperatura, categoria, peso)
    if migliore is None:
        return None
    return migliore[1:]


def descrizione(codice) -> str:
    """Frase pronta da mettere in tabella."""
    trovato = cerca(codice)
    if not trovato:
        return "Processo non classificato: verificare il codice ATECO."
    settore, processo, temperatura, _, _ = trovato
    if temperatura in ("n.a.", "processo", "ambiente", "variabile"):
        return f"{settore}: {processo}."
    return f"{settore}: {processo} ({temperatura})."


def verdetto(codice) -> str:
    trovato = cerca(codice)
    if not trovato:
        return "Da classificare"
    return trovato[3]


def peso(codice) -> float:
    trovato = cerca(codice)
    return trovato[4] if trovato else 1.0
