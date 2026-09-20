// preload.js
// Context bridge for the Studio Manager UI
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('flowAPI', {
  // Accounts
  getAccounts: () => ipcRenderer.invoke('get-accounts'),
  saveAccounts: (accounts) => ipcRenderer.invoke('save-accounts', accounts),
  switchAccount: (accountId) => ipcRenderer.invoke('switch-account', accountId),
  addAccount: (accountData) => ipcRenderer.invoke('add-account', accountData),
  deleteAccount: (accountId) => ipcRenderer.invoke('delete-account', accountId),
  updateAccount: (accountId, updates) => ipcRenderer.invoke('update-account', accountId, updates),
  importChromeProfiles: () => ipcRenderer.invoke('import-chrome-profiles'),

  // Browser Navigation & Controls
  navigateFlow: (action) => ipcRenderer.invoke('navigate-flow', action),
  openLoginModal: (accountId) => ipcRenderer.invoke('open-login-modal', accountId),
  refreshCurrentCredits: () => ipcRenderer.invoke('refresh-credits'),
  setFlowViewVisible: (visible) => ipcRenderer.invoke('set-flow-view-visible', visible),
  openExternal: (url) => ipcRenderer.invoke('open-external', url),

  // Settings & Storage
  getSettings: () => ipcRenderer.invoke('get-settings'),
  saveSettings: (settings) => ipcRenderer.invoke('save-settings', settings),

  // Event Listeners
  onCreditUpdate: (callback) => {
    const subscription = (event, data) => callback(data);
    ipcRenderer.on('flow-credits-updated', subscription);
    return () => ipcRenderer.removeListener('flow-credits-updated', subscription);
  },
  onAccountUpdated: (callback) => {
    const subscription = (event, data) => callback(data);
    ipcRenderer.on('account-updated', subscription);
    return () => ipcRenderer.removeListener('account-updated', subscription);
  },
  onAccountSwitched: (callback) => {
    const subscription = (event, data) => callback(data);
    ipcRenderer.on('account-switched', subscription);
    return () => ipcRenderer.removeListener('account-switched', subscription);
  },
  onFlowNavigation: (callback) => {
    const subscription = (event, data) => callback(data);
    ipcRenderer.on('flow-navigated', subscription);
    return () => ipcRenderer.removeListener('flow-navigated', subscription);
  },
  onNotification: (callback) => {
    const subscription = (event, data) => callback(data);
    ipcRenderer.on('app-notification', subscription);
    return () => ipcRenderer.removeListener('app-notification', subscription);
  }
});
