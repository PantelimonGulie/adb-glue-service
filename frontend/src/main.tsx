import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { App } from './App';
import { AutoRefreshProvider } from './api/autoRefresh';
import { ApiError } from './api/client';
import './styles/tokens.css';
import './styles/global.css';

const client = new QueryClient({
  defaultOptions: {
    queries: {
      // A 4xx will not change by asking again; a dropped connection might.
      retry: (failures, error) =>
        failures < 2 && !(error instanceof ApiError && error.status < 500),
    },
  },
});

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={client}>
      <AutoRefreshProvider>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </AutoRefreshProvider>
    </QueryClientProvider>
  </StrictMode>,
);
