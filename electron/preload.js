/**
 * electron/preload.js
 * Expõe API segura para o frontend via contextBridge.
 */

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  isElectron:  true,
  platform:    process.platform,
  minimize:    () => ipcRenderer.send('window-minimize'),
  maximize:    () => ipcRenderer.send('window-maximize'),
  closeWindow: () => ipcRenderer.send('window-close'),
  getVersion:  () => ipcRenderer.invoke('get-version'),
});