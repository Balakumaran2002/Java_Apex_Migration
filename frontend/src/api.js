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

export default apiClient;
