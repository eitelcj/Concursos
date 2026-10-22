import { patch, post } from '../api.js';
import { $, esc, safeUrl, toast } from '../dom.js';
import { STATUS_LABELS, dateTime, period, plural, salary } from '../format.js';
import { icon } from '../icons.js';
import { state } from '../state.js';
import { isFavorite, toggleLocalFavorite } from '../favorites.js';
import { openEditor } from './editor.js';

let root;
let refresh = async () => {};

export function mount(container, onRefresh) {
  root = container;
  refresh = onRefresh;
  root.innerHTML = `
    <div class="stats" aria-label="Resumo">
      <div class="stat is-open"><span>Abertos comprovados</span><strong id="countOpen">0</strong></div>
      <div class="stat is-due"><span>Encerram em 7 dias</span><strong id="countDue">0</strong></div>
      <div class="stat"><span>A conferir</span><strong id="countPending">0</strong></div>
    </div>
    <div class="toolbar">
      <div class="toolbar-row">
        <div class="search">
          ${icon('search')}
          <label class="sr-only" for="search">Buscar</label>
          <input class="input" type="search" id="search" placeholder="Buscar cargo, órgão ou cidade" autocomplete="off">
        </div>
        <button class="btn admin-only" id="scanBtn" type="button">${icon('refresh')}<span>Verificar agora</span></button>
        <button class="btn btn-primary admin-only" id="addBtn" type="button">${icon('plus')}<span>Concurso</span></button>
      </div>
      <div class="filters">
        <label class="sr-only" for="status">Situação</label>
        <select class="select" id="status">
          <option value="all">Todas as situações</option>
          <option value="open">Inscrições abertas</option>
          <option value="upcoming">Inscrições em breve</option>
          <option value="verify">A conferir</option>
          <option value="closed">Encerrados</option>
          <option value="favorite">Favoritos</option>
        </select>
        <label class="sr-only" for="region">Região</label>
        <select class="select" id="region">
          <option value="all">Todas as regiões</option>
          <option value="sp">Prova ou trabalho em SP</option>
          <option value="national">Nacional</option>
        </select>
        <label class="chip-check"><input type="checkbox" id="salary"> R$ 7 mil+ comprovado</label>
      </div>
      <div class="section-head">
        <p class="scan-line">${icon('clock')}<span id="latestScan">Nenhuma varredura ainda</span></p>
        <p class="result-count" id="resultCount" aria-live="polite"></p>
      </div>
    </div>
    <div id="items" class="items" aria-busy="true">
      <div class="skeleton"></div><div class="skeleton"></div>
    </div>
    <p class="muted">Somente fontes oficiais. Datas e salários sem prova documental aparecem como “a confirmar”.</p>`;

  for (const id of ['search', 'status', 'region', 'salary']) {
    $(`#${id}`, root).addEventListener(id === 'search' ? 'input' : 'change', render);
  }
  $('#scanBtn', root).addEventListener('click', scan);
  $('#addBtn', root).addEventListener('click', () => openEditor(null, refresh));
  $('#items', root).addEventListener('click', onAction);
}

function facts(item) {
  const fact = (label, value, extra = '') =>
    `<div><dt>${label}</dt><dd class="${value ? extra : 'pending'}">${esc(value || 'A confirmar')}</dd></div>`;
  const verified = item.document_verified;
  return `<dl class="facts">
    ${fact('Salário do cargo', salary(item), item.salary_highlight ? 'highlight' : '')}
    ${fact('Inscrições', verified ? period(item.registration_start, item.registration_end) : '')}
    ${fact('Prova', verified ? item.exam_cities : '')}
    ${fact('Lotação', verified ? item.work_cities : '')}
  </dl>`;
}

function card(item) {
  const status = STATUS_LABELS[item.status] || item.status;
  const due = item.status === 'open' && item.days_left != null
    ? `<span class="badge badge-verify">${icon('clock')}${item.days_left === 0 ? 'Último dia' : `Encerra em ${plural(item.days_left, 'dia', 'dias')}`}</span>`
    : '';
  const proof = item.document_verified
    ? `<span class="badge badge-ok">${icon('check')}Edital validado</span>`
    : '<span class="badge">Sem prova documental</span>';
  const links = [
    item.notice_url && `<a class="link-out" href="${safeUrl(item.notice_url)}" target="_blank" rel="noopener noreferrer">${icon('file')}Edital</a>`,
    item.official_url && `<a class="link-out" href="${safeUrl(item.official_url)}" target="_blank" rel="noopener noreferrer">${icon('external')}Site oficial</a>`,
    item.status === 'open' && item.apply_url && item.document_verified &&
      `<a class="btn btn-primary btn-sm" href="${safeUrl(item.apply_url)}" target="_blank" rel="noopener noreferrer">Inscrever-se ${icon('external')}</a>`,
  ].filter(Boolean).join('');
  const excerpt = (item.proof?.role_excerpt || '').slice(0, 280);
  const audit = item.proof
    ? `Edital ${esc(item.proof.sha256.slice(0, 16))}… verificado em ${esc(dateTime(item.proof.checked_at))}`
    : 'Edital ainda não verificado';
  return `<article class="opp" data-status="${esc(item.status)}" data-id="${item.id}">
    <div class="opp-head">
      <div>
        <div class="badges"><span class="badge badge-${esc(item.status)}">${esc(status)}</span>${due}${proof}${item.applied ? `<span class="badge badge-info">${icon('check')}Inscrito</span>` : ''}</div>
        <h3 class="opp-title">${esc(item.title)}</h3>
        <p class="opp-sub">${esc(item.agency || item.source || 'Órgão não informado')} · ${esc(item.position || 'Cargo de TI a especificar')}</p>
      </div>
      <button class="icon-btn" type="button" data-action="favorite" aria-pressed="${isFavorite(item) ? 'true' : 'false'}" aria-label="${isFavorite(item) ? 'Remover dos favoritos' : 'Favoritar'}">${icon('star')}</button>
    </div>
    ${facts(item)}
    <div class="opp-foot">
      <div class="opp-links">${links || '<span class="muted">Sem links oficiais</span>'}</div>
      <div class="opp-admin admin-only">
        <button class="btn btn-sm" type="button" data-action="edit">${icon('edit')}Editar</button>
        <button class="btn btn-sm" type="button" data-action="verify">${icon('shield')}${item.document_verified ? 'Revalidar' : 'Validar edital'}</button>
        <button class="btn btn-sm" type="button" data-action="applied">${item.applied ? 'Desmarcar inscrição' : 'Marcar inscrição'}</button>
      </div>
    </div>
    <details>
      <summary>Observações e auditoria</summary>
      ${item.notes ? `<p>${esc(item.notes)}</p>` : ''}
      <p class="muted">Origem: ${esc(item.source || '—')} · ${audit}</p>
      ${excerpt ? `<p class="muted">Trecho do edital: “${esc(excerpt)}”</p>` : ''}
    </details>
  </article>`;
}

export function render() {
  if (!root) return;
  const visible = state.items.filter((item) => !item.dismissed);
  $('#countOpen', root).textContent = visible.filter((i) => i.status === 'open').length;
  $('#countDue', root).textContent = visible.filter((i) => i.status === 'open' && i.days_left != null && i.days_left <= 7).length;
  $('#countPending', root).textContent = visible.filter((i) => !i.document_verified).length;

  const query = $('#search', root).value.trim().toLocaleLowerCase('pt-BR');
  const status = $('#status', root).value;
  const region = $('#region', root).value;
  const rich = $('#salary', root).checked;
  const list = visible.filter((i) =>
    (status === 'all' || (status === 'favorite' ? isFavorite(i) : i.status === status)) &&
    (region === 'all' || (region === 'sp' ? i.eligible_sp : i.national)) &&
    (!rich || i.salary_highlight) &&
    (!query || [i.title, i.agency, i.position, i.work_cities, i.exam_cities].join(' ').toLocaleLowerCase('pt-BR').includes(query)));

  const items = $('#items', root);
  items.setAttribute('aria-busy', 'false');
  $('#resultCount', root).textContent = state.loaded ? plural(list.length, 'concurso', 'concursos') : '';
  items.innerHTML = list.length
    ? list.map(card).join('')
    : `<div class="empty">${icon('inbox')}<strong>Nenhum concurso com estes filtros</strong><span>Limpe a busca ou veja a aba Fontes para conferir a cobertura.</span></div>`;

  const health = state.sources.health || [];
  const failed = health.filter((h) => h.state === 'failed' || h.state === 'blocked').length;
  const latest = [...health].sort((a, b) => String(b.started_at).localeCompare(String(a.started_at)))[0];
  $('#latestScan', root).textContent = latest
    ? `Última varredura: ${dateTime(latest.started_at)}${failed ? ` · ${plural(failed, 'fonte com problema', 'fontes com problema')}` : ''}`
    : 'Nenhuma varredura ainda';
}

async function onAction(event) {
  const button = event.target.closest('[data-action]');
  if (!button) return;
  const id = Number(button.closest('[data-id]').dataset.id);
  const item = state.items.find((i) => i.id === id);
  if (!item) return;
  try {
    switch (button.dataset.action) {
      case 'favorite':
        if (!state.admin) {
          toggleLocalFavorite(id);
          render();
          return;
        }
        await patch(`/api/opportunities/${id}`, { favorite: item.favorite ? 0 : 1 });
        break;
      case 'applied':
        await patch(`/api/opportunities/${id}`, { applied: item.applied ? 0 : 1 });
        break;
      case 'edit':
        openEditor(item, refresh);
        return;
      case 'verify':
        toast('Conferindo documento, cargo, salário e datas…');
        await post(`/api/opportunities/${id}/verify`);
        toast('Edital verificado e registrado.');
        break;
      default:
        return;
    }
    await refresh();
  } catch (error) {
    toast(error.message);
  }
}

async function scan() {
  const button = $('#scanBtn', root);
  button.disabled = true;
  try {
    await post('/api/scan');
    toast('Varredura iniciada. Acompanhe em Fontes.');
    location.hash = '#fontes';
    setTimeout(refresh, 4000);
  } catch (error) {
    toast(error.message);
  } finally {
    button.disabled = false;
  }
}
