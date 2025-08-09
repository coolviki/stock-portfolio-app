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

  async updateTransaction(id, transaction, userId) {
    const formData = new FormData();
    formData.append('user_id', userId);
    Object.keys(transaction).forEach(key => {
      if (transaction[key] !== null && transaction[key] !== undefined) {
        formData.append(key, transaction[key]);
      }
    });
    
    const response = await api.put(`/transactions/${id}`, formData);
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

  async searchStocks(query) {
    if (!query || query.trim().length < 2) {
      return { results: [] };
    }
    const response = await api.get(`/search-stocks/${encodeURIComponent(query.trim())}`);
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

  async createSecurity(security) {
    const response = await api.post('/securities/', security);
    return response.data;
  },

  async updateSecurity(securityId, security) {
    const response = await api.put(`/securities/${securityId}`, security);
    return response.data;
  },

  async deleteSecurity(securityId) {
    const response = await api.delete(`/securities/${securityId}`);
    return response.data;
  }
};