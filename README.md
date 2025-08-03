# Stock Portfolio Management App

A comprehensive stock portfolio management application built with Python (FastAPI) backend and React frontend. The app allows users to track their stock transactions, upload contract notes, and view portfolio analytics.

## Features

### 🚀 Core Features
- **Multi-user Support**: Create and manage multiple user portfolios
- **PDF Contract Note Upload**: Upload password-protected PDF contract notes for automatic transaction extraction
- **Manual Transaction Entry**: Add transactions manually with a user-friendly form
- **Portfolio Dashboard**: View realized and unrealized gains with interactive charts
- **Transaction Management**: Filter, edit, and export transaction history
- **Real-time Stock Prices**: Integration with stock market APIs for current prices
- **User Switching**: Switch between different user portfolios or view all users' data

### 📊 Dashboard Features
- Portfolio allocation pie chart
- Gains/losses breakdown
- Current holdings table with P&L calculations
- Summary cards for key metrics

### 📱 User Interface
- Responsive design with Bootstrap
- Interactive charts using Chart.js
- Modern sidebar navigation
- Toast notifications for user feedback

## Technology Stack

### Backend
- **FastAPI**: Modern Python web framework
- **SQLAlchemy**: SQL toolkit and ORM
- **PostgreSQL/SQLite**: Database options
- **PyPDF2**: PDF processing for contract notes
- **Pydantic**: Data validation
- **JWT**: Authentication and authorization

### Frontend
- **React 18**: Modern React with hooks
- **React Router**: Client-side routing
- **Bootstrap 5**: CSS framework
- **Chart.js**: Interactive charts
- **Axios**: HTTP client
- **React DatePicker**: Date selection components

## Installation and Setup

### Prerequisites
- Python 3.8+
- Node.js 16+
- npm or yarn

### Backend Setup

1. Navigate to the backend directory:
```bash
cd backend
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install Python dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
cp .env.example .env
# Edit .env file with your configuration
```

5. Run the backend server:
```bash
python main.py
```

The API will be available at `http://localhost:8000`

### Frontend Setup

1. Navigate to the frontend directory:
```bash
cd frontend
```

2. Install Node.js dependencies:
```bash
npm install
```

3. Start the development server:
```bash
npm start
```

The app will be available at `http://localhost:3000`

## API Documentation

Once the backend is running, you can access the interactive API documentation at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Database Schema

### Users Table
- `id`: Primary key
- `username`: Unique username
- `email`: User email
- `hashed_password`: Encrypted password
- `is_active`: User status
- `created_at`: Registration timestamp

### Transactions Table
- `id`: Primary key
- `user_id`: Foreign key to users
- `security_name`: Name of the security
- `security_symbol`: Stock symbol
- `transaction_type`: BUY or SELL
- `quantity`: Number of shares
- `price_per_unit`: Price per share
- `total_amount`: Total transaction amount
- `transaction_date`: Date of transaction
- `order_date`: Date of order
- `exchange`: Stock exchange (NSE, BSE, etc.)
- `broker_fees`: Brokerage fees
- `taxes`: Applicable taxes

## PDF Contract Note Processing

The application can process password-protected PDF contract notes from Indian stock brokers. The system:

1. Accepts multiple PDF files with password protection
2. Extracts transaction data from the "scrip wise summary" section
3. Parses security names, quantities, prices, and amounts
4. Automatically creates transaction records
5. Provides preview and confirmation before saving

### Supported PDF Formats
- Standard Indian broker contract notes
- Password-protected PDFs
- Tabular data extraction
- Multiple securities per contract note

## Usage Guide

### Getting Started
1. Register a new account or login
2. Use the sidebar to navigate between different sections
3. Start by adding transactions manually or uploading contract notes

### Adding Transactions
- **Manual Entry**: Use the manual entry form for individual transactions
- **PDF Upload**: Upload contract notes for bulk transaction import
- **Edit/Delete**: Modify existing transactions from the transactions page

### Viewing Portfolio
- **Dashboard**: Overview of your portfolio performance
- **Transactions**: Detailed transaction history with filters
- **Multi-user**: Switch between users or view all users' data

### User Management
- Create new users from the Users page
- Switch between user portfolios using the top navigation
- View system-wide statistics

## Configuration

### Environment Variables
Create a `.env` file in the backend directory:

```env
# Database
DATABASE_URL=sqlite:///./stock_portfolio.db

# Security
SECRET_KEY=your-secret-key-here

# API Keys (optional)
ALPHA_VANTAGE_API_KEY=your-api-key
```

### Database Configuration
- **SQLite**: Default option, good for development
- **PostgreSQL**: Recommended for production

## Development

### Running Tests
```bash
# Backend tests
cd backend
python -m pytest

# Frontend tests
cd frontend
npm test
```

### Code Structure
```
stock-portfolio-app/
├── backend/
│   ├── main.py              # FastAPI application
│   ├── models.py            # Database models
│   ├── schemas.py           # Pydantic schemas
│   ├── database.py          # Database configuration
│   ├── auth.py              # Authentication logic
│   ├── pdf_parser.py        # PDF processing
│   └── stock_api.py         # Stock price API
├── frontend/
│   ├── src/
│   │   ├── components/      # Reusable components
│   │   ├── pages/           # Page components
│   │   ├── services/        # API services
│   │   └── context/         # React context
│   └── public/
└── contractnotes/           # Sample PDFs (not in git)
```

## Deployment

### Backend Deployment
1. Set up a production database (PostgreSQL recommended)
2. Configure environment variables for production
3. Use a WSGI server like Gunicorn
4. Set up reverse proxy with Nginx

### Frontend Deployment
1. Build the React app: `npm run build`
2. Serve static files with a web server
3. Configure API endpoint for production

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues and questions:
1. Check the existing issues on GitHub
2. Create a new issue with detailed description
3. Include steps to reproduce any bugs

## Future Enhancements

- [ ] Advanced portfolio analytics
- [ ] Email notifications
- [ ] Mobile app
- [ ] Advanced PDF parsing
- [ ] Integration with more brokers
- [ ] Tax calculation features
- [ ] Dividend tracking
- [ ] Portfolio rebalancing suggestions

---

Built with ❤️ using FastAPI and React