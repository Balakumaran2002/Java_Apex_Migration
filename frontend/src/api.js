import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000/api';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Interceptor to inject provider and apiKey from local storage
apiClient.interceptors.request.use((config) => {
  const settings = JSON.parse(localStorage.getItem('assistant_settings') || '{}');
  
  if (config.data) {
    let dataObj = config.data;
    const isString = typeof config.data === 'string';
    
    if (isString) {
      try {
        dataObj = JSON.parse(config.data);
      } catch (e) {
        // Fallback if not parsable
      }
    }
    
    if (dataObj && typeof dataObj === 'object') {
      if (!dataObj.apiKey && settings.apiKey) {
        dataObj.apiKey = settings.apiKey;
      }
      if (!dataObj.provider && settings.provider) {
        dataObj.provider = settings.provider;
      }
      if (!dataObj.modelName && settings.modelName) {
        dataObj.modelName = settings.modelName;
      }
      
      if (isString) {
        config.data = JSON.stringify(dataObj);
      } else {
        config.data = dataObj;
      }
    }
  }
  return config;
}, (error) => {
  return Promise.reject(error);
});

export const getStatus = async () => {
  const response = await apiClient.get('/status');
  return response.data;
};

export const getLLMStatus = async () => {
  const response = await apiClient.get('/llm/status');
  return response.data;
};

export const analyzeRepository = async (repoUrl) => {
  const response = await apiClient.post('/analyze', { repoUrl });
  return response.data;
};

export const migrateRepository = async (repoUrl, targetVersion) => {
  const response = await apiClient.post('/migrate', { repoUrl, targetVersion });
  return response.data;
};

export const getMigrationStatus = async (taskId) => {
  const response = await apiClient.get(`/migrate/status/${taskId}`);
  return response.data;
};

export const convertCode = async (files) => {
  const response = await apiClient.post('/convert', { files });
  return response.data;
};

export const getMigrationReportUrl = () => {
  return `${API_BASE_URL}/report/migration`;
};

export const getConversionReportUrl = () => {
  return `${API_BASE_URL}/report/conversion`;
};

export const getPythonZipUrl = () => {
  return `${API_BASE_URL}/download/python`;
};

export const askChatbot = async (message) => {
  const response = await apiClient.post('/chat', { message });
  return response.data;
};

export const startProject = async (repoName) => {
  const response = await apiClient.post('/run/start', { repoName });
  return response.data;
};

export const stopProject = async (repoName) => {
  const response = await apiClient.post('/run/stop', { repoName });
  return response.data;
};

export const getProjectStatus = async (repoName) => {
  const response = await apiClient.get(`/run/status/${repoName}`);
  return response.data;
};

export const getProjectLogs = async (repoName) => {
  const response = await apiClient.get(`/run/logs/${repoName}`);
  return response.data;
};

// --- History Endpoints ---
export const getMigrationHistory = async () => {
  const response = await apiClient.get('/history');
  return response.data;
};

export const clearMigrationHistory = async () => {
  const response = await apiClient.delete('/history');
  return response.data;
};

// --- API Key Management Endpoints ---

export const getActiveProvider = async () => {
  const response = await apiClient.get('/keys/active-provider');
  return response.data;
};

export const setActiveProvider = async (provider) => {
  const response = await apiClient.put('/keys/active-provider', { provider });
  return response.data;
};

export const getApiKeys = async (provider) => {
  const response = await apiClient.get(`/keys/${provider}`);
  return response.data;
};

export const addApiKey = async (provider, name, key, is_default = false) => {
  const response = await apiClient.post(`/keys/${provider}`, { name, key, is_default });
  return response.data;
};

export const editApiKey = async (provider, keyId, name, key = null) => {
  const payload = { name };
  if (key) payload.key = key;
  const response = await apiClient.put(`/keys/${provider}/${keyId}`, payload);
  return response.data;
};

export const deleteApiKey = async (provider, keyId) => {
  const response = await apiClient.delete(`/keys/${provider}/${keyId}`);
  return response.data;
};

export const toggleApiKeyStatus = async (provider, keyId, is_active) => {
  const response = await apiClient.patch(`/keys/${provider}/${keyId}/status`, { is_active });
  return response.data;
};

export const setDefaultApiKey = async (provider, keyId) => {
  const response = await apiClient.patch(`/keys/${provider}/${keyId}/default`);
  return response.data;
};

export default apiClient;
