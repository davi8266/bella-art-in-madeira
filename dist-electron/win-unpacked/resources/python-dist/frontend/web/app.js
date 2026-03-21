/* ── Paginação ──────────────────────────────────────────────── */
const _PAG = {};  // estado de paginação por tabela

function paginate(tableId, rows, renderFn, pageSize = 20) {
  if (!_PAG[tableId]) _PAG[tableId] = { page: 1, pageSize };
  const state = _PAG[tableId];
  state.pageSize = pageSize;
  const total = rows.length;
  const totalPages = Math.max(1, Math.ceil(total / state.pageSize));
  if (state.page > totalPages) state.page = totalPages;
  const start = (state.page - 1) * state.pageSize;
  const slice = rows.slice(start, start + state.pageSize);
  renderFn(slice);
  _renderPagControls(tableId, state.page, totalPages, total);
}

function _renderPagControls(tableId, page, totalPages, total) {
  const existing = document.getElementById('pag-' + tableId);
  if (existing) existing.remove();
  if (totalPages <= 1) return;
  const table = document.getElementById(tableId);
  if (!table) return;
  const wrap = document.createElement('div');
  wrap.id = 'pag-' + tableId;
  wrap.style.cssText = 'display:flex;align-items:center;justify-content:space-between;padding:8px 4px;gap:8px;';
  const info = document.createElement('span');
  info.style.cssText = 'font-size:12px;color:var(--text-3);';
  info.textContent = `${total} itens — página ${page} de ${totalPages}`;
  const btns = document.createElement('div');
  btns.style.cssText = 'display:flex;gap:4px;';
  [['«', 1], ['‹', page - 1], ['›', page + 1], ['»', totalPages]].forEach(([label, target]) => {
    const b = document.createElement('button');
    b.textContent = label;
    b.style.cssText = `background:var(--surface-raised);border:1px solid var(--border-mid);color:var(--text-2);
      border-radius:6px;padding:3px 9px;font-size:12px;cursor:pointer;transition:all .12s ease;font-family:inherit;`;
    b.disabled = (target < 1 || target > totalPages || target === page);
    if (!b.disabled) b.addEventListener('click', () => {
      _PAG[tableId].page = target;
      b.dispatchEvent(new CustomEvent('pag-change', { bubbles: true, detail: { tableId } }));
    });
    btns.appendChild(b);
  });
  wrap.appendChild(info);
  wrap.appendChild(btns);
  table.insertAdjacentElement('afterend', wrap);
  // Evento customizado para re-render
  wrap.addEventListener('pag-change', (e) => {
    const tid = e.detail.tableId;
    if (tid === 'materias') refreshMaterias();
    if (tid === 'vendas')   { const pid = document.getElementById('v-produto')?.value; if (pid) loadVendasList(pid); }
  });
}


/* ── Auditoria ──────────────────────────────────────────────── */
const _AUDIT_KEY = 'bellart_audit_log';
const _AUDIT_MAX = 200;

function auditLog(acao, detalhes = {}) {
  try {
    const logs = _getAuditLogs();
    const entry = {
      ts: new Date().toISOString(),
      acao,
      detalhes,
      user: (() => { try { return JSON.parse(sessionStorage.getItem('bellart_user') || '{}').username || 'sistema'; } catch { return 'sistema'; } })()
    };
    logs.unshift(entry);
    if (logs.length > _AUDIT_MAX) logs.splice(_AUDIT_MAX);
    localStorage.setItem(_AUDIT_KEY, JSON.stringify(logs));
  } catch(e) {}
}

function _getAuditLogs() {
  try { return JSON.parse(localStorage.getItem(_AUDIT_KEY) || '[]'); } catch { return []; }
}

function showAuditModal() {
  let modal = document.getElementById('audit-modal');
  if (!modal) {
    modal = document.createElement('div');
    modal.id = 'audit-modal';
    modal.style.cssText = 'position:fixed;inset:0;z-index:9997;background:rgba(0,0,0,.6);display:flex;align-items:center;justify-content:center;backdrop-filter:blur(4px);';
    modal.innerHTML = `
      <div style="background:var(--surface-raised);border:1px solid var(--border-mid);border-radius:16px;
        width:min(700px,95vw);max-height:80vh;display:flex;flex-direction:column;box-shadow:var(--shadow-lg);">
        <div style="display:flex;align-items:center;justify-content:space-between;padding:16px 20px;border-bottom:1px solid var(--border);">
          <span style="font-size:14px;font-weight:600;color:var(--text-1);text-transform:uppercase;letter-spacing:.05em;">Log de Auditoria</span>
          <div style="display:flex;gap:8px;">
            <button id="audit-clear" style="background:transparent;border:1px solid rgba(248,113,113,.3);color:var(--red);
              border-radius:6px;padding:4px 12px;font-size:12px;cursor:pointer;font-family:inherit;">Limpar</button>
            <button id="audit-close" style="background:var(--surface-active);border:1px solid var(--border-mid);color:var(--text-2);
              border-radius:6px;padding:4px 12px;font-size:12px;cursor:pointer;font-family:inherit;">Fechar</button>
          </div>
        </div>
        <div style="overflow-y:auto;padding:8px 0;" id="audit-body"></div>
      </div>`;
    document.body.appendChild(modal);
    document.getElementById('audit-close').onclick = () => modal.style.display = 'none';
    document.getElementById('audit-clear').onclick = async () => {
      const ok = await confirmar('Limpar todo o histórico de auditoria?', 'Limpar Log');
      if (ok) { localStorage.removeItem(_AUDIT_KEY); _renderAuditLogs(); }
    };
    modal.addEventListener('click', e => { if (e.target === modal) modal.style.display = 'none'; });
  }
  modal.style.display = 'flex';
  _renderAuditLogs();
}

function _renderAuditLogs() {
  const body = document.getElementById('audit-body');
  if (!body) return;
  const logs = _getAuditLogs();
  if (!logs.length) {
    body.innerHTML = '<div style="text-align:center;padding:32px;color:var(--text-3);font-size:13px;">Nenhum registro ainda</div>';
    return;
  }
  const ICONS = { 'produto_criado':'✚', 'produto_editado':'✎', 'produto_removido':'✕',
    'materia_criada':'✚', 'materia_editada':'✎', 'materia_removida':'✕',
    'venda_criada':'↑', 'venda_removida':'↓', 'backup_exportado':'⬇', 'backup_importado':'⬆',
    'login':'◎', 'taxa_salva':'%' };
  const COLORS = { 'criado':'var(--green)','criada':'var(--green)','editado':'var(--accent)',
    'editada':'var(--accent)','removido':'var(--red)','removida':'var(--red)',
    'exportado':'var(--cyan)','importado':'var(--yellow)','login':'var(--accent2)','salva':'var(--accent)' };
  body.innerHTML = logs.map(l => {
    const d = new Date(l.ts);
    const hora = d.toLocaleString('pt-BR', { day:'2-digit', month:'2-digit', hour:'2-digit', minute:'2-digit' });
    const tipo = l.acao.split('_').pop();
    const cor = COLORS[tipo] || 'var(--text-3)';
    const icon = ICONS[l.acao] || '·';
    const det = Object.entries(l.detalhes || {}).map(([k,v]) => `<span style="color:var(--text-3)">${k}:</span> ${v}`).join(' · ');
    return `<div style="display:flex;align-items:flex-start;gap:12px;padding:10px 20px;border-bottom:1px solid var(--border);">
      <span style="color:${cor};font-size:14px;margin-top:1px;min-width:16px;">${icon}</span>
      <div style="flex:1;min-width:0;">
        <div style="display:flex;justify-content:space-between;align-items:baseline;gap:8px;">
          <span style="font-size:13px;color:var(--text-1);font-weight:500;">${l.acao.replace(/_/g,' ')}</span>
          <span style="font-size:11px;color:var(--text-3);white-space:nowrap;">${hora} · ${l.user}</span>
        </div>
        ${det ? `<div style="font-size:12px;color:var(--text-2);margin-top:2px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${det}</div>` : ''}
      </div>
    </div>`;
  }).join('');
}

/* ============================================================
   Melhorias de alta prioridade — v2
   1. apiFetch: wrapper com tratamento de erros de rede
   2. Validação de formulários
   3. Modal de confirmação antes de deletar
   ============================================================ */

// ── 1. Monitor de conexão ────────────────────────────────────
let _isOnline = true;

function setOnlineStatus(online) {
  if (_isOnline === online) return;
  _isOnline = online;
  let bar = document.getElementById('offline-bar');
  if (!online) {
    if (!bar) {
      bar = document.createElement('div');
      bar.id = 'offline-bar';
      bar.style.cssText = `
        position:fixed; top:0; left:0; right:0; z-index:99999;
        background:#f87171; color:#fff; text-align:center;
        font-size:13px; font-weight:600; padding:6px 12px;
        letter-spacing:.04em; animation: slideDown .3s ease;
      `;
      bar.textContent = '⚠ Sem conexão com o servidor — verifique se o Bellart está rodando';
      document.body.prepend(bar);
    }
  } else {
    if (bar) { bar.style.animation = 'slideUp .3s ease'; setTimeout(() => bar.remove(), 300); }
    showToast('<div class="alert alert-success">✓ Conexão restabelecida</div>');
  }
}

// Wrapper de fetch com tratamento de erros centralizado
async function apiFetch(url, options = {}) {
  try {
    const r = await fetch(url, options);
    setOnlineStatus(true);
    if (!r.ok) {
      const text = await r.text().catch(() => '');
      throw new Error(`HTTP ${r.status}: ${text || r.statusText}`);
    }
    return r;
  } catch (e) {
    if (e instanceof TypeError && e.message.includes('fetch')) {
      setOnlineStatus(false);
      throw new Error('Sem conexão com o servidor');
    }
    setOnlineStatus(true);
    throw e;
  }
}

// Checagem periódica de conexão a cada 10s
setInterval(async () => {
  try {
    await apiFetch('/api/network_info', { cache: 'no-store' });
    setOnlineStatus(true);
  } catch {
    setOnlineStatus(false);
  }
}, 10000);

// ── 2. Modal de confirmação elegante ────────────────────────
function confirmar(mensagem, titulo = 'Confirmar') {
  return new Promise(resolve => {
    let modal = document.getElementById('confirm-modal');
    if (!modal) {
      modal = document.createElement('div');
      modal.id = 'confirm-modal';
      modal.style.cssText = `
        position:fixed; inset:0; z-index:9998;
        background:rgba(0,0,0,.6); display:flex;
        align-items:center; justify-content:center;
        backdrop-filter:blur(4px);
      `;
      modal.innerHTML = `
        <div id="confirm-box" style="
          background:#282d40; border:1px solid rgba(255,255,255,.16);
          border-radius:16px; padding:28px 32px; max-width:400px; width:90%;
          box-shadow:0 24px 48px rgba(0,0,0,.6);
          animation: softAppear .2s ease;
        ">
          <div id="confirm-titulo" style="font-size:16px;font-weight:600;color:#f0f2f8;margin-bottom:10px;"></div>
          <div id="confirm-msg" style="font-size:14px;color:#b0b8d0;margin-bottom:24px;line-height:1.5;"></div>
          <div style="display:flex;gap:10px;justify-content:flex-end;">
            <button id="confirm-nao" style="
              background:transparent; border:1px solid rgba(255,255,255,.16);
              color:#b0b8d0; border-radius:8px; padding:8px 20px;
              font-size:13px; font-weight:500; cursor:pointer;
              transition:all .15s ease; font-family:inherit;
            ">Cancelar</button>
            <button id="confirm-sim" style="
              background:#f87171; border:1px solid #f87171;
              color:#fff; border-radius:8px; padding:8px 20px;
              font-size:13px; font-weight:600; cursor:pointer;
              transition:all .15s ease; font-family:inherit;
            ">Confirmar</button>
          </div>
        </div>
      `;
      document.body.appendChild(modal);
    }

    document.getElementById('confirm-titulo').textContent = titulo;
    document.getElementById('confirm-msg').textContent = mensagem;
    modal.style.display = 'flex';

    const sim = document.getElementById('confirm-sim');
    const nao = document.getElementById('confirm-nao');

    const cleanup = () => { modal.style.display = 'none'; };

    sim.onclick = () => { cleanup(); resolve(true); };
    nao.onclick = () => { cleanup(); resolve(false); };
    modal.onclick = (e) => { if (e.target === modal) { cleanup(); resolve(false); } };
  });
}

// ── 3. Validação de formulários ─────────────────────────────
function validarProduto(nome, precos) {
  if (!nome || !nome.trim()) {
    showToast('<div class="alert alert-warning">⚠ Nome do produto é obrigatório</div>');
    document.getElementById('p-nome')?.focus();
    return false;
  }
  if (nome.trim().length < 2) {
    showToast('<div class="alert alert-warning">⚠ Nome deve ter pelo menos 2 caracteres</div>');
    return false;
  }
  for (const [plat, val] of Object.entries(precos)) {
    if (val < 0) {
      showToast(`<div class="alert alert-warning">⚠ Preço da ${plat} não pode ser negativo</div>`);
      return false;
    }
  }
  return true;
}

function validarMateria(nome, estoque, custo) {
  if (!nome || !nome.trim()) {
    showToast('<div class="alert alert-warning">⚠ Nome da matéria-prima é obrigatório</div>');
    document.getElementById('m-nome')?.focus();
    return false;
  }
  if (estoque < 0) {
    showToast('<div class="alert alert-warning">⚠ Estoque não pode ser negativo</div>');
    return false;
  }
  if (custo < 0) {
    showToast('<div class="alert alert-warning">⚠ Custo médio não pode ser negativo</div>');
    return false;
  }
  return true;
}

function validarVenda(produtoId, plataformaId, quantidade) {
  if (!produtoId) {
    showToast('<div class="alert alert-warning">⚠ Selecione um produto</div>');
    return false;
  }
  if (!plataformaId) {
    showToast('<div class="alert alert-warning">⚠ Selecione uma plataforma</div>');
    return false;
  }
  if (!quantidade || quantidade < 1 || !Number.isInteger(Number(quantidade))) {
    showToast('<div class="alert alert-warning">⚠ Quantidade deve ser um número inteiro maior que zero</div>');
    return false;
  }
  return true;
}

let productsCacheForSearch = [];

async function loadProdutos() {
  try{
    const r = await apiFetch('/api/produtos?ts=' + Date.now(), { cache: 'no-store' });
    const data = await r.json();
    productsCacheForSearch = data;
    const datalist = document.getElementById('produto-datalist');
    const input = document.getElementById('produto-input');
    const hidden = document.getElementById('produto');
    if (!datalist || !input || !hidden) return;
    const prev = hidden.value;
    datalist.innerHTML = '';
    data.forEach(p => {
      const o = document.createElement('option');
      o.value = p.id + ' - ' + p.nome;
      datalist.appendChild(o);
    });
    if (data.length) {
      let targetId = null;
      const hasProdSel = !!(typeof prodSel !== 'undefined' && prodSel && data.some(d=>String(d.id)===String(prodSel.id)));
      if (hasProdSel) targetId = prodSel.id;
      else if (prev && data.some(d=>String(d.id)===String(prev))) targetId = prev;
      else targetId = data[0].id;
      hidden.value = targetId;
      const targetP = data.find(d => String(d.id) === String(targetId));
      if (targetP) input.value = targetP.id + ' - ' + targetP.nome;
      await loadRelatorios();
    } else {
      hidden.value = '';
      input.value = '';
      prodSel = null;
      clearProdutoView();
      clearRelatoriosView();
    }
  } catch(e){
    showToast('<div class="alert alert-warning">Falha ao carregar produtos</div>');
  }
}

let chartLucro;
let chartVendasRel;

function format(v) {
  try {
    return 'R$ ' + Number(v||0).toLocaleString('pt-BR', {minimumFractionDigits:2, maximumFractionDigits:2});
  } catch {
    const n = Number(v||0);
    return 'R$ ' + n.toFixed(2);
  }
}

let estoqueMateriaisCache = [];
let estoqueMateriaisSelecionados = null;
let fretePorProduto = {};

function normalizeFretePlatformName(nome){
  const n = String(nome||'').toLowerCase();
  if (n.includes('mercado livre')) return 'Mercado Livre';
  if (n.includes('magalu')) return 'Magalu';
  if (n.includes('shopee')) return 'Shopee';
  return String(nome||'').trim();
}

let ignoreMlFixoPorProduto = {};
let ignoreMagaluFixoPorProduto = {};
try {
  const storedIgnore = localStorage.getItem('ignoreMlFixoPorProduto');
  if (storedIgnore) {
    const parsedIgnore = JSON.parse(storedIgnore);
    if (parsedIgnore && typeof parsedIgnore === 'object') ignoreMlFixoPorProduto = parsedIgnore;
  }
  const storedIgnoreMag = localStorage.getItem('ignoreMagaluFixoPorProduto');
  if (storedIgnoreMag) {
    const parsedIgnoreMag = JSON.parse(storedIgnoreMag);
    if (parsedIgnoreMag && typeof parsedIgnoreMag === 'object') ignoreMagaluFixoPorProduto = parsedIgnoreMag;
  }
} catch(e) {
  ignoreMlFixoPorProduto = {};
  ignoreMagaluFixoPorProduto = {};
}

function isIgnoreMlFixo(produtoId){
  const pid = String(produtoId||'');
  if (!pid) return false;
  return !!ignoreMlFixoPorProduto[pid];
}

function isIgnoreMagaluFixo(produtoId){
  const pid = String(produtoId||'');
  if (!pid) return false;
  return !!ignoreMagaluFixoPorProduto[pid];
}

function setIgnoreMlFixo(produtoId, flag){
  const pid = String(produtoId||'');
  if (!pid) return;
  if (flag) ignoreMlFixoPorProduto[pid] = true;
  else delete ignoreMlFixoPorProduto[pid];
  try {
    localStorage.setItem('ignoreMlFixoPorProduto', JSON.stringify(ignoreMlFixoPorProduto));
  } catch(e) {
  }
}

function setIgnoreMagaluFixo(produtoId, flag){
  const pid = String(produtoId||'');
  if (!pid) return;
  if (flag) ignoreMagaluFixoPorProduto[pid] = true;
  else delete ignoreMagaluFixoPorProduto[pid];
  try {
    localStorage.setItem('ignoreMagaluFixoPorProduto', JSON.stringify(ignoreMagaluFixoPorProduto));
  } catch(e) {
  }
}

function getFreteForProduto(produtoId, plataforma){
  if (!produtoId || !plataforma) return 0;
  const pid = String(produtoId);
  const map = fretePorProduto[pid];
  if (!map) return 0;
  const key = normalizeFretePlatformName(plataforma);
  const v = map[key];
  return typeof v === 'number' && !isNaN(v) ? v : 0;
}

async function loadRelatorios() {
  const pidEl = document.getElementById('produto');
  const pid = pidEl && pidEl.value ? pidEl.value : '';

  // Atualizar foto do produto no relatório
  const imgRel = document.getElementById('rel-p-photo');
  if (imgRel) {
    const ts = Date.now();
    imgRel.src = pid ? `/static/uploads/${pid}.png?ts=${ts}` : '/brand/produtos.png';
    imgRel.onerror = () => { imgRel.src = '/brand/produtos.png'; };
  }

  if (!pid){
    clearRelatoriosView();
    return;
  }
  const r = await apiFetch('/api/relatorios/' + pid);
  const rows = await r.json();
  const rowsCalc = rows.map(row=>{
    const platName = String(row.plataforma || '');
    const lowerPlat = platName.toLowerCase();
    const isMl = lowerPlat.includes('mercado livre');
    const isMag = lowerPlat.includes('magalu');
    const ignoreMlFixo = isMl && isIgnoreMlFixo(pid);
    const ignoreMagFixo = isMag && isIgnoreMagaluFixo(pid);
    const frete = getFreteForProduto(pid, platName);
    const bruto = Number(row.bruto||0);
    const impostosBase = Number(row.impostos_total||0);
    const fixoBase = Number(row.fixo||0);
    let impostosAdj = impostosBase;
    let receitaBase = Number(row.receita||0);
    if (ignoreMlFixo || ignoreMagFixo) {
      impostosAdj = impostosBase - fixoBase;
      receitaBase = receitaBase + fixoBase;
    }
    const custoTotal = Number(row.custo_total||0);
    const receitaAdj = receitaBase - frete;
    const lucroAdj = receitaAdj - custoTotal;
    const margemAdj = bruto ? (lucroAdj / bruto) : 0;
    return Object.assign({}, row, {impostos_total: impostosAdj, receita_calc: receitaAdj, lucro_calc: lucroAdj, margem_calc: margemAdj});
  });

  // Cálculo do Produto
  const tbodyCalc = document.querySelector('#calc-prod tbody');
  if (tbodyCalc) {
    tbodyCalc.innerHTML = '';
    rowsCalc.forEach(row=>{
      const tr = document.createElement('tr');
      const platName = String(row.plataforma || '');
      const platCls = platName.toLowerCase().includes('mercado') ? 'plat-ml' : platName.toLowerCase().includes('magalu') ? 'plat-mag' : platName.toLowerCase().includes('shopee') ? 'plat-sh' : '';
      if (platCls) tr.classList.add(platCls);
      const bruto = Number(row.bruto||0);
      const impostos = Number(row.impostos_total||0);
      const receita = Number(row.receita_calc||0);
      const lucro = Number(row.lucro_calc||0);
      const margem = Number(row.margem_calc||0);
      tr.innerHTML = `<td>${row.plataforma}</td><td></td><td>${format(impostos)}</td><td>${format(receita)}</td><td>${format(lucro)}</td><td>${(margem*100).toFixed(2)}%</td>`;
      const precoTd = tr.children[1];
      if (precoTd) {
        const input = document.createElement('input');
        input.type = 'number';
        input.step = '0.01';
        input.className = 'form-control form-control-sm';
        input.value = bruto.toFixed(2);
        input.dataset.plataforma = platName;
        input.addEventListener('change', async ()=>{
          const raw = String(input.value || '').replace(',', '.');
          const val = parseFloat(raw);
          if (!isFinite(val)) return;
          let platApi = platName;
          // Removed normalization to allow distinct ML tier prices
          // const lower = platName.toLowerCase();
          // if (lower.includes('mercado livre')) {
          //   platApi = 'Mercado Livre';
          // }
          try {
            await apiFetch(`/api/prices/${pid}`, {
              method:'POST',
              headers:{'Content-Type':'application/json'},
              body: JSON.stringify({plataforma: platApi, preco: val})
            });
            await loadRelatorios();
          } catch(e) {
          }
        });
        precoTd.appendChild(input);
      }
      tbodyCalc.appendChild(tr);
    });
    const custo = rows.length ? rows[0].custo_total : 0;
    const custoMats = rows.length ? rows[0].custo_mats : 0;
    const lucroMax = rowsCalc.reduce((m,x)=> Math.max(m, Number(x.lucro_calc||0)), 0);
    const margemMax = rowsCalc.reduce((m,x)=> Math.max(m, Number(x.margem_calc||0)), 0);
    const elCusto = document.getElementById('calc-custo'); if (elCusto) elCusto.textContent = format(custo);
    
    const elLucro = document.getElementById('calc-lucro-max'); if (elLucro) elLucro.textContent = format(lucroMax);
    const elMargem = document.getElementById('calc-margem-max'); if (elMargem) elMargem.textContent = (margemMax*100).toFixed(2) + '%';
  }

  // Materiais breakdown
  const tbodyMats = document.querySelector('#rel-mats tbody');
  if (tbodyMats) {
    tbodyMats.innerHTML = '';
    if (rows.length > 0 && rows[0].materiais) {
        rows[0].materiais.forEach(mat => {
            const tr = document.createElement('tr');
            tr.innerHTML = `<td>${mat.nome}</td><td>${Number(mat.qtd).toLocaleString('pt-BR')}</td><td>${format(mat.custo_unit)}</td><td>${format(mat.custo_item)}</td>`;
            tbodyMats.appendChild(tr);
        });
    }
  }

  // Gráficos: Lucro e Impostos
  const lucroLabels = rowsCalc.map(r => r.plataforma);
  const lucroData = rowsCalc.map(r => r.lucro_calc);
  const impLabels = rowsCalc.map(r => r.plataforma);
  const impData = rowsCalc.map(r => r.impostos_total);
  if (chartLucro) chartLucro.destroy();
  chartLucro = new Chart(document.getElementById('chartLucro'), {
    type: 'bar',
    data: { labels: lucroLabels, datasets: [{ label: 'Lucro', data: lucroData, borderWidth: 0, backgroundColor: '#5A2E2E' }] },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }
  });
  const impCanvas = document.getElementById('chartImpostos');
  if (impCanvas) {
    if (window.chartImpostos) window.chartImpostos.destroy();
    window.chartImpostos = new Chart(impCanvas, {
      type: 'pie',
      data: { labels: impLabels, datasets: [{ data: impData, backgroundColor: ['#3E4147','#DFBA69','#2A2C31'] }] },
      options: { responsive: true, maintainAspectRatio: false }
    });
  }

  // Vendas do Produto (todas)
  const vr = await apiFetch(`/api/vendas/${pid}`);
  const vendas = await vr.json();
  await ensureRelPlatforms();
  const filtered = filterRelVendas(vendas);
  
  const platFin = {};
  rowsCalc.forEach(r => { platFin[r.plataforma] = r; });

  function findPlatFinForVendaPlat(venda){
    const nomePlat = String(venda.plataforma || '');
    const mlMode = venda.ml_mode || null;
    if (platFin[nomePlat]) return platFin[nomePlat];
    const lower = nomePlat.toLowerCase();
    if (lower.includes('mercado livre') || lower.includes('mercado')){
      if (mlMode === 'premium'){
        return platFin['Mercado Livre Premium'] || platFin['Mercado Livre Clássico'] || null;
      }
      if (mlMode === 'classico'){
        return platFin['Mercado Livre Clássico'] || platFin['Mercado Livre Premium'] || null;
      }
      return platFin['Mercado Livre Clássico'] || platFin['Mercado Livre Premium'] || null;
    }
    return null;
  }

  const totalQtd = filtered.reduce((s,v)=> s + Number(v.quantidade||0), 0);
  const totalRec = filtered.reduce((s,v)=> s + Number(v.quantidade||0) * Number(v.preco||0), 0);
  
  let totalLucro = 0;
  filtered.forEach(v => {
      const pfin = findPlatFinForVendaPlat(v);
      if (pfin) {
          const price = Number(v.preco||0);
          const qty = Number(v.quantidade||0);
          let fixoVenda = Number(pfin.fixo||0);
          const vplatLower = String(v.plataforma||'').toLowerCase();
          const isMl = vplatLower.includes('mercado livre');
          const isMag = vplatLower.includes('magalu');
          if ((isMl && isIgnoreMlFixo(pid)) || (isMag && isIgnoreMagaluFixo(pid))) {
            fixoVenda = 0;
          }
          const fees = price * (Number(pfin.taxa||0) + Number(pfin.imposto||0)) + fixoVenda;
          const cost = Number(pfin.custo_total||0);
          const frete = getFreteForProduto(pid, v.plataforma);
          const profitUnit = price - fees - cost - frete;
          totalLucro += profitUnit * qty;
      } else {
          // If platform not found (maybe renamed or deleted?), assume roughly same margin or just 0 cost?
          // Safest is to just take price - cost if we have cost, ignoring fees?
          // Or just 0 profit.
          // Let's try to find a default cost.
          const cost = rows.length ? Number(rows[0].custo_total||0) : 0;
          totalLucro += (Number(v.preco||0) - cost) * Number(v.quantidade||0);
      }
  });

  const media = totalQtd ? (totalRec / totalQtd) : 0;
  const count = filtered.length;
  const ultima = (filtered[0] && filtered[0].data) ? filtered[0].data : '-';
  const vtbody = document.querySelector('#rel-vendas tbody');
  if (vtbody){
    vtbody.innerHTML = '';
    filtered.forEach(v=>{
      const tr = document.createElement('tr');
      tr.innerHTML = `<td>${v.data}</td><td>${v.plataforma}</td><td>${v.quantidade}</td><td>${format(Number(v.preco||0))}</td><td>${format(Number(v.preco||0)*Number(v.quantidade||0))}</td>`;
      vtbody.appendChild(tr);
    });
  }
  const elQtd = document.getElementById('rel-v-qtd'); if (elQtd) elQtd.textContent = String(totalQtd);
  const elRec = document.getElementById('rel-v-receita'); if (elRec) elRec.textContent = format(totalRec);
  const elLucroRel = document.getElementById('rel-v-lucro'); if (elLucroRel) elLucroRel.textContent = format(totalLucro);
  const elMed = document.getElementById('rel-v-media'); if (elMed) elMed.textContent = format(media);
  const elCnt = document.getElementById('rel-v-count'); if (elCnt) elCnt.textContent = String(count);
  const elUlt = document.getElementById('rel-v-ultima'); if (elUlt) elUlt.textContent = ultima;

  const series = buildRelVendasSeries(filtered);
  if (chartVendasRel) chartVendasRel.destroy();
  chartVendasRel = new Chart(document.getElementById('chartVendasRel'), {
    type: 'line',
    data: { labels: series.labels, datasets: [{ label: 'Receita', data: series.values, borderColor: '#3E4147', backgroundColor: 'rgba(62,65,71,.2)', tension: 0.2 }] },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { ticks: { callback: (v)=> Number(v).toLocaleString('pt-BR') } } } }
  });

  // Resumo de Vendas via QR
  const vqr = await apiFetch(`/api/vendas_qr/${pid}`);
  const vendasQR = await vqr.json();
  const totalQtdQR = vendasQR.reduce((s,v)=> s + Number(v.quantidade||0), 0);
  const totalRecQR = vendasQR.reduce((s,v)=> s + Number(v.quantidade||0) * Number(v.preco||0), 0);
  const mediaQR = totalQtdQR ? (totalRecQR / totalQtdQR) : 0;
  const countQR = vendasQR.length;
  const ultimaQR = (vendasQR[0] && vendasQR[0].data) ? vendasQR[0].data : '-';
  const qtbody = document.querySelector('#rel-vendas-qr tbody');
  if (qtbody){
    qtbody.innerHTML = '';
    vendasQR.forEach(v=>{
      const tr = document.createElement('tr');
      tr.innerHTML = `<td>${v.data}</td><td>${v.plataforma}</td><td>${v.quantidade}</td><td>${format(Number(v.preco||0))}</td><td>${format(Number(v.preco||0)*Number(v.quantidade||0))}</td>`;
      qtbody.appendChild(tr);
    });
  }
  const elQtdQR = document.getElementById('qr-v-qtd'); if (elQtdQR) elQtdQR.textContent = String(totalQtdQR);
  const elRecQR = document.getElementById('qr-v-receita'); if (elRecQR) elRecQR.textContent = format(totalRecQR);
  const elMedQR = document.getElementById('qr-v-media'); if (elMedQR) elMedQR.textContent = format(mediaQR);
  const elCntQR = document.getElementById('qr-v-count'); if (elCntQR) elCntQR.textContent = String(countQR);
  const elUltQR = document.getElementById('qr-v-ultima'); if (elUltQR) elUltQR.textContent = ultimaQR;
  const seriesQR = buildRelVendasSeries(vendasQR);
  const chartElQR = document.getElementById('chartVendasQR');
  if (chartElQR){
    if (window.chartVendasQR) window.chartVendasQR.destroy();
    window.chartVendasQR = new Chart(chartElQR, { type:'line', data:{ labels: seriesQR.labels, datasets:[{ label:'Receita (QR)', data: seriesQR.values, borderColor:'#2A2C31', backgroundColor:'rgba(42,44,49,.2)', tension:0.2 }] }, options:{ responsive:true, maintainAspectRatio:false, plugins:{ legend:{ display:false } }, scales:{ y:{ ticks:{ callback:(v)=> Number(v).toLocaleString('pt-BR') } } } } });
  }
}

let relPlatformsCache = [];
async function ensureRelPlatforms(){
  if (relPlatformsCache.length) return;
  const r = await apiFetch('/api/platforms');
  relPlatformsCache = await r.json();
  const sel = document.getElementById('rel-v-plat');
  if (sel){
    sel.innerHTML='';
    const oAll = document.createElement('option'); oAll.value = 'all'; oAll.textContent = 'Todas'; sel.appendChild(oAll);
    relPlatformsCache.forEach(p=>{ const o = document.createElement('option'); o.value = String(p.id); o.textContent = p.nome; sel.appendChild(o); });
    sel.value = 'all';
    sel.addEventListener('change', ()=> loadRelatorios());
  }
  const s = document.getElementById('rel-v-start'); const e = document.getElementById('rel-v-end');
  if (s) s.addEventListener('change', ()=> loadRelatorios());
  if (e) e.addEventListener('change', ()=> loadRelatorios());
  const psel = document.getElementById('rel-v-period');
  if (psel) psel.addEventListener('change', ()=>{ applyRelPeriod(psel.value); loadRelatorios(); });
}

function pad2(n){ return String(n).padStart(2,'0'); }
function formatDateYMD(d){ return `${d.getFullYear()}-${pad2(d.getMonth()+1)}-${pad2(d.getDate())}`; }
function applyRelPeriod(period){
  const today = new Date();
  let start = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  let end = new Date(start);
  if (period === 'dia'){
  } else if (period === 'semana'){
    const day = start.getDay();
    const diffToMonday = (day + 6) % 7;
    start = new Date(start.getFullYear(), start.getMonth(), start.getDate() - diffToMonday);
    end = new Date(start.getFullYear(), start.getMonth(), start.getDate() + 6);
  } else if (period === 'mes'){
    start = new Date(start.getFullYear(), start.getMonth(), 1);
    end = new Date(start.getFullYear(), start.getMonth()+1, 0);
  } else if (period === 'ano'){
    start = new Date(start.getFullYear(), 0, 1);
    end = new Date(start.getFullYear(), 11, 31);
  } else {
    return;
  }
  const sEl = document.getElementById('rel-v-start');
  const eEl = document.getElementById('rel-v-end');
  if (sEl) sEl.value = formatDateYMD(start);
  if (eEl) eEl.value = formatDateYMD(end);
}

function filterRelVendas(vendas){
  const sEl = document.getElementById('rel-v-start'); const s = (sEl && sEl.value) ? sEl.value : '';
  const eEl = document.getElementById('rel-v-end'); const e = (eEl && eEl.value) ? eEl.value : '';
  const pEl = document.getElementById('rel-v-plat'); const plat = (pEl && pEl.value) ? pEl.value : 'all';
  return vendas.filter(v=>{
    const okPlat = plat==='all' || String(plat)===String(getPlatIdByName(v.plataforma));
    const d = v.data || '';
    const okStart = !s || d >= s;
    const okEnd = !e || d <= e;
    return okPlat && okStart && okEnd;
  });
}

function getPlatIdByName(nome){
  const p = relPlatformsCache.find(x=> String(x.nome)===String(nome));
  return p ? p.id : null;
}

function buildRelVendasSeries(vendas){
  const map = {};
  vendas.forEach(v=>{ const d = v.data; const t = Number(v.quantidade||0)*Number(v.preco||0); map[d] = (map[d]||0)+t; });
  const labels = Object.keys(map).sort();
  const values = labels.map(k=> map[k]);
  return {labels, values};
}

document.addEventListener('DOMContentLoaded', () => {
  try {
    console.log('App starting...');
    const exitBtn1 = document.getElementById('nav-exit');
    const exitModal = document.getElementById('exit-modal');
    const exitConfirm = document.getElementById('exit-confirm');
    const exitCancel = document.getElementById('exit-cancel');
    function doQuit(){ if(window.electronAPI && window.electronAPI.appQuit){ window.electronAPI.appQuit(); } else { apiFetch('/api/exit', {method:'POST'}); } }
    function cancelExit(){ if(exitModal) exitModal.classList.add('d-none'); const relLink = document.querySelector('#side-menu .item[data-tab="rel"]'); if(relLink) relLink.click(); }
    window.triggerExitFlow = function(){ if(exitModal) exitModal.classList.remove('d-none'); };
    if (exitBtn1 && exitModal){ exitBtn1.addEventListener('click', (e)=>{ e.preventDefault(); window.triggerExitFlow(); }); }
    if (exitConfirm){ exitConfirm.addEventListener('click', ()=>{ if(exitModal) exitModal.classList.add('d-none'); doQuit(); }); }
    if (exitCancel){ exitCancel.addEventListener('click', cancelExit); }
    if (exitModal){ exitModal.addEventListener('click', (e)=>{ if(e.target === exitModal) cancelExit(); }); }
    

    const profBtn = document.getElementById('nav-profile');
    if (profBtn){ profBtn.addEventListener('click', ()=> openProfile()); }
    const lsub = document.getElementById('login-submit');
    if (lsub) lsub.addEventListener('click', doLogin);
    const pcs = document.getElementById('profile-close');
    const psv = document.getElementById('profile-save');
    if (pcs) pcs.addEventListener('click', ()=> toggleProfile(false));
    if (psv) psv.addEventListener('click', saveProfile);
    initAuth();
  } catch(e) {
    console.error('Fatal init error:', e);
    alert('Fatal init error: ' + e.message);
  }
});

function setupTabs(){
  const links = document.querySelectorAll('#side-menu .item');
  links.forEach(a=>a.addEventListener('click', (e)=>{
    e.preventDefault();
    links.forEach(l=>l.classList.remove('active'));
    a.classList.add('active');
    const tab = a.dataset.tab;
    document.querySelectorAll('main section').forEach(s=>s.classList.add('d-none'));
    const tgt = document.getElementById(`tab-${tab}`);
    if (tgt) {
      tgt.classList.remove('d-none');
      softAppear(tgt);
    }
    if (tab === 'rel') {
        const activeSub = document.querySelector('#rel-subtabs button.active');
        if (activeSub && activeSub.dataset.target === 'rel-store') loadStoreReport();
        else loadRelatorios();
    }
    if (tab === 'mat') refreshMaterias();
    if (tab === 'cfg') renderTaxas();
    if (tab === 'qr') initQRTab();
  }));
}

function initAuth(){
  try {
    const u = JSON.parse(localStorage.getItem('authUser')||'null');
    // Remove loader
    const loader = document.getElementById('init-loader');
    if (loader) loader.remove();
    
    if (!u){ toggleLogin(true); }
    else { toggleLogin(false); continueApp(); }
  } catch (e) {
    console.error('Auth error:', e);
    // Remove loader even on error so user sees the error
    const loader = document.getElementById('init-loader');
    if (loader) loader.remove();
    // Fallback to login if auth fails
    toggleLogin(true);
  }
}
function toggleLogin(show){
  const screen = document.getElementById('login-screen');
  const shell = document.getElementById('app-shell');
  if (screen) screen.classList.toggle('d-none', !show);
  if (shell) shell.classList.toggle('d-none', !!show);
  const pre = document.getElementById('pre-auth');
  if (pre && !show){
    pre.remove();
  }
}
function toggleProfile(show){
  const m = document.getElementById('profile-modal'); if (m) m.classList.toggle('d-none', !show);
}
async function doLogin(){
  const user = document.getElementById('login-user').value.trim();
  const pass = document.getElementById('login-pass').value;
  const r = await apiFetch('/api/login', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({username:user, password:pass})});
  const j = await r.json();
  if (j && j.ok){ localStorage.setItem('authUser', JSON.stringify(j.user)); document.getElementById('profile-user').value = j.user.username; toggleLogin(false); continueApp(); }
  else { const msg = document.getElementById('login-msg'); if (msg) msg.innerHTML = '<div class="alert alert-danger">Login inválido</div>'; }
}
function openProfile(){
  const u = JSON.parse(localStorage.getItem('authUser')||'null');
  if (!u){ toggleLogin(true); return; }
  document.getElementById('profile-user').value = u.username || '';
  document.getElementById('profile-old').value = '';
  document.getElementById('profile-new').value = '';
  const msg = document.getElementById('profile-msg'); if (msg) msg.innerHTML = '';
  toggleProfile(true);
}
async function saveProfile(){
  const u = JSON.parse(localStorage.getItem('authUser')||'null');
  if (!u) { toggleLogin(true); return; }
  const old = document.getElementById('profile-old').value;
  const nw = document.getElementById('profile-new').value;
  const r = await apiFetch('/api/users/password', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({username: u.username, old: old, new: nw})});
  const j = await r.json();
  const msg = document.getElementById('profile-msg');
  if (j && j.ok){ if (msg) msg.innerHTML = '<div class="alert alert-success">Senha alterada</div>'; }
  else { if (msg) msg.innerHTML = '<div class="alert alert-danger">Senha atual incorreta</div>'; }
}

function exportTableCSV(tableId, filename){
  const table = document.getElementById(tableId);
  if (!table) return;
  const rows = [];
  const ths = table.querySelectorAll('thead th');
  rows.push(Array.from(ths).map(th => '"' + String(th.textContent||'').replace(/"/g,'""') + '"').join(','));
  table.querySelectorAll('tbody tr').forEach(tr => {
    const tds = tr.querySelectorAll('td');
    rows.push(Array.from(tds).map(td => '"' + String(td.textContent||'').replace(/"/g,'""') + '"').join(','));
  });
  const blob = new Blob([rows.join('\n')], {type: 'text/csv;charset=utf-8;'});
  const fname = filename || (tableId + '.csv');
  if (window.navigator && typeof window.navigator.msSaveOrOpenBlob === 'function') {
    window.navigator.msSaveOrOpenBlob(blob, fname);
    return;
  }
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = fname;
  a.style.display = 'none';
  document.body.appendChild(a);
  if ('download' in a) {
    a.click();
  } else {
    window.open(url);
  }
  setTimeout(function(){ URL.revokeObjectURL(url); a.remove(); }, 200);
}

function downloadCanvasAsPNG(canvasId, filename){
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const dataURL = canvas.toDataURL('image/png');
  const a = document.createElement('a');
  a.href = dataURL;
  a.download = filename || (canvasId + '.png');
  document.body.appendChild(a);
  a.click();
  setTimeout(()=> a.remove(), 200);
}

function initRelatoriosControls(){
  const relRef = document.getElementById('rel-refresh'); if (relRef) relRef.addEventListener('click', ()=> loadRelatorios());
  const calcRef = document.getElementById('calc-refresh'); if (calcRef) calcRef.addEventListener('click', ()=> loadRelatorios());
  initRelatoriosSubTabs();
}

let storeChart = null;
let currentStoreFilter = 'all';

async function loadStoreReport(startDate = null, endDate = null) {
    try {
        let url = '/api/reports/store';
        const params = [];
        if (startDate) params.push(`start=${startDate}`);
        if (endDate) params.push(`end=${endDate}`);
        if (params.length > 0) url += '?' + params.join('&');
        
        const r = await fetch(url);
        const data = await r.json();
        
        const setText = (id, val) => { const el = document.getElementById(id); if(el) el.textContent = format(val); };
        setText('store-receita', data.total_receita);
        setText('store-mat', data.total_custo_materiais);
        setText('store-taxas', data.total_taxas);
        setText('store-lucro', data.total_lucro);
        setText('store-estoque', data.valor_estoque_materiais);
        updateStoreEstoqueTag(false);
        
        setText('store-d-receita', data.total_receita);
        setText('store-d-mat', data.total_custo_materiais);
        setText('store-d-taxas', data.total_taxas);
        const elLucro = document.getElementById('store-d-lucro');
        if(elLucro) elLucro.textContent = format(data.total_lucro);
        
        const elMargem = document.getElementById('store-d-margem');
        if(elMargem) elMargem.textContent = (data.margem_geral * 100).toFixed(2) + '%';
        
        const ctx = document.getElementById('storeChart');
        if (ctx) {
            if (storeChart) storeChart.destroy();
            storeChart = new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: ['Lucro', 'Materiais', 'Taxas'],
                    datasets: [{
                        data: [data.total_lucro, data.total_custo_materiais, data.total_taxas],
                        backgroundColor: ['#198754', '#6c757d', '#ffc107'],
                        borderWidth: 0
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: 'right' }
                    }
                }
            });
        }
        
        // Render ranking table
        const tbody = document.querySelector('#store-ranking-table tbody');
        if (tbody) {
            tbody.innerHTML = '';
            if (data.ranking_produtos && data.ranking_produtos.length > 0) {
                data.ranking_produtos.forEach((prod, index) => {
                    const tr = document.createElement('tr');
                    tr.innerHTML = `
                        <th scope="row">${index + 1}</th>
                        <td>${prod.nome}</td>
                        <td class="text-center">${prod.qtd}</td>
                        <td class="text-end">${format(prod.receita)}</td>
                        <td class="text-end text-success">${format(prod.lucro)}</td>
                    `;
                    tbody.appendChild(tr);
                });
            } else {
                tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted">Nenhuma venda no período</td></tr>';
            }
        }
        
    } catch (e) {
        console.error(e);
        showToast('<div class="alert alert-danger">Erro ao carregar relatório da loja</div>');
    }
}

function setStoreFilter(type) {
    currentStoreFilter = type;
    
    // Update active button state
    document.querySelectorAll('#rel-store .btn-group button').forEach(b => {
        if (b.getAttribute('onclick').includes(`'${type}'`)) {
            b.classList.add('active');
        } else {
            b.classList.remove('active');
        }
    });

    let start = null;
    let end = null;
    const now = new Date();
    
    // Helper to format YYYY-MM-DD
    const fmt = d => d.toISOString().split('T')[0];
    
    if (type === 'today') {
        start = fmt(now);
        end = fmt(now);
    } else if (type === 'week') {
        // Current week (Monday to Sunday) or last 7 days? Let's assume start of week (Sunday)
        const day = now.getDay(); // 0 (Sun) to 6 (Sat)
        const diff = now.getDate() - day; // adjust when day is sunday
        const s = new Date(now);
        s.setDate(diff);
        start = fmt(s);
        end = fmt(now);
    } else if (type === 'month') {
        const s = new Date(now.getFullYear(), now.getMonth(), 1);
        start = fmt(s);
        const e = new Date(now.getFullYear(), now.getMonth() + 1, 0);
        end = fmt(e);
    } else if (type === 'year') {
        const s = new Date(now.getFullYear(), 0, 1);
        start = fmt(s);
        const e = new Date(now.getFullYear(), 11, 31);
        end = fmt(e);
    } else if (type === 'all') {
        start = null;
        end = null;
    }
    
    // Clear custom inputs if preset is selected
    if (type !== 'custom') {
        document.getElementById('store-date-start').value = start || '';
        document.getElementById('store-date-end').value = end || '';
    }
    
    loadStoreReport(start, end);
}

function applyStoreDateFilter() {
    // Custom filter
    const start = document.getElementById('store-date-start').value;
    const end = document.getElementById('store-date-end').value;
    
    // Deselect preset buttons
    document.querySelectorAll('#rel-store .btn-group button').forEach(b => b.classList.remove('active'));
    
    loadStoreReport(start, end);
}

async function initEstoqueFilter(){
  const card = document.getElementById('store-estoque-card');
  if (card){
    card.addEventListener('click', openEstoqueModal);
  }
  const closeBtn = document.getElementById('estoque-close');
  if (closeBtn){
    closeBtn.addEventListener('click', ()=> toggleEstoqueModal(false));
  }
  const allChk = document.getElementById('estoque-all');
  if (allChk){
    allChk.addEventListener('change', ()=>{
      if (allChk.checked){
        estoqueMateriaisSelecionados = null;
        syncEstoqueSelectionUI();
        aplicarEstoqueSelecao();
      }
    });
  }
  const clearBtn = document.getElementById('estoque-clear');
  if (clearBtn){
    clearBtn.addEventListener('click', ()=>{
      estoqueMateriaisSelecionados = [];
      syncEstoqueSelectionUI();
      aplicarEstoqueSelecao();
    });
  }
  const applyBtn = document.getElementById('estoque-apply');
  if (applyBtn){
    applyBtn.addEventListener('click', aplicarEstoqueSelecao);
  }
  
  const tbody = document.querySelector('#estoque-mats tbody');
  if (tbody){
    tbody.addEventListener('change', (e)=>{
      if (e.target && e.target.classList.contains('estoque-mat-chk')){
        const allChk = document.getElementById('estoque-all');
        if (allChk){
            if (!e.target.checked) {
                allChk.checked = false;
            } else {
                // Verificar se todos estão marcados agora
                const all = Array.from(tbody.querySelectorAll('.estoque-mat-chk'));
                if (all.every(c => c.checked)) {
                    allChk.checked = true;
                }
            }
        }
        updateEstoqueResumo();
      }
    });
  }
}

function toggleEstoqueModal(show){
  const m = document.getElementById('estoque-modal');
  if (m) m.classList.toggle('d-none', !show);
}

async function openEstoqueModal(){
  if (!estoqueMateriaisCache.length){
    try{
      const rows = await (await apiFetch('/api/materias')).json();
      estoqueMateriaisCache = rows;
    } catch(e){
      showToast('<div class="alert alert-warning">Não foi possível carregar materiais de estoque</div>');
      return;
    }
  }
  const tbody = document.querySelector('#estoque-mats tbody');
  if (tbody){
    tbody.innerHTML = '';
    const selectedSet = new Set(Array.isArray(estoqueMateriaisSelecionados) ? estoqueMateriaisSelecionados : []);
    estoqueMateriaisCache.forEach(m=>{
      const checked = estoqueMateriaisSelecionados === null ? true : selectedSet.has(m.id);
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td class="text-center"><input type="checkbox" class="form-check-input estoque-mat-chk" data-id="${m.id}" ${checked ? 'checked' : ''}></td>
        <td>${m.nome}</td>
        <td class="text-end">${Number(m.estoque||0).toFixed(4).replace(/\.?0+$/,'')}</td>
        <td class="text-end">${format(m.custo||0)}</td>
      `;
      tbody.appendChild(tr);
    });
  }
  const allChk = document.getElementById('estoque-all');
  if (allChk){
    allChk.checked = estoqueMateriaisSelecionados === null;
  }
  updateEstoqueResumo();
  toggleEstoqueModal(true);
}

function syncEstoqueSelectionUI(){
  const tbody = document.querySelector('#estoque-mats tbody');
  if (!tbody) return;
  const selectedSet = new Set(Array.isArray(estoqueMateriaisSelecionados) ? estoqueMateriaisSelecionados : []);
  const allChk = document.getElementById('estoque-all');
  const allSelected = estoqueMateriaisSelecionados === null;
  tbody.querySelectorAll('input.estoque-mat-chk').forEach(chk=>{
    if (allSelected){
      chk.checked = true;
    } else {
      const id = parseInt(chk.dataset.id);
      chk.checked = selectedSet.has(id);
    }
  });
  if (allChk){
    allChk.checked = allSelected;
  }
  updateEstoqueResumo();
}

function collectEstoqueSelectionFromUI(){
  const tbody = document.querySelector('#estoque-mats tbody');
  if (!tbody) return;
  const allChk = document.getElementById('estoque-all');
  if (allChk && allChk.checked){
    estoqueMateriaisSelecionados = null;
    return;
  }
  const ids = [];
  tbody.querySelectorAll('input.estoque-mat-chk').forEach(chk=>{
    if (chk.checked){
      const id = parseInt(chk.dataset.id);
      if (!Number.isNaN(id)) ids.push(id);
    }
  });
  estoqueMateriaisSelecionados = ids;
}

function updateEstoqueResumo(){
  const span = document.getElementById('estoque-resumo');
  if (!span) return;
  if (estoqueMateriaisSelecionados === null){
    span.textContent = 'Todos os materiais incluídos';
    return;
  }
  const total = estoqueMateriaisSelecionados.length;
  if (!total){
    span.textContent = 'Nenhum material selecionado';
    return;
  }
  span.textContent = `${total} material${total>1?'is':''} selecionado${total>1?'s':''}`;
}

function aplicarEstoqueSelecao(){
  collectEstoqueSelectionFromUI();
  recalcEstoqueFromSelecao();
  toggleEstoqueModal(false);
}

function recalcEstoqueFromSelecao(){
  if (!estoqueMateriaisCache.length){
    updateStoreEstoqueTag(false);
    return;
  }
  
  const usarTodos = estoqueMateriaisSelecionados === null;
  const selectedSet = usarTodos ? null : new Set(estoqueMateriaisSelecionados);
  
  let total = 0;
  estoqueMateriaisCache.forEach(m=>{
    if (usarTodos || selectedSet.has(m.id)){
      const est = Number(m.estoque||0);
      const custo = Number(m.custo||0);
      if (isFinite(est) && isFinite(custo)){
        total += est * custo;
      }
    }
  });
  
  const el = document.getElementById('store-estoque');
  if (el){
    el.textContent = format(total);
  }
  updateStoreEstoqueTag(!usarTodos);
}

function updateStoreEstoqueTag(filtrado){
  const tag = document.getElementById('store-estoque-tag');
  if (!tag) return;
  if (!filtrado || estoqueMateriaisSelecionados === null){
    tag.textContent = '';
    return;
  }
  tag.textContent = 'filtrado';
}

function initRelatoriosSubTabs() {
    const tabs = document.querySelectorAll('#rel-subtabs button');
    tabs.forEach(t => {
        t.addEventListener('click', (e) => {
            e.preventDefault();
            tabs.forEach(x => x.classList.remove('active'));
            t.classList.add('active');
            
            const target = t.dataset.target;
            const elStore = document.getElementById('rel-store');
            const elProd = document.getElementById('rel-prod-view');
            
            if(elStore) elStore.classList.add('d-none');
            if(elProd) elProd.classList.add('d-none');
            
            const tgtEl = document.getElementById(target);
            if(tgtEl) tgtEl.classList.remove('d-none');
            
            if (target === 'rel-store') {
                loadStoreReport();
            } else {
                loadRelatorios();
            }
        });
    });

    const active = document.querySelector('#rel-subtabs button.active');
    if (active && active.dataset.target === 'rel-store') {
        loadStoreReport();
    }
}

function continueApp(){
  const prodInput = document.getElementById('produto-input');
  if (prodInput) {
    prodInput.addEventListener('change', () => {
      const val = prodInput.value;
      const hidden = document.getElementById('produto');
      if (!hidden) return;
      const match = productsCacheForSearch.find(p => (p.id + ' - ' + p.nome) === val);
      if (match) {
        hidden.value = match.id;
        loadRelatorios();
      } else {
        const matchId = productsCacheForSearch.find(p => String(p.id) === val);
        if (matchId) {
            hidden.value = matchId.id;
            prodInput.value = matchId.id + ' - ' + matchId.nome;
            loadRelatorios();
            return;
        }
        const matchName = productsCacheForSearch.find(p => p.nome.toLowerCase() === val.toLowerCase());
         if (matchName) {
           hidden.value = matchName.id;
           prodInput.value = matchName.id + ' - ' + matchName.nome;
           loadRelatorios();
         } else {
            const partials = productsCacheForSearch.filter(p => p.nome.toLowerCase().includes(val.toLowerCase()) || String(p.id).includes(val));
            if (partials.length === 1) {
                const p = partials[0];
                hidden.value = p.id;
                prodInput.value = p.id + ' - ' + p.nome;
                loadRelatorios();
            }
         }
         if (val === '') {
            hidden.value = '';
            loadRelatorios();
        }
      }
    });
    prodInput.addEventListener('input', () => {
        if (prodInput.value === '') {
            const h = document.getElementById('produto');
            if(h) h.value = '';
        }
    });
  }
  setupTabs();
  fixSidebarPosition();
  window.addEventListener('resize', fixSidebarPosition);
  initProdutos();
  initMaterias();
  initConfig();
  initVendas();
  loadProdutos();
  initRelatoriosControls();
  initEstoqueFilter();
  initDynamicNavbar();
}

function initDynamicNavbar(){
  const body = document.body;
  const sidebar = document.querySelector('.sidebar');
  const hamb = document.getElementById('nav-hamb');
  const apply = () => {
    const collapsed = window.scrollY > 10;
    body.classList.toggle('nav-collapsed', collapsed);
    body.classList.toggle('nav-expanded', !collapsed);
    fixSidebarPosition();
  };
  apply();
  window.addEventListener('scroll', apply, { passive: true });
  // Hamburger é apenas estético; sem ação de clique.
}

// Produtos
let prodSel = null;
let isPrintMode = false;
let selectedForPrint = new Set();
let prodEditSnapshot = null;
let creatingNovoProduto = false;
let prevProdSel = null;
let pendingPhotoFile = null;
let pendingComposition = [];
let materiasCache = [];
let vendaPrecoAtual = 0;
let freteCurrentPlatform = 'Mercado Livre';

function togglePrintMode(){
  isPrintMode = !isPrintMode;
  const btn = document.getElementById('p-print-mode');
  if (btn) {
    btn.classList.toggle('btn-outline-secondary', !isPrintMode);
    btn.classList.toggle('btn-primary', isPrintMode);
  }
  const btnCont = document.getElementById('p-print-action-container');
  if (btnCont) btnCont.classList.toggle('d-none', !isPrintMode);
  
  const btnNovo = document.getElementById('p-novo');
  if (btnNovo) btnNovo.disabled = isPrintMode;
  
  refreshProdutos();
}

async function openPrintModal(){
  if (selectedForPrint.size === 0) {
    showToast('<div class="alert alert-warning">Nenhum produto selecionado</div>');
    return;
  }
  
  const modal = document.getElementById('print-modal');
  const list = document.getElementById('print-list');
  if (!modal || !list) return;
  
  list.innerHTML = '<div class="text-center p-3"><div class="spinner-border text-primary"></div></div>';
  modal.classList.remove('d-none');
  
  const items = [];
  for (const pid of selectedForPrint){
    const p = productsCacheForSearch.find(x => String(x.id) === String(pid));
    if (p) items.push(p);
  }
  
  // Fetch QRs for each item
  list.innerHTML = '';
  
  for (const p of items){
    const row = document.createElement('div');
    row.className = 'border-bottom pb-2';
    
    // Fetch QRs
    let qrs = [];
    try {
      qrs = await (await apiFetch(`/api/qr/${p.id}`)).json();
    } catch(e) {}
    
    // Fallback if no QRs? User can generate them in the main view.
    // Assuming they exist or user wants to print what exists.
    
    if (qrs.length === 0) {
        row.innerHTML = `<div class="fw-bold">${p.nome}</div><div class="text-muted small">Sem QR Codes gerados.</div>`;
        list.appendChild(row);
        continue;
    }
    
    let html = `<div class="fw-bold mb-1">${p.nome}</div><div class="d-flex flex-wrap gap-3">`;
    qrs.forEach(q => {
        const uid = `pq-${p.id}-${q.plataforma_id}-${q.ml_mode||''}`;
        html += `
          <div class="form-check">
            <input class="form-check-input print-qr-chk" type="checkbox" id="${uid}" value="${q.code}" data-pid="${p.id}" data-label="${q.plataforma}" checked>
            <label class="form-check-label small" for="${uid}">${q.plataforma}</label>
          </div>
        `;
    });
    html += `</div>`;
    row.innerHTML = html;
    list.appendChild(row);
  }
}

async function downloadPrintPDF(){
  const inputs = document.querySelectorAll('.print-qr-chk:checked');
  if (inputs.length === 0) {
    showToast('<div class="alert alert-warning">Nenhum QR Code selecionado</div>');
    return;
  }
  
  // Group by Product
  const map = {};
  inputs.forEach(inp => {
    const pid = inp.dataset.pid;
    if (!map[pid]) map[pid] = { nome: '', codes: [] };
    const p = productsCacheForSearch.find(x => String(x.id) === String(pid));
    if (p) map[pid].nome = p.nome;
    
    map[pid].codes.push({
        label: inp.dataset.label,
        code: inp.value
    });
  });
  
  const payload = Object.values(map);
  const btn = document.getElementById('print-confirm');
  const oldText = btn.innerText;
  btn.disabled = true;
  btn.innerText = 'Gerando PDF...';
  
  try {
    const r = await apiFetch('/api/print_qrs', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
    });
    
    if (r.ok) {
        const blob = await r.blob();
        
        // Verificar se estamos no ambiente Desktop (pywebview)
        if (window.pywebview && window.pywebview.api) {
            // Converter Blob para Base64
            const reader = new FileReader();
            reader.readAsDataURL(blob);
            reader.onloadend = async function() {
                const base64data = reader.result.split(',')[1];
                const result = await window.pywebview.api.save_file_dialog("etiquetas_qr.pdf", base64data);
                
                if (result.ok) {
                     showToast(`<div class="alert alert-success">PDF salvo em: ${result.path}</div>`);
                     document.getElementById('print-modal').classList.add('d-none');
                } else if (result.reason !== 'cancelled') {
                     showToast(`<div class="alert alert-danger">Erro ao salvar: ${result.error}</div>`);
                }
            }
        } else {
            // Fallback para navegador
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'etiquetas_qr.pdf';
            document.body.appendChild(a);
            a.click();
            setTimeout(()=> { URL.revokeObjectURL(url); a.remove(); }, 1000);
            document.getElementById('print-modal').classList.add('d-none');
            showToast('<div class="alert alert-success">PDF gerado! Verifique sua pasta de Downloads.</div>');
        }
    } else {
        showToast('<div class="alert alert-danger">Erro ao gerar PDF</div>');
    }
  } catch(e) {
    console.error(e);
    showToast('<div class="alert alert-danger">Erro de conexão</div>');
  } finally {
    btn.disabled = false;
    btn.innerText = oldText;
  }
}

function getCurrentProdutoId(){
  return prodSel && prodSel.id ? String(prodSel.id) : '';
}

function getPrecoAtualProdutoPlataforma(nome){
  let el = null;
  if (nome === 'Mercado Livre Clássico') el = document.getElementById('p-ml-classico');
  else if (nome === 'Mercado Livre Premium') el = document.getElementById('p-ml-premium');
  else if (nome === 'Mercado Livre') {
    // Fallback or prefer Classic?
    el = document.getElementById('p-ml-classico'); 
  }
  else if (nome === 'Magalu') el = document.getElementById('p-mag');
  else if (nome === 'Shopee') el = document.getElementById('p-sh');
  if (!el) return 0;
  const raw = String(el.value || '').replace(',', '.');
  const v = parseFloat(raw);
  return isNaN(v) ? 0 : v;
}

function updateFreteResumoProduto(){
  const el = document.getElementById('p-frete-resumo');
  if (!el) return;
  const pid = getCurrentProdutoId();
  if (!pid){
    el.textContent = '';
    return;
  }
  const parts = [];
  const ml = getFreteForProduto(pid, 'Mercado Livre');
  if (ml > 0) parts.push('ML: ' + format(ml));
  const mag = getFreteForProduto(pid, 'Magalu');
  if (mag > 0) parts.push('Magalu: ' + format(mag));
  const sh = getFreteForProduto(pid, 'Shopee');
  if (sh > 0) parts.push('Shopee: ' + format(sh));
  el.textContent = parts.length ? 'Frete considerado: ' + parts.join(' · ') : '';
}

function updateFixoTogglesProduto(){
  const elMl = document.getElementById('p-ml-fixo-toggle');
  const elMag = document.getElementById('p-magalu-fixo-toggle');
  const pid = getCurrentProdutoId();
  
  if (elMl){
    if (!pid){
        elMl.checked = false;
        elMl.disabled = true;
    } else {
        elMl.disabled = false;
        elMl.checked = isIgnoreMlFixo(pid);
    }
  }
  
  if (elMag){
    if (!pid){
        elMag.checked = false;
        elMag.disabled = true;
    } else {
        elMag.disabled = false;
        elMag.checked = isIgnoreMagaluFixo(pid);
    }
  }
}

function toggleFreteModal(show){
  const m = document.getElementById('frete-modal');
  if (m) m.classList.toggle('d-none', !show);
}

function updateFreteResumoModal(){
  const resumo = document.getElementById('frete-resumo');
  if (!resumo) return;
  const preco = getPrecoAtualProdutoPlataforma(freteCurrentPlatform);
  const valInp = document.getElementById('frete-valor');
  let frete = 0;
  if (valInp){
    frete = parseFloat(String(valInp.value || '').replace(',', '.'));
    if (!isFinite(frete) || frete < 0) frete = 0;
  }
  if (!preco){
    resumo.textContent = '';
    return;
  }
  const receita = preco - frete;
  resumo.textContent = 'Preço de venda: ' + format(preco) + ' · Após frete: ' + format(receita);
}

function guessFretePlatform(){
  if (getPrecoAtualProdutoPlataforma('Mercado Livre') > 0) return 'Mercado Livre';
  if (getPrecoAtualProdutoPlataforma('Magalu') > 0) return 'Magalu';
  if (getPrecoAtualProdutoPlataforma('Shopee') > 0) return 'Shopee';
  return 'Mercado Livre';
}

function openFreteModal(initialPlatform){
  const pid = getCurrentProdutoId();
  if (!pid) return;
  freteCurrentPlatform = initialPlatform || freteCurrentPlatform || 'Mercado Livre';
  const platSel = document.getElementById('frete-plataforma');
  if (platSel){
    platSel.value = freteCurrentPlatform;
  }
  const inp = document.getElementById('frete-valor');
  if (inp){
    const saved = getFreteForProduto(pid, freteCurrentPlatform);
    inp.value = saved ? saved.toFixed(2) : '';
  }
  updateFreteResumoModal();
  toggleFreteModal(true);
}

function initFreteUI(){
  const mlToggle = document.getElementById('p-ml-fixo-toggle');
  if (mlToggle){
    mlToggle.addEventListener('change', ()=>{
      const pid = getCurrentProdutoId();
      if (!pid){
        mlToggle.checked = false;
        return;
      }
      setIgnoreMlFixo(pid, mlToggle.checked);
      loadRelatorios();
    });
  }
  const magToggle = document.getElementById('p-magalu-fixo-toggle');
  if (magToggle){
    magToggle.addEventListener('change', ()=>{
      const pid = getCurrentProdutoId();
      if (!pid){
        magToggle.checked = false;
        return;
      }
      setIgnoreMagaluFixo(pid, magToggle.checked);
      loadRelatorios();
    });
  }
  const btn = document.getElementById('p-frete-btn');
  if (btn){
    btn.addEventListener('click', ()=>{
      const plat = guessFretePlatform();
      openFreteModal(plat);
    });
  }
  const closeBtn = document.getElementById('frete-close');
  if (closeBtn){
    closeBtn.addEventListener('click', ()=> toggleFreteModal(false));
  }
  const platSel = document.getElementById('frete-plataforma');
  if (platSel){
    platSel.addEventListener('change', ()=>{
      freteCurrentPlatform = platSel.value || 'Mercado Livre';
      const pid = getCurrentProdutoId();
      const inp = document.getElementById('frete-valor');
      if (inp){
        const saved = getFreteForProduto(pid, freteCurrentPlatform);
        inp.value = saved ? saved.toFixed(2) : '';
      }
      updateFreteResumoModal();
    });
  }
  const valInp = document.getElementById('frete-valor');
  if (valInp){
    valInp.addEventListener('input', ()=>{
      updateFreteResumoModal();
    });
  }
  const aplicarBtn = document.getElementById('frete-aplicar');
  if (aplicarBtn){
    aplicarBtn.addEventListener('click', ()=>{
      const pid = getCurrentProdutoId();
      if (!pid) return;
      const inp = document.getElementById('frete-valor');
      if (!inp) return;
      let v = parseFloat(String(inp.value || '').replace(',', '.'));
      if (!isFinite(v) || v < 0) v = 0;
      if (!fretePorProduto[pid]) fretePorProduto[pid] = {};
      const key = normalizeFretePlatformName(freteCurrentPlatform);
      fretePorProduto[pid][key] = v;
      updateFreteResumoProduto();
      toggleFreteModal(false);
      loadRelatorios();
    });
  }
  const limparBtn = document.getElementById('frete-limpar');
  if (limparBtn){
    limparBtn.addEventListener('click', ()=>{
      const pid = getCurrentProdutoId();
      if (!pid) return;
      const map = fretePorProduto[pid];
      if (map){
        const key = normalizeFretePlatformName(freteCurrentPlatform);
        delete map[key];
      }
      const inp = document.getElementById('frete-valor');
      if (inp) inp.value = '';
      updateFreteResumoModal();
      updateFreteResumoProduto();
      loadRelatorios();
    });
  }
}

async function initProdutos(){
  await refreshProdutos();
  await refreshMateriasChoices();
  document.getElementById('p-salvar').addEventListener('click', saveProduto);
  document.getElementById('p-cancelar').addEventListener('click', cancelProdutoEdit);
  document.getElementById('p-novo').addEventListener('click', startNovoProdutoInline);
  document.getElementById('p-remover').addEventListener('click', deleteProduto);
  document.getElementById('p-editar').addEventListener('click', enableProdutoEdit);
  document.getElementById('c-vincular').addEventListener('click', vincularMateria);
  document.getElementById('p-print-mode').addEventListener('click', togglePrintMode);
  document.getElementById('p-print-action').addEventListener('click', openPrintModal);
  const printClose = document.getElementById('print-close'); if(printClose) printClose.addEventListener('click', ()=>document.getElementById('print-modal').classList.add('d-none'));
  const printConf = document.getElementById('print-confirm'); if(printConf) printConf.addEventListener('click', downloadPrintPDF);
  const ps = document.getElementById('p-search');
  const so = document.getElementById('p-sort');
  if (ps) ps.addEventListener('input', refreshProdutos);
  if (so) so.addEventListener('change', refreshProdutos);
  const photoBtn = document.getElementById('p-photo-btn');
  const photoFile = document.getElementById('p-photo-file');
  if (photoBtn && photoFile){
    photoBtn.addEventListener('click', ()=> photoFile.click());
    photoFile.addEventListener('change', handlePhotoChange);
    photoBtn.classList.add('d-none');
  }
  const cs = document.getElementById('comp-salvar');
  const cc = document.getElementById('comp-cancelar');
  if (cs && cc){
    cs.addEventListener('click', async ()=>{
      const inputs = document.querySelectorAll('#comp tbody input.comp-qtd');
      for (const inp of inputs){
        const id = inp.dataset.id;
        await apiFetch(`/api/composicao/${id}`, {method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify({quantidade: parseFloat(inp.value||0)})});
      }
      setCompReadonly(true);
      toggleCompButtons({editar:true, salvar:false, cancelar:false});
      showCompMsg('<div class="alert alert-success alert-dismissible fade show" role="alert">Composição salva.<button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button></div>');
    });
    cc.addEventListener('click', async ()=>{
      await refreshComposicao();
      setCompReadonly(true);
      toggleCompButtons({editar:true, salvar:false, cancelar:false});
      showCompMsg('<div class="alert alert-secondary alert-dismissible fade show" role="alert">Edição cancelada.<button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button></div>');
    });
  }
  initFreteUI();
}

async function refreshProdutos(){
  const r = await apiFetch('/api/produtos?ts=' + Date.now(), { cache: 'no-store' });
  const data = await r.json();
  const qEl = document.getElementById('p-search'); const q = String((qEl && qEl.value) ? qEl.value : '').toLowerCase();
  const sEl = document.getElementById('p-sort'); const sort = (sEl && sEl.value) ? sEl.value : 'nome';
  let rows = data.filter(p=>{
    return !q || String(p.id).includes(q) || String(p.nome).toLowerCase().includes(q) || String(p.sku||'').toLowerCase().includes(q);
  });
  rows.sort((a,b)=> sort==='id' ? (a.id-b.id) : String(a.nome).localeCompare(String(b.nome)) );
  const list = document.getElementById('prod-list');
  list.innerHTML='';
  rows.forEach(p=>{
    const item = document.createElement('a');
    item.className = 'list-group-item list-group-item-action d-flex justify-content-between align-items-center';
    item.setAttribute('data-id', p.id);
    
    let checkHtml = '';
    if (isPrintMode) {
        const isChecked = selectedForPrint.has(p.id);
        checkHtml = `<input type="checkbox" class="form-check-input me-2" ${isChecked ? 'checked' : ''} style="pointer-events:none;">`;
        if (isChecked) item.classList.add('list-group-item-info');
    }

    item.innerHTML = `<div class=\"d-flex align-items-center\">${checkHtml}<div class=\"d-flex flex-column\"><span class=\"title\">${p.nome}</span><span class=\"sub\">SKU ${p.sku||'-'} · ID ${p.id}</span></div></div>`;
    
    item.addEventListener('click',(e)=>{
        if (isPrintMode) {
            e.preventDefault();
            if (selectedForPrint.has(p.id)) selectedForPrint.delete(p.id);
            else selectedForPrint.add(p.id);
            refreshProdutos();
            updatePrintCount();
        } else {
            selectProduto(p);
        }
    });

    if (!isPrintMode && prodSel && prodSel.id === p.id) item.classList.add('active');
    list.appendChild(item);
  });
  
  if (!isPrintMode) {
      if (rows.length && !prodSel && !creatingNovoProduto) {
        selectProduto(rows[0]);
      } else if (!rows.length && !creatingNovoProduto) {
        prodSel = null;
        clearProdutoView();
        clearRelatoriosView();
      }
  }
}

function updatePrintCount(){
    const el = document.getElementById('p-print-count');
    if(el) el.textContent = selectedForPrint.size;
}

async function selectProduto(p){
  prodSel = p;
  document.getElementById('p-nome').value = p.nome;
  document.getElementById('p-sku').value = p.sku || '';
  const pr = await (await apiFetch(`/api/prices/${p.id}`)).json();
  document.getElementById('p-ml-classico').value = (pr['Mercado Livre Clássico']||0).toFixed(2);
  document.getElementById('p-ml-premium').value = (pr['Mercado Livre Premium']||0).toFixed(2);
  document.getElementById('p-mag').value = (pr['Magalu']||0).toFixed(2);
  document.getElementById('p-sh').value = (pr['Shopee']||0).toFixed(2);
  loadProdutoPhoto();
  // Primeiro garanta que o formulário esteja em modo somente leitura
  setProdutoReadonly(true);
  toggleProdutoButtons({editar:true, salvar:false, cancelar:false});
  toggleCompButtons({editar:true, salvar:false, cancelar:false});
  // Em seguida atualize a composição já com os botões corretos, evitando liberar edição indevidamente
  await refreshComposicao();
  showProdMsg('');
  updateProdListActive();
  togglePhotoBtn(false);
  pendingPhotoFile = null;
  toggleRemover(true);
  await renderQRCodes();
  const qrGen2 = document.getElementById('qr-gen'); if (qrGen2) qrGen2.disabled = false;
  const qrDelAll2 = document.getElementById('qr-del-all'); if (qrDelAll2) qrDelAll2.disabled = false;
  const qrList2 = document.getElementById('qr-list'); if (qrList2) qrList2.classList.remove('d-none');
  const qrHeader2 = qrGen2 ? (qrGen2.parentElement && qrGen2.parentElement.parentElement) : null; if (qrHeader2) qrHeader2.classList.remove('d-none');
  updateFreteResumoProduto();
  updateFixoTogglesProduto();
}

function setProdutoForm(o){
  document.getElementById('p-nome').value = o.nome;
  document.getElementById('p-sku').value = o.sku;
  document.getElementById('p-ml-classico').value = o.ml_classico || 0;
  document.getElementById('p-ml-premium').value = o.ml_premium || 0;
  document.getElementById('p-mag').value = o.mag;
  document.getElementById('p-sh').value = o.sh;
}

async function saveProduto(){
  const nome = document.getElementById('p-nome').value.trim();
  const sku = document.getElementById('p-sku').value.trim();
  const _precos = {
    'ML Clássico': parseFloat(document.getElementById('p-ml-classico').value||0),
    'ML Premium':  parseFloat(document.getElementById('p-ml-premium').value||0),
    'Magalu':      parseFloat(document.getElementById('p-mag').value||0),
    'Shopee':      parseFloat(document.getElementById('p-sh').value||0),
  };
  if (!validarProduto(nome, _precos)) return;
  if (!nome) return;
  if (!prodSel){
    const r = await apiFetch('/api/products', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({nome, sku})});
    const j = await r.json();
    prodSel = {id: j.id, nome};
    if (pendingPhotoFile){
      await uploadProdutoPhoto();
      pendingPhotoFile = null;
    }
    for (const item of pendingComposition){
      await apiFetch('/api/composicao', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({produto_id: prodSel.id, materia_id: item.materia_id, quantidade: item.quantidade})});
    }
    pendingComposition = [];
  } else {
    await apiFetch(`/api/products/${prodSel.id}`, {method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify({nome, sku})});
    prodSel.nome = nome;
    prodSel.sku = sku;
  }
  const inputs = document.querySelectorAll('#comp tbody input.comp-qtd');
  for (const inp of inputs){
    const id = inp.dataset.id;
    if (!id) continue;
    await apiFetch(`/api/composicao/${id}`, {method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify({quantidade: parseFloat(inp.value||0)})});
  }
  await apiFetch(`/api/prices/${prodSel.id}`, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({plataforma:'Mercado Livre Clássico', preco: parseFloat(document.getElementById('p-ml-classico').value||0)})});
  await apiFetch(`/api/prices/${prodSel.id}`, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({plataforma:'Mercado Livre Premium', preco: parseFloat(document.getElementById('p-ml-premium').value||0)})});
  await apiFetch(`/api/prices/${prodSel.id}`, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({plataforma:'Magalu', preco: parseFloat(document.getElementById('p-mag').value||0)})});
  await apiFetch(`/api/prices/${prodSel.id}`, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({plataforma:'Shopee', preco: parseFloat(document.getElementById('p-sh').value||0)})});
  await refreshProdutos();
  await loadRelatorios();
  await selectProduto(prodSel);
  await loadProdutos();
  await loadVendasProdutos();
  setProdutoReadonly(true);
  toggleProdutoButtons({editar:true, salvar:false, cancelar:false});
  setCompReadonly(true);
  toggleCompButtons({editar:true, salvar:false, cancelar:false});
  const msg = creatingNovoProduto ? 'Produto criado com sucesso.' : 'Produto alterado com sucesso.';
  showProdMsg(`<div class="alert alert-success alert-dismissible fade show" role="alert">${msg}<button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button></div>`);
  creatingNovoProduto = false;
  prevProdSel = null;
  togglePhotoBtn(false);
  toggleRemover(true);
}

async function deleteProduto(){
  if (!prodSel) return;
  const _okDel = await confirmar(`Remover o produto "${prodSel.nome}"? Todos os dados relacionados serão removidos.`, "Remover Produto");
  if (!_okDel) return;
  auditLog('produto_removido', {nome: prodSel.nome, id: prodSel.id});
  await apiFetch(`/api/products/${prodSel.id}`, {method:'DELETE'});
  prodSel = null;
  await refreshProdutos();
  await loadProdutos();
  await loadVendasProdutos();
}

async function refreshComposicao(){
  const tbody = document.querySelector('#comp tbody');
  tbody.innerHTML='';
  if (!prodSel){
    pendingComposition.forEach((r, idx)=>{
      const mat = materiasCache.find(m=>m.id === r.materia_id) || {nome:'', unidade:'', custo:0};
      const rendTxt = formatRendimentoFromQtd(r.quantidade, mat.unidade);
      const tr = document.createElement('tr');
      tr.innerHTML = `<td>novo</td><td>${mat.nome}</td><td>${mat.unidade||''}</td><td><input data-pindex="${idx}" class="form-control form-control-sm comp-qtd" type="number" step="0.0001" value="${r.quantidade}"></td><td>${rendTxt}</td><td>${Number(mat.custo||0).toFixed(2)}</td><td><button class="btn btn-sm btn-danger" data-pdel="${idx}">Remover</button></td>`;
      tbody.appendChild(tr);
    });
    tbody.querySelectorAll('button[data-pdel]').forEach(btn=>{
      btn.addEventListener('click', async ()=>{
        const i = parseInt(btn.dataset.pdel);
        pendingComposition.splice(i, 1);
        await refreshComposicao();
      });
    });
    setCompReadonly(false);
    return;
  }
  const rows = await (await apiFetch(`/api/composicao/${prodSel.id}`)).json();
  rows.forEach(r=>{
    const rendTxt = formatRendimentoFromQtd(r.qtd, r.unidade);
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${r.id}</td><td>${r.materia}</td><td>${r.unidade}</td><td><input data-id="${r.id}" class="form-control form-control-sm comp-qtd" type="number" step="0.0001" value="${r.qtd}"></td><td>${rendTxt}</td><td>${r.custo_medio.toFixed(2)}</td><td><button class="btn btn-sm btn-danger" data-del="${r.id}">Remover</button></td>`;
    tbody.appendChild(tr);
  });
  tbody.querySelectorAll('button[data-del]').forEach(btn=>{
    btn.addEventListener('click', async ()=>{
      const id = btn.dataset.del;
      await apiFetch(`/api/composicao/${id}`, {method:'DELETE'});
      await refreshComposicao();
    });
  });
  const salvarBtn = document.getElementById('p-salvar');
  const isEditMode = !!(salvarBtn && !salvarBtn.classList.contains('d-none')) || creatingNovoProduto;
  setCompReadonly(!isEditMode);
}

function formatRendimentoFromQtd(qtd, unidade){
  const q = Number(qtd);
  if (!q || !isFinite(q) || q <= 0) return '';
  const raw = 1 / q;
  const rounded = Math.round(raw);
  if (!isFinite(raw) || rounded <= 1) return '';
  const diff = Math.abs(raw - rounded);
  if (diff > 1e-4) return '';
  const prodLabel = rounded === 1 ? 'produto' : 'produtos';
  const unitLabel = unidade || 'unidade';
  return `${rounded} ${prodLabel} por ${unitLabel}`;
}

async function refreshMateriasChoices(){
  const mats = await (await apiFetch('/api/materias')).json();
  const sel = document.getElementById('c-mat');
  sel.innerHTML='';
  materiasCache = mats;
  mats.forEach(m=>{const o=document.createElement('option');o.value=m.id;o.textContent=m.nome;sel.appendChild(o);});
}

async function vincularMateria(){
  const materia_id = parseInt(document.getElementById('c-mat').value);
  let quantidade = parseFloat(document.getElementById('c-qtd').value||0);
  const rendimento = parseFloat(document.getElementById('c-rendimento').value||1);
  
  if (rendimento > 0 && rendimento !== 1) {
    quantidade = quantidade / rendimento;
  }

  if (!prodSel){
    pendingComposition.push({materia_id, quantidade});
    await refreshComposicao();
    return;
  }
  await apiFetch('/api/composicao', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({produto_id: prodSel.id, materia_id, quantidade})});
  await refreshComposicao();
}

function setCompReadonly(ro){
  document.querySelectorAll('#comp tbody input.comp-qtd').forEach(el=>{
    el.disabled = !!ro;
    el.classList.toggle('bg-body-secondary', !!ro);
  });
  const vinc = document.getElementById('c-vincular');
  if (vinc){
    vinc.disabled = !!ro;
    vinc.classList.toggle('d-none', !!ro);
  }
  const cm = document.getElementById('c-mat');
  const cq = document.getElementById('c-qtd');
  const cr = document.getElementById('c-rendimento');
  if (cm){ cm.disabled = !!ro; cm.classList.toggle('bg-body-secondary', !!ro); }
  if (cq){ cq.disabled = !!ro; cq.classList.toggle('bg-body-secondary', !!ro); }
  if (cr){ cr.disabled = !!ro; cr.classList.toggle('bg-body-secondary', !!ro); }
  document.querySelectorAll('#comp tbody button[data-del]').forEach(btn=>{
    btn.classList.toggle('d-none', !!ro);
    btn.disabled = !!ro;
  });
}
function toggleCompButtons({editar, salvar, cancelar}){
  const e = document.getElementById('comp-editar');
  const s = document.getElementById('comp-salvar');
  const c = document.getElementById('comp-cancelar');
  if (e) e.classList.toggle('d-none', !editar);
  if (s) s.classList.toggle('d-none', !salvar);
  if (c) c.classList.toggle('d-none', !cancelar);
}
function showCompMsg(html){
  const div = document.getElementById('comp-msg');
  if (div) div.innerHTML = '';
  if (html) showToast(html);
}

function setProdutoReadonly(ro){
  ['p-nome','p-sku','p-ml-classico','p-ml-premium','p-mag','p-sh'].forEach(id=>{
    const el = document.getElementById(id);
    el.disabled = !!ro;
    el.classList.toggle('bg-body-secondary', !!ro);
  });
}

function toggleProdutoButtons({editar, salvar, cancelar}){
  document.getElementById('p-editar').classList.toggle('d-none', !editar);
  document.getElementById('p-salvar').classList.toggle('d-none', !salvar);
  document.getElementById('p-cancelar').classList.toggle('d-none', !cancelar);
}

function enableProdutoEdit(){
  prodEditSnapshot = getProdutoForm();
  setProdutoReadonly(false);
  toggleProdutoButtons({editar:false, salvar:true, cancelar:true});
  togglePhotoBtn(true);
  const rem = document.getElementById('p-remover'); if (rem) rem.classList.add('d-none');
  // Durante a edição do produto, a composição deve ser editável
  setCompReadonly(false);
  toggleCompButtons({editar:false, salvar:true, cancelar:true});
  softAppear(['#p-salvar','#p-cancelar','#c-mat','#c-qtd','#c-vincular','#comp']);
  // Reavaliar a composição para garantir que os campos e ações refletem o modo de edição
  try { refreshComposicao(); } catch(err) {}
}

function showProdMsg(html){
  const div = document.getElementById('prod-msg');
  div.innerHTML = '';
  if (html) showToast(html);
}

function togglePhotoBtn(show){
  const btn = document.getElementById('p-photo-btn');
  if (btn){
    btn.classList.toggle('d-none', !show);
  }
}

function toggleRemover(show){
  const btn = document.getElementById('p-remover');
  if (btn){
    btn.classList.toggle('d-none', !show);
  }
}

function clearProdutoView(){
  setProdutoForm({nome:'',sku:'',ml:'',mag:'',sh:''});
  setProdutoReadonly(true);
  toggleProdutoButtons({editar:false, salvar:false, cancelar:false});
  const tbody = document.querySelector('#comp tbody'); if (tbody) tbody.innerHTML='';
  setCompReadonly(true);
  toggleCompButtons({editar:false, salvar:false, cancelar:false});
  togglePhotoBtn(false);
  toggleRemover(false);
  resetProdutoPhoto();
  const vinc = document.getElementById('c-vincular'); if (vinc) vinc.disabled = true;
  const qrList = document.getElementById('qr-list'); if (qrList) { qrList.innerHTML=''; qrList.classList.add('d-none'); }
  const qrGen = document.getElementById('qr-gen'); if (qrGen) qrGen.disabled = true;
  const qrDelAll = document.getElementById('qr-del-all'); if (qrDelAll) qrDelAll.disabled = true;
  const qrHeader = qrGen ? (qrGen.parentElement && qrGen.parentElement.parentElement) : null; if (qrHeader) qrHeader.classList.add('d-none');
  const freteRes = document.getElementById('p-frete-resumo'); if (freteRes) freteRes.textContent = '';
  const mlToggle = document.getElementById('p-ml-fixo-toggle'); if (mlToggle) { mlToggle.checked = false; mlToggle.disabled = true; }
  const magToggle = document.getElementById('p-magalu-fixo-toggle'); if (magToggle) { magToggle.checked = false; magToggle.disabled = true; }
}

function clearRelatoriosView(){
  const tbodyCalc = document.querySelector('#calc-prod tbody'); if (tbodyCalc) tbodyCalc.innerHTML='';
  const elCusto = document.getElementById('calc-custo'); if (elCusto) elCusto.textContent = format(0);
  const elLucro = document.getElementById('calc-lucro-max'); if (elLucro) elLucro.textContent = format(0);
  const elMargem = document.getElementById('calc-margem-max'); if (elMargem) elMargem.textContent = '0%';
  const vtbody = document.querySelector('#rel-vendas tbody'); if (vtbody) vtbody.innerHTML='';
  const elQtd = document.getElementById('rel-v-qtd'); if (elQtd) elQtd.textContent = '0';
  const elRec = document.getElementById('rel-v-receita'); if (elRec) elRec.textContent = format(0);
  const elLucroRel = document.getElementById('rel-v-lucro'); if (elLucroRel) elLucroRel.textContent = format(0);
  const elMed = document.getElementById('rel-v-media'); if (elMed) elMed.textContent = format(0);
  const elCnt = document.getElementById('rel-v-count'); if (elCnt) elCnt.textContent = '0';
  const elUlt = document.getElementById('rel-v-ultima'); if (elUlt) elUlt.textContent = '-';
  const qtbody = document.querySelector('#rel-vendas-qr tbody'); if (qtbody) qtbody.innerHTML='';
  const mtbody = document.querySelector('#rel-mats tbody'); if (mtbody) mtbody.innerHTML='';
  const elQtdQR = document.getElementById('qr-v-qtd'); if (elQtdQR) elQtdQR.textContent = '0';
  const elRecQR = document.getElementById('qr-v-receita'); if (elRecQR) elRecQR.textContent = format(0);
  const elMedQR = document.getElementById('qr-v-media'); if (elMedQR) elMedQR.textContent = format(0);
  const elCntQR = document.getElementById('qr-v-count'); if (elCntQR) elCntQR.textContent = '0';
  const elUltQR = document.getElementById('qr-v-ultima'); if (elUltQR) elUltQR.textContent = '-';
  const imgRel = document.getElementById('rel-p-photo'); if (imgRel) imgRel.src = '/brand/produtos.png';
  if (chartLucro){ try{ chartLucro.destroy(); } catch{} chartLucro = null; }
  if (window.chartImpostos){ try{ window.chartImpostos.destroy(); } catch{} window.chartImpostos = null; }
  if (window.chartVendasQR){ try{ window.chartVendasQR.destroy(); } catch{} window.chartVendasQR = null; }
}

function softAppear(targets){
  const arr = Array.isArray(targets) ? targets : [targets];
  arr.forEach(sel => {
    const el = typeof sel === 'string' ? document.querySelector(sel) : sel;
    if (el){
      el.classList.remove('soft-appear');
      void el.offsetWidth;
      el.classList.add('soft-appear');
    }
  });
}

function showToast(html){
  let cont = document.getElementById('toast-container');
  if (!cont){
    cont = document.createElement('div');
    cont.id = 'toast-container';
    cont.className = 'toast-container';
    document.body.appendChild(cont);
  }
  const note = document.createElement('div');
  note.className = 'toast-note soft-appear';
  note.innerHTML = html;
  cont.appendChild(note);
  setTimeout(()=>{
    note.classList.remove('soft-appear');
    note.classList.add('soft-disappear');
    const innerAlert = note.querySelector('.alert');
    if (innerAlert){
      innerAlert.classList.remove('soft-appear');
      innerAlert.classList.add('soft-disappear');
    }
    setTimeout(()=>{
      note.remove();
      if (cont && cont.childElementCount === 0) cont.remove();
    }, 220);
  }, 3000);
}

function getProdutoForm(){
  return {
    nome: document.getElementById('p-nome').value,
    sku: document.getElementById('p-sku').value,
    ml_classico: document.getElementById('p-ml-classico').value,
    ml_premium: document.getElementById('p-ml-premium').value,
    mag: document.getElementById('p-mag').value,
    sh: document.getElementById('p-sh').value,
  };
}

async function cancelProdutoEdit(){
  if (creatingNovoProduto){
    creatingNovoProduto = false;
    if (prevProdSel){
      selectProduto(prevProdSel);
    } else {
      setProdutoForm({nome:'',sku:'',ml_classico:'',ml_premium:'',mag:'',sh:''});
      setProdutoReadonly(true);
      toggleProdutoButtons({editar:true, salvar:false, cancelar:false});
      toggleRemover(false);
      resetProdutoPhoto();
    }
    const vinc = document.getElementById('c-vincular'); if (vinc) vinc.disabled = true;
    // Garantir que a composição volte a ficar bloqueada e sem pendências
    try { pendingComposition = []; } catch(err) {}
    setCompReadonly(true);
    try { refreshComposicao(); } catch(err) {}
    toggleCompButtons({editar:false, salvar:false, cancelar:false});
    showProdMsg('<div class="alert alert-secondary alert-dismissible fade show" role="alert">Criação cancelada.<button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button></div>');
    prevProdSel = null;
    togglePhotoBtn(false);
    pendingPhotoFile = null;
    return;
  }
  if (prodEditSnapshot){
    setProdutoForm(prodEditSnapshot);
  }
  setProdutoReadonly(true);
  toggleProdutoButtons({editar:true, salvar:false, cancelar:false});
  showProdMsg('<div class="alert alert-secondary alert-dismissible fade show" role="alert">Edição cancelada.<button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button></div>');
  togglePhotoBtn(false);
  await refreshComposicao();
  setCompReadonly(true);
  toggleCompButtons({editar:true, salvar:false, cancelar:false});
  toggleRemover(true);
}

// Matérias
let matSel = null;
async function initMaterias(){
  try{
    await refreshMaterias();
    const s = document.getElementById('m-salvar'); if (s) s.addEventListener('click', saveMateria);
    const e = document.getElementById('m-editar'); if (e) e.addEventListener('click', enableMatEdit);
    const c = document.getElementById('m-cancelar'); if (c) c.addEventListener('click', cancelMatEdit);
    const n = document.getElementById('m-novo'); if (n) n.addEventListener('click', ()=>{matSel=null; setMatForm({nome:'',un:'',est:'',custo:''}); enableMatEdit(); showMatMsg('');});
    const r = document.getElementById('m-remover'); if (r) r.addEventListener('click', deleteMateria);
  } catch(err){
    showMatMsg('<div class="alert alert-warning">Falha ao carregar matérias</div>');
  }
}

async function refreshMaterias(){
  try{
    const rows = await (await apiFetch('/api/materias')).json();
    const tbody = document.querySelector('#materias tbody');
    if (!tbody) return;
    paginate('materias', rows, (slice) => {
      tbody.innerHTML='';
      slice.forEach(m=>{
        const tr = document.createElement('tr');
        tr.dataset.id = m.id;
        tr.innerHTML = `<td>${m.id}</td><td>${m.nome}</td><td>${m.unidade}</td><td>${parseFloat(m.estoque).toFixed(4).replace(/\.?0+$/, '')}</td><td>${m.custo}</td>`;
        tr.addEventListener('click', ()=>selectMateria(m));
        tbody.appendChild(tr);
      });
    }, 15);
    const firstRow = rows[0];
    if (firstRow) selectMateria(firstRow);
  } catch(err){
    showMatMsg('<div class="alert alert-warning">Não foi possível listar matérias</div>');
  }
}

function selectMateria(m){
  matSel = m;
  const tbody = document.querySelector('#materias tbody');
  if(tbody){
      tbody.querySelectorAll('tr').forEach(r=>r.classList.remove('table-active'));
      const tr = tbody.querySelector(`tr[data-id="${m.id}"]`);
      if(tr) tr.classList.add('table-active');
  }
  setMatForm({nome:m.nome,un:m.unidade,est:m.estoque,custo:m.custo});
  setMatReadonly(true);
  toggleMatButtons({editar:true, salvar:false, cancelar:false});
  showMatMsg('');
}

function setMatForm(o){
  document.getElementById('m-nome').value = o.nome;
  document.getElementById('m-un').value = o.un;
  document.getElementById('m-est').value = o.est;
  document.getElementById('m-custo').value = o.custo;
}

async function saveMateria(){
  const nome = document.getElementById('m-nome').value.trim();
  const unidade = document.getElementById('m-un').value.trim();
  const estoque = parseFloat(document.getElementById('m-est').value||0);
  const custo = parseFloat(document.getElementById('m-custo').value||0);
  if (!matSel){
    const r = await apiFetch('/api/materias', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({nome, unidade, estoque, custo})});
    const j = await r.json();
    matSel = {id:j.id, nome, unidade, estoque, custo};
  } else {
    await apiFetch(`/api/materias/${matSel.id}`, {method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify({nome, unidade, estoque, custo})});
    matSel = {id:matSel.id, nome, unidade, estoque, custo};
  }
  await refreshMaterias();
  await refreshMateriasChoices();
  selectMateria(matSel);
  setMatReadonly(true);
  toggleMatButtons({editar:true, salvar:false, cancelar:false});
  showMatMsg('<div class="alert alert-success alert-dismissible fade show" role="alert">Matéria alterada com sucesso.<button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button></div>');
  auditLog(matSel && matSel.id ? 'materia_editada' : 'materia_criada', {nome});
}

function startNovoProdutoInline(){
  prevProdSel = prodSel;
  creatingNovoProduto = true;
  prodEditSnapshot = null;
  prodSel = null;
  setProdutoForm({nome:'',sku:'',ml_classico:'',ml_premium:'',mag:'',sh:''});
  setProdutoReadonly(false);
  toggleProdutoButtons({editar:false, salvar:true, cancelar:true});
  showProdMsg('<div class="alert alert-info alert-dismissible fade show" role="alert">Criando novo produto.<button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button></div>');
  const tbody = document.querySelector('#comp tbody'); if (tbody) tbody.innerHTML='';
  const vinc = document.getElementById('c-vincular'); if (vinc) vinc.disabled = true;
  setCompReadonly(false);
  toggleCompButtons({editar:false, salvar:false, cancelar:false});
  togglePhotoBtn(true);
  toggleRemover(false);
  pendingPhotoFile = null;
  resetProdutoPhoto();
  const qrList = document.getElementById('qr-list'); if (qrList) qrList.innerHTML='';
  const qrGen = document.getElementById('qr-gen'); if (qrGen) qrGen.disabled = true;
  const qrDelAll = document.getElementById('qr-del-all'); if (qrDelAll) qrDelAll.disabled = true;
  const qrHeader = qrGen ? (qrGen.parentElement && qrGen.parentElement.parentElement) : null; if (qrHeader) qrHeader.classList.add('d-none');
  if (qrList) qrList.classList.add('d-none');
  updateProdListActive();
  softAppear(['#p-salvar','#p-cancelar','#c-mat','#c-qtd','#c-vincular','#comp']);
}

window.addEventListener('message', async (ev)=>{
  if (ev && ev.data && ev.data.event === 'productCreated'){
    await refreshProdutos();
    await loadProdutos();
  }
});

async function deleteMateria(){
  if (!matSel) return;
  const _okMat = await confirmar(`Remover "${matSel.nome}"? O material será desvinculado de todos os produtos.`, "Remover Matéria-Prima");
  if (!_okMat) return;
  auditLog('materia_removida', {nome: matSel.nome});
  await apiFetch(`/api/materias/${matSel.id}`, {method:'DELETE'});
  matSel = null;
  await refreshMaterias();
  await refreshMateriasChoices();
}

function setMatReadonly(ro){
  ['m-nome','m-un','m-est','m-custo'].forEach(id=>{
    const el = document.getElementById(id);
    el.disabled = !!ro;
    el.classList.toggle('bg-body-secondary', !!ro);
  });
}
function toggleMatButtons({editar, salvar, cancelar}){
  document.getElementById('m-editar').classList.toggle('d-none', !editar);
  document.getElementById('m-salvar').classList.toggle('d-none', !salvar);
  document.getElementById('m-cancelar').classList.toggle('d-none', !cancelar);
}
function enableMatEdit(){
  setMatReadonly(false);
  toggleMatButtons({editar:false, salvar:true, cancelar:true});
}
function cancelMatEdit(){
  if (matSel){
    setMatForm({nome:matSel.nome,un:matSel.unidade,est:matSel.estoque,custo:matSel.custo});
  } else {
    setMatForm({nome:'',un:'',est:'',custo:''});
  }
  setMatReadonly(true);
  toggleMatButtons({editar:true, salvar:false, cancelar:false});
  showMatMsg('<div class="alert alert-secondary alert-dismissible fade show" role="alert">Edição cancelada.<button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button></div>');
}
function showMatMsg(html){
  const div = document.getElementById('mat-msg');
  if (div) div.innerHTML = html || '';
}

// Configuração (Taxas)
async function initConfig(){
  try{ await renderTaxas(); } catch(err){ const wrap = document.getElementById('cfg-taxas'); if (wrap) wrap.innerHTML = '<div class="alert alert-warning">Falha ao carregar taxas</div>'; }
  // Inicializa botões de Backup/Importação
  setupBackupUI();
}

async function renderTaxas(){
  const taxes = await (await apiFetch('/api/taxes')).json();
  const wrap = document.getElementById('cfg-taxas');
  if (!wrap) return;
  wrap.innerHTML = '';
  Object.keys(taxes).forEach(nome=>{
    const [p, f, i] = taxes[nome];
    const row = document.createElement('div');
    row.className = 'row g-2 align-items-end mb-2';
    row.innerHTML = `
      <div class="col-sm-3"><label class="form-label">${nome} %</label><input class="form-control" id="tax-${nome}-p" type="number" step="0.01" value="${(p*100).toFixed(2)}"></div>
      <div class="col-sm-3"><label class="form-label">${nome} Fixo</label><input class="form-control" id="tax-${nome}-f" type="number" step="0.01" value="${f.toFixed(2)}"></div>
      <div class="col-sm-3"><label class="form-label">Imposto (%)</label><input class="form-control" id="tax-${nome}-i" type="number" step="0.01" value="${(i*100).toFixed(2)}"></div>
      <div class="col-sm-3"><button class="btn btn-primary" id="tax-${nome}-save">Salvar</button></div>
    `;
    wrap.appendChild(row);
    const btn = document.getElementById(`tax-${nome}-save`);
    if (btn) btn.addEventListener('click', async ()=>{
      const pval = parseFloat(document.getElementById(`tax-${nome}-p`).value||0)/100.0;
      const fval = parseFloat(document.getElementById(`tax-${nome}-f`).value||0);
      const ival = parseFloat(document.getElementById(`tax-${nome}-i`).value||0)/100.0;
      await apiFetch(`/api/taxes/${nome}`, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({percentual:pval, fixo:fval, imposto:ival})});
      await renderTaxas();
      await loadRelatorios();
    });
  });
}
function fixSidebarPosition(){
  const nav = document.querySelector('nav.navbar');
  const h = nav ? nav.offsetHeight : 56;
  document.documentElement.style.setProperty('--nav-h', `${h}px`);
}
function updateProdListActive(){
  const items = document.querySelectorAll('#prod-list .list-group-item');
  let activeEl = null;
  items.forEach(el=>{
    const id = parseInt(el.getAttribute('data-id'));
    const isActive = !!prodSel && id === prodSel.id;
    el.classList.toggle('active', isActive);
    if (isActive) activeEl = el;
  });
  if (activeEl){
    activeEl.scrollIntoView({behavior:'smooth', block:'nearest'});
  }
}

// Vendas
async function initVendas(){
  await loadVendasProdutos();
  await loadVendasPlataformas();
  await updateVendasPriceView();
  initBatchMode();
  const vProdEl = document.getElementById('v-produto'); 
  const pid = parseInt(vProdEl && vProdEl.value ? vProdEl.value : 0);
  // Sempre carrega a lista, mesmo se pid for 0
  await loadVendasList(pid);

  const prodSelEl = document.getElementById('v-produto');
  const platSelEl = document.getElementById('v-plataforma');
  if (prodSelEl) prodSelEl.addEventListener('change', async ()=>{
    await updateVendasPriceView();
    const pid2 = parseInt(prodSelEl.value||0);
    // Removemos a verificação if(pid2) para permitir 0
    await loadVendasList(pid2);
  });
  if (platSelEl) platSelEl.addEventListener('change', async ()=>{
    await updateVendasPriceView();
    // Se estiver em "Todos", talvez não faça sentido recarregar a lista só porque mudou a plataforma do formulário de inserção,
    // mas se o usuário quiser filtrar por plataforma no futuro... por enquanto o formulário de inserção é independente da lista de visualização "Todos".
    // Mas a lista mostra "Últimas Vendas". Se estamos vendo "Todos", a plataforma selecionada no combo não afeta a lista (que mostra todas as plataformas).
    // Se estamos vendo um produto específico, a lista mostra vendas daquele produto (todas plataformas).
    // Então mudar a plataforma NÃO deve afetar a lista, apenas o preço sugerido.
    // O código original recarregava a lista... vamos manter para consistência se ele filtrar no futuro, 
    // mas na implementação atual loadVendasList(pid) só usa o pid.
    const vProdEl3 = document.getElementById('v-produto'); 
    const pid3 = parseInt(vProdEl3 && vProdEl3.value ? vProdEl3.value : 0);
    // Recarrega lista apenas para garantir consistência visual, embora loadVendasList não use plataforma_id
    await loadVendasList(pid3);
  });
  const qtdEl = document.getElementById('v-quantidade');
  if (qtdEl) qtdEl.addEventListener('input', updateResumoVenda);
  const saveBtn = document.getElementById('v-salvar');
  if (saveBtn) saveBtn.addEventListener('click', submitVenda);
  const qrInp = document.getElementById('qr-input');
  const qrBtn = document.getElementById('qr-reg');
  const qrQtd = document.getElementById('qr-qtd');
  if (qrInp){
    qrInp.addEventListener('keydown', async (e)=>{ if (e.key === 'Enter'){ e.preventDefault(); await registerQR(); } });
    setTimeout(()=> qrInp.focus(), 100);
  }
  if (qrBtn) qrBtn.addEventListener('click', registerQR);
}

async function loadVendasProdutos(){
  const r = await apiFetch('/api/produtos');
  const data = await r.json();
  const sel = document.getElementById('v-produto');
  if (!sel) return;
  const prev = sel.value;
  sel.innerHTML = '<option value="0">(Todos os Produtos)</option>';
  data.forEach(p=>{
    const o = document.createElement('option');
    o.value = p.id;
    o.textContent = `${p.id} - ${p.nome}`;
    sel.appendChild(o);
  });
  let targetId = '0';
  if (typeof prodSel !== 'undefined' && prodSel && data.some(d=>String(d.id)===String(prodSel.id))) targetId = prodSel.id;
  else if (prev && (prev === '0' || data.some(d=>String(d.id)===String(prev)))) targetId = prev;
  
  sel.value = targetId;
}

async function loadVendasPlataformas(){
  const r = await apiFetch('/api/platforms');
  const data = await r.json();
  const sel = document.getElementById('v-plataforma');
  if (!sel) return;
  const prev = sel.value;
  sel.innerHTML = '';
  data.forEach(p=>{
    const nome = String(p.nome||'');
    if (nome === 'Mercado Livre'){
      const o1 = document.createElement('option');
      o1.value = p.id;
      o1.textContent = 'Mercado Livre Premium';
      sel.appendChild(o1);
      const o2 = document.createElement('option');
      o2.value = p.id;
      o2.textContent = 'Mercado Livre Clássico';
      sel.appendChild(o2);
    } else {
      const o = document.createElement('option');
      o.value = p.id;
      o.textContent = nome;
      sel.appendChild(o);
    }
  });
  if (prev && data.some(d=>String(d.id)===String(prev))) sel.value = prev;
  else if (data.length) sel.value = data[0].id;
}

async function updateVendasPriceView(){
  const vProdEl = document.getElementById('v-produto');
  const vPlatEl = document.getElementById('v-plataforma');
  const pid = parseInt(vProdEl && vProdEl.value ? vProdEl.value : 0);
  
  if (!pid) {
      const inp = document.getElementById('v-preco-view');
      if(inp) inp.value = '';
      updateResumoVenda();
      return;
  }

  const platId = parseInt(vPlatEl && vPlatEl.value ? vPlatEl.value : 0);
  const inp = document.getElementById('v-preco-view');
  if (!platId || !inp) return;
  const prices = await (await apiFetch(`/api/prices/${pid}`)).json();
  const el = document.querySelector(`#v-plataforma option[value='${platId}']`);
  const platLabel = el ? (el.textContent || '') : '';
  // Usa o nome exato da opção como chave, com fallback para variantes ML
  let val = Number(prices[platLabel] ?? 0);
  if (!val) {
    const lower = platLabel.toLowerCase();
    if (lower.includes('premium')) val = Number(prices['Mercado Livre Premium'] ?? 0);
    else if (lower.includes('clássico') || lower.includes('classico')) val = Number(prices['Mercado Livre Clássico'] ?? 0);
    else if (lower.includes('mercado livre')) val = Number(prices['Mercado Livre Clássico'] ?? prices['Mercado Livre Premium'] ?? 0);
  }
  vendaPrecoAtual = val;
  inp.value = format(val);
  updateResumoVenda();
}

async function loadVendasList(pid){
  const rows = await (await apiFetch(`/api/vendas/${pid}`)).json();
  const table = document.getElementById('vendas');
  if (!table) return;
  
  const thead = table.querySelector('thead tr');
  const tbody = table.querySelector('tbody');
  tbody.innerHTML = '';

  const isAll = (pid == 0);
  
  if (isAll) {
      thead.innerHTML = '<th>Data</th><th>Produto</th><th>Plataforma</th><th>Qtd</th><th>Preço</th><th style="width:50px"></th>';
  } else {
      thead.innerHTML = '<th>Data</th><th>Plataforma</th><th>Qtd</th><th>Preço</th><th style="width:50px"></th>';
  }

  paginate('vendas', rows, (slice) => {
    tbody.innerHTML = '';
    slice.forEach(r=>{
      const tr = document.createElement('tr');
      let html = `<td>${r.data}</td>`;
      if (isAll) html += `<td>${r.produto_nome || '-'}</td>`;
      html += `<td>${r.plataforma}</td><td>${r.quantidade}</td><td>${Number(r.preco).toFixed(2)}</td>`;
      tr.innerHTML = html;
      const tdAct = document.createElement('td');
      const btn = document.createElement('button');
      btn.className = 'btn btn-sm btn-outline-danger py-0 px-2';
      btn.title = 'Excluir Venda';
      btn.textContent = '×';
      btn.style.fontSize = '1.2rem';
      btn.onclick = () => deleteVenda(r.id, pid);
      tdAct.appendChild(btn);
      tr.appendChild(tdAct);
      tbody.appendChild(tr);
    });
  }, 20);
  softAppear(table);
}

async function deleteVenda(vid, pid){
  const _okVenda = await confirmar('Excluir esta venda? O estoque será restaurado.', 'Excluir Venda');
  if(!_okVenda) return;
  try {
    const r = await apiFetch(`/api/vendas/${vid}`, {method:'DELETE'});
    const j = await r.json();
    if (j.ok){
      showToast('<div class="alert alert-success">Venda excluída</div>');
      auditLog('venda_removida', {id: vid});
      await loadVendasList(pid);
    } else {
      showToast('<div class="alert alert-warning">Erro ao excluir</div>');
    }
  } catch(e){
    showToast('<div class="alert alert-danger">Erro de rede</div>');
  }
}

async function submitVenda(){
  const vProdEl4 = document.getElementById('v-produto'); const pid = parseInt(vProdEl4 && vProdEl4.value ? vProdEl4.value : 0);
  const vPlatEl4 = document.getElementById('v-plataforma'); const plataforma_id = parseInt(vPlatEl4 && vPlatEl4.value ? vPlatEl4.value : 0);
  const vQtdEl = document.getElementById('v-quantidade'); const quantidade = parseInt(vQtdEl && vQtdEl.value ? vQtdEl.value : 1);
  const vDataEl = document.getElementById('v-data'); const dataStr = (vDataEl && vDataEl.value) ? vDataEl.value : new Date().toISOString().slice(0,10);
  if (!pid || !plataforma_id || !quantidade) return;
  let ml_mode = null;
  if (vPlatEl4){
    const opt = vPlatEl4.options[vPlatEl4.selectedIndex];
    const label = opt ? String(opt.textContent||'') : '';
    const low = label.toLowerCase();
    if (low.includes('mercado livre')){
      if (low.includes('premium')) ml_mode = 'premium';
      else if (low.includes('clássico') || low.includes('classico')) ml_mode = 'classico';
    }
  }
  const r = await apiFetch('/api/vendas', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({produto_id: pid, plataforma_id, quantidade, data: dataStr, ml_mode})});
  const j = await r.json();
  if (j && j.id){
    showToast(`<div class="alert alert-success">Venda registrada</div>`);
    await loadVendasList(pid);
    updateResumoVenda();
  } else {
    showToast(`<div class="alert alert-warning">Falha ao registrar venda</div>`);
  }
}

async function registerQR(){
  let inpEl = document.getElementById('qr-input');
  let code = (inpEl && inpEl.value) ? inpEl.value : '';
  code = (code || '').trim().replace(/\s+/g,'').replace(/[^A-Za-z0-9]/g,'');
  const qtdEl = document.getElementById('qr-qtd');
  const qtd = parseInt(qtdEl && qtdEl.value ? qtdEl.value : 1);
  const vProdEl = document.getElementById('v-produto');
  const pidCtx = parseInt(vProdEl && vProdEl.value ? vProdEl.value : 0);
  const vPlatEl = document.getElementById('v-plataforma');
  const plidCtx = parseInt(vPlatEl && vPlatEl.value ? vPlatEl.value : 0);
  if (!code) return;
  const r = await apiFetch('/api/qr/register', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({code, quantidade: qtd, produto_id: pidCtx||undefined, plataforma_id: plidCtx||undefined})});
  const j = await r.json();
  if (j && j.id){
    showToast('<div class="alert alert-success">Venda por QR registrada</div>');
    const pidEl = document.getElementById('v-produto');
    const pid = parseInt(pidEl && pidEl.value ? pidEl.value : 0);
    if (pid) await loadVendasList(pid);
    const inpEl2 = document.getElementById('qr-input'); if (inpEl2) inpEl2.value = '';
  } else {
    const msg = j && j.error ? j.error : 'Código QR inválido';
    showToast(`<div class="alert alert-warning">${msg}</div>`);
  }
}

async function renderQRCodes(){
  const list = document.getElementById('qr-list');
  const genBtn = document.getElementById('qr-gen');
  const genAllBtn = document.getElementById('qr-gen-all');
  const delAllBtn = document.getElementById('qr-del-all');
  if (!list || !prodSel) return;
  list.innerHTML = '';
  const rows = await (await apiFetch(`/api/qr/${prodSel.id}`)).json();
  rows.forEach((row, idx)=>{
    const item = document.createElement('div');
    item.className = 'list-group-item';
    item.style.display = 'grid';
    item.style.gridTemplateColumns = '1fr auto 96px auto';
    item.style.alignItems = 'center';
    item.style.columnGap = '12px';
    const left = document.createElement('div');
    left.className = 'd-flex flex-column';
    left.innerHTML = `<span class=\"fw-semibold\">${row.plataforma}</span>`;

    const dlCol = document.createElement('div');
    dlCol.style.width = 'auto';
    dlCol.style.height = '96px';
    dlCol.className = 'd-flex align-items-center justify-content-center';
    const dlBtn = document.createElement('button');
    dlBtn.className = 'btn btn-sm btn-outline-secondary px-3';
    dlBtn.style.width = 'auto';
    dlBtn.style.height = '36px';
    dlBtn.title = 'Baixar imagem';
    dlBtn.textContent = 'Baixar';
    dlBtn.onclick = async ()=>{
      try{
        const size = 512;
        // Tenta salvar direto em disco via endpoint (funciona no WebView)
        try{
          let urlSave = `/api/qr/png/save/${prodSel.id}/${row.plataforma_id}?size=${size}`;
          if (row.ml_mode) urlSave += `&ml_mode=${row.ml_mode}`;
          const resp = await fetch(urlSave);
          if (resp.ok){
            const data = await resp.json();
            if (data && data.ok){
              showToast(`<div class=\"alert alert-success\">Imagem salva em: ${data.path}</div>`);
              return;
            }
          }
        } catch(_){ /* ignora e faz fallback */ }
        // Fallback: baixar via Content-Disposition no navegador
        let url = `/api/qr/png/${prodSel.id}/${row.plataforma_id}?size=${size}`;
        if (row.ml_mode) url += `&ml_mode=${row.ml_mode}`;
        const a = document.createElement('a');
        a.href = url;
        a.rel = 'noopener';
        a.target = '_self';
        document.body.appendChild(a);
        a.click();
        a.remove();
      } catch(e){
        showToast('<div class=\"alert alert-warning\">Erro ao baixar imagem</div>');
      }
    };
    dlCol.appendChild(dlBtn);

    const qrBox = document.createElement('div');
    qrBox.style.width = '96px';
    qrBox.style.height = '96px';
    qrBox.className = 'd-flex align-items-center justify-content-center';
    const actions = document.createElement('div');
    const delBtn = document.createElement('button');
    delBtn.className = 'btn btn-sm btn-outline-danger';
    delBtn.textContent = 'Remover';
    delBtn.onclick = async ()=>{ 
        let url = `/api/qr/${prodSel.id}/${row.plataforma_id}`;
        if (row.ml_mode) url += `?ml_mode=${row.ml_mode}`;
        await fetch(url, {method:'DELETE'}); 
        await renderQRCodes(); 
        showToast('<div class=\"alert alert-warning\">Código removido</div>'); 
    };
    const copyBtn = document.createElement('button');
    copyBtn.className = 'btn btn-sm btn-outline-secondary ms-2';
    copyBtn.textContent = 'Copiar';
    copyBtn.onclick = async ()=>{ try{ await navigator.clipboard.writeText(row.code); showToast('<div class=\"alert alert-success\">Código copiado</div>'); } catch { const tmp = document.createElement('input'); tmp.value = row.code; document.body.appendChild(tmp); tmp.select(); document.execCommand('copy'); tmp.remove(); showToast('<div class=\"alert alert-success\">Código copiado</div>'); } };


    actions.appendChild(delBtn);
    actions.appendChild(copyBtn);
    item.appendChild(left);
    item.appendChild(dlCol);
    item.appendChild(qrBox);
    item.appendChild(actions);
    list.appendChild(item);
    if (window.QRCode){
      new QRCode(qrBox, {text: row.code, width: 96, height: 96});
    }
  });
  if (genBtn){
    genBtn.onclick = async ()=>{
      await apiFetch(`/api/qr/${prodSel.id}?force=1`, {method:'POST'});
      await renderQRCodes();
      showToast('<div class="alert alert-success">Códigos QR atualizados</div>');
    };
  }
  if (genAllBtn){
    genAllBtn.onclick = async ()=>{
      if(!confirm('Isso irá gerar/atualizar QR Codes para TODOS os produtos ativos. Deseja continuar?')) return;
      try {
        const resp = await apiFetch('/api/qr/generate_all_global', {method:'POST'});
        const data = await resp.json();
        if (data.ok){
          showToast(`<div class="alert alert-success">Processo concluído! ${data.count} QR Codes verificados/gerados.</div>`);
          await renderQRCodes();
        } else {
          showToast('<div class="alert alert-danger">Erro ao processar QR Codes globais.</div>');
        }
      } catch(e) {
        showToast('<div class="alert alert-danger">Erro de comunicação.</div>');
      }
    };
  }
  if (delAllBtn){
    delAllBtn.onclick = async ()=>{
      await apiFetch(`/api/qr/${prodSel.id}`, {method:'DELETE'});
      await renderQRCodes();
      showToast('<div class="alert alert-warning">Todos os códigos removidos</div>');
    };
  }
}

function updateResumoVenda(){
  const qEl = document.getElementById('v-quantidade');
  const q = parseInt(qEl && qEl.value ? qEl.value : 1);
  const pi = document.getElementById('v-preco-info');
  const qi = document.getElementById('v-qtd-info');
  const ti = document.getElementById('v-total-info');
  if (pi) pi.textContent = format(vendaPrecoAtual);
  if (qi) qi.textContent = String(q);
  if (ti) ti.textContent = format(vendaPrecoAtual * q);
}

// atualizar opções de produto da aba vendas quando produto é salvo ou removido
function loadProdutoPhoto(){
  const img = document.getElementById('p-photo');
  if (!img || !prodSel) return;
  const ts = Date.now();
  img.src = `/static/uploads/${prodSel.id}.png?ts=${ts}`;
  img.onerror = ()=>{ img.src = '/brand/produtos.png'; };
}

async function uploadProdutoPhoto(){
  if (!prodSel) return;
  const file = document.getElementById('p-photo-file').files[0];
  if (!file) return;
  const buf = await file.arrayBuffer();
  await apiFetch(`/api/products/${prodSel.id}/photo`, {method:'POST', headers:{'Content-Type':'application/octet-stream'}, body: buf});
  loadProdutoPhoto();
}

async function handlePhotoChange(){
  const file = document.getElementById('p-photo-file').files[0];
  if (!file) return;
  if (!prodSel){
    pendingPhotoFile = file;
    const img = document.getElementById('p-photo');
    if (img){ img.src = URL.createObjectURL(file); }
    return;
  }
  await uploadProdutoPhoto();
}

function resetProdutoPhoto(){
  const img = document.getElementById('p-photo');
  if (!img) return;
  img.src = '/brand/produtos.png';
  const file = document.getElementById('p-photo-file');
  if (file) file.value = '';
}
async function initQRTab(){
  const inp = document.getElementById('qr2-input');
  const qtd = document.getElementById('qr2-qtd');
  const btn = document.getElementById('qr2-reg');
  const tableBody = document.querySelector('#qr2-last tbody');
  if (inp){ setTimeout(()=> inp.focus(), 100); inp.addEventListener('keydown', async (e)=>{ if (e.key==='Enter'){ e.preventDefault(); await registerQR2(); } }); }
  if (btn) btn.onclick = registerQR2;
  // carregar últimas vendas globais (opcional: últimas 20)
  try{
    const r = await apiFetch('/api/produtos');
    const prods = await r.json();
    // mostra nada aqui; deixamos tabela para mostrar resultados após registro
    if (tableBody) tableBody.innerHTML='';
  } catch {}
}

async function registerQR2(){
  let inp2 = document.getElementById('qr2-input');
  let code = (inp2 && inp2.value) ? inp2.value : '';
  code = (code || '').trim().replace(/\s+/g,'').replace(/[^A-Za-z0-9]/g,'');
  const qtdEl2 = document.getElementById('qr2-qtd');
  const qtd = parseInt(qtdEl2 && qtdEl2.value ? qtdEl2.value : 1);
  if (!code) return;
  const r = await apiFetch('/api/qr/register', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({code, quantidade: qtd})});
  const j = await r.json();
  if (j && j.id){
    showToast('<div class="alert alert-success">Venda por QR registrada</div>');
    const inpAgain = document.getElementById('qr2-input'); if (inpAgain) inpAgain.value = '';
    await refreshQR2Last(j.produto_id);
  } else {
    const msg = j && j.error ? j.error : 'Código QR inválido';
    showToast(`<div class="alert alert-warning">${msg}</div>`);
  }
}

async function refreshQR2Last(produtoId){
  try{
    const rows = await (await apiFetch(`/api/vendas/${produtoId}`)).json();
    const tbody = document.querySelector('#qr2-last tbody');
    if (!tbody) return;
    tbody.innerHTML='';
    rows.slice(0,10).forEach(r=>{
      const tr = document.createElement('tr');
      tr.innerHTML = `<td>${produtoId}</td><td>${r.plataforma}</td><td>${r.quantidade}</td><td>${Number(r.preco).toFixed(2)}</td><td>${r.data}</td>`;
      tbody.appendChild(tr);
    });
  } catch {}
}

// Backup & Importação (Configurações)
function setupBackupUI(){
  const expBtn = document.getElementById('backup-export');
  const impBtn = document.getElementById('backup-import');
  const fileInp = document.getElementById('backup-file');
  const saveBtn = document.getElementById('backup-save-direct');
  if (expBtn){ expBtn.onclick = exportBackup; }
  if (impBtn){ impBtn.onclick = importBackup; }
  if (saveBtn){ saveBtn.onclick = saveBackupDirect; }
  if (fileInp){ fileInp.addEventListener('change', ()=> showBackupMsg('')); }
}

function showBackupMsg(html){
  const div = document.getElementById('backup-msg');
  if (div) div.innerHTML = html || '';
}

async function exportBackup(){
  // Primeiro tenta salvar diretamente na pasta Downloads via backend
  try{
    const respSave = await apiFetch('/api/backup/save?dest=downloads', {method:'POST'});
    const j = await respSave.json();
    if (respSave.ok && j && j.ok){
      const path = (j.path||'').replace(/\\/g,'/');
      showBackupMsg(`<div class="alert alert-success alert-dismissible fade show" role="alert">Backup salvo em Downloads: <code>${path}</code><button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button></div>`);
      return;
    }
  } catch(_e){ /* continua com fallback de download */ }
  // Fallback: baixar pelo navegador
  try{
    const resp = await apiFetch('/api/backup');
    if (!resp.ok) throw new Error('Falha ao gerar backup');
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'bellart-backup.zip';
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    showBackupMsg('<div class="alert alert-success alert-dismissible fade show" role="alert">Backup gerado e baixado com sucesso.<button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button></div>');
  } catch(e){
    showBackupMsg('<div class="alert alert-warning alert-dismissible fade show" role="alert">Não foi possível gerar o backup.<button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button></div>');
  }
}

async function importBackup(){
  try{
    const inp = document.getElementById('backup-file');
    const file = inp && inp.files && inp.files[0];
    if (!file){
      showBackupMsg('<div class="alert alert-secondary alert-dismissible fade show" role="alert">Selecione um arquivo .zip para importar.<button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button></div>');
      return;
    }
    const buf = await file.arrayBuffer();
    const resp = await apiFetch('/api/restore', {method:'POST', headers:{'Content-Type':'application/zip'}, body: buf});
    const j = await resp.json();
    if (j && j.ok){
      showBackupMsg('<div class="alert alert-success alert-dismissible fade show" role="alert">Importação concluída. Dados atualizados.<button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button></div>');
      // Recarrega dados relevantes
      try{ await refreshProdutos(); await loadProdutos(); } catch {}
      try{ await refreshMaterias(); } catch {}
      try{ await renderTaxas(); await loadRelatorios(); } catch {}
      // Atualiza foto do produto selecionado, se houver
      try{ loadProdutoPhoto(); } catch {}
    } else {
      const msg = j && j.error ? j.error : 'Falha ao importar backup';
      showBackupMsg(`<div class="alert alert-warning alert-dismissible fade show" role="alert">${msg}<button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button></div>`);
    }
  } catch(e){
    showBackupMsg('<div class="alert alert-warning alert-dismissible fade show" role="alert">Erro ao importar backup.<button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button></div>');
  }
}

async function saveBackupDirect(){
  try{
    const resp = await apiFetch('/api/backup/save', {method:'POST'});
    const j = await resp.json();
    if (j && j.ok){
      const path = (j.path||'').replace(/\\/g,'/');
      showBackupMsg(`<div class="alert alert-success alert-dismissible fade show" role="alert">Backup salvo em: <code>${path}</code><button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button></div>`);
    } else {
      const msg = j && j.error ? j.error : 'Falha ao salvar backup diretamente';
      showBackupMsg(`<div class="alert alert-warning alert-dismissible fade show" role="alert">${msg}<button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button></div>`);
    }
  } catch(e){
    showBackupMsg('<div class="alert alert-warning alert-dismissible fade show" role="alert">Erro ao salvar backup diretamente.<button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button></div>');
  }
}

// Batch Mode
let batchItems = [];

async function initBatchMode(){
  const startBtn = document.getElementById('btn-start-batch');
  const closeBtn = document.getElementById('btn-close-batch');
  const finishBtn = document.getElementById('btn-finish-batch');
  const inp = document.getElementById('batch-input');
  
  if(startBtn) startBtn.onclick = startBatch;
  if(closeBtn) closeBtn.onclick = closeBatch;
  if(finishBtn) finishBtn.onclick = finishBatch;
  
  if(inp){
    let batchTimer = null;
    const processCode = async () => {
        const code = inp.value.trim();
        if(code){
            inp.value = '';
            await addBatchItem(code);
        }
    };

    inp.addEventListener('keydown', async (e)=>{
      if(e.key === 'Enter'){
        e.preventDefault();
        if(batchTimer) clearTimeout(batchTimer);
        await processCode();
      }
    });
    
    inp.addEventListener('input', ()=>{
        if(batchTimer) clearTimeout(batchTimer);
        batchTimer = setTimeout(async ()=>{
            await processCode();
        }, 300);
    });

    // Keep focus
    inp.addEventListener('blur', ()=> setTimeout(()=>inp.focus(), 100));
  }
}

function startBatch(){
  batchItems = [];
  renderBatchTable();
  document.getElementById('batch-overlay').classList.remove('d-none');
  setTimeout(()=> document.getElementById('batch-input').focus(), 200);
}

function closeBatch(){
  if(batchItems.length > 0 && !confirm('Existem itens não salvos. Deseja sair?')) return;
  document.getElementById('batch-overlay').classList.add('d-none');
  batchItems = [];
}

async function addBatchItem(code){
  try {
      code = code.replace(/\s+/g,'').replace(/[^A-Za-z0-9-]/g,'');
      if(!code) return;
      
      const r = await apiFetch(`/api/qr/lookup?code=${encodeURIComponent(code)}`);
      const data = await r.json();
      if(data.error){
          showToast(`<div class="alert alert-warning">${data.error}</div>`);
          return;
      }
      batchItems.push({
          produto_id: data.produto_id,
          plataforma_id: data.plataforma_id,
          produto_nome: data.produto_nome,
          plataforma_nome: data.plataforma_nome,
          ml_mode: data.ml_mode || null,
          code: code,
          quantidade: 1
      });
      renderBatchTable();
  } catch(e){
      console.error(e);
      showToast('<div class="alert alert-danger">Erro ao buscar código</div>');
  }
}

function renderBatchTable(){
    const tbody = document.querySelector('#batch-table tbody');
    const countEl = document.getElementById('batch-total-count');
    tbody.innerHTML = '';
    batchItems.forEach((item, idx) => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${idx + 1}</td>
            <td>${item.produto_nome}</td>
            <td>${item.plataforma_nome}</td>
            <td><button class="btn btn-sm btn-outline-danger" onclick="removeBatchItem(${idx})">×</button></td>
        `;
        tbody.appendChild(tr);
    });
    countEl.textContent = batchItems.length;
    const container = document.querySelector('#batch-table').parentElement;
    if(container) container.scrollTop = container.scrollHeight;
}

function removeBatchItem(idx){
    batchItems.splice(idx, 1);
    renderBatchTable();
}

async function finishBatch(){
    if(batchItems.length === 0) return;
    try {
        const r = await apiFetch('/api/vendas/batch', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(batchItems)
        });
        const res = await r.json();
        if(res.ok){
            showToast(`<div class="alert alert-success">${res.count} vendas registradas com sucesso!</div>`);
            batchItems = [];
            document.getElementById('batch-overlay').classList.add('d-none');
             const vProdEl = document.getElementById('v-produto');
             const pid = parseInt(vProdEl && vProdEl.value ? vProdEl.value : 0);
             await loadVendasList(pid);
        } else {
            showToast('<div class="alert alert-danger">Erro ao salvar vendas</div>');
        }
    } catch(e){
        showToast('<div class="alert alert-danger">Erro de rede</div>');
    }
}