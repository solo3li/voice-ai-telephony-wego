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
      allActiveTools.push({ ...t, server_name: s.name, server_url: s.server_url });
    });
  });
  if (mcpToolsCount) mcpToolsCount.innerText = allActiveTools.length;

  if (servers.length === 0) {
    mcpServersGrid.innerHTML = `
      <div class="col-span-full text-center py-10 px-4 bg-[#FAF7F2] rounded-3xl border-2 border-dashed border-[#DDD5C7] space-y-3">
        <span class="text-3xl block">⚡</span>
        <h4 class="text-sm font-bold text-[#1C1917]">لا توجد خوادم MCP مربوطة حالياً</h4>
        <p class="text-xs text-[#6E645D]">يمكنك ربط خادم أدوات خارجي عبر بروتوكول FastMCP SSE لتمكين المساعد الصوتي من استدعاء دواله أثناء المكالمات.</p>
        <button type="button" onclick="openMcpModal(null)" class="px-5 py-2 rounded-xl bg-[#680E23] hover:bg-[#7E152F] text-white text-xs font-bold transition inline-flex items-center gap-1.5 shadow-md">
          <span>+</span> <span>ربط خادم MCP جديد</span>
        </button>
      </div>
    `;
  } else {
    mcpServersGrid.innerHTML = servers.map(s => {
      const toolsCount = (s.cached_tools || []).length;
      const statusDotClass = s.is_active ? 'bg-emerald-500 animate-pulse' : 'bg-[#C5A880]';
      const badgeClass = s.is_active 
        ? 'bg-[#FAF0F2] border border-[#E8CCD2] text-[#680E23]' 
        : 'bg-[#F5EFE6] border border-[#DDD5C7] text-[#8C827A]';
      const badgeText = s.is_active ? 'مفعل للمكالمات' : 'معطل';
      const toggleBtnText = s.is_active ? 'تعطيل' : 'تفعيل';
      const toggleBtnClass = s.is_active
        ? 'bg-[#F5EFE6] hover:bg-[#EAE3D9] text-[#443D39] border border-[#DDD5C7]'
        : 'bg-emerald-50 hover:bg-emerald-100 text-emerald-800 border border-emerald-300 font-bold';

      return `
        <div class="p-5 rounded-3xl bg-white border ${s.is_active ? 'border-[#D4AF37]/50 shadow-md' : 'border-[#EAE3D9] opacity-85'} hover:border-[#680E23]/40 transition-all duration-300 flex flex-col justify-between space-y-4">
          <div class="space-y-3">
            <div class="flex items-start justify-between gap-2">
              <div class="flex items-center gap-2.5 min-w-0">
                <span class="w-2.5 h-2.5 rounded-full ${statusDotClass} shrink-0"></span>
                <h4 class="font-bold text-xs text-[#1C1917] truncate" title="${s.name}">${s.name}</h4>
              </div>
              <span class="px-2 py-0.5 rounded-full text-[10px] font-semibold shrink-0 ${badgeClass}">${badgeText}</span>
            </div>

            <div class="p-2.5 rounded-xl bg-[#FAF7F2] border border-[#EAE3D9] font-mono text-[11px] text-[#680E23] truncate" title="${s.server_url}">
              <span class="text-[#8C827A] select-none text-[10px]">SSE: </span>${s.server_url}
            </div>

            <div class="flex items-center justify-between text-[11px] text-[#8C827A] pt-1">
              <span>الدوال المكتشفة: <strong class="text-[#1C1917] font-mono">${toolsCount}</strong></span>
              <span>${s.last_synced_at ? `مزامنة: ${s.last_synced_at}` : 'لم تتم المزامنة'}</span>
            </div>
          </div>

          <div class="pt-3 border-t border-[#EAE3D9] flex items-center justify-between gap-1.5 text-xs">
            <button type="button" onclick="toggleMcpActive(${s.id})" class="px-3 py-1.5 rounded-xl text-xs font-semibold transition ${toggleBtnClass}">
              ${toggleBtnText}
            </button>
            <div class="flex items-center gap-1">
              <button type="button" onclick="syncMcpServer(${s.id})" class="p-1.5 rounded-xl bg-[#FAF7F2] hover:bg-[#F5EFE6] text-[#680E23] border border-[#DDD5C7] transition" title="فحص وتحديث الأدوات">
                🔄
              </button>
              <button type="button" onclick="openMcpModal(${s.id})" class="p-1.5 rounded-xl bg-[#FAF7F2] hover:bg-[#F5EFE6] text-[#443D39] border border-[#DDD5C7] transition" title="تعديل الإعدادات">
                ✏️
              </button>
              <button type="button" onclick="deleteMcpServer(${s.id})" class="p-1.5 rounded-xl bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 transition" title="حذف الخادم">
                🗑️
              </button>
            </div>
          </div>
        </div>
      `;
    }).join('');
  }

  if (!mcpToolsContainer) return;
  if (allActiveTools.length === 0) {
    mcpToolsContainer.innerHTML = `
      <div class="col-span-full text-center py-6 text-[#8C827A] text-xs bg-[#FAF7F2]/50 rounded-2xl border border-dashed border-[#DDD5C7]">
        لا توجد أدوات مكتشفة من الخوادم المفعلة حالياً. اضغط على زر التحديث 🔄 لأي خادم لقراءة دواله.
      </div>
    `;
  } else {
    mcpToolsContainer.innerHTML = allActiveTools.map(t => {
      const paramsList = t.parameters && t.parameters.properties ? Object.keys(t.parameters.properties) : [];
      const badges = paramsList.map(p => `<span class="px-2 py-0.5 rounded-md bg-[#FAF0F2] border border-[#E8CCD2] text-[#680E23] font-mono text-[10px] font-semibold">${p}</span>`).join(' ');
      return `
        <div class="p-4 rounded-2xl bg-white border border-[#EAE3D9] hover:border-[#D4AF37] transition shadow-sm space-y-2">
          <div class="flex items-center justify-between gap-2">
            <span class="font-mono font-bold text-[#680E23] text-xs flex items-center gap-1.5 truncate">
              <span class="text-[10px]">⚡</span>
              ${escapeHtml(t.name)}
            </span>
            <span class="text-[10px] px-2 py-0.5 rounded-full bg-[#FAF0F2] border border-[#EAE3D9] text-[#680E23] font-semibold shrink-0" title="${escapeHtml(t.server_url)}">
              ${escapeHtml(t.server_name)}
            </span>
          </div>
          <p class="text-[#443D39] text-[11px] leading-relaxed line-clamp-2" title="${escapeHtml(t.description)}">${escapeHtml(t.description || 'بدون وصف')}</p>
          ${badges ? `<div class="pt-1 flex flex-wrap gap-1 items-center"><span class="text-[10px] text-[#8C827A]">المعاملات:</span> ${badges}</div>` : ''}
        </div>
      `;
    }).join('');
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
      connAlert.innerHTML = '<span>❌ يرجى إدخال رابط الخادم (Server URL) أولاً.</span>';
      connAlert.classList.remove('hidden');
    }
    return;
  }

  if (btn) btn.disabled = true;
  if (btnText) btnText.innerText = 'جاري الفحص واكتشاف الأدوات...';
  if (connAlert) {
    connAlert.className = 'mt-2.5 p-3 rounded-2xl text-xs bg-[#FAF7F2] border border-[#DDD5C7] text-[#443D39] flex items-center gap-2';
    connAlert.innerHTML = '<span>🔄 جاري محاولة الاتصال بنقطة نهاية SSE ومصافحة بروتوكول MCP...</span>';
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
        connAlert.className = 'mt-2.5 p-3 rounded-2xl text-xs bg-emerald-50 border border-emerald-300 text-emerald-800 space-y-1';
        connAlert.innerHTML = `
          <div class="font-bold flex items-center gap-1.5">
            <span>✅</span> <span>تم الاتصال بالخادم بنجاح!</span>
          </div>
          <div class="text-[11px] text-emerald-700">
            تم فحص البروتوكول واكتشاف <strong>${data.tools_count}</strong> أداة جاهزة للاستخدام الصوتي.
          </div>
        `;
      }
      if (latencyBadge) {
        latencyBadge.innerText = `${data.latency_ms} ms`;
        latencyBadge.className = 'px-2.5 py-1 rounded-full text-[11px] font-mono font-bold bg-emerald-50 text-emerald-800 border border-emerald-300';
        latencyBadge.classList.remove('hidden');
      }

      currentModalDiscoveredTools = data.tools || [];
      populatePlaygroundTools(currentModalDiscoveredTools);
    } else {
      if (connAlert) {
        connAlert.className = 'mt-2.5 p-3 rounded-2xl text-xs bg-rose-50 border border-rose-200 text-rose-800 space-y-1';
        connAlert.innerHTML = `
          <div class="font-bold flex items-center gap-1.5">
            <span>❌</span> <span>تعذر الاتصال بخادم MCP:</span>
          </div>
          <div class="text-[11px] text-rose-700">
            ${escapeHtml(data.error_message || 'فشل الاتصال بالخادم.')}
          </div>
          <div class="text-[10px] text-[#6E645D] pt-0.5">
            ملاحظة: يمكنك حفظ الخادم رغم ذلك كـ (معطل) إذا كان قيد الإعداد.
          </div>
        `;
      }
      if (latencyBadge && data.latency_ms) {
        latencyBadge.innerText = `${data.latency_ms} ms`;
        latencyBadge.className = 'px-2.5 py-1 rounded-full text-[11px] font-mono font-semibold bg-rose-50 text-rose-800 border border-rose-200';
        latencyBadge.classList.remove('hidden');
      }
    }
  } catch (err) {
    if (connAlert) {
      connAlert.className = 'mt-2.5 p-3 rounded-2xl text-xs bg-rose-50 border border-rose-200 text-rose-800 flex items-center gap-2';
      connAlert.innerHTML = `<span>❌ حدث خطأ في الشبكة أثناء طلب الفحص: ${escapeHtml(err.message || '')}</span>`;
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
    execBadge.innerText = '⏳ جاري الاستدعاء...';
    execBadge.className = 'font-mono text-[10px] px-2.5 py-0.5 rounded-full font-bold bg-[#FAF7F2] text-[#443D39] border border-[#DDD5C7]';
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
        execBadge.innerText = `✅ ناجح (${data.execution_time_ms} ms)`;
        execBadge.className = 'font-mono text-[10px] px-2.5 py-0.5 rounded-full font-bold bg-emerald-50 text-emerald-800 border border-emerald-300';
      }
      if (resultOutput) {
        resultOutput.innerText = data.result || 'تم التنفيذ بنجاح بدون نص مخرجات.';
      }
    } else {
      if (execBadge) {
        execBadge.innerText = `❌ فشل (${data.error_type || 'error'}) - ${data.execution_time_ms || 0} ms`;
        execBadge.className = 'font-mono text-[10px] px-2.5 py-0.5 rounded-full font-bold bg-rose-50 text-rose-800 border border-rose-200';
      }
      if (resultOutput) {
        resultOutput.innerText = data.error_message || data.result || 'فشل تنفيذ الأداة.';
      }
    }
  } catch (err) {
    if (execBadge) {
      execBadge.innerText = '❌ خطأ شبكة';
      execBadge.className = 'font-mono text-[10px] px-2.5 py-0.5 rounded-full font-bold bg-rose-50 text-rose-800 border border-rose-200';
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
      if (modalTitle) modalTitle.innerHTML = '<span>⚙️</span> إعدادات خادم FastMCP';
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
    if (modalTitle) modalTitle.innerHTML = '<span>⚡</span> ربط خادم FastMCP خارجي جديد';
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
    mcpSyncAlert.className = 'mt-3 p-3.5 rounded-2xl text-xs bg-[#F5EFE6] border border-[#DDD5C7] text-[#443D39] flex items-center gap-2';
    mcpSyncAlert.innerHTML = `<span>🔄 جاري فحص الاتصال وتحديث دوال الخادم...</span>`;
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
        mcpSyncAlert.innerHTML = `<span>✅ ${data.message}</span>`;
      }
      showToast(data.message, 'success');
    } else {
      if (mcpSyncAlert) {
        mcpSyncAlert.className = 'mt-3 p-3.5 rounded-2xl text-xs bg-rose-50 border border-rose-200 text-rose-800 flex items-center gap-2';
        mcpSyncAlert.innerHTML = `<span>❌ ${data.message}</span>`;
      }
      showToast(data.message, 'error');
    }
  } catch (err) {
    if (mcpSyncAlert) {
      mcpSyncAlert.className = 'mt-3 p-3.5 rounded-2xl text-xs bg-rose-50 border border-rose-200 text-rose-800 flex items-center gap-2';
      mcpSyncAlert.innerHTML = `<span>❌ تعذر الاتصال بالخادم.</span>`;
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
