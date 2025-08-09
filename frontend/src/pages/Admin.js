import React, { useState } from 'react';
import { Container, Row, Col, Card, Button, Form, Alert, Spinner } from 'react-bootstrap';
import { toast } from 'react-toastify';
import { apiService } from '../services/apiService';
import { fetchAdminExport, fetchAdminImport } from '../utils/apiUtils';

const Admin = () => {
  const [exportLoading, setExportLoading] = useState(false);
  const [importLoading, setImportLoading] = useState(false);
  const [importFile, setImportFile] = useState(null);
  const [replaceExisting, setReplaceExisting] = useState(false);
  const [importResult, setImportResult] = useState(null);

  const handleExport = async () => {
    setExportLoading(true);
    try {
      const response = await fetchAdminExport();
      
      if (!response.ok) {
        throw new Error('Export failed');
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.style.display = 'none';
      a.href = url;
      
      // Get filename from response headers or generate one
      const contentDisposition = response.headers.get('content-disposition');
      let filename = 'stock_portfolio_export.json';
      if (contentDisposition) {
        const matches = contentDisposition.match(/filename="(.+)"/);
        if (matches) {
          filename = matches[1];
        }
      }
      
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      
      toast.success('Database exported successfully!');
    } catch (error) {
      console.error('Export error:', error);
      toast.error('Failed to export database');
    } finally {
      setExportLoading(false);
    }
  };

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    setImportFile(file);
    setImportResult(null);
  };

  const handleImport = async () => {
    if (!importFile) {
      toast.error('Please select a file to import');
      return;
    }

    setImportLoading(true);
    setImportResult(null);
    
    try {
      const formData = new FormData();
      formData.append('file', importFile);
      formData.append('replace_existing', replaceExisting.toString());

      const response = await fetchAdminImport(formData);

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Import failed');
      }

      const result = await response.json();
      setImportResult(result);
      
      if (result.errors && result.errors.length > 0) {
        toast.warning(`Import completed with ${result.errors.length} errors`);
      } else {
        toast.success('Database imported successfully!');
      }
      
      // Clear the file input
      setImportFile(null);
      document.getElementById('importFile').value = '';
      
    } catch (error) {
      console.error('Import error:', error);
      toast.error(`Import failed: ${error.message}`);
    } finally {
      setImportLoading(false);
    }
  };

  return (
    <Container fluid className="p-4">
      <Row>
        <Col>
          <h2 className="mb-4">Admin Panel</h2>
          <p className="text-muted mb-4">
            Manage database operations including export and import functionality.
          </p>
        </Col>
      </Row>

      <Row>
        <Col md={6} className="mb-4">
          <Card>
            <Card.Header>
              <h5 className="mb-0">📤 Export Database</h5>
            </Card.Header>
            <Card.Body>
              <p className="text-muted">
                Export all users and transactions to a JSON file for backup or migration purposes.
              </p>
              <Button 
                variant="primary" 
                onClick={handleExport}
                disabled={exportLoading}
                className="d-flex align-items-center"
              >
                {exportLoading && <Spinner size="sm" className="me-2" />}
                {exportLoading ? 'Exporting...' : 'Export Database'}
              </Button>
            </Card.Body>
          </Card>
        </Col>

        <Col md={6} className="mb-4">
          <Card>
            <Card.Header>
              <h5 className="mb-0">📥 Import Database</h5>
            </Card.Header>
            <Card.Body>
              <p className="text-muted">
                Import users and transactions from a previously exported JSON file.
              </p>
              
              <Form>
                <Form.Group className="mb-3">
                  <Form.Label>Select JSON File</Form.Label>
                  <Form.Control
                    type="file"
                    id="importFile"
                    accept=".json"
                    onChange={handleFileChange}
                  />
                </Form.Group>
                
                <Form.Group className="mb-3">
                  <Form.Check
                    type="checkbox"
                    id="replaceExisting"
                    label="Replace existing data (⚠️ This will delete all current data)"
                    checked={replaceExisting}
                    onChange={(e) => setReplaceExisting(e.target.checked)}
                  />
                </Form.Group>
                
                <Button 
                  variant="success" 
                  onClick={handleImport}
                  disabled={importLoading || !importFile}
                  className="d-flex align-items-center"
                >
                  {importLoading && <Spinner size="sm" className="me-2" />}
                  {importLoading ? 'Importing...' : 'Import Database'}
                </Button>
              </Form>
            </Card.Body>
          </Card>
        </Col>
      </Row>

      {importResult && (
        <Row>
          <Col>
            <Card className="mt-4">
              <Card.Header>
                <h5 className="mb-0">Import Results</h5>
              </Card.Header>
              <Card.Body>
                <Row>
                  <Col md={3}>
                    <div className="text-center">
                      <h6 className="text-success">Users Imported</h6>
                      <h4>{importResult.users_imported}</h4>
                    </div>
                  </Col>
                  <Col md={3}>
                    <div className="text-center">
                      <h6 className="text-success">Transactions Imported</h6>
                      <h4>{importResult.transactions_imported}</h4>
                    </div>
                  </Col>
                  <Col md={3}>
                    <div className="text-center">
                      <h6 className="text-warning">Users Skipped</h6>
                      <h4>{importResult.users_skipped}</h4>
                    </div>
                  </Col>
                  <Col md={3}>
                    <div className="text-center">
                      <h6 className="text-warning">Transactions Skipped</h6>
                      <h4>{importResult.transactions_skipped}</h4>
                    </div>
                  </Col>
                </Row>
                
                {importResult.errors && importResult.errors.length > 0 && (
                  <Alert variant="danger" className="mt-3">
                    <h6>Errors encountered during import:</h6>
                    <ul className="mb-0">
                      {importResult.errors.map((error, index) => (
                        <li key={index}>{error}</li>
                      ))}
                    </ul>
                  </Alert>
                )}
              </Card.Body>
            </Card>
          </Col>
        </Row>
      )}

      <Row className="mt-4">
        <Col>
          <Card>
            <Card.Header>
              <h5 className="mb-0">ℹ️ Important Notes</h5>
            </Card.Header>
            <Card.Body>
              <ul className="mb-0">
                <li><strong>Export:</strong> Creates a timestamped JSON file containing all users and transactions.</li>
                <li><strong>Import (Merge):</strong> Adds new data while preserving existing data. Duplicate usernames are skipped.</li>
                <li><strong>Import (Replace):</strong> Completely replaces all existing data with imported data.</li>
                <li><strong>File Format:</strong> Only JSON files exported from this system are supported.</li>
                <li><strong>Backup:</strong> Always export your current data before performing a replace import.</li>
              </ul>
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </Container>
  );
};

export default Admin;