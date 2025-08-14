// Utility functions for API calls
import api from '../services/authService';

// Get the current API base URL for direct fetch calls
export const getApiBaseUrl = () => {
  return api.defaults.baseURL;
};

// Helper function for stock price fetching in tooltips
export const fetchStockPrice = async (endpoint) => {
  const baseUrl = getApiBaseUrl();
  const url = `${baseUrl}${endpoint}`;
  return fetch(url);
};

// Stock price fetching functions
export const fetchStockPriceBySymbol = (symbol) => {
  return fetchStockPrice(`/stock-price/${symbol}`);
};

export const fetchStockPriceByIsin = (isin) => {
  return fetchStockPrice(`/stock-price-isin/${isin}`);
};

// Export admin functions
export const fetchAdminExport = (adminEmail) => {
  const baseUrl = getApiBaseUrl();
  const params = new URLSearchParams();
  params.append('user_email', adminEmail);
  return fetch(`${baseUrl}/admin/export?${params}`);
};

export const fetchAdminImport = (formData) => {
  const baseUrl = getApiBaseUrl();
  return fetch(`${baseUrl}/admin/import`, {
    method: 'POST',
    body: formData,
  });
};