import api from './authService';

export const apiService = {
  // Transaction APIs
  async getTransactions(userId, filters = {}) {
    const params = new URLSearchParams();
    params.append('user_id', userId);
    Object.keys(filters).forEach(key => {
      if (filters[key]) params.append(key, filters[key]);
    });
    
    const response = await api.get(`/transactions/?${params}`);
    return response.data;
  },

  async createTransaction(transaction, userId) {
    const transactionWithUserId = {
      ...transaction,
      user_id: userId
    };
    
    const response = await api.post('/transactions/', transactionWithUserId);
    return response.data;
  },

  async createTransactionLegacy(transaction) {
    const response = await api.post('/transactions/legacy/', transaction);
    return response.data;
  },

  async updateTransaction(id, transaction, userId) {
    // Send JSON body - backend expects TransactionUpdate schema
    const updateData = {};
    Object.keys(transaction).forEach(key => {
      if (transaction[key] !== null && transaction[key] !== undefined) {
        updateData[key] = transaction[key];
      }
    });

    const response = await api.put(`/transactions/${id}`, updateData);
    return response.data;
  },

  async deleteTransaction(id, userId) {
    const formData = new FormData();
    formData.append('user_id', userId);
    
    const response = await api.delete(`/transactions/${id}`, { data: formData });
    return response.data;
  },

  // File Upload APIs
  async uploadContractNotes(files, password, userId) {
    const formData = new FormData();
    files.forEach(file => formData.append('files', file));
    formData.append('password', password);
    formData.append('user_id', userId);
    
    const response = await api.post('/upload-contract-notes/', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  // Stock APIs
  async getStockPrice(symbol) {
    const response = await api.get(`/stock-price/${symbol}`);
    return response.data;
  },

  async getMarketIndices() {
    const response = await api.get('/market-indices');
    return response.data;
  },

  async searchStocks(query) {
    if (!query || query.trim().length < 2) {
      return { results: [] };
    }
    const response = await api.get(`/search-stocks/${encodeURIComponent(query.trim())}`);
    return response.data;
  },

  async enrichSecurityData(securityName, ticker, isin) {
    const params = new URLSearchParams();
    if (securityName) params.append('security_name', securityName);
    if (ticker) params.append('ticker', ticker);
    if (isin) params.append('isin', isin);
    
    const response = await api.get(`/securities/enrich?${params}`);
    return response.data;
  },

  // Portfolio APIs
  async getPortfolioSummary(userId) {
    if (!userId) {
      throw new Error('User ID is required');
    }
    const response = await api.get('/portfolio-summary/', {
      params: { user_id: userId }
    });
    return response.data;
  },

  // User APIs
  async getUsers() {
    const response = await api.get('/users/');
    return response.data;
  },

  async createUser(userData) {
    const response = await api.post('/users/', userData);
    return response.data;
  },

  async deleteUser(userId) {
    const response = await api.delete(`/users/${userId}`);
    return response.data;
  },

  async clearUserTransactions(userId) {
    const response = await api.delete(`/users/${userId}/transactions`);
    return response.data;
  },

  // Capital Gains APIs
  async getCapitalGains(financialYear, userId = null) {
    const params = new URLSearchParams();
    params.append('financial_year', financialYear);
    if (userId) {
      params.append('user_id', userId);
    }
    
    const response = await api.get(`/capital-gains/?${params}`);
    return response.data;
  },

  async getCapitalGainsAvailableYears(userId = null) {
    const params = new URLSearchParams();
    if (userId) {
      params.append('user_id', userId);
    }
    
    const response = await api.get(`/capital-gains/available-years?${params}`);
    return response.data;
  },

  // Security APIs
  async getSecurities(skip = 0, limit = 100) {
    const params = new URLSearchParams();
    params.append('skip', skip);
    params.append('limit', limit);
    
    const response = await api.get(`/securities/?${params}`);
    return response.data;
  },

  async getSecurity(securityId) {
    const response = await api.get(`/securities/${securityId}`);
    return response.data;
  },

  async createSecurity(security, adminEmail) {
    const formData = new FormData();
    formData.append('admin_email', adminEmail);
    Object.keys(security).forEach(key => {
      formData.append(key, security[key]);
    });
    
    const response = await api.post('/securities/', formData);
    return response.data;
  },

  async updateSecurity(securityId, security, adminEmail) {
    const formData = new FormData();
    formData.append('admin_email', adminEmail);
    Object.keys(security).forEach(key => {
      formData.append(key, security[key]);
    });
    
    const response = await api.put(`/securities/${securityId}`, formData);
    return response.data;
  },

  async deleteSecurity(securityId, adminEmail) {
    const formData = new FormData();
    formData.append('admin_email', adminEmail);
    
    const response = await api.delete(`/securities/${securityId}`, { data: formData });
    return response.data;
  },

  // Admin APIs
  async checkAdminAccess(userEmail) {
    const response = await api.get('/admin/check-access', {
      params: { user_email: userEmail }
    });
    return response.data;
  },

  async getAdminUsers() {
    const response = await api.get('/admin/users/list');
    return response.data;
  },

  async addAdminUser(email) {
    const formData = new FormData();
    formData.append('email', email);
    
    const response = await api.post('/admin/users/add', formData);
    return response.data;
  },

  async removeAdminUser(email) {
    const formData = new FormData();
    formData.append('email', email);

    const response = await api.delete('/admin/users/remove', { data: formData });
    return response.data;
  },

  // Corporate Events APIs
  async getCorporateEvents(filters = {}) {
    const params = new URLSearchParams();
    if (filters.security_id) params.append('security_id', filters.security_id);
    if (filters.event_type) params.append('event_type', filters.event_type);
    if (filters.is_applied !== undefined) params.append('is_applied', filters.is_applied);
    if (filters.skip) params.append('skip', filters.skip);
    if (filters.limit) params.append('limit', filters.limit);

    const response = await api.get(`/corporate-events/?${params}`);
    return response.data;
  },

  async getCorporateEvent(eventId) {
    const response = await api.get(`/corporate-events/${eventId}`);
    return response.data;
  },

  async createCorporateEvent(event, adminEmail) {
    const params = new URLSearchParams();
    params.append('admin_email', adminEmail);

    const response = await api.post(`/corporate-events/?${params}`, event);
    return response.data;
  },

  async updateCorporateEvent(eventId, event, adminEmail) {
    const params = new URLSearchParams();
    params.append('admin_email', adminEmail);

    const response = await api.put(`/corporate-events/${eventId}?${params}`, event);
    return response.data;
  },

  async deleteCorporateEvent(eventId, adminEmail) {
    const params = new URLSearchParams();
    params.append('admin_email', adminEmail);

    const response = await api.delete(`/corporate-events/${eventId}?${params}`);
    return response.data;
  },

  async applyCorporateEvent(eventId, adminEmail) {
    const params = new URLSearchParams();
    params.append('admin_email', adminEmail);

    const response = await api.post(`/corporate-events/${eventId}/apply?${params}`);
    return response.data;
  },

  async revertCorporateEvent(eventId, adminEmail) {
    const params = new URLSearchParams();
    params.append('admin_email', adminEmail);

    const response = await api.post(`/corporate-events/${eventId}/revert?${params}`);
    return response.data;
  },

  // Corporate Events Fetching
  async fetchCorporateEventsForSecurity(securityId, adminEmail, force = false) {
    const params = new URLSearchParams();
    params.append('admin_email', adminEmail);
    if (force) params.append('force', 'true');

    const response = await api.post(`/corporate-events/fetch/${securityId}?${params}`);
    return response.data;
  },

  async fetchCorporateEventsForAll(adminEmail, force = false) {
    const params = new URLSearchParams();
    params.append('admin_email', adminEmail);
    if (force) params.append('force', 'true');

    const response = await api.post(`/corporate-events/fetch-all?${params}`);
    return response.data;
  },

  async getCorporateEventsFetchStatus(adminEmail) {
    const params = new URLSearchParams();
    params.append('admin_email', adminEmail);

    const response = await api.get(`/corporate-events/fetch-status?${params}`);
    return response.data;
  },

  // Lots APIs
  async getLots(userId, filters = {}) {
    const params = new URLSearchParams();
    params.append('user_id', userId);
    if (filters.security_id) params.append('security_id', filters.security_id);
    if (filters.status) params.append('status', filters.status);
    if (filters.skip) params.append('skip', filters.skip);
    if (filters.limit) params.append('limit', filters.limit);

    const response = await api.get(`/lots/?${params}`);
    return response.data;
  },

  async getLotDetail(lotId) {
    const response = await api.get(`/lots/${lotId}`);
    return response.data;
  },

  async getLotAdjustments(lotId) {
    const response = await api.get(`/lots/${lotId}/adjustments`);
    return response.data;
  },

  async getLotSaleAllocations(lotId) {
    const response = await api.get(`/lots/${lotId}/sale-allocations`);
    return response.data;
  },

  // Adjusted Portfolio APIs
  async getAdjustedPortfolio(userId) {
    const params = new URLSearchParams();
    params.append('user_id', userId);

    const response = await api.get(`/portfolio-adjusted/?${params}`);
    return response.data;
  },

  async getAdjustedCapitalGains(financialYear, userId = null) {
    const params = new URLSearchParams();
    params.append('financial_year', financialYear);
    if (userId) params.append('user_id', userId);

    const response = await api.get(`/capital-gains-adjusted/?${params}`);
    return response.data;
  },

  async recalculateSaleAllocations(userId, securityId, adminEmail) {
    const params = new URLSearchParams();
    params.append('user_id', userId);
    if (securityId) params.append('security_id', securityId);
    params.append('admin_email', adminEmail);

    const response = await api.post(`/lots/recalculate?${params}`);
    return response.data;
  },

  async runLotMigration(adminEmail) {
    const params = new URLSearchParams();
    params.append('admin_email', adminEmail);

    const response = await api.post(`/admin/migrate-to-lots?${params}`);
    return response.data;
  }
};