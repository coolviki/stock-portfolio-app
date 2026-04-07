import React, { useState, useEffect } from 'react';
import { Container, Row, Col, Card, Form, Table, Badge, Button, Collapse, Alert, Spinner, ToggleButtonGroup, ToggleButton } from 'react-bootstrap';
import { useAuth } from '../context/AuthContext';
import { apiService } from '../services/apiService';
import { toast } from 'react-toastify';

const CapitalGains = () => {
  const { user } = useAuth();
  const [loading, setLoading] = useState(false);
  const [availableYears, setAvailableYears] = useState([]);
  const [selectedYear, setSelectedYear] = useState('');
  const [capitalGains, setCapitalGains] = useState(null);
  const [adjustedCapitalGains, setAdjustedCapitalGains] = useState(null);
  const [expandedSecurities, setExpandedSecurities] = useState({});
  const [viewMode, setViewMode] = useState('adjusted'); // 'original', 'adjusted', 'both' - default to adjusted for accurate lot-based calculation

  useEffect(() => {
    loadAvailableYears();
  }, [user]);

  useEffect(() => {
    if (selectedYear) {
      // Always load adjusted data (lot-based) as it's more accurate
      loadAdjustedCapitalGains();
      if (viewMode === 'original' || viewMode === 'both') {
        loadCapitalGains();
      }
    }
  }, [selectedYear, user]);

  useEffect(() => {
    if (selectedYear && (viewMode === 'adjusted' || viewMode === 'both') && !adjustedCapitalGains) {
      loadAdjustedCapitalGains();
    }
  }, [viewMode]);

  const loadAvailableYears = async () => {
    try {
      setLoading(true);
      const userId = user?.id;
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
      const userId = user?.id;
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

  const loadAdjustedCapitalGains = async () => {
    if (!selectedYear) return;

    try {
      setLoading(true);
      const userId = user?.id;
      const response = await apiService.getAdjustedCapitalGains(parseInt(selectedYear), userId);
      setAdjustedCapitalGains(response);
    } catch (error) {
      console.error('Error loading adjusted capital gains:', error);
      // Silently fail for adjusted gains - they may not be available if no lots exist
      setAdjustedCapitalGains(null);
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
          
          {/* Year Selection and View Mode */}
          <Card className="mb-4">
            <Card.Body>
              <Row className="align-items-center">
                <Col md={4}>
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
                        setAdjustedCapitalGains(null);
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
                <Col md={4}>
                  <Form.Group>
                    <Form.Label>Cost Basis View:</Form.Label>
                    <div>
                      <ToggleButtonGroup
                        type="radio"
                        name="viewMode"
                        value={viewMode}
                        onChange={(val) => setViewMode(val)}
                      >
                        <ToggleButton id="view-original" value="original" variant="outline-primary" size="sm">
                          Original
                        </ToggleButton>
                        <ToggleButton id="view-adjusted" value="adjusted" variant="outline-success" size="sm">
                          Adjusted
                        </ToggleButton>
                        <ToggleButton id="view-both" value="both" variant="outline-info" size="sm">
                          Compare
                        </ToggleButton>
                      </ToggleButtonGroup>
                    </div>
                    <Form.Text className="text-muted">
                      Adjusted values reflect corporate events (splits, bonuses)
                    </Form.Text>
                  </Form.Group>
                </Col>
                <Col md={4}>
                  <p className="text-muted mb-0">
                    {`Showing data for ${user?.username || 'current user'}`}
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
          {(capitalGains || adjustedCapitalGains) && (
            <>
              <Row className="mb-4">
                <Col md={4}>
                  <Card className="h-100">
                    <Card.Body className="text-center">
                      <h5 className="card-title">Total Gain/Loss</h5>
                      {viewMode === 'both' && adjustedCapitalGains && capitalGains ? (
                        <>
                          <div className="mb-2">
                            <small className="text-muted">Original:</small>
                            <h4 className={`text-${getGainLossColor(capitalGains.total_gain_loss)} mb-0`}>
                              {formatCurrency(capitalGains.total_gain_loss)}
                            </h4>
                          </div>
                          <div>
                            <small className="text-muted">Adjusted:</small>
                            <h4 className={`text-${getGainLossColor(adjustedCapitalGains.total_adjusted_gain_loss)} mb-0`}>
                              {formatCurrency(adjustedCapitalGains.total_adjusted_gain_loss)}
                            </h4>
                          </div>
                        </>
                      ) : adjustedCapitalGains ? (
                        <h3 className={`text-${getGainLossColor(adjustedCapitalGains.total_adjusted_gain_loss)}`}>
                          {formatCurrency(adjustedCapitalGains.total_adjusted_gain_loss)}
                        </h3>
                      ) : capitalGains ? (
                        <h3 className={`text-${getGainLossColor(capitalGains.total_gain_loss)}`}>
                          {formatCurrency(capitalGains.total_gain_loss)}
                        </h3>
                      ) : null}
                    </Card.Body>
                  </Card>
                </Col>
                <Col md={4}>
                  <Card className="h-100">
                    <Card.Body className="text-center">
                      <h5 className="card-title">Short Term Gain/Loss</h5>
                      {viewMode === 'both' && adjustedCapitalGains && capitalGains ? (
                        <>
                          <div className="mb-2">
                            <small className="text-muted">Original:</small>
                            <h4 className={`text-${getGainLossColor(capitalGains.short_term_gain_loss)} mb-0`}>
                              {formatCurrency(capitalGains.short_term_gain_loss)}
                            </h4>
                          </div>
                          <div>
                            <small className="text-muted">Adjusted:</small>
                            <h4 className={`text-${getGainLossColor(adjustedCapitalGains.short_term_adjusted)} mb-0`}>
                              {formatCurrency(adjustedCapitalGains.short_term_adjusted)}
                            </h4>
                          </div>
                        </>
                      ) : adjustedCapitalGains ? (
                        <h3 className={`text-${getGainLossColor(adjustedCapitalGains.short_term_adjusted)}`}>
                          {formatCurrency(adjustedCapitalGains.short_term_adjusted)}
                        </h3>
                      ) : capitalGains ? (
                        <h3 className={`text-${getGainLossColor(capitalGains.short_term_gain_loss)}`}>
                          {formatCurrency(capitalGains.short_term_gain_loss)}
                        </h3>
                      ) : null}
                      <small className="text-muted">Holdings &lt;= 1 year</small>
                    </Card.Body>
                  </Card>
                </Col>
                <Col md={4}>
                  <Card className="h-100">
                    <Card.Body className="text-center">
                      <h5 className="card-title">Long Term Gain/Loss</h5>
                      {viewMode === 'both' && adjustedCapitalGains && capitalGains ? (
                        <>
                          <div className="mb-2">
                            <small className="text-muted">Original:</small>
                            <h4 className={`text-${getGainLossColor(capitalGains.long_term_gain_loss)} mb-0`}>
                              {formatCurrency(capitalGains.long_term_gain_loss)}
                            </h4>
                          </div>
                          <div>
                            <small className="text-muted">Adjusted:</small>
                            <h4 className={`text-${getGainLossColor(adjustedCapitalGains.long_term_adjusted)} mb-0`}>
                              {formatCurrency(adjustedCapitalGains.long_term_adjusted)}
                            </h4>
                          </div>
                        </>
                      ) : adjustedCapitalGains ? (
                        <h3 className={`text-${getGainLossColor(adjustedCapitalGains.long_term_adjusted)}`}>
                          {formatCurrency(adjustedCapitalGains.long_term_adjusted)}
                        </h3>
                      ) : capitalGains ? (
                        <h3 className={`text-${getGainLossColor(capitalGains.long_term_gain_loss)}`}>
                          {formatCurrency(capitalGains.long_term_gain_loss)}
                        </h3>
                      ) : null}
                      <small className="text-muted">Holdings &gt; 1 year</small>
                    </Card.Body>
                  </Card>
                </Col>
              </Row>

              {/* Adjusted Data Notice */}
              {(viewMode === 'adjusted' || viewMode === 'both') && !adjustedCapitalGains && (
                <Alert variant="info" className="mb-4">
                  <strong>Note:</strong> Adjusted capital gains data is not available.
                  This may be because the lot migration has not been run yet.
                  Contact your administrator to run the lot migration.
                </Alert>
              )}

              {/* Securities Breakdown */}
              <Card>
                <Card.Header>
                  <h5 className="mb-0">Securities Breakdown - {adjustedCapitalGains?.financial_year || capitalGains?.financial_year || ''}</h5>
                </Card.Header>
                <Card.Body>
                  {(() => {
                    // Use adjusted securities when available, otherwise use original
                    const securitiesToShow = adjustedCapitalGains?.securities || capitalGains?.securities;

                    if (!securitiesToShow || securitiesToShow.length === 0) {
                      return (
                        <Alert variant="info">
                          No realized gains/losses for the selected financial year.
                        </Alert>
                      );
                    }

                    return (
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
                        {securitiesToShow.map((securityData, index) => {
                          // Handle both original and adjusted API response formats
                          // Both APIs return security info in securityData.security
                          const securityInfo = securityData.security;
                          const securityName = securityInfo?.security_name || 'Unknown';
                          const securitySymbol = securityInfo?.security_ticker;
                          const isin = securityInfo?.security_ISIN;
                          // Check if this data is from adjusted API (has adjusted fields)
                          const hasAdjustedFields = securityData.total_adjusted_gain_loss !== undefined;
                          const totalGainLoss = hasAdjustedFields ? securityData.total_adjusted_gain_loss : securityData.total_gain_loss;
                          const shortTermGainLoss = hasAdjustedFields ? securityData.short_term_adjusted : securityData.short_term_gain_loss;
                          const longTermGainLoss = hasAdjustedFields ? securityData.long_term_adjusted : securityData.long_term_gain_loss;

                          return (
                          <React.Fragment key={index}>
                            <tr>
                              <td>
                                <strong>{securityName}</strong>
                                {securitySymbol && (
                                  <div className="text-muted small">
                                    {securitySymbol}
                                  </div>
                                )}
                              </td>
                              <td>
                                <small className="text-muted">
                                  {isin || 'N/A'}
                                </small>
                              </td>
                              <td className="text-end">
                                <Badge bg={getGainLossColor(totalGainLoss)}>
                                  {formatCurrency(totalGainLoss)}
                                </Badge>
                              </td>
                              <td className="text-end">
                                <span className={`text-${getGainLossColor(shortTermGainLoss)}`}>
                                  {formatCurrency(shortTermGainLoss)}
                                </span>
                              </td>
                              <td className="text-end">
                                <span className={`text-${getGainLossColor(longTermGainLoss)}`}>
                                  {formatCurrency(longTermGainLoss)}
                                </span>
                              </td>
                              <td className="text-center">
                                <Button
                                  variant="outline-primary"
                                  size="sm"
                                  onClick={() => toggleSecurityDetails(securityName)}
                                >
                                  {expandedSecurities[securityName] ? 'Hide' : 'Show'} Details
                                </Button>
                              </td>
                            </tr>
                            
                            {/* Details Row */}
                            <tr>
                              <td colSpan="6" className="p-0">
                                <Collapse in={expandedSecurities[securityName]}>
                                  <div className="p-3 bg-light">
                                    <h6>Transaction Details for {securityName}</h6>
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
                                        {(securityData.details || []).map((detail, detailIndex) => {
                                          // Handle both original and adjusted API response formats
                                          const buyDate = detail.buy_transaction?.transaction_date || detail.purchase_date;
                                          const sellDate = detail.sell_transaction?.transaction_date || detail.sell_date;
                                          const buyPrice = detail.buy_price_per_unit || detail.original_cost_per_unit || detail.adjusted_cost_per_unit;
                                          const sellPrice = detail.sell_price_per_unit || detail.sale_price_per_unit;
                                          const gainLoss = detail.gain_loss || detail.adjusted_gain_loss || detail.original_gain_loss;
                                          const gainLossPercent = detail.gain_loss_percentage || (buyPrice > 0 ? ((sellPrice - buyPrice) / buyPrice) * 100 : 0);

                                          return (
                                          <tr key={detailIndex}>
                                            <td>{formatDate(buyDate)}</td>
                                            <td>{formatDate(sellDate)}</td>
                                            <td className="text-end">{detail.quantity_sold}</td>
                                            <td className="text-end">{formatCurrency(buyPrice)}</td>
                                            <td className="text-end">{formatCurrency(sellPrice)}</td>
                                            <td className="text-end">
                                              <span className={`text-${getGainLossColor(gainLoss)}`}>
                                                {formatCurrency(gainLoss)}
                                              </span>
                                            </td>
                                            <td className="text-end">
                                              <span className={`text-${getGainLossColor(gainLossPercent)}`}>
                                                {formatPercentage(gainLossPercent)}
                                              </span>
                                            </td>
                                            <td className="text-center">{detail.holding_period_days}</td>
                                            <td className="text-center">
                                              <Badge bg={detail.is_long_term ? 'info' : 'warning'}>
                                                {detail.is_long_term ? 'Long Term' : 'Short Term'}
                                              </Badge>
                                            </td>
                                          </tr>
                                          );
                                        })}
                                      </tbody>
                                    </Table>
                                  </div>
                                </Collapse>
                              </td>
                            </tr>
                          </React.Fragment>
                          );
                        })}
                      </tbody>
                    </Table>
                    );
                  })()}
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