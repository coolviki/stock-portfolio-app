import React, { useState } from 'react';
import { Card, Form, Button, Alert, Table, Modal, Badge } from 'react-bootstrap';
import { apiService } from '../services/apiService';
import { useAuth } from '../context/AuthContext';
import { toast } from 'react-toastify';

const Upload = () => {
  const [files, setFiles] = useState([]);
  const [password, setPassword] = useState('');
  const [uploading, setUploading] = useState(false);
  const [uploadResults, setUploadResults] = useState(null);
  const [showPreview, setShowPreview] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const { selectedUserId } = useAuth();

  const handleFileSelect = (e) => {
    const selectedFiles = Array.from(e.target.files);
    setFiles(selectedFiles);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const droppedFiles = Array.from(e.dataTransfer.files);
    const pdfFiles = droppedFiles.filter(file => file.type === 'application/pdf');
    setFiles(pdfFiles);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setDragOver(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setDragOver(false);
  };

  const handleUpload = async () => {
    if (files.length === 0) {
      toast.error('Please select PDF files to upload');
      return;
    }

    if (!password) {
      toast.error('Please enter the password for the PDF files');
      return;
    }

    if (!selectedUserId) {
      toast.error('Please select a user first');
      return;
    }

    setUploading(true);
    try {
      const result = await apiService.uploadContractNotes(files, password, selectedUserId);
      setUploadResults(result);
      setShowPreview(true);
      toast.success(`Successfully processed ${result.uploaded_transactions} transactions`);
    } catch (error) {
      toast.error('Error uploading contract notes: ' + (error.response?.data?.detail || error.message));
      console.error('Upload error:', error);
    } finally {
      setUploading(false);
    }
  };

  const removeFile = (index) => {
    setFiles(files.filter((_, i) => i !== index));
  };

  const resetUpload = () => {
    setFiles([]);
    setPassword('');
    setUploadResults(null);
    setShowPreview(false);
  };

  // Function to aggregate transactions by security and transaction type
  const aggregateTransactions = (transactions) => {
    const aggregatedMap = new Map();
    
    transactions.forEach(transaction => {
      if (!transaction.security_name || transaction.error) return;
      
      // Create a unique key for each security + transaction type + date combination
      const date = transaction.transaction_date ? new Date(transaction.transaction_date).toDateString() : 'Unknown Date';
      const key = `${transaction.security_name}_${transaction.transaction_type}_${date}`;
      
      if (aggregatedMap.has(key)) {
        // Aggregate with existing transaction
        const existing = aggregatedMap.get(key);
        existing.quantity += transaction.quantity || 0;
        existing.total_amount += transaction.total_amount || 0;
        existing.transaction_count += 1;
        // Weighted average price calculation
        existing.price_per_unit = existing.total_amount / existing.quantity;
      } else {
        // Create new aggregated transaction
        aggregatedMap.set(key, {
          ...transaction,
          quantity: transaction.quantity || 0,
          total_amount: transaction.total_amount || 0,
          transaction_count: 1,
          price_per_unit: transaction.price_per_unit || 0
        });
      }
    });
    
    return Array.from(aggregatedMap.values()).sort((a, b) => {
      // Sort by security name, then by transaction type
      if (a.security_name !== b.security_name) {
        return a.security_name.localeCompare(b.security_name);
      }
      return a.transaction_type.localeCompare(b.transaction_type);
    });
  };

  return (
    <div>
      <h2 className="mb-4">📤 Upload Contract Notes</h2>

      <Card className="mb-4">
        <Card.Header>
          <h5>Upload PDF Contract Notes</h5>
        </Card.Header>
        <Card.Body>
          <Alert variant="info">
            <strong>Instructions:</strong>
            <ul className="mb-0 mt-2">
              <li>Upload password-protected PDF contract notes from your broker</li>
              <li>The system will automatically extract transaction details</li>
              <li>You can review and confirm the extracted data before saving</li>
              <li>Supported formats: PDF files with tabular transaction data</li>
            </ul>
          </Alert>

          {/* File Drop Area */}
          <div
            className={`upload-area mb-3 ${dragOver ? 'dragover' : ''}`}
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onClick={() => document.getElementById('fileInput').click()}
          >
            <div>
              <h4>📁 Drop PDF files here or click to browse</h4>
              <p className="text-muted">Supports multiple PDF files</p>
            </div>
            <input
              id="fileInput"
              type="file"
              multiple
              accept=".pdf"
              onChange={handleFileSelect}
              style={{ display: 'none' }}
            />
          </div>

          {/* Selected Files */}
          {files.length > 0 && (
            <div className="mb-3">
              <h6>Selected Files:</h6>
              <ul className="list-group">
                {files.map((file, index) => (
                  <li key={index} className="list-group-item d-flex justify-content-between align-items-center">
                    <span>
                      📄 {file.name} 
                      <small className="text-muted ms-2">({(file.size / 1024).toFixed(1)} KB)</small>
                    </span>
                    <Button
                      variant="outline-danger"
                      size="sm"
                      onClick={() => removeFile(index)}
                    >
                      Remove
                    </Button>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Password Input */}
          <Form.Group className="mb-3">
            <Form.Label>PDF Password</Form.Label>
            <Form.Control
              type="password"
              placeholder="Enter the password for your PDF files"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={uploading}
            />
            <Form.Text className="text-muted">
              All selected PDF files should have the same password
            </Form.Text>
          </Form.Group>

          {/* Upload Button */}
          <div className="d-flex gap-2">
            <Button
              variant="primary"
              onClick={handleUpload}
              disabled={uploading || files.length === 0 || !password}
            >
              {uploading ? 'Processing...' : 'Upload and Process'}
            </Button>
            
            {files.length > 0 && (
              <Button variant="outline-secondary" onClick={resetUpload}>
                Reset
              </Button>
            )}
          </div>
        </Card.Body>
      </Card>

      {/* Processing Status */}
      {uploading && (
        <Card className="mb-4">
          <Card.Body className="text-center">
            <div className="spinner-border text-primary mb-3" role="status">
              <span className="visually-hidden">Loading...</span>
            </div>
            <h5>Processing PDF Files...</h5>
            <p className="text-muted">Extracting transaction data from your contract notes</p>
          </Card.Body>
        </Card>
      )}

      {/* Upload Results Summary */}
      {uploadResults && (
        <Card>
          <Card.Header>
            <h5>Upload Results</h5>
          </Card.Header>
          <Card.Body>
            <div className="row text-center mb-3">
              <div className="col-md-4">
                <div className="card bg-success text-white">
                  <div className="card-body">
                    <h3>{uploadResults.uploaded_transactions}</h3>
                    <p>Transactions Added</p>
                  </div>
                </div>
              </div>
              <div className="col-md-4">
                <div className="card bg-info text-white">
                  <div className="card-body">
                    <h3>{files.length}</h3>
                    <p>Files Processed</p>
                  </div>
                </div>
              </div>
              <div className="col-md-4">
                <div className="card bg-warning text-white">
                  <div className="card-body">
                    <h3>{uploadResults.results.filter(r => r.error).length}</h3>
                    <p>Errors</p>
                  </div>
                </div>
              </div>
            </div>

            {uploadResults.results.some(r => r.error) && (
              <Alert variant="warning">
                <h6>Processing Errors:</h6>
                <ul className="mb-0">
                  {uploadResults.results
                    .filter(r => r.error)
                    .map((result, index) => (
                      <li key={index}>{result.error}</li>
                    ))}
                </ul>
              </Alert>
            )}

            <div className="d-flex gap-2">
              <Button variant="success" onClick={resetUpload}>
                Upload More Files
              </Button>
              <Button variant="primary" onClick={() => window.location.href = '/transactions'}>
                View All Transactions
              </Button>
            </div>
          </Card.Body>
        </Card>
      )}

      {/* Transaction Preview Modal */}
      <Modal show={showPreview} onHide={() => setShowPreview(false)} size="xl">
        <Modal.Header closeButton>
          <Modal.Title>Extracted Transactions Preview</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          {uploadResults && (
            <div>
              <Alert variant="success">
                Successfully extracted {uploadResults.uploaded_transactions} transactions
              </Alert>
              
              {(() => {
                const validTransactions = uploadResults.results.filter(r => !r.error && r.security_name);
                const aggregatedTransactions = aggregateTransactions(validTransactions);
                
                return (
                  <>
                    <div className="d-flex justify-content-between align-items-center mb-3">
                      <h6>Transaction Summary (Aggregated by Security)</h6>
                      <Badge bg="info" pill>
                        {aggregatedTransactions.length} unique positions from {validTransactions.length} individual trades
                      </Badge>
                    </div>
                    
                    <div className="table-responsive">
                      <Table striped hover>
                        <thead>
                          <tr>
                            <th>Security</th>
                            <th>Type</th>
                            <th>Total Quantity</th>
                            <th>Avg Price</th>
                            <th>Total Amount</th>
                            <th>Date</th>
                            <th>Trades</th>
                          </tr>
                        </thead>
                        <tbody>
                          {aggregatedTransactions.map((transaction, index) => (
                            <tr key={index}>
                              <td>{transaction.security_name}</td>
                              <td>
                                <Badge bg={transaction.transaction_type === 'BUY' ? 'success' : 'danger'}>
                                  {transaction.transaction_type}
                                </Badge>
                              </td>
                              <td>{transaction.quantity ? transaction.quantity.toLocaleString('en-IN') : 'N/A'}</td>
                              <td>₹{transaction.price_per_unit ? transaction.price_per_unit.toFixed(2) : 'N/A'}</td>
                              <td>₹{transaction.total_amount ? transaction.total_amount.toLocaleString('en-IN') : 'N/A'}</td>
                              <td>{transaction.transaction_date ? new Date(transaction.transaction_date).toLocaleDateString() : 'N/A'}</td>
                              <td>
                                <Badge bg="secondary" pill>
                                  {transaction.transaction_count}
                                </Badge>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </Table>
                    </div>
                    
                    {validTransactions.length > aggregatedTransactions.length && (
                      <Alert variant="info" className="mt-3">
                        <small>
                          <strong>Note:</strong> Multiple trades for the same security on the same day have been combined. 
                          Original {validTransactions.length} individual trades aggregated into {aggregatedTransactions.length} positions.
                        </small>
                      </Alert>
                    )}
                  </>
                );
              })()}
            </div>
          )}
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={() => setShowPreview(false)}>
            Close
          </Button>
          <Button variant="primary" onClick={() => window.location.href = '/transactions'}>
            View All Transactions
          </Button>
        </Modal.Footer>
      </Modal>
    </div>
  );
};

export default Upload;