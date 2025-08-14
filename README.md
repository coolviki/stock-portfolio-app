# Stock Portfolio Management App

A comprehensive stock portfolio management application built with Python (FastAPI) backend and React frontend. The app allows users to track their stock transactions, upload contract notes, and view portfolio analytics.

## 🌐 Live Demo

**[View Live Application](https://stock-portfolio-app-production.up.railway.app/)**

Experience the full application with all features including admin capabilities, portfolio analytics, and transaction management.

## Features

### 🚀 Core Features
- **Multi-user Support**: Create and manage multiple user portfolios
- **PDF Contract Note Upload**: Upload password-protected PDF contract notes for automatic transaction extraction
- **Manual Transaction Entry**: Add transactions manually with a user-friendly form
- **Portfolio Dashboard**: View realized and unrealized gains with interactive charts
- **Transaction Management**: Filter, edit, and export transaction history
- **Real-time Stock Prices**: Integration with stock market APIs for current prices
- **User Switching**: Switch between different user portfolios or view all users' data
- **Firebase Authentication**: Secure user authentication with Google Firebase

### 👑 Admin Features
- **🔐 Security Master**: Complete securities database management with CRUD operations
- **👥 Manager Users**: Admin user management with whitelist-based access control
- **⚙️ Admin Panel**: Database export/import functionality with admin verification
- **🎯 Role-based Access**: Conditional navigation and access control for admin features
- **📊 Admin Analytics**: Statistics and insights for system administrators

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
- **JWT & Firebase**: Authentication and authorization
- **Firebase Admin**: User management and token verification
- **Admin Utils**: Role-based access control and user management

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
- Firebase account (for authentication)

### Quick Start (Using Helper Scripts)

**Start Backend:**
```bash
./start-backend.sh
```

**Start Frontend:**
```bash
./start-frontend.sh
```

These scripts handle virtual environment setup, dependency installation, and server startup automatically.

### Manual Setup

#### Backend Setup

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

### Admin Access
- **Admin users** have access to Security Master, Manager Users, and Admin Panel
- Admin access is controlled by email whitelist (`admin_whitelist.json`)
- Admin-only features are marked with crown icons (👑) in the navigation
- Non-admin users see appropriate access denied messages for restricted features

## Configuration

### Environment Variables

#### Local Development
Create a `.env` file in the backend directory:

```env
# Database
DATABASE_URL=sqlite:///./stock_portfolio.db

# Security
SECRET_KEY=your-secret-key-here

# Firebase Backend Configuration (optional for local development)
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_PRIVATE_KEY_ID=your-private-key-id
FIREBASE_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----\nYour private key\n-----END PRIVATE KEY-----
FIREBASE_CLIENT_EMAIL=your-service-account@project.iam.gserviceaccount.com
FIREBASE_CLIENT_ID=your-client-id

# API Keys (optional)
ALPHA_VANTAGE_API_KEY=your-api-key
```

#### Frontend Environment Variables
Create a `.env` file in the frontend directory:

```env
# API Configuration
REACT_APP_API_URL=http://localhost:8000

# Firebase Frontend Configuration
REACT_APP_FIREBASE_API_KEY=your-frontend-api-key
REACT_APP_FIREBASE_AUTH_DOMAIN=your-project.firebaseapp.com
REACT_APP_FIREBASE_PROJECT_ID=your-project-id
REACT_APP_FIREBASE_STORAGE_BUCKET=your-project.appspot.com
REACT_APP_FIREBASE_MESSAGING_SENDER_ID=123456789
REACT_APP_FIREBASE_APP_ID=1:123456789:web:abcdef123456
```

#### Production Environment Variables (Railway)
Set these in Railway dashboard under Variables section. See the [Railway Deployment Setup](#railway-deployment-setup) section for complete list.

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

The application is deployed on **Railway** and accessible at: [https://stock-portfolio-app-production.up.railway.app/](https://stock-portfolio-app-production.up.railway.app/)

### Railway Deployment Setup

#### Step 1: Project Setup
1. **Fork/Clone the repository** to your GitHub account
2. **Connect to Railway**: 
   - Go to [railway.app](https://railway.app) and login with GitHub
   - Click "New Project" → "Deploy from GitHub repo"
   - Select your forked repository

#### Step 2: Configure Build Settings
Railway should automatically detect the project structure. If needed, configure:
- **Root Directory**: Leave empty (monorepo setup)
- **Build Command**: `cd frontend && npm run build`
- **Start Command**: `cd backend && python main.py`

#### Step 3: Environment Variables Setup

**Required Environment Variables in Railway:**

**Firebase Configuration:**
```bash
FIREBASE_PROJECT_ID=your-firebase-project-id
FIREBASE_PRIVATE_KEY_ID=your-private-key-id
FIREBASE_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----\nYour private key here\n-----END PRIVATE KEY-----
FIREBASE_CLIENT_EMAIL=your-service-account@project.iam.gserviceaccount.com
FIREBASE_CLIENT_ID=your-client-id
FIREBASE_AUTH_URI=https://accounts.google.com/o/oauth2/auth
FIREBASE_TOKEN_URI=https://oauth2.googleapis.com/token

# Frontend Firebase Config (for client-side)
REACT_APP_FIREBASE_API_KEY=your-frontend-api-key
REACT_APP_FIREBASE_AUTH_DOMAIN=your-project.firebaseapp.com
REACT_APP_FIREBASE_PROJECT_ID=your-firebase-project-id
REACT_APP_FIREBASE_STORAGE_BUCKET=your-project.appspot.com
REACT_APP_FIREBASE_MESSAGING_SENDER_ID=123456789
REACT_APP_FIREBASE_APP_ID=1:123456789:web:abcdef123456
```

**Application Configuration:**
```bash
# Database (Railway provides this automatically)
DATABASE_URL=postgresql://user:pass@host:port/db

# Security
SECRET_KEY=your-secret-key-here-make-it-long-and-random

# API Configuration
REACT_APP_API_URL=https://your-app-name.up.railway.app
```

#### Step 4: Firebase Setup

**Backend Firebase (Service Account):**
1. Go to [Firebase Console](https://console.firebase.google.com)
2. Select your project → Project Settings → Service Accounts
3. Click "Generate new private key" and download the JSON file
4. Extract the values and set them as Railway environment variables above

**Frontend Firebase (Web App):**
1. In Firebase Console → Project Settings → General
2. Scroll to "Your apps" section
3. Click "Web app" icon or add a new web app
4. Copy the config values and set them as REACT_APP_* variables in Railway

#### Step 5: Database Migration
Railway automatically provisions a PostgreSQL database. The app will create tables on first run.

#### Step 6: Admin User Setup
1. After deployment, access the app
2. Login with Google using your email
3. SSH into Railway container or use Railway CLI:
   ```bash
   railway shell
   ```
4. Add your email to admin whitelist:
   ```bash
   cd backend
   python -c "
   import json
   with open('admin_whitelist.json', 'w') as f:
       json.dump(['your-email@gmail.com'], f, indent=2)
   "
   ```

#### Step 7: Deploy and Verify
1. Railway automatically deploys when you push to GitHub
2. Check the deployment logs in Railway dashboard
3. Visit your app URL to verify everything works
4. Test admin features and Firebase authentication

### Common Railway Deployment Issues

**Build Failures:**
- Check that `frontend/package.json` and `backend/requirements.txt` exist
- Verify environment variables are set correctly
- Check Railway logs for specific error messages

**Firebase Authentication Errors:**
- Ensure all FIREBASE_* variables are set with correct values
- Verify REACT_APP_* variables are set (Railway needs the REACT_APP_ prefix)
- Check that Firebase project allows your Railway domain

**Admin Access Issues:**
- Verify your email is in `backend/admin_whitelist.json`
- Check that admin endpoints return correct permissions
- Test admin API endpoints using the `/docs` interface

### Alternative Deployment Options

#### Manual Deployment

**Backend Deployment:**
1. Set up a production database (PostgreSQL recommended)
2. Configure environment variables for production
3. Use a WSGI server like Gunicorn:
   ```bash
   gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app
   ```
4. Set up reverse proxy with Nginx

**Frontend Deployment:**
1. Build the React app: `npm run build`
2. Serve static files with a web server
3. Configure API endpoint for production

#### Docker Deployment
```dockerfile
# Example Dockerfile for backend
FROM python:3.9
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "main.py"]
```

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