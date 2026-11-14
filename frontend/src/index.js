import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import { AuthProvider } from './contexts/AuthContext';
import { LabelsProvider } from './contexts/LabelsContext';
import './index.css';

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <AuthProvider>
      <LabelsProvider>
        <App />
      </LabelsProvider>
    </AuthProvider>
  </React.StrictMode>
);

// Open the app with no signal: a small service worker keeps the app's own files (never the API).
if ('serviceWorker' in navigator && process.env.NODE_ENV === 'production') {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => { /* the app still works online */ });
  });
}
