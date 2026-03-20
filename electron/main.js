/**
 * electron/main.js — Bellart ERP
 * Processo principal do Electron.
 * Sobe o backend Python e abre a janela desktop.
 */

const { app, BrowserWindow, Tray, Menu, nativeImage, dialog, shell } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const http = require('http');
const fs = require('fs');

// ── Configurações ─────────────────────────────────────────────
const PORT = 8765;
const BASE_URL = `http://127.0.0.1:${PORT}`;
const isDev = !app.isPackaged;

let mainWindow = null;
let tray = null;
let pythonProcess = null;

// ── Encontrar Python no Windows ───────────────────────────────
function findPython() {
  // Em produção: usa Python embutido
  if (!isDev) {
    return path.join(process.resourcesPath, 'python-dist', 'python', 'python.exe');
  }

  // Em desenvolvimento: tenta várias opções
  const projectRoot = path.join(__dirname, '..');

  const candidates = [
    // 1. venv local do projeto (prioridade máxima — tem todas as deps)
    path.join(projectRoot, '.venv', 'Scripts', 'python.exe'),
    path.join(projectRoot, 'venv', 'Scripts', 'python.exe'),
    path.join(projectRoot, '.venv', 'bin', 'python'),
    path.join(projectRoot, 'venv', 'bin', 'python'),
    // 2. Python 3.11 nos caminhos padrão do Windows
    path.join('C:', 'Users', process.env.USERNAME || '', 'AppData', 'Local', 'Programs', 'Python', 'Python311', 'python.exe'),
    path.join('C:', 'Python311', 'python.exe'),
    path.join('C:', 'Program Files', 'Python311', 'python.exe'),
    // 3. Python 3.13 (versão encontrada no seu sistema)
    path.join('C:', 'Users', process.env.USERNAME || '', 'AppData', 'Local', 'Programs', 'Python', 'Python313', 'python.exe'),
    // 4. Comandos genéricos como fallback
    'python',
    'python3',
    'py',
  ];

  // Verifica qual existe (para caminhos absolutos)
  for (const candidate of candidates) {
    if (candidate.includes(path.sep) && fs.existsSync(candidate)) {
      console.log(`[Electron] Python encontrado: ${candidate}`);
      return candidate;
    }
  }

  // Fallback: deixa o sistema resolver
  console.log('[Electron] Usando Python do PATH');
  return 'python';
}

function getRunScript() {
  if (!isDev) {
    return path.join(process.resourcesPath, 'python-dist', 'run.py');
  }
  return path.join(__dirname, '..', 'run.py');
}

function getCwd() {
  if (!isDev) return process.resourcesPath;
  return path.join(__dirname, '..');
}

// ── Subir o backend Python ────────────────────────────────────
function startPython() {
  const pythonExe = findPython();
  const runScript = getRunScript();
  const cwd = getCwd();

  console.log(`[Electron] Python: ${pythonExe}`);
  console.log(`[Electron] Script: ${runScript}`);
  console.log(`[Electron] CWD: ${cwd}`);

  pythonProcess = spawn(pythonExe, [runScript], {
    cwd,
    env: { ...process.env, PYTHONUNBUFFERED: '1' },
    windowsHide: true,
    shell: false,
  });

  pythonProcess.stdout.on('data', (data) => {
    console.log(`[Python] ${data.toString().trim()}`);
  });

  pythonProcess.stderr.on('data', (data) => {
    const msg = data.toString().trim();
    console.log(`[Python] ${msg}`);
    // uvicorn loga no stderr — não tratar como erro real
  });

  pythonProcess.on('error', (err) => {
    console.error(`[Python ERRO] ${err.message}`);
    dialog.showErrorBox(
      'Python não encontrado',
      `Não foi possível iniciar o Python.\n\nErro: ${err.message}\n\nVerifique se o Python 3.11 está instalado e no PATH.`
    );
    app.quit();
  });

  pythonProcess.on('close', (code) => {
    console.log(`[Python] Encerrado com código ${code}`);
    if (code !== 0 && code !== null && mainWindow) {
      dialog.showErrorBox(
        'Servidor encerrado',
        `O servidor Bellart encerrou inesperadamente (código ${code}).\n\nFeche e abra o Bellart novamente.`
      );
    }
  });
}

// ── Aguardar servidor ─────────────────────────────────────────
function waitForServer(retries = 50, delay = 500) {
  return new Promise((resolve, reject) => {
    let attempts = 0;
    const check = () => {
      const req = http.get(BASE_URL, (res) => {
        resolve();
      });
      req.on('error', () => {
        attempts++;
        if (attempts >= retries) {
          reject(new Error(`Servidor não respondeu após ${retries} tentativas`));
        } else {
          setTimeout(check, delay);
        }
      });
      req.setTimeout(1000, () => {
        req.destroy();
        attempts++;
        if (attempts >= retries) {
          reject(new Error('Timeout aguardando servidor'));
        } else {
          setTimeout(check, delay);
        }
      });
    };
    setTimeout(check, 1000); // aguarda 1s antes da primeira tentativa
  });
}

// ── Janela principal ──────────────────────────────────────────
function createWindow() {
  const iconPath = path.join(__dirname, '..', 'frontend', 'static', 'logo.ico');

  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    title: 'Bellart ERP',
    icon: fs.existsSync(iconPath) ? iconPath : undefined,
    backgroundColor: '#0e1018',
    show: false,
    frame: false,
    titleBarStyle: 'hidden',
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js'),
    },
    autoHideMenuBar: true,
  });

  mainWindow.loadURL(BASE_URL);

  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
  });

  // Minimiza para bandeja ao fechar (não encerra o app)
  mainWindow.on('close', (e) => {
    if (!app.isQuitting) {
      e.preventDefault();
      mainWindow.hide();
    }
  });

  mainWindow.on('closed', () => { mainWindow = null; });
}

// ── Bandeja do sistema ────────────────────────────────────────
function createTray() {
  const iconPath = path.join(__dirname, '..', 'frontend', 'static', 'logo.ico');
  const icon = fs.existsSync(iconPath)
    ? nativeImage.createFromPath(iconPath).resize({ width: 16, height: 16 })
    : nativeImage.createEmpty();

  tray = new Tray(icon);
  tray.setToolTip('Bellart ERP');

  const menu = Menu.buildFromTemplate([
    {
      label: 'Abrir Bellart',
      click: () => {
        if (mainWindow) { mainWindow.show(); mainWindow.focus(); }
        else createWindow();
      },
    },
    { type: 'separator' },
    {
      label: 'Sair',
      click: () => { app.isQuitting = true; app.quit(); },
    },
  ]);

  tray.setContextMenu(menu);
  tray.on('double-click', () => {
    if (mainWindow) { mainWindow.show(); mainWindow.focus(); }
    else createWindow();
  });
}

// ── Splash screen ─────────────────────────────────────────────
function createSplash() {
  const splash = new BrowserWindow({
    width: 400,
    height: 260,
    frame: false,
    alwaysOnTop: true,
    backgroundColor: '#0e1018',
    webPreferences: { nodeIntegration: false },
  });
  splash.loadFile(path.join(__dirname, 'splash.html'));
  return splash;
}

// ── Inicialização ─────────────────────────────────────────────
app.whenReady().then(async () => {
  // Adiciona 'BellartElectron' ao userAgent para detecção no frontend
  const { session } = require('electron');
  session.defaultSession.webRequest.onBeforeSendHeaders((details, callback) => {
    details.requestHeaders['User-Agent'] += ' BellartElectron';
    callback({ requestHeaders: details.requestHeaders });
  });
  // Garante instância única
  const gotLock = app.requestSingleInstanceLock();
  if (!gotLock) {
    app.quit();
    return;
  }
  app.on('second-instance', () => {
    if (mainWindow) { mainWindow.show(); mainWindow.focus(); }
  });

  createTray();

  const splash = createSplash();
  startPython();

  try {
    await waitForServer();
    splash.close();
    createWindow();
  } catch (err) {
    splash.close();
    dialog.showErrorBox(
      'Erro ao iniciar',
      `Não foi possível conectar ao servidor Bellart.\n\n${err.message}\n\nVerifique se o Python 3.11 está instalado corretamente e tente novamente.`
    );
    app.quit();
  }
});

// ── Encerramento ──────────────────────────────────────────────
app.on('before-quit', () => {
  app.isQuitting = true;
  if (pythonProcess) { pythonProcess.kill(); pythonProcess = null; }
});

// ── Handlers IPC para controle da janela ─────────────────────
const { ipcMain } = require('electron');

ipcMain.on('window-minimize', () => { if (mainWindow) mainWindow.minimize(); });
ipcMain.on('window-maximize', () => {
  if (!mainWindow) return;
  if (mainWindow.isMaximized()) mainWindow.unmaximize();
  else mainWindow.maximize();
});
ipcMain.on('window-close', () => {
  if (!app.isQuitting && mainWindow) mainWindow.hide();
});
ipcMain.handle('get-version', () => app.getVersion());

app.on('activate', () => {
  if (!mainWindow && app.isReady()) createWindow();
});