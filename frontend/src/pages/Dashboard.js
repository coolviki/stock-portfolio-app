import React, { useState, useEffect } from 'react';
import { Row, Col, Card, Table, Spinner, Button, Modal, Badge, Dropdown, Form, Nav, Tab } from 'react-bootstrap';
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
  const [historyTimeRange, setHistoryTimeRange] = useState('1m');
  const [loading, setLoading] = useState(true);
  const [sortConfig, setSortConfig] = useState({ key: 'dayPnlPercent', direction: 'desc' }); // Default: Day P&L % (highest gains on top)
  const { user } = useAuth();

  // Transaction history modal state
  const [showTxModal, setShowTxModal] = useState(false);
  const [selectedStock, setSelectedStock] = useState(null);
  const [stockTransactions, setStockTransactions] = useState([]);
  const [stockCorporateEvents, setStockCorporateEvents] = useState([]);
  const [txLoading, setTxLoading] = useState(false);

  // Stock modal tab state
  const [activeModalTab, setActiveModalTab] = useState('chart');
  const [stockHistory, setStockHistory] = useState(null);
  const [stockHistoryRange, setStockHistoryRange] = useState('5d');
  const [stockHistoryLoading, setStockHistoryLoading] = useState(false);
  const [stockNews, setStockNews] = useState([]);
  const [stockNewsLoading, setStockNewsLoading] = useState(false);

  // Column visibility state
  const [visibleColumns, setVisibleColumns] = useState({
    qty: true,
    avgPrice: true,
    currentPrice: true,
    invested: true,
    value: true,
    dayPnl: true,
    totalPnl: true,
    xirr: true,
    allocation: true
  });

  // Show zero holdings toggle
  const [showZeroHoldings, setShowZeroHoldings] = useState(false);
  const [zeroHoldings, setZeroHoldings] = useState([]);

  // Column configuration for the settings dropdown
  const columnConfig = [
    { key: 'qty', label: 'Qty' },
    { key: 'avgPrice', label: 'Avg. Price' },
    { key: 'currentPrice', label: 'Current Price' },
    { key: 'invested', label: 'Invested' },
    { key: 'value', label: 'Value' },
    { key: 'dayPnl', label: 'Day P&L' },
    { key: 'totalPnl', label: 'Total P&L' },
    { key: 'xirr', label: 'XIRR' },
    { key: 'allocation', label: '%' }
  ];

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
    loadColumnPreferences();
  }, [user]);

  useEffect(() => {
    loadPortfolioHistory(historyTimeRange);
  }, [user, historyTimeRange]);

  const loadColumnPreferences = async () => {
    if (!user?.id) return;
    try {
      const prefs = await apiService.getUserPreferences(user.id);
      if (prefs.dashboard_columns) {
        setVisibleColumns(prefs.dashboard_columns);
      }
    } catch (error) {
      console.error('Error loading column preferences:', error);
      // Use defaults on error
    }
  };

  const handleColumnToggle = async (columnKey) => {
    const newVisibility = {
      ...visibleColumns,
      [columnKey]: !visibleColumns[columnKey]
    };
    setVisibleColumns(newVisibility);

    // Persist to backend
    try {
      await apiService.updateDashboardColumns(user.id, newVisibility);
    } catch (error) {
      console.error('Error saving column preferences:', error);
      toast.error('Failed to save column settings');
      // Revert on error
      setVisibleColumns(visibleColumns);
    }
  };

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

  const loadZeroHoldings = async () => {
    try {
      if (!user?.id) return;
      const data = await apiService.getZeroHoldings(user.id);
      setZeroHoldings(data.zero_holdings || []);
    } catch (error) {
      console.error('Error loading zero holdings:', error);
    }
  };

  const handleShowZeroHoldingsChange = (e) => {
    const checked = e.target.checked;
    setShowZeroHoldings(checked);
    if (checked && zeroHoldings.length === 0) {
      loadZeroHoldings();
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
    setActiveModalTab('chart');
    setTxLoading(true);
    setStockTransactions([]);
    setStockCorporateEvents([]);
    setStockHistory(null);
    setStockHistoryRange('5d');
    setStockNews([]);

    try {
      // Fetch transactions for this stock
      const transactions = await apiService.getTransactions(user.id, { security_name: symbol });
      // Sort by date descending (most recent first)
      const sorted = transactions.sort((a, b) => new Date(b.transaction_date) - new Date(a.transaction_date));
      setStockTransactions(sorted);

      // Fetch corporate events for this security (if we have transactions)
      if (sorted.length > 0 && sorted[0].security_id) {
        // Store security_id in selectedStock for later use
        setSelectedStock(prev => ({ ...prev, security_id: sorted[0].security_id }));

        try {
          const events = await apiService.getCorporateEvents({
            security_id: sorted[0].security_id,
            is_applied: true
          });
          // Filter to only SPLIT and BONUS events (the ones that affect holdings)
          const relevantEvents = events.filter(e =>
            ['SPLIT', 'BONUS'].includes(e.event_type)
          );
          setStockCorporateEvents(relevantEvents);
        } catch (eventError) {
          console.error('Error fetching corporate events:', eventError);
        }

        // Load stock history
        loadStockHistory(sorted[0].security_id, '5d');
      }
    } catch (error) {
      console.error('Error fetching transactions:', error);
      toast.error('Failed to load transaction history');
    } finally {
      setTxLoading(false);
    }
  };

  const loadStockHistory = async (securityId, range) => {
    if (!securityId) return;

    setStockHistoryLoading(true);
    try {
      const data = await apiService.getStockHistory(securityId, range);
      setStockHistory(data);
    } catch (error) {
      console.error('Error fetching stock history:', error);
      setStockHistory(null);
    } finally {
      setStockHistoryLoading(false);
    }
  };

  const handleStockHistoryRangeChange = (range) => {
    setStockHistoryRange(range);
    if (selectedStock?.security_id) {
      loadStockHistory(selectedStock.security_id, range);
    }
  };

  const loadStockNews = async (securityId) => {
    if (!securityId) return;

    setStockNewsLoading(true);
    try {
      const data = await apiService.getStockNews(securityId);
      setStockNews(data.articles || []);
    } catch (error) {
      console.error('Error fetching stock news:', error);
      setStockNews([]);
    } finally {
      setStockNewsLoading(false);
    }
  };

  const handleModalTabChange = (tab) => {
    setActiveModalTab(tab);
    // Load news on first visit to news tab
    if (tab === 'news' && stockNews.length === 0 && selectedStock?.security_id) {
      loadStockNews(selectedStock.security_id);
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
        case 'quantity':
          aVal = a.stock.quantity;
          bVal = b.stock.quantity;
          break;
        case 'avgPrice':
          aVal = a.stock.quantity > 0 ? a.stock.total_invested / a.stock.quantity : 0;
          bVal = b.stock.quantity > 0 ? b.stock.total_invested / b.stock.quantity : 0;
          break;
        case 'currentPrice':
          aVal = a.stock.quantity > 0 ? a.currentVal / a.stock.quantity : 0;
          bVal = b.stock.quantity > 0 ? b.currentVal / b.stock.quantity : 0;
          break;
        case 'invested':
          aVal = a.stock.total_invested;
          bVal = b.stock.total_invested;
          break;
        case 'value':
          aVal = a.currentVal;
          bVal = b.currentVal;
          break;
        case 'allocation':
          aVal = a.currentVal;
          bVal = b.currentVal;
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

  // Add zero holdings if checkbox is checked
  const zeroHoldingsFormatted = showZeroHoldings ? zeroHoldings.map(zh => ({
    symbol: zh.symbol,
    stock: {
      quantity: 0,
      total_invested: 0,
      isin: zh.isin,
      security_symbol: zh.security_symbol,
      security_id: zh.security_id,
      isZeroHolding: true
    },
    currentVal: 0,
    pnl: zh.realized_gain_loss || 0,
    pnlPercent: 0,
    dailyChange: 0,
    dailyChangePercent: 0,
    xirr: null,
    avgHoldingDays: null,
    isZeroHolding: true,
    lastSaleDate: zh.last_sale_date
  })) : [];

  const allDisplayHoldings = [...sortedHoldings, ...zeroHoldingsFormatted];

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
            <div className={`market-index-card compact ${marketIndices.SENSEX?.change >= 0 ? 'positive' : 'negative'}`}>
              <div className="index-name">SENSEX</div>
              <div className="index-value">
                {(marketIndices.SENSEX?.value || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
              </div>
              <div className="index-change">
                {marketIndices.SENSEX?.change >= 0 ? '+' : ''}{(marketIndices.SENSEX?.change_percent || 0).toFixed(1)}%
              </div>
            </div>
          </Col>
          <Col xs={3}>
            <div className={`market-index-card compact ${marketIndices.NIFTY?.change >= 0 ? 'positive' : 'negative'}`}>
              <div className="index-name">NIFTY</div>
              <div className="index-value">
                {(marketIndices.NIFTY?.value || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
              </div>
              <div className="index-change">
                {marketIndices.NIFTY?.change >= 0 ? '+' : ''}{(marketIndices.NIFTY?.change_percent || 0).toFixed(1)}%
              </div>
            </div>
          </Col>
          <Col xs={3}>
            <div className={`market-index-card compact ${marketIndices.NASDAQ?.change >= 0 ? 'positive' : 'negative'}`}>
              <div className="index-name">NASDAQ</div>
              <div className="index-value">
                {(marketIndices.NASDAQ?.value || 0).toLocaleString('en-US', { maximumFractionDigits: 0 })}
              </div>
              <div className="index-change">
                {marketIndices.NASDAQ?.change >= 0 ? '+' : ''}{(marketIndices.NASDAQ?.change_percent || 0).toFixed(1)}%
              </div>
            </div>
          </Col>
          <Col xs={3}>
            <div className={`market-index-card compact ${marketIndices.DJI?.change >= 0 ? 'positive' : 'negative'}`}>
              <div className="index-name">DOW</div>
              <div className="index-value">
                {(marketIndices.DJI?.value || 0).toLocaleString('en-US', { maximumFractionDigits: 0 })}
              </div>
              <div className="index-change">
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
            <div className="d-none d-md-flex align-items-center gap-3">
              {portfolio.overall_xirr !== null && portfolio.overall_xirr !== undefined && (
                <div className="text-end">
                  <small className="text-muted">Portfolio XIRR</small>
                  <div className={`fw-bold ${portfolio.overall_xirr >= 0 ? 'text-success' : 'text-danger'}`}>
                    {portfolio.overall_xirr >= 0 ? '+' : ''}{portfolio.overall_xirr.toFixed(1)}%
                  </div>
                </div>
              )}
              {/* Show Zero Holdings Checkbox */}
              <Form.Check
                type="checkbox"
                id="show-zero-holdings"
                label="Show sold"
                checked={showZeroHoldings}
                onChange={handleShowZeroHoldingsChange}
                className="mb-0 me-2"
                style={{ fontSize: '0.85rem' }}
              />
              {/* Column Settings Dropdown */}
              <Dropdown autoClose="outside">
                <Dropdown.Toggle variant="outline-secondary" size="sm" id="column-settings">
                  <span style={{ fontSize: '0.85rem' }}>⚙ Columns</span>
                </Dropdown.Toggle>
                <Dropdown.Menu align="end" style={{ minWidth: '180px' }}>
                  <Dropdown.Header>Show/Hide Columns</Dropdown.Header>
                  {columnConfig.map(col => (
                    <div
                      key={col.key}
                      className="dropdown-item py-1"
                      style={{ cursor: 'pointer' }}
                      onClick={() => handleColumnToggle(col.key)}
                    >
                      <Form.Check
                        type="checkbox"
                        checked={visibleColumns[col.key]}
                        onChange={() => handleColumnToggle(col.key)}
                        label={col.label}
                        className="mb-0"
                        onClick={(e) => e.stopPropagation()}
                      />
                    </div>
                  ))}
                </Dropdown.Menu>
              </Dropdown>
            </div>
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
            {allDisplayHoldings.map(({ symbol, stock, currentVal, pnl, pnlPercent, dailyChange, dailyChangePercent, xirr, avgHoldingDays, isZeroHolding, lastSaleDate }) => {
              const isDay = sortConfig.key === 'dayPnl' || sortConfig.key === 'dayPnlPercent';
              const isXirr = sortConfig.key === 'xirr';
              const currentPrice = stock.quantity > 0 ? currentVal / stock.quantity : 0;
              const avgPrice = stock.quantity > 0 ? stock.total_invested / stock.quantity : 0;

              return (
                <div key={symbol} className={`holding-item-new px-3 py-2 border-bottom ${isZeroHolding ? 'opacity-75 bg-light' : ''}`}>
                  <div className="d-flex justify-content-between align-items-center">
                    <div>
                      <strong
                        className="holding-symbol"
                        style={{ cursor: 'pointer', textDecoration: 'underline', textDecorationStyle: 'dotted' }}
                        onClick={() => handleStockClick(symbol, stock)}
                      >
                        {symbol}
                        {isZeroHolding && <Badge bg="secondary" className="ms-2" style={{ fontSize: '0.65rem' }}>SOLD</Badge>}
                      </strong>
                      <div className="holding-meta">
                        {isZeroHolding ? (
                          <span className="text-muted">Realized P&L: <span className={pnl >= 0 ? 'text-success' : 'text-danger'}>₹{pnl.toLocaleString('en-IN', {maximumFractionDigits: 0})}</span></span>
                        ) : (
                          <>
                            {stock.quantity} shares @ ₹{avgPrice.toFixed(0)}, CMP{' '}
                            <span className={currentPrice >= avgPrice ? 'text-success' : 'text-danger'}>
                              ₹{currentPrice.toFixed(0)}
                            </span>
                          </>
                        )}
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
                  {visibleColumns.qty && (
                    <th
                      style={{ cursor: 'pointer' }}
                      onClick={() => handleSort('quantity')}
                      className="sortable-header"
                    >
                      Qty {sortConfig.key === 'quantity' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                    </th>
                  )}
                  {visibleColumns.avgPrice && (
                    <th
                      style={{ cursor: 'pointer' }}
                      onClick={() => handleSort('avgPrice')}
                      className="sortable-header"
                    >
                      Avg. Price {sortConfig.key === 'avgPrice' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                    </th>
                  )}
                  {visibleColumns.currentPrice && (
                    <th
                      style={{ cursor: 'pointer' }}
                      onClick={() => handleSort('currentPrice')}
                      className="sortable-header"
                    >
                      Current Price {sortConfig.key === 'currentPrice' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                    </th>
                  )}
                  {visibleColumns.invested && (
                    <th
                      style={{ cursor: 'pointer' }}
                      onClick={() => handleSort('invested')}
                      className="sortable-header d-none d-lg-table-cell"
                    >
                      Invested {sortConfig.key === 'invested' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                    </th>
                  )}
                  {visibleColumns.value && (
                    <th
                      style={{ cursor: 'pointer' }}
                      onClick={() => handleSort('value')}
                      className="sortable-header"
                    >
                      Value {sortConfig.key === 'value' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                    </th>
                  )}
                  {visibleColumns.dayPnl && (
                    <th
                      style={{ cursor: 'pointer' }}
                      onClick={() => handleSort('dayPnl')}
                      className="sortable-header"
                    >
                      Day P&L {sortConfig.key === 'dayPnl' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                    </th>
                  )}
                  {visibleColumns.totalPnl && (
                    <th
                      style={{ cursor: 'pointer' }}
                      onClick={() => handleSort('pnl')}
                      className="sortable-header"
                    >
                      Total P&L {sortConfig.key === 'pnl' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                    </th>
                  )}
                  {visibleColumns.xirr && (
                    <th
                      style={{ cursor: 'pointer' }}
                      onClick={() => handleSort('xirr')}
                      className="sortable-header"
                    >
                      XIRR {sortConfig.key === 'xirr' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                    </th>
                  )}
                  {visibleColumns.allocation && (
                    <th
                      style={{ cursor: 'pointer' }}
                      onClick={() => handleSort('allocation')}
                      className="sortable-header"
                    >
                      % {sortConfig.key === 'allocation' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                    </th>
                  )}
                </tr>
              </thead>
              <tbody>
                {allDisplayHoldings.map(({ symbol, stock, currentVal, pnl, pnlPercent, dailyChange, dailyChangePercent, xirr, avgHoldingDays, isZeroHolding, lastSaleDate }) => {
                  const currentPrice = stock.quantity > 0 ? currentVal / stock.quantity : 0;
                  const avgPrice = stock.quantity > 0 ? stock.total_invested / stock.quantity : 0;

                  return (
                    <tr key={symbol} className={isZeroHolding ? 'table-secondary opacity-75' : ''}>
                      <td>
                        <strong
                          style={{ cursor: 'pointer', textDecoration: 'underline', textDecorationStyle: 'dotted' }}
                          onClick={() => handleStockClick(symbol, stock)}
                        >
                          {symbol}
                        </strong>
                        {isZeroHolding && <Badge bg="secondary" className="ms-2" style={{ fontSize: '0.65rem' }}>SOLD</Badge>}
                      </td>
                      {visibleColumns.qty && <td>{isZeroHolding ? '-' : stock.quantity}</td>}
                      {visibleColumns.avgPrice && <td>{isZeroHolding ? '-' : `₹${avgPrice.toFixed(2)}`}</td>}
                      {visibleColumns.currentPrice && (
                        <td className={isZeroHolding ? 'text-muted' : (currentPrice >= avgPrice ? 'text-success' : 'text-danger')}>
                          {isZeroHolding ? '-' : `₹${currentPrice.toFixed(2)}`}
                        </td>
                      )}
                      {visibleColumns.invested && (
                        <td className="d-none d-lg-table-cell">{isZeroHolding ? '-' : `₹${stock.total_invested.toLocaleString('en-IN')}`}</td>
                      )}
                      {visibleColumns.value && (
                        <td className={isZeroHolding ? 'text-muted' : (pnl >= 0 ? 'text-success' : 'text-danger')}>
                          {isZeroHolding ? '-' : `₹${currentVal.toLocaleString('en-IN')}`}
                        </td>
                      )}
                      {visibleColumns.dayPnl && (
                        <td className={isZeroHolding ? 'text-muted' : (dailyChange >= 0 ? 'text-success' : 'text-danger')}>
                          {isZeroHolding ? '-' : (
                            <>
                              {dailyChange >= 0 ? '+' : ''}₹{dailyChange.toLocaleString('en-IN', {maximumFractionDigits: 0})}
                              <small className="d-block" style={{fontSize: '0.7rem'}}>
                                ({dailyChangePercent >= 0 ? '+' : ''}{dailyChangePercent.toFixed(1)}%)
                              </small>
                            </>
                          )}
                        </td>
                      )}
                      {visibleColumns.totalPnl && (
                        <td className={pnl >= 0 ? 'text-success' : 'text-danger'}>
                          {pnl >= 0 ? '+' : ''}₹{pnl.toLocaleString('en-IN', {maximumFractionDigits: 0})}
                          {!isZeroHolding && (
                            <small className="d-block" style={{fontSize: '0.7rem'}}>
                              ({pnlPercent >= 0 ? '+' : ''}{pnlPercent.toFixed(1)}%)
                            </small>
                          )}
                          {isZeroHolding && (
                            <small className="d-block text-muted" style={{fontSize: '0.7rem'}}>
                              Realized
                            </small>
                          )}
                        </td>
                      )}
                      {visibleColumns.xirr && (
                        <td className={xirr !== null ? (xirr >= 0 ? 'text-success' : 'text-danger') : 'text-muted'}>
                          {xirr !== null ? (
                            <>
                              {xirr >= 0 ? '+' : ''}{xirr.toFixed(1)}%
                              {avgHoldingDays !== null && (
                                <small className="d-block text-muted" style={{fontSize: '0.7rem'}}>
                                  {avgHoldingDays} days
                                </small>
                              )}
                            </>
                          ) : (
                            <small>N/A</small>
                          )}
                        </td>
                      )}
                      {visibleColumns.allocation && (
                        <td>
                          {currentValue > 0 ? (currentVal / currentValue * 100).toFixed(1) : 0}%
                        </td>
                      )}
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
                      pointRadius: 4,
                      pointHoverRadius: 6,
                      pointBackgroundColor: 'rgb(75, 192, 192)',
                      pointBorderColor: '#fff',
                      pointBorderWidth: 2
                    },
                    {
                      label: 'Current Value',
                      data: portfolioHistory.data_points.map((dp) => {
                        // Use current_value from snapshot if available, otherwise fall back to cost_basis
                        return dp.current_value !== undefined ? dp.current_value : dp.cost_basis;
                      }),
                      borderColor: portfolioHistory.current_value >= portfolioHistory.current_cost_basis
                        ? 'rgb(34, 197, 94)'
                        : 'rgb(239, 68, 68)',
                      backgroundColor: portfolioHistory.current_value >= portfolioHistory.current_cost_basis
                        ? 'rgba(34, 197, 94, 0.1)'
                        : 'rgba(239, 68, 68, 0.1)',
                      fill: true,
                      tension: 0.3,
                      pointRadius: 4,
                      pointHoverRadius: 6,
                      pointBackgroundColor: portfolioHistory.current_value >= portfolioHistory.current_cost_basis
                        ? 'rgb(34, 197, 94)'
                        : 'rgb(239, 68, 68)',
                      pointBorderColor: '#fff',
                      pointBorderWidth: 2
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

      {/* Stock Detail Modal */}
      <Modal show={showTxModal} onHide={() => setShowTxModal(false)} size="lg" centered>
        <Modal.Header closeButton>
          <Modal.Title>
            {selectedStock?.symbol}
          </Modal.Title>
        </Modal.Header>
        <Modal.Body style={{ maxHeight: '70vh', overflowY: 'auto' }}>
          <Tab.Container activeKey={activeModalTab} onSelect={handleModalTabChange}>
            <Nav variant="tabs" className="mb-3">
              <Nav.Item>
                <Nav.Link eventKey="chart">Chart</Nav.Link>
              </Nav.Item>
              <Nav.Item>
                <Nav.Link eventKey="news">News</Nav.Link>
              </Nav.Item>
              <Nav.Item>
                <Nav.Link eventKey="transactions">Transactions</Nav.Link>
              </Nav.Item>
            </Nav>

            <Tab.Content>
              {/* Chart Tab */}
              <Tab.Pane eventKey="chart">
                <div className="mb-3 d-flex justify-content-end">
                  <div className="btn-group btn-group-sm">
                    {['1d', '5d', '1m', '3m', '6m', '1y', '5y', 'max'].map(range => (
                      <Button
                        key={range}
                        variant={stockHistoryRange === range ? 'primary' : 'outline-secondary'}
                        size="sm"
                        onClick={() => handleStockHistoryRangeChange(range)}
                        style={{ minWidth: '40px', fontSize: '0.75rem', padding: '0.2rem 0.5rem' }}
                      >
                        {range === '1m' ? '1M' : range.toUpperCase()}
                      </Button>
                    ))}
                  </div>
                </div>

                {stockHistoryLoading ? (
                  <div className="text-center py-5">
                    <Spinner animation="border" size="sm" />
                    <span className="ms-2">Loading chart data...</span>
                  </div>
                ) : stockHistory && stockHistory.data_points && stockHistory.data_points.length > 0 ? (
                  <div style={{ height: '300px' }}>
                    <Line
                      data={{
                        labels: stockHistory.data_points.map(dp => {
                          const date = new Date(dp.date);
                          if (stockHistoryRange === '1d') {
                            return date.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });
                          }
                          if (stockHistoryRange === '5d') {
                            return date.toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric' });
                          }
                          if (stockHistoryRange === '1m' || stockHistoryRange === '3m') {
                            return date.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });
                          }
                          return date.toLocaleDateString('en-IN', { month: 'short', year: '2-digit' });
                        }),
                        datasets: [{
                          label: 'Close Price',
                          data: stockHistory.data_points.map(dp => dp.close),
                          borderColor: stockHistory.data_points.length > 1 &&
                            stockHistory.data_points[stockHistory.data_points.length - 1].close >= stockHistory.data_points[0].close
                            ? 'rgb(34, 197, 94)'
                            : 'rgb(239, 68, 68)',
                          backgroundColor: stockHistory.data_points.length > 1 &&
                            stockHistory.data_points[stockHistory.data_points.length - 1].close >= stockHistory.data_points[0].close
                            ? 'rgba(34, 197, 94, 0.1)'
                            : 'rgba(239, 68, 68, 0.1)',
                          fill: true,
                          tension: 0.3,
                          pointRadius: stockHistory.data_points.length > 60 ? 0 : 3,
                          pointHoverRadius: 5
                        }]
                      }}
                      options={{
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                          legend: { display: false },
                          tooltip: {
                            callbacks: {
                              label: (context) => `₹${context.parsed.y.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`
                            }
                          }
                        },
                        scales: {
                          y: {
                            ticks: {
                              callback: (value) => '₹' + value.toLocaleString('en-IN')
                            }
                          }
                        }
                      }}
                    />
                  </div>
                ) : (
                  <div className="text-center py-5 text-muted">
                    <p>No chart data available for this security</p>
                  </div>
                )}

                {/* Price summary below chart */}
                {stockHistory && stockHistory.data_points && stockHistory.data_points.length > 0 && (
                  <div className="mt-3 text-center">
                    <small className="text-muted">
                      {(() => {
                        const first = stockHistory.data_points[0];
                        const last = stockHistory.data_points[stockHistory.data_points.length - 1];
                        const change = last.close - first.close;
                        const changePercent = (change / first.close) * 100;
                        return (
                          <>
                            Open: ₹{first.close.toLocaleString('en-IN', { maximumFractionDigits: 2 })} |
                            Current: ₹{last.close.toLocaleString('en-IN', { maximumFractionDigits: 2 })} |
                            <span className={change >= 0 ? 'text-success' : 'text-danger'}>
                              {' '}{change >= 0 ? '+' : ''}{changePercent.toFixed(2)}%
                            </span>
                          </>
                        );
                      })()}
                    </small>
                  </div>
                )}
              </Tab.Pane>

              {/* News Tab */}
              <Tab.Pane eventKey="news">
                {stockNewsLoading ? (
                  <div className="text-center py-5">
                    <Spinner animation="border" size="sm" />
                    <span className="ms-2">Loading news...</span>
                  </div>
                ) : stockNews.length > 0 ? (
                  <div className="news-list">
                    {stockNews.map((article, idx) => (
                      <div key={idx} className="news-item border-bottom py-2">
                        <div className="d-flex justify-content-between align-items-start">
                          <div className="flex-grow-1">
                            <a
                              href={article.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-decoration-none"
                            >
                              <h6 className="mb-1">{article.title}</h6>
                            </a>
                            {article.description && (
                              <p className="text-muted small mb-1" style={{ lineHeight: '1.3' }}>
                                {article.description.length > 150
                                  ? article.description.substring(0, 150) + '...'
                                  : article.description}
                              </p>
                            )}
                            <small className="text-muted">
                              {article.source && <span>{article.source} • </span>}
                              {new Date(article.published_at).toLocaleDateString('en-IN', {
                                day: 'numeric',
                                month: 'short',
                                year: 'numeric'
                              })}
                            </small>
                          </div>
                          {article.sentiment && (
                            <Badge
                              bg={
                                article.sentiment === 'positive' ? 'success' :
                                article.sentiment === 'negative' ? 'danger' : 'secondary'
                              }
                              className="ms-2"
                              style={{ fontSize: '0.65rem' }}
                            >
                              {article.sentiment}
                            </Badge>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-5 text-muted">
                    <p>No news available for this security</p>
                  </div>
                )}
              </Tab.Pane>

              {/* Transactions Tab */}
              <Tab.Pane eventKey="transactions">
          {txLoading ? (
            <div className="text-center py-4">
              <Spinner animation="border" size="sm" />
              <span className="ms-2">Loading transactions...</span>
            </div>
          ) : stockTransactions.length > 0 ? (
            (() => {
              // Merge transactions and corporate events into a unified timeline
              const timeline = [
                ...stockTransactions.map(tx => ({
                  type: 'transaction',
                  date: new Date(tx.transaction_date),
                  data: tx
                })),
                ...stockCorporateEvents.map(evt => ({
                  type: 'corporate_event',
                  date: new Date(evt.event_date),
                  data: evt
                }))
              ];

              // Sort ascending (oldest first) to calculate running holdings
              timeline.sort((a, b) => a.date - b.date);

              // Calculate running holdings after each event
              let runningHoldings = 0;
              timeline.forEach(item => {
                if (item.type === 'transaction') {
                  const tx = item.data;
                  if (tx.transaction_type === 'BUY') {
                    runningHoldings += tx.quantity;
                  } else {
                    runningHoldings -= tx.quantity;
                  }
                  item.qtyChange = tx.transaction_type === 'BUY' ? tx.quantity : -tx.quantity;
                } else {
                  // Corporate event - calculate quantity change
                  const evt = item.data;
                  let qtyChange = 0;
                  if (evt.event_type === 'BONUS' && evt.ratio_numerator && evt.ratio_denominator) {
                    // Bonus: get ratio_numerator shares for every ratio_denominator held
                    qtyChange = Math.floor(runningHoldings * evt.ratio_numerator / evt.ratio_denominator);
                  } else if (evt.event_type === 'SPLIT' && evt.ratio_numerator && evt.ratio_denominator) {
                    // Split: each share becomes ratio_numerator/ratio_denominator shares
                    const newHoldings = Math.floor(runningHoldings * evt.ratio_numerator / evt.ratio_denominator);
                    qtyChange = newHoldings - runningHoldings;
                  }
                  runningHoldings += qtyChange;
                  item.qtyChange = qtyChange;
                }
                item.holdingsAfter = runningHoldings;
              });

              // Reverse to show most recent first
              timeline.reverse();

              // Calculate summary
              const txTotal = stockTransactions.reduce((sum, tx) =>
                sum + (tx.transaction_type === 'BUY' ? tx.total_amount : -tx.total_amount), 0
              );
              const currentHoldings = timeline.length > 0 ? timeline[0].holdingsAfter : 0;

              return (
                <Table bordered hover size="sm" responsive>
                  <thead className="table-dark">
                    <tr>
                      <th>Date</th>
                      <th>Type</th>
                      <th>Qty</th>
                      <th>Price</th>
                      <th>Total</th>
                      <th>Holdings</th>
                    </tr>
                  </thead>
                  <tbody>
                    {timeline.map((item, idx) => {
                      if (item.type === 'transaction') {
                        const tx = item.data;
                        return (
                          <tr key={`tx-${tx.id}`}>
                            <td>{item.date.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })}</td>
                            <td>
                              <Badge bg={tx.transaction_type === 'BUY' ? 'success' : 'danger'}>
                                {tx.transaction_type}
                              </Badge>
                            </td>
                            <td>{tx.transaction_type === 'BUY' ? '+' : '-'}{tx.quantity}</td>
                            <td>₹{tx.price_per_unit?.toFixed(2)}</td>
                            <td>₹{tx.total_amount?.toLocaleString('en-IN', { maximumFractionDigits: 0 })}</td>
                            <td><strong>{item.holdingsAfter}</strong></td>
                          </tr>
                        );
                      } else {
                        const evt = item.data;
                        const ratioStr = evt.ratio_numerator && evt.ratio_denominator
                          ? `${evt.ratio_numerator}:${evt.ratio_denominator}`
                          : '';
                        return (
                          <tr key={`evt-${evt.id}`} style={{ backgroundColor: '#e8f4f8' }}>
                            <td>{item.date.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })}</td>
                            <td>
                              <Badge bg="info">
                                {evt.event_type} {ratioStr}
                              </Badge>
                            </td>
                            <td className="text-info">
                              {item.qtyChange > 0 ? '+' : ''}{item.qtyChange}
                            </td>
                            <td colSpan="2" className="text-muted fst-italic small">
                              {evt.event_type === 'BONUS' && ratioStr && (
                                <>+{evt.ratio_numerator} for every {evt.ratio_denominator} held</>
                              )}
                              {evt.event_type === 'SPLIT' && ratioStr && (
                                <>{evt.ratio_numerator}:{evt.ratio_denominator} split</>
                              )}
                              {!ratioStr && evt.description}
                            </td>
                            <td><strong>{item.holdingsAfter}</strong></td>
                          </tr>
                        );
                      }
                    })}
                  </tbody>
                  <tfoot className="table-light">
                    <tr>
                      <td colSpan="2"><strong>Summary</strong></td>
                      <td></td>
                      <td></td>
                      <td>
                        <strong>₹{txTotal.toLocaleString('en-IN', { maximumFractionDigits: 0 })}</strong>
                      </td>
                      <td><strong>{currentHoldings}</strong></td>
                    </tr>
                  </tfoot>
                </Table>
              );
            })()
          ) : (
            <p className="text-center text-muted py-4">No transactions found for this stock</p>
          )}
              </Tab.Pane>
            </Tab.Content>
          </Tab.Container>
        </Modal.Body>
        <Modal.Footer className="justify-content-between">
          <small className="text-muted">
            {stockTransactions.length} transaction{stockTransactions.length !== 1 ? 's' : ''}
            {stockCorporateEvents.length > 0 && (
              <>, {stockCorporateEvents.length} corporate event{stockCorporateEvents.length !== 1 ? 's' : ''}</>
            )}
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
