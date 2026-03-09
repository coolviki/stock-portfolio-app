import React, { useState } from 'react';
import { Container, Row, Col, Card, Button, Form, Alert, Spinner, Modal } from 'react-bootstrap';
import { toast } from 'react-toastify';
import { fetchAdminExport, fetchAdminImport, clearDatabase } from '../utils/apiUtils';
import { useAuth } from '../context/AuthContext';

const Admin = () => {
  const { user, isAdmin } = useAuth();
  const [exportLoading, setExportLoading] = useState(false);
  const [importLoading, setImportLoading] = useState(false);
  const [importFile, setImportFile] = useState(null);
  const [replaceExisting, setReplaceExisting] = useState(false);
  const [importResult, setImportResult] = useState(null);

  // Clear database state
  const [clearDbLoading, setClearDbLoading] = useState(false);
  const [showWarning1, setShowWarning1] = useState(false);
  const [showWarning2, setShowWarning2] = useState(false);
  const [showWarning3, setShowWarning3] = useState(false);
  const [confirmText, setConfirmText] = useState('');

  const handleExport = async () => {
    if (!user?.email) {
      toast.error('User email is required for admin operations');
      return;
    }

    setExportLoading(true);
    try {
      const response = await fetchAdminExport(user.email);
      
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

    if (!user?.email) {
      toast.error('User email is required for admin operations');
      return;
    }

    setImportLoading(true);
    setImportResult(null);
    
    try {
      const formData = new FormData();
      formData.append('file', importFile);
      formData.append('replace_existing', replaceExisting.toString());
      formData.append('admin_email', user.email);

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

  const handleClearDbStart = () => {
    setShowWarning1(true);
  };

  const handleWarning1Continue = () => {
    setShowWarning1(false);
    setShowWarning2(true);
  };

  const handleWarning2Continue = () => {
    setShowWarning2(false);
    setShowWarning3(true);
    setConfirmText('');
  };

  const handleWarning3Continue = async () => {
    if (confirmText !== 'DELETE-ALL-DATA') {
      toast.error('Confirmation text does not match. Operation cancelled.');
      return;
    }

    if (!user?.email) {
      toast.error('User email is required for admin operations');
      return;
    }

    setClearDbLoading(true);
    try {
      const response = await clearDatabase(user.email, confirmText);

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to clear database');
      }

      const result = await response.json();
      toast.success(`Database cleared! ${result.total_records_deleted} records deleted.`);
      setShowWarning3(false);
      setConfirmText('');
    } catch (error) {
      console.error('Clear database error:', error);
      toast.error(`Failed to clear database: ${error.message}`);
    } finally {
      setClearDbLoading(false);
    }
  };

  const handleCancelClear = () => {
    setShowWarning1(false);
    setShowWarning2(false);
    setShowWarning3(false);
    setConfirmText('');
  };

  if (!isAdmin) {
    return (
      <Container fluid className="p-4">
        <div className="d-flex justify-content-center align-items-center" style={{ height: '400px' }}>
          <Alert variant="danger" className="text-center">
            <Alert.Heading>🔒 Access Denied</Alert.Heading>
            <p>
              You do not have admin privileges to access the Admin panel.
              <br />
              Please contact an administrator if you need access.
            </p>
            <hr />
            <p className="mb-0">
              <strong>Current user:</strong> {user?.email || user?.username || 'Unknown'}
            </p>
          </Alert>
        </div>
      </Container>
    );
  }

  return (
    <Container fluid className="p-4">
      <Row>
        <Col>
          <h2 className="mb-4">⚙️ Admin Panel</h2>
          <p className="text-muted mb-4">
            Manage database operations including export and import functionality.
          </p>
          <Alert variant="success" className="mb-4">
            <strong>Welcome, Admin!</strong> You have full administrative access to manage the system.
            <br />
            <strong>Current admin:</strong> {user?.email || user?.username}
          </Alert>
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

      {/* Danger Zone */}
      <Row className="mt-4">
        <Col>
          <Card border="danger">
            <Card.Header className="bg-danger text-white">
              <h5 className="mb-0">☠️ DANGER ZONE</h5>
            </Card.Header>
            <Card.Body>
              <Alert variant="danger">
                <strong>Warning:</strong> The actions in this section are destructive and cannot be undone.
              </Alert>
              <div className="d-flex justify-content-between align-items-center">
                <div>
                  <h6 className="mb-1">Clear Entire Database</h6>
                  <p className="text-muted mb-0">
                    Permanently delete ALL users, transactions, securities, corporate events, and lots.
                  </p>
                </div>
                <Button
                  variant="danger"
                  onClick={handleClearDbStart}
                  disabled={clearDbLoading}
                >
                  {clearDbLoading && <Spinner size="sm" className="me-2" />}
                  Clear Database
                </Button>
              </div>
            </Card.Body>
          </Card>
        </Col>
      </Row>

      {/* Warning Modal 1 */}
      <Modal show={showWarning1} onHide={handleCancelClear} centered>
        <Modal.Header className="bg-warning">
          <Modal.Title>⚠️ WARNING 1 of 3</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <Alert variant="warning" className="mb-3">
            <h5>Are you sure you want to clear the database?</h5>
          </Alert>
          <p>This action will <strong>permanently delete</strong>:</p>
          <ul>
            <li>All user accounts</li>
            <li>All stock transactions</li>
            <li>All securities</li>
            <li>All corporate events</li>
            <li>All lots and sale allocations</li>
          </ul>
          <p className="text-danger fw-bold">This action cannot be undone!</p>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={handleCancelClear}>
            Cancel
          </Button>
          <Button variant="warning" onClick={handleWarning1Continue}>
            I Understand, Continue
          </Button>
        </Modal.Footer>
      </Modal>

      {/* Warning Modal 2 */}
      <Modal show={showWarning2} onHide={handleCancelClear} centered>
        <Modal.Header className="bg-danger text-white">
          <Modal.Title>🚨 WARNING 2 of 3 - POINT OF NO RETURN</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <Alert variant="danger" className="mb-3">
            <h5>THIS IS YOUR SECOND WARNING!</h5>
          </Alert>
          <div className="text-center mb-3">
            <span style={{ fontSize: '4rem' }}>☠️</span>
          </div>
          <p className="fw-bold">You are about to DESTROY ALL DATA in the system!</p>
          <p>Consider these questions:</p>
          <ul>
            <li>Have you exported a backup of your data?</li>
            <li>Are you absolutely certain you want to delete everything?</li>
            <li>Do you understand that this affects ALL users, not just you?</li>
          </ul>
          <Alert variant="dark">
            <strong>Recommendation:</strong> Go back and export your data first!
          </Alert>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="success" onClick={handleCancelClear}>
            Go Back (Safe Choice)
          </Button>
          <Button variant="danger" onClick={handleWarning2Continue}>
            Proceed Anyway
          </Button>
        </Modal.Footer>
      </Modal>

      {/* Warning Modal 3 - Final Confirmation */}
      <Modal show={showWarning3} onHide={handleCancelClear} centered>
        <Modal.Header className="bg-dark text-white">
          <Modal.Title>💀 FINAL WARNING 3 of 3</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <Alert variant="danger" className="mb-3">
            <h4 className="text-center">LAST CHANCE TO STOP!</h4>
          </Alert>
          <div className="text-center mb-4">
            <span style={{ fontSize: '5rem' }}>💣</span>
          </div>
          <p className="text-center fw-bold fs-5">
            Type <code>DELETE-ALL-DATA</code> to confirm:
          </p>
          <Form.Control
            type="text"
            value={confirmText}
            onChange={(e) => setConfirmText(e.target.value)}
            placeholder="Type DELETE-ALL-DATA"
            className="text-center fs-5 mb-3"
            style={{
              borderColor: confirmText === 'DELETE-ALL-DATA' ? 'red' : undefined,
              borderWidth: confirmText === 'DELETE-ALL-DATA' ? '3px' : undefined
            }}
          />
          {confirmText === 'DELETE-ALL-DATA' && (
            <Alert variant="danger" className="text-center">
              <strong>CONFIRMED!</strong> Click the button below to permanently delete all data.
            </Alert>
          )}
        </Modal.Body>
        <Modal.Footer>
          <Button variant="success" onClick={handleCancelClear}>
            Cancel (Keep My Data)
          </Button>
          <Button
            variant="danger"
            onClick={handleWarning3Continue}
            disabled={confirmText !== 'DELETE-ALL-DATA' || clearDbLoading}
          >
            {clearDbLoading && <Spinner size="sm" className="me-2" />}
            {clearDbLoading ? 'Deleting...' : '☠️ DELETE EVERYTHING ☠️'}
          </Button>
        </Modal.Footer>
      </Modal>
    </Container>
  );
};

export default Admin;