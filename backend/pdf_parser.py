import PyPDF2
import re
from datetime import datetime
from typing import List, Dict
import io
from stock_api import enrich_security_data

def extract_isin_from_text(text: str, security_name: str) -> str:
    """
    Extract ISIN from contract note text based on security name
    """
    # Look for ISIN pattern near the security name
    # ISIN format: 2 letters + 10 alphanumeric characters (e.g., INE925R01014)
    isin_pattern = r'(IN[A-Z0-9]{10})'
    
    # Find all ISINs in the text
    isins = re.findall(isin_pattern, text)
    
    if isins:
        # Try to find ISIN closest to the security name
        security_index = text.find(security_name)
        if security_index != -1:
            # Look for ISIN within a reasonable distance from security name
            for isin in isins:
                isin_index = text.find(isin)
                if abs(isin_index - security_index) < 1000:  # Within 1000 characters
                    return isin
        
        # If no close match, return the first ISIN found
        return isins[0]
    
    return None

def parse_contract_note(pdf_content: bytes, password: str) -> List[Dict]:
    """
    Parse contract note PDF and extract transaction data
    """
    transactions = []
    
    try:
        pdf_stream = io.BytesIO(pdf_content)
        pdf_reader = PyPDF2.PdfReader(pdf_stream)
        
        # Decrypt PDF if password protected
        if pdf_reader.is_encrypted:
            pdf_reader.decrypt(password)
        
        full_text = ""
        for page in pdf_reader.pages:
            full_text += page.extract_text()
        
        # Look for the scrip wise summary section
        summary_patterns = [
            r"The scrip wise summary is enclosed below",
            r"The srcip wise summary is enclosed below",  # Handle typo in HDFC PDFs
            r"scrip wise summary",
            r"srcip wise summary",  # Handle typo
            r"Script wise summary",
            r"Scripwise Summary",  # Another HDFC format
            r"Security wise summary"
        ]
        
        summary_start = -1
        for pattern in summary_patterns:
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                summary_start = match.end()
                break
        
        if summary_start == -1:
            raise ValueError("Could not find scrip wise summary section")
        
        # Extract the relevant section
        summary_text = full_text[summary_start:]
        
        # Check if this is a tabular format (contains Trade Time, Order No, etc.)
        is_tabular_format = 'Trade Time' in summary_text and 'Order No' in summary_text
        
        # Extract order date from the document
        date_patterns = [
            r"Trade Date[:\s]+(\d{2}[-/]\d{2}[-/]\d{4})",
            r"Order Date[:\s]+(\d{2}[-/]\d{2}[-/]\d{4})",
            r"Date[:\s]+(\d{2}[-/]\d{2}[-/]\d{4})",
            r"(\d{2}[-/][a-z]{3}[-/]\d{4})"  # Handle dates like 31-jul-2024
        ]
        
        order_date = None
        for pattern in date_patterns:
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                date_str = match.group(1)
                try:
                    # Try different date formats
                    if re.match(r'\d{2}[-/][a-z]{3}[-/]\d{4}', date_str, re.IGNORECASE):
                        order_date = datetime.strptime(date_str, '%d-%b-%Y')
                    else:
                        order_date = datetime.strptime(date_str.replace('-', '/'), '%d/%m/%Y')
                    break
                except:
                    continue
        
        if not order_date:
            order_date = datetime.now()
        
        # Handle tabular format (individual trades with Order No, Trade Time, etc.)
        if is_tabular_format:
            return parse_tabular_format(summary_text, order_date, full_text)
        
        # Parse HDFC format transaction lines
        # Remove line breaks from summary text to make regex easier
        summary_clean = re.sub(r'\n+', ' ', summary_text)
        
        # Look for company names and extract transaction data
        # Pattern to find lines starting with "Equity" followed by company name
        equity_lines = re.findall(r'Equity([A-Z\s&\.\-]+?)(?=-Cash-|$)', summary_clean, re.IGNORECASE)
        
        # Alternative pattern for SELL format: Look for company names that come after transaction numbers
        # Use multiple passes to catch all transactions since they repeat the "Equity" pattern
        
        # Split by "Sub Total" to separate different transactions
        transaction_blocks = re.split(r'Sub Total', summary_clean)
        
        for block in transaction_blocks:
            if '-Cash-' in block:
                # Look for pattern in each block - some start with "Equity", others just have the transaction data
                sell_match = None
                
                # Try pattern with "Equity" prefix first
                if 'Equity' in block:
                    sell_match = re.search(r'Equity(\d+)\s+(\d+)\s+([\d,\.]+)\s+([\d,\.]+).*?([A-Z\s&\.\-]+?)\s+(?:LIMIT[ED]*|LI\s*MITED).*?-Cash-', block, re.IGNORECASE)
                
                # If no match, try pattern without "Equity" prefix (for subsequent transactions)
                if not sell_match:
                    sell_match = re.search(r'(\d+)\s+(\d+)\s+([\d,\.]+)\s+([\d,\.]+).*?([A-Z\s&\.\-]+?)\s+(?:LIMIT[ED]*|LI\s*MITED).*?-Cash-', block, re.IGNORECASE)
                if sell_match:
                    quantity_bought = int(sell_match.group(1))
                    quantity_sold = int(sell_match.group(2))
                    total_gross = float(sell_match.group(3))
                    average_rate = float(sell_match.group(4))
                    security_name = sell_match.group(5).strip()
                    
                    # Clean up security name
                    security_name = re.sub(r'\s+', ' ', security_name)
                    if not security_name.endswith('LIMITED') and not security_name.endswith('LTD'):
                        security_name += ' LIMITED'
                    
                    # Determine transaction type and quantity
                    if quantity_bought > 0:
                        transaction_type = "BUY"
                        quantity = quantity_bought
                        total_amount = total_gross
                    elif quantity_sold > 0:
                        transaction_type = "SELL"
                        quantity = quantity_sold
                        total_amount = total_gross
                    else:
                        continue  # Skip if no quantity
                    
                    # Try to determine security symbol from company name
                    security_symbol = None
                    if 'GREENPANEL' in security_name.upper():
                        security_symbol = 'GREENPANEL'
                    elif 'MUTHOOT' in security_name.upper():
                        security_symbol = 'MUTHOOTFIN'
                    elif 'WONDERLA' in security_name.upper():
                        security_symbol = 'WONDERLA'
                    elif 'CMS' in security_name.upper() or 'INFO SYSTEMS' in security_name.upper():
                        security_symbol = 'CMS'
                    
                    # Extract ISIN for this security
                    isin = extract_isin_from_text(full_text, security_name)
                    
                    # Enrich security data - fetch ticker when ISIN is available
                    enriched_data = enrich_security_data(
                        security_name=security_name,
                        ticker=security_symbol,
                        isin=isin
                    )
                    
                    transaction = {
                        'security_name': enriched_data.get('security_name', security_name),
                        'security_symbol': enriched_data.get('ticker', security_symbol),
                        'isin': enriched_data.get('isin', isin),
                        'transaction_type': transaction_type,
                        'quantity': quantity,
                        'price_per_unit': average_rate,
                        'total_amount': total_amount,
                        'transaction_date': order_date,
                        'order_date': order_date,
                        'exchange': 'NSE',
                        'broker_fees': 0.0,
                        'taxes': 0.0
                    }
                    
                    transactions.append(transaction)
        
        for company_name in equity_lines:
            security_name = company_name.strip()
            # Clean up security name
            security_name = re.sub(r'\s+', ' ', security_name)  # Normalize spaces
            
            # Try two different formats:
            # Format 1: Sub Total after company name (BUY format)
            company_pattern = re.escape(f'Equity{company_name}')
            sub_total_match = re.search(f'{company_pattern}.*?Sub Total\\s+(\\d+)\\s+(\\d+)([\\d,\\.]+)\\s+([\\d,\\.]+)', summary_clean, re.IGNORECASE)
            
            # Format 2: Company name after transaction numbers (SELL format)  
            sell_format_match = re.search(f'Equity(\\d+)\\s+(\\d+)\\s+([\\d,\\.]+)\\s+([\\d,\\.]+).*?{re.escape(company_name)}', summary_clean, re.IGNORECASE)
            
            if sub_total_match:
                # Format 1: BUY transactions
                quantity_bought = int(sub_total_match.group(1))
                # Handle the concatenated quantity_sold + total_gross (like "0116344.30")
                qty_sold_and_total = sub_total_match.group(2) + sub_total_match.group(3)
                average_rate = float(sub_total_match.group(4))
                
                # Split the concatenated string - qty sold is typically 1 digit, rest is total
                if len(qty_sold_and_total) > 1:
                    quantity_sold = int(qty_sold_and_total[0])  # First digit is qty sold
                    total_gross = float(qty_sold_and_total[1:])  # Rest is total gross
                else:
                    quantity_sold = int(qty_sold_and_total)
                    total_gross = 0.0
                    
            elif sell_format_match:
                # Format 2: SELL transactions - numbers come before company name
                quantity_bought = int(sell_format_match.group(1))
                quantity_sold = int(sell_format_match.group(2))
                total_gross = float(sell_format_match.group(3))
                average_rate = float(sell_format_match.group(4))
            else:
                continue  # No valid format found
                
            # Determine transaction type and quantity
            if quantity_bought > 0:
                transaction_type = "BUY"
                quantity = quantity_bought
                total_amount = total_gross
            elif quantity_sold > 0:
                transaction_type = "SELL"
                quantity = quantity_sold
                total_amount = total_gross
            else:
                continue  # Skip if no quantity
                
            # Try to determine security symbol from company name
            security_symbol = None
            if 'CMS' in security_name.upper() or 'INFO SYSTEMS' in security_name.upper():
                security_symbol = 'CMS'
            elif 'GREENPANEL' in security_name.upper():
                security_symbol = 'GREENPANEL'
            elif 'MUTHOOT' in security_name.upper():
                security_symbol = 'MUTHOOTFIN'
            elif 'WONDERLA' in security_name.upper():
                security_symbol = 'WONDERLA'
            elif 'LTD' in security_name.upper():
                # Try to extract symbol from company name (first few letters)
                words = security_name.split()
                if len(words) > 0:
                    security_symbol = ''.join([word[0] for word in words[:3] if word.upper() not in ['LTD', 'LIMITED', 'INC', 'CORP']])
            
            # Extract ISIN for this security
            isin = extract_isin_from_text(full_text, security_name)
            
            # Enrich security data - fetch ticker when ISIN is available
            enriched_data = enrich_security_data(
                security_name=security_name,
                ticker=security_symbol,
                isin=isin
            )
            
            transaction = {
                'security_name': enriched_data.get('security_name', security_name),
                'security_symbol': enriched_data.get('ticker', security_symbol),
                'isin': enriched_data.get('isin', isin),
                'transaction_type': transaction_type,
                'quantity': quantity,
                'price_per_unit': average_rate,
                'total_amount': total_amount,
                'transaction_date': order_date,
                'order_date': order_date,
                'exchange': 'NSE',
                'broker_fees': 0.0,
                'taxes': 0.0
            }
            
            transactions.append(transaction)
    
    except Exception as e:
        raise ValueError(f"Error parsing PDF: {str(e)}")
    
    return transactions


def parse_tabular_format(summary_text, order_date, full_text):
    """Parse tabular format PDFs with individual trade entries"""
    transactions = []
    
    # Clean the text
    summary_clean = re.sub(r'\n+', ' ', summary_text)
    
    # Parse the specific tabular format where data spans multiple lines
    # Look for entries like: S COMPANY_NAME\nLIMITED\n-Cash-INE...\nQUANTITY PRICE
    
    transactions_found = set()  # To avoid duplicates
    
    # Split into lines and process sequentially
    lines = summary_text.split('\n')
    i = 0
    while i < len(lines) - 3:
        line = lines[i].strip()
        
        # Look for transaction start: Order details + S/B COMPANY_NAME
        if re.match(r'\d+\s+\d+:\d+:\d+\s+\d+\s+\d+:\d+:\d+\s+([SB])\s+([A-Z\s]+)', line):
            match = re.match(r'\d+\s+\d+:\d+:\d+\s+\d+\s+\d+:\d+:\d+\s+([SB])\s+([A-Z\s]+)', line)
            if match:
                transaction_type_char = match.group(1)
                company_start = match.group(2).strip()
                
                # Get the next few lines to complete the company name and find quantity/price
                company_parts = [company_start]
                j = i + 1
                
                # Collect company name parts until we hit -Cash-
                while j < len(lines) and '-Cash-' not in lines[j]:
                    if lines[j].strip() and not re.match(r'^\d+\s+[\d.]+', lines[j]):
                        company_parts.append(lines[j].strip())
                    j += 1
                
                # Find the quantity/price line (after -Cash-)
                while j < len(lines):
                    qty_price_line = lines[j].strip()
                    qty_price_match = re.match(r'(\d+)\s+([\d.]+)', qty_price_line)
                    if qty_price_match:
                        # Extract the last 2-3 digits as quantity, rest as order/trade number
                        full_number = qty_price_match.group(1)
                        price = float(qty_price_match.group(2))
                        
                        # For TARSONS: 10231 -> quantity = 31, 10234 -> quantity = 34, etc.
                        if len(full_number) >= 3:
                            quantity = int(full_number[-2:])  # Last 2 digits
                        else:
                            quantity = int(full_number)
                        
                        # Build complete company name
                        security_name = ' '.join(company_parts)
                        security_name = re.sub(r'\s+', ' ', security_name).strip()
                        
                        # Clean up broken words and fix company names
                        security_name = re.sub(r'DIST RIBUTORS', 'DISTRIBUTORS', security_name)
                        security_name = re.sub(r'LIMI$', 'LIMITED', security_name)
                        security_name = re.sub(r'LIMIT$', 'LIMITED', security_name)
                        
                        if not security_name.endswith(('LIMITED', 'LTD')):
                            security_name += ' LIMITED'
                        
                        # Create unique key to avoid duplicates
                        transaction_key = (security_name, transaction_type_char, quantity, price)
                        
                        if transaction_key not in transactions_found:
                            transactions_found.add(transaction_key)
                            
                            transaction_type = "SELL" if transaction_type_char == 'S' else "BUY"
                            total_amount = quantity * price
                            
                            security_symbol = None
                            if 'TARSONS' in security_name.upper():
                                security_symbol = 'TARSONS'
                            elif 'DIGIDRIVE' in security_name.upper():
                                security_symbol = 'DIGIDRIVE' 
                            elif 'MANAPPURAM' in security_name.upper():
                                security_symbol = 'MANAPPURAM'
                            
                            # Extract ISIN for this security
                            isin = extract_isin_from_text(full_text, security_name)
                            
                            # Enrich security data - fetch ticker when ISIN is available
                            enriched_data = enrich_security_data(
                                security_name=security_name,
                                ticker=security_symbol,
                                isin=isin
                            )
                            
                            transaction = {
                                'security_name': enriched_data.get('security_name', security_name),
                                'security_symbol': enriched_data.get('ticker', security_symbol),
                                'isin': enriched_data.get('isin', isin),
                                'transaction_type': transaction_type,
                                'quantity': quantity,
                                'price_per_unit': price,
                                'total_amount': total_amount,
                                'transaction_date': order_date,
                                'order_date': order_date,
                                'exchange': 'BSE',
                                'broker_fees': 0.0,
                                'taxes': 0.0
                            }
                            
                            transactions.append(transaction)
                        
                        break
                    j += 1
        i += 1
    
    return transactions