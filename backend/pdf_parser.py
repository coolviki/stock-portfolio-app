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
            r"scrip wise summary",
            r"Script wise summary",
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
            r"Order Date[:\s]+(\d{2}[-/]\d{2}[-/]\d{4})",
            r"Trade Date[:\s]+(\d{2}[-/]\d{2}[-/]\d{4})",
            r"Date[:\s]+(\d{2}[-/]\d{2}[-/]\d{4})"
        ]
        
        order_date = None
        for pattern in date_patterns:
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                date_str = match.group(1)
                try:
                    order_date = datetime.strptime(date_str.replace('-', '/'), '%d/%m/%Y')
                    break
                except:
                    continue
        
        if not order_date:
            order_date = datetime.now()
        
        # Parse transaction lines
        # Look for patterns like:
        # SECURITY_NAME BUY/SELL QUANTITY PRICE AMOUNT
        transaction_pattern = r'([A-Z\s&]+(?:LTD|LIMITED|CORP|INC)?)\s+(BUY|SELL)\s+(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)'
        
        matches = re.findall(transaction_pattern, summary_text, re.IGNORECASE)
        
        for match in matches:
            security_name = match[0].strip()
            transaction_type = match[1].upper()
            quantity = float(match[2])
            price_per_unit = float(match[3])
            total_amount = float(match[4])
            
            # Extract security symbol if available (usually in parentheses)
            symbol_match = re.search(r'\(([A-Z0-9]+)\)', security_name)
            security_symbol = symbol_match.group(1) if symbol_match else None
            
            # Clean security name
            security_name = re.sub(r'\([^)]*\)', '', security_name).strip()
            
            transaction = {
                'security_name': security_name,
                'security_symbol': security_symbol,
                'transaction_type': transaction_type,
                'quantity': quantity,
                'price_per_unit': price_per_unit,
                'total_amount': total_amount,
                'transaction_date': order_date,
                'order_date': order_date,
                'exchange': 'NSE',  # Default, can be extracted if available
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