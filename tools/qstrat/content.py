"""Editorial content: the stock universe, the thinkers and the strategies.

Everything a reader sees about a person or a rule lives here, so it can be
reviewed in one place. Keep claims factual and sourced; paraphrase, don't quote.
"""

# --------------------------------------------------------------------------
# Universe
# --------------------------------------------------------------------------
# kind: etf | crypto | stock    cur: display currency prefix
TICKERS = [
    # Market indexes (benchmarks: not directly tradable; buy them through an index ETF)
    {"sym": "^GSPC", "name": "S&P 500 index", "short": "S&P 500", "slug": "sp500", "group": "Market indexes", "cur": "", "index": True},
    {"sym": "^NDX", "name": "Nasdaq-100 index", "short": "Nasdaq-100", "slug": "nasdaq-100", "group": "Market indexes", "cur": "", "index": True},
    {"sym": "^DJI", "name": "Dow Jones Industrial Average", "short": "Dow", "slug": "dow", "group": "Market indexes", "cur": "", "index": True},
    {"sym": "^RUT", "name": "Russell 2000 index", "short": "Russell 2000", "slug": "russell-2000", "group": "Market indexes", "cur": "", "index": True},
    {"sym": "^GSPTSE", "name": "S&P/TSX Composite index", "short": "TSX", "slug": "tsx", "group": "Market indexes", "cur": "", "index": True},
    # US sector ETFs (Select Sector SPDRs, plus a semiconductor ETF)
    {"sym": "XLK", "name": "Technology Select Sector ETF", "short": "XLK", "group": "Sectors", "cur": "$", "sector": "Technology"},
    {"sym": "SMH", "name": "VanEck Semiconductor ETF", "short": "SMH", "group": "Sectors", "cur": "$", "sector": "Semiconductors"},
    {"sym": "XLC", "name": "Communication Services Select Sector ETF", "short": "XLC", "group": "Sectors", "cur": "$", "sector": "Communication services"},
    {"sym": "XLY", "name": "Consumer Discretionary Select Sector ETF", "short": "XLY", "group": "Sectors", "cur": "$", "sector": "Consumer discretionary"},
    {"sym": "XLF", "name": "Financial Select Sector ETF", "short": "XLF", "group": "Sectors", "cur": "$", "sector": "Financials"},
    {"sym": "XLV", "name": "Health Care Select Sector ETF", "short": "XLV", "group": "Sectors", "cur": "$", "sector": "Health care"},
    {"sym": "XLI", "name": "Industrial Select Sector ETF", "short": "XLI", "group": "Sectors", "cur": "$", "sector": "Industrials"},
    {"sym": "XLE", "name": "Energy Select Sector ETF", "short": "XLE", "group": "Sectors", "cur": "$", "sector": "Energy"},
    {"sym": "XLB", "name": "Materials Select Sector ETF", "short": "XLB", "group": "Sectors", "cur": "$", "sector": "Materials"},
    {"sym": "XLP", "name": "Consumer Staples Select Sector ETF", "short": "XLP", "group": "Sectors", "cur": "$", "sector": "Consumer staples"},
    {"sym": "XLU", "name": "Utilities Select Sector ETF", "short": "XLU", "group": "Sectors", "cur": "$", "sector": "Utilities"},
    {"sym": "XLRE", "name": "Real Estate Select Sector ETF", "short": "XLRE", "group": "Sectors", "cur": "$", "sector": "Real estate"},
    # Indexes & ETFs
    {"sym": "SPY", "name": "S&P 500 ETF", "group": "Indexes & ETFs", "cur": "$"},
    {"sym": "QQQ", "name": "Nasdaq-100 ETF", "group": "Indexes & ETFs", "cur": "$"},
    {"sym": "IWM", "name": "Russell 2000 ETF", "group": "Indexes & ETFs", "cur": "$"},
    {"sym": "XIU.TO", "name": "S&P/TSX 60 ETF", "group": "Indexes & ETFs", "cur": "C$"},
    {"sym": "GLD", "name": "Gold ETF", "group": "Indexes & ETFs", "cur": "$"},
    {"sym": "SLV", "name": "Silver ETF", "group": "Indexes & ETFs", "cur": "$"},
    {"sym": "TLT", "name": "20+ Year Treasury ETF", "group": "Indexes & ETFs", "cur": "$"},
    # Crypto
    {"sym": "BTC-USD", "name": "Bitcoin", "group": "Crypto", "cur": "$"},
    {"sym": "ETH-USD", "name": "Ether", "group": "Crypto", "cur": "$"},
    # Big tech
    {"sym": "AAPL", "name": "Apple", "group": "Big tech", "cur": "$"},
    {"sym": "MSFT", "name": "Microsoft", "group": "Big tech", "cur": "$"},
    {"sym": "AMZN", "name": "Amazon", "group": "Big tech", "cur": "$"},
    {"sym": "GOOGL", "name": "Alphabet", "group": "Big tech", "cur": "$"},
    {"sym": "META", "name": "Meta Platforms", "group": "Big tech", "cur": "$"},
    {"sym": "TSLA", "name": "Tesla", "group": "Big tech", "cur": "$"},
    # Semiconductors
    {"sym": "NVDA", "name": "Nvidia", "group": "Semiconductors", "cur": "$"},
    {"sym": "AMD", "name": "AMD", "group": "Semiconductors", "cur": "$"},
    {"sym": "AVGO", "name": "Broadcom", "group": "Semiconductors", "cur": "$"},
    {"sym": "MU", "name": "Micron", "group": "Semiconductors", "cur": "$"},
    {"sym": "INTC", "name": "Intel", "group": "Semiconductors", "cur": "$"},
    {"sym": "LSCC", "name": "Lattice Semiconductor", "group": "Semiconductors", "cur": "$"},
    {"sym": "STM", "name": "STMicroelectronics", "group": "Semiconductors", "cur": "$"},
    {"sym": "STHH", "name": "STMicroelectronics (currency-hedged ETF)", "group": "Semiconductors", "cur": "$"},
    # Software & devices
    {"sym": "SHOP.TO", "name": "Shopify", "group": "Software & devices", "cur": "C$"},
    {"sym": "BB.TO", "name": "BlackBerry", "group": "Software & devices", "cur": "C$"},
    {"sym": "SUPX", "name": "SuperX AI Technology", "group": "Software & devices", "cur": "$"},
    {"sym": "GPRO", "name": "GoPro", "group": "Software & devices", "cur": "$"},
    # Healthcare
    {"sym": "LLY", "name": "Eli Lilly", "group": "Healthcare", "cur": "$"},
    {"sym": "NVO", "name": "Novo Nordisk", "group": "Healthcare", "cur": "$"},
    {"sym": "PFE", "name": "Pfizer", "group": "Healthcare", "cur": "$"},
    {"sym": "BSX", "name": "Boston Scientific", "group": "Healthcare", "cur": "$"},
    {"sym": "MDT", "name": "Medtronic", "group": "Healthcare", "cur": "$"},
    {"sym": "NPCE", "name": "NeuroPace", "group": "Healthcare", "cur": "$"},
    # Financials
    {"sym": "JPM", "name": "JPMorgan Chase", "group": "Financials", "cur": "$"},
    {"sym": "RY.TO", "name": "Royal Bank of Canada", "group": "Financials", "cur": "C$"},
    # Industrials & rentals
    {"sym": "CARR", "name": "Carrier Global", "group": "Industrials & rentals", "cur": "$"},
    {"sym": "URI", "name": "United Rentals", "group": "Industrials & rentals", "cur": "$"},
    {"sym": "R", "name": "Ryder System", "group": "Industrials & rentals", "cur": "$"},
    {"sym": "WSC", "name": "WillScot", "group": "Industrials & rentals", "cur": "$"},
    {"sym": "HTZ", "name": "Hertz", "group": "Industrials & rentals", "cur": "$"},
    {"sym": "CAR", "name": "Avis Budget", "group": "Industrials & rentals", "cur": "$"},
    {"sym": "TRNS", "name": "Transcat", "group": "Industrials & rentals", "cur": "$"},
    {"sym": "FLXS", "name": "Flexsteel Industries", "group": "Industrials & rentals", "cur": "$"},
    {"sym": "FC", "name": "Franklin Covey", "group": "Industrials & rentals", "cur": "$"},
    # Energy & power
    {"sym": "XOM", "name": "Exxon Mobil", "group": "Energy & power", "cur": "$"},
    {"sym": "APA", "name": "APA Corp", "group": "Energy & power", "cur": "$"},
    {"sym": "CVE.TO", "name": "Cenovus Energy", "group": "Energy & power", "cur": "C$"},
    {"sym": "WCP.TO", "name": "Whitecap Resources", "group": "Energy & power", "cur": "C$"},
    {"sym": "EIX", "name": "Edison International", "group": "Energy & power", "cur": "$"},
    {"sym": "FLNC", "name": "Fluence Energy", "group": "Energy & power", "cur": "$"},
    {"sym": "EOSE", "name": "Eos Energy", "group": "Energy & power", "cur": "$"},
    # Metals & mining
    {"sym": "AEM.TO", "name": "Agnico Eagle Mines", "group": "Metals & mining", "cur": "C$"},
    {"sym": "IMG.TO", "name": "IAMGOLD", "group": "Metals & mining", "cur": "C$"},
    {"sym": "HBM.TO", "name": "Hudbay Minerals", "group": "Metals & mining", "cur": "C$"},
    {"sym": "CS.TO", "name": "Capstone Copper", "group": "Metals & mining", "cur": "C$"},
    # Crypto miners
    {"sym": "MARA", "name": "MARA Holdings", "group": "Crypto miners", "cur": "$"},
    {"sym": "RIOT", "name": "Riot Platforms", "group": "Crypto miners", "cur": "$"},
    {"sym": "BTDR", "name": "Bitdeer Technologies", "group": "Crypto miners", "cur": "$"},
    # Micro caps (under $100M)
    {"sym": "OPTT", "name": "Ocean Power Technologies", "group": "Micro caps", "cur": "$", "micro": True},
    {"sym": "PRSO", "name": "Peraso", "group": "Micro caps", "cur": "$", "micro": True},
    {"sym": "HOLO", "name": "MicroCloud Hologram", "group": "Micro caps", "cur": "$", "micro": True},
    {"sym": "NAMM", "name": "Namib Minerals", "group": "Micro caps", "cur": "$", "micro": True},
    {"sym": "LEAP.V", "name": "Quantum Critical Metals", "group": "Micro caps", "cur": "C$", "micro": True},
    {"sym": "QUTX", "name": "Quantum X", "group": "Micro caps", "cur": "$", "micro": True},
]
# Nasdaq-100 members (list as of Oct 5, 2026). Members already covered above are
# tagged "ndx"; the rest are added here with full analysis and a page for every play.
# GOOG (Alphabet class C) is covered by GOOGL and Shopify by its Toronto listing.
NDX_COVERED = {"AAPL", "MSFT", "AMZN", "GOOGL", "META", "TSLA", "NVDA", "AMD", "AVGO", "MU", "INTC", "SHOP.TO"}
NDX_NEW = {
    "Semiconductors": [("ASML", "ASML Holding"), ("LRCX", "Lam Research"), ("AMAT", "Applied Materials"), ("KLAC", "KLA"),
                       ("ARM", "Arm Holdings"), ("TXN", "Texas Instruments"), ("MRVL", "Marvell Technology"), ("ADI", "Analog Devices"),
                       ("QCOM", "Qualcomm"), ("MPWR", "Monolithic Power Systems"), ("NXPI", "NXP Semiconductors"), ("MCHP", "Microchip Technology"),
                       ("ALAB", "Astera Labs"), ("TER", "Teradyne"), ("SNDK", "Sandisk")],
    "Software & devices": [("PLTR", "Palantir"), ("CSCO", "Cisco"), ("PANW", "Palo Alto Networks"), ("CRWD", "CrowdStrike"),
                           ("FTNT", "Fortinet"), ("DDOG", "Datadog"), ("CDNS", "Cadence Design Systems"), ("SNPS", "Synopsys"),
                           ("ADBE", "Adobe"), ("INTU", "Intuit"), ("ADSK", "Autodesk"), ("WDAY", "Workday"), ("APP", "AppLovin"),
                           ("ROP", "Roper Technologies"), ("TRI", "Thomson Reuters"), ("STX", "Seagate Technology"), ("WDC", "Western Digital"),
                           ("LITE", "Lumentum"), ("NBIS", "Nebius Group"), ("CRWV", "CoreWeave"), ("MSTR", "Strategy (MicroStrategy)")],
    "Consumer & retail": [("WMT", "Walmart"), ("COST", "Costco"), ("PEP", "PepsiCo"), ("MDLZ", "Mondelez"), ("MNST", "Monster Beverage"),
                          ("KDP", "Keurig Dr Pepper"), ("CCEP", "Coca-Cola Europacific Partners"), ("BKNG", "Booking Holdings"),
                          ("ABNB", "Airbnb"), ("MAR", "Marriott"), ("SBUX", "Starbucks"), ("DASH", "DoorDash"), ("ROST", "Ross Stores"),
                          ("ORLY", "O'Reilly Automotive"), ("PDD", "PDD Holdings"), ("MELI", "MercadoLibre")],
    "Media & telecom": [("NFLX", "Netflix"), ("TMUS", "T-Mobile US"), ("CMCSA", "Comcast"), ("WBD", "Warner Bros. Discovery"),
                        ("TTWO", "Take-Two Interactive")],
    "Healthcare": [("AMGN", "Amgen"), ("GILD", "Gilead Sciences"), ("VRTX", "Vertex Pharmaceuticals"), ("REGN", "Regeneron"),
                   ("ALNY", "Alnylam Pharmaceuticals"), ("ISRG", "Intuitive Surgical"), ("IDXX", "IDEXX Laboratories"), ("DXCM", "DexCom"),
                   ("GEHC", "GE HealthCare")],
    "Financials": [("PYPL", "PayPal")],
    "Industrials & materials": [("HON", "Honeywell"), ("HONA", "Honeywell Aerospace"), ("LIN", "Linde"), ("ADP", "ADP"), ("PAYX", "Paychex"),
                                ("CTAS", "Cintas"), ("CPRT", "Copart"), ("CSX", "CSX"), ("ODFL", "Old Dominion Freight Line"), ("PCAR", "Paccar"),
                                ("FAST", "Fastenal"), ("AXON", "Axon Enterprise"), ("FER", "Ferrovial"), ("RKLB", "Rocket Lab"), ("SPCX", "SpaceX")],
    "Energy & power": [("CEG", "Constellation Energy"), ("AEP", "American Electric Power"), ("XEL", "Xcel Energy"), ("EXC", "Exelon"),
                       ("BKR", "Baker Hughes"), ("FANG", "Diamondback Energy")],
}
# TSX-listed companies (the 218 names on Proud to Work's TSX tracker, Oct 5, 2026).
# The nine already covered above are tagged "tsx"; the rest are added here with
# full analysis: every play, and a page for each one. Each tuple is (Yahoo
# symbol, name, ticker as the TSX writes it). Prices are in Canadian dollars.
TSX_COVERED = {"SHOP.TO", "BB.TO", "RY.TO", "CVE.TO", "WCP.TO", "AEM.TO", "IMG.TO", "HBM.TO", "CS.TO"}
TSX_NEW = {
    "Software & devices": [
        ("CLS.TO", "Celestica", "CLS"),
        ("CSU.TO", "Constellation Software", "CSU"),
        ("DCBO.TO", "Docebo", "DCBO"),
        ("DSG.TO", "Descartes Systems", "DSG"),
        ("GIB-A.TO", "CGI", "GIB.A"),
        ("KXS.TO", "Kinaxis", "KXS"),
        ("LSPD.TO", "Lightspeed Commerce", "LSPD"),
        ("OTEX.TO", "OpenText", "OTEX"),
        ("TRI.TO", "Thomson Reuters (Toronto listing)", "TRI.TO"),
    ],
    "Consumer & retail": [
        ("ATD.TO", "Alimentation Couche-Tard", "ATD"),
        ("ATZ.TO", "Aritzia", "ATZ"),
        ("BYD.TO", "Boyd Group", "BYD"),
        ("CTC-A.TO", "Canadian Tire", "CTC.A"),
        ("DOL.TO", "Dollarama", "DOL"),
        ("DOO.TO", "BRP", "DOO"),
        ("EMP-A.TO", "Empire Company", "EMP.A"),
        ("GIL.TO", "Gildan Activewear", "GIL"),
        ("JWEL.TO", "Jamieson Wellness", "JWEL"),
        ("L.TO", "Loblaw", "L"),
        ("MFI.TO", "Maple Leaf Foods", "MFI"),
        ("MRU.TO", "Metro Inc.", "MRU"),
        ("NWC.TO", "North West Company", "NWC"),
        ("PBH.TO", "Premium Brands", "PBH"),
        ("PET.TO", "Pet Valu", "PET"),
        ("QSR.TO", "Restaurant Brands International", "QSR"),
        ("SAP.TO", "Saputo", "SAP"),
        ("WN.TO", "George Weston", "WN"),
    ],
    "Media & telecom": [
        ("BCE.TO", "BCE", "BCE"),
        ("CCA.TO", "Cogeco Communications", "CCA"),
        ("QBR-B.TO", "Quebecor", "QBR.B"),
        ("RCI-B.TO", "Rogers Communications", "RCI.B"),
        ("T.TO", "Telus", "T"),
        ("TSAT.TO", "Telesat", "TSAT"),
    ],
    "Healthcare": [
        ("BHC.TO", "Bausch Health", "BHC"),
        ("CURA.TO", "Curaleaf", "CURA"),
        ("SIA.TO", "Sienna Senior Living", "SIA"),
    ],
    "Financials": [
        ("BAM.TO", "Brookfield Asset Management", "BAM"),
        ("BMO.TO", "Bank of Montreal", "BMO"),
        ("BN.TO", "Brookfield Corporation", "BN"),
        ("BNS.TO", "Bank of Nova Scotia", "BNS"),
        ("CM.TO", "Canadian Imperial Bank of Commerce", "CM"),
        ("DFY.TO", "Definity Financial", "DFY"),
        ("EQB.TO", "EQB", "EQB"),
        ("FFH.TO", "Fairfax Financial", "FFH"),
        ("GSY.TO", "goeasy", "GSY"),
        ("GWO.TO", "Great-West Lifeco", "GWO"),
        ("IAG.TO", "iA Financial", "IAG"),
        ("IFC.TO", "Intact Financial", "IFC"),
        ("IGM.TO", "IGM Financial", "IGM"),
        ("LB.TO", "Laurentian Bank of Canada", "LB"),
        ("MFC.TO", "Manulife Financial", "MFC"),
        ("NA.TO", "National Bank of Canada", "NA"),
        ("ONEX.TO", "Onex", "ONEX"),
        ("POW.TO", "Power Corporation of Canada", "POW"),
        ("SII.TO", "Sprott", "SII"),
        ("SLF.TO", "Sun Life Financial", "SLF"),
        ("TD.TO", "TD Bank", "TD"),
        ("TSU.TO", "Trisura Group", "TSU"),
        ("X.TO", "TMX Group", "X"),
    ],
    "Real estate": [
        ("AIF.TO", "Altus Group", "AIF"),
        ("AP-UN.TO", "Allied Properties REIT", "AP.UN"),
        ("BEI-UN.TO", "Boardwalk REIT", "BEI.UN"),
        ("CAR-UN.TO", "Canadian Apartment Properties REIT", "CAR.UN"),
        ("CHP-UN.TO", "Choice Properties REIT", "CHP.UN"),
        ("CIGI.TO", "Colliers International", "CIGI"),
        ("CRR-UN.TO", "Crombie REIT", "CRR.UN"),
        ("CRT-UN.TO", "CT REIT", "CRT.UN"),
        ("CSH-UN.TO", "Chartwell Retirement Residences", "CSH.UN"),
        ("DIR-UN.TO", "Dream Industrial REIT", "DIR.UN"),
        ("FCR-UN.TO", "First Capital REIT", "FCR.UN"),
        ("FSV.TO", "FirstService", "FSV"),
        ("GRT-UN.TO", "Granite REIT", "GRT.UN"),
        ("HR-UN.TO", "H&R REIT", "HR.UN"),
        ("KMP-UN.TO", "Killam Apartment REIT", "KMP.UN"),
        ("PMZ-UN.TO", "Primaris REIT", "PMZ.UN"),
        ("REI-UN.TO", "RioCan REIT", "REI.UN"),
        ("SRU-UN.TO", "SmartCentres REIT", "SRU.UN"),
        ("VITL-UN.TO", "Vital Infrastructure Property Trust", "VITL.UN"),
    ],
    "Industrials & materials": [
        ("AC.TO", "Air Canada", "AC"),
        ("ARE.TO", "Aecon Group", "ARE"),
        ("ATRL.TO", "AtkinsRéalis", "ATRL"),
        ("ATS.TO", "ATS Corporation", "ATS"),
        ("BBD-B.TO", "Bombardier", "BBD.B"),
        ("BBUC.TO", "Brookfield Business Corp", "BBUC"),
        ("BDGI.TO", "Badger Infrastructure Solutions", "BDGI"),
        ("BDT.TO", "Bird Construction", "BDT"),
        ("CAE.TO", "CAE", "CAE"),
        ("CCL-B.TO", "CCL Industries", "CCL.B"),
        ("CGY.TO", "Calian Group", "CGY"),
        ("CJT.TO", "Cargojet", "CJT"),
        ("CNR.TO", "Canadian National Railway", "CNR"),
        ("CP.TO", "Canadian Pacific Kansas City", "CP"),
        ("EFN.TO", "Element Fleet Management", "EFN"),
        ("EIF.TO", "Exchange Income", "EIF"),
        ("FTT.TO", "Finning International", "FTT"),
        ("GFL.TO", "GFL Environmental", "GFL"),
        ("LNR.TO", "Linamar", "LNR"),
        ("MDA.TO", "MDA Space", "MDA"),
        ("MG.TO", "Magna International", "MG"),
        ("MTL.TO", "Mullen Group", "MTL"),
        ("MX.TO", "Methanex", "MX"),
        ("NFI.TO", "NFI Group", "NFI"),
        ("NTR.TO", "Nutrien", "NTR"),
        ("RBA.TO", "RB Global", "RBA"),
        ("RCH.TO", "Richelieu Hardware", "RCH"),
        ("RUS.TO", "Russel Metals", "RUS"),
        ("SJ.TO", "Stella-Jones", "SJ"),
        ("STN.TO", "Stantec", "STN"),
        ("TCL-A.TO", "Transcontinental", "TCL.A"),
        ("TFII.TO", "TFI International", "TFII"),
        ("TIH.TO", "Toromont Industries", "TIH"),
        ("VNP.TO", "5N Plus", "VNP"),
        ("WCN.TO", "Waste Connections", "WCN"),
        ("WFG.TO", "West Fraser Timber", "WFG"),
        ("WPK.TO", "Winpak", "WPK"),
        ("WSP.TO", "WSP Global", "WSP"),
    ],
    "Energy & power": [
        ("AAV.TO", "Advantage Energy", "AAV"),
        ("ACO-X.TO", "ATCO", "ACO.X"),
        ("ALA.TO", "AltaGas", "ALA"),
        ("AQN.TO", "Algonquin Power & Utilities", "AQN"),
        ("ATH.TO", "Athabasca Oil", "ATH"),
        ("BEP-UN.TO", "Brookfield Renewable Partners", "BEP.UN"),
        ("BIP-UN.TO", "Brookfield Infrastructure Partners", "BIP.UN"),
        ("BIR.TO", "Birchcliff Energy", "BIR"),
        ("BTE.TO", "Baytex Energy", "BTE"),
        ("CCO.TO", "Cameco", "CCO"),
        ("CEU.TO", "CES Energy Solutions", "CEU"),
        ("CNQ.TO", "Canadian Natural Resources", "CNQ"),
        ("CPX.TO", "Capital Power", "CPX"),
        ("CU.TO", "Canadian Utilities", "CU"),
        ("DML.TO", "Denison Mines", "DML"),
        ("EFR.TO", "Energy Fuels", "EFR"),
        ("EFX.TO", "Enerflex", "EFX"),
        ("EMA.TO", "Emera", "EMA"),
        ("ENB.TO", "Enbridge", "ENB"),
        ("FRU.TO", "Freehold Royalties", "FRU"),
        ("FTS.TO", "Fortis", "FTS"),
        ("GEI.TO", "Gibson Energy", "GEI"),
        ("H.TO", "Hydro One", "H"),
        ("HWX.TO", "Headwater Exploration", "HWX"),
        ("IMO.TO", "Imperial Oil", "IMO"),
        ("IPCO.TO", "International Petroleum", "IPCO"),
        ("KEL.TO", "Kelt Exploration", "KEL"),
        ("KEY.TO", "Keyera", "KEY"),
        ("NPI.TO", "Northland Power", "NPI"),
        ("NXE.TO", "NexGen Energy", "NXE"),
        ("PEY.TO", "Peyto Exploration & Development", "PEY"),
        ("POU.TO", "Paramount Resources", "POU"),
        ("PPL.TO", "Pembina Pipeline", "PPL"),
        ("PSK.TO", "PrairieSky Royalty", "PSK"),
        ("PXT.TO", "Parex Resources", "PXT"),
        ("SCR.TO", "Strathcona Resources", "SCR"),
        ("SOBO.TO", "South Bow", "SOBO"),
        ("SPB.TO", "Superior Plus", "SPB"),
        ("SU.TO", "Suncor Energy", "SU"),
        ("TA.TO", "TransAlta", "TA"),
        ("TOU.TO", "Tourmaline Oil", "TOU"),
        ("TPZ.TO", "Topaz Energy", "TPZ"),
        ("TRP.TO", "TC Energy", "TRP"),
        ("TVE.TO", "Tamarack Valley Energy", "TVE"),
        ("TVK.TO", "TerraVest Industries", "TVK"),
        ("VET.TO", "Vermilion Energy", "VET"),
    ],
    "Metals & mining": [
        ("AAUC.TO", "Allied Gold", "AAUC"),
        ("ABRA.TO", "AbraSilver Resource", "ABRA"),
        ("ABX.TO", "Barrick Gold", "ABX"),
        ("AG.TO", "First Majestic Silver", "AG"),
        ("AGI.TO", "Alamos Gold", "AGI"),
        ("ARIS.TO", "Aris Mining", "ARIS"),
        ("ASM.TO", "Avino Silver & Gold Mines", "ASM"),
        ("AYA.TO", "Aya Gold & Silver", "AYA"),
        ("BTO.TO", "B2Gold", "BTO"),
        ("CG.TO", "Centerra Gold", "CG"),
        ("DPM.TO", "Dundee Precious Metals", "DPM"),
        ("DSV.TO", "Discovery Silver", "DSV"),
        ("EDR.TO", "Endeavour Silver", "EDR"),
        ("ELD.TO", "Eldorado Gold", "ELD"),
        ("EQX.TO", "Equinox Gold", "EQX"),
        ("ERO.TO", "Ero Copper", "ERO"),
        ("FM.TO", "First Quantum Minerals", "FM"),
        ("FNV.TO", "Franco-Nevada", "FNV"),
        ("FVI.TO", "Fortuna Mining", "FVI"),
        ("GMIN.TO", "G Mining Ventures", "GMIN"),
        ("IAU.TO", "i-80 Gold", "IAU"),
        ("IVN.TO", "Ivanhoe Mines", "IVN"),
        ("K.TO", "Kinross Gold", "K"),
        ("KNT.TO", "K92 Mining", "KNT"),
        ("LAC.TO", "Lithium Americas", "LAC"),
        ("LIF.TO", "Labrador Iron Ore Royalty", "LIF"),
        ("LUG.TO", "Lundin Gold", "LUG"),
        ("LUN.TO", "Lundin Mining", "LUN"),
        ("MAU.TO", "Montage Gold", "MAU"),
        ("NG.TO", "NovaGold Resources", "NG"),
        ("NGEX.TO", "NGEx Minerals", "NGEX"),
        ("OGC.TO", "OceanaGold", "OGC"),
        ("OR.TO", "Osisko Gold Royalties", "OR"),
        ("PAAS.TO", "Pan American Silver", "PAAS"),
        ("PPTA.TO", "Perpetua Resources", "PPTA"),
        ("SEA.TO", "Seabridge Gold", "SEA"),
        ("SKE.TO", "Skeena Resources", "SKE"),
        ("SSRM.TO", "SSR Mining", "SSRM"),
        ("SVM.TO", "Silvercorp Metals", "SVM"),
        ("TECK-B.TO", "Teck Resources", "TECK.B"),
        ("TFPM.TO", "Triple Flag Precious Metals", "TFPM"),
        ("TKO.TO", "Taseko Mines", "TKO"),
        ("TXG.TO", "Torex Gold Resources", "TXG"),
        ("USA.TO", "Americas Gold and Silver", "USA"),
        ("VZLA.TO", "Vizsla Silver", "VZLA"),
        ("WDO.TO", "Wesdome Gold Mines", "WDO"),
        ("WPM.TO", "Wheaton Precious Metals", "WPM"),
    ],
}
for _t in TICKERS:
    if _t["sym"] in NDX_COVERED:
        _t["ndx"] = True
    if _t["sym"] in TSX_COVERED:
        _t["tsx"] = True
_have = {t["sym"] for t in TICKERS}
# "bulk": added as a whole list, so the home page's board keeps to the original names
for _g, _names in NDX_NEW.items():
    for _sym, _name in _names:
        if _sym not in _have:
            TICKERS.append({"sym": _sym, "name": _name, "group": _g, "cur": "$", "ndx": True, "bulk": True})
            _have.add(_sym)
for _g, _names in TSX_NEW.items():
    for _sym, _name, _short in _names:
        if _sym not in _have:
            TICKERS.append({"sym": _sym, "name": _name, "short": _short, "group": _g, "cur": "C$", "tsx": True, "bulk": True})
            _have.add(_sym)

GROUP_ORDER = ["Market indexes", "Sectors", "Indexes & ETFs", "Crypto", "Big tech", "Semiconductors", "Software & devices", "Consumer & retail",
               "Media & telecom", "Healthcare", "Financials", "Real estate", "Industrials & materials", "Industrials & rentals", "Energy & power",
               "Metals & mining", "Crypto miners", "Micro caps"]

# Tickers Be The Puck doesn't cover, even if a reader asks for them
EXCLUDED = {"MGRC"}

# Reader-requested tickers (added by the nightly queue; see tools/sync_requests.py)
import json as _json0
import os as _os0
_REQ = _os0.path.join(_os0.path.dirname(_os0.path.dirname(_os0.path.dirname(_os0.path.abspath(__file__)))), "data", "universe", "requested.json")
_known = {t["sym"] for t in TICKERS}
if _os0.path.exists(_REQ):
    for _r in _json0.load(open(_REQ)).get("tickers", []):
        if _r.get("status") == "ok" and _r["sym"] not in _known and _r["sym"] not in EXCLUDED:
            TICKERS.append({"sym": _r["sym"], "name": _r.get("name") or _r["sym"], "group": "Reader-requested",
                            "cur": _r.get("cur", "$"), "requested": True, "since": _r.get("added")})
            _known.add(_r["sym"])
GROUP_ORDER.append("Reader-requested")


def _short(sym):
    return sym.replace("-USD", "").replace(".TO", "").replace(".V", "").replace(".NE", "").replace("^", "")


for t in TICKERS:
    t.setdefault("slug", t["sym"].lower().replace(".", "-").replace("^", ""))
    t["crypto"] = t["sym"].endswith("-USD")
    t.setdefault("short", _short(t["sym"]))
    t["canadian"] = t["sym"].endswith((".TO", ".V", ".NE")) or t["sym"] == "^GSPTSE"
    # benchmark for beta and crash comparisons
    if t["sym"] == "^GSPC":
        t["bench"] = None
    elif t["canadian"]:
        t["bench"] = "^GSPTSE" if t["sym"] != "^GSPTSE" else "^GSPC"
    else:
        t["bench"] = "^GSPC"
TK_BY_SYM = {t["sym"]: t for t in TICKERS}
INDEXES = [t for t in TICKERS if t.get("index")]


# --------------------------------------------------------------------------
# Analysts (verified bios, books and sources live in analysts.json) and plays
# --------------------------------------------------------------------------
import json as _json
import os as _os

from .plays import PLAYS, PLAY, TIMED, STARTER, STARTER_SLUGS, BAR_WORD, FAMILIES, FAMILY, FAMILY_ORDER, by_family  # noqa: E402,F401

with open(_os.path.join(_os.path.dirname(__file__), "analysts.json"), encoding="utf-8") as _f:
    THINKERS = _json.load(_f)
for _a in THINKERS:
    _a["sources"] = [tuple(x) for x in _a["sources"]]
    _a["strategies"] = [p["slug"] for p in PLAYS if _a["slug"] in p["analysts"]]
for _p in PLAYS:
    _p["thinker"] = _p["analysts"][0]
THINKER = {t["slug"]: t for t in THINKERS}
_missing = {a for p in PLAYS for a in p["analysts"]} - set(THINKER)
assert not _missing, f"plays credit unknown analysts: {_missing}"

STRATEGIES = PLAYS
STRATEGY = PLAY


def credit(p):
    """'A' or 'A & B' for a play's analysts."""
    return " & ".join(THINKER[a]["name"] for a in p["analysts"])
