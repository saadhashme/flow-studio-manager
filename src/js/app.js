// app.js - UI Controller & State Management for Flow Studio Manager

const audioContext = (typeof window !== 'undefined' && (window.AudioContext || window.webkitAudioContext)) ? new (window.AudioContext || window.webkitAudioContext)() : null;

function playChime(type = 'switch') {
  if (!state.settings.audioAlerts || !audioContext) return;
  try {
    const osc = audioContext.createOscillator();
    const gain = audioContext.createGain();
    osc.connect(gain);
    gain.connect(audioContext.destination);

    if (type === 'switch') {
      osc.frequency.setValueAtTime(523.25, audioContext.currentTime);
      osc.frequency.exponentialRampToValueAtTime(659.25, audioContext.currentTime + 0.15);
      gain.gain.setValueAtTime(0.08, audioContext.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, audioContext.currentTime + 0.25);
      osc.start();
      osc.stop(audioContext.currentTime + 0.25);
    } else if (type === 'warning') {
      osc.frequency.setValueAtTime(440, audioContext.currentTime);
      osc.frequency.exponentialRampToValueAtTime(330, audioContext.currentTime + 0.2);
      gain.gain.setValueAtTime(0.1, audioContext.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, audioContext.currentTime + 0.3);
      osc.start();
      osc.stop(audioContext.currentTime + 0.3);
    } else if (type === 'credit') {
      osc.frequency.setValueAtTime(880, audioContext.currentTime);
      gain.gain.setValueAtTime(0.05, audioContext.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, audioContext.currentTime + 0.12);
      osc.start();
      osc.stop(audioContext.currentTime + 0.12);
    }
  } catch (e) {}
}

const state = {
  accounts: [],
  activeAccountId: null,
  activeFilter: 'all',
  settings: {
    autoSwitch: true,
    minCreditsForSwitch: 15,
    prioritizePro: true,
    audioAlerts: true
  },
  discoveredProfiles: []
};

const el = {
  topBar: document.getElementById('top-bar'),
  activeAvatar: document.getElementById('active-avatar'),
  activeName: document.getElementById('active-name'),
  activeEmail: document.getElementById('active-email'),
  activePlanBadge: document.getElementById('active-plan-badge'),
  activeCreditsNum: document.getElementById('active-credits-num'),
  activeCreditProgress: document.getElementById('active-credit-progress'),
  creditClipsEstimate: document.getElementById('credit-clips-estimate'),
  readyAccountsTag: document.getElementById('ready-accounts-tag'),
  
  btnNextAccount: document.getElementById('btn-next-account'),
  btnRefreshCredits: document.getElementById('btn-refresh-credits'),
  btnNavBack: document.getElementById('btn-nav-back'),
  btnNavForward: document.getElementById('btn-nav-forward'),
  btnNavReload: document.getElementById('btn-nav-reload'),
  btnNavHome: document.getElementById('btn-nav-home'),
  btnLoginActive: document.getElementById('btn-login-active'),
  btnCookiesActive: document.getElementById('btn-cookies-active'),
  btnOpenSettings: document.getElementById('btn-open-settings'),

  statTotalCredits: document.getElementById('stat-total-credits'),
  statReadyCount: document.getElementById('stat-ready-count'),
  statPoolProgress: document.getElementById('stat-pool-progress'),
  statExhaustedTag: document.getElementById('stat-exhausted-tag'),
  toggleAutoSwitch: document.getElementById('toggle-auto-switch'),
  
  countAll: document.getElementById('count-all'),
  countPro: document.getElementById('count-pro'),
  countFree: document.getElementById('count-free'),
  countReady: document.getElementById('count-ready'),
  filterTabs: document.querySelectorAll('.filter-tab'),

  accountsList: document.getElementById('accounts-list'),
  flowWorkspace: document.getElementById('flow-workspace'),
  flowPlaceholder: document.getElementById('flow-placeholder'),
  
  btnImportChrome: document.getElementById('btn-import-chrome'),
  btnEmptyImport: document.getElementById('btn-empty-import'),
  chromeSubtext: document.getElementById('chrome-subtext'),
  btnAddAccountTop: document.getElementById('btn-add-account-top'),
  btnEmptyAdd: document.getElementById('btn-empty-add'),
  resetTimer: document.getElementById('reset-timer'),
  btnAuthorLink: document.getElementById('btn-author-link'),

  modalAccount: document.getElementById('modal-account'),
  modalAccountTitle: document.getElementById('modal-account-title'),
  formAccount: document.getElementById('form-account'),
  inputAccountId: document.getElementById('input-account-id'),
  inputAccountName: document.getElementById('input-account-name'),
  inputAccountEmail: document.getElementById('input-account-email'),
  selectAccountType: document.getElementById('select-account-type'),
  inputAccountCredits: document.getElementById('input-account-credits'),
  btnCloseAccountModal: document.getElementById('btn-close-account-modal'),
  btnCancelAccount: document.getElementById('btn-cancel-account'),

  modalChromeImport: document.getElementById('modal-chrome-import'),
  chromeDetectedCount: document.getElementById('chrome-detected-count'),
  chromeProfilesList: document.getElementById('chrome-profiles-list'),
  chkSelectAllProfiles: document.getElementById('chk-select-all-profiles'),
  btnCloseChromeModal: document.getElementById('btn-close-chrome-modal'),
  btnCancelChrome: document.getElementById('btn-cancel-chrome'),
  btnConfirmImport: document.getElementById('btn-confirm-import'),

  modalSettings: document.getElementById('modal-settings'),
  settingAutoSwitch: document.getElementById('setting-auto-switch'),
  settingMinCredits: document.getElementById('setting-min-credits'),
  settingPrioritizePro: document.getElementById('setting-prioritize-pro'),
  settingAudioAlerts: document.getElementById('setting-audio-alerts'),
  btnCloseSettingsModal: document.getElementById('btn-close-settings-modal'),
  btnSaveSettings: document.getElementById('btn-save-settings'),

  modalCookies: document.getElementById('modal-cookies'),
  modalCookiesTitle: document.getElementById('modal-cookies-title'),
  modalCookiesSubtitle: document.getElementById('modal-cookies-subtitle'),
  inputCookieData: document.getElementById('input-cookie-data'),
  cookieCountBadge: document.getElementById('cookie-count-badge'),
  cookieTipText: document.getElementById('cookie-tip-text'),
  btnPasteClipboardCookie: document.getElementById('btn-paste-clipboard-cookie'),
  btnClearCookie: document.getElementById('btn-clear-cookie'),
  btnCloseCookiesModal: document.getElementById('btn-close-cookies-modal'),
  btnCancelCookies: document.getElementById('btn-cancel-cookies'),
  btnApplyCookies: document.getElementById('btn-apply-cookies'),
  btnAccountModalCookies: document.getElementById('btn-account-modal-cookies'),

  toastContainer: document.getElementById('toast-container')
};

async function init() {
  bindEvents();
  await loadSettings();
  await loadAccounts();
  startResetCountdown();

  // Dynamic Chrome profile detection for sidebar
  if (window.flowAPI && typeof window.flowAPI.importChromeProfiles === 'function') {
    window.flowAPI.importChromeProfiles().then(res => {
      if (el.chromeSubtext) {
        if (res && res.success && Array.isArray(res.profiles) && res.profiles.length > 0) {
          el.chromeSubtext.textContent = `Detected ${res.profiles.length} profiles`;
        } else {
          el.chromeSubtext.textContent = 'Import profiles';
        }
      }
    }).catch(() => {
      if (el.chromeSubtext) el.chromeSubtext.textContent = 'Import profiles';
    });
  }

  if (window.flowAPI) {
    // Single credit update or full account update
    window.flowAPI.onCreditUpdate((data) => {
      handleAccountUpdatedFromIPC({
        accountId: data.accountId,
        account: { credits: data.credits },
        source: data.source
      });
    });

    window.flowAPI.onAccountUpdated((data) => {
      handleAccountUpdatedFromIPC(data);
    });

    window.flowAPI.onAccountSwitched((data) => {
      state.activeAccountId = data.accountId;
      updateActiveAccountDisplay();
      renderAccountsList();
      updatePoolStats();
      playChime('switch');
    });

    window.flowAPI.onNotification((data) => {
      showToast(data.message, data.level === 'warning' ? 'warning' : 'success');
      if (data.type === 'auto-switched') {
        playChime('switch');
      } else if (data.type === 'all-depleted') {
        playChime('warning');
      }
    });
  }
}

async function loadAccounts() {
  if (!window.flowAPI) return;
  const accounts = await window.flowAPI.getAccounts();
  state.accounts = accounts || [];

  if (state.accounts.length > 0) {
    el.flowPlaceholder.style.display = 'none';
    if (!state.activeAccountId) {
      const firstReady = state.accounts.find(a => (a.credits || 0) >= state.settings.minCreditsForSwitch) || state.accounts[0];
      switchAccount(firstReady.id);
    } else {
      updateActiveAccountDisplay();
    }
  } else {
    el.flowPlaceholder.style.display = 'flex';
    resetActiveAccountDisplay();
  }

  renderAccountsList();
  updatePoolStats();
}

async function loadSettings() {
  if (!window.flowAPI) return;
  const s = await window.flowAPI.getSettings();
  if (s) {
    state.settings = { ...state.settings, ...s };
    el.toggleAutoSwitch.checked = state.settings.autoSwitch;
    el.settingAutoSwitch.checked = state.settings.autoSwitch;
    el.settingMinCredits.value = state.settings.minCreditsForSwitch;
    el.settingPrioritizePro.checked = state.settings.prioritizePro;
    el.settingAudioAlerts.checked = state.settings.audioAlerts;
  }
}

async function switchAccount(accountId) {
  if (!window.flowAPI) return;
  state.activeAccountId = accountId;
  await window.flowAPI.switchAccount(accountId);
  el.flowPlaceholder.style.display = 'none';
  updateActiveAccountDisplay();
  renderAccountsList();
  updatePoolStats();
}

function switchToNextAccount() {
  const ready = getReadyAccounts();
  if (ready.length === 0) {
    showToast('No accounts currently have ≥ 15 credits remaining today.', 'warning');
    playChime('warning');
    return;
  }

  let next = null;
  const otherReady = ready.filter(a => a.id !== state.activeAccountId);
  if (otherReady.length > 0) {
    next = otherReady[0];
  } else {
    next = ready[0];
  }

  if (next) {
    switchAccount(next.id);
    const cr = typeof next.credits === 'number' ? next.credits.toLocaleString() : 'Syncing';
    showToast(`Switched to "${next.name}" (${cr} credits)`, 'success');
  }
}

function getReadyAccounts() {
  const min = state.settings.minCreditsForSwitch || 15;
  let ready = state.accounts.filter(a => (typeof a.credits === 'number' ? a.credits : 50) >= min);
  if (state.settings.prioritizePro) {
    ready.sort((a, b) => {
      if (a.type === 'pro' && b.type !== 'pro') return -1;
      if (b.type === 'pro' && a.type !== 'pro') return 1;
      return (b.credits || 0) - (a.credits || 0);
    });
  }
  return ready;
}

function handleAccountUpdatedFromIPC(data) {
  const acc = state.accounts.find(a => a.id === data.accountId);
  if (acc) {
    const oldCr = acc.credits;
    if (data.account) {
      Object.assign(acc, data.account);
    }
    
    if (state.activeAccountId === data.accountId) {
      updateActiveAccountDisplay();
      if (typeof acc.credits === 'number' && oldCr !== acc.credits) {
        playChime('credit');
        showToast(`${acc.name}: ${acc.credits.toLocaleString()} credits (${acc.type.toUpperCase()})`, 'success');
      }
    }
    renderAccountsList();
    updatePoolStats();
  }
}

function updateActiveAccountDisplay() {
  const acc = state.accounts.find(a => a.id === state.activeAccountId);
  if (!acc) {
    resetActiveAccountDisplay();
    return;
  }

  const initial = (acc.name || acc.email || '?').charAt(0).toUpperCase();
  el.activeAvatar.textContent = initial;
  el.activeName.textContent = acc.name || 'Account';
  el.activeEmail.textContent = acc.email || '';
  
  const isPro = acc.type === 'pro';
  el.activePlanBadge.textContent = isPro ? 'PRO' : 'FREE';
  el.activePlanBadge.className = `badge ${isPro ? 'badge-pro' : 'badge-free'} clickable`;
  el.activePlanBadge.title = `Plan: ${isPro ? 'Pro (Paid)' : 'Free'} - Click to toggle`;

  const credits = acc.credits;
  const maxCredits = acc.maxCredits || (isPro ? 1000 : 50);

  if (typeof credits === 'number') {
    el.activeCreditsNum.textContent = credits.toLocaleString();
    const pct = Math.min(100, Math.max(0, (credits / maxCredits) * 100));
    el.activeCreditProgress.style.width = pct + '%';
    
    const maxEl = document.querySelector('.credit-max');
    if (maxEl) {
      if (isPro) {
        maxEl.textContent = 'cr';
      } else {
        maxEl.textContent = '/ 50';
      }
    }

    el.activeCreditProgress.classList.remove('warning', 'danger');
    if (credits < 15) {
      el.activeCreditProgress.classList.add('danger');
    } else if (credits < 30 && !isPro) {
      el.activeCreditProgress.classList.add('warning');
    }

    const clips = Math.floor(credits / 15);
    if (clips > 0) {
      el.creditClipsEstimate.textContent = `~${clips} clips left (15 cr/clip)`;
      el.creditClipsEstimate.style.color = 'var(--accent-emerald)';
    } else {
      el.creditClipsEstimate.textContent = `0 clips left (needs ≥ 15 cr)`;
      el.creditClipsEstimate.style.color = 'var(--accent-rose)';
    }
  } else {
    el.activeCreditsNum.textContent = '--';
    el.activeCreditProgress.style.width = '20%';
    el.activeCreditProgress.classList.add('warning');
    el.creditClipsEstimate.textContent = 'Syncing with Google Flow...';
    el.creditClipsEstimate.style.color = 'var(--text-muted)';
  }
}

function resetActiveAccountDisplay() {
  el.activeAvatar.textContent = '?';
  el.activeName.textContent = 'No Account Selected';
  el.activeEmail.textContent = 'Add or import accounts';
  el.activeCreditsNum.textContent = '--';
  el.activeCreditProgress.style.width = '0%';
  el.creditClipsEstimate.textContent = '0 clips';
}

function updatePoolStats() {
  const total = state.accounts.length;
  let totalCredits = 0;
  let totalMaxCredits = 0;
  let readyCount = 0;
  let depletedCount = 0;
  let proCount = 0;
  let freeCount = 0;
  let proCredits = 0;
  let freeCredits = 0;

  for (const a of state.accounts) {
    const isPro = a.type === 'pro';
    const cr = typeof a.credits === 'number' ? a.credits : 0;
    const max = a.maxCredits || (isPro ? 1000 : 50);
    
    totalCredits += cr;
    totalMaxCredits += max;

    if (isPro) {
      proCount++;
      proCredits += cr;
    } else {
      freeCount++;
      freeCredits += cr;
    }

    if ((typeof a.credits === 'number' ? a.credits : 50) >= state.settings.minCreditsForSwitch) {
      readyCount++;
    } else {
      depletedCount++;
    }
  }

  // Display clean total available credits across pool
  el.statTotalCredits.textContent = `${totalCredits.toLocaleString()} cr`;
  el.statTotalCredits.title = `Pro: ${proCredits.toLocaleString()} cr | Free: ${freeCredits.toLocaleString()} cr`;
  el.statReadyCount.textContent = `${readyCount} / ${total}`;
  const poolPct = totalMaxCredits > 0 ? Math.min(100, (totalCredits / totalMaxCredits) * 100) : 0;
  el.statPoolProgress.style.width = `${poolPct}%`;
  el.statExhaustedTag.textContent = `${depletedCount} empty`;

  el.countAll.textContent = total;
  el.countPro.textContent = proCount;
  el.countFree.textContent = freeCount;
  el.countReady.textContent = readyCount;

  el.readyAccountsTag.textContent = `${readyCount} ready (Alt+N)`;
}

function renderAccountsList() {
  const filter = state.activeFilter;
  let filtered = state.accounts.filter(a => {
    if (filter === 'pro') return a.type === 'pro';
    if (filter === 'free') return a.type === 'free';
    if (filter === 'ready') return (typeof a.credits === 'number' ? a.credits : 50) >= state.settings.minCreditsForSwitch;
    return true;
  });

  el.accountsList.innerHTML = '';

  if (filtered.length === 0) {
    const emptyMsg = document.createElement('div');
    emptyMsg.style.padding = '20px 10px';
    emptyMsg.style.textAlign = 'center';
    emptyMsg.style.fontSize = '12px';
    emptyMsg.style.color = 'var(--text-muted)';
    emptyMsg.textContent = state.accounts.length === 0 ? 'No accounts added yet.' : 'No accounts match this filter.';
    el.accountsList.appendChild(emptyMsg);
    return;
  }

  filtered.forEach((acc) => {
    const card = document.createElement('div');
    const isActive = acc.id === state.activeAccountId;
    card.className = `account-card ${isActive ? 'active' : ''}`;
    
    const isPro = acc.type === 'pro';
    const credits = acc.credits;
    let creditClass = '';
    let creditsDisplay = '-- cr';

    if (typeof credits === 'number') {
      creditsDisplay = `${credits.toLocaleString()} cr`;
      if (credits < 15) creditClass = 'danger';
      else if (credits < 30 && !isPro) creditClass = 'warning';
    } else {
      creditClass = 'pending';
    }

    const initial = (acc.name || acc.email || '?').charAt(0).toUpperCase();

    card.innerHTML = `
      <div class="card-avatar ${isPro ? 'pro' : ''}">${initial}</div>
      <div class="card-info">
        <div class="card-name-row">
          <span class="card-name">${escapeHtml(acc.name || 'Account')}</span>
          <span class="badge ${isPro ? 'badge-pro' : 'badge-free'} clickable" title="Click to toggle Pro / Free">${isPro ? 'PRO' : 'FREE'}</span>
        </div>
        <div class="card-email">${escapeHtml(acc.email || '')}</div>
      </div>
      <div class="card-credits-pill ${creditClass}" title="Click to adjust credits manually">${creditsDisplay}</div>
      <button class="card-menu-btn" title="Account Options" data-id="${acc.id}">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
          <circle cx="12" cy="5" r="2"></circle>
          <circle cx="12" cy="12" r="2"></circle>
          <circle cx="12" cy="19" r="2"></circle>
        </svg>
      </button>
    `;

    // 1-Click Toggle Pro / Free
    const badgeEl = card.querySelector('.badge');
    badgeEl.addEventListener('click', async (e) => {
      e.stopPropagation();
      const newType = acc.type === 'pro' ? 'free' : 'pro';
      const newMax = newType === 'pro' ? Math.max(acc.credits || 0, 1000) : 50;
      acc.type = newType;
      acc.maxCredits = newMax;
      await window.flowAPI.updateAccount(acc.id, { type: newType, maxCredits: newMax });
      showToast(`"${acc.name}" changed to ${newType.toUpperCase()}`, 'success');
      if (state.activeAccountId === acc.id) updateActiveAccountDisplay();
      renderAccountsList();
      updatePoolStats();
    });

    // 1-Click Adjust Credits
    const pillEl = card.querySelector('.card-credits-pill');
    pillEl.addEventListener('click', async (e) => {
      e.stopPropagation();
      const input = prompt(`Enter current Flow credits for "${acc.name}":`, acc.credits !== null ? acc.credits : (acc.type === 'pro' ? 1000 : 50));
      if (input !== null) {
        const num = parseInt(input.replace(/,/g, '').trim(), 10);
        if (!isNaN(num) && num >= 0) {
          acc.credits = num;
          if (num > (acc.maxCredits || 50)) acc.maxCredits = num;
          await window.flowAPI.updateAccount(acc.id, { credits: num, maxCredits: acc.maxCredits });
          showToast(`Updated credits for "${acc.name}" to ${num.toLocaleString()}`, 'success');
          if (state.activeAccountId === acc.id) updateActiveAccountDisplay();
          renderAccountsList();
          updatePoolStats();
        }
      }
    });

    card.addEventListener('click', (e) => {
      if (e.target.closest('.card-menu-btn')) {
        e.stopPropagation();
        openAccountEdit(acc);
        return;
      }
      switchAccount(acc.id);
    });

    el.accountsList.appendChild(card);
  });
}

function closeAllModals() {
  el.modalAccount.classList.add('hidden');
  el.modalChromeImport.classList.add('hidden');
  el.modalSettings.classList.add('hidden');
  if (el.modalCookies) el.modalCookies.classList.add('hidden');
  if (window.flowAPI) {
    window.flowAPI.setFlowViewVisible(true);
  }
}

let cookieTargetAccountId = null;

function openCookieModal(accountId) {
  cookieTargetAccountId = accountId || state.activeAccountId;
  if (!cookieTargetAccountId) {
    showToast('Please select or add an account first.', 'warning');
    return;
  }

  const acc = state.accounts.find(a => a.id === cookieTargetAccountId);
  if (window.flowAPI) window.flowAPI.setFlowViewVisible(false);

  if (el.modalCookiesTitle) {
    el.modalCookiesTitle.textContent = `Paste Cookies: ${acc ? acc.name : 'Account'}`;
  }
  if (el.modalCookiesSubtitle) {
    el.modalCookiesSubtitle.textContent = `Inject Chrome session cookies directly into "${acc ? (acc.email || acc.name) : 'this account'}"`;
  }

  el.inputCookieData.value = '';
  updateCookiePreview();
  el.modalCookies.classList.remove('hidden');
  setTimeout(() => el.inputCookieData.focus(), 50);
}

function closeCookieModal() {
  closeAllModals();
}

function updateCookiePreview() {
  if (!el.inputCookieData) return;
  const raw = el.inputCookieData.value.trim();
  if (!raw) {
    el.cookieCountBadge.className = 'cookie-badge-info';
    el.cookieCountBadge.textContent = 'Ready to paste';
    el.cookieTipText.textContent = 'Paste JSON from Cookie-Editor or Header string';
    return;
  }

  // Check JSON format
  try {
    const parsed = JSON.parse(raw);
    const arr = Array.isArray(parsed) ? parsed : (Array.isArray(parsed.cookies) ? parsed.cookies : Object.keys(parsed));
    const googleTokens = arr.filter(c => {
      const name = typeof c === 'string' ? c : (c.name || '');
      return ['SID', 'HSID', 'SSID', 'APISID', 'SAPISID', '__Secure-1PSID', '__Secure-3PSID', 'NID'].includes(name);
    });
    el.cookieCountBadge.className = 'cookie-badge-success';
    el.cookieCountBadge.textContent = `✓ ${arr.length} cookies detected (${googleTokens.length} Google auth tokens)`;
    el.cookieTipText.textContent = 'Valid JSON format ready to apply!';
    return;
  } catch (e) {}

  // Check header string
  const pairs = raw.replace(/^Cookie:\s*/i, '').split(/[;\r\n]+/).map(s => s.trim()).filter(Boolean);
  if (pairs.length > 0 && pairs.some(p => p.includes('='))) {
    el.cookieCountBadge.className = 'cookie-badge-success';
    el.cookieCountBadge.textContent = `✓ ${pairs.length} cookie pairs detected`;
    el.cookieTipText.textContent = 'Header string format ready to apply!';
  } else {
    el.cookieCountBadge.className = 'cookie-badge-warning';
    el.cookieCountBadge.textContent = 'Format unrecognized';
    el.cookieTipText.textContent = 'Please paste a JSON array or name=value pairs';
  }
}

function openAccountEdit(acc) {
  if (window.flowAPI) window.flowAPI.setFlowViewVisible(false);
  el.modalAccountTitle.textContent = 'Edit Account';
  el.inputAccountId.value = acc.id;
  el.inputAccountName.value = acc.name || '';
  el.inputAccountEmail.value = acc.email || '';
  el.selectAccountType.value = acc.type || 'free';
  el.inputAccountCredits.value = typeof acc.credits === 'number' ? acc.credits : (acc.type === 'pro' ? 1000 : 50);
  
  let deleteBtn = document.getElementById('btn-delete-account');
  if (!deleteBtn) {
    deleteBtn = document.createElement('button');
    deleteBtn.id = 'btn-delete-account';
    deleteBtn.type = 'button';
    deleteBtn.className = 'btn';
    deleteBtn.style.background = 'rgba(239, 68, 68, 0.15)';
    deleteBtn.style.color = '#f87171';
    deleteBtn.style.border = '1px solid rgba(239, 68, 68, 0.3)';
    deleteBtn.style.marginRight = 'auto';
    deleteBtn.textContent = 'Delete';
    deleteBtn.addEventListener('click', async () => {
      if (confirm(`Remove account "${acc.name}"?`)) {
        await window.flowAPI.deleteAccount(acc.id);
        closeAllModals();
        await loadAccounts();
        showToast(`Account removed`, 'warning');
      }
    });
    el.formAccount.querySelector('.modal-footer').prepend(deleteBtn);
  } else {
    deleteBtn.style.display = 'block';
  }

  el.modalAccount.classList.remove('hidden');
}

function openAddAccountModal() {
  if (window.flowAPI) window.flowAPI.setFlowViewVisible(false);
  el.modalAccountTitle.textContent = 'Add Google Account';
  el.inputAccountId.value = '';
  el.inputAccountName.value = '';
  el.inputAccountEmail.value = '';
  el.selectAccountType.value = 'free';
  el.inputAccountCredits.value = 50;
  
  const deleteBtn = document.getElementById('btn-delete-account');
  if (deleteBtn) deleteBtn.style.display = 'none';

  el.modalAccount.classList.remove('hidden');
  el.inputAccountName.focus();
}

function closeAccountModal() {
  closeAllModals();
}

async function openChromeImportModal() {
  if (window.flowAPI) window.flowAPI.setFlowViewVisible(false);
  el.modalChromeImport.classList.remove('hidden');
  el.chromeDetectedCount.textContent = 'Scanning Chrome profiles...';
  el.chromeProfilesList.innerHTML = '<div style="padding: 24px; text-align: center; color: var(--text-muted);">Reading Chrome profiles...</div>';

  if (!window.flowAPI) return;
  try {
    const res = await window.flowAPI.importChromeProfiles();
    if (!res || !res.success) {
      el.chromeProfilesList.innerHTML = `<div style="padding: 24px; text-align: center; color: var(--accent-rose); line-height: 1.6;">${escapeHtml((res && res.message) || 'Chrome profile not found on this system.')}</div>`;
      el.chromeDetectedCount.textContent = '0 found';
      if (el.chromeSubtext) el.chromeSubtext.textContent = '0 profiles found';
      return;
    }

    state.discoveredProfiles = res.profiles || [];
    el.chromeDetectedCount.textContent = `${state.discoveredProfiles.length} profiles discovered`;
    if (el.chromeSubtext) {
      el.chromeSubtext.textContent = `Detected ${state.discoveredProfiles.length} profiles`;
    }
    renderChromeProfilesList();
  } catch (err) {
    el.chromeProfilesList.innerHTML = `<div style="padding: 24px; text-align: center; color: var(--accent-rose); line-height: 1.6;">${escapeHtml(err.message || 'Error scanning profiles')}</div>`;
    el.chromeDetectedCount.textContent = '0 found';
  }
}

function renderChromeProfilesList() {
  el.chromeProfilesList.innerHTML = '';
  if (state.discoveredProfiles.length === 0) {
    el.chromeProfilesList.innerHTML = '<div style="padding: 20px; text-align: center; color: var(--text-muted);">No profiles found in Chrome.</div>';
    return;
  }

  state.discoveredProfiles.forEach((prof, i) => {
    const row = document.createElement('label');
    row.className = `chrome-profile-item ${prof.isAlreadyAdded ? 'already-added' : ''}`;
    
    row.innerHTML = `
      <input type="checkbox" class="chk-chrome-item" data-index="${i}" ${prof.isAlreadyAdded ? 'disabled' : 'checked'}>
      <div class="chrome-item-info">
        <div class="chrome-item-name">${escapeHtml(prof.name || prof.chromeKey)}</div>
        <div class="chrome-item-email">${escapeHtml(prof.email || 'No email associated')}</div>
      </div>
      <div class="badge ${prof.isAlreadyAdded ? 'badge-free' : 'badge-pro'}">
        ${prof.isAlreadyAdded ? 'ALREADY ADDED' : prof.chromeKey}
      </div>
    `;

    el.chromeProfilesList.appendChild(row);
  });
}

async function confirmChromeImport() {
  const checkboxes = el.chromeProfilesList.querySelectorAll('.chk-chrome-item:checked');
  if (checkboxes.length === 0) {
    showToast('No profiles selected for import.', 'warning');
    return;
  }

  let importedCount = 0;
  for (const chk of checkboxes) {
    const idx = parseInt(chk.getAttribute('data-index'), 10);
    const prof = state.discoveredProfiles[idx];
    if (prof) {
      await window.flowAPI.addAccount({
        name: prof.name || prof.chromeKey,
        email: prof.email || '',
        type: 'free', // Defaults to Free until detected or user toggles
        credits: null, // Pending sync
        chromeProfile: prof.chromeKey
      });
      importedCount++;
    }
  }

  el.modalChromeImport.classList.add('hidden');
  await loadAccounts();
  showToast(`Imported ${importedCount} accounts!`, 'success');
  playChime('switch');
}

function getTimeUntilPacificMidnight() {
  const now = new Date();
  
  // Format current time in America/Los_Angeles (Google HQ Timezone for all quota resets)
  const formatter = new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/Los_Angeles',
    year: 'numeric',
    month: 'numeric',
    day: 'numeric',
    hour: 'numeric',
    minute: 'numeric',
    second: 'numeric',
    hour12: false
  });
  
  const parts = Object.fromEntries(formatter.formatToParts(now).map(p => [p.type, p.value]));
  const ptHour = parseInt(parts.hour, 10);
  const ptMinute = parseInt(parts.minute, 10);
  const ptSecond = parseInt(parts.second, 10);
  
  const secondsSincePtMidnight = (ptHour * 3600) + (ptMinute * 60) + ptSecond;
  const totalSecondsInDay = 86400;
  const secondsUntilMidnight = (totalSecondsInDay - secondsSincePtMidnight) % totalSecondsInDay;
  
  const hours = Math.floor(secondsUntilMidnight / 3600);
  const mins = Math.floor((secondsUntilMidnight % 3600) / 60);

  const resetDate = new Date(now.getTime() + secondsUntilMidnight * 1000);
  const localResetTime = resetDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  return { hours, mins, secondsUntilMidnight, localResetTime };
}

let lastResetDay = null;

function startResetCountdown() {
  function updateTimer() {
    const { hours, mins, secondsUntilMidnight, localResetTime } = getTimeUntilPacificMidnight();
    
    if (el.resetTimer) {
      el.resetTimer.textContent = `${hours}h ${mins}m (${localResetTime})`;
      if (el.resetTimer.parentElement) {
        el.resetTimer.parentElement.title = `Google Flow daily quota resets at Midnight Pacific Time (Google HQ), which is ${localResetTime} in your local time.`;
      }
    }

    // Auto-refresh credits on local app when daily reset boundary is crossed
    const now = new Date();
    const currentDay = now.getDate();
    if (secondsUntilMidnight < 90 && lastResetDay !== currentDay) {
      lastResetDay = currentDay;
      handleDailyResetTriggered();
    }
  }

  updateTimer();
  setInterval(updateTimer, 30000);
}

async function handleDailyResetTriggered() {
  console.log('[Daily Reset] Google Midnight Pacific reached -> Refreshing 50 credits on Free accounts');
  showToast('Google daily reset reached: Free credits refreshed to 50!', 'success');
  playChime('credit');

  for (const acc of state.accounts) {
    if (acc.type === 'free') {
      acc.credits = 50;
      acc.maxCredits = 50;
      acc.lastUpdated = Date.now();
      if (window.flowAPI) {
        await window.flowAPI.updateAccount(acc.id, { credits: 50, maxCredits: 50 });
      }
    }
  }

  updateActiveAccountDisplay();
  renderAccountsList();
  updatePoolStats();
}

function showToast(message, type = 'info') {
  const toast = document.createElement('div');
  toast.className = `toast ${type === 'success' ? 'toast-success' : type === 'warning' ? 'toast-warning' : ''}`;
  toast.textContent = message;
  el.toastContainer.appendChild(toast);

  setTimeout(() => {
    toast.style.transition = 'opacity 0.3s, transform 0.3s';
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(10px)';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

function bindEvents() {
  el.btnNextAccount.addEventListener('click', switchToNextAccount);
  
  window.addEventListener('keydown', (e) => {
    if (e.altKey && (e.key === 'n' || e.key === 'N')) {
      e.preventDefault();
      switchToNextAccount();
    }
  });

  // Top Bar Plan Badge Toggle
  el.activePlanBadge.addEventListener('click', async () => {
    const acc = state.accounts.find(a => a.id === state.activeAccountId);
    if (acc) {
      const newType = acc.type === 'pro' ? 'free' : 'pro';
      const newMax = newType === 'pro' ? Math.max(acc.credits || 0, 1000) : 50;
      acc.type = newType;
      acc.maxCredits = newMax;
      await window.flowAPI.updateAccount(acc.id, { type: newType, maxCredits: newMax });
      showToast(`"${acc.name}" set to ${newType.toUpperCase()}`, 'success');
      updateActiveAccountDisplay();
      renderAccountsList();
      updatePoolStats();
    }
  });

  el.btnRefreshCredits.addEventListener('click', () => {
    if (window.flowAPI) {
      window.flowAPI.refreshCurrentCredits();
      showToast('Scanning Google Flow for credits & plan...', 'info');
    }
  });

  el.btnNavBack.addEventListener('click', () => window.flowAPI && window.flowAPI.navigateFlow('back'));
  el.btnNavForward.addEventListener('click', () => window.flowAPI && window.flowAPI.navigateFlow('forward'));
  el.btnNavReload.addEventListener('click', () => window.flowAPI && window.flowAPI.navigateFlow('reload'));
  el.btnNavHome.addEventListener('click', () => window.flowAPI && window.flowAPI.navigateFlow('home'));

  el.btnLoginActive.addEventListener('click', () => {
    if (state.activeAccountId && window.flowAPI) {
      window.flowAPI.openLoginModal(state.activeAccountId);
    } else {
      showToast('Please select an account first.', 'warning');
    }
  });

  if (el.btnCookiesActive) {
    el.btnCookiesActive.addEventListener('click', () => {
      if (state.activeAccountId) {
        openCookieModal(state.activeAccountId);
      } else {
        showToast('Please select an account first.', 'warning');
      }
    });
  }

  if (el.btnAccountModalCookies) {
    el.btnAccountModalCookies.addEventListener('click', () => {
      const id = el.inputAccountId.value || state.activeAccountId;
      if (id) {
        closeAllModals();
        openCookieModal(id);
      } else {
        showToast('Please save the account first before pasting cookies.', 'info');
      }
    });
  }

  if (el.btnCloseCookiesModal) el.btnCloseCookiesModal.addEventListener('click', closeCookieModal);
  if (el.btnCancelCookies) el.btnCancelCookies.addEventListener('click', closeCookieModal);

  if (el.inputCookieData) {
    el.inputCookieData.addEventListener('input', updateCookiePreview);
  }

  if (el.btnClearCookie) {
    el.btnClearCookie.addEventListener('click', () => {
      el.inputCookieData.value = '';
      updateCookiePreview();
      el.inputCookieData.focus();
    });
  }

  if (el.btnPasteClipboardCookie) {
    el.btnPasteClipboardCookie.addEventListener('click', async () => {
      try {
        const text = await navigator.clipboard.readText();
        if (text) {
          el.inputCookieData.value = text;
          updateCookiePreview();
          showToast('Pasted cookies from clipboard!', 'info');
        } else {
          showToast('Clipboard is empty. Copy cookies first.', 'warning');
        }
      } catch (err) {
        showToast('Clipboard permission denied. Please press Ctrl+V directly.', 'warning');
      }
    });
  }

  if (el.btnApplyCookies) {
    el.btnApplyCookies.addEventListener('click', async () => {
      const cookieData = el.inputCookieData.value.trim();
      if (!cookieData) {
        showToast('Please paste cookie data first.', 'warning');
        return;
      }
      if (!cookieTargetAccountId) {
        showToast('No target account selected.', 'warning');
        return;
      }

      const btn = el.btnApplyCookies;
      const originalText = btn.innerHTML;
      btn.disabled = true;
      btn.innerHTML = '<span>Injecting cookies...</span>';

      try {
        const res = await window.flowAPI.importCookies(cookieTargetAccountId, cookieData);
        if (res && res.success) {
          showToast(`🍪 ${res.message}`, 'success');
          playChime('credit');

          // If this account wasn't active, switch to it now
          if (state.activeAccountId !== cookieTargetAccountId) {
            switchAccount(cookieTargetAccountId);
          }

          closeCookieModal();

          // After 3.5s, refresh credits from newly loaded session
          setTimeout(() => {
            if (window.flowAPI) window.flowAPI.refreshCurrentCredits();
          }, 3500);
        } else {
          showToast((res && res.message) || 'Failed to apply cookies. Please check format.', 'warning');
        }
      } catch (err) {
        showToast('Error applying cookies: ' + err.message, 'warning');
      } finally {
        btn.disabled = false;
        btn.innerHTML = originalText;
      }
    });
  }

  el.filterTabs.forEach(tab => {
    tab.addEventListener('click', () => {
      el.filterTabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      state.activeFilter = tab.getAttribute('data-filter');
      renderAccountsList();
    });
  });

  el.toggleAutoSwitch.addEventListener('change', (e) => {
    state.settings.autoSwitch = e.target.checked;
    if (window.flowAPI) {
      window.flowAPI.saveSettings(state.settings);
    }
    showToast(`Auto-Switch ${state.settings.autoSwitch ? 'Enabled' : 'Disabled'}`, 'info');
  });

  el.btnAddAccountTop.addEventListener('click', openAddAccountModal);
  el.btnEmptyAdd.addEventListener('click', openAddAccountModal);
  el.btnCloseAccountModal.addEventListener('click', closeAccountModal);
  el.btnCancelAccount.addEventListener('click', closeAccountModal);

  el.formAccount.addEventListener('submit', async (e) => {
    e.preventDefault();
    const id = el.inputAccountId.value;
    const type = el.selectAccountType.value;
    const cr = parseInt(el.inputAccountCredits.value, 10);
    const data = {
      name: el.inputAccountName.value.trim(),
      email: el.inputAccountEmail.value.trim(),
      type: type,
      credits: isNaN(cr) ? null : cr,
      maxCredits: type === 'pro' ? Math.max(isNaN(cr) ? 1000 : cr, 1000) : 50
    };

    if (id) {
      await window.flowAPI.updateAccount(id, data);
      showToast('Account updated', 'success');
    } else {
      const created = await window.flowAPI.addAccount(data);
      switchAccount(created.id);
      showToast(`Account "${created.name}" added`, 'success');
    }

    closeAccountModal();
    await loadAccounts();
  });

  el.btnImportChrome.addEventListener('click', openChromeImportModal);
  el.btnEmptyImport.addEventListener('click', openChromeImportModal);
  el.btnCloseChromeModal.addEventListener('click', closeAllModals);
  el.btnCancelChrome.addEventListener('click', closeAllModals);
  el.btnConfirmImport.addEventListener('click', confirmChromeImport);

  el.chkSelectAllProfiles.addEventListener('change', (e) => {
    const isChecked = e.target.checked;
    el.chromeProfilesList.querySelectorAll('.chk-chrome-item:not(:disabled)').forEach(chk => {
      chk.checked = isChecked;
    });
  });

  el.btnOpenSettings.addEventListener('click', () => {
    if (window.flowAPI) window.flowAPI.setFlowViewVisible(false);
    el.modalSettings.classList.remove('hidden');
  });

  el.btnCloseSettingsModal.addEventListener('click', closeAllModals);

  el.btnSaveSettings.addEventListener('click', async () => {
    state.settings.autoSwitch = el.settingAutoSwitch.checked;
    state.settings.minCreditsForSwitch = parseInt(el.settingMinCredits.value, 10) || 15;
    state.settings.prioritizePro = el.settingPrioritizePro.checked;
    state.settings.audioAlerts = el.settingAudioAlerts.checked;
    el.toggleAutoSwitch.checked = state.settings.autoSwitch;

    if (window.flowAPI) {
      await window.flowAPI.saveSettings(state.settings);
    }

    closeAllModals();
    updatePoolStats();
    showToast('Settings saved', 'success');
  });

  // Close modals when clicking the dark backdrop outside the modal dialog
  [el.modalAccount, el.modalChromeImport, el.modalSettings].forEach(m => {
    m.addEventListener('click', (e) => {
      if (e.target === m) {
        closeAllModals();
      }
    });
  });

  // Close modals on Escape key
  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      closeAllModals();
    }
  });

  // Author WhatsApp Contact Link
  if (el.btnAuthorLink) {
    el.btnAuthorLink.addEventListener('click', (e) => {
      e.preventDefault();
      const url = el.btnAuthorLink.getAttribute('href') || 'https://wa.me/+923025080076';
      if (window.flowAPI && typeof window.flowAPI.openExternal === 'function') {
        window.flowAPI.openExternal(url);
      } else {
        window.open(url, '_blank');
      }
    });
  }
}

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

window.addEventListener('DOMContentLoaded', init);
