# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a multi-user stock portfolio management application with Python FastAPI backend and React frontend. The app enables users to track stock transactions through manual entry or automated PDF contract note parsing, view portfolio analytics, and manage real-time stock pricing with ISIN support.

## Development Commands

### Backend Development
```bash
# Start backend (handles venv setup, dependencies, and server)
./start-backend.sh

# Manual backend setup
cd backend
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

### Frontend Development
```bash
# Start frontend (handles npm install and dev server)
./start-frontend.sh

# Manual frontend setup
cd frontend
npm install
npm start      # Development server
npm run build  # Production build
npm test       # Run tests
```

### Database Operations
```bash
# Run database migrations (when adding new columns)
cd backend
python add_isin_migration.py  # Example: adds ISIN column

# Access database directly
sqlite3 stock_portfolio.db
```

## Architecture Overview

### Backend Architecture (`backend/`)
- **FastAPI Application** (`main.py`): REST API with auto-generated docs at `/docs`
- **Database Models** (`models.py`): SQLAlchemy ORM models for Users and Transactions
- **Pydantic Schemas** (`schemas.py`): Request/response validation and serialization
- **PDF Processing** (`pdf_parser.py`): Extracts transaction data from encrypted broker PDFs
- **Stock Price API** (`stock_api.py`): ISIN-aware stock pricing with fallback mechanisms
- **Database Layer** (`database.py`): SQLAlchemy configuration and session management

### Frontend Architecture (`frontend/src/`)
- **React Router** navigation with protected routes
- **Context API** (`context/AuthContext.js`): Global user state management
- **API Services** (`services/`): Centralized HTTP client for backend communication
- **Page Components** (`pages/`): Full-page views (Dashboard, Transactions, Upload, etc.)
- **Shared Components** (`components/`): Reusable UI components (Navbar, Sidebar)

### Key Data Flow
1. **Transaction Entry**: Manual form OR PDF upload → PDF parser → Transaction validation → Database
2. **Portfolio Calculation**: Retrieve transactions → Group by security → Fetch real-time prices (ISIN→Symbol→Price) → Calculate P&L
3. **User Management**: Simple username-based system (no authentication) with user switching

## Database Schema

### Core Tables
- **users**: `id`, `username`, `created_at`
- **transactions**: `id`, `user_id`, `security_name`, `security_symbol`, `isin`, `transaction_type` (BUY/SELL), `quantity`, `price_per_unit`, `total_amount`, `transaction_date`, `order_date`, `exchange`, `broker_fees`, `taxes`

### ISIN Integration
The system uses International Securities Identification Numbers (ISIN) for accurate stock pricing:
- ISIN stored in transactions table for precise security identification
- `stock_api.py` contains ISIN-to-symbol mapping for Indian stocks
- Price fetching priority: ISIN → Symbol → Hash-based fallback

## Stock Price System

### Price Fetching Strategy
1. **ISIN Lookup**: Check `ISIN_TO_SYMBOL` mapping in `stock_api.py`
2. **Yahoo Finance API**: Attempt real-time price fetch with symbol
3. **Mock Prices**: Fallback to hardcoded prices for known stocks
4. **Hash Fallback**: Generate consistent price based on security identifier hash

### Adding New Securities
To support new stocks, update `stock_api.py`:
```python
ISIN_TO_SYMBOL = {
    'INE925R01014': 'CMS',  # Example: CMS Info Systems
    # Add new ISIN mappings here
}

mock_prices = {
    'CMS': 452.00,  # Add current market prices
    # Add new stock prices here
}
```

## PDF Contract Note Processing

### Supported Formats
- Password-protected Indian broker PDFs
- Extracts from "scrip wise summary" sections
- Handles multiple transaction formats (tabular and block text)
- Automatically extracts ISIN codes from PDF content

### Parser Logic (`pdf_parser.py`)
1. **PDF Decryption**: Uses PyPDF2 with provided password
2. **Section Detection**: Locates transaction summary sections
3. **Data Extraction**: Regex patterns for security names, quantities, prices
4. **ISIN Extraction**: `extract_isin_from_text()` finds ISIN codes near security names
5. **Transaction Creation**: Builds transaction objects with all required fields

## Frontend State Management

### User Context (`AuthContext.js`)
- `selectedUserId`: Currently active user for portfolio display
- `isAllUsers`: Toggle for viewing all users vs single user
- User switching functionality across all components

### API Integration (`apiService.js`)
- Centralized HTTP client with base URL configuration
- Methods for all backend endpoints (transactions, users, portfolio, uploads)
- Error handling and response formatting

## Key Features Implementation

### Multi-User Portfolio
- Users created by entering username (auto-creates if new)
- Portfolio calculations isolated per user
- Admin view aggregates across all users

### Real-Time Portfolio Analytics
- `get_portfolio_summary()` endpoint calculates:
  - Current holdings with live prices
  - Realized gains from completed SELL transactions
  - Unrealized gains from current holdings
  - Portfolio allocation percentages

### Transaction Management
- CRUD operations with optimistic UI updates
- Edit mode with form validation
- Bulk upload via PDF processing
- Date filtering and search capabilities

## Testing and Debugging

### API Testing
- FastAPI auto-docs at `http://localhost:8000/docs`
- Test endpoints directly or use curl/Postman
- Database inspection: `sqlite3 stock_portfolio.db`

### Frontend Debugging
- React DevTools for component inspection
- Network tab for API call monitoring
- Console logs in browser developer tools

### Common Issues
- **PDF Upload Failures**: Check password and PDF format compatibility
- **Price Fetching Errors**: Verify ISIN mapping or add to mock prices
- **Database Errors**: Run migration scripts or check schema compatibility

## Production Considerations

### Database Migration
- Run `add_isin_migration.py` for existing deployments
- Consider PostgreSQL for production (SQLite for development)
- Backup database before schema changes

### Environment Variables
Create `.env` in backend directory:
```env
DATABASE_URL=sqlite:///./stock_portfolio.db
SECRET_KEY=your-secret-key-here
# Add production API keys as needed
```

### Security Notes
- Currently uses simplified user system (username-only)
- Contract note passwords handled in-memory only
- ISIN data improves price accuracy and reduces API dependencies