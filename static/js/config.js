/* config.js — set your backend endpoint and API key */
const API_URL = 'https://traffic-api-c04h.onrender.com';  // your Render URL
const API_KEY = '12345';                                   // must match Render env

// Optional safety checks (keeps console useful on Monday)
if (!API_URL || !API_URL.startsWith('http')) {
  console.error('API_URL is not set correctly in config.js');
}
if (!API_KEY) {
  console.error('API_KEY is missing in config.js');
}

// Optional: request timeout (ms) for fetch helpers can use this
const API_TIMEOUT_MS = 8000;
