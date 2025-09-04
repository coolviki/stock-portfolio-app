import React, { useState, useEffect } from 'react';
import { Row, Col, Card, Table, Badge, Spinner, OverlayTrigger, Tooltip } from 'react-bootstrap';
import { Chart as ChartJS, ArcElement, Tooltip as ChartTooltip, Legend, CategoryScale, LinearScale, BarElement, Title } from 'chart.js';
import { Doughnut, Bar } from 'react-chartjs-2';
import { apiService } from '../services/apiService';
import { useAuth } from '../context/AuthContext';
import { toast } from 'react-toastify';
import { fetchStockPriceBySymbol, fetchStockPriceByIsin } from '../utils/apiUtils';

ChartJS.register(ArcElement, ChartTooltip, Legend, CategoryScale, LinearScale, BarElement, Title);

const Dashboard = () => {
  const [portfolio, setPortfolio] = useState(null);
  const [loading, setLoading] = useState(true);
  const [priceData, setPriceData] = useState({});
  const [loadingPrice, setLoadingPrice] = useState({});
  const { user } = useAuth();

  const fetchSecurityPrice = async (ticker, isin) => {
    const securityKey = ticker;
    
    // Don't fetch if already loading
    if (loadingPrice[securityKey]) {
      return;
    }

    setLoadingPrice(prev => ({ ...prev, [securityKey]: true }));
    
    try {
      let price = null;
      let method = '';
      let timestamp = new Date().toLocaleString('en-IN');

      // Try waterfall price fetching: TICKER → ISIN → Security Name
      if (ticker) {
        try {
          const response = await fetchStockPriceBySymbol(ticker);
          if (response.ok) {
            const data = await response.json();
            price = data.price;
            method = 'TICKER';
          }
        } catch (error) {
          console.log('Ticker price fetch failed:', error);
        }
      }

      // Fallback to ISIN if ticker failed
      if (!price && isin) {
        try {
          const response = await fetchStockPriceByIsin(isin);
          if (response.ok) {
            const data = await response.json();
            price = data.price;
            method = 'ISIN';
          }
        } catch (error) {
          console.log('ISIN price fetch failed:', error);
        }
      }

      // Store the price data
      setPriceData(prev => ({
        ...prev,
        [securityKey]: {
          price: price || 'N/A',
          method,
          timestamp,
          symbol: ticker || 'N/A',
          error: !price
        }
      }));

    } catch (error) {
      console.error('Error fetching price:', error);
      setPriceData(prev => ({
        ...prev,
        [securityKey]: {
          price: 'Error',
          method: 'ERROR',
          timestamp: new Date().toLocaleString('en-IN'),
          symbol: ticker || 'N/A',
          error: true
        }
      }));
    } finally {
      setLoadingPrice(prev => ({ ...prev, [securityKey]: false }));
    }
  };

  const handleSecurityNameClick = (ticker, isin) => {
    fetchSecurityPrice(ticker, isin);
  };

  const renderPriceTooltip = (tickerSymbol, isin, securityName) => {
    const securityKey = tickerSymbol;
    const loading = loadingPrice[securityKey];
    const data = priceData[securityKey];

    if (loading) {
      return (
        <Tooltip id={`price-tooltip-${securityKey}`}>
          <div className="text-center">
            <Spinner animation="border" size="sm" className="me-2" />
            Fetching price...
          </div>
        </Tooltip>
      );
    }

    if (!data) {
      return (
        <Tooltip id={`price-tooltip-${securityKey}`}>
          <div>
            <strong>📈 Click to fetch latest price</strong>
            <br />
            <small>Price will be fetched using waterfall method:<br />
            1. Ticker Symbol ({tickerSymbol || 'N/A'})<br />
            2. ISIN Code ({isin || 'N/A'})<br />
            3. Fallback pricing</small>
          </div>
        </Tooltip>
      );
    }

    return (
      <Tooltip id={`price-tooltip-${securityKey}`}>
        <div>
          <strong>💰 Latest Price Information</strong>
          <hr className="my-2" style={{borderColor: '#fff'}} />
          <div><strong>Security:</strong> {securityName}</div>
          <div><strong>Symbol:</strong> {data.symbol}</div>
          <div><strong>Price:</strong> {data.error ? '❌ Unable to fetch' : `₹${parseFloat(data.price).toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`}</div>
          <div><strong>Method:</strong> {data.method || 'FALLBACK'}</div>
          <div><strong>Updated:</strong> {data.timestamp}</div>
          {!data.error && (
            <small className="text-light">
              <br />💡 Click again to refresh price
            </small>
          )}
        </div>
      </Tooltip>
    );
  };

  useEffect(() => {
    loadPortfolioData();
  }, [user]);

  const loadPortfolioData = async () => {
    try {
      setLoading(true);
      if (!user?.id) {
        toast.error('User not logged in');
        return;
      }
      const data = await apiService.getPortfolioSummary(user.id);
      setPortfolio(data);
    } catch (error) {
      toast.error('Unable to load Portfolio Data');
      console.error('Error loading portfolio:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="d-flex justify-content-center align-items-center" style={{ height: '400px' }}>
        <Spinner animation="border" variant="primary" />
      </div>
    );
  }

  if (!portfolio) {
    return (
      <div className="text-center mt-5">
        <h4>No portfolio data available</h4>
        <p>Start by adding some transactions!</p>
      </div>
    );
  }

  const totalInvested = Object.values(portfolio.portfolio || {}).reduce(
    (sum, stock) => sum + stock.total_invested, 0
  );
  
  const currentValue = Object.values(portfolio.current_values || {}).reduce(
    (sum, value) => sum + value, 0
  );

  const totalGains = portfolio.realized_gains + portfolio.unrealized_gains;
  const totalGainsPercent = totalInvested > 0 ? (totalGains / totalInvested) * 100 : 0;

  // Chart data for portfolio allocation
  const portfolioLabels = Object.keys(portfolio.portfolio || {}).filter(
    symbol => portfolio.portfolio[symbol].quantity > 0
  );
  const portfolioData = {
    labels: portfolioLabels,
    datasets: [
      {
        data: portfolioLabels.map(symbol => portfolio.current_values[symbol] || 0),
        backgroundColor: [
          '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF',
          '#FF9F40', '#FF6384', '#C9CBCF', '#4BC0C0', '#FF6384'
        ],
        borderWidth: 2,
        borderColor: '#fff'
      }
    ]
  };

  // Gains/Losses chart
  const gainsData = {
    labels: ['Realized Gains', 'Unrealized Gains'],
    datasets: [
      {
        label: 'Amount (₹)',
        data: [portfolio.realized_gains, portfolio.unrealized_gains],
        backgroundColor: [
          portfolio.realized_gains >= 0 ? '#28a745' : '#dc3545',
          portfolio.unrealized_gains >= 0 ? '#28a745' : '#dc3545'
        ],
        borderColor: [
          portfolio.realized_gains >= 0 ? '#1e7e34' : '#bd2130',
          portfolio.unrealized_gains >= 0 ? '#1e7e34' : '#bd2130'
        ],
        borderWidth: 1
      }
    ]
  };

  return (
    <div>
      <h2 className="mb-4 d-flex align-items-center">
        <img src="/images/analytics.svg" alt="Portfolio Analytics" style={{width: '2.5rem', height: '2.5rem', marginRight: '0.5rem'}} />
        Portfolio Dashboard
      </h2>
      
      {/* Summary Cards */}
      <Row className="mb-4">
        <Col md={3}>
          <Card className="card-stat text-center h-100">
            <Card.Body>
              <h5>Total Invested</h5>
              <h3>₹{totalInvested.toLocaleString('en-IN')}</h3>
            </Card.Body>
          </Card>
        </Col>
        <Col md={3}>
          <Card className="card-stat text-center h-100">
            <Card.Body>
              <h5>Current Value</h5>
              <h3>₹{currentValue.toLocaleString('en-IN')}</h3>
            </Card.Body>
          </Card>
        </Col>
        <Col md={3}>
          <Card className={`card-stat text-center h-100 ${totalGains >= 0 ? 'profit' : 'loss'}`}>
            <Card.Body>
              <h5>Total P&L</h5>
              <h3>₹{totalGains.toLocaleString('en-IN')}</h3>
              <small>{totalGainsPercent.toFixed(2)}%</small>
            </Card.Body>
          </Card>
        </Col>
        <Col md={3}>
          <Card className="card-stat text-center h-100">
            <Card.Body>
              <h5>Holdings</h5>
              <h3>{portfolioLabels.length}</h3>
              <small>Securities</small>
            </Card.Body>
          </Card>
        </Col>
      </Row>

      <Row className="mb-4">
        <Col md={6}>
          <Card>
            <Card.Header>
              <h5>Portfolio Allocation</h5>
            </Card.Header>
            <Card.Body>
              {portfolioLabels.length > 0 ? (
                <Doughnut 
                  data={portfolioData} 
                  options={{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                      legend: {
                        position: 'bottom'
                      }
                    }
                  }}
                  height={300}
                />
              ) : (
                <p className="text-center text-muted">No current holdings</p>
              )}
            </Card.Body>
          </Card>
        </Col>
        
        <Col md={6}>
          <Card>
            <Card.Header>
              <h5>Gains/Losses Breakdown</h5>
            </Card.Header>
            <Card.Body>
              <Bar 
                data={gainsData}
                options={{
                  responsive: true,
                  maintainAspectRatio: false,
                  plugins: {
                    legend: {
                      display: false
                    }
                  },
                  scales: {
                    y: {
                      beginAtZero: true,
                      ticks: {
                        callback: function(value) {
                          return '₹' + value.toLocaleString('en-IN');
                        }
                      }
                    }
                  }
                }}
                height={300}
              />
            </Card.Body>
          </Card>
        </Col>
      </Row>

      {/* Holdings Table */}
      <Card>
        <Card.Header>
          <div className="d-flex justify-content-between align-items-center">
            <h5>Current Holdings</h5>
            <small className="text-muted">💡 Click on security names to see current prices</small>
          </div>
        </Card.Header>
        <Card.Body>
          <div className="table-responsive">
            <Table striped hover>
              <thead>
                <tr>
                  <th>Security</th>
                  <th>Quantity</th>
                  <th>Avg. Price</th>
                  <th>Current Price</th>
                  <th>Invested</th>
                  <th>Current Value</th>
                  <th>P&L</th>
                  <th>P&L %</th>
                </tr>
              </thead>
              <tbody>
                {portfolioLabels.map(symbol => {
                  const stock = portfolio.portfolio[symbol];
                  const currentValue = portfolio.current_values[symbol] || 0;
                  const currentPrice = stock.quantity > 0 ? currentValue / stock.quantity : 0;
                  const avgPrice = stock.quantity > 0 ? stock.total_invested / stock.quantity : 0;
                  const pnl = currentValue - stock.total_invested;
                  const pnlPercent = stock.total_invested > 0 ? (pnl / stock.total_invested) * 100 : 0;

                  return (
                    <tr key={symbol}>
                      <td>
                        <OverlayTrigger
                          placement="top"
                          delay={{ show: 250, hide: 400 }}
                          overlay={renderPriceTooltip(stock.security_symbol || symbol, stock.isin, symbol)}
                          trigger={['hover', 'focus']}
                        >
                          <strong 
                            style={{
                              color: '#0d6efd',
                              cursor: 'pointer',
                              textDecoration: 'underline',
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '4px'
                            }}
                            onClick={() => handleSecurityNameClick(stock.security_symbol || symbol, stock.isin)}
                            title={`Click to fetch current price for ${symbol}`}
                            onMouseEnter={(e) => e.target.style.color = '#0a58ca'}
                            onMouseLeave={(e) => e.target.style.color = '#0d6efd'}
                          >
                            {symbol}
                            {loadingPrice[stock.security_symbol || symbol] ? (
                              <Spinner animation="border" size="sm" />
                            ) : (
                              '📈'
                            )}
                          </strong>
                        </OverlayTrigger>
                      </td>
                      <td>{stock.quantity}</td>
                      <td>₹{avgPrice.toFixed(2)}</td>
                      <td>₹{currentPrice.toFixed(2)}</td>
                      <td>₹{stock.total_invested.toLocaleString('en-IN')}</td>
                      <td>₹{currentValue.toLocaleString('en-IN')}</td>
                      <td className={pnl >= 0 ? 'profit' : 'loss'}>
                        ₹{pnl.toLocaleString('en-IN')}
                      </td>
                      <td>
                        <Badge bg={pnlPercent >= 0 ? 'success' : 'danger'}>
                          {pnlPercent.toFixed(2)}%
                        </Badge>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </Table>
          </div>
          
          {portfolioLabels.length === 0 && (
            <p className="text-center text-muted mt-3">No current holdings</p>
          )}
        </Card.Body>
      </Card>
    </div>
  );
};

export default Dashboard;