import { api } from '../api.js';
import { $, toast } from '../dom.js';

const TEXT = [
  ['title', 'Nome do concurso', 'wide', 'text', true],
  ['agency', 'Órgão', '', 'text'],
  ['position', 'Cargo específico de TI', '', 'text', true],
  ['salary_min', 'Salário mínimo do cargo', '', 'number'],
  ['salary_max', 'Salário máximo do cargo', '', 'number'],
  ['registration_start', 'Início das inscrições', '', 'date'],
  ['registration_end', 'Fim das inscrições', '', 'date'],
  ['exam_date', 'Data da prova', '', 'date'],
  ['state', 'UF de trabalho', '', 'text'],
  ['exam_cities', 'Local da prova', '', 'text'],
  ['work_cities', 'Local de trabalho', '', 'text'],
  ['official_url', 'Página oficial', 'wide', 'url', true],
  ['notice_url', 'Edital oficial (link direto do documento)', 'wide', 'url', true],
  ['apply_url', 'Página de inscrição', 'wide', 'url'],
];
const CHECKS = [
  ['exam_in_sp', 'Prova em SP'],
  ['work_in_sp', 'Trabalho em SP'],
  ['national', 'Nacional'],
];

let current = null;
let done = async () => {};

function build(dialog) {
  dialog.innerHTML = `<form method="dialog" id="editForm">
    <div class="dialog-head"><h2 id="editorTitle">Concurso</h2><button class="btn btn-ghost" type="button" data-close>Fechar</button></div>
    <div class="dialog-body">
      ${TEXT.map(([name, label, cls, type, required]) => `<label class="field ${cls}">${label}
        <input class="input" name="${name}" type="${type}" ${type === 'number' ? 'step="0.01" min="0"' : ''} ${required ? 'required' : ''}></label>`).join('')}
      <div class="wide checks">${CHECKS.map(([name, label]) => `<label class="check"><input type="checkbox" name="${name}"> ${label}</label>`).join('')}</div>
      <label class="field wide">Observações<textarea class="textarea" name="notes" rows="3"></textarea></label>
      <p class="wide muted">Salvar não confirma nada: use “Validar edital” para conferir os dados no documento oficial.</p>
      <p class="wide form-error" id="editError" role="alert"></p>
    </div>
    <div class="dialog-foot"><button class="btn" type="button" data-close>Cancelar</button><button class="btn btn-primary" type="submit">Salvar</button></div>
  </form>`;
  dialog.addEventListener('click', (event) => {
    if (event.target.closest('[data-close]') || event.target === dialog) dialog.close();
  });
  $('#editForm', dialog).addEventListener('submit', save);
}

export function openEditor(item, onSaved) {
  const dialog = $('#editor');
  if (!dialog.firstChild) build(dialog);
  current = item;
  done = onSaved;
  const form = $('#editForm', dialog);
  form.reset();
  $('#editorTitle', dialog).textContent = item ? 'Editar concurso' : 'Adicionar concurso';
  $('#editError', dialog).textContent = '';
  if (item) {
    for (const [name] of TEXT) form.elements[name].value = item[name] ?? '';
    for (const [name] of CHECKS) form.elements[name].checked = Boolean(item[name]);
    form.elements.notes.value = item.notes ?? '';
  }
  dialog.showModal();
  form.elements.title.focus();
}

async function save(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const payload = {};
  for (const [name, , , type] of TEXT) {
    const value = form.elements[name].value.trim();
    payload[name] = type === 'number' ? (value === '' ? null : Number(value)) : value || null;
  }
  for (const [name] of CHECKS) payload[name] = form.elements[name].checked ? 1 : 0;
  payload.notes = form.elements.notes.value.trim() || null;
  try {
    await api(current ? `/api/opportunities/${current.id}` : '/api/opportunities', {
      method: current ? 'PATCH' : 'POST',
      body: JSON.stringify(payload),
    });
    $('#editor').close();
    toast('Salvo. Use “Validar edital” para confirmar os dados.');
    await done();
  } catch (error) {
    $('#editError').textContent = error.message;
  }
}
