import React, { useState, useEffect } from 'react';
import { Row, Col, Card, Table, Spinner, Button, Modal, Badge, Form, Alert } from 'react-bootstrap';
import { Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend, ArcElement } from 'chart.js';
import { Line, Doughnut } from 'react-chartjs-2';
import { apiService } from '../services/apiService';
import { useAuth } from '../context/AuthContext';
import { toast } from 'react-toastify';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend, ArcElement);

const BenchmarkComparison = () => {
  const [benchmarkAnalytics, setBenchmarkAnalytics] = useState(null);
  const [benchmarks, setBenchmarks] = useState([]);
  const [portfolioBenchmarks, setPortfolioBenchmarks] = useState([]);
  const [currentBenchmarkValues, setCurrentBenchmarkValues] = useState([]);
  const [selectedBenchmarkId, setSelectedBenchmarkId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [analyticsLoading, setAnalyticsLoading] = useState(false);
  const { selectedUserId, user, isAdmin } = useAuth();

  // Date range state
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');

  // Admin modal state
  const [showAdminModal, setShowAdminModal] = useState(false);
  const [adminAction, setAdminAction] = useState('');

  useEffect(() => {
    loadBenchmarkData();
  }, [selectedUserId]);

  useEffect(() => {
    if (selectedBenchmarkId || (portfolioBenchmarks.length > 0 && !selectedBenchmarkId)) {
      loadBenchmarkAnalytics();
    }
  }, [selectedUserId, selectedBenchmarkId, startDate, endDate]);

  const loadBenchmarkData = async () => {
    setLoading(true);
    try {
      const [benchmarksData, currentValuesData] = await Promise.all([
        apiService.getBenchmarks(),
        apiService.getCurrentBenchmarkValues()
      ]);

      setBenchmarks(benchmarksData);
      setCurrentBenchmarkValues(currentValuesData.benchmarks || []);

      // Load portfolio benchmarks if user selected
      if (selectedUserId) {
        const portfolioBenchmarksData = await apiService.getPortfolioBenchmarks(selectedUserId);
        setPortfolioBenchmarks(portfolioBenchmarksData.benchmarks || []);

        // Set default benchmark to primary benchmark if exists
        const primaryBenchmark = portfolioBenchmarksData.benchmarks?.find(pb => pb.is_primary);
        if (primaryBenchmark && !selectedBenchmarkId) {
          setSelectedBenchmarkId(primaryBenchmark.benchmark_id);
        }
      }
    } catch (error) {
      console.error('Error loading benchmark data:', error);
      toast.error('Failed to load benchmark data');
    } finally {
      setLoading(false);
    }
  };

  const loadBenchmarkAnalytics = async () => {
    if (!selectedUserId) return;

    setAnalyticsLoading(true);
    try {
      const benchmarkId = selectedBenchmarkId || (portfolioBenchmarks.length > 0 ? portfolioBenchmarks.find(pb => pb.is_primary)?.benchmark_id : null);
      
      if (!benchmarkId) {
        setBenchmarkAnalytics(null);
        return;
      }

      const analyticsData = await apiService.getPortfolioBenchmarkAnalytics(
        selectedUserId,
        benchmarkId,
        startDate || null,
        endDate || null
      );

      setBenchmarkAnalytics(analyticsData);
    } catch (error) {
      console.error('Error loading benchmark analytics:', error);
      toast.error('Failed to load benchmark analytics');
    } finally {
      setAnalyticsLoading(false);
    }
  };

  const handleBenchmarkChange = (benchmarkId) => {
    setSelectedBenchmarkId(parseInt(benchmarkId));
  };

  const handleInitializeBenchmarks = async () => {
    try {
      await apiService.initializeDefaultBenchmarks(user.email);
      toast.success('Default benchmarks initialized successfully');
      loadBenchmarkData();
    } catch (error) {
      console.error('Error initializing benchmarks:', error);
      toast.error('Failed to initialize benchmarks');
    }
  };

  const handleBackfillBenchmark = async (benchmarkId) => {
    try {
      const oneYearAgo = new Date();
      oneYearAgo.setFullYear(oneYearAgo.getFullYear() - 1);
      const startDate = oneYearAgo.toISOString().split('T')[0];

      await apiService.backfillBenchmarkData(benchmarkId, startDate, null, user.email);
      toast.success('Benchmark data backfilled successfully');
      loadBenchmarkData();
    } catch (error) {
      console.error('Error backfilling benchmark data:', error);
      toast.error('Failed to backfill benchmark data');
    }
  };

  const handleAssignBenchmark = async (benchmarkId, isPrimary = true) => {
    if (!selectedUserId) return;

    try {
      await apiService.assignBenchmarkToPortfolio(selectedUserId, benchmarkId, isPrimary, user.email);
      toast.success('Benchmark assigned to portfolio successfully');
      loadBenchmarkData();
    } catch (error) {
      console.error('Error assigning benchmark:', error);
      toast.error('Failed to assign benchmark');
    }
  };

  const formatNumber = (num) => {
    if (num === null || num === undefined) return 'N/A';
    return new Intl.NumberFormat('en-IN').format(num);
  };

  const formatPercent = (num, decimals = 2) => {
    if (num === null || num === undefined) return 'N/A';
    return `${num.toFixed(decimals)}%`;
  };

  const renderPerformanceCard = (title, portfolioValue, benchmarkValue, unit = '%') => (
    <Card className="mb-3">
      <Card.Body>
        <h6 className="text-muted mb-2">{title}</h6>
        <Row>
          <Col xs={6}>
            <div className="text-center">
              <div className="h5 mb-0 text-primary">
                {portfolioValue !== null ? `${portfolioValue.toFixed(2)}${unit}` : 'N/A'}
              </div>
              <small className="text-muted">Portfolio</small>
            </div>
          </Col>
          <Col xs={6}>
            <div className="text-center">
              <div className="h5 mb-0 text-secondary">
                {benchmarkValue !== null ? `${benchmarkValue.toFixed(2)}${unit}` : 'N/A'}
              </div>
              <small className="text-muted">Benchmark</small>
            </div>
          </Col>
        </Row>
        {portfolioValue !== null && benchmarkValue !== null && (
          <div className="text-center mt-2">
            <Badge bg={portfolioValue > benchmarkValue ? 'success' : 'danger'}>
              {portfolioValue > benchmarkValue ? '✓' : '✗'} 
              {' '}
              {Math.abs(portfolioValue - benchmarkValue).toFixed(2)}{unit}
            </Badge>
          </div>
        )}
      </Card.Body>
    </Card>
  );

  if (loading) {
    return (
      <div className="text-center p-4">
        <Spinner animation="border" role="status">
          <span className="visually-hidden">Loading...</span>
        </Spinner>
        <p className="mt-2">Loading benchmark comparison...</p>
      </div>
    );
  }

  return (
    <div className="p-4">
      <Row>
        <Col>
          <div className="d-flex justify-content-between align-items-center mb-4">
            <h2>📊 Benchmark Comparison</h2>
            {isAdmin && (
              <Button variant="outline-secondary" size="sm" onClick={() => setShowAdminModal(true)}>
                Admin Tools
              </Button>
            )}
          </div>
        </Col>
      </Row>

      {/* Current Benchmark Values */}
      {currentBenchmarkValues.length > 0 && (
        <Row className="mb-4">
          <Col>
            <Card>
              <Card.Header>📈 Market Indices</Card.Header>
              <Card.Body>
                <Row>
                  {currentBenchmarkValues.map((benchmark) => (
                    <Col md={6} lg={3} key={benchmark.benchmark.id} className="mb-3">
                      <Card className="h-100 border-0" style={{ backgroundColor: '#f8f9fa' }}>
                        <Card.Body className="text-center">
                          <h6 className="mb-1">{benchmark.benchmark.name}</h6>
                          <div className="h5 mb-2">{formatNumber(benchmark.current_value)}</div>
                          <Badge bg={benchmark.change >= 0 ? 'success' : 'danger'}>
                            {benchmark.change >= 0 ? '+' : ''}{benchmark.change} ({formatPercent(benchmark.change_percent)})
                          </Badge>
                          {benchmark.last_updated && (
                            <div className="mt-1">
                              <small className="text-muted">Updated: {new Date(benchmark.last_updated).toLocaleDateString()}</small>
                            </div>
                          )}
                        </Card.Body>
                      </Card>
                    </Col>
                  ))}
                </Row>
              </Card.Body>
            </Card>
          </Col>
        </Row>
      )}

      {/* Portfolio vs Benchmark Analytics */}
      {selectedUserId && (
        <Row>
          <Col lg={8}>
            <Card className="mb-4">
              <Card.Header>
                <div className="d-flex justify-content-between align-items-center">
                  <span>📊 Performance Analysis</span>
                  <div className="d-flex gap-2">
                    <Form.Control
                      type="date"
                      size="sm"
                      placeholder="Start Date"
                      value={startDate}
                      onChange={(e) => setStartDate(e.target.value)}
                      style={{ width: '150px' }}
                    />
                    <Form.Control
                      type="date"
                      size="sm"
                      placeholder="End Date"
                      value={endDate}
                      onChange={(e) => setEndDate(e.target.value)}
                      style={{ width: '150px' }}
                    />
                    <Form.Select
                      size="sm"
                      value={selectedBenchmarkId || ''}
                      onChange={(e) => handleBenchmarkChange(e.target.value)}
                      style={{ width: '200px' }}
                    >
                      <option value="">Select Benchmark</option>
                      {benchmarks.map((benchmark) => (
                        <option key={benchmark.id} value={benchmark.id}>
                          {benchmark.name}
                        </option>
                      ))}
                    </Form.Select>
                  </div>
                </div>
              </Card.Header>
              <Card.Body>
                {analyticsLoading ? (
                  <div className="text-center p-4">
                    <Spinner animation="border" role="status" size="sm" />
                    <span className="ms-2">Loading analytics...</span>
                  </div>
                ) : benchmarkAnalytics ? (
                  <div>
                    <Alert variant="info" className="mb-3">
                      <strong>{benchmarkAnalytics.benchmark.name}</strong> comparison for{' '}
                      {benchmarkAnalytics.total_days} days
                      {benchmarkAnalytics.start_date && benchmarkAnalytics.end_date && (
                        <span> ({new Date(benchmarkAnalytics.start_date).toLocaleDateString()} - {new Date(benchmarkAnalytics.end_date).toLocaleDateString()})</span>
                      )}
                    </Alert>

                    <Row>
                      <Col md={4}>
                        {renderPerformanceCard(
                          'Total Return',
                          benchmarkAnalytics.portfolio_total_return,
                          benchmarkAnalytics.benchmark_total_return
                        )}
                      </Col>
                      <Col md={4}>
                        {renderPerformanceCard(
                          'XIRR (Annualized)',
                          benchmarkAnalytics.portfolio_xirr,
                          benchmarkAnalytics.benchmark_xirr
                        )}
                      </Col>
                      <Col md={4}>
                        {renderPerformanceCard(
                          'Volatility',
                          benchmarkAnalytics.volatility_portfolio,
                          benchmarkAnalytics.volatility_benchmark
                        )}
                      </Col>
                    </Row>

                    <Row>
                      <Col md={4}>
                        <Card className="mb-3">
                          <Card.Body className="text-center">
                            <h6 className="text-muted mb-2">Alpha (Excess Return)</h6>
                            <div className={`h4 mb-0 ${benchmarkAnalytics.alpha_annualized > 0 ? 'text-success' : 'text-danger'}`}>
                              {benchmarkAnalytics.alpha_annualized ? formatPercent(benchmarkAnalytics.alpha_annualized) : 'N/A'}
                            </div>
                            <small className="text-muted">Annualized</small>
                          </Card.Body>
                        </Card>
                      </Col>
                      <Col md={4}>
                        <Card className="mb-3">
                          <Card.Body className="text-center">
                            <h6 className="text-muted mb-2">Beta</h6>
                            <div className="h4 mb-0 text-info">
                              {benchmarkAnalytics.beta ? benchmarkAnalytics.beta.toFixed(2) : 'N/A'}
                            </div>
                            <small className="text-muted">Market Sensitivity</small>
                          </Card.Body>
                        </Card>
                      </Col>
                      <Col md={4}>
                        <Card className="mb-3">
                          <Card.Body className="text-center">
                            <h6 className="text-muted mb-2">Correlation</h6>
                            <div className="h4 mb-0 text-warning">
                              {benchmarkAnalytics.correlation ? benchmarkAnalytics.correlation.toFixed(2) : 'N/A'}
                            </div>
                            <small className="text-muted">Benchmark Correlation</small>
                          </Card.Body>
                        </Card>
                      </Col>
                    </Row>

                    {/* Outperformance Summary */}
                    <Card className="mt-3" style={{ backgroundColor: benchmarkAnalytics.outperformance_total > 0 ? '#d4edda' : '#f8d7da' }}>
                      <Card.Body className="text-center">
                        <h5 className={benchmarkAnalytics.outperformance_total > 0 ? 'text-success' : 'text-danger'}>
                          {benchmarkAnalytics.outperformance_total > 0 ? '🎉 Portfolio Outperforming!' : '📉 Portfolio Underperforming'}
                        </h5>
                        <p className="mb-0">
                          Your portfolio {benchmarkAnalytics.outperformance_total > 0 ? 'beat' : 'lagged'} {benchmarkAnalytics.benchmark.name} by{' '}
                          <strong>{formatPercent(Math.abs(benchmarkAnalytics.outperformance_total))}</strong>
                          {benchmarkAnalytics.outperformance_xirr && (
                            <span> (XIRR: {formatPercent(Math.abs(benchmarkAnalytics.outperformance_xirr))})</span>
                          )}
                        </p>
                      </Card.Body>
                    </Card>
                  </div>
                ) : (
                  <Alert variant="warning">
                    No benchmark data available. Please select a benchmark and ensure it has historical data.
                  </Alert>
                )}
              </Card.Body>
            </Card>
          </Col>

          <Col lg={4}>
            <Card>
              <Card.Header>⚙️ Portfolio Benchmarks</Card.Header>
              <Card.Body>
                {portfolioBenchmarks.length > 0 ? (
                  <div>
                    {portfolioBenchmarks.map((pb) => (
                      <div key={pb.id} className="border-bottom pb-2 mb-2">
                        <div className="d-flex justify-content-between align-items-center">
                          <div>
                            <strong>{pb.benchmark.name}</strong>
                            {pb.is_primary && (
                              <Badge bg="primary" className="ms-2">Primary</Badge>
                            )}
                          </div>
                          <Button
                            variant="outline-primary"
                            size="sm"
                            onClick={() => setSelectedBenchmarkId(pb.benchmark_id)}
                            disabled={selectedBenchmarkId === pb.benchmark_id}
                          >
                            {selectedBenchmarkId === pb.benchmark_id ? 'Selected' : 'Select'}
                          </Button>
                        </div>
                        <small className="text-muted">
                          Since: {new Date(pb.start_date).toLocaleDateString()}
                        </small>
                      </div>
                    ))}
                  </div>
                ) : (
                  <Alert variant="info">
                    No benchmarks assigned to this portfolio. Admin can assign benchmarks using the tools above.
                  </Alert>
                )}
              </Card.Body>
            </Card>
          </Col>
        </Row>
      )}

      {/* Admin Modal */}
      <Modal show={showAdminModal} onHide={() => setShowAdminModal(false)} size="lg">
        <Modal.Header closeButton>
          <Modal.Title>Benchmark Admin Tools</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <Row>
            <Col md={6}>
              <Card className="mb-3">
                <Card.Body>
                  <h6>Initialize Default Benchmarks</h6>
                  <p className="small text-muted">Add NIFTY 50 and BSE Sensex to the system</p>
                  <Button variant="primary" size="sm" onClick={handleInitializeBenchmarks}>
                    Initialize Benchmarks
                  </Button>
                </Card.Body>
              </Card>
            </Col>
            <Col md={6}>
              <Card className="mb-3">
                <Card.Body>
                  <h6>Assign Benchmarks</h6>
                  <p className="small text-muted">Assign benchmarks to selected portfolio</p>
                  {benchmarks.map((benchmark) => (
                    <div key={benchmark.id} className="mb-2">
                      <Button
                        variant="outline-secondary"
                        size="sm"
                        onClick={() => handleAssignBenchmark(benchmark.id)}
                        disabled={!selectedUserId}
                      >
                        Assign {benchmark.name}
                      </Button>
                    </div>
                  ))}
                </Card.Body>
              </Card>
            </Col>
          </Row>

          {benchmarks.length > 0 && (
            <Card>
              <Card.Body>
                <h6>Backfill Historical Data</h6>
                <p className="small text-muted">Load 1 year of historical data for each benchmark</p>
                <Row>
                  {benchmarks.map((benchmark) => (
                    <Col md={6} key={benchmark.id} className="mb-2">
                      <Button
                        variant="outline-success"
                        size="sm"
                        onClick={() => handleBackfillBenchmark(benchmark.id)}
                        className="w-100"
                      >
                        Backfill {benchmark.name}
                      </Button>
                    </Col>
                  ))}
                </Row>
              </Card.Body>
            </Card>
          )}
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={() => setShowAdminModal(false)}>
            Close
          </Button>
        </Modal.Footer>
      </Modal>
    </div>
  );
};

export default BenchmarkComparison;