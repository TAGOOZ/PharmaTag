import { ThemeProvider } from '@pharmatag/ui';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import '@pharmatag/ui/styles.css';
import './index.css';
import { App } from './App';

const root = document.getElementById('root');
if (!root) throw new Error('root element #root not found');

createRoot(root).render(
  <StrictMode>
    <ThemeProvider>
      <App />
    </ThemeProvider>
  </StrictMode>,
);
