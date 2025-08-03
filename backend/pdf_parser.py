import PyPDF2
import re
from datetime import datetime
from typing import List, Dict
import io

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
                    
                    transaction = {
                        'security_name': security_name,
                        'security_symbol': security_symbol,
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
            
            transaction = {
                'security_name': security_name,
                'security_symbol': security_symbol,
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

def extract_table_data(text: str) -> List[Dict]:
    """
    Alternative method to extract tabular data from contract notes
    """
    lines = text.split('\n')
    transactions = []
    
    # Look for table headers
    header_patterns = [
        r'Security.*Buy.*Sell.*Quantity.*Rate.*Amount',
        r'Script.*Type.*Qty.*Price.*Value'
    ]
    
    table_start = -1
    for i, line in enumerate(lines):
        for pattern in header_patterns:
            if re.search(pattern, line, re.IGNORECASE):
                table_start = i + 1
                break
        if table_start != -1:
            break
    
    if table_start == -1:
        return transactions
    
    # Parse table rows
    for i in range(table_start, len(lines)):
        line = lines[i].strip()
        if not line or line.startswith('Total') or line.startswith('Grand'):
            break
        
        # Split by multiple spaces (assuming tabular format)
        parts = re.split(r'\s{2,}', line)
        if len(parts) >= 5:
            try:
                security_name = parts[0]
                transaction_type = 'BUY' if 'buy' in parts[1].lower() else 'SELL'
                quantity = float(re.findall(r'\d+(?:\.\d+)?', parts[2])[0])
                price = float(re.findall(r'\d+(?:\.\d+)?', parts[3])[0])
                amount = float(re.findall(r'\d+(?:\.\d+)?', parts[4])[0])
                
                transaction = {
                    'security_name': security_name,
                    'security_symbol': None,
                    'transaction_type': transaction_type,
                    'quantity': quantity,
                    'price_per_unit': price,
                    'total_amount': amount,
                    'transaction_date': datetime.now(),
                    'order_date': datetime.now(),
                    'exchange': 'NSE',
                    'broker_fees': 0.0,
                    'taxes': 0.0
                }
                
                transactions.append(transaction)
            except (ValueError, IndexError):
                continue
    
    return transactions