import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { PetApp } from './PetApp.js';

const el = document.getElementById('root');
if (el) {
  createRoot(el).render(
    <StrictMode>
      <PetApp />
    </StrictMode>,
  );
}
