import { post } from '../api.js';
import { $, toast } from '../dom.js';
import { icon } from '../icons.js';
import { state } from '../state.js';
import * as theme from '../theme.js';

let root;

export function mount(container) {
  root = container;
  root.innerHTML = `
    <div class="settings-grid">
      <section class="panel">
        <h3>Aparência</h3>
        <p class="muted">Escolha o tema claro ou escuro. “Automático” segue o tema do seu dispositivo.</p>
        <div class="segmented" role="group" aria-label="Tema" id="themeChoice">
          <button type="button" data-theme-choice="light">${icon('sun')}Claro</button>
          <button type="button" data-theme-choice="dark">${icon('moon')}Escuro</button>
          <button type="button" data-theme-choice="auto">${icon('monitor')}Automático</button>
        </div>
      </section>
      <section class="panel" id="mfaPanel">
        <h3>Verificação em duas etapas (MFA)</h3>
        <p class="muted" id="mfaStatus"></p>
        <form id="mfaSetupForm" class="form-grid">
          <label class="field">Confirme sua senha<input class="input" type="password" id="mfaPassword" autocomplete="current-password" required></label>
          <div class="form-actions"><button class="btn btn-primary" type="submit">${icon('shield')}Configurar aplicativo autenticador</button></div>
        </form>
        <div id="mfaQr" class="qr hidden">
          <img id="qrImage" alt="QR Code para o aplicativo autenticador">
          <p class="muted">Ou digite a chave manualmente: <code id="manualSecret"></code></p>
          <form id="mfaConfirmForm" class="form-grid">
            <label class="field">Código de 6 dígitos do aplicativo<input class="input" required id="confirmCode" inputmode="numeric" maxlength="6" placeholder="000000"></label>
            <div class="form-actions"><button class="btn btn-primary" type="submit">Ativar MFA</button></div>
          </form>
        </div>
        <div id="recovery" class="hidden">
          <p><strong>Guarde estes códigos de recuperação agora.</strong> Eles aparecem só uma vez.</p>
          <pre class="codes" id="recoveryCodes"></pre>
        </div>
        <form id="mfaDisableForm" class="form-grid hidden">
          <label class="field">Senha<input class="input" id="disablePassword" type="password" autocomplete="current-password" required></label>
          <label class="field">Código do aplicativo ou de recuperação<input class="input" id="disableCode" required></label>
          <div class="form-actions"><button class="btn btn-danger" type="submit">Desativar MFA</button></div>
        </form>
      </section>
    </div>`;

  theme.onChange((_, pref) => {
    for (const button of root.querySelectorAll('[data-theme-choice]')) {
      button.setAttribute('aria-pressed', String(button.dataset.themeChoice === pref));
    }
  });
  $('#themeChoice', root).addEventListener('click', (event) => {
    const button = event.target.closest('[data-theme-choice]');
    if (button) theme.setPreference(button.dataset.themeChoice);
  });
  $('#mfaSetupForm', root).addEventListener('submit', setup);
  $('#mfaConfirmForm', root).addEventListener('submit', confirm);
  $('#mfaDisableForm', root).addEventListener('submit', disable);
}

export function render() {
  if (!root) return;
  $('#mfaStatus', root).textContent = state.mfa
    ? 'MFA ativo: o código do aplicativo é pedido a cada login.'
    : 'MFA desligado. Recomendado se o radar estiver acessível pela internet.';
  $('#mfaSetupForm', root).classList.toggle('hidden', state.mfa);
  $('#mfaDisableForm', root).classList.toggle('hidden', !state.mfa);
}

async function setup(event) {
  event.preventDefault();
  try {
    const result = await post('/api/auth/mfa/setup', { password: $('#mfaPassword', root).value });
    $('#qrImage', root).src = result.qr;
    $('#manualSecret', root).textContent = result.secret;
    $('#mfaQr', root).classList.remove('hidden');
    $('#mfaSetupForm', root).classList.add('hidden');
  } catch (error) {
    toast(error.message);
  }
}

async function confirm(event) {
  event.preventDefault();
  try {
    const result = await post('/api/auth/mfa/confirm', { code: $('#confirmCode', root).value });
    state.mfa = true;
    $('#mfaQr', root).classList.add('hidden');
    $('#recoveryCodes', root).textContent = result.recovery_codes.join('\n');
    $('#recovery', root).classList.remove('hidden');
    render();
    toast('MFA ativado. Guarde os códigos de recuperação.');
  } catch (error) {
    toast(error.message);
  }
}

async function disable(event) {
  event.preventDefault();
  if (!window.confirm('Desativar a verificação em duas etapas?')) return;
  try {
    await post('/api/auth/mfa/disable', { password: $('#disablePassword', root).value, code: $('#disableCode', root).value });
    state.mfa = false;
    $('#recovery', root).classList.add('hidden');
    render();
    toast('MFA desativado.');
  } catch (error) {
    toast(error.message);
  }
}
