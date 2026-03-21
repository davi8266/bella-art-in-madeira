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
const crypto = require('crypto');

// Token único gerado a cada inicialização — só o Electron sabe
const BELLART_SECRET = crypto.randomBytes(32).toString('hex');

// ── Nome do app (garante nome correto na taskbar mesmo em dev) ─
app.setName('Sistema Bella Art in madeira');
app.setAppUserModelId('Sistema Bella Art in madeira');

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

// ── Log em arquivo (para diagnóstico em produção) ─────────────
const LOG_PATH = path.join(app.getPath('userData'), 'bellart-python.log');
let logStream = null;
try {
  const fsSync = require('fs');
  logStream = fsSync.createWriteStream(LOG_PATH, { flags: 'w' });
} catch(e) {}
function logLine(msg) {
  const line = `[${new Date().toISOString()}] ${msg}`;
  console.log(line);
  if (logStream) logStream.write(line + '\n');
}

// ── Subir o backend Python ────────────────────────────────────
let _splashRef = null; // referência para fechar splash em caso de erro antes da janela abrir
function startPython() {
  const pythonExe = findPython();
  const runScript = getRunScript();
  const cwd = getCwd();

  logLine(`[Electron] Python: ${pythonExe}`);
  logLine(`[Electron] Script: ${runScript}`);
  logLine(`[Electron] CWD: ${cwd}`);
  logLine(`[Electron] Log: ${LOG_PATH}`);

  // Verificar se o executável existe antes de tentar iniciar
  if (!isDev && !fs.existsSync(pythonExe)) {
    dialog.showErrorBox(
      'Python não encontrado',
      `O Python embutido não foi encontrado em:\n${pythonExe}\n\nO build pode estar incompleto. Tente reconstruir o aplicativo.`
    );
    app.quit();
    return;
  }

  pythonProcess = spawn(pythonExe, [runScript], {
    cwd,
    env: { ...process.env, PYTHONUNBUFFERED: '1', BELLART_SECRET },
    windowsHide: true,
    shell: false,
  });

  let stderrBuffer = '';

  pythonProcess.stdout.on('data', (data) => {
    logLine(`[Python stdout] ${data.toString().trim()}`);
  });

  pythonProcess.stderr.on('data', (data) => {
    const msg = data.toString().trim();
    logLine(`[Python stderr] ${msg}`);
    stderrBuffer += msg + '\n';
  });

  pythonProcess.on('error', (err) => {
    logLine(`[Python ERRO] ${err.message}`);
    if (_splashRef && !_splashRef.isDestroyed()) _splashRef.close();
    dialog.showErrorBox(
      'Python não encontrado',
      `Não foi possível iniciar o Python.\n\nErro: ${err.message}\n\nLog: ${LOG_PATH}`
    );
    app.quit();
  });

  pythonProcess.on('close', (code) => {
    logLine(`[Python] Encerrado com código ${code}`);
    if (code !== 0 && code !== null) {
      const detail = stderrBuffer.slice(-800) || '(sem saída)';
      if (!mainWindow || mainWindow.isDestroyed()) {
        // Fechou antes da janela abrir — provavelmente erro de import
        if (_splashRef && !_splashRef.isDestroyed()) _splashRef.close();
        dialog.showErrorBox(
          'Erro ao iniciar o servidor',
          `O servidor Python encerrou inesperadamente (código ${code}).\n\nErro:\n${detail}\n\nLog completo: ${LOG_PATH}`
        );
        app.quit();
      } else {
        dialog.showErrorBox(
          'Servidor encerrado',
          `O servidor Bellart encerrou inesperadamente (código ${code}).\n\nFeche e abra o Bellart novamente.\n\nLog: ${LOG_PATH}`
        );
      }
    }
  });
}

// ── Aguardar servidor ─────────────────────────────────────────
function waitForServer(retries = 120, delay = 1000) {
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
    title: 'Sistema Bella Art in madeira',
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

  mainWindow.loadURL(BASE_URL, {
    extraHeaders: 'Cache-Control: no-cache\n'
  });

  // Bloqueia todos os atalhos de DevTools (F12, Ctrl+Shift+I, Ctrl+Shift+J, Ctrl+Shift+C)
  mainWindow.webContents.on('before-input-event', (event, input) => {
    const ctrl = input.control || input.meta;
    const shift = input.shift;
    const key = input.key;
    if (
      key === 'F12' ||
      (ctrl && shift && (key === 'I' || key === 'i')) ||
      (ctrl && shift && (key === 'J' || key === 'j')) ||
      (ctrl && shift && (key === 'C' || key === 'c'))
    ) {
      event.preventDefault();
    }
  });

  // Desativa menu de contexto (clique direito) para remover "Inspecionar Elemento"
  mainWindow.webContents.on('context-menu', (e) => {
    e.preventDefault();
  });

  // Garante que a titlebar aparece após o carregamento da página
  mainWindow.webContents.on('did-finish-load', () => {
    mainWindow.webContents.executeJavaScript(`
      (function() {
        var tb = document.getElementById('titlebar');
        if (tb) {
          tb.style.display = 'flex';
          document.documentElement.classList.add('has-titlebar');
        }
      })();
    `).catch(() => {});
  });

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
  tray.setToolTip('Sistema Bella Art in madeira');

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
  const { session } = require('electron');

  // Limpa o cache para garantir que sempre carrega os arquivos mais recentes
  await session.defaultSession.clearCache();

  // Adiciona 'BellartElectron' ao userAgent e injeta o token secreto em todas as requisições
  session.defaultSession.webRequest.onBeforeSendHeaders((details, callback) => {
    details.requestHeaders['User-Agent'] += ' BellartElectron';
    details.requestHeaders['X-Bellart-Secret'] = BELLART_SECRET;
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
  _splashRef = splash;
  startPython();

  try {
    await waitForServer();
    if (!splash.isDestroyed()) splash.close();
    createWindow();
  } catch (err) {
    if (!splash.isDestroyed()) splash.close();
    dialog.showErrorBox(
      'Erro ao iniciar',
      `O servidor não respondeu após 120 tentativas.\n\nLog de erros salvo em:\n${LOG_PATH}\n\nAbra esse arquivo para ver o erro detalhado do Python.`
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
ipcMain.on('app-quit', () => {
  app.isQuitting = true;
  app.quit();
});
ipcMain.handle('get-version', () => app.getVersion());

app.on('activate', () => {
  if (!mainWindow && app.isReady()) createWindow();
});