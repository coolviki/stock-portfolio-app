import React, { useState, useEffect } from 'react';
import { Row, Col, Card, Table, Spinner, ButtonGroup, Button } from 'react-bootstrap';
import { Chart as ChartJS, ArcElement, Tooltip as ChartTooltip, Legend, CategoryScale, LinearScale, BarElement, Title } from 'chart.js';
import { Doughnut, Bar } from 'react-chartjs-2';
import { apiService } from '../services/apiService';
import { useAuth } from '../context/AuthContext';
import { toast } from 'react-toastify';

ChartJS.register(ArcElement, ChartTooltip, Legend, CategoryScale, LinearScale, BarElement, Title);

const Dashboard = () => {
  const [portfolio, setPortfolio] = useState(null);
  const [marketIndices, setMarketIndices] = useState(null);
  const [loading, setLoading] = useState(true);
  const [sortConfig, setSortConfig] = useState({ key: 'symbol', direction: 'asc' });
  const { user } = useAuth();



  useEffect(() => {
    loadPortfolioData();
    loadMarketIndices();
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

  const loadMarketIndices = async () => {
    try {
      const data = await apiService.getMarketIndices();
      setMarketIndices(data);
    } catch (error) {
      console.error('Error loading market indices:', error);
    }
  };

  const handleSort = (key) => {
    setSortConfig(prev => ({
      key,
      direction: prev.key === key && prev.direction === 'asc' ? 'desc' : 'asc'
    }));
  };

  const getSortedHoldings = (holdings, currentValues, portfolioData) => {
    const holdingsArray = holdings.map(symbol => {
      const stock = portfolioData.portfolio[symbol];
      const currentVal = currentValues[symbol] || 0;
      const pnl = currentVal - stock.total_invested;
      const pnlPercent = stock.total_invested > 0 ? (pnl / stock.total_invested) * 100 : 0;
      const dailyChange = stock.todays_change || 0;
      const dailyChangePercent = stock.change_percent || 0;
      return { symbol, stock, currentVal, pnl, pnlPercent, dailyChange, dailyChangePercent };
    });

    return holdingsArray.sort((a, b) => {
      let aVal, bVal;
      switch (sortConfig.key) {
        case 'pnl':
          aVal = a.pnl;
          bVal = b.pnl;
          break;
        case 'pnlPercent':
          aVal = a.pnlPercent;
          bVal = b.pnlPercent;
          break;
        case 'dayPnl':
          aVal = a.dailyChange;
          bVal = b.dailyChange;
          break;
        case 'dayPnlPercent':
          aVal = a.dailyChangePercent;
          bVal = b.dailyChangePercent;
          break;
        default:
          aVal = a.symbol;
          bVal = b.symbol;
          return sortConfig.direction === 'asc'
            ? aVal.localeCompare(bVal)
            : bVal.localeCompare(aVal);
      }
      return sortConfig.direction === 'asc' ? aVal - bVal : bVal - aVal;
    });
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

  // Today's change data
  const todaysChange = portfolio.todays_change || 0;
  const todaysChangePercent = portfolio.todays_change_percent || 0;

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

  const sortedHoldings = getSortedHoldings(portfolioLabels, portfolio.current_values, portfolio);

  return (
    <div className="dashboard-container">
      {/* Header - simplified on mobile */}
      <h2 className="mb-3 mb-md-4 d-flex align-items-center">
        <img src="/images/analytics.svg" alt="Portfolio Analytics" className="d-none d-sm-block" style={{width: '2.5rem', height: '2.5rem', marginRight: '0.5rem'}} />
        <span className="d-none d-sm-inline">Portfolio Dashboard</span>
        <span className="d-sm-none">Dashboard</span>
      </h2>

      {/* Market Indices - Mobile prominent display */}
      {marketIndices && (
        <Row className="mb-3 g-2">
          <Col xs={6}>
            <div className="market-index-card">
              <div className="d-flex justify-content-between align-items-center">
                <span className="index-name">SENSEX</span>
                <span className={`index-change ${marketIndices.SENSEX?.change >= 0 ? 'positive' : 'negative'}`}>
                  {marketIndices.SENSEX?.change >= 0 ? '▲' : '▼'} {Math.abs(marketIndices.SENSEX?.change_percent || 0).toFixed(2)}%
                </span>
              </div>
              <div className="index-value">
                {(marketIndices.SENSEX?.value || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
              </div>
              <div className={`index-change-value ${marketIndices.SENSEX?.change >= 0 ? 'positive' : 'negative'}`}>
                {marketIndices.SENSEX?.change >= 0 ? '+' : ''}{(marketIndices.SENSEX?.change || 0).toFixed(2)}
              </div>
            </div>
          </Col>
          <Col xs={6}>
            <div className="market-index-card">
              <div className="d-flex justify-content-between align-items-center">
                <span className="index-name">NIFTY 50</span>
                <span className={`index-change ${marketIndices.NIFTY?.change >= 0 ? 'positive' : 'negative'}`}>
                  {marketIndices.NIFTY?.change >= 0 ? '▲' : '▼'} {Math.abs(marketIndices.NIFTY?.change_percent || 0).toFixed(2)}%
                </span>
              </div>
              <div className="index-value">
                {(marketIndices.NIFTY?.value || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
              </div>
              <div className={`index-change-value ${marketIndices.NIFTY?.change >= 0 ? 'positive' : 'negative'}`}>
                {marketIndices.NIFTY?.change >= 0 ? '+' : ''}{(marketIndices.NIFTY?.change || 0).toFixed(2)}
              </div>
            </div>
          </Col>
        </Row>
      )}

      {/* Summary Cards - Compact and sleek on mobile */}
      <Row className="mb-3 mb-md-4 g-2">
        <Col xs={6} md={3} lg={true}>
          <Card className="card-stat-new invested text-center h-100 border-0">
            <Card.Body className="py-2 px-2">
              <small className="stat-label">Invested</small>
              <div className="stat-value">₹{totalInvested.toLocaleString('en-IN', {maximumFractionDigits: 0})}</div>
            </Card.Body>
          </Card>
        </Col>
        <Col xs={6} md={3} lg={true}>
          <Card className="card-stat-new current text-center h-100 border-0">
            <Card.Body className="py-2 px-2">
              <small className="stat-label">Current</small>
              <div className="stat-value">₹{currentValue.toLocaleString('en-IN', {maximumFractionDigits: 0})}</div>
            </Card.Body>
          </Card>
        </Col>
        <Col xs={6} md={3} lg={true}>
          <Card className={`card-stat-new text-center h-100 border-0 ${totalGains >= 0 ? 'profit' : 'loss'}`}>
            <Card.Body className="py-2 px-2">
              <small className="stat-label">Total P&L</small>
              <div className="stat-value">
                {totalGains >= 0 ? '+' : ''}₹{totalGains.toLocaleString('en-IN', {maximumFractionDigits: 0})}
              </div>
              <small className="stat-percent">{totalGains >= 0 ? '+' : ''}{totalGainsPercent.toFixed(1)}%</small>
            </Card.Body>
          </Card>
        </Col>
        <Col xs={6} md={3} lg={true}>
          <Card className={`card-stat-new text-center h-100 border-0 ${todaysChange >= 0 ? 'profit' : 'loss'}`}>
            <Card.Body className="py-2 px-2">
              <small className="stat-label">Today</small>
              <div className="stat-value">
                {todaysChange >= 0 ? '+' : ''}₹{todaysChange.toLocaleString('en-IN', {maximumFractionDigits: 0})}
              </div>
              <small className="stat-percent">{todaysChange >= 0 ? '+' : ''}{todaysChangePercent.toFixed(1)}%</small>
            </Card.Body>
          </Card>
        </Col>
        {/* Holdings count - hidden on mobile */}
        <Col className="d-none d-lg-block" lg={true}>
          <Card className="card-stat-new holdings text-center h-100 border-0">
            <Card.Body className="py-2 px-2">
              <small className="stat-label">Holdings</small>
              <div className="stat-value">{portfolioLabels.length}</div>
              <small className="stat-percent">Securities</small>
            </Card.Body>
          </Card>
        </Col>
      </Row>

      {/* Charts - Hidden on mobile for cleaner view */}
      <Row className="mb-4 g-3 d-none d-md-flex">
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

      {/* Holdings Table - Clean layout for mobile with sorting */}
      <Card className="border-0 shadow-sm">
        <Card.Header className="bg-transparent border-bottom">
          <div className="d-flex justify-content-between align-items-center">
            <div>
              <h6 className="mb-0 d-md-none">Holdings ({portfolioLabels.length})</h6>
              <h5 className="mb-0 d-none d-md-block">Current Holdings</h5>
            </div>
          </div>
          {/* Mobile Sort Controls */}
          <div className="d-md-none mt-2 d-flex justify-content-end gap-2">
            <Button
              variant={sortConfig.key === 'dayPnl' ? 'primary' : 'outline-secondary'}
              size="sm"
              onClick={() => handleSort('dayPnl')}
              className="sort-btn-label"
            >
              Day {sortConfig.key === 'dayPnl' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
            </Button>
            <Button
              variant={sortConfig.key === 'pnl' ? 'primary' : 'outline-secondary'}
              size="sm"
              onClick={() => handleSort('pnl')}
              className="sort-btn-label"
            >
              Total {sortConfig.key === 'pnl' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
            </Button>
          </div>
        </Card.Header>
        <Card.Body className="p-0 p-md-3">
          {/* Mobile: Two-row layout showing both Day and Total P&L */}
          <div className="d-md-none">
            {sortedHoldings.map(({ symbol, stock, currentVal, pnl, pnlPercent, dailyChange, dailyChangePercent }) => {
              return (
                <div key={symbol} className="holding-item-new px-3 py-2 border-bottom">
                  <div className="d-flex justify-content-between align-items-start mb-1">
                    <div>
                      <strong className="holding-symbol">{symbol}</strong>
                      <div className="holding-meta">{stock.quantity} shares @ ₹{(stock.total_invested / stock.quantity).toFixed(0)}</div>
                    </div>
                    <div className="text-end">
                      <div className="holding-value">₹{currentVal.toLocaleString('en-IN', {maximumFractionDigits: 0})}</div>
                    </div>
                  </div>
                  <div className="pnl-rows">
                    <div className="pnl-row">
                      <span className="pnl-label">Day</span>
                      <span className={`pnl-value ${dailyChange >= 0 ? 'positive' : 'negative'}`}>
                        {dailyChange >= 0 ? '+' : ''}₹{dailyChange.toLocaleString('en-IN', {maximumFractionDigits: 0})}
                        <span className="pnl-percent"> ({dailyChangePercent >= 0 ? '+' : ''}{dailyChangePercent.toFixed(1)}%)</span>
                      </span>
                    </div>
                    <div className="pnl-row">
                      <span className="pnl-label">Total</span>
                      <span className={`pnl-value ${pnl >= 0 ? 'positive' : 'negative'}`}>
                        {pnl >= 0 ? '+' : ''}₹{pnl.toLocaleString('en-IN', {maximumFractionDigits: 0})}
                        <span className="pnl-percent"> ({pnlPercent >= 0 ? '+' : ''}{pnlPercent.toFixed(1)}%)</span>
                      </span>
                    </div>
                  </div>
                </div>
              );
            })}
            {portfolioLabels.length === 0 && (
              <p className="text-center text-muted py-4">No current holdings</p>
            )}
          </div>

          {/* Desktop: Full table with sortable headers */}
          <div className="d-none d-md-block table-responsive">
            <Table striped hover size="sm" className="mb-0">
              <thead>
                <tr>
                  <th>Security</th>
                  <th>Qty</th>
                  <th>Avg. Price</th>
                  <th>Current Price</th>
                  <th className="d-none d-lg-table-cell">Invested</th>
                  <th>Value</th>
                  <th>Day P&L</th>
                  <th
                    style={{ cursor: 'pointer' }}
                    onClick={() => handleSort('pnl')}
                    className="sortable-header"
                  >
                    Total P&L {sortConfig.key === 'pnl' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                  </th>
                </tr>
              </thead>
              <tbody>
                {sortedHoldings.map(({ symbol, stock, currentVal, pnl, pnlPercent }) => {
                  const currentPrice = stock.quantity > 0 ? currentVal / stock.quantity : 0;
                  const avgPrice = stock.quantity > 0 ? stock.total_invested / stock.quantity : 0;
                  const dailyChange = stock.todays_change || 0;
                  const dailyChangePercent = stock.change_percent || 0;

                  return (
                    <tr key={symbol}>
                      <td><strong>{symbol}</strong></td>
                      <td>{stock.quantity}</td>
                      <td>₹{avgPrice.toFixed(2)}</td>
                      <td>₹{currentPrice.toFixed(2)}</td>
                      <td className="d-none d-lg-table-cell">₹{stock.total_invested.toLocaleString('en-IN')}</td>
                      <td>₹{currentVal.toLocaleString('en-IN')}</td>
                      <td className={dailyChange >= 0 ? 'text-success' : 'text-danger'}>
                        {dailyChange >= 0 ? '+' : ''}₹{dailyChange.toLocaleString('en-IN', {maximumFractionDigits: 0})}
                        <small className="d-block" style={{fontSize: '0.7rem'}}>
                          ({dailyChangePercent >= 0 ? '+' : ''}{dailyChangePercent.toFixed(1)}%)
                        </small>
                      </td>
                      <td className={pnl >= 0 ? 'text-success' : 'text-danger'}>
                        {pnl >= 0 ? '+' : ''}₹{pnl.toLocaleString('en-IN', {maximumFractionDigits: 0})}
                        <small className="d-block" style={{fontSize: '0.7rem'}}>
                          ({pnlPercent >= 0 ? '+' : ''}{pnlPercent.toFixed(1)}%)
                        </small>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </Table>
            {portfolioLabels.length === 0 && (
              <p className="text-center text-muted py-3">No current holdings</p>
            )}
          </div>
        </Card.Body>
      </Card>
    </div>
  );
};

export default Dashboard;
