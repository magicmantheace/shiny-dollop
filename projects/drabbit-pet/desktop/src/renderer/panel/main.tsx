import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { PanelApp } from './PanelApp.js';

const el = document.getElementById('root');
if (el) {
  createRoot(el).render(
    <StrictMode>
      <PanelApp />
    </StrictMode>,
  );
}
