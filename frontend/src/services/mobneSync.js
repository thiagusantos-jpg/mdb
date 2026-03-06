import api from './api.js';

export const mobneSync = {
  triggerSync: (entity = 'produtos', page = 1) =>
    api.post('/sync/mobne', { entity, page, pageSize: 100 }),

  getStatus: () => api.get('/sync/status'),
};
