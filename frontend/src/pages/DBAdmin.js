import React, { useState, useEffect } from 'react';
import { Container, Row, Col, Card, Table, Button, Alert, Spinner, Badge, Pagination, Form } from 'react-bootstrap';
import { useAuth } from '../context/AuthContext';
import { apiService } from '../services/apiService';

const DBAdmin = () => {
  const { user, isAdmin } = useAuth();
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Table viewer state
  const [selectedTable, setSelectedTable] = useState(null);
  const [tableData, setTableData] = useState(null);
  const [tableLoading, setTableLoading] = useState(false);
  const [currentPage, setCurrentPage] = useState(0);
  const [pageSize, setPageSize] = useState(25);

  useEffect(() => {
    if (isAdmin && user?.email) {
      fetchStats();
    }
  }, [isAdmin, user]);

  const fetchStats = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await apiService.getDBStats(user.email);
      setStats(response);
    } catch (err) {
      console.error('Error fetching DB stats:', err);
      setError('Failed to fetch database statistics');
    } finally {
      setLoading(false);
    }
  };

  const fetchTableData = async (tableName, page = 0) => {
    try {
      setTableLoading(true);
      const response = await apiService.getTableData(tableName, user.email, page * pageSize, pageSize);
      setTableData(response);
      setCurrentPage(page);
    } catch (err) {
      console.error('Error fetching table data:', err);
      setError(`Failed to fetch data from ${tableName}`);
    } finally {
      setTableLoading(false);
    }
  };

  const handleTableClick = (tableName) => {
    setSelectedTable(tableName);
    setCurrentPage(0);
    fetchTableData(tableName, 0);
  };

  const handlePageChange = (page) => {
    fetchTableData(selectedTable, page);
  };

  const formatValue = (value, columnName) => {
    if (value === null || value === undefined) {
      return <span className="text-muted">NULL</span>;
    }
    if (typeof value === 'boolean') {
      return value ? <Badge bg="success">true</Badge> : <Badge bg="secondary">false</Badge>;
    }
    if (columnName.includes('price') || columnName.includes('amount') || columnName.includes('cost') || columnName.includes('value')) {
      return typeof value === 'number' ? `₹${value.toLocaleString('en-IN', { minimumFractionDigits: 2 })}` : value;
    }
    if (columnName.includes('date') || columnName.includes('_at')) {
      if (typeof value === 'string' && value.includes('T')) {
        return new Date(value).toLocaleString('en-IN');
      }
    }
    if (typeof value === 'string' && value.length > 50) {
      return value.substring(0, 50) + '...';
    }
    return String(value);
  };

  if (!isAdmin) {
    return (
      <Container fluid className="p-4">
        <Alert variant="danger" className="text-center">
          <Alert.Heading>Access Denied</Alert.Heading>
          <p>You do not have admin privileges to access the DB Browser.</p>
        </Alert>
      </Container>
    );
  }

  if (loading) {
    return (
      <Container fluid className="p-4 text-center">
        <Spinner animation="border" role="status">
          <span className="visually-hidden">Loading...</span>
        </Spinner>
        <p className="mt-2">Loading database statistics...</p>
      </Container>
    );
  }

  if (error) {
    return (
      <Container fluid className="p-4">
        <Alert variant="danger">{error}</Alert>
        <Button onClick={fetchStats}>Retry</Button>
      </Container>
    );
  }

  const totalPages = tableData ? Math.ceil(tableData.total_count / pageSize) : 0;

  return (
    <Container fluid className="p-4">
      <Row className="mb-4">
        <Col>
          <h2>Database Browser</h2>
          <p className="text-muted">View and inspect all database tables (Admin only)</p>
        </Col>
      </Row>

      {/* Stats Overview */}
      <Row className="mb-4">
        <Col>
          <Card>
            <Card.Header>
              <h5 className="mb-0">Database Overview</h5>
            </Card.Header>
            <Card.Body>
              <Row>
                {stats && Object.entries(stats.stats).map(([key, value]) => (
                  <Col key={key} xs={6} md={3} lg={2} className="mb-3">
                    <Card
                      className={`h-100 ${selectedTable === value.table_name ? 'border-primary' : ''}`}
                      style={{ cursor: 'pointer' }}
                      onClick={() => handleTableClick(value.table_name)}
                    >
                      <Card.Body className="text-center py-3">
                        <h3 className="mb-1">{value.count.toLocaleString()}</h3>
                        <small className="text-muted text-uppercase">{key.replace(/_/g, ' ')}</small>
                      </Card.Body>
                    </Card>
                  </Col>
                ))}
              </Row>
              <div className="text-center mt-3">
                <Badge bg="info" className="fs-6">
                  Total Records: {stats?.total_records?.toLocaleString() || 0}
                </Badge>
              </div>
            </Card.Body>
          </Card>
        </Col>
      </Row>

      {/* Table Viewer */}
      {selectedTable && (
        <Row>
          <Col>
            <Card>
              <Card.Header className="d-flex justify-content-between align-items-center">
                <div>
                  <h5 className="mb-0">
                    Table: <code>{selectedTable}</code>
                    {tableData && (
                      <Badge bg="secondary" className="ms-2">
                        {tableData.total_count} rows
                      </Badge>
                    )}
                  </h5>
                </div>
                <div className="d-flex align-items-center gap-2">
                  <Form.Select
                    size="sm"
                    value={pageSize}
                    onChange={(e) => {
                      setPageSize(Number(e.target.value));
                      fetchTableData(selectedTable, 0);
                    }}
                    style={{ width: 'auto' }}
                  >
                    <option value={10}>10 per page</option>
                    <option value={25}>25 per page</option>
                    <option value={50}>50 per page</option>
                    <option value={100}>100 per page</option>
                  </Form.Select>
                  <Button
                    variant="outline-secondary"
                    size="sm"
                    onClick={() => fetchTableData(selectedTable, currentPage)}
                  >
                    Refresh
                  </Button>
                  <Button
                    variant="outline-danger"
                    size="sm"
                    onClick={() => {
                      setSelectedTable(null);
                      setTableData(null);
                    }}
                  >
                    Close
                  </Button>
                </div>
              </Card.Header>
              <Card.Body className="p-0">
                {tableLoading ? (
                  <div className="text-center py-4">
                    <Spinner animation="border" size="sm" />
                    <span className="ms-2">Loading data...</span>
                  </div>
                ) : tableData && tableData.data.length > 0 ? (
                  <>
                    <div className="table-responsive" style={{ maxHeight: '60vh', overflow: 'auto' }}>
                      <Table striped bordered hover size="sm" className="mb-0">
                        <thead className="table-dark" style={{ position: 'sticky', top: 0, zIndex: 1 }}>
                          <tr>
                            {tableData.columns.map(col => (
                              <th key={col} style={{ whiteSpace: 'nowrap' }}>{col}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {tableData.data.map((row, idx) => (
                            <tr key={idx}>
                              {tableData.columns.map(col => (
                                <td key={col} style={{ maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                  {formatValue(row[col], col)}
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </Table>
                    </div>

                    {/* Pagination */}
                    <div className="d-flex justify-content-between align-items-center p-3 border-top">
                      <small className="text-muted">
                        Showing {currentPage * pageSize + 1} - {Math.min((currentPage + 1) * pageSize, tableData.total_count)} of {tableData.total_count}
                      </small>
                      {totalPages > 1 && (
                        <Pagination size="sm" className="mb-0">
                          <Pagination.First
                            onClick={() => handlePageChange(0)}
                            disabled={currentPage === 0}
                          />
                          <Pagination.Prev
                            onClick={() => handlePageChange(currentPage - 1)}
                            disabled={currentPage === 0}
                          />
                          {[...Array(Math.min(5, totalPages))].map((_, i) => {
                            let pageNum;
                            if (totalPages <= 5) {
                              pageNum = i;
                            } else if (currentPage < 3) {
                              pageNum = i;
                            } else if (currentPage > totalPages - 4) {
                              pageNum = totalPages - 5 + i;
                            } else {
                              pageNum = currentPage - 2 + i;
                            }
                            return (
                              <Pagination.Item
                                key={pageNum}
                                active={pageNum === currentPage}
                                onClick={() => handlePageChange(pageNum)}
                              >
                                {pageNum + 1}
                              </Pagination.Item>
                            );
                          })}
                          <Pagination.Next
                            onClick={() => handlePageChange(currentPage + 1)}
                            disabled={currentPage >= totalPages - 1}
                          />
                          <Pagination.Last
                            onClick={() => handlePageChange(totalPages - 1)}
                            disabled={currentPage >= totalPages - 1}
                          />
                        </Pagination>
                      )}
                    </div>
                  </>
                ) : (
                  <Alert variant="info" className="m-3">No data in this table</Alert>
                )}
              </Card.Body>
            </Card>
          </Col>
        </Row>
      )}

      {!selectedTable && (
        <Row>
          <Col>
            <Alert variant="info">
              Click on any table card above to view its contents
            </Alert>
          </Col>
        </Row>
      )}
    </Container>
  );
};

export default DBAdmin;
