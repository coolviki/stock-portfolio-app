import axios from 'axios';

// In production (monorepo), use relative URL. In development, use localhost.
const API_URL = process.env.NODE_ENV === 'production' ? '' : (process.env.REACT_APP_API_URL || 'http://localhost:8000');

const api = axios.create({
  baseURL: API_URL,
});

export const authService = {
  async login(username) {
    const formData = new FormData();
    formData.append('username', username);
    
    const response = await api.post('/users/select-or-create', formData);
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