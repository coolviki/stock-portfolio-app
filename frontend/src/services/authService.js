import axios from 'axios';

// API URL configuration for different environments
const API_URL = process.env.REACT_APP_API_URL ||
  (process.env.NODE_ENV === 'production' ? '' : 'http://localhost:8000');

const api = axios.create({
  baseURL: API_URL,
});

export const authService = {
  async getAuthConfig() {
    const response = await api.get('/config/auth');
    return response.data;
  },

  async login(username) {
    const formData = new FormData();
    formData.append('username', username);

    const response = await api.post('/users/select-or-create', formData);
    return { user_data: response.data };
  },

  async firebaseLogin(userData) {
    const response = await api.post('/auth/firebase', userData);
    return { user_data: response.data };
  },

  async getAllUsers() {
    const response = await api.get('/users/');
    return response.data;
  },

  async getUserByUsername(username) {
    const response = await api.get(`/users/${username}`);
    return response.data;
  }
};

export default api;