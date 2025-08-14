import React, { useState, useEffect } from 'react';
import { Container, Row, Col, Card, Form, Table, Badge, Button, Collapse, Alert, Spinner } from 'react-bootstrap';
import { useAuth } from '../context/AuthContext';
import { apiService } from '../services/apiService';
import { toast } from 'react-toastify';

const CapitalGains = () => {
  const { user, selectedUserId, isAllUsers } = useAuth();
  const [loading, setLoading] = useState(false);
  const [availableYears, setAvailableYears] = useState([]);
  const [selectedYear, setSelectedYear] = useState('');
  const [capitalGains, setCapitalGains] = useState(null);
  const [expandedSecurities, setExpandedSecurities] = useState({});

  useEffect(() => {
    loadAvailableYears();
  }, [user, selectedUserId]);

  useEffect(() => {
    if (selectedYear) {
      loadCapitalGains();
    }
  }, [selectedYear, user, selectedUserId]);

  const loadAvailableYears = async () => {
    try {
      setLoading(true);
      const userId = selectedUserId;
      const response = await apiService.getCapitalGainsAvailableYears(userId);
      setAvailableYears(response.available_years || []);
      
      // Set current financial year as default if available
      if (response.available_years?.length > 0) {
        const currentFY = response.current_financial_year;
        const defaultYear = response.available_years.includes(currentFY) 
          ? currentFY 
          : response.available_years[0];
        setSelectedYear(defaultYear.toString());
      }
    } catch (error) {
      console.error('Error loading available years:', error);
      toast.error('Failed to load available years');
    } finally {
      setLoading(false);
    }
  };

  const loadCapitalGains = async () => {
    if (!selectedYear) return;
    
    try {
      setLoading(true);
      const userId = selectedUserId;
      const response = await apiService.getCapitalGains(parseInt(selectedYear), userId);
      setCapitalGains(response);
    } catch (error) {
      console.error('Error loading capital gains:', error);
      
      // Enhanced error handling
      if (error.response?.status === 400) {
        toast.error(error.response.data?.detail || 'Invalid request parameters');
      } else if (error.response?.status === 404) {
        toast.error('User not found');
      } else if (error.response?.status >= 500) {
        toast.error('Server error occurred. Please try again later.');
      } else {
        toast.error('Failed to load capital gains data');
      }
      
      // Clear data on error
      setCapitalGains(null);
    } finally {
      setLoading(false);
    }
  };

  const toggleSecurityDetails = (securityName) => {
    setExpandedSecurities(prev => ({
      ...prev,
      [securityName]: !prev[securityName]
    }));
  };

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR'
    }).format(amount || 0);
  };

  const formatPercentage = (percentage) => {
    return `${percentage >= 0 ? '+' : ''}${percentage.toFixed(2)}%`;
  };

  const getGainLossColor = (amount) => {
    if (amount > 0) return 'success';
    if (amount < 0) return 'danger';
    return 'secondary';
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('en-IN');
  };

  if (loading && !capitalGains) {
    return (
      <Container className="mt-4">
        <div className="text-center">
          <Spinner animation="border" variant="primary" />
          <p className="mt-2">Loading capital gains data...</p>
        </div>
      </Container>
    );
  }

  return (
    <Container fluid className="mt-4">
      <Row>
        <Col>
          <h2 className="mb-4">Capital Gains Analysis</h2>
          
          {/* Year Selection */}
          <Card className="mb-4">
            <Card.Body>
              <Row className="align-items-center">
                <Col md={6}>
                  <Form.Group>
                    <Form.Label>Select Financial Year:</Form.Label>
                    <Form.Select 
                      value={selectedYear} 
                      onChange={(e) => {
                        const year = e.target.value;
                        if (year && (isNaN(year) || year < 2000 || year > new Date().getFullYear() + 1)) {
                          toast.error('Please select a valid financial year');
                          return;
                        }
                        setSelectedYear(year);
                      }}
                      disabled={loading}
                    >
                      <option value="">Select a financial year...</option>
                      {availableYears.map(year => (
                        <option key={year} value={year}>
                          FY {year}-{year + 1}
                        </option>
                      ))}
                    </Form.Select>
                  </Form.Group>
                </Col>
                <Col md={6}>
                  <p className="text-muted mb-0">
                    {isAllUsers ? 'Showing data for all users' : `Showing data for selected user`}
                  </p>
                </Col>
              </Row>
            </Card.Body>
          </Card>

          {availableYears.length === 0 && !loading && (
            <Alert variant="info">
              <Alert.Heading>No Capital Gains Data Available</Alert.Heading>
              <p>
                No sell transactions found. Capital gains are calculated only when you have sell transactions.
                Upload your contract notes or manually enter sell transactions to see capital gains analysis.
              </p>
            </Alert>
          )}

          {/* Summary Cards */}
          {capitalGains && (
            <>
              <Row className="mb-4">
                <Col md={4}>
                  <Card className="h-100">
                    <Card.Body className="text-center">
                      <h5 className="card-title">Total Gain/Loss</h5>
                      <h3 className={`text-${getGainLossColor(capitalGains.total_gain_loss)}`}>
                        {formatCurrency(capitalGains.total_gain_loss)}
                      </h3>
                    </Card.Body>
                  </Card>
                </Col>
                <Col md={4}>
                  <Card className="h-100">
                    <Card.Body className="text-center">
                      <h5 className="card-title">Short Term Gain/Loss</h5>
                      <h3 className={`text-${getGainLossColor(capitalGains.short_term_gain_loss)}`}>
                        {formatCurrency(capitalGains.short_term_gain_loss)}
                      </h3>
                      <small className="text-muted">Holdings ≤ 1 year</small>
                    </Card.Body>
                  </Card>
                </Col>
                <Col md={4}>
                  <Card className="h-100">
                    <Card.Body className="text-center">
                      <h5 className="card-title">Long Term Gain/Loss</h5>
                      <h3 className={`text-${getGainLossColor(capitalGains.long_term_gain_loss)}`}>
                        {formatCurrency(capitalGains.long_term_gain_loss)}
                      </h3>
                      <small className="text-muted">Holdings > 1 year</small>
                    </Card.Body>
                  </Card>
                </Col>
              </Row>

              {/* Securities Breakdown */}
              <Card>
                <Card.Header>
                  <h5 className="mb-0">Securities Breakdown - {capitalGains.financial_year}</h5>
                </Card.Header>
                <Card.Body>
                  {capitalGains.securities.length === 0 ? (
                    <Alert variant="info">
                      No realized gains/losses for the selected financial year.
                    </Alert>
                  ) : (
                    <Table responsive hover>
                      <thead>
                        <tr>
                          <th>Security</th>
                          <th>ISIN</th>
                          <th className="text-end">Total Gain/Loss</th>
                          <th className="text-end">Short Term</th>
                          <th className="text-end">Long Term</th>
                          <th className="text-center">Details</th>
                        </tr>
                      </thead>
                      <tbody>
                        {capitalGains.securities.map((security, index) => (
                          <React.Fragment key={index}>
                            <tr>
                              <td>
                                <strong>{security.security_name}</strong>
                                {security.security_symbol && (
                                  <div className="text-muted small">
                                    {security.security_symbol}
                                  </div>
                                )}
                              </td>
                              <td>
                                <small className="text-muted">
                                  {security.isin || 'N/A'}
                                </small>
                              </td>
                              <td className="text-end">
                                <Badge bg={getGainLossColor(security.total_gain_loss)}>
                                  {formatCurrency(security.total_gain_loss)}
                                </Badge>
                              </td>
                              <td className="text-end">
                                <span className={`text-${getGainLossColor(security.short_term_gain_loss)}`}>
                                  {formatCurrency(security.short_term_gain_loss)}
                                </span>
                              </td>
                              <td className="text-end">
                                <span className={`text-${getGainLossColor(security.long_term_gain_loss)}`}>
                                  {formatCurrency(security.long_term_gain_loss)}
                                </span>
                              </td>
                              <td className="text-center">
                                <Button
                                  variant="outline-primary"
                                  size="sm"
                                  onClick={() => toggleSecurityDetails(security.security_name)}
                                >
                                  {expandedSecurities[security.security_name] ? 'Hide' : 'Show'} Details
                                </Button>
                              </td>
                            </tr>
                            
                            {/* Details Row */}
                            <tr>
                              <td colSpan="6" className="p-0">
                                <Collapse in={expandedSecurities[security.security_name]}>
                                  <div className="p-3 bg-light">
                                    <h6>Transaction Details for {security.security_name}</h6>
                                    <Table size="sm" className="mb-0">
                                      <thead>
                                        <tr>
                                          <th>Buy Date</th>
                                          <th>Sell Date</th>
                                          <th className="text-end">Quantity</th>
                                          <th className="text-end">Buy Price</th>
                                          <th className="text-end">Sell Price</th>
                                          <th className="text-end">Gain/Loss</th>
                                          <th className="text-end">Return %</th>
                                          <th className="text-center">Days Held</th>
                                          <th className="text-center">Type</th>
                                        </tr>
                                      </thead>
                                      <tbody>
                                        {security.details.map((detail, detailIndex) => (
                                          <tr key={detailIndex}>
                                            <td>{formatDate(detail.buy_transaction.transaction_date)}</td>
                                            <td>{formatDate(detail.sell_transaction.transaction_date)}</td>
                                            <td className="text-end">{detail.quantity_sold}</td>
                                            <td className="text-end">{formatCurrency(detail.buy_price_per_unit)}</td>
                                            <td className="text-end">{formatCurrency(detail.sell_price_per_unit)}</td>
                                            <td className="text-end">
                                              <span className={`text-${getGainLossColor(detail.gain_loss)}`}>
                                                {formatCurrency(detail.gain_loss)}
                                              </span>
                                            </td>
                                            <td className="text-end">
                                              <span className={`text-${getGainLossColor(detail.gain_loss_percentage)}`}>
                                                {formatPercentage(detail.gain_loss_percentage)}
                                              </span>
                                            </td>
                                            <td className="text-center">{detail.holding_period_days}</td>
                                            <td className="text-center">
                                              <Badge bg={detail.is_long_term ? 'info' : 'warning'}>
                                                {detail.is_long_term ? 'Long Term' : 'Short Term'}
                                              </Badge>
                                            </td>
                                          </tr>
                                        ))}
                                      </tbody>
                                    </Table>
                                  </div>
                                </Collapse>
                              </td>
                            </tr>
                          </React.Fragment>
                        ))}
                      </tbody>
                    </Table>
                  )}
                </Card.Body>
              </Card>
            </>
          )}
        </Col>
      </Row>
    </Container>
  );
};

export default CapitalGains;