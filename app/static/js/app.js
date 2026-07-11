/**
 * WeatherWise — Frontend Application Logic
 * ------------------------------------------
 * Responsibilities:
 *  - Tab navigation in the dashboard
 *  - Weather widget (live fetch on load + manual refresh)
 *  - Chat interface (send, receive, typing indicator, reset)
 *  - AI feature forms (plan, checklist, travel, alerts)
 *  - Markdown rendering for AI responses
 *  - Copy-to-clipboard for results
 *  - Toast notifications
 *  - Loading overlay
 *
 * No external dependencies — Vanilla JS only.
 * All fetch calls are made to the same origin (no CORS issues).
 */

'use strict';

// ── Constants ─────────────────────────────────────────────────
const API = {
  WEATHER:      '/api/weather',
  CITIES:       '/api/cities',
  CHAT:         '/api/chat',
  CHAT_RESET:   '/api/chat/reset',
  PLAN:         '/api/preparedness-plan',
  CHECKLIST:    '/api/checklist',
  TRAVEL:       '/api/travel-advisory',
  ALERTS:       '/api/alerts',
};

/** Weather icon map based on WMO weather code ranges */
const WEATHER_ICONS = {
  clear:        '☀️',
  partlyCloudy: '⛅',
  cloudy:       '☁️',
  fog:          '🌫️',
  drizzle:      '🌦️',
  rain:         '🌧️',
  heavyRain:    '⛈️',
  snow:         '❄️',
  thunder:      '⛈️',
};

// ── State ─────────────────────────────────────────────────────
const state = {
  currentCity:    'Mumbai',
  currentLanguage: 'English',
  isChatBusy:     false,
  isFormBusy:     false,
};

// ── DOM References ────────────────────────────────────────────
const dom = {
  // Weather
  cityInput:      () => document.getElementById('city-input'),
  weatherFetchBtn:() => document.getElementById('weather-fetch-btn'),
  wwIcon:         () => document.getElementById('ww-icon'),
  wwTemp:         () => document.getElementById('ww-temp'),
  wwDesc:         () => document.getElementById('ww-desc'),
  wwAlert:        () => document.getElementById('ww-alert'),

  // Language
  langSelect:     () => document.getElementById('language-select'),

  // Chat
  chatMessages:   () => document.getElementById('chat-messages'),
  chatInput:      () => document.getElementById('chat-input'),
  chatSendBtn:    () => document.getElementById('chat-send-btn'),
  resetChatBtn:   () => document.getElementById('reset-chat-btn'),

  // Forms
  planForm:       () => document.getElementById('plan-form'),
  checklistForm:  () => document.getElementById('checklist-form'),
  travelForm:     () => document.getElementById('travel-form'),
  alertsForm:     () => document.getElementById('alerts-form'),

  // Results
  planResult:     () => document.getElementById('plan-result'),
  planContent:    () => document.getElementById('plan-result-content'),
  checklistResult:() => document.getElementById('checklist-result'),
  checklistContent:() => document.getElementById('checklist-result-content'),
  travelResult:   () => document.getElementById('travel-result'),
  travelContent:  () => document.getElementById('travel-result-content'),
  alertsResult:   () => document.getElementById('alerts-result'),
  alertsContent:  () => document.getElementById('alerts-result-content'),

  // UI
  loadingOverlay: () => document.getElementById('loading-overlay'),
  loadingText:    () => document.getElementById('loading-text'),
  toast:          () => document.getElementById('toast'),
};

// ══════════════════════════════════════════════════════════════
// INITIALISATION
// ══════════════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', () => {
  initTabNavigation();
  initWeatherWidget();
  initCityAutocomplete();
  initChat();
  initForms();
  initCopyButtons();
  initLanguageSelector();
});

// City autocomplete shared by weather and AI feature forms.
function initCityAutocomplete() {
  document.querySelectorAll('[data-city-autocomplete]').forEach(input => {
    const list = document.createElement('div');
    list.className = 'city-suggestions';
    list.id = `${input.id}-suggestions`;
    list.setAttribute('role', 'listbox');
    list.hidden = true;
    document.body.appendChild(list);

    input.setAttribute('autocomplete', 'off');
    input.setAttribute('aria-autocomplete', 'list');
    input.setAttribute('aria-controls', list.id);
    input.setAttribute('aria-expanded', 'false');

    let timer;
    let controller;
    let activeIndex = -1;
    let suggestions = [];

    const positionList = () => {
      const rect = input.getBoundingClientRect();
      list.style.left = `${rect.left}px`;
      list.style.top = `${rect.bottom + 4}px`;
      list.style.width = `${rect.width}px`;
    };

    const closeList = () => {
      list.hidden = true;
      activeIndex = -1;
      input.setAttribute('aria-expanded', 'false');
      input.removeAttribute('aria-activedescendant');
    };

    const choose = index => {
      const place = suggestions[index];
      if (!place) return;
      input.value = place.name;
      input.dispatchEvent(new Event('change', { bubbles: true }));
      closeList();
      input.focus();
    };

    const setActive = index => {
      const options = list.querySelectorAll('[role="option"]');
      if (!options.length) return;
      activeIndex = (index + options.length) % options.length;
      options.forEach((option, i) => option.classList.toggle('city-suggestion--active', i === activeIndex));
      input.setAttribute('aria-activedescendant', options[activeIndex].id);
      options[activeIndex].scrollIntoView({ block: 'nearest' });
    };

    const render = places => {
      list.replaceChildren();
      suggestions = places;
      if (!places.length) { closeList(); return; }

      places.forEach((place, index) => {
        const option = document.createElement('button');
        option.type = 'button';
        option.className = 'city-suggestion';
        option.id = `${list.id}-option-${index}`;
        option.setAttribute('role', 'option');

        const name = document.createElement('span');
        name.className = 'city-suggestion__name';
        name.textContent = place.name;
        const detail = document.createElement('span');
        detail.className = 'city-suggestion__detail';
        detail.textContent = [place.admin1, place.country].filter(Boolean).join(', ');
        option.append(name, detail);
        option.addEventListener('mousedown', event => event.preventDefault());
        option.addEventListener('click', () => choose(index));
        list.appendChild(option);
      });

      positionList();
      list.hidden = false;
      input.setAttribute('aria-expanded', 'true');
    };

    input.addEventListener('input', () => {
      clearTimeout(timer);
      controller?.abort();
      const query = input.value.trim();
      if (query.length < 2) { closeList(); return; }

      timer = setTimeout(async () => {
        controller = new AbortController();
        try {
          const response = await fetch(`${API.CITIES}?q=${encodeURIComponent(query)}`, {
            signal: controller.signal,
          });
          if (!response.ok) { closeList(); return; }
          const data = await response.json();
          render(data.suggestions || []);
        } catch (error) {
          if (error.name !== 'AbortError') closeList();
        }
      }, 250);
    });

    input.addEventListener('keydown', event => {
      if (list.hidden || !suggestions.length) return;
      if (event.key === 'ArrowDown') { event.preventDefault(); setActive(activeIndex + 1); }
      else if (event.key === 'ArrowUp') { event.preventDefault(); setActive(activeIndex - 1); }
      else if (event.key === 'Enter' && activeIndex >= 0) { event.preventDefault(); choose(activeIndex); }
      else if (event.key === 'Escape') closeList();
    });
    input.addEventListener('blur', () => setTimeout(closeList, 120));
    input.addEventListener('focus', () => {
      if (suggestions.length && input.value.trim().length >= 2) {
        positionList();
        list.hidden = false;
        input.setAttribute('aria-expanded', 'true');
      }
    });
    window.addEventListener('resize', () => { if (!list.hidden) positionList(); });
    window.addEventListener('scroll', () => { if (!list.hidden) positionList(); }, true);
  });
}

// ══════════════════════════════════════════════════════════════
// TAB NAVIGATION
// ══════════════════════════════════════════════════════════════

function initTabNavigation() {
  const tabs = document.querySelectorAll('.sidebar__tab');
  if (!tabs.length) return;

  tabs.forEach(tab => {
    tab.addEventListener('click', () => switchTab(tab.dataset.tab));
    tab.addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        switchTab(tab.dataset.tab);
      }
    });
  });
}

/**
 * Activate the panel for the given tab name.
 * @param {string} tabName - e.g. 'chat', 'plan', 'checklist', 'travel', 'alerts'
 */
function switchTab(tabName) {
  // Update tab buttons
  document.querySelectorAll('.sidebar__tab').forEach(t => {
    const isActive = t.dataset.tab === tabName;
    t.classList.toggle('sidebar__tab--active', isActive);
    t.setAttribute('aria-selected', String(isActive));
  });

  // Show/hide panels
  document.querySelectorAll('.panel').forEach(panel => {
    const isActive = panel.id === `panel-${tabName}`;
    panel.classList.toggle('panel--active', isActive);
    panel.hidden = !isActive;
  });
}

// ══════════════════════════════════════════════════════════════
// WEATHER WIDGET
// ══════════════════════════════════════════════════════════════

function initWeatherWidget() {
  const fetchBtn = dom.weatherFetchBtn();
  const cityInput = dom.cityInput();
  if (!fetchBtn || !cityInput) return;

  fetchBtn.addEventListener('click', () => fetchWeather(cityInput.value.trim()));

  cityInput.addEventListener('keydown', e => {
    if (e.key === 'Enter') fetchWeather(cityInput.value.trim());
  });

  // Auto-fetch on dashboard load
  fetchWeather(state.currentCity);
}

/**
 * Fetch weather data and update the widget UI.
 * @param {string} city
 */
async function fetchWeather(city) {
  if (!city) return;
  state.currentCity = city;

  const desc = dom.wwDesc();
  if (desc) desc.textContent = 'Fetching…';

  try {
    const resp = await fetch(`${API.WEATHER}?city=${encodeURIComponent(city)}`);
    if (!resp.ok) {
      const err = await resp.json();
      throw new Error(err.error || 'Failed to fetch weather');
    }
    const data = await resp.json();
    updateWeatherWidget(data);
  } catch (err) {
    if (dom.wwDesc()) dom.wwDesc().textContent = 'Weather unavailable';
    console.warn('Weather fetch failed:', err.message);
  }
}

/**
 * Populate weather widget DOM elements from API response.
 * @param {Object} data - weather response object
 */
function updateWeatherWidget(data) {
  const { current, forecast_summary: forecast } = data;

  // Icon
  const iconEl = dom.wwIcon();
  if (iconEl) iconEl.textContent = getWeatherIcon(current.weathercode);

  // Temperature
  const tempEl = dom.wwTemp();
  if (tempEl) tempEl.textContent = `${current.temperature}°C`;

  // Description
  const descEl = dom.wwDesc();
  if (descEl) descEl.textContent = current.description;

  // Alert level dot
  const alertEl = dom.wwAlert();
  if (alertEl) {
    alertEl.textContent = '●';
    alertEl.className = `ww__alert ww__alert--${forecast.monsoon_alert_level}`;
    alertEl.setAttribute('title', `Monsoon alert: ${forecast.monsoon_alert_level.toUpperCase()}`);
  }
}

/**
 * Map WMO weather code to an emoji icon.
 * @param {number} code
 * @returns {string} emoji
 */
function getWeatherIcon(code) {
  if (code === 0 || code === 1) return WEATHER_ICONS.clear;
  if (code === 2 || code === 3) return code === 2 ? WEATHER_ICONS.partlyCloudy : WEATHER_ICONS.cloudy;
  if (code >= 45 && code <= 48) return WEATHER_ICONS.fog;
  if (code >= 51 && code <= 55) return WEATHER_ICONS.drizzle;
  if (code >= 61 && code <= 65) return WEATHER_ICONS.rain;
  if (code >= 71 && code <= 77) return WEATHER_ICONS.snow;
  if (code >= 80 && code <= 82) return code === 82 ? WEATHER_ICONS.heavyRain : WEATHER_ICONS.rain;
  if (code >= 95)               return WEATHER_ICONS.thunder;
  return WEATHER_ICONS.rain;
}

// ══════════════════════════════════════════════════════════════
// LANGUAGE SELECTOR
// ══════════════════════════════════════════════════════════════

function initLanguageSelector() {
  const select = dom.langSelect();
  if (!select) return;
  select.addEventListener('change', () => {
    state.currentLanguage = select.value;
  });
}

// ══════════════════════════════════════════════════════════════
// CHAT
// ══════════════════════════════════════════════════════════════

function initChat() {
  const sendBtn  = dom.chatSendBtn();
  const input    = dom.chatInput();
  const resetBtn = dom.resetChatBtn();

  if (!sendBtn || !input) return;

  // Send on button click
  sendBtn.addEventListener('click', sendChatMessage);

  // Send on Enter (Shift+Enter = new line)
  input.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendChatMessage();
    }
  });

  // Auto-resize textarea
  input.addEventListener('input', () => {
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 120) + 'px';
  });

  // Reset chat
  if (resetBtn) {
    resetBtn.addEventListener('click', resetChat);
  }
}

/** Send the user's chat message to the API and display the response. */
async function sendChatMessage() {
  if (state.isChatBusy) return;

  const input  = dom.chatInput();
  const message = input.value.trim();
  if (!message) return;

  // Render user message
  appendChatMessage('user', message);
  input.value = '';
  input.style.height = 'auto';

  // Show typing indicator
  state.isChatBusy = true;
  dom.chatSendBtn().disabled = true;
  const typingId = showTypingIndicator();

  try {
    const resp = await fetch(API.CHAT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message,
        language: state.currentLanguage,
        city: state.currentCity,
      }),
    });

    removeTypingIndicator(typingId);

    if (!resp.ok) {
      const err = await resp.json();
      throw new Error(err.error || 'AI service error');
    }

    const data = await resp.json();
    appendChatMessage('ai', data.reply);
  } catch (err) {
    removeTypingIndicator(typingId);
    appendChatMessage('ai', `⚠️ ${err.message}. Please try again.`);
  } finally {
    state.isChatBusy = false;
    dom.chatSendBtn().disabled = false;
    dom.chatInput().focus();
  }
}

/**
 * Append a message bubble to the chat log.
 * @param {'user'|'ai'} role
 * @param {string} text
 */
function appendChatMessage(role, text) {
  const container = dom.chatMessages();
  if (!container) return;

  const wrapper = document.createElement('div');
  wrapper.className = `chat-msg chat-msg--${role}`;

  const avatar = document.createElement('div');
  avatar.className = 'chat-msg__avatar';
  avatar.setAttribute('aria-hidden', 'true');
  avatar.textContent = role === 'ai' ? '🌧️' : '👤';

  const bubble = document.createElement('div');
  bubble.className = 'chat-msg__bubble';
  bubble.innerHTML = renderMarkdown(text);

  wrapper.appendChild(avatar);
  wrapper.appendChild(bubble);
  container.appendChild(wrapper);

  // Scroll to bottom
  container.scrollTop = container.scrollHeight;
}

/**
 * Show the AI typing indicator and return its element id.
 * @returns {string} unique element id for later removal
 */
function showTypingIndicator() {
  const container = dom.chatMessages();
  const id = `typing-${Date.now()}`;

  const wrapper = document.createElement('div');
  wrapper.className = 'chat-msg chat-msg--ai';
  wrapper.id = id;

  const avatar = document.createElement('div');
  avatar.className = 'chat-msg__avatar';
  avatar.setAttribute('aria-hidden', 'true');
  avatar.textContent = '🌧️';

  const bubble = document.createElement('div');
  bubble.className = 'chat-msg__bubble typing-indicator';
  bubble.innerHTML = `
    <div class="typing-dot"></div>
    <div class="typing-dot"></div>
    <div class="typing-dot"></div>`;

  wrapper.appendChild(avatar);
  wrapper.appendChild(bubble);
  container.appendChild(wrapper);
  container.scrollTop = container.scrollHeight;

  return id;
}

/**
 * Remove the typing indicator from the DOM.
 * @param {string} id
 */
function removeTypingIndicator(id) {
  const el = document.getElementById(id);
  if (el) el.remove();
}

/** Call the reset API and clear the chat UI. */
async function resetChat() {
  try {
    await fetch(API.CHAT_RESET, { method: 'POST' });
  } catch (_) {
    // Best-effort — clear UI regardless
  }

  const container = dom.chatMessages();
  // Keep only the welcome message (first child)
  while (container.children.length > 1) {
    container.removeChild(container.lastChild);
  }

  showToast('Conversation reset. Starting fresh!', 'info');
}

// ══════════════════════════════════════════════════════════════
// AI FORMS (Plan, Checklist, Travel, Alerts)
// ══════════════════════════════════════════════════════════════

function initForms() {
  setupForm('plan-form',      handlePlanSubmit);
  setupForm('checklist-form', handleChecklistSubmit);
  setupForm('travel-form',    handleTravelSubmit);
  setupForm('alerts-form',    handleAlertsSubmit);
}

/**
 * Attach a submit handler to a form element.
 * @param {string} formId
 * @param {Function} handler
 */
function setupForm(formId, handler) {
  const form = document.getElementById(formId);
  if (!form) return;
  form.addEventListener('submit', e => {
    e.preventDefault();
    if (!state.isFormBusy) handler();
  });
}

/** Collect checked vulnerability values from the plan form. */
function getVulnerabilities() {
  const boxes = document.querySelectorAll('input[name="vulnerability"]:checked');
  return Array.from(boxes).map(b => b.value);
}

async function handlePlanSubmit() {
  const location   = document.getElementById('plan-location')?.value.trim();
  const familySize = document.getElementById('plan-family-size')?.value;
  const phase      = document.getElementById('plan-phase')?.value;

  if (!location) { showToast('Please enter a location.', 'error'); return; }

  await callAI({
    url: API.PLAN,
    body: {
      location,
      family_size: parseInt(familySize, 10),
      vulnerabilities: getVulnerabilities(),
      phase,
      language: state.currentLanguage,
    },
    loadingText: 'Generating your personalised plan…',
    resultEl:    dom.planResult(),
    contentEl:   dom.planContent(),
    responseKey: 'plan',
  });
}

async function handleChecklistSubmit() {
  const location   = document.getElementById('checklist-location')?.value.trim();
  const housing    = document.getElementById('checklist-housing')?.value;
  const familySize = document.getElementById('checklist-family-size')?.value;

  if (!location) { showToast('Please enter a location.', 'error'); return; }

  await callAI({
    url: API.CHECKLIST,
    body: {
      location,
      housing_type: housing,
      family_size: parseInt(familySize, 10),
      language: state.currentLanguage,
    },
    loadingText: 'Building your emergency checklist…',
    resultEl:    dom.checklistResult(),
    contentEl:   dom.checklistContent(),
    responseKey: 'checklist',
  });
}

async function handleTravelSubmit() {
  const origin      = document.getElementById('travel-origin')?.value.trim();
  const destination = document.getElementById('travel-destination')?.value.trim();
  const travelDate  = document.getElementById('travel-date')?.value;
  const mode        = document.getElementById('travel-mode')?.value;

  if (!origin)      { showToast('Please enter an origin city.', 'error'); return; }
  if (!destination) { showToast('Please enter a destination city.', 'error'); return; }
  if (!travelDate)  { showToast('Please select a travel date.', 'error'); return; }

  await callAI({
    url: API.TRAVEL,
    body: {
      origin,
      destination,
      travel_date: travelDate,
      transport_mode: mode,
      language: state.currentLanguage,
    },
    loadingText: 'Analysing route safety…',
    resultEl:    dom.travelResult(),
    contentEl:   dom.travelContent(),
    responseKey: 'advisory',
  });
}

async function handleAlertsSubmit() {
  const location = document.getElementById('alerts-location')?.value.trim();
  const phase    = document.getElementById('alerts-phase')?.value;

  if (!location) { showToast('Please enter a location.', 'error'); return; }

  await callAI({
    url: API.ALERTS,
    body: {
      location,
      phase,
      language: state.currentLanguage,
    },
    loadingText: 'Generating safety alerts…',
    resultEl:    dom.alertsResult(),
    contentEl:   dom.alertsContent(),
    responseKey: 'alerts',
  });
}

/**
 * Generic AI call helper — prevents code duplication across form handlers.
 *
 * @param {Object}  opts
 * @param {string}  opts.url         - API endpoint URL
 * @param {Object}  opts.body        - JSON request body
 * @param {string}  opts.loadingText - Text shown in loading overlay
 * @param {Element} opts.resultEl    - Container element to show/hide
 * @param {Element} opts.contentEl   - Element to write rendered AI response into
 * @param {string}  opts.responseKey - Key to extract from API JSON response
 */
async function callAI({ url, body, loadingText, resultEl, contentEl, responseKey }) {
  state.isFormBusy = true;
  showLoading(loadingText);

  try {
    const resp = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    const data = await resp.json();

    if (!resp.ok) {
      throw new Error(data.error || `Request failed (${resp.status})`);
    }

    const text = data[responseKey];
    if (!text) throw new Error('Empty response from AI.');

    contentEl.innerHTML = renderMarkdown(text);
    resultEl.hidden = false;
    resultEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
  } catch (err) {
    showToast(err.message, 'error');
  } finally {
    hideLoading();
    state.isFormBusy = false;
  }
}

// ══════════════════════════════════════════════════════════════
// COPY TO CLIPBOARD
// ══════════════════════════════════════════════════════════════

function initCopyButtons() {
  document.addEventListener('click', async e => {
    const btn = e.target.closest('.copy-btn');
    if (!btn) return;

    const targetId = btn.dataset.target;
    const target   = document.getElementById(targetId);
    if (!target) return;

    const text = target.innerText || target.textContent;
    try {
      await navigator.clipboard.writeText(text);
      const originalText = btn.textContent;
      btn.textContent = '✅ Copied!';
      setTimeout(() => { btn.textContent = originalText; }, 2000);
    } catch (_) {
      showToast('Could not copy to clipboard.', 'error');
    }
  });
}

// ══════════════════════════════════════════════════════════════
// MARKDOWN RENDERER (lightweight, no dependencies)
// ══════════════════════════════════════════════════════════════

/**
 * Convert a small subset of Markdown to HTML.
 * Handles: headings (# ## ###), bold (**), italic (*), code (`),
 *          bullet lists (- / *), numbered lists (1. 2.), and line breaks.
 *
 * @param {string} text
 * @returns {string} HTML string
 */
function renderMarkdown(text) {
  if (!text) return '';

  // Escape HTML entities to prevent XSS before we add our own safe tags
  let html = escapeHtml(text);

  // Headings
  html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
  html = html.replace(/^## (.+)$/gm,  '<h2>$1</h2>');
  html = html.replace(/^# (.+)$/gm,   '<h1>$1</h1>');

  // Bold and italic
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/\*(.+?)\*/g,     '<em>$1</em>');
  html = html.replace(/__(.+?)__/g,     '<strong>$1</strong>');
  html = html.replace(/_(.+?)_/g,       '<em>$1</em>');

  // Inline code
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

  // Bullet lists (- or *)
  html = html.replace(/^[\-\*] (.+)$/gm, '<li>$1</li>');
  html = html.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');

  // Numbered lists
  html = html.replace(/^\d+\. (.+)$/gm, '<li>$1</li>');

  // Paragraph breaks (double newline → paragraph wrap)
  html = html
    .split(/\n{2,}/)
    .map(block => {
      block = block.trim();
      if (!block) return '';
      // Don't wrap block-level elements in <p>
      if (/^<(h[1-6]|ul|ol|li)/.test(block)) return block;
      return `<p>${block.replace(/\n/g, '<br>')}</p>`;
    })
    .join('\n');

  return html;
}

/**
 * Escape HTML special characters.
 * @param {string} text
 * @returns {string}
 */
function escapeHtml(text) {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

// ══════════════════════════════════════════════════════════════
// UI UTILITIES
// ══════════════════════════════════════════════════════════════

/**
 * Show the loading overlay with a custom message.
 * @param {string} [message='Generating response…']
 */
function showLoading(message = 'Generating response…') {
  const overlay = dom.loadingOverlay();
  const text    = dom.loadingText();
  if (!overlay) return;
  if (text) text.textContent = message;
  overlay.hidden = false;
}

/** Hide the loading overlay. */
function hideLoading() {
  const overlay = dom.loadingOverlay();
  if (overlay) overlay.hidden = true;
}

/**
 * Show a temporary toast notification.
 * @param {string} message
 * @param {'success'|'error'|'info'} [type='info']
 * @param {number} [duration=3500] - ms before auto-dismiss
 */
function showToast(message, type = 'info', duration = 3500) {
  const toast = dom.toast();
  if (!toast) return;

  toast.textContent = message;
  toast.className = `toast toast--${type}`;
  toast.hidden = false;

  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => {
    toast.hidden = true;
  }, duration);
}
