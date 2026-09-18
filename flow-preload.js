// flow-preload.js
// Complete Google Flow stealth, automated real-time credit tracking & generation deduction
const { ipcRenderer } = require('electron');

// 1. Google Authentication Stealth Mocks
try {
  try {
    Object.defineProperty(Object.getPrototypeOf(navigator), 'webdriver', {
      get: () => undefined,
      configurable: true
    });
  } catch (e) {}
  try {
    delete navigator.__proto__.webdriver;
  } catch (e) {}
  try {
    delete navigator.webdriver;
  } catch (e) {}

  if (navigator.userAgentData) {
    const defaultBrands = [
      { brand: 'Chromium', version: '130' },
      { brand: 'Google Chrome', version: '130' },
      { brand: 'Not?A_Brand', version: '99' }
    ];
    try {
      Object.defineProperty(navigator.userAgentData, 'brands', {
        get: () => defaultBrands,
        configurable: true
      });
    } catch (e) {}
  }

  window.chrome = {
    app: {
      isInstalled: false,
      InstallState: { DISABLED: 'disabled', INSTALLED: 'installed', NOT_INSTALLED: 'not_installed' },
      RunningState: { CANNOT_RUN: 'cannot_run', READY_TO_RUN: 'ready_to_run', RUNNING: 'running' }
    },
    csi: function() { return { startE: Date.now(), onloadT: Date.now(), pageT: 1, tran: 15 }; },
    loadTimes: function() {
      return {
        requestTime: Date.now() / 1000 - 1,
        startLoadTime: Date.now() / 1000 - 0.8,
        commitLoadTime: Date.now() / 1000 - 0.5,
        finishDocumentLoadTime: Date.now() / 1000 - 0.2,
        finishLoadTime: Date.now() / 1000,
        firstPaintTime: Date.now() / 1000 - 0.3,
        firstPaintAfterLoadTime: 0,
        navigationType: 'Other',
        wasFetchedViaSpdy: true,
        wasNpnNegotiated: true,
        npnNegotiatedProtocol: 'h2',
        wasAlternateProtocolAvailable: false,
        connectionInfo: 'h2'
      };
    },
    runtime: {
      OnInstalledReason: {},
      OnRestartRequiredReason: {},
      PlatformArch: {},
      PlatformNaclArch: {},
      PlatformOs: {},
      RequestUpdateCheckStatus: {},
      connect: function() {},
      sendMessage: function() {}
    }
  };

  if (!navigator.plugins || navigator.plugins.length === 0) {
    const mockPlugins = [
      { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
      { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: '' },
      { name: 'Native Client', filename: 'internal-nacl-plugin', description: '' }
    ];
    try {
      Object.defineProperty(navigator, 'plugins', {
        get: () => mockPlugins,
        configurable: true
      });
    } catch (e) {}
  }
} catch (e) {
  console.warn('[Stealth Preload Warning]:', e);
}

// 2. Helper to Parse Credit Numbers
function parseCreditNumber(str) {
  if (!str) return null;
  const cleaned = str.toString().replace(/,/g, '').trim();
  const num = parseInt(cleaned, 10);
  if (isNaN(num) || num < 0 || num > 100000) return null;
  return num;
}

let lastReportedCredits = null;
let lastReportedPlan = null;

function reportAccountState(credits, planType, source) {
  const parsedCredits = parseCreditNumber(credits);
  const data = { source, timestamp: Date.now() };

  let changed = false;
  if (parsedCredits !== null && parsedCredits !== lastReportedCredits) {
    lastReportedCredits = parsedCredits;
    data.credits = parsedCredits;
    changed = true;
  }

  let resolvedPlan = planType;
  if (!resolvedPlan && parsedCredits !== null) {
    if (parsedCredits > 100) resolvedPlan = 'pro';
  }

  if (resolvedPlan && resolvedPlan !== lastReportedPlan) {
    lastReportedPlan = resolvedPlan;
    data.planType = resolvedPlan;
    changed = true;
  }

  if (changed || data.credits !== undefined || data.planType !== undefined) {
    console.log(`[Flow Monitor] State update: credits=${data.credits}, plan=${data.planType} via ${source}`);
    try {
      ipcRenderer.send('flow-credits-updated', data);
    } catch (e) {}
  }
}

// 3. API & Network Interceptors (fetch + XMLHttpRequest)
try {
  const originalFetch = window.fetch;
  window.fetch = async function(...args) {
    const response = await originalFetch.apply(this, args);
    try {
      const url = typeof args[0] === 'string' ? args[0] : (args[0] && args[0].url ? args[0].url : '');
      // Inspect all google internal / api calls
      if (url.includes('google') || url.includes('alkali') || url.includes('flow') || url.includes('sandbox')) {
        const clone = response.clone();
        clone.text().then(text => {
          analyzeTextForCreditsAndPlan(text, 'api:fetch');
        }).catch(() => {});
      }
    } catch (err) {}
    return response;
  };

  const originalXHROpen = XMLHttpRequest.prototype.open;
  const originalXHRSend = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function(method, url) {
    this._url = url;
    return originalXHROpen.apply(this, arguments);
  };
  XMLHttpRequest.prototype.send = function() {
    this.addEventListener('load', () => {
      try {
        const url = this._url || '';
        if (url.includes('google') || url.includes('alkali') || url.includes('flow')) {
          analyzeTextForCreditsAndPlan(this.responseText, 'api:xhr');
        }
      } catch (e) {}
    });
    return originalXHRSend.apply(this, arguments);
  };
} catch (e) {
  console.warn('[Network Hook Warning]:', e);
}

function detectPlanFromHeader() {
  try {
    const header = document.querySelector('header, nav, [role="banner"]') || document.body;
    const elements = header.querySelectorAll('button, span, div, a');
    for (const el of elements) {
      const text = (el.innerText || el.textContent || '').trim();
      // Exact match: Google Flow displays a distinct "PRO" button pill right before the avatar circle
      if (text === 'PRO') {
        const rect = el.getBoundingClientRect();
        if (rect.top < 80 && rect.right > window.innerWidth - 200 && rect.width > 20) {
          return 'pro';
        }
      }
    }
  } catch (e) {}
  return 'free';
}

function analyzeTextForCreditsAndPlan(text, source) {
  if (!text || typeof text !== 'string') return;

  const detectedPlan = detectPlanFromHeader();

  const matchPopup = text.match(/([\d,]+)\s+Google\s+Flow\s+credits/i);
  if (matchPopup) {
    const num = parseCreditNumber(matchPopup[1]);
    if (num !== null) {
      reportAccountState(num, detectedPlan, `${source}:google-flow-credits`);
      return;
    }
  }

  if (/refresh\s+daily/i.test(text)) {
    const refreshMatch = text.match(/([\d,]+)\s*(?:Google\s+Flow\s+)?credits[\s\S]{0,80}refresh\s+daily/i) ||
                         text.match(/refresh\s+daily[\s\S]{0,80}?([\d,]+)\s*(?:Google\s+Flow\s+)?credits/i);
    if (refreshMatch) {
      const num = parseCreditNumber(refreshMatch[1]);
      if (num !== null) {
        reportAccountState(num, detectedPlan, `${source}:refresh-daily`);
        return;
      }
    }
  }

  try {
    const json = JSON.parse(text);
    findCreditsInObject(json);
  } catch (e) {
    const jsonMatch = text.match(/"(?:credits|creditsRemaining|flowCredits|availableCredits|balance|remainingQuota)"\s*:\s*"?([\d,]+)"?/i);
    if (jsonMatch) {
      const num = parseCreditNumber(jsonMatch[1]);
      if (num !== null) {
        reportAccountState(num, detectedPlan, 'api:json-regex');
      }
    }
  }
}

function findCreditsInObject(obj) {
  if (!obj || typeof obj !== 'object') return;
  for (const key of Object.keys(obj)) {
    const val = obj[key];
    const lower = key.toLowerCase();
    if ((lower.includes('credit') || lower.includes('quota') || lower.includes('balance')) && (typeof val === 'number' || typeof val === 'string')) {
      const num = parseCreditNumber(val);
      if (num !== null) {
        reportAccountState(num, num > 100 ? 'pro' : null, `api:${key}`);
        return;
      }
    } else if (typeof val === 'object') {
      findCreditsInObject(val);
    }
  }
}

// 4. DOM Scanner for Account Menu & Header Plan
function scanDOMForCreditsAndPlan() {
  try {
    const plan = detectPlanFromHeader();

    let creditsFound = null;
    const allElements = document.querySelectorAll('div, span, p, [role="menu"], [role="dialog"], [role="tooltip"], section');
    for (const el of allElements) {
      if (el.children.length > 6) continue;
      const text = el.innerText || el.textContent || '';
      if (!text) continue;

      if ((text.includes('10 credits') || text.includes('15 credits')) && !text.includes('refresh') && !text.includes('Flow') && !text.includes('Google')) {
        continue;
      }

      if (/Google\s+Flow\s+credits/i.test(text) || (/credits/i.test(text) && /refresh\s+daily/i.test(text))) {
        const match = text.match(/([\d,]+)\s*(?:Google\s+Flow\s+)?credits/i);
        if (match) {
          const num = parseCreditNumber(match[1]);
          if (num !== null) {
            creditsFound = num;
            break;
          }
        }
      }
    }

    reportAccountState(creditsFound, plan, creditsFound !== null ? 'dom:account-popup' : 'header:pro-pill');
  } catch (err) {}
}

// 5. Automatic Top-Right Avatar Element Finder
function findGoogleAvatarElement() {
  try {
    // Check known aria labels
    const aria = document.querySelector('[aria-label*="Google Account"], [aria-label*="Account:"], [aria-label*="Google-Konto"]');
    if (aria) return aria;

    // Search header buttons near top right (x > window.innerWidth - 130, y < 70)
    const header = document.querySelector('header, nav, [role="banner"]') || document.body;
    const buttons = header.querySelectorAll('button, [role="button"], a, div[tabindex]');
    
    for (let i = buttons.length - 1; i >= 0; i--) {
      const btn = buttons[i];
      const rect = btn.getBoundingClientRect();
      if (rect.right > window.innerWidth - 120 && rect.top < 70 && rect.width >= 20 && rect.height >= 20) {
        return btn;
      }
    }

    // Circular avatar element fallback
    const elements = document.querySelectorAll('div, span, button');
    for (const el of elements) {
      const rect = el.getBoundingClientRect();
      if (rect.right > window.innerWidth - 80 && rect.top < 65 && rect.width >= 24 && rect.width <= 50) {
        return el;
      }
    }
  } catch (e) {}
  return null;
}

window.triggerFlowCreditSync = function() {
  scanDOMForCreditsAndPlan();
};

// 5. Real-Time Generation Detector (Auto-Deducts 15 Credits when a video is created)
let lastGenerationTime = 0;

function handleVideoGenerationTriggered() {
  const now = Date.now();
  if (now - lastGenerationTime < 4000) return;
  lastGenerationTime = now;

  console.log('[Flow Monitor] Video clip generation initiated -> Auto-deducting 15 credits');
  try {
    ipcRenderer.send('flow-generation-started', { cost: 15 });
  } catch (e) {}

  // Trigger passive DOM scan after 3s and 8s
  setTimeout(scanDOMForCreditsAndPlan, 3000);
  setTimeout(scanDOMForCreditsAndPlan, 8000);
}

// Listen for DOM changes & generation triggers in page
window.addEventListener('DOMContentLoaded', () => {
  scanDOMForCreditsAndPlan();

  // Watch for text changes (e.g. flyout opening naturally or video generation messages)
  const observer = new MutationObserver((mutations) => {
    scanDOMForCreditsAndPlan();

    for (const m of mutations) {
      for (const node of m.addedNodes) {
        if (node.nodeType === Node.ELEMENT_NODE) {
          const text = (node.innerText || node.textContent || '').toLowerCase();
          if (text.includes('started generating') || text.includes('in the queue') || text.includes('generating your video')) {
            handleVideoGenerationTriggered();
          }
        }
      }
    }
  });

  if (document.body) {
    observer.observe(document.body, {
      childList: true,
      subtree: true,
      characterData: true
    });
  }

  // Intercept prompt submission (Enter key)
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      const active = document.activeElement;
      if (active && (active.tagName === 'TEXTAREA' || active.tagName === 'INPUT' || active.getAttribute('contenteditable') === 'true')) {
        const val = (active.value || active.innerText || '').trim();
        if (val.length > 2) {
          setTimeout(handleVideoGenerationTriggered, 600);
        }
      }
    }
  }, true);

  // Intercept button clicks (Approve, Arrow submit, etc.)
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('button, [role="button"]');
    if (!btn) return;
    const text = (btn.innerText || btn.textContent || '').trim().toLowerCase();
    const aria = (btn.getAttribute('aria-label') || '').toLowerCase();
    
    if (text === 'approve' || aria.includes('send') || aria.includes('create') || btn.querySelector('svg polygon, svg path[d*="arrow"]')) {
      setTimeout(handleVideoGenerationTriggered, 600);
    }
  }, true);

  // Periodic passive DOM scan every 10 seconds (no clicks, purely reading)
  setInterval(scanDOMForCreditsAndPlan, 10000);
});

// Clean up Node globals
try {
  delete window.require;
  delete window.exports;
  delete window.module;
} catch (e) {}

try {
  ipcRenderer.send('flow-view-ready', { url: window.location.href });
} catch (e) {}
