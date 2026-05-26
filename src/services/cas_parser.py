import pypdf
import re
import pandas as pd

# Direct mapping of common Indian ISINs to standard NSE/BSE tickers for yfinance compatibility
ISIN_TO_SYMBOL = {
    # Equities
    "INE296A01032": "BAJFINANCE.NS",
    "INE149A01033": "CHOLAHLDNG.NS",
    "INE138Y01010": "KFINTECH.NS",
    "INE0W2G01015": "SAGILITY.NS",
    "INE672A01026": "TATAINVEST.NS",
    "INE245A01021": "TATAPOWER.NS",
    "INE05FR01029": "ASHAPURI.NS",
    "INE878H01024": "INVENTURE.NS",
    "INE154A01025": "ITC.NS",
    "INE848E01016": "NHPC.NS",
    "INE881D01027": "OFSS.NS",
    "INE002A01018": "RELIANCE.NS",
    "INE040H01021": "SUZLON.NS",
    "INE814H01029": "ADANIPOWER.NS",
    "INE249Z01020": "MAZDOCK.NS",
    "INE735W01017": "UTKARSHBNK.NS",
    "INE457A01014": "MAHABANK.NS",
    "INE263A01024": "BEL.NS",
    "INE0HOQ01053": "BILLIONBRAINS", # Private equity/unlisted
    "INE063P01018": "EQUITASBNK.NS",
    "INE039A01010": "IFCI.NS",
    "INE242A01010": "IOC.NS",
    "INE202E01016": "IREDA.NS",
    "INE351F01018": "JPPOWER.NS",
    "INE758E01017": "JIOFIN.NS",
    "INE797F01020": "JUBLFOOD.NS",
    "INE134B01017": "KECL.NS",
    "INE750C01026": "MARKSANS.NS",
    "INE202B01038": "PEL.NS",
    "INE133E01013": "TI.NS",
    "INE551W01018": "UJJIVANSFB.NS",
    "INE200M01039": "VBL.NS",
    # ETFs (Mutual funds held in Demat form)
    "INF204KC1402": "SILVERBEES.NS",
    "INF204KB17I5": "GOLDBEES.NS",
    "INF204KB14I2": "NIFTYBEES.NS",
    "INF789F1AUX7": "GOLDSHARE.NS",
    "INF789F1AUW9": "UTINEXT50.NS",
}

def parse_cdsl_cas(pdf_file, password: str) -> pd.DataFrame:
    """
    Parses CDSL Consolidated Account Statement (CAS) PDF.
    Extracts stock and mutual fund holdings into a unified pandas DataFrame.
    """
    reader = pypdf.PdfReader(pdf_file)
    if reader.is_encrypted:
        if not password:
            raise ValueError("PDF is encrypted but no decryption password was provided.")
        reader.decrypt(password)
        
    all_text = ""
    for page in reader.pages:
        all_text += page.extract_text() + "\n"
        
    holdings = []
    
    # Split text into Demat Section and MF Folio Section to avoid cross-contamination
    demat_section_text = ""
    mf_section_text = ""
    
    demat_start = all_text.find("DEMAT ACCOUNTS HELD WITH CDSL")
    mf_start = all_text.find("MUTUAL FUND UNITS HELD WITH MF/RTA")
    
    if demat_start != -1:
        if mf_start != -1:
            demat_section_text = all_text[demat_start:mf_start]
            mf_section_text = all_text[mf_start:]
        else:
            demat_section_text = all_text[demat_start:]
    else:
        demat_section_text = all_text
        mf_section_text = all_text

    # 1. Parse Mutual Funds section (held with MF/RTA)
    mf_holding_match = re.search(
        r"MUTUAL FUND UNITS HELD AS ON.*?\nScheme Name ISIN Folio No\..*?\n(.*?)Grand T otal", 
        mf_section_text, 
        re.DOTALL | re.IGNORECASE
    )
    if mf_holding_match:
        mf_text = mf_holding_match.group(1)
        lines = mf_text.strip().split('\n')
        current_scheme = ""
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # If we see a new scheme start (e.g., "GODG - Axis Gold...") and not currently accumulating
            if current_scheme == "":
                if re.match(r'^[A-Z0-9]{3,6}\s*-\s*', line):
                    current_scheme = line
                    continue
                else:
                    # Ignore random table headers/labels
                    continue
                
            # If we are currently accumulating a scheme, look for the ISIN line
            isin_match = re.search(r'(INF[A-Z0-9]{9})\s*(.*)', line)
            if isin_match:
                isin = isin_match.group(1)
                rest = isin_match.group(2)
                
                tokens = rest.split()
                if len(tokens) >= 5:
                    numbers = []
                    for t in tokens[-6:]:
                        t_clean = t.replace(',', '').replace('(', '').replace(')', '').strip()
                        try:
                            numbers.append(float(t_clean))
                        except ValueError:
                            pass
                            
                    if len(numbers) >= 4:
                        valuation = numbers[-3] if len(numbers) >= 5 else numbers[-1]
                        buy_price = 0.0
                        quantity = 0.0
                        
                        if len(numbers) >= 6:
                            quantity = numbers[-6]
                            nav = numbers[-5]
                            valuation = numbers[-3]
                            invested = numbers[-4]
                            if quantity > 0:
                                buy_price = invested / quantity
                        elif len(numbers) == 5:
                            quantity = numbers[-5]
                            nav = numbers[-4]
                            valuation = numbers[-3]
                            invested = valuation
                            buy_price = nav
                        
                        # Clean asset name
                        asset_name = current_scheme.strip()
                        asset_name = re.sub(r'^[A-Z0-9]+\s*-\s*', '', asset_name)
                        
                        ticker = ISIN_TO_SYMBOL.get(isin, isin)
                        
                        holdings.append({
                            "Asset Name": asset_name,
                            "Ticker": ticker,
                            "Asset Type": "Mutual Fund",
                            "Sector": "Mutual Fund",
                            "Current Value": valuation,
                            "Currency": "INR",
                            "Quantity": quantity,
                            "Buy Price": buy_price,
                            "Current Price": nav,
                            "ISIN": isin
                        })
                current_scheme = "" # Reset
            else:
                # Accumulate multi-line scheme names (ignoring noise/headers)
                if not any(kw in line for kw in ["Page", "Central Depository", "CONSOLIDATED"]):
                    current_scheme += " " + line

    # 2. Parse Demat holdings section (Equities & ETFs)
    lines = demat_section_text.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        # ISIN is exactly 12 characters: INE/INF + 9 alphanumeric characters
        isin_match = re.match(r'^(INE[A-Z0-9]{9}|INF[A-Z0-9]{9})', line)
        if isin_match:
            isin = isin_match.group(1)
            security_name_parts = [line[12:].strip()]
            i += 1
            numbers_found = False
            numbers_tokens = []
            
            while i < len(lines) and not numbers_found:
                next_line = lines[i].strip()
                if not next_line:
                    i += 1
                    continue
                tokens = next_line.split()
                has_floats = False
                for token in tokens:
                    token_clean = token.replace(',', '').replace('(', '').replace(')', '').strip()
                    try:
                        float(token_clean)
                        has_floats = True
                        break
                    except ValueError:
                        pass
                
                if has_floats and ('--' in next_line or len(tokens) >= 5):
                    numbers_found = True
                    numbers_tokens = tokens
                else:
                    if not any(kw in next_line for kw in ["ISIN", "तभ ूत", "Page", "Central Depository", "CONSOLIDATED"]):
                        security_name_parts.append(next_line)
                    i += 1
            
            if numbers_found:
                security_name = " ".join(security_name_parts).strip()
                security_name = re.sub(r'#.*', '', security_name)
                security_name = re.sub(r'\s*-?\s*EQUITY SHARES.*', '', security_name, flags=re.IGNORECASE)
                security_name = re.sub(r'\s*-?\s*EQ SH.*', '', security_name, flags=re.IGNORECASE)
                security_name = security_name.strip()
                
                numbers = []
                for token in numbers_tokens:
                    token_clean = token.replace(',', '').replace('(', '').replace(')', '').strip()
                    try:
                        numbers.append(float(token_clean))
                    except ValueError:
                        pass
                
                if len(numbers) >= 2:
                    qty = numbers[0]
                    price = numbers[-2]
                    val = numbers[-1]
                    
                    asset_type = "Equity"
                    sector = "Unclassified"
                    if isin.startswith("INF"):
                        asset_type = "Mutual Fund"
                        sector = "Mutual Fund"
                        
                    ticker = ISIN_TO_SYMBOL.get(isin, isin)
                    
                    holdings.append({
                        "Asset Name": security_name,
                        "Ticker": ticker,
                        "Asset Type": asset_type,
                        "Sector": sector,
                        "Current Value": val,
                        "Currency": "INR",
                        "Quantity": qty,
                        "Buy Price": price,
                        "Current Price": price,
                        "ISIN": isin
                    })
        else:
            i += 1
            
    # Deduplicate by ISIN (combining quantities and values across multiple DPs if present)
    combined_holdings = {}
    for h in holdings:
        isin = h["ISIN"]
        if isin in combined_holdings:
            existing = combined_holdings[isin]
            existing["Quantity"] += h["Quantity"]
            existing["Current Value"] += h["Current Value"]
            if existing["Quantity"] > 0:
                existing["Buy Price"] = (existing["Buy Price"] * (existing["Quantity"] - h["Quantity"]) + h["Buy Price"] * h["Quantity"]) / existing["Quantity"]
            if "Current Price" in h:
                existing["Current Price"] = h["Current Price"]
        else:
            combined_holdings[isin] = h
            
    df = pd.DataFrame(list(combined_holdings.values()))
    
    if df.empty:
        # Return empty DataFrame with required columns
        return pd.DataFrame(columns=["Asset Name", "Ticker", "Asset Type", "Sector", "Current Value", "Currency", "Quantity", "Buy Price", "Current Price", "ISIN"])
        
    return df
