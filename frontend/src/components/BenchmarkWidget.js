import React, { useState, useEffect } from 'react';
import { Card, Spinner, Badge, Button, Row, Col } from 'react-bootstrap';
import { Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend } from 'chart.js';
import { Line } from 'react-chartjs-2';
import { apiService } from '../services/apiService';
import { useNavigate } from 'react-router-dom';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend);

const BenchmarkWidget = ({ userId }) => {
  const [currentBenchmarkValues, setCurrentBenchmarkValues] = useState([]);
  const [portfolioAnalytics, setPortfolioAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    loadBenchmarkData();
  }, [userId]);

  const loadBenchmarkData = async () => {
    if (!userId) return;

    setLoading(true);
    try {
      const [currentValues, portfolioBenchmarks] = await Promise.all([
        apiService.getCurrentBenchmarkValues(),
        apiService.getPortfolioBenchmarks(userId)
      ]);

      setCurrentBenchmarkValues(currentValues.benchmarks || []);

      // If user has a primary benchmark, load analytics
      const primaryBenchmark = portfolioBenchmarks.benchmarks?.find(pb => pb.is_primary);
      if (primaryBenchmark) {
        try {
          const analytics = await apiService.getPortfolioBenchmarkAnalytics(userId);
          setPortfolioAnalytics(analytics);
        } catch (error) {
          console.error('Error loading portfolio analytics:', error);
          // Don't show error, just skip analytics
        }
      }
    } catch (error) {
      console.error('Error loading benchmark data:', error);
    } finally {
      setLoading(false);
    }
  };

  const formatNumber = (num) => {
    if (num === null || num === undefined) return 'N/A';
    return new Intl.NumberFormat('en-IN').format(Math.round(num));
  };

  const formatPercent = (num, decimals = 1) => {
    if (num === null || num === undefined) return 'N/A';
    return `${num.toFixed(decimals)}%`;
  };

  if (loading) {
    return (
      <Card className="h-100">
        <Card.Header className="d-flex justify-content-between align-items-center">
          <span>📈 Market Benchmarks</span>
        </Card.Header>
        <Card.Body className="d-flex justify-content-center align-items-center">
          <Spinner animation="border" size="sm" />
        </Card.Body>
      </Card>
    );
  }

  return (
    <Card className="h-100">
      <Card.Header className="d-flex justify-content-between align-items-center">
        <span>📈 Market Benchmarks</span>
        <Button 
          variant="outline-primary" 
          size="sm"
          onClick={() => navigate('/benchmark-comparison')}
        >
          View Details
        </Button>
      </Card.Header>
      <Card.Body>
        {/* Current Market Indices */}
        <Row className="mb-3">
          {currentBenchmarkValues.slice(0, 2).map((benchmark) => (
            <Col xs={6} key={benchmark.benchmark.id}>
              <div className="text-center p-2 border rounded">
                <div className="fw-bold small">{benchmark.benchmark.name}</div>
                <div className="h6 mb-1">{formatNumber(benchmark.current_value)}</div>
                <Badge bg={benchmark.change >= 0 ? 'success' : 'danger'} className="small">
                  {benchmark.change >= 0 ? '+' : ''}{benchmark.change} ({formatPercent(benchmark.change_percent)})
                </Badge>
              </div>
            </Col>
          ))}
        </Row>

        {/* Portfolio vs Benchmark Performance */}
        {portfolioAnalytics && (
          <div>
            <div className="text-center mb-3">
              <div className="fw-bold small text-muted">Portfolio vs {portfolioAnalytics.benchmark.name}</div>
              <div className={`h5 mb-0 ${portfolioAnalytics.outperformance_total > 0 ? 'text-success' : 'text-danger'}`}>
                {portfolioAnalytics.outperformance_total > 0 ? '📈 Outperforming' : '📉 Underperforming'}
              </div>
              <Badge bg={portfolioAnalytics.outperformance_total > 0 ? 'success' : 'danger'}>
                {portfolioAnalytics.outperformance_total > 0 ? '+' : ''}{formatPercent(portfolioAnalytics.outperformance_total)}
              </Badge>
            </div>

            <Row className="text-center small">
              <Col xs={4}>
                <div className="text-muted">Portfolio Return</div>
                <div className="fw-bold text-primary">{formatPercent(portfolioAnalytics.portfolio_total_return)}</div>
              </Col>
              <Col xs={4}>
                <div className="text-muted">Benchmark Return</div>
                <div className="fw-bold text-secondary">{formatPercent(portfolioAnalytics.benchmark_total_return)}</div>
              </Col>
              <Col xs={4}>
                <div className="text-muted">Alpha</div>
                <div className={`fw-bold ${portfolioAnalytics.alpha_annualized > 0 ? 'text-success' : 'text-danger'}`}>
                  {portfolioAnalytics.alpha_annualized ? formatPercent(portfolioAnalytics.alpha_annualized) : 'N/A'}
                </div>
              </Col>
            </Row>

            {portfolioAnalytics.beta && (
              <div className="text-center mt-2">
                <small className="text-muted">
                  Beta: <span className="fw-bold">{portfolioAnalytics.beta.toFixed(2)}</span>
                  {portfolioAnalytics.correlation && (
                    <span> | Correlation: <span className="fw-bold">{portfolioAnalytics.correlation.toFixed(2)}</span></span>
                  )}
                </small>
              </div>
            )}
          </div>
        )}

        {!portfolioAnalytics && (
          <div className="text-center text-muted">
            <small>Assign a benchmark to see performance comparison</small>
          </div>
        )}
      </Card.Body>
    </Card>
  );
};

export default BenchmarkWidget;