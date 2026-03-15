import React, { useState, useEffect } from 'react';
import { Row, Col, Card, Table, Spinner, Button, Modal, Badge } from 'react-bootstrap';
import { Chart as ChartJS, ArcElement, Tooltip as ChartTooltip, Legend, CategoryScale, LinearScale, BarElement, Title, PointElement, LineElement, Filler } from 'chart.js';
import { Doughnut, Bar, Line } from 'react-chartjs-2';
import { apiService } from '../services/apiService';
import { useAuth } from '../context/AuthContext';
import { toast } from 'react-toastify';

ChartJS.register(ArcElement, ChartTooltip, Legend, CategoryScale, LinearScale, BarElement, Title, PointElement, LineElement, Filler);

const Dashboard = () => {
  const [portfolio, setPortfolio] = useState(null);
  const [marketIndices, setMarketIndices] = useState(null);
  const [portfolioHistory, setPortfolioHistory] = useState(null);
  const [historyTimeRange, setHistoryTimeRange] = useState('5d');
  const [loading, setLoading] = useState(true);
  const [sortConfig, setSortConfig] = useState({ key: 'dayPnlPercent', direction: 'desc' }); // Default: Day P&L % (highest gains on top)
  const { user } = useAuth();

  // Transaction history modal state
  const [showTxModal, setShowTxModal] = useState(false);
  const [selectedStock, setSelectedStock] = useState(null);
  const [stockTransactions, setStockTransactions] = useState([]);
  const [txLoading, setTxLoading] = useState(false);

  const timeRangeOptions = [
    { value: '5d', label: '5D' },
    { value: '1m', label: '1M' },
    { value: 'ytd', label: 'YTD' },
    { value: '1y', label: '1Y' },
    { value: '5y', label: '5Y' },
    { value: 'max', label: 'MAX' }
  ];

  useEffect(() => {
    loadPortfolioData();
    loadMarketIndices();
  }, [user]);

  useEffect(() => {
    loadPortfolioHistory(historyTimeRange);
  }, [user, historyTimeRange]);

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

  const loadPortfolioHistory = async (timeRange = '5d') => {
    try {
      if (!user?.id) return;
      const data = await apiService.getPortfolioHistory(user.id, timeRange);
      setPortfolioHistory(data);
    } catch (error) {
      console.error('Error loading portfolio history:', error);
    }
  };

  const handleSort = (key) => {
    setSortConfig(prev => ({
      key,
      // Default to desc (highest first), toggle to asc on second click
      direction: prev.key === key && prev.direction === 'desc' ? 'asc' : 'desc'
    }));
  };

  const handleStockClick = async (symbol, stockData) => {
    setSelectedStock({ symbol, ...stockData });
    setShowTxModal(true);
    setTxLoading(true);
    setStockTransactions([]);

    try {
      // Fetch transactions for this stock
      const transactions = await apiService.getTransactions(user.id, { security_name: symbol });
      // Sort by date descending (most recent first)
      const sorted = transactions.sort((a, b) => new Date(b.transaction_date) - new Date(a.transaction_date));
      setStockTransactions(sorted);
    } catch (error) {
      console.error('Error fetching transactions:', error);
      toast.error('Failed to load transaction history');
    } finally {
      setTxLoading(false);
    }
  };

  const getSortedHoldings = (holdings, currentValues, portfolioData) => {
    const holdingsArray = holdings.map(symbol => {
      const stock = portfolioData.portfolio[symbol];
      const currentVal = currentValues[symbol] || 0;
      const pnl = currentVal - stock.total_invested;
      const pnlPercent = stock.total_invested > 0 ? (pnl / stock.total_invested) * 100 : 0;
      const dailyChange = stock.todays_change || 0;
      const dailyChangePercent = stock.change_percent || 0;
      const xirr = stock.xirr || null;
      const avgHoldingDays = stock.avg_holding_days || null;
      return { symbol, stock, currentVal, pnl, pnlPercent, dailyChange, dailyChangePercent, xirr, avgHoldingDays };
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
        case 'xirr':
          aVal = a.xirr ?? -Infinity;
          bVal = b.xirr ?? -Infinity;
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

  // All holdings for the table (sorted by value)
  const allHoldingSymbols = Object.keys(portfolio.portfolio || {})
    .filter(symbol => portfolio.portfolio[symbol].quantity > 0);

  // Chart data for portfolio allocation (top 9 + Others)
  const allHoldingsSorted = allHoldingSymbols
    .map(symbol => ({
      symbol,
      value: portfolio.current_values?.[symbol] || 0
    }))
    .sort((a, b) => b.value - a.value);

  // Take top 9, club rest as "Others"
  const TOP_N = 9;
  const topHoldings = allHoldingsSorted.slice(0, TOP_N);
  const otherHoldings = allHoldingsSorted.slice(TOP_N);
  const othersValue = otherHoldings.reduce((sum, h) => sum + h.value, 0);

  const chartLabels = topHoldings.map(h => h.symbol);
  const chartValues = topHoldings.map(h => h.value);

  // Add "Others" if there are more than TOP_N holdings
  if (othersValue > 0) {
    chartLabels.push('Others');
    chartValues.push(othersValue);
  }

  const portfolioData = {
    labels: chartLabels,
    datasets: [
      {
        data: chartValues,
        backgroundColor: [
          '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF',
          '#FF9F40', '#4BC0C0', '#C9CBCF', '#8B5CF6', '#6B7280'
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

  const sortedHoldings = getSortedHoldings(allHoldingSymbols, portfolio.current_values, portfolio);

  return (
    <div className="dashboard-container">
      {/* Header - simplified on mobile */}
      <h2 className="mb-3 mb-md-4 d-flex align-items-center">
        <img src="/images/analytics.svg" alt="Portfolio Analytics" className="d-none d-sm-block" style={{width: '2.5rem', height: '2.5rem', marginRight: '0.5rem'}} />
        <span className="d-none d-sm-inline">Portfolio Dashboard</span>
        <span className="d-sm-none">Dashboard</span>
      </h2>

      {/* Market Indices - Compact 4-column display */}
      {marketIndices && (
        <Row className="mb-3 g-1">
          <Col xs={3}>
            <div className="market-index-card compact">
              <div className="index-name">SENSEX</div>
              <div className="index-value">
                {(marketIndices.SENSEX?.value || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
              </div>
              <div className={`index-change ${marketIndices.SENSEX?.change >= 0 ? 'positive' : 'negative'}`}>
                {marketIndices.SENSEX?.change >= 0 ? '+' : ''}{(marketIndices.SENSEX?.change_percent || 0).toFixed(1)}%
              </div>
            </div>
          </Col>
          <Col xs={3}>
            <div className="market-index-card compact">
              <div className="index-name">NIFTY</div>
              <div className="index-value">
                {(marketIndices.NIFTY?.value || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
              </div>
              <div className={`index-change ${marketIndices.NIFTY?.change >= 0 ? 'positive' : 'negative'}`}>
                {marketIndices.NIFTY?.change >= 0 ? '+' : ''}{(marketIndices.NIFTY?.change_percent || 0).toFixed(1)}%
              </div>
            </div>
          </Col>
          <Col xs={3}>
            <div className="market-index-card compact">
              <div className="index-name">NASDAQ</div>
              <div className="index-value">
                {(marketIndices.NASDAQ?.value || 0).toLocaleString('en-US', { maximumFractionDigits: 0 })}
              </div>
              <div className={`index-change ${marketIndices.NASDAQ?.change >= 0 ? 'positive' : 'negative'}`}>
                {marketIndices.NASDAQ?.change >= 0 ? '+' : ''}{(marketIndices.NASDAQ?.change_percent || 0).toFixed(1)}%
              </div>
            </div>
          </Col>
          <Col xs={3}>
            <div className="market-index-card compact">
              <div className="index-name">DOW</div>
              <div className="index-value">
                {(marketIndices.DJI?.value || 0).toLocaleString('en-US', { maximumFractionDigits: 0 })}
              </div>
              <div className={`index-change ${marketIndices.DJI?.change >= 0 ? 'positive' : 'negative'}`}>
                {marketIndices.DJI?.change >= 0 ? '+' : ''}{(marketIndices.DJI?.change_percent || 0).toFixed(1)}%
              </div>
            </div>
          </Col>
        </Row>
      )}

      {/* Summary Cards - 3 columns on mobile */}
      <Row className="mb-3 mb-md-4 g-1 g-md-2">
        <Col xs={4} md={3} lg={true}>
          <Card className="card-stat-new invested text-center h-100 border-0">
            <Card.Body className="py-2 px-1">
              <small className="stat-label">Invested</small>
              <div className="stat-value">₹{totalInvested.toLocaleString('en-IN', {maximumFractionDigits: 0})}</div>
            </Card.Body>
          </Card>
        </Col>
        <Col xs={4} md={3} lg={true}>
          <Card className={`card-stat-new text-center h-100 border-0 ${totalGains >= 0 ? 'profit' : 'loss'}`}>
            <Card.Body className="py-2 px-1">
              <small className="stat-label">Current</small>
              <div className="stat-value">₹{currentValue.toLocaleString('en-IN', {maximumFractionDigits: 0})}</div>
              <small className="stat-percent">
                {totalGains >= 0 ? '+' : ''}{totalGainsPercent.toFixed(1)}%
              </small>
            </Card.Body>
          </Card>
        </Col>
        <Col xs={4} md={3} lg={true}>
          <Card className={`card-stat-new text-center h-100 border-0 ${todaysChange >= 0 ? 'profit' : 'loss'}`}>
            <Card.Body className="py-2 px-1">
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
              <div className="stat-value">{allHoldingSymbols.length}</div>
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
              {allHoldingSymbols.length > 0 ? (
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
              <h6 className="mb-0 d-md-none">
                Holdings ({allHoldingSymbols.length})
                {portfolio.overall_xirr !== null && portfolio.overall_xirr !== undefined && (
                  <span className={`ms-2 ${portfolio.overall_xirr >= 0 ? 'text-success' : 'text-danger'}`}>
                    XIRR: {portfolio.overall_xirr >= 0 ? '+' : ''}{portfolio.overall_xirr.toFixed(1)}%
                  </span>
                )}
              </h6>
              <h5 className="mb-0 d-none d-md-block">Current Holdings</h5>
            </div>
            {portfolio.overall_xirr !== null && portfolio.overall_xirr !== undefined && (
              <div className="d-none d-md-block text-end">
                <small className="text-muted">Portfolio XIRR</small>
                <div className={`fw-bold ${portfolio.overall_xirr >= 0 ? 'text-success' : 'text-danger'}`}>
                  {portfolio.overall_xirr >= 0 ? '+' : ''}{portfolio.overall_xirr.toFixed(1)}%
                </div>
              </div>
            )}
          </div>
          {/* Mobile Controls: Day/Total/XIRR sort toggle */}
          <div className="d-md-none mt-2 d-flex justify-content-end align-items-center">
            <div className="d-flex gap-1">
              <Button
                variant={(sortConfig.key === 'dayPnl' || sortConfig.key === 'dayPnlPercent') ? 'primary' : 'outline-secondary'}
                size="sm"
                onClick={() => handleSort('dayPnlPercent')}
                className="sort-btn-label"
              >
                Day {(sortConfig.key === 'dayPnl' || sortConfig.key === 'dayPnlPercent') && (sortConfig.direction === 'asc' ? '↑' : '↓')}
              </Button>
              <Button
                variant={(sortConfig.key === 'pnl' || sortConfig.key === 'pnlPercent') ? 'primary' : 'outline-secondary'}
                size="sm"
                onClick={() => handleSort('pnlPercent')}
                className="sort-btn-label"
              >
                Total {(sortConfig.key === 'pnl' || sortConfig.key === 'pnlPercent') && (sortConfig.direction === 'asc' ? '↑' : '↓')}
              </Button>
              <Button
                variant={sortConfig.key === 'xirr' ? 'primary' : 'outline-secondary'}
                size="sm"
                onClick={() => handleSort('xirr')}
                className="sort-btn-label"
              >
                XIRR {sortConfig.key === 'xirr' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
              </Button>
            </div>
          </div>
        </Card.Header>
        <Card.Body className="p-0 p-md-3">
          {/* Mobile: Single P&L row based on Day/Total/XIRR selection */}
          <div className="d-md-none">
            {sortedHoldings.map(({ symbol, stock, currentVal, pnl, pnlPercent, dailyChange, dailyChangePercent, xirr, avgHoldingDays }) => {
              const isDay = sortConfig.key === 'dayPnl' || sortConfig.key === 'dayPnlPercent';
              const isXirr = sortConfig.key === 'xirr';
              const currentPrice = stock.quantity > 0 ? currentVal / stock.quantity : 0;
              const avgPrice = stock.quantity > 0 ? stock.total_invested / stock.quantity : 0;

              return (
                <div key={symbol} className="holding-item-new px-3 py-2 border-bottom">
                  <div className="d-flex justify-content-between align-items-center">
                    <div>
                      <strong
                        className="holding-symbol"
                        style={{ cursor: 'pointer', textDecoration: 'underline', textDecorationStyle: 'dotted' }}
                        onClick={() => handleStockClick(symbol, stock)}
                      >{symbol}</strong>
                      <div className="holding-meta">
                        {stock.quantity} shares @ ₹{avgPrice.toFixed(0)}, CMP{' '}
                        <span className={currentPrice >= avgPrice ? 'text-success' : 'text-danger'}>
                          ₹{currentPrice.toFixed(0)}
                        </span>
                      </div>
                    </div>
                    <div className="text-end">
                      {isXirr ? (
                        <>
                          <div className={`holding-value ${xirr !== null ? (xirr >= 0 ? 'text-success' : 'text-danger') : 'text-muted'}`}>
                            {xirr !== null ? `${xirr >= 0 ? '+' : ''}${xirr.toFixed(1)}%` : 'N/A'}
                          </div>
                          <div className="holding-pnl-single text-muted">
                            <small>{avgHoldingDays !== null ? `${avgHoldingDays} days` : 'XIRR'}</small>
                          </div>
                        </>
                      ) : (
                        <>
                          <div className={`holding-value ${(isDay ? dailyChange : pnl) >= 0 ? 'text-success' : 'text-danger'}`}>
                            {(isDay ? dailyChange : pnl) >= 0 ? '+' : ''}₹{(isDay ? dailyChange : pnl).toLocaleString('en-IN', {maximumFractionDigits: 0})}
                          </div>
                          <div className={`holding-pnl-single ${(isDay ? dailyChange : pnl) >= 0 ? 'positive' : 'negative'}`}>
                            {(isDay ? dailyChangePercent : pnlPercent) >= 0 ? '+' : ''}{(isDay ? dailyChangePercent : pnlPercent).toFixed(1)}%
                          </div>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
            {allHoldingSymbols.length === 0 && (
              <p className="text-center text-muted py-4">No current holdings</p>
            )}
          </div>

          {/* Desktop: Full table with sortable headers */}
          <div className="d-none d-md-block table-responsive">
            <Table striped hover size="sm" className="mb-0">
              <thead>
                <tr>
                  <th
                    style={{ cursor: 'pointer' }}
                    onClick={() => handleSort('name')}
                    className="sortable-header"
                  >
                    Security {sortConfig.key === 'name' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                  </th>
                  <th>Qty</th>
                  <th>Avg. Price</th>
                  <th>Current Price</th>
                  <th className="d-none d-lg-table-cell">Invested</th>
                  <th>Value</th>
                  <th
                    style={{ cursor: 'pointer' }}
                    onClick={() => handleSort('dayPnl')}
                    className="sortable-header"
                  >
                    Day P&L {sortConfig.key === 'dayPnl' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                  </th>
                  <th
                    style={{ cursor: 'pointer' }}
                    onClick={() => handleSort('pnl')}
                    className="sortable-header"
                  >
                    Total P&L {sortConfig.key === 'pnl' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                  </th>
                  <th
                    style={{ cursor: 'pointer' }}
                    onClick={() => handleSort('xirr')}
                    className="sortable-header"
                  >
                    XIRR {sortConfig.key === 'xirr' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                  </th>
                </tr>
              </thead>
              <tbody>
                {sortedHoldings.map(({ symbol, stock, currentVal, pnl, pnlPercent, dailyChange, dailyChangePercent, xirr }) => {
                  const currentPrice = stock.quantity > 0 ? currentVal / stock.quantity : 0;
                  const avgPrice = stock.quantity > 0 ? stock.total_invested / stock.quantity : 0;

                  return (
                    <tr key={symbol}>
                      <td>
                        <strong
                          style={{ cursor: 'pointer', textDecoration: 'underline', textDecorationStyle: 'dotted' }}
                          onClick={() => handleStockClick(symbol, stock)}
                        >{symbol}</strong>
                      </td>
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
                      <td className={xirr !== null ? (xirr >= 0 ? 'text-success' : 'text-danger') : 'text-muted'}>
                        {xirr !== null ? (
                          <>{xirr >= 0 ? '+' : ''}{xirr.toFixed(1)}%</>
                        ) : (
                          <small>N/A</small>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </Table>
            {allHoldingSymbols.length === 0 && (
              <p className="text-center text-muted py-3">No current holdings</p>
            )}
          </div>
        </Card.Body>
      </Card>

      {/* Portfolio Value Over Time Chart
          TODO: Revisit this chart to use portfolio_snapshots table data for accurate historical
          market values instead of computing on-the-fly. The snapshots are captured daily at 6 PM IST.
          Currently shows: invested amount + cost basis over time, with current value only at today's date.
      */}
      {portfolioHistory && portfolioHistory.data_points && portfolioHistory.data_points.length > 0 && (
        <Card className="mt-4">
          <Card.Header className="d-flex justify-content-between align-items-center flex-wrap gap-2">
            <h5 className="mb-0">Portfolio Value Over Time</h5>
            <div className="btn-group btn-group-sm">
              {timeRangeOptions.map(option => (
                <Button
                  key={option.value}
                  variant={historyTimeRange === option.value ? 'primary' : 'outline-secondary'}
                  size="sm"
                  onClick={() => setHistoryTimeRange(option.value)}
                  style={{ minWidth: '40px', fontSize: '0.75rem', padding: '0.2rem 0.5rem' }}
                >
                  {option.label}
                </Button>
              ))}
            </div>
          </Card.Header>
          <Card.Body>
            <div style={{ height: '300px' }}>
              <Line
                data={{
                  labels: portfolioHistory.data_points.map(dp => {
                    const date = new Date(dp.date);
                    // Use shorter format for shorter time ranges
                    if (historyTimeRange === '5d' || historyTimeRange === '1m') {
                      return date.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });
                    }
                    return date.toLocaleDateString('en-IN', { month: 'short', year: '2-digit' });
                  }),
                  datasets: [
                    {
                      label: 'Amount Invested',
                      data: portfolioHistory.data_points.map(dp => dp.invested),
                      borderColor: 'rgb(75, 192, 192)',
                      backgroundColor: 'rgba(75, 192, 192, 0.1)',
                      fill: true,
                      tension: 0.3,
                      pointRadius: 2,
                      pointHoverRadius: 5
                    },
                    {
                      label: 'Current Value',
                      data: portfolioHistory.data_points.map((dp, idx) => {
                        // Show current value only for the last data point
                        if (idx === portfolioHistory.data_points.length - 1 && dp.current_value) {
                          return dp.current_value;
                        }
                        // For other points, show cost basis (what remains invested after sells)
                        return dp.cost_basis;
                      }),
                      borderColor: portfolioHistory.current_value >= portfolioHistory.current_cost_basis
                        ? 'rgb(34, 197, 94)'
                        : 'rgb(239, 68, 68)',
                      backgroundColor: portfolioHistory.current_value >= portfolioHistory.current_cost_basis
                        ? 'rgba(34, 197, 94, 0.1)'
                        : 'rgba(239, 68, 68, 0.1)',
                      fill: true,
                      tension: 0.3,
                      pointRadius: 2,
                      pointHoverRadius: 5
                    }
                  ]
                }}
                options={{
                  responsive: true,
                  maintainAspectRatio: false,
                  interaction: {
                    mode: 'index',
                    intersect: false,
                  },
                  plugins: {
                    legend: {
                      position: 'top',
                    },
                    tooltip: {
                      callbacks: {
                        label: function(context) {
                          return `${context.dataset.label}: ₹${context.parsed.y.toLocaleString('en-IN')}`;
                        }
                      }
                    }
                  },
                  scales: {
                    y: {
                      beginAtZero: true,
                      ticks: {
                        callback: function(value) {
                          if (value >= 10000000) {
                            return '₹' + (value / 10000000).toFixed(1) + 'Cr';
                          } else if (value >= 100000) {
                            return '₹' + (value / 100000).toFixed(1) + 'L';
                          } else if (value >= 1000) {
                            return '₹' + (value / 1000).toFixed(0) + 'K';
                          }
                          return '₹' + value;
                        }
                      }
                    }
                  }
                }}
              />
            </div>
            <div className="text-center mt-3">
              <small className="text-muted">
                Total Invested: ₹{portfolioHistory.total_invested?.toLocaleString('en-IN')} |
                Current Value: ₹{portfolioHistory.current_value?.toLocaleString('en-IN')} |
                {portfolioHistory.current_value >= portfolioHistory.current_cost_basis ? (
                  <span className="text-success">
                    Gain: ₹{(portfolioHistory.current_value - portfolioHistory.current_cost_basis).toLocaleString('en-IN')}
                  </span>
                ) : (
                  <span className="text-danger">
                    Loss: ₹{(portfolioHistory.current_cost_basis - portfolioHistory.current_value).toLocaleString('en-IN')}
                  </span>
                )}
              </small>
            </div>
          </Card.Body>
        </Card>
      )}

      {/* Transaction History Modal */}
      <Modal show={showTxModal} onHide={() => setShowTxModal(false)} size="lg" centered>
        <Modal.Header closeButton>
          <Modal.Title>
            {selectedStock?.symbol}
            <small className="text-muted ms-2" style={{ fontSize: '0.6em' }}>Transaction History</small>
          </Modal.Title>
        </Modal.Header>
        <Modal.Body style={{ maxHeight: '60vh', overflowY: 'auto' }}>
          {txLoading ? (
            <div className="text-center py-4">
              <Spinner animation="border" size="sm" />
              <span className="ms-2">Loading transactions...</span>
            </div>
          ) : stockTransactions.length > 0 ? (
            <Table striped bordered hover size="sm" responsive>
              <thead className="table-dark">
                <tr>
                  <th>Date</th>
                  <th>Type</th>
                  <th>Qty</th>
                  <th>Price</th>
                  <th>Total</th>
                </tr>
              </thead>
              <tbody>
                {stockTransactions.map((tx) => (
                  <tr key={tx.id}>
                    <td>{new Date(tx.transaction_date).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })}</td>
                    <td>
                      <Badge bg={tx.transaction_type === 'BUY' ? 'success' : 'danger'}>
                        {tx.transaction_type}
                      </Badge>
                    </td>
                    <td>{tx.quantity}</td>
                    <td>₹{tx.price_per_unit?.toFixed(2)}</td>
                    <td>₹{tx.total_amount?.toLocaleString('en-IN', { maximumFractionDigits: 0 })}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot className="table-light">
                <tr>
                  <td colSpan="2"><strong>Summary</strong></td>
                  <td>
                    <strong>
                      {stockTransactions.reduce((sum, tx) =>
                        sum + (tx.transaction_type === 'BUY' ? tx.quantity : -tx.quantity), 0
                      )}
                    </strong>
                  </td>
                  <td></td>
                  <td>
                    <strong>
                      ₹{stockTransactions.reduce((sum, tx) =>
                        sum + (tx.transaction_type === 'BUY' ? tx.total_amount : -tx.total_amount), 0
                      ).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                    </strong>
                  </td>
                </tr>
              </tfoot>
            </Table>
          ) : (
            <p className="text-center text-muted py-4">No transactions found for this stock</p>
          )}
        </Modal.Body>
        <Modal.Footer className="justify-content-between">
          <small className="text-muted">
            {stockTransactions.length} transaction{stockTransactions.length !== 1 ? 's' : ''}
          </small>
          <Button variant="secondary" size="sm" onClick={() => setShowTxModal(false)}>
            Close
          </Button>
        </Modal.Footer>
      </Modal>
    </div>
  );
};

export default Dashboard;
