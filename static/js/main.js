// Entry point: authentication, navigation (#hash routes), data loading and periodic refresh.
import { ApiError, api, post, setCsrf } from './api.js';
import { $, $$, esc, toast } from './dom.js';
import { icon } from './icons.js';
import { state } from './state.js';
import * as theme from './theme.js';
import * as alertsView from './views/alerts.js';
import * as opportunitiesView from './views/opportunities.js';
import * as settingsView from './views/settings.js';
import * as sourcesView from './views/sources.js';

const ROUTES = [
  { id: 'concursos', label: 'Concursos', icon: 'radar', view: opportunitiesView },
  { id: 'alertas', label: 'Alertas', icon: 'bell', view: alertsView },
  { id: 'fontes', label: 'Fontes', icon: 'database', view: sourcesView },
  { id: 'configuracoes', label: 'Configurações', icon: 'settings', view: settingsView },
];

function currentRoute() {
  const id = location.hash.replace('#', '');
  return ROUTES.find((r) => r.id === id) || ROUTES[0];
}

function navigate() {
  const route = currentRoute();
  for (const r of ROUTES) $(`#view-${r.id}`).classList.toggle('hidden', r !== route);
  for (const link of $$('.nav-link')) {
    if (link.dataset.route === route.id) link.setAttribute('aria-current', 'page');
    else link.removeAttribute('aria-current');
  }
  $('#pageTitle').textContent = route.label;
  document.title = `${route.label} · Radar Public Sector`;
}

function buildNav() {
  $('#nav').innerHTML = ROUTES.map(
    (r) => `<a class="nav-link" href="#${r.id}" data-route="${r.id}">${icon(r.icon)}<span>${esc(r.label)}</span></a>`,
  ).join('');
}

function showApp(authenticated) {
  state.authenticated = authenticated;
  $('#appView').classList.toggle('hidden', !authenticated);
  $('#loginView').classList.toggle('hidden', authenticated);
}

export async function loadAll() {
  try {
    const [opportunities, alerts, sources, candidates] = await Promise.all([
      api('/api/opportunities'),
      api('/api/alerts'),
      api('/api/sources'),
      api('/api/candidates'),
    ]);
    state.items = opportunities.items;
    state.alerts = alerts.items;
    state.sources = sources;
    state.candidates = candidates.items;
    state.loaded = true;
    for (const r of ROUTES) r.view.render();
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return showApp(false);
    toast(error.message);
  }
}

async function login(event) {
  event.preventDefault();
  const form = event.currentTarget;
  $('#loginError').textContent = '';
  try {
    const result = await post('/api/auth/login', { password: form.elements.password.value, code: form.elements.code.value });
    if (result.mfa_required) {
      $('#otpField').classList.remove('hidden');
      form.elements.code.required = true;
      form.elements.code.focus();
      return;
    }
    setCsrf(result.csrf);
    state.mfa = result.mfa_enabled;
    form.reset();
    $('#otpField').classList.add('hidden');
    showApp(true);
    await loadAll();
  } catch (error) {
    $('#loginError').textContent = error.message;
  }
}

async function logout() {
  try {
    await post('/api/auth/logout');
  } finally {
    setCsrf('');
    showApp(false);
    $('#loginForm').reset();
    $('#otpField').classList.add('hidden');
  }
}

async function init() {
  buildNav();
  for (const r of ROUTES) r.view.mount($(`#view-${r.id}`), loadAll);
  theme.bindToggle($('#themeToggle'));
  $('#logoutBtn').querySelector('[data-icon]').outerHTML = icon('logout');
  $('#loginForm').addEventListener('submit', login);
  $('#logoutBtn').addEventListener('click', logout);
  window.addEventListener('hashchange', navigate);
  window.addEventListener('scroll', () => $('#topbar').classList.toggle('scrolled', window.scrollY > 4), { passive: true });
  navigate();
  try {
    const status = await api('/api/auth/status');
    state.mfa = status.mfa_enabled;
    setCsrf(status.csrf);
    showApp(status.authenticated);
    if (status.authenticated) await loadAll();
  } catch (error) {
    showApp(false);
    toast(error.message);
  }
  setInterval(() => {
    if (!document.hidden && state.authenticated) loadAll();
  }, 90_000);
}

init();
