/**
 * Tools & MCP Store JavaScript
 * Handles multi-MCP servers configuration, discovery of tools, SSE sync, and active state toggling.
 */

let userMcpServers = [];
let mcpSyncAlert = null;
let mcpServersGrid = null;
let mcpToolsContainer = null;
let mcpToolsCount = null;
let mcpActiveCountBadge = null;
let mcpTotalCountBadge = null;
let mcpModal = null;

async function loadMcpServers() {
  try {
    const res = await fetch('/api/agents/mcp/');
    const data = await res.json();
    if (data.status === 'success') {
      userMcpServers = data.servers || [];
      renderMcpServersGrid(userMcpServers);
    }
  } catch (err) {
    console.error('Error loading MCP servers list:', err);
  }
}

function renderMcpServersGrid(servers) {
  if (!mcpServersGrid) return;

  const activeServers = servers.filter(s => s.is_active);
  if (mcpActiveCountBadge) mcpActiveCountBadge.innerText = activeServers.length;
  if (mcpTotalCountBadge) mcpTotalCountBadge.innerText = servers.length;

  let allActiveTools = [];
  activeServers.forEach(s => {
    (s.cached_tools || []).forEach(t => {
      allActiveTools.push({ ...t, server_id: s.id, server_name: s.name, server_url: s.server_url, last_synced_at: s.last_synced_at });
    });
  });
  if (mcpToolsCount) mcpToolsCount.innerText = allActiveTools.length;

  if (servers.length === 0) {
    const noServersTitle = window.t ? window.t('store_no_servers_title', 'لا توجد خوادم MCP مربوطة حالياً') : 'لا توجد خوادم MCP مربوطة حالياً';
    const noServersDesc = window.t ? window.t('store_no_servers_desc', 'يمكنك ربط خادم أدوات خارجي عبر بروتوكول FastMCP SSE لتمكين المساعد الصوتي من استدعاء دواله أثناء المكالمات.') : 'يمكنك ربط خادم أدوات خارجي عبر بروتوكول FastMCP SSE لتمكين المساعد الصوتي من استدعاء دواله أثناء المكالمات.';
    const btnNewLink = window.t ? window.t('store_btn_new_server_link', 'ربط خادم MCP جديد') : 'ربط خادم MCP جديد';
    mcpServersGrid.innerHTML = `
      <div class="col-span-full text-center py-10 px-4 bg-slate-50 rounded-xl border-2 border-dashed border-slate-200 space-y-3">
        <svg class="w-8 h-8 mx-auto text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
        <h4 class="text-sm font-bold text-slate-900">${noServersTitle}</h4>
        <p class="text-xs text-slate-500">${noServersDesc}</p>
        <button type="button" onclick="openMcpModal(null)" class="px-5 py-2 rounded-lg bg-[#7c3aed] hover:bg-[#6d28d9] text-white text-xs font-medium transition inline-flex items-center gap-1.5 shadow-2xs">
          <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/>
          </svg>
          <span>${btnNewLink}</span>
        </button>
      </div>
    `;
  } else {
    const discToolsLabel = window.t ? window.t('store_discovered_tools', 'الدوال المكتشفة:') : 'الدوال المكتشفة:';
    const syncedLabel = window.t ? window.t('store_synced_at', 'مزامنة:') : 'مزامنة:';
    const neverSyncedLabel = window.t ? window.t('store_never_synced', 'لم تتم المزامنة') : 'لم تتم المزامنة';
    const syncHint = window.t ? window.t('store_btn_sync_hint', 'فحص وتحديث الأدوات') : 'فحص وتحديث الأدوات';
    const editHint = window.t ? window.t('store_btn_edit_hint', 'تعديل الإعدادات') : 'تعديل الإعدادات';
    const deleteHint = window.t ? window.t('store_btn_delete_hint', 'حذف الخادم') : 'حذف الخادم';

    mcpServersGrid.innerHTML = servers.map(s => {
      const toolsCount = (s.cached_tools || []).length;
      const statusDotClass = s.is_active ? 'bg-emerald-500 animate-pulse' : 'bg-slate-400';
      const badgeClass = s.is_active 
        ? 'bg-emerald-50 border border-emerald-200 text-emerald-700' 
        : 'bg-slate-100 border border-slate-200 text-slate-600';
      const badgeText = s.is_active 
        ? (window.t ? window.t('store_status_active', 'مفعل للمكالمات') : 'مفعل للمكالمات') 
        : (window.t ? window.t('store_status_disabled', 'معطل') : 'معطل');
      const toggleBtnText = s.is_active 
        ? (window.t ? window.t('store_btn_disable', 'تعطيل') : 'تعطيل') 
        : (window.t ? window.t('store_btn_enable', 'تفعيل') : 'تفعيل');
      const toggleBtnClass = s.is_active
        ? 'bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200'
        : 'bg-emerald-50 hover:bg-emerald-100 text-emerald-700 border border-emerald-200 font-medium';

      return `
        <div class="p-4 rounded-xl bg-white border ${s.is_active ? 'border-violet-300 shadow-2xs' : 'border-slate-200 opacity-85'} hover:border-slate-300 transition-all flex flex-col justify-between space-y-4">
          <div class="space-y-3">
            <div class="flex items-start justify-between gap-2">
              <div class="flex items-center gap-2.5 min-w-0">
                <span class="w-2.5 h-2.5 rounded-full ${statusDotClass} shrink-0"></span>
                <h4 class="font-bold text-xs text-slate-900 truncate" title="${s.name}">${s.name}</h4>
              </div>
              <span class="px-2 py-0.5 rounded-full text-xs font-semibold shrink-0 ${badgeClass}">${badgeText}</span>
            </div>

            <div class="p-2.5 rounded-lg bg-slate-50 border border-slate-200 font-mono text-xs text-slate-700 truncate" title="${s.server_url}">
              <span class="text-slate-400 select-none text-xs">SSE: </span>${s.server_url}
            </div>

            <div class="flex items-center justify-between text-xs text-slate-500 pt-1">
              <span>${discToolsLabel} <strong class="text-slate-900 font-mono">${toolsCount}</strong></span>
              <span>${s.last_synced_at ? `${syncedLabel} ${s.last_synced_at}` : neverSyncedLabel}</span>
            </div>
          </div>

          <div class="pt-3 border-t border-slate-200 flex items-center justify-between gap-1.5 text-xs">
            <button type="button" onclick="toggleMcpActive(${s.id})" class="px-3 py-1.5 rounded-lg text-xs font-medium transition ${toggleBtnClass}">
              ${toggleBtnText}
            </button>
            <div class="flex items-center gap-1">
              <button type="button" onclick="syncMcpServer(${s.id})" class="p-1.5 rounded-lg bg-slate-50 hover:bg-slate-100 text-slate-700 border border-slate-200 transition" title="${syncHint}">
                <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
              </button>
              <button type="button" onclick="openMcpModal(${s.id})" class="p-1.5 rounded-lg bg-slate-50 hover:bg-slate-100 text-slate-700 border border-slate-200 transition" title="${editHint}">
                <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                </svg>
              </button>
              <button type="button" onclick="deleteMcpServer(${s.id})" class="p-1.5 rounded-lg bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 transition" title="${deleteHint}">
                <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              </button>
            </div>
          </div>
        </div>
      `;
    }).join('');
  }

  if (!mcpToolsContainer) return;
  if (allActiveTools.length === 0) {
    const noToolsMsg = window.t ? window.t('store_no_tools_discovered', 'لا توجد أدوات مكتشفة من الخوادم المفعلة حالياً. اضغط على زر التحديث لأي خادم لقراءة دواله.') : 'لا توجد أدوات مكتشفة من الخوادم المفعلة حالياً. اضغط على زر التحديث لأي خادم لقراءة دواله.';
    mcpToolsContainer.innerHTML = `
      <div class="col-span-full text-center py-6 text-slate-500 text-xs bg-slate-50 rounded-xl border border-dashed border-slate-200">
        ${noToolsMsg}
      </div>
    `;
  } else {
    const noDesc = window.t ? window.t('store_no_desc', 'بدون وصف') : 'بدون وصف';
    mcpToolsContainer.innerHTML = allActiveTools.map(t => {
      const schema = t.parameters || t.inputSchema || {};
      const props = schema.properties || {};
      const requiredList = schema.required || [];
      const paramKeys = Object.keys(props);
      const schemaBadges = paramKeys.length > 0
        ? paramKeys.map(k => {
            const p = props[k] || {};
            const isReq = requiredList.includes(k);
            const pType = p.type || 'string';
            return `<span class="px-1.5 py-0.5 rounded bg-slate-50 border border-slate-200 text-slate-700 font-mono text-2xs" title="${escapeHtml(p.description || '')}"><strong>${escapeHtml(k)}</strong>: <span class="text-violet-600">${escapeHtml(pType)}</span>${isReq ? ' <span class="text-rose-500 font-bold" title="إلزامي">*</span>' : ''}</span>`;
          }).join(' ')
        : '<span class="text-slate-400 text-2xs italic">لا يتطلب معاملات</span>';

      return `
        <div class="p-4 rounded-xl bg-white border border-slate-200 hover:border-slate-300 transition shadow-2xs space-y-3 flex flex-col justify-between">
          <div class="space-y-2.5">
            <div class="flex items-start justify-between gap-2">
              <div class="flex items-center gap-1.5 min-w-0">
                <svg class="w-4 h-4 text-[#7c3aed] shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
                <span class="font-mono font-bold text-slate-900 text-xs truncate" title="${escapeHtml(t.name)}">
                  ${escapeHtml(t.name)}
                </span>
              </div>
              <span class="text-2xs px-2 py-0.5 rounded-full bg-slate-100 border border-slate-200 text-slate-600 font-medium shrink-0 truncate max-w-[120px]" title="${escapeHtml(t.server_url)}">
                ${escapeHtml(t.server_name)}
              </span>
            </div>

            <p class="text-slate-600 text-xs leading-relaxed line-clamp-2" title="${escapeHtml(t.description)}">
              ${escapeHtml(t.description || noDesc)}
            </p>

            <div class="flex flex-wrap items-center gap-1.5 pt-1">
              <span class="px-2 py-0.5 rounded-md text-2xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200 inline-flex items-center gap-1">
                <span class="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                <span>متزامن مع Chatwoot Captain</span>
              </span>
            </div>

            <div class="pt-2 border-t border-slate-100 space-y-1">
              <span class="text-2xs text-slate-400 font-medium block">مخطط المُدخلات (Input Schema):</span>
              <div class="flex flex-wrap gap-1 items-center">
                ${schemaBadges}
              </div>
            </div>
          </div>

          <div class="pt-3 border-t border-slate-100">
            <button 
              type="button" 
              onclick="openToolQuickTest('${escapeHtml(t.name)}', ${t.server_id || 0})" 
              class="w-full px-3 py-1.5 rounded-lg bg-[#7c3aed] hover:bg-[#6d28d9] text-white text-xs font-medium transition inline-flex items-center justify-center gap-1.5 shadow-2xs"
            >
              <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
              </svg>
              <span>تجربة مباشرة (Live Test)</span>
            </button>
          </div>
        </div>
      `;
    }).join('');
  }
}

function openToolQuickTest(toolName, serverId) {
  if (!serverId && userMcpServers) {
    const s = userMcpServers.find(srv => (srv.cached_tools || []).some(t => t.name === toolName));
    if (s) serverId = s.id;
  }
  openMcpModal(serverId);
  const playground = document.getElementById('modal-tool-playground');
  if (playground) {
    playground.classList.remove('hidden');
    playground.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
  const toolSelect = document.getElementById('playground-tool-select');
  if (toolSelect && toolSelect.options) {
    for (let i = 0; i < toolSelect.options.length; i++) {
      if (toolSelect.options[i].text === toolName) {
        toolSelect.selectedIndex = i;
        onPlaygroundToolChange();
        break;
      }
    }
  }
}

let currentModalDiscoveredTools = [];

function populatePlaygroundTools(tools) {
  const playground = document.getElementById('modal-tool-playground');
  const toolSelect = document.getElementById('playground-tool-select');
  const countBadge = document.getElementById('playground-tools-count-badge');
  if (!playground || !toolSelect) return;

  if (!tools || tools.length === 0) {
    playground.classList.add('hidden');
    return;
  }

  playground.classList.remove('hidden');
  if (countBadge) countBadge.innerText = `${tools.length} أداة`;

  toolSelect.innerHTML = tools.map((t, idx) => {
    return `<option value="${idx}">${escapeHtml(t.name)}</option>`;
  }).join('');

  onPlaygroundToolChange();
}

function onPlaygroundToolChange() {
  const toolSelect = document.getElementById('playground-tool-select');
  const descEl = document.getElementById('playground-tool-desc');
  const resContainer = document.getElementById('playground-result-container');
  if (resContainer) resContainer.classList.add('hidden');

  if (!toolSelect || !currentModalDiscoveredTools.length) return;
  const idx = parseInt(toolSelect.value) || 0;
  const tool = currentModalDiscoveredTools[idx];
  if (!tool) return;

  if (descEl) {
    descEl.innerText = tool.description || 'لا يوجد وصف توضيحي لهذه الأداة.';
  }

  fillPlaygroundSampleArgs();
}

function fillPlaygroundSampleArgs() {
  const toolSelect = document.getElementById('playground-tool-select');
  const argsEl = document.getElementById('playground-tool-args');
  if (!toolSelect || !argsEl || !currentModalDiscoveredTools.length) return;

  const idx = parseInt(toolSelect.value) || 0;
  const tool = currentModalDiscoveredTools[idx];
  if (!tool) return;

  const schema = tool.parameters || {};
  const props = schema.properties || {};
  const required = schema.required || [];

  const sample = {};
  for (const [key, prop] of Object.entries(props)) {
    const pType = (prop.type || 'string').toLowerCase();
    if (pType === 'string') {
      sample[key] = prop.default || (required.includes(key) ? "قيمة تجريبية" : "");
    } else if (pType === 'integer' || pType === 'number') {
      sample[key] = prop.default !== undefined ? prop.default : 1;
    } else if (pType === 'boolean') {
      sample[key] = prop.default !== undefined ? prop.default : true;
    } else if (pType === 'array') {
      sample[key] = [];
    } else if (pType === 'object') {
      sample[key] = {};
    } else {
      sample[key] = "";
    }
  }

  argsEl.value = JSON.stringify(sample, null, 2);
}

async function testMcpConnectionFromModal() {
  const idVal = document.getElementById('modal-mcp-id').value;
  const server_url = document.getElementById('modal-mcp-url').value.trim();
  const auth_token = document.getElementById('modal-mcp-token').value.trim();
  const btn = document.getElementById('btn-test-mcp-conn');
  const btnText = document.getElementById('btn-test-mcp-conn-text');
  const connAlert = document.getElementById('modal-test-conn-alert');
  const latencyBadge = document.getElementById('test-conn-latency-badge');

  if (!server_url) {
    if (connAlert) {
      connAlert.className = 'mt-2.5 p-3 rounded-2xl text-xs bg-rose-50 border border-rose-200 text-rose-800 flex items-center gap-2';
      connAlert.innerHTML = '<span>يرجى إدخال رابط الخادم (Server URL) أولاً.</span>';
      connAlert.classList.remove('hidden');
    }
    return;
  }

  if (btn) btn.disabled = true;
  if (btnText) btnText.innerText = 'جاري الفحص واكتشاف الأدوات...';
  if (connAlert) {
    connAlert.className = 'mt-2.5 p-3 rounded-xl text-xs bg-slate-50 border border-slate-200 text-slate-700 flex items-center gap-2';
    connAlert.innerHTML = '<span>جاري محاولة الاتصال بنقطة نهاية SSE ومصافحة بروتوكول MCP...</span>';
    connAlert.classList.remove('hidden');
  }
  if (latencyBadge) latencyBadge.classList.add('hidden');

  try {
    const res = await fetch('/api/agents/mcp/test-connection/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken')
      },
      body: JSON.stringify({
        id: idVal ? parseInt(idVal) : null,
        server_url,
        auth_token
      })
    });
    const data = await res.json();

    if (data.ok) {
      if (connAlert) {
        connAlert.className = 'mt-2.5 p-3 rounded-xl text-xs bg-emerald-50 border border-emerald-200 text-emerald-800 space-y-1';
        connAlert.innerHTML = `
          <div class="font-bold flex items-center gap-1.5">
            <span>تم الاتصال بالخادم بنجاح!</span>
          </div>
          <div class="text-xs text-emerald-700">
            تم فحص البروتوكول واكتشاف <strong>${data.tools_count}</strong> أداة جاهزة للاستخدام الصوتي.
          </div>
        `;
      }
      if (latencyBadge) {
        latencyBadge.innerText = `${data.latency_ms} ms`;
        latencyBadge.className = 'px-2.5 py-1 rounded-full text-xs font-mono font-medium bg-emerald-50 text-emerald-700 border border-emerald-200';
        latencyBadge.classList.remove('hidden');
      }

      currentModalDiscoveredTools = data.tools || [];
      populatePlaygroundTools(currentModalDiscoveredTools);
    } else {
      if (connAlert) {
        connAlert.className = 'mt-2.5 p-3 rounded-xl text-xs bg-rose-50 border border-rose-200 text-rose-800 space-y-1';
        connAlert.innerHTML = `
          <div class="font-bold flex items-center gap-1.5">
            <span>تعذر الاتصال بخادم MCP:</span>
          </div>
          <div class="text-xs text-rose-700">
            ${escapeHtml(data.error_message || 'فشل الاتصال بالخادم.')}
          </div>
          <div class="text-xs text-slate-500 pt-0.5">
            ملاحظة: يمكنك حفظ الخادم رغم ذلك كـ (معطل) إذا كان قيد الإعداد.
          </div>
        `;
      }
      if (latencyBadge && data.latency_ms) {
        latencyBadge.innerText = `${data.latency_ms} ms`;
        latencyBadge.className = 'px-2.5 py-1 rounded-full text-xs font-mono font-semibold bg-rose-50 text-rose-800 border border-rose-200';
        latencyBadge.classList.remove('hidden');
      }
    }
  } catch (err) {
    if (connAlert) {
      connAlert.className = 'mt-2.5 p-3 rounded-2xl text-xs bg-rose-50 border border-rose-200 text-rose-800 flex items-center gap-2';
      connAlert.innerHTML = `<span>حدث خطأ في الشبكة أثناء طلب الفحص: ${escapeHtml(err.message || '')}</span>`;
    }
  } finally {
    if (btn) btn.disabled = false;
    if (btnText) btnText.innerText = 'فحص الاتصال واكتشاف الأدوات';
  }
}

async function testMcpToolFromModal() {
  const idVal = document.getElementById('modal-mcp-id').value;
  const server_url = document.getElementById('modal-mcp-url').value.trim();
  const auth_token = document.getElementById('modal-mcp-token').value.trim();
  const toolSelect = document.getElementById('playground-tool-select');
  const argsText = document.getElementById('playground-tool-args').value.trim();
  const btn = document.getElementById('btn-execute-test-tool');
  const btnText = document.getElementById('btn-execute-test-tool-text');
  const resContainer = document.getElementById('playground-result-container');
  const execBadge = document.getElementById('playground-exec-badge');
  const resultOutput = document.getElementById('playground-result-output');

  if (!toolSelect || !currentModalDiscoveredTools.length) return;
  const idx = parseInt(toolSelect.value) || 0;
  const tool = currentModalDiscoveredTools[idx];
  if (!tool) return;

  let parsedArgs = {};
  if (argsText) {
    try {
      parsedArgs = JSON.parse(argsText);
    } catch (e) {
      alert('صيغة المُدخلات غير صالحة. يجب أن تكون بتنسيق JSON صحيح (مثل: {"key": "value"}).');
      return;
    }
  }

  if (btn) btn.disabled = true;
  if (btnText) btnText.innerText = 'جاري التنفيذ...';
  if (resContainer) resContainer.classList.remove('hidden');
  if (execBadge) {
    execBadge.innerText = 'جاري الاستدعاء...';
    execBadge.className = 'font-mono text-xs px-2.5 py-0.5 rounded-full font-medium bg-slate-100 text-slate-700 border border-slate-200';
  }
  if (resultOutput) resultOutput.innerText = 'جاري انتظار استجابة الخادم...';

  try {
    const res = await fetch('/api/agents/mcp/test-tool/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken')
      },
      body: JSON.stringify({
        id: idVal ? parseInt(idVal) : null,
        server_url,
        auth_token,
        tool_name: tool.name,
        arguments: parsedArgs
      })
    });
    const data = await res.json();

    if (data.ok) {
      if (execBadge) {
        execBadge.innerText = `ناجح (${data.execution_time_ms} ms)`;
        execBadge.className = 'font-mono text-xs px-2.5 py-0.5 rounded-full font-bold bg-emerald-50 text-emerald-800 border border-emerald-300';
      }
      if (resultOutput) {
        resultOutput.innerText = data.result || 'تم التنفيذ بنجاح بدون نص مخرجات.';
      }
    } else {
      if (execBadge) {
        execBadge.innerText = `فشل (${data.error_type || 'error'}) - ${data.execution_time_ms || 0} ms`;
        execBadge.className = 'font-mono text-xs px-2.5 py-0.5 rounded-full font-bold bg-rose-50 text-rose-800 border border-rose-200';
      }
      if (resultOutput) {
        resultOutput.innerText = data.error_message || data.result || 'فشل تنفيذ الأداة.';
      }
    }
  } catch (err) {
    if (execBadge) {
      execBadge.innerText = 'خطأ شبكة';
      execBadge.className = 'font-mono text-xs px-2.5 py-0.5 rounded-full font-bold bg-rose-50 text-rose-800 border border-rose-200';
    }
    if (resultOutput) {
      resultOutput.innerText = 'حدث خطأ في الاتصال أثناء تنفيذ الأداة: ' + (err.message || '');
    }
  } finally {
    if (btn) btn.disabled = false;
    if (btnText) btnText.innerText = 'تجربة الاستدعاء الآن';
  }
}

function openMcpModal(serverId = null) {
  const modalTitle = document.getElementById('modal-mcp-title');
  const modalBtnDelete = document.getElementById('modal-btn-delete-mcp');
  const idInput = document.getElementById('modal-mcp-id');
  const nameInput = document.getElementById('modal-mcp-name');
  const urlInput = document.getElementById('modal-mcp-url');
  const tokenInput = document.getElementById('modal-mcp-token');
  const activeInput = document.getElementById('modal-mcp-active');

  const connAlert = document.getElementById('modal-test-conn-alert');
  const latencyBadge = document.getElementById('test-conn-latency-badge');
  const playground = document.getElementById('modal-tool-playground');
  const playgroundRes = document.getElementById('playground-result-container');
  if (connAlert) { connAlert.className = 'hidden'; connAlert.innerHTML = ''; }
  if (latencyBadge) { latencyBadge.className = 'hidden'; latencyBadge.innerText = ''; }
  if (playgroundRes) { playgroundRes.classList.add('hidden'); }

  currentModalDiscoveredTools = [];

  if (serverId) {
    const s = userMcpServers.find(x => x.id === serverId);
    if (s) {
      if (modalTitle) modalTitle.innerHTML = '<svg class="w-4 h-4 text-slate-500 inline-block mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/></svg> إعدادات خادم FastMCP';
      if (idInput) idInput.value = s.id;
      if (nameInput) nameInput.value = s.name;
      if (urlInput) urlInput.value = s.server_url;
      if (tokenInput) tokenInput.value = s.auth_token || '';
      if (activeInput) activeInput.checked = s.is_active;
      if (modalBtnDelete) modalBtnDelete.classList.remove('hidden');

      if (Array.isArray(s.cached_tools) && s.cached_tools.length > 0) {
        currentModalDiscoveredTools = s.cached_tools;
        populatePlaygroundTools(s.cached_tools);
      } else if (playground) {
        playground.classList.add('hidden');
      }
    }
  } else {
    if (modalTitle) modalTitle.innerHTML = '<svg class="w-4 h-4 text-[#7c3aed] inline-block mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/></svg> ربط خادم FastMCP خارجي جديد';
    if (idInput) idInput.value = '';
    if (nameInput) nameInput.value = 'خادم FastMCP إضافي';
    if (urlInput) urlInput.value = 'http://';
    if (tokenInput) tokenInput.value = '';
    if (activeInput) activeInput.checked = true;
    if (modalBtnDelete) modalBtnDelete.classList.add('hidden');
    if (playground) playground.classList.add('hidden');
  }
  if (mcpModal) mcpModal.classList.remove('hidden');
}

function closeMcpModal() {
  if (mcpModal) mcpModal.classList.add('hidden');
}

async function saveMcpSettings(e) {
  e.preventDefault();
  const idVal = document.getElementById('modal-mcp-id').value;
  const name = document.getElementById('modal-mcp-name').value.trim();
  const server_url = document.getElementById('modal-mcp-url').value.trim();
  const auth_token = document.getElementById('modal-mcp-token').value.trim();
  const is_active = document.getElementById('modal-mcp-active').checked;

  const btn = document.getElementById('btn-save-mcp-settings');
  if (btn) {
    btn.disabled = true;
    btn.innerText = 'جاري الحفظ...';
  }

  try {
    const res = await fetch('/api/agents/mcp/save/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken')
      },
      body: JSON.stringify({ id: idVal ? parseInt(idVal) : null, name, server_url, auth_token, is_active })
    });
    const data = await res.json();
    if (data.status === 'success') {
      closeMcpModal();
      showToast(data.message, 'success');
      await loadMcpServers();
    } else {
      showToast('فشل الحفظ: ' + (data.message || ''), 'error');
    }
  } catch (err) {
    showToast('حدث خطأ أثناء حفظ الخادم.', 'error');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerText = 'حفظ التعديلات';
    }
  }
}

async function syncMcpServer(serverId = null) {
  if (mcpSyncAlert) {
    mcpSyncAlert.className = 'mt-3 p-3.5 rounded-xl text-xs bg-slate-50 border border-slate-200 text-slate-700 flex items-center gap-2';
    mcpSyncAlert.innerHTML = `<span>جاري فحص الاتصال وتحديث دوال الخادم...</span>`;
    mcpSyncAlert.classList.remove('hidden');
  }

  try {
    const res = await fetch('/api/agents/mcp/sync/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken')
      },
      body: JSON.stringify({ id: serverId })
    });
    const data = await res.json();
    if (data.status === 'success') {
      await loadMcpServers();
      if (mcpSyncAlert) {
        mcpSyncAlert.className = 'mt-3 p-3.5 rounded-2xl text-xs bg-emerald-50 border border-emerald-300 text-emerald-800 flex items-center gap-2';
        mcpSyncAlert.innerHTML = `<span>${data.message}</span>`;
      }
      showToast(data.message, 'success');
    } else {
      if (mcpSyncAlert) {
        mcpSyncAlert.className = 'mt-3 p-3.5 rounded-2xl text-xs bg-rose-50 border border-rose-200 text-rose-800 flex items-center gap-2';
        mcpSyncAlert.innerHTML = `<span>${data.message}</span>`;
      }
      showToast(data.message, 'error');
    }
  } catch (err) {
    if (mcpSyncAlert) {
      mcpSyncAlert.className = 'mt-3 p-3.5 rounded-2xl text-xs bg-rose-50 border border-rose-200 text-rose-800 flex items-center gap-2';
      mcpSyncAlert.innerHTML = `<span>تعذر الاتصال بالخادم.</span>`;
    }
    showToast('تعذر الاتصال بالخادم.', 'error');
  }
}

async function toggleMcpActive(serverId) {
  try {
    const res = await fetch('/api/agents/mcp/toggle/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken')
      },
      body: JSON.stringify({ id: serverId })
    });
    const data = await res.json();
    if (data.status === 'success') {
      showToast('تم تحديث حالة خادم MCP', 'success');
      await loadMcpServers();
    } else {
      showToast('فشل تغيير الحالة: ' + (data.message || ''), 'error');
    }
  } catch (err) {
    showToast('حدث خطأ أثناء تغيير حالة خادم MCP.', 'error');
  }
}

async function deleteMcpServer(serverId) {
  if (!confirm('هل أنت متأكد من رغبتك في حذف هذا الخادم؟\nسيتم إزالة جميع أدواته ولن يتمكن المساعد الصوتي من استدعائها.')) {
    return;
  }
  try {
    const res = await fetch('/api/agents/mcp/delete/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken')
      },
      body: JSON.stringify({ id: serverId })
    });
    const data = await res.json();
    if (data.status === 'success') {
      showToast(data.message, 'success');
      await loadMcpServers();
    } else {
      showToast('فشل الحذف: ' + (data.message || ''), 'error');
    }
  } catch (err) {
    showToast('حدث خطأ أثناء حذف خادم MCP.', 'error');
  }
}

function deleteMcpFromModal() {
  const idVal = document.getElementById('modal-mcp-id').value;
  if (idVal) {
    closeMcpModal();
    deleteMcpServer(parseInt(idVal));
  }
}

document.addEventListener('DOMContentLoaded', () => {
  mcpSyncAlert = document.getElementById('mcp-sync-alert');
  mcpServersGrid = document.getElementById('mcp-servers-grid');
  mcpToolsContainer = document.getElementById('mcp-tools-container');
  mcpToolsCount = document.getElementById('mcp-tools-count');
  mcpActiveCountBadge = document.getElementById('mcp-active-servers-count');
  mcpTotalCountBadge = document.getElementById('mcp-total-servers-count');
  mcpModal = document.getElementById('mcp-modal');

  loadMcpServers();
});

window.addEventListener('appLanguageChanged', () => {
  renderMcpServersGrid(userMcpServers);
});
