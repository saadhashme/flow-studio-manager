// main.js - Flow Multi-Account Studio Manager
const { app, BrowserWindow, BrowserView, ipcMain, session, nativeImage } = require('electron');
const path = require('path');
const fs = require('fs');

// 1. Anti-Bot / Anti-Detection Chrome Flags
app.commandLine.appendSwitch('disable-blink-features', 'AutomationControlled');
app.commandLine.appendSwitch('disable-features', 'WidgetLayering,IsolateOrigins,site-per-process');
app.commandLine.appendSwitch('enable-features', 'NetworkService,NetworkServiceInProcess');

// Exact match with Electron 33's bundled Chromium 130
const CHROME_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36';
app.userAgentFallback = CHROME_UA;

let mainWindow = null;
let activeFlowView = null;
let activeAccountId = null;
let viewCache = new Map(); // accountId -> BrowserView
let sidebarWidth = 330;
let topbarHeight = 64;

// Persistent Storage Paths
function getStoragePath(fileName) {
  const userDataDir = app.getPath('userData');
  if (!fs.existsSync(userDataDir)) {
    fs.mkdirSync(userDataDir, { recursive: true });
  }
  return path.join(userDataDir, fileName);
}

function loadAccountsFromDisk() {
  const file = getStoragePath('accounts.json');
  if (fs.existsSync(file)) {
    try {
      return JSON.parse(fs.readFileSync(file, 'utf8'));
    } catch (e) {
      console.error('Error reading accounts.json:', e);
    }
  }
  return [];
}

function saveAccountsToDisk(accounts) {
  const file = getStoragePath('accounts.json');
  fs.writeFileSync(file, JSON.stringify(accounts, null, 2), 'utf8');
}

function loadSettingsFromDisk() {
  const file = getStoragePath('settings.json');
  if (fs.existsSync(file)) {
    try {
      return JSON.parse(fs.readFileSync(file, 'utf8'));
    } catch (e) {}
  }
  return {
    autoSwitch: true,
    minCreditsForSwitch: 15,
    soundAlerts: true,
    prioritizePro: true
  };
}

function saveSettingsToDisk(settings) {
  const file = getStoragePath('settings.json');
  fs.writeFileSync(file, JSON.stringify(settings, null, 2), 'utf8');
}

// 2. Configure Session Partition with Stealth & Header Sanitization
function setupSessionPartition(partitionName) {
  const ses = session.fromPartition(partitionName);

  ses.setUserAgent(CHROME_UA);

  ses.webRequest.onBeforeSendHeaders((details, callback) => {
    const headers = { ...details.requestHeaders };
    
    headers['sec-ch-ua'] = '"Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"';
    headers['sec-ch-ua-mobile'] = '?0';
    headers['sec-ch-ua-platform'] = '"Windows"';
    headers['sec-ch-ua-platform-version'] = '"10.0.0"';

    delete headers['X-Electron'];
    delete headers['x-electron'];

    callback({ requestHeaders: headers });
  });

  return ses;
}

// 3. Create or Get BrowserView for Account
function getOrCreateViewForAccount(account) {
  if (viewCache.has(account.id)) {
    return viewCache.get(account.id);
  }

  const partitionName = `persist:flow_account_${account.id}`;
  setupSessionPartition(partitionName);

  const view = new BrowserView({
    webPreferences: {
      partition: partitionName,
      preload: path.join(__dirname, 'flow-preload.js'),
      nodeIntegration: false,
      contextIsolation: false, // Critical: runs stealth patches in MAIN world
      sandbox: false,
      webSecurity: true,
      allowRunningInsecureContent: false,
      userAgent: CHROME_UA
    }
  });

  // Handle flow credits, plan updates & generation deductions from preload
  view.webContents.on('ipc-message', (event, channel, ...args) => {
    if (channel === 'flow-credits-updated') {
      const data = args[0];
      handleAccountStateUpdated(account.id, data);
    } else if (channel === 'flow-generation-started') {
      const cost = (args[0] && args[0].cost) || 15;
      handleGenerationDeduction(account.id, cost);
    }
  });

  view.webContents.on('did-navigate', (event, url) => {
    if (mainWindow && activeAccountId === account.id) {
      mainWindow.webContents.send('flow-navigated', { accountId: account.id, url });
    }
  });

  // Initial Load
  view.webContents.loadURL('https://flow.google.com/');

  viewCache.set(account.id, view);
  return view;
}

function handleGenerationDeduction(accountId, cost) {
  const accounts = loadAccountsFromDisk();
  const acc = accounts.find(a => a.id === accountId);
  if (acc && typeof acc.credits === 'number') {
    const prev = acc.credits;
    acc.credits = Math.max(0, acc.credits - cost);
    acc.lastUpdated = Date.now();
    saveAccountsToDisk(accounts);

    console.log(`[Auto-Deduction] Deducted ${cost} credits from ${acc.name}: ${prev} -> ${acc.credits}`);

    if (mainWindow) {
      mainWindow.webContents.send('account-updated', {
        accountId,
        account: acc,
        source: 'deduction:video-clip-generated'
      });
      mainWindow.webContents.send('app-notification', {
        type: 'clip-generated',
        message: `🎬 -${cost} Credits: Video clip started (Remaining: ${acc.credits.toLocaleString()})`,
        level: 'info'
      });
    }

    const settings = loadSettingsFromDisk();
    if (settings.autoSwitch && activeAccountId === accountId && acc.credits < settings.minCreditsForSwitch) {
      triggerAutoSwitchToNext(accountId, accounts, settings);
    }
  }
}

function updateViewBounds() {
  if (!mainWindow || !activeFlowView) return;
  const bounds = mainWindow.getContentBounds();
  activeFlowView.setBounds({
    x: sidebarWidth,
    y: topbarHeight,
    width: Math.max(0, bounds.width - sidebarWidth),
    height: Math.max(0, bounds.height - topbarHeight)
  });
}

function switchActiveAccount(accountId) {
  const accounts = loadAccountsFromDisk();
  const account = accounts.find(a => a.id === accountId);
  if (!account) return false;

  activeAccountId = accountId;

  if (activeFlowView) {
    mainWindow.removeBrowserView(activeFlowView);
  }

  const newView = getOrCreateViewForAccount(account);
  mainWindow.addBrowserView(newView);
  activeFlowView = newView;
  updateViewBounds();

  if (mainWindow) {
    mainWindow.webContents.send('account-switched', { accountId, account });
  }

  return true;
}

function handleAccountStateUpdated(accountId, data) {
  const accounts = loadAccountsFromDisk();
  const acc = accounts.find(a => a.id === accountId);
  if (acc) {
    let changed = false;

    if (typeof data.credits === 'number') {
      acc.credits = data.credits;
      acc.lastUpdated = Date.now();
      
      // Scale maxCredits dynamically
      if (!acc.maxCredits || data.credits > acc.maxCredits) {
        acc.maxCredits = Math.max(data.credits, acc.type === 'pro' ? 1000 : 50);
      }
      changed = true;
    }

    if (data.planType && acc.type !== data.planType) {
      acc.type = data.planType;
      if (acc.type === 'pro' && (!acc.maxCredits || acc.maxCredits < 1000)) {
        acc.maxCredits = Math.max(acc.credits || 0, 1000);
      }
      changed = true;
    }

    if (changed) {
      saveAccountsToDisk(accounts);

      if (mainWindow) {
        mainWindow.webContents.send('account-updated', {
          accountId,
          account: acc,
          source: data.source
        });
      }

      // Check Auto-Switch if active account runs out
      const settings = loadSettingsFromDisk();
      if (settings.autoSwitch && activeAccountId === accountId && acc.credits < settings.minCreditsForSwitch) {
        triggerAutoSwitchToNext(accountId, accounts, settings);
      }
    }
  }
}

function triggerAutoSwitchToNext(currentAccountId, accounts, settings) {
  let candidates = accounts.filter(a => a.id !== currentAccountId && (a.credits !== null && a.credits !== undefined) && a.credits >= settings.minCreditsForSwitch);
  
  if (settings.prioritizePro) {
    candidates.sort((a, b) => {
      if (a.type === 'pro' && b.type !== 'pro') return -1;
      if (b.type === 'pro' && a.type !== 'pro') return 1;
      return (b.credits || 0) - (a.credits || 0);
    });
  } else {
    candidates.sort((a, b) => (b.credits || 0) - (a.credits || 0));
  }

  if (candidates.length > 0) {
    const nextAcc = candidates[0];
    console.log(`[Auto-Switch] Switching from ${currentAccountId} to ${nextAcc.id} (${nextAcc.name})`);
    switchActiveAccount(nextAcc.id);
    if (mainWindow) {
      mainWindow.webContents.send('app-notification', {
        type: 'auto-switched',
        message: `Credits depleted! Automatically switched to "${nextAcc.name}" (${nextAcc.credits} credits).`,
        nextAccountId: nextAcc.id
      });
    }
  } else {
    if (mainWindow) {
      mainWindow.webContents.send('app-notification', {
        type: 'all-depleted',
        message: 'All accounts have fewer than 15 credits remaining for today!',
        level: 'warning'
      });
    }
  }
}

// 4. Create Main Window
function createMainWindow() {
  const iconPng = path.join(__dirname, 'assets', 'icon.png');
  const iconIco = path.join(__dirname, 'assets', 'icon.ico');
  let appIcon = null;
  if (fs.existsSync(iconPng)) {
    appIcon = nativeImage.createFromPath(iconPng);
  } else if (fs.existsSync(iconIco)) {
    appIcon = nativeImage.createFromPath(iconIco);
  }

  mainWindow = new BrowserWindow({
    width: 1440,
    height: 920,
    minWidth: 1060,
    minHeight: 700,
    backgroundColor: '#0a0d14',
    title: 'Flow Studio Manager',
    icon: (appIcon && !appIcon.isEmpty()) ? appIcon : (fs.existsSync(iconIco) ? iconIco : undefined),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true
    }
  });

  if (appIcon && !appIcon.isEmpty()) {
    mainWindow.setIcon(appIcon);
  }

  mainWindow.loadFile(path.join(__dirname, 'src', 'index.html'));

  mainWindow.on('resize', () => {
    updateViewBounds();
  });

  mainWindow.on('maximize', () => {
    setTimeout(updateViewBounds, 100);
  });

  mainWindow.on('unmaximize', () => {
    setTimeout(updateViewBounds, 100);
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
    activeFlowView = null;
    viewCache.clear();
  });
}

// 5. App Lifecycle
if (process.platform === 'win32') {
  app.setAppUserModelId('com.flowstudiomanager.app');
}

app.whenReady().then(() => {
  createMainWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createMainWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

// 6. IPC Handlers
ipcMain.handle('get-accounts', () => {
  return loadAccountsFromDisk();
});

ipcMain.handle('save-accounts', (event, accounts) => {
  saveAccountsToDisk(accounts);
  return true;
});

ipcMain.handle('switch-account', (event, accountId) => {
  return switchActiveAccount(accountId);
});

ipcMain.handle('add-account', (event, accountData) => {
  const accounts = loadAccountsFromDisk();
  const isPro = accountData.type === 'pro';
  const initialCredits = typeof accountData.credits === 'number' ? accountData.credits : (accountData.credits === null ? null : null);
  
  const newAccount = {
    id: 'acc_' + Date.now() + '_' + Math.random().toString(36).substr(2, 5),
    name: accountData.name || 'Account ' + (accounts.length + 1),
    email: accountData.email || '',
    type: accountData.type || 'free', // Defaults to free until detected or specified
    credits: initialCredits,
    maxCredits: isPro ? (initialCredits ? Math.max(initialCredits, 1000) : 1000) : 50,
    lastUpdated: Date.now(),
    chromeProfile: accountData.chromeProfile || null,
    status: initialCredits !== null ? 'ready' : 'pending_sync'
  };

  accounts.push(newAccount);
  saveAccountsToDisk(accounts);

  if (accounts.length === 1) {
    switchActiveAccount(newAccount.id);
  }

  return newAccount;
});

ipcMain.handle('delete-account', (event, accountId) => {
  let accounts = loadAccountsFromDisk();
  accounts = accounts.filter(a => a.id !== accountId);
  saveAccountsToDisk(accounts);

  if (viewCache.has(accountId)) {
    const view = viewCache.get(accountId);
    if (activeFlowView === view) {
      mainWindow.removeBrowserView(view);
      activeFlowView = null;
    }
    view.webContents.destroy();
    viewCache.delete(accountId);
  }

  if (activeAccountId === accountId && accounts.length > 0) {
    switchActiveAccount(accounts[0].id);
  }

  return true;
});

ipcMain.handle('update-account', (event, accountId, updates) => {
  const accounts = loadAccountsFromDisk();
  const acc = accounts.find(a => a.id === accountId);
  if (acc) {
    Object.assign(acc, updates);
    if (updates.type === 'pro' && (!acc.maxCredits || acc.maxCredits < 1000)) {
      acc.maxCredits = Math.max(acc.credits || 0, 1000);
    }
    saveAccountsToDisk(accounts);
    return acc;
  }
  return null;
});

ipcMain.handle('import-chrome-profiles', () => {
  const localStatePath = path.join(process.env.LOCALAPPDATA, 'Google', 'Chrome', 'User Data', 'Local State');
  if (!fs.existsSync(localStatePath)) {
    return { success: false, message: 'Chrome Local State not found on this system.', profiles: [] };
  }

  try {
    const raw = fs.readFileSync(localStatePath, 'utf8');
    const data = JSON.parse(raw);
    const infoCache = data.profile ? data.profile.info_cache : {};
    
    const existingAccounts = loadAccountsFromDisk();
    const existingEmails = new Set(existingAccounts.map(a => (a.email || '').toLowerCase().trim()));

    const discovered = [];
    for (const [key, val] of Object.entries(infoCache)) {
      const email = (val.user_name || '').trim();
      const displayName = val.name || val.gaia_name || key;
      if (email || val.gaia_name) {
        discovered.push({
          chromeKey: key,
          name: displayName,
          email: email,
          isAlreadyAdded: email ? existingEmails.has(email.toLowerCase()) : false
        });
      }
    }

    return { success: true, profiles: discovered };
  } catch (err) {
    return { success: false, message: err.message, profiles: [] };
  }
});

// Dedicated Sign-In Window
ipcMain.handle('open-login-modal', (event, accountId) => {
  const accounts = loadAccountsFromDisk();
  const acc = accounts.find(a => a.id === accountId);
  if (!acc) return false;

  const partitionName = `persist:flow_account_${accountId}`;
  setupSessionPartition(partitionName);

  const authWindow = new BrowserWindow({
    width: 620,
    height: 740,
    parent: mainWindow,
    modal: true,
    title: `Sign In to Google Flow: ${acc.name}`,
    webPreferences: {
      partition: partitionName,
      preload: path.join(__dirname, 'flow-preload.js'),
      nodeIntegration: false,
      contextIsolation: false,
      sandbox: false,
      userAgent: CHROME_UA
    }
  });

  authWindow.loadURL('https://accounts.google.com/ServiceLogin?continue=https://flow.google.com/');

  authWindow.webContents.on('did-navigate', (e, url) => {
    if (url.includes('flow.google.com') && !url.includes('ServiceLogin') && !url.includes('signin')) {
      setTimeout(() => {
        if (!authWindow.isDestroyed()) {
          authWindow.close();
        }
        if (viewCache.has(accountId)) {
          viewCache.get(accountId).webContents.loadURL('https://flow.google.com/');
        }
      }, 1500);
    }
  });

  return true;
});

// Toggle view visibility when HTML modals open/close
ipcMain.handle('set-flow-view-visible', (event, visible) => {
  if (!mainWindow || !activeFlowView) return false;
  if (visible) {
    try {
      mainWindow.addBrowserView(activeFlowView);
      updateViewBounds();
    } catch (e) {}
  } else {
    try {
      mainWindow.removeBrowserView(activeFlowView);
    } catch (e) {}
  }
  return true;
});

// Browser Controls
ipcMain.handle('navigate-flow', (event, action) => {
  if (!activeFlowView) return false;
  const wc = activeFlowView.webContents;
  if (action === 'back' && wc.canGoBack()) wc.goBack();
  else if (action === 'forward' && wc.canGoForward()) wc.goForward();
  else if (action === 'reload') wc.reload();
  else if (action === 'home') wc.loadURL('https://flow.google.com/');
  return true;
});

ipcMain.handle('refresh-credits', () => {
  if (!activeFlowView) return false;
  activeFlowView.webContents.executeJavaScript(`
    (function() {
      if (typeof window.triggerFlowCreditSync === 'function') {
        window.triggerFlowCreditSync();
      } else if (typeof scanDOMForCreditsAndPlan === 'function') {
        scanDOMForCreditsAndPlan();
      }
    })();
  `).catch(() => {});
  return true;
});

ipcMain.handle('get-settings', () => {
  return loadSettingsFromDisk();
});

ipcMain.handle('save-settings', (event, settings) => {
  saveSettingsToDisk(settings);
  return true;
});
