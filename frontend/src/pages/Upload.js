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
  const [editMode, setEditMode] = useState(false);
  const [editedTransactions, setEditedTransactions] = useState({});
  const [savingChanges, setSavingChanges] = useState(false);
  const [selectedBroker, setSelectedBroker] = useState('hdfc-securities');
  const { user, selectedUserId } = useAuth();

  // Popular Indian stock brokers list
  const brokers = [
    {
      id: 'hdfc-securities',
      name: 'HDFC Securities',
      icon: '🏦',
      supported: true,
      description: 'Fully supported - PDF parsing available'
    },
    {
      id: 'zerodha',
      name: 'Zerodha',
      icon: '⚡',
      supported: false,
      description: 'Coming soon'
    },
    {
      id: 'upstox',
      name: 'Upstox',
      icon: '📈',
      supported: false,
      description: 'Coming soon'
    },
    {
      id: 'angel-one',
      name: 'Angel One (Angel Broking)',
      icon: '👼',
      supported: false,
      description: 'Coming soon'
    },
    {
      id: 'icici-direct',
      name: 'ICICI Direct',
      icon: '🏛️',
      supported: false,
      description: 'Coming soon'
    },
    {
      id: 'kotak-securities',
      name: 'Kotak Securities',
      icon: '🏢',
      supported: false,
      description: 'Coming soon'
    },
    {
      id: 'sharekhan',
      name: 'Sharekhan',
      icon: '📊',
      supported: false,
      description: 'Coming soon'
    },
    {
      id: 'motilal-oswal',
      name: 'Motilal Oswal',
      icon: '🔷',
      supported: false,
      description: 'Coming soon'
    },
    {
      id: 'edelweiss',
      name: 'Edelweiss',
      icon: '❄️',
      supported: false,
      description: 'Coming soon'
    },
    {
      id: '5paisa',
      name: '5paisa',
      icon: '5️⃣',
      supported: false,
      description: 'Coming soon'
    },
    {
      id: 'groww',
      name: 'Groww',
      icon: '🌱',
      supported: false,
      description: 'Coming soon'
    },
    {
      id: 'paytm-money',
      name: 'Paytm Money',
      icon: '💰',
      supported: false,
      description: 'Coming soon'
    }
  ];

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

    if (!user?.id) {
      toast.error('Please log in first');
      return;
    }

    // Check if broker is supported
    const broker = brokers.find(b => b.id === selectedBroker);
    if (!broker?.supported) {
      toast.error(`${broker?.name || 'Selected broker'} is not yet supported. Please select HDFC Securities for now.`);
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
    setSelectedBroker('hdfc-securities');
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

  // Editing functions
  const handleEditToggle = () => {
    if (editMode) {
      // Cancel edit mode - reset edited transactions
      setEditedTransactions({});
    }
    setEditMode(!editMode);
  };

  const handleTransactionEdit = (transactionId, field, value) => {
    setEditedTransactions(prev => ({
      ...prev,
      [transactionId]: {
        ...prev[transactionId],
        [field]: value
      }
    }));
  };

  const handleSaveChanges = async () => {
    setSavingChanges(true);
    try {
      const updatedResults = [...uploadResults.results];
      
      // Process each edited transaction
      for (const transactionId of Object.keys(editedTransactions)) {
        const edits = editedTransactions[transactionId];
        const transactionIndex = updatedResults.findIndex(t => t.id == transactionId);
        
        if (transactionIndex !== -1) {
          const transaction = updatedResults[transactionIndex];
          const updateData = {};
          
          // Prepare update data with proper type conversion
          Object.keys(edits).forEach(field => {
            if (field === 'quantity' || field === 'price_per_unit') {
              updateData[field] = parseFloat(edits[field]) || 0;
            } else {
              updateData[field] = edits[field];
            }
          });
          
          // Recalculate total amount if quantity or price changed
          if (updateData.quantity !== undefined || updateData.price_per_unit !== undefined) {
            const quantity = updateData.quantity !== undefined ? updateData.quantity : transaction.quantity;
            const price = updateData.price_per_unit !== undefined ? updateData.price_per_unit : transaction.price_per_unit;
            updateData.total_amount = quantity * price;
          }
          
          // Call backend API to update the transaction
          const updatedTransaction = await apiService.updateTransaction(transactionId, updateData, selectedUserId);
          
          // Update the local results with the backend response
          updatedResults[transactionIndex] = {
            ...transaction,
            ...updatedTransaction,
            transaction_date: updatedTransaction.transaction_date,
            order_date: updatedTransaction.order_date,
            created_at: updatedTransaction.created_at,
            updated_at: updatedTransaction.updated_at
          };
        }
      }

      // Update uploadResults with edited transactions
      setUploadResults({
        ...uploadResults,
        results: updatedResults
      });
      
      setEditMode(false);
      setEditedTransactions({});
      toast.success(`Successfully updated ${Object.keys(editedTransactions).length} transaction(s)!`);
    } catch (error) {
      toast.error('Error saving changes: ' + (error.response?.data?.detail || error.message));
      console.error('Save changes error:', error);
    } finally {
      setSavingChanges(false);
    }
  };

  const renderEditableField = (transaction, field, value, type = 'text') => {
    if (!editMode) {
      // Display mode
      if (field === 'total_amount' && value) {
        return `₹${value.toLocaleString('en-IN')}`;
      } else if (field === 'price_per_unit' && value) {
        return `₹${value.toFixed(2)}`;
      } else if (field === 'quantity' && value) {
        return value.toLocaleString('en-IN');
      }
      return value || 'N/A';
    }

    // Edit mode
    const editedValue = editedTransactions[transaction.id]?.[field] ?? value;
    
    return (
      <Form.Control
        type={type}
        size="sm"
        value={editedValue || ''}
        onChange={(e) => handleTransactionEdit(transaction.id, field, e.target.value)}
        style={{ minWidth: type === 'number' ? '80px' : '120px' }}
      />
    );
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
              <li>Select your broker from the dropdown below</li>
              <li>Upload password-protected PDF contract notes from your broker</li>
              <li>The system will automatically extract transaction details</li>
              <li>You can review and confirm the extracted data before saving</li>
              <li>Supported formats: PDF files with tabular transaction data</li>
            </ul>
          </Alert>

          {/* Broker Selection */}
          <div className="mb-4">
            <Form.Group>
              <Form.Label className="fw-bold">Select Your Broker</Form.Label>
              <Form.Select
                value={selectedBroker}
                onChange={(e) => setSelectedBroker(e.target.value)}
                disabled={uploading}
                className="mb-3"
              >
                {brokers.map((broker) => (
                  <option key={broker.id} value={broker.id}>
                    {broker.icon} {broker.name} {!broker.supported ? '(Coming Soon)' : ''}
                  </option>
                ))}
              </Form.Select>
              
              {/* Broker Status Alert */}
              {(() => {
                const selectedBrokerData = brokers.find(b => b.id === selectedBroker);
                if (!selectedBrokerData) return null;
                
                return (
                  <Alert 
                    variant={selectedBrokerData.supported ? 'success' : 'warning'} 
                    className="mb-0"
                  >
                    <div className="d-flex align-items-center">
                      <span className="fs-4 me-2">{selectedBrokerData.icon}</span>
                      <div>
                        <strong>{selectedBrokerData.name}</strong>
                        <div className="small">{selectedBrokerData.description}</div>
                        {!selectedBrokerData.supported && (
                          <div className="small text-muted mt-1">
                            Currently only HDFC Securities contract notes can be processed. 
                            Support for other brokers is coming soon!
                          </div>
                        )}
                      </div>
                    </div>
                  </Alert>
                );
              })()}
            </Form.Group>
          </div>

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
              disabled={uploading || files.length === 0 || !password || !brokers.find(b => b.id === selectedBroker)?.supported}
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
      <Modal show={showPreview} onHide={() => {
        setShowPreview(false);
        setEditMode(false);
        setEditedTransactions({});
      }} size="xl">
        <Modal.Header closeButton>
          <Modal.Title>
            {editMode ? 'Edit Transactions' : 'Extracted Transactions Preview'}
          </Modal.Title>
        </Modal.Header>
        <Modal.Body>
          {uploadResults && (
            <div>
              <Alert variant="success">
                Successfully extracted {uploadResults.uploaded_transactions} transactions
              </Alert>
              
              {/* Edit Controls */}
              <div className="d-flex justify-content-between align-items-center mb-3">
                <div>
                  {editMode && (
                    <Alert variant="warning" className="mb-0 me-3" style={{display: 'inline-block', padding: '5px 10px'}}>
                      <small><strong>Edit Mode:</strong> Click on fields to modify transaction details</small>
                    </Alert>
                  )}
                </div>
                <div className="d-flex gap-2">
                  {editMode ? (
                    <>
                      <Button 
                        variant="success" 
                        size="sm" 
                        onClick={handleSaveChanges}
                        disabled={savingChanges || Object.keys(editedTransactions).length === 0}
                      >
                        {savingChanges ? 'Saving...' : 'Save Changes'}
                      </Button>
                      <Button variant="outline-secondary" size="sm" onClick={handleEditToggle}>
                        Cancel
                      </Button>
                    </>
                  ) : (
                    <Button variant="outline-primary" size="sm" onClick={handleEditToggle}>
                      ✏️ Edit Transactions
                    </Button>
                  )}
                </div>
              </div>
              
              {(() => {
                const validTransactions = uploadResults.results.filter(r => !r.error && r.security_name);
                const aggregatedTransactions = aggregateTransactions(validTransactions);
                
                // In edit mode, show individual transactions; otherwise show aggregated
                const transactionsToShow = editMode ? validTransactions : aggregatedTransactions;
                
                return (
                  <>
                    <div className="d-flex justify-content-between align-items-center mb-3">
                      <h6>
                        {editMode 
                          ? 'Individual Transactions (Editable)' 
                          : 'Transaction Summary (Aggregated by Security)'
                        }
                      </h6>
                      {!editMode && (
                        <Badge bg="info" pill>
                          {aggregatedTransactions.length} unique positions from {validTransactions.length} individual trades
                        </Badge>
                      )}
                    </div>
                    
                    <div className="table-responsive">
                      <Table striped hover>
                        <thead>
                          <tr>
                            <th>Security</th>
                            <th>Type</th>
                            <th>{editMode ? 'Quantity' : 'Total Quantity'}</th>
                            <th>{editMode ? 'Price' : 'Avg Price'}</th>
                            <th>Total Amount</th>
                            <th>Date</th>
                            {!editMode && <th>Trades</th>}
                          </tr>
                        </thead>
                        <tbody>
                          {transactionsToShow.map((transaction, index) => (
                            <tr key={editMode ? transaction.id || index : index}>
                              <td>
                                {editMode ? (
                                  renderEditableField(transaction, 'security_name', transaction.security_name)
                                ) : (
                                  transaction.security_name
                                )}
                              </td>
                              <td>
                                {editMode ? (
                                  <Form.Select
                                    size="sm"
                                    value={editedTransactions[transaction.id]?.transaction_type ?? transaction.transaction_type}
                                    onChange={(e) => handleTransactionEdit(transaction.id, 'transaction_type', e.target.value)}
                                    style={{ minWidth: '80px' }}
                                  >
                                    <option value="BUY">BUY</option>
                                    <option value="SELL">SELL</option>
                                  </Form.Select>
                                ) : (
                                  <Badge bg={transaction.transaction_type === 'BUY' ? 'success' : 'danger'}>
                                    {transaction.transaction_type}
                                  </Badge>
                                )}
                              </td>
                              <td>
                                {editMode ? (
                                  renderEditableField(transaction, 'quantity', transaction.quantity, 'number')
                                ) : (
                                  transaction.quantity ? transaction.quantity.toLocaleString('en-IN') : 'N/A'
                                )}
                              </td>
                              <td>
                                {editMode ? (
                                  renderEditableField(transaction, 'price_per_unit', transaction.price_per_unit, 'number')
                                ) : (
                                  transaction.price_per_unit ? `₹${transaction.price_per_unit.toFixed(2)}` : 'N/A'
                                )}
                              </td>
                              <td>
                                {editMode ? (
                                  // In edit mode, calculate total amount automatically
                                  (() => {
                                    const edits = editedTransactions[transaction.id] || {};
                                    const qty = edits.quantity ?? transaction.quantity;
                                    const price = edits.price_per_unit ?? transaction.price_per_unit;
                                    const total = qty && price ? qty * price : transaction.total_amount;
                                    return total ? `₹${total.toLocaleString('en-IN')}` : 'N/A';
                                  })()
                                ) : (
                                  transaction.total_amount ? `₹${transaction.total_amount.toLocaleString('en-IN')}` : 'N/A'
                                )}
                              </td>
                              <td>
                                {transaction.transaction_date ? new Date(transaction.transaction_date).toLocaleDateString() : 'N/A'}
                              </td>
                              {!editMode && (
                                <td>
                                  <Badge bg="secondary" pill>
                                    {transaction.transaction_count || 1}
                                  </Badge>
                                </td>
                              )}
                            </tr>
                          ))}
                        </tbody>
                      </Table>
                    </div>
                    
                    {!editMode && validTransactions.length > aggregatedTransactions.length && (
                      <Alert variant="info" className="mt-3">
                        <small>
                          <strong>Note:</strong> Multiple trades for the same security on the same day have been combined. 
                          Original {validTransactions.length} individual trades aggregated into {aggregatedTransactions.length} positions.
                        </small>
                      </Alert>
                    )}
                    
                    {editMode && Object.keys(editedTransactions).length > 0 && (
                      <Alert variant="warning" className="mt-3">
                        <small>
                          <strong>Pending Changes:</strong> You have {Object.keys(editedTransactions).length} transaction(s) with unsaved changes.
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