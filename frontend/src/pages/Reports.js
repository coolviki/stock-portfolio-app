import React, { useState, useEffect, useCallback } from 'react';
import { Container, Row, Col, Card, Form, Table, Button, Alert, Spinner, ToggleButtonGroup, ToggleButton } from 'react-bootstrap';
import { useAuth } from '../context/AuthContext';
import { apiService } from '../services/apiService';
import { toast } from 'react-toastify';

const Reports = () => {
  const { user } = useAuth();
  const [loading, setLoading] = useState(false);
  const [reportType, setReportType] = useState('holdings'); // 'holdings' or 'statement'
  const [financialYears, setFinancialYears] = useState([]);

  // Holdings As-Of-Date state
  const [asOfDate, setAsOfDate] = useState(new Date().toISOString().split('T')[0]);
  const [holdingsData, setHoldingsData] = useState(null);

  // Transaction Statement state
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [selectedFY, setSelectedFY] = useState('');
  const [statementData, setStatementData] = useState(null);

  // Common options
  const [includeZeroHoldings, setIncludeZeroHoldings] = useState(false);

  const loadFinancialYears = useCallback(async () => {
    try {
      const response = await apiService.getReportFinancialYears(user?.id);
      setFinancialYears(response.financial_years || []);

      // Set default date range to current FY
      if (response.current_financial_year) {
        const fy = response.current_financial_year;
        setStartDate(`${fy}-04-01`);
        setEndDate(`${fy + 1}-03-31`);
        setSelectedFY(fy.toString());
      }
    } catch (error) {
      console.error('Error loading financial years:', error);
    }
  }, [user?.id]);

  useEffect(() => {
    loadFinancialYears();
  }, [loadFinancialYears]);

  const handleFYChange = (fy) => {
    setSelectedFY(fy);
    if (fy) {
      const year = parseInt(fy);
      setStartDate(`${year}-04-01`);
      setEndDate(`${year + 1}-03-31`);
    }
  };

  const generateHoldingsReport = async () => {
    if (!asOfDate) {
      toast.error('Please select a date');
      return;
    }

    try {
      setLoading(true);
      setHoldingsData(null);
      const response = await apiService.getHoldingsAsOfDate(
        asOfDate,
        user?.id,
        includeZeroHoldings
      );
      setHoldingsData(response);
    } catch (error) {
      console.error('Error generating holdings report:', error);
      toast.error('Failed to generate holdings report');
    } finally {
      setLoading(false);
    }
  };

  const generateStatementReport = async () => {
    if (!startDate || !endDate) {
      toast.error('Please select start and end dates');
      return;
    }

    try {
      setLoading(true);
      setStatementData(null);
      const response = await apiService.getTransactionStatement(
        startDate,
        endDate,
        user?.id,
        includeZeroHoldings
      );
      setStatementData(response);
    } catch (error) {
      console.error('Error generating transaction statement:', error);
      toast.error('Failed to generate transaction statement');
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      minimumFractionDigits: 2
    }).format(amount || 0);
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('en-IN');
  };

  const formatQuantity = (qty) => {
    return qty % 1 === 0 ? qty.toString() : qty.toFixed(4);
  };

  const exportToCSV = (data, filename) => {
    if (!data || data.length === 0) {
      toast.error('No data to export');
      return;
    }

    // Get headers from first row
    const headers = Object.keys(data[0]);

    // Build CSV content
    const csvContent = [
      headers.join(','),
      ...data.map(row =>
        headers.map(header => {
          const value = row[header];
          // Handle values that might contain commas or quotes
          if (typeof value === 'string' && (value.includes(',') || value.includes('"'))) {
            return `"${value.replace(/"/g, '""')}"`;
          }
          return value ?? '';
        }).join(',')
      )
    ].join('\n');

    // Create and download file
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `${filename}_${new Date().toISOString().split('T')[0]}.csv`;
    link.click();
    URL.revokeObjectURL(link.href);
    toast.success('CSV exported successfully');
  };

  const exportHoldingsToCSV = () => {
    if (!holdingsData?.holdings) return;

    const csvData = holdingsData.holdings.map(h => ({
      'Security Name': h.security_name,
      'Ticker': h.security_ticker,
      'ISIN': h.isin,
      'Quantity': h.quantity,
      'Avg Cost': h.avg_cost,
      'Total Invested': h.total_invested,
      '% of Portfolio': h.portfolio_percentage
    }));

    exportToCSV(csvData, `holdings_as_of_${asOfDate}`);
  };

  const exportStatementToCSV = () => {
    if (!statementData?.items) return;

    const csvData = statementData.items.map(item => {
      if (item.type === 'TRANSACTION') {
        return {
          'Date': item.date,
          'Type': item.transaction_type,
          'Security Name': item.security_name,
          'Ticker': item.security_ticker,
          'ISIN': item.isin,
          'Quantity': item.quantity,
          'Price': item.price_per_unit,
          'Amount': item.total_amount,
          'Exchange': item.exchange || '',
          'Running Balance': item.running_balance
        };
      } else {
        return {
          'Date': item.date,
          'Type': `EVENT: ${item.event_type}`,
          'Security Name': item.security_name,
          'Ticker': item.security_ticker,
          'ISIN': item.isin,
          'Quantity': '',
          'Price': '',
          'Amount': '',
          'Exchange': '',
          'Running Balance': item.description
        };
      }
    });

    exportToCSV(csvData, `statement_${startDate}_to_${endDate}`);
  };

  return (
    <Container fluid className="mt-4">
      <Row>
        <Col>
          <h2 className="mb-4">Reports</h2>

          {/* Report Type Selection */}
          <Card className="mb-4">
            <Card.Body>
              <Row className="align-items-center">
                <Col md={6}>
                  <Form.Group>
                    <Form.Label>Report Type:</Form.Label>
                    <div>
                      <ToggleButtonGroup
                        type="radio"
                        name="reportType"
                        value={reportType}
                        onChange={(val) => {
                          setReportType(val);
                          setHoldingsData(null);
                          setStatementData(null);
                        }}
                      >
                        <ToggleButton id="report-holdings" value="holdings" variant="outline-primary">
                          Holdings As-Of-Date
                        </ToggleButton>
                        <ToggleButton id="report-statement" value="statement" variant="outline-primary">
                          Transaction Statement
                        </ToggleButton>
                      </ToggleButtonGroup>
                    </div>
                  </Form.Group>
                </Col>
                <Col md={6}>
                  <Form.Group>
                    <Form.Check
                      type="checkbox"
                      id="includeZeroHoldings"
                      label="Include securities with zero current holdings"
                      checked={includeZeroHoldings}
                      onChange={(e) => setIncludeZeroHoldings(e.target.checked)}
                    />
                    <Form.Text className="text-muted">
                      Show all securities including those fully sold
                    </Form.Text>
                  </Form.Group>
                </Col>
              </Row>
            </Card.Body>
          </Card>

          {/* Holdings As-Of-Date Form */}
          {reportType === 'holdings' && (
            <Card className="mb-4">
              <Card.Header>
                <h5 className="mb-0">Holdings As-Of-Date Report</h5>
              </Card.Header>
              <Card.Body>
                <Row className="align-items-end">
                  <Col md={4}>
                    <Form.Group>
                      <Form.Label>As of Date:</Form.Label>
                      <Form.Control
                        type="date"
                        value={asOfDate}
                        onChange={(e) => setAsOfDate(e.target.value)}
                        max={new Date().toISOString().split('T')[0]}
                      />
                    </Form.Group>
                  </Col>
                  <Col md={4}>
                    <Button
                      variant="primary"
                      onClick={generateHoldingsReport}
                      disabled={loading}
                    >
                      {loading ? (
                        <>
                          <Spinner animation="border" size="sm" className="me-2" />
                          Generating...
                        </>
                      ) : (
                        'Generate Report'
                      )}
                    </Button>
                  </Col>
                </Row>
              </Card.Body>
            </Card>
          )}

          {/* Transaction Statement Form */}
          {reportType === 'statement' && (
            <Card className="mb-4">
              <Card.Header>
                <h5 className="mb-0">Transaction Statement</h5>
              </Card.Header>
              <Card.Body>
                <Row className="align-items-end mb-3">
                  <Col md={3}>
                    <Form.Group>
                      <Form.Label>Quick Select FY:</Form.Label>
                      <Form.Select
                        value={selectedFY}
                        onChange={(e) => handleFYChange(e.target.value)}
                      >
                        <option value="">Custom Range</option>
                        {financialYears.map(fy => (
                          <option key={fy} value={fy}>
                            FY {fy}-{(fy + 1).toString().slice(-2)}
                          </option>
                        ))}
                      </Form.Select>
                    </Form.Group>
                  </Col>
                  <Col md={3}>
                    <Form.Group>
                      <Form.Label>Start Date:</Form.Label>
                      <Form.Control
                        type="date"
                        value={startDate}
                        onChange={(e) => {
                          setStartDate(e.target.value);
                          setSelectedFY('');
                        }}
                      />
                    </Form.Group>
                  </Col>
                  <Col md={3}>
                    <Form.Group>
                      <Form.Label>End Date:</Form.Label>
                      <Form.Control
                        type="date"
                        value={endDate}
                        onChange={(e) => {
                          setEndDate(e.target.value);
                          setSelectedFY('');
                        }}
                        max={new Date().toISOString().split('T')[0]}
                      />
                    </Form.Group>
                  </Col>
                  <Col md={3}>
                    <Button
                      variant="primary"
                      onClick={generateStatementReport}
                      disabled={loading}
                    >
                      {loading ? (
                        <>
                          <Spinner animation="border" size="sm" className="me-2" />
                          Generating...
                        </>
                      ) : (
                        'Generate Report'
                      )}
                    </Button>
                  </Col>
                </Row>
              </Card.Body>
            </Card>
          )}

          {/* Holdings Report Results */}
          {holdingsData && (
            <Card>
              <Card.Header className="d-flex justify-content-between align-items-center">
                <h5 className="mb-0">
                  Holdings as of {formatDate(holdingsData.as_of_date)}
                </h5>
                <Button
                  variant="outline-success"
                  size="sm"
                  onClick={exportHoldingsToCSV}
                >
                  Export CSV
                </Button>
              </Card.Header>
              <Card.Body>
                {/* Summary Row */}
                <Row className="mb-4">
                  <Col md={4}>
                    <Card className="bg-light">
                      <Card.Body className="text-center">
                        <h6 className="text-muted">Total Securities</h6>
                        <h4>{holdingsData.total_securities}</h4>
                      </Card.Body>
                    </Card>
                  </Col>
                  <Col md={4}>
                    <Card className="bg-light">
                      <Card.Body className="text-center">
                        <h6 className="text-muted">Total Invested</h6>
                        <h4>{formatCurrency(holdingsData.total_invested)}</h4>
                      </Card.Body>
                    </Card>
                  </Col>
                </Row>

                {holdingsData.holdings.length === 0 ? (
                  <Alert variant="info">
                    No holdings found for the selected date.
                  </Alert>
                ) : (
                  <Table responsive hover>
                    <thead>
                      <tr>
                        <th>Security</th>
                        <th>ISIN</th>
                        <th className="text-end">Quantity</th>
                        <th className="text-end">Avg Cost</th>
                        <th className="text-end">Total Invested</th>
                        <th className="text-end">% of Portfolio</th>
                      </tr>
                    </thead>
                    <tbody>
                      {holdingsData.holdings.map((holding, index) => (
                        <tr key={index}>
                          <td>
                            <strong>{holding.security_name}</strong>
                            {holding.security_ticker && (
                              <div className="text-muted small">{holding.security_ticker}</div>
                            )}
                          </td>
                          <td className="small text-muted">{holding.isin || 'N/A'}</td>
                          <td className="text-end">{formatQuantity(holding.quantity)}</td>
                          <td className="text-end">{formatCurrency(holding.avg_cost)}</td>
                          <td className="text-end">{formatCurrency(holding.total_invested)}</td>
                          <td className="text-end">{holding.portfolio_percentage}%</td>
                        </tr>
                      ))}
                    </tbody>
                    <tfoot>
                      <tr className="table-secondary fw-bold">
                        <td colSpan="4">Total</td>
                        <td className="text-end">{formatCurrency(holdingsData.total_invested)}</td>
                        <td className="text-end">100%</td>
                      </tr>
                    </tfoot>
                  </Table>
                )}
              </Card.Body>
            </Card>
          )}

          {/* Transaction Statement Results */}
          {statementData && (
            <Card>
              <Card.Header className="d-flex justify-content-between align-items-center">
                <h5 className="mb-0">
                  Transaction Statement: {formatDate(statementData.start_date)} to {formatDate(statementData.end_date)}
                </h5>
                <Button
                  variant="outline-success"
                  size="sm"
                  onClick={exportStatementToCSV}
                >
                  Export CSV
                </Button>
              </Card.Header>
              <Card.Body>
                {/* Summary Row */}
                <Row className="mb-4">
                  <Col md={2}>
                    <Card className="bg-light">
                      <Card.Body className="text-center py-2">
                        <h6 className="text-muted small mb-1">Transactions</h6>
                        <h5 className="mb-0">{statementData.total_transactions}</h5>
                      </Card.Body>
                    </Card>
                  </Col>
                  <Col md={2}>
                    <Card className="bg-light">
                      <Card.Body className="text-center py-2">
                        <h6 className="text-muted small mb-1">Corp Events</h6>
                        <h5 className="mb-0">{statementData.total_corporate_events}</h5>
                      </Card.Body>
                    </Card>
                  </Col>
                  <Col md={3}>
                    <Card className="bg-success text-white">
                      <Card.Body className="text-center py-2">
                        <h6 className="small mb-1">Total Bought</h6>
                        <h5 className="mb-0">{formatCurrency(statementData.total_bought)}</h5>
                      </Card.Body>
                    </Card>
                  </Col>
                  <Col md={3}>
                    <Card className="bg-danger text-white">
                      <Card.Body className="text-center py-2">
                        <h6 className="small mb-1">Total Sold</h6>
                        <h5 className="mb-0">{formatCurrency(statementData.total_sold)}</h5>
                      </Card.Body>
                    </Card>
                  </Col>
                  <Col md={2}>
                    <Card className={statementData.net_investment >= 0 ? 'bg-info text-white' : 'bg-warning'}>
                      <Card.Body className="text-center py-2">
                        <h6 className="small mb-1">Net Investment</h6>
                        <h5 className="mb-0">{formatCurrency(statementData.net_investment)}</h5>
                      </Card.Body>
                    </Card>
                  </Col>
                </Row>

                {statementData.items.length === 0 ? (
                  <Alert variant="info">
                    No transactions or corporate events found for the selected period.
                  </Alert>
                ) : (
                  <Table responsive hover size="sm">
                    <thead>
                      <tr>
                        <th>Date</th>
                        <th>Type</th>
                        <th>Security</th>
                        <th className="text-end">Quantity</th>
                        <th className="text-end">Price</th>
                        <th className="text-end">Amount</th>
                        <th className="text-end">Running Balance</th>
                      </tr>
                    </thead>
                    <tbody>
                      {statementData.items.map((item, index) => (
                        <tr key={index} className={item.type === 'CORPORATE_EVENT' ? 'table-warning' : ''}>
                          <td>{formatDate(item.date)}</td>
                          <td>
                            {item.type === 'TRANSACTION' ? (
                              <span className={`badge bg-${item.transaction_type === 'BUY' ? 'success' : 'danger'}`}>
                                {item.transaction_type}
                              </span>
                            ) : (
                              <span className="badge bg-warning text-dark">
                                {item.event_type}
                              </span>
                            )}
                          </td>
                          <td>
                            <strong>{item.security_name}</strong>
                            {item.security_ticker && (
                              <span className="text-muted ms-1 small">({item.security_ticker})</span>
                            )}
                          </td>
                          <td className="text-end">
                            {item.type === 'TRANSACTION' ? formatQuantity(item.quantity) : '-'}
                          </td>
                          <td className="text-end">
                            {item.type === 'TRANSACTION' ? formatCurrency(item.price_per_unit) : '-'}
                          </td>
                          <td className="text-end">
                            {item.type === 'TRANSACTION' ? formatCurrency(item.total_amount) : '-'}
                          </td>
                          <td className="text-end">
                            {item.type === 'TRANSACTION' ? (
                              formatQuantity(item.running_balance)
                            ) : (
                              <small className="text-muted">{item.description}</small>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </Table>
                )}
              </Card.Body>
            </Card>
          )}
        </Col>
      </Row>
    </Container>
  );
};

export default Reports;
