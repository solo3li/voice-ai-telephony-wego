/**
 * Telephony & PBX Management JavaScript
 * Handles Generic Outbound SIP Trunks, AI Calling Trigger, and Inbound PBX Trunks (Issabel / Asterisk)
 */

let currentOutboundTrunk = null;
let currentPbxTrunks = [];

function switchTelephonySubtab(sub) {
  document.querySelectorAll('.telephony-subtab-panel').forEach(el => el.classList.add('hidden'));
  document.querySelectorAll('.subtab-btn').forEach(btn => {
    btn.classList.remove('bg-[#680E23]', 'text-white', 'shadow-sm');
    btn.classList.add('text-[#6E645D]');
  });
  const target = document.getElementById('subtab-content-' + sub);
  if (target) target.classList.remove('hidden');
  const activeBtn = document.getElementById('subtab-btn-' + sub);
  if (activeBtn) {
    activeBtn.classList.add('bg-[#680E23]', 'text-white', 'shadow-sm');
    activeBtn.classList.remove('text-[#6E645D]');
  }
}

// ==================== Generic Outbound SIP Trunk ====================

async function loadOutboundTrunk() {
  try {
    const res = await fetch('/api/telephony/trunk/');
    const data = await res.json();
    if (data.status !== 'success') return;

    const badge = document.getElementById('outbound-trunk-badge');
    const details = document.getElementById('outbound-trunk-details');

    if (data.has_trunk && data.trunk) {
      currentOutboundTrunk = data.trunk;
      if (badge) {
        badge.className = "px-2.5 py-0.5 rounded-full text-[10px] font-semibold bg-[#FAF0F2] text-[#680E23] border border-[#EAE3D9]";
        badge.innerHTML = "متصل وجاهز للاتصال";
      }

      if (details) {
        details.innerHTML = `
          <div class="space-y-1.5 pt-1">
            <div class="flex justify-between items-center"><span class="text-[#6E645D]">الاسم:</span> <span class="font-bold text-[#1C1917]">${escapeHtml(data.trunk.name)}</span></div>
            <div class="flex justify-between items-center"><span class="text-[#6E645D]">الخادم:</span> <span class="font-mono text-[#680E23] text-[11px]">${escapeHtml(data.trunk.sip_host)}:${data.trunk.sip_port}</span></div>
            <div class="flex justify-between items-center"><span class="text-[#6E645D]">البروتوكول:</span> <span class="text-[#680E23] font-semibold">${data.trunk.transport}</span></div>
            <div class="flex justify-between items-center"><span class="text-[#6E645D]">Caller ID:</span> <span class="font-mono text-[#680E23] font-semibold">${escapeHtml(data.trunk.caller_id || 'افتراضي')}</span></div>
            <div class="flex justify-between items-center"><span class="text-[#6E645D]">معرف LiveKit:</span> <span class="font-mono text-[10px] text-[#680E23]">${data.trunk.livekit_outbound_trunk_id}</span></div>
          </div>
          <div class="pt-2 border-t border-[#EAE3D9] flex justify-end">
            <button type="button" onclick="handleDeleteOutboundTrunk(${data.trunk.id})" class="text-[11px] text-rose-500 hover:text-rose-700 font-semibold flex items-center gap-1 transition">
              <span>حذف الجذع</span>
            </button>
          </div>
        `;
      }

      // Populate form fields
      const nInp = document.getElementById('outbound-name');
      const hInp = document.getElementById('outbound-host');
      const pInp = document.getElementById('outbound-port');
      const tInp = document.getElementById('outbound-transport');
      const uInp = document.getElementById('outbound-username');
      const cInp = document.getElementById('outbound-caller-id');
      if (nInp) nInp.value = data.trunk.name || '';
      if (hInp) hInp.value = data.trunk.sip_host || '';
      if (pInp) pInp.value = data.trunk.sip_port || 5060;
      if (tInp) tInp.value = data.trunk.transport || 'UDP';
      if (uInp) uInp.value = data.trunk.auth_username || '';
      if (cInp) cInp.value = data.trunk.caller_id || '';
    } else {
      currentOutboundTrunk = null;
      if (badge) {
        badge.className = "px-2 py-0.5 rounded-full text-[10px] font-semibold bg-gray-100 text-gray-500 border border-gray-200";
        badge.innerText = "غير مهيأ";
      }
      if (details) {
        details.innerHTML = `
          <div class="text-[#8C827A] text-center py-4">
            لم يتم حفظ أي جذع SIP خارجي بعد. أدخل بيانات حساب Telnyx أو Twilio أو المزود الخاص بك لحفظه.
          </div>
        `;
      }
    }
  } catch (err) {
    console.error('Error loading outbound trunk:', err);
  }
}

async function handleSaveOutboundTrunk(e) {
  e.preventDefault();
  const btn = document.getElementById('btn-save-outbound');
  const msg = document.getElementById('outbound-trunk-msg');
  if (msg) msg.className = "hidden p-2.5 rounded-xl text-xs font-semibold";

  const payload = {
    name: document.getElementById('outbound-name').value.trim() || 'حساب المزود الخارجي (Generic SIP Trunk)',
    sip_host: document.getElementById('outbound-host').value.trim(),
    sip_port: parseInt(document.getElementById('outbound-port').value || 5060),
    transport: document.getElementById('outbound-transport').value,
    auth_username: document.getElementById('outbound-username').value.trim(),
    auth_password: document.getElementById('outbound-password').value.trim(),
    caller_id: document.getElementById('outbound-caller-id').value.trim(),
  };

  if (!payload.sip_host) {
    if (msg) {
      msg.className = "p-2.5 rounded-xl text-xs font-semibold bg-rose-50 border border-rose-200 text-rose-700";
      msg.innerText = "يرجى كتابة عنوان الخادم (SIP Host).";
    }
    return;
  }

  btn.disabled = true;
  btn.innerHTML = '<span>جاري الربط مع LiveKit...</span>';

  try {
    const res = await fetch('/api/telephony/trunk/save/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken')
      },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (data.status === 'success') {
      if (msg) {
        msg.className = "p-2.5 rounded-xl text-xs font-semibold bg-[#FAF0F2] border border-[#EAE3D9] text-[#680E23]";
        msg.innerText = data.message;
      }
      showToast('تم حفظ وتفعيل الجذع الخارجي بنجاح!', 'success');
      await loadOutboundTrunk();
    } else {
      if (msg) {
        msg.className = "p-2.5 rounded-xl text-xs font-semibold bg-rose-50 border border-rose-200 text-rose-700";
        msg.innerText = data.message || "حدث خطأ أثناء حفظ الجذع.";
      }
    }
  } catch (err) {
    if (msg) {
      msg.className = "p-2.5 rounded-xl text-xs font-semibold bg-rose-50 border border-rose-200 text-rose-700";
      msg.innerText = "فشل الاتصال بالخادم.";
    }
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<span>حفظ وتفعيل الجذع الخارجي</span>';
  }
}

async function handleDeleteOutboundTrunk(id) {
  if (!confirm('هل أنت متأكد من حذف الجذع الخارجي؟ لن تتمكن من إجراء اتصالات صادرة حتى إعادة إعداده.')) return;
  try {
    const res = await fetch(`/api/telephony/trunk/${id}/delete/`, {
      method: 'POST',
      headers: { 'X-CSRFToken': getCookie('csrftoken') }
    });
    const data = await res.json();
    if (data.status === 'success') {
      showToast('تم حذف الجذع الخارجي', 'success');
      await loadOutboundTrunk();
    } else {
      showToast('فشل الحذف: ' + (data.message || ''), 'error');
    }
  } catch (err) {
    showToast('حدث خطأ أثناء حذف الجذع الخارجي.', 'error');
  }
}

// ==================== Outbound AI Call Trigger ====================

async function loadOutboundGateways() {
  const select = document.getElementById('ai-call-gateway');
  if (!select) return;
  select.innerHTML = '<option value="auto:">المسار الافتراضي للنظام (تلقائي)</option>';
  try {
    const res = await fetch('/api/telephony/outbound-gateways/');
    const data = await res.json();
    if (data.status === 'success' && data.gateways) {
      data.gateways.forEach(g => {
        const val = `${g.type}:${g.id || ''}`;
        const isDef = g.is_default ? ' ⭐ (الافتراضي)' : '';
        const icon = g.type === 'pbx' ? '🏢' : '🌐';
        select.innerHTML += `<option value="${val}">${icon} ${escapeHtml(g.name)}${isDef}</option>`;
      });
      if (data.default_gateway) {
        select.value = `${data.default_gateway.type}:${data.default_gateway.id || ''}`;
      }
    }
  } catch (e) {
    console.error('Failed to load outbound gateways:', e);
  }
}

async function openNewAICallModal() {
  await loadOutboundGateways();

  const select = document.getElementById('ai-call-profile');
  if (select) {
    select.innerHTML = '<option value="">البروفايل النشط حالياً في النظام</option>';
    try {
      const res = await fetch('/api/agents/profiles/');
      const data = await res.json();
      if (data.status === 'success' && data.profiles) {
        data.profiles.forEach(p => {
          select.innerHTML += `<option value="${p.id}">${escapeHtml(p.name)} (${p.dialect_display || ''})</option>`;
        });
      }
    } catch (e) {}
  }

  const errEl = document.getElementById('ai-call-error');
  const succEl = document.getElementById('ai-call-success');
  if (errEl) errEl.classList.add('hidden');
  if (succEl) succEl.classList.add('hidden');

  const modal = document.getElementById('ai-call-modal');
  if (modal) modal.classList.remove('hidden');

  const phoneInp = document.getElementById('ai-call-phone');
  if (phoneInp) phoneInp.focus();
}

function closeAICallModal() {
  const modal = document.getElementById('ai-call-modal');
  if (modal) modal.classList.add('hidden');
}

function applyGoalTemplate(type) {
  const area = document.getElementById('ai-call-goal');
  if (!area) return;
  if (type === 'confirm_order') {
    area.value = "الاتصال بالعميل بلباقة لتأكيد تفاصيل الطلب رقم 1005 (قميص كاجوال وبنطلون جينز)، وسؤاله عن عنوان الشحن المناسب لتأكيد إرسال الشحنة اليوم.";
  } else if (type === 'survey') {
    area.value = "الاتصال بالعميل وسؤاله عن رأيه في تجربته الشرائية الأخيرة والمنتجات التي استلمها، وتسجيل أي ملاحظات أو شكاوى يذكرها.";
  } else if (type === 'reminder') {
    area.value = "تذكير العميل بموعد التسليم المحدد غداً بين الساعة 2 ظهراً و 5 مساءً، والتأكد من تواجده للاستلام.";
  }
}

async function handleTriggerAICall(e) {
  e.preventDefault();
  const phone = document.getElementById('ai-call-phone').value.trim();
  const profileId = document.getElementById('ai-call-profile').value;
  const callGoal = document.getElementById('ai-call-goal').value.trim();
  const gatewayVal = (document.getElementById('ai-call-gateway') && document.getElementById('ai-call-gateway').value) || 'auto:';
  const [gwType, gwId] = gatewayVal.split(':');
  const btn = document.getElementById('btn-submit-ai-call');
  const errEl = document.getElementById('ai-call-error');
  const succEl = document.getElementById('ai-call-success');

  if (errEl) errEl.classList.add('hidden');
  if (succEl) succEl.classList.add('hidden');

  if (!phone) {
    if (errEl) {
      errEl.innerText = "يرجى إدخال رقم الهاتف.";
      errEl.classList.remove('hidden');
    }
    return;
  }

  btn.disabled = true;
  btn.innerHTML = '<span>جاري طلب الرقم وتجهيز المساعد...</span>';

  try {
    const payload = {
      phone_number: phone,
      profile_id: profileId || null,
      call_goal: callGoal,
      gateway_type: gwType || 'auto',
      gateway_id: gwId ? parseInt(gwId) : null
    };

    const res = await fetch('/api/telephony/ai-call/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken')
      },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (data.status === 'success') {
      if (succEl) {
        succEl.innerHTML = `
          <div><strong>✅ ${escapeHtml(data.message)}</strong></div>
          <div class="mt-1 text-[11px] text-[#680E23] font-bold">الرقم: <span class="font-mono">${escapeHtml(data.destination_phone)}</span> | المسار: <span>${escapeHtml(data.gateway_used || 'الافتراضي')}</span> | الغرفة: <span class="font-mono">${escapeHtml(data.room_name)}</span></div>
        `;
        succEl.classList.remove('hidden');
      }
      showToast('تم بدء مكالمة الـ AI بنجاح!', 'success');
    } else {
      if (errEl) {
        errEl.innerText = data.message || "فشل بدء المكالمة الصادرة.";
        errEl.classList.remove('hidden');
      }
    }
  } catch (err) {
    if (errEl) {
      errEl.innerText = "حدث خطأ في الاتصال بالخادم.";
      errEl.classList.remove('hidden');
    }
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<span>📞 بدء الاتصال الآن</span>';
  }
}

// ==================== Inbound PBX Trunks (Issabel / Asterisk) ====================

async function loadPbxTrunks() {
  const grid = document.getElementById('pbx-trunks-grid');
  const countEl = document.getElementById('pbx-trunks-count');
  if (!grid) return;

  try {
    const res = await fetch('/api/telephony/pbx-trunks/');
    const data = await res.json();
    if (data.status !== 'success') return;

    currentPbxTrunks = data.trunks || [];
    if (countEl) countEl.innerText = currentPbxTrunks.length;

    if (currentPbxTrunks.length === 0) {
      grid.innerHTML = `
        <div class="col-span-full bg-white border-2 border-dashed border-[#EAE3D9] rounded-3xl p-8 text-center space-y-3">
          <div class="text-3xl">🏢</div>
          <div class="text-[#443D39] font-semibold text-sm">لا يوجد سنترال محلي مربوط حالياً</div>
          <p class="text-[#8C827A] text-xs max-w-md mx-auto">
            اضغط على زر "ربط سنترال Issabel / Asterisk جديد" لإنشاء جذع SIP والحصول على كود PEER Details الجاهز للصق في السنترال.
          </p>
          <button type="button" onclick="openNewPbxModal()" class="px-4 py-2 rounded-xl bg-[#680E23] hover:bg-[#7E152F] text-white font-semibold text-xs inline-flex items-center gap-1.5 shadow-md shadow-[#680E23]/20">
            <span>➕ ربط أول سنترال</span>
          </button>
        </div>
      `;
      return;
    }

    grid.innerHTML = currentPbxTrunks.map(t => {
      const isIp = t.auth_mode === 'ip';
      const authBadge = isIp
        ? `<span class="px-2 py-0.5 rounded-md text-[10px] font-mono bg-[#FAF0F2] text-[#680E23] border border-[#EAE3D9]">IP: ${escapeHtml(t.pbx_ip || 'غير محدد')}</span>`
        : `<span class="px-2 py-0.5 rounded-md text-[10px] font-mono bg-[#FAF0F2]/80 text-[#680E23] border border-[#EAE3D9]">User: ${escapeHtml(t.auth_username || 'غير محدد')}</span>`;

      const destBadge = t.destination_type === 'ai'
        ? `<div class="flex items-center gap-1.5 text-xs text-[#680E23] font-semibold"><span>🤖</span> <span>المساعد الذكي (Smart IVR)</span> ${t.target_profile_name ? `<span class="text-[10px] text-[#6E645D] font-normal">(${escapeHtml(t.target_profile_name)})</span>` : ''}</div>`
        : `<div class="flex items-center gap-1.5 text-xs text-[#680E23] font-semibold"><span>👥</span> <span>طابور: ${escapeHtml(t.target_queue_name || 'غير محدد')} [${escapeHtml(t.target_queue_code || '')}]</span></div>`;

      let numDisplay = '';
      if (Array.isArray(t.inbound_numbers)) {
        numDisplay = t.inbound_numbers.join(', ');
      } else if (typeof t.inbound_numbers === 'string') {
        numDisplay = t.inbound_numbers.trim();
      }
      const numbersBadge = numDisplay
        ? `<span class="font-mono text-[#443D39]">${escapeHtml(numDisplay)}</span>`
        : `<span class="text-[#8C827A]">جميع المكالمات الواردة</span>`;

      const bidiBadge = t.enable_outbound
        ? `<span class="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-[#FAF0F2] text-[#680E23] border border-[#EAE3D9]" title="صادر ووارد">🔄 ${t.is_default_outbound ? 'ثنائي (افتراضي)' : 'ثنائي الاتجاه'}</span>`
        : `<span class="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-gray-100 text-gray-600 border border-gray-200">وارد فقط</span>`;

      return `
        <div class="bg-white border border-[#EAE3D9] hover:border-[#680E23]/40 transition rounded-2xl p-4 flex flex-col justify-between space-y-4 shadow-sm hover:shadow-md">
          <div class="space-y-2.5">
            <div class="flex justify-between items-start">
              <div>
                <h3 class="font-bold text-[#1C1917] text-sm flex items-center gap-1.5">
                  <span>🏢</span>
                  <span>${escapeHtml(t.name)}</span>
                </h3>
                <div class="mt-1 flex items-center gap-1.5 flex-wrap">
                  ${authBadge}
                  ${bidiBadge}
                </div>
              </div>
              <span class="px-2 py-0.5 rounded-full text-[10px] font-semibold ${t.is_active ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-gray-100 text-gray-500 border border-gray-200'}">
                ${t.is_active ? '🟢 متصل' : '⚪ معطل'}
              </span>
            </div>

            <div class="pt-2 border-t border-[#EAE3D9] space-y-1.5 text-xs">
              <div class="flex justify-between items-center text-[11px]">
                <span class="text-[#6E645D]">الوجهة:</span>
                ${destBadge}
              </div>
              <div class="flex justify-between items-center text-[11px]">
                <span class="text-[#6E645D]">الأرقام / DIDs:</span>
                ${numbersBadge}
              </div>
              <div class="flex justify-between items-center text-[10px] font-mono text-[#8C827A]">
                <span>LiveKit Trunk:</span>
                <span class="truncate max-w-[120px]" title="${escapeHtml(t.livekit_trunk_id || '')}">${escapeHtml(t.livekit_trunk_id ? t.livekit_trunk_id.substring(0, 15) + '...' : 'غير مزامن')}</span>
              </div>
              ${t.enable_outbound && t.livekit_outbound_trunk_id ? `
              <div class="flex justify-between items-center text-[10px] font-mono text-[#680E23]/80">
                <span>LK Outbound:</span>
                <span class="truncate max-w-[120px]" title="${escapeHtml(t.livekit_outbound_trunk_id)}">${escapeHtml(t.livekit_outbound_trunk_id.substring(0, 15) + '...')}</span>
              </div>
              ` : ''}
            </div>
          </div>

          <div class="pt-2 border-t border-[#EAE3D9] flex items-center justify-between gap-2">
            <button 
              type="button" 
              onclick="showIssabelConfigModal(${t.id})" 
              class="px-3 py-1.5 rounded-xl bg-[#FAF0F2] hover:bg-[#F5E0E4] text-[#680E23] border border-[#EAE3D9] text-[11px] font-bold transition flex items-center gap-1 shadow-sm"
              title="عرض كود الإعداد للسنترال"
            >
              <span>📋 كود Issabel</span>
            </button>
            <button 
              type="button" 
              onclick="handleDeletePbxTrunk(${t.id}, '${escapeHtml(t.name)}')" 
              class="p-1.5 rounded-xl hover:bg-rose-50 text-[#8C827A] hover:text-rose-600 transition"
              title="حذف الربط"
            >
              <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </button>
          </div>
        </div>
      `;
    }).join('');

  } catch (err) {
    console.error('Error loading PBX trunks:', err);
  }
}

async function openNewPbxModal() {
  const form = document.getElementById('new-pbx-form');
  if (form) form.reset();

  const err = document.getElementById('pbx-modal-error');
  const succ = document.getElementById('pbx-modal-success');
  if (err) err.classList.add('hidden');
  if (succ) succ.classList.add('hidden');

  const outbCheck = document.getElementById('pbx-enable-outbound');
  if (outbCheck) outbCheck.checked = true;
  const portInput = document.getElementById('pbx-outbound-port');
  if (portInput) portInput.value = 5060;
  const transInput = document.getElementById('pbx-outbound-transport');
  if (transInput) transInput.value = 'UDP';
  const defCheck = document.getElementById('pbx-is-default-outbound');
  if (defCheck) defCheck.checked = false;
  togglePbxOutboundOptions();

  onPbxAuthModeChange();
  onPbxDestinationChange();

  // Populate Profiles dropdown
  const profSelect = document.getElementById('pbx-target-profile');
  if (profSelect) {
    profSelect.innerHTML = '<option value="">البروفايل النشط حالياً في النظام</option>';
    try {
      const res = await fetch('/api/agents/profiles/');
      const data = await res.json();
      if (data.status === 'success' && data.profiles) {
        data.profiles.forEach(p => {
          profSelect.innerHTML += `<option value="${p.id}">${escapeHtml(p.name)} (${escapeHtml(p.dialect_display || '')})</option>`;
        });
      }
    } catch (e) {}
  }

  // Populate Queues dropdown
  const queueSelect = document.getElementById('pbx-target-queue');
  if (queueSelect) {
    queueSelect.innerHTML = '<option value="">اختر طابور الانتظار...</option>';
    try {
      const res = await fetch('/api/call-center/queues/');
      const data = await res.json();
      if (data.status === 'success' && data.queues) {
        data.queues.forEach(q => {
          queueSelect.innerHTML += `<option value="${q.id}">[${escapeHtml(q.code)}] ${escapeHtml(q.name)}</option>`;
        });
      }
    } catch (e) {}
  }

  const modal = document.getElementById('new-pbx-modal');
  if (modal) modal.classList.remove('hidden');
}

function closeNewPbxModal() {
  const modal = document.getElementById('new-pbx-modal');
  if (modal) modal.classList.add('hidden');
}

function togglePbxOutboundOptions() {
  const check = document.getElementById('pbx-enable-outbound');
  const opts = document.getElementById('pbx-outbound-options');
  if (opts && check) {
    if (check.checked) {
      opts.classList.remove('hidden');
    } else {
      opts.classList.add('hidden');
    }
  }
}

function onPbxAuthModeChange() {
  const mode = document.getElementById('pbx-auth-mode').value;
  const ipGroup = document.getElementById('pbx-ip-group');
  const credsGroup = document.getElementById('pbx-creds-group');
  const ipInput = document.getElementById('pbx-ip');
  const userInput = document.getElementById('pbx-auth-username');
  const passInput = document.getElementById('pbx-auth-password');

  if (mode === 'ip') {
    if (ipGroup) ipGroup.classList.remove('hidden');
    if (credsGroup) credsGroup.classList.add('hidden');
    if (ipInput) ipInput.required = true;
    if (userInput) userInput.required = false;
    if (passInput) passInput.required = false;
  } else {
    if (ipGroup) ipGroup.classList.add('hidden');
    if (credsGroup) credsGroup.classList.remove('hidden');
    if (ipInput) ipInput.required = false;
    if (userInput) userInput.required = true;
    if (passInput) passInput.required = true;
  }
}

function onPbxDestinationChange() {
  const dest = document.getElementById('pbx-destination-type').value;
  const aiGroup = document.getElementById('pbx-ai-group');
  const queueGroup = document.getElementById('pbx-queue-group');
  const queueSelect = document.getElementById('pbx-target-queue');

  if (dest === 'ai') {
    if (aiGroup) aiGroup.classList.remove('hidden');
    if (queueGroup) queueGroup.classList.add('hidden');
    if (queueSelect) queueSelect.required = false;
  } else {
    if (aiGroup) aiGroup.classList.add('hidden');
    if (queueGroup) queueGroup.classList.remove('hidden');
    if (queueSelect) queueSelect.required = true;
  }
}

async function handleSavePbxTrunk(e) {
  e.preventDefault();
  const btn = document.getElementById('btn-submit-pbx');
  const errEl = document.getElementById('pbx-modal-error');
  const succEl = document.getElementById('pbx-modal-success');

  if (errEl) errEl.classList.add('hidden');
  if (succEl) succEl.classList.add('hidden');

  const name = document.getElementById('pbx-name').value.trim();
  const authMode = document.getElementById('pbx-auth-mode').value;
  const pbxIp = document.getElementById('pbx-ip').value.trim();
  const authUsername = document.getElementById('pbx-auth-username').value.trim();
  const authPassword = document.getElementById('pbx-auth-password').value.trim();
  const destinationType = document.getElementById('pbx-destination-type').value;
  const targetProfileId = document.getElementById('pbx-target-profile').value;
  const targetQueueId = document.getElementById('pbx-target-queue').value;
  const inboundNumbers = document.getElementById('pbx-inbound-numbers').value.trim();

  const enableOutbound = document.getElementById('pbx-enable-outbound') ? document.getElementById('pbx-enable-outbound').checked : true;
  const outboundPort = document.getElementById('pbx-outbound-port') ? (parseInt(document.getElementById('pbx-outbound-port').value) || 5060) : 5060;
  const outboundTransport = document.getElementById('pbx-outbound-transport') ? document.getElementById('pbx-outbound-transport').value : 'UDP';
  const isDefaultOutbound = document.getElementById('pbx-is-default-outbound') ? document.getElementById('pbx-is-default-outbound').checked : false;

  btn.disabled = true;
  btn.innerHTML = '<span>جاري إنشاء الجذع والمزامنة مع LiveKit...</span>';

  const payload = {
    name: name,
    auth_mode: authMode,
    pbx_ip: pbxIp,
    auth_username: authUsername,
    auth_password: authPassword,
    destination_type: destinationType,
    target_profile_id: targetProfileId || null,
    target_queue_id: targetQueueId || null,
    inbound_numbers: inboundNumbers,
    enable_outbound: enableOutbound,
    outbound_port: outboundPort,
    outbound_transport: outboundTransport,
    is_default_outbound: isDefaultOutbound
  };

  try {
    const res = await fetch('/api/telephony/pbx-trunks/save/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken')
      },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (data.status === 'success') {
      if (succEl) {
        succEl.innerText = data.message || 'تم إنشاء الجذع وربطه بنجاح!';
        succEl.classList.remove('hidden');
      }
      showToast('تم ربط السنترال بنجاح!', 'success');
      setTimeout(async () => {
        closeNewPbxModal();
        await loadPbxTrunks();
        if (data.trunk && data.trunk.id) {
          showIssabelConfigModal(data.trunk.id);
        }
      }, 800);
    } else {
      if (errEl) {
        errEl.innerText = data.message || 'فشل إنشاء السنترال.';
        errEl.classList.remove('hidden');
      }
    }
  } catch (err) {
    if (errEl) {
      errEl.innerText = 'حدث خطأ أثناء الاتصال بالخادم.';
      errEl.classList.remove('hidden');
    }
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<span>💾 إنشاء وتفعيل في LiveKit</span>';
  }
}

async function handleDeletePbxTrunk(id, name) {
  if (!confirm(`هل أنت متأكد من حذف سنترال "${name}"؟ سيتم إيقاف الـ SIP Trunk وحذف قاعدة التوجيه في LiveKit.`)) return;
  try {
    const res = await fetch(`/api/telephony/pbx-trunks/${id}/delete/`, {
      method: 'POST',
      headers: { 'X-CSRFToken': getCookie('csrftoken') }
    });
    const data = await res.json();
    if (data.status === 'success') {
      showToast('تم حذف السنترال بنجاح', 'success');
      await loadPbxTrunks();
    } else {
      showToast('فشل الحذف: ' + (data.message || ''), 'error');
    }
  } catch (err) {
    showToast('حدث خطأ أثناء حذف السنترال.', 'error');
  }
}

function showIssabelConfigModal(trunkId) {
  const trunk = currentPbxTrunks.find(t => t.id === trunkId);
  if (!trunk) return;

  const titleEl = document.getElementById('issabel-modal-title');
  const peerEl = document.getElementById('issabel-peer-content');
  const userEl = document.getElementById('issabel-user-content');
  const userBox = document.getElementById('issabel-user-box');
  const regBox = document.getElementById('issabel-register-box');
  const regEl = document.getElementById('issabel-register-content');

  if (titleEl) titleEl.innerText = `كود إعداد السنترال: ${trunk.name}`;
  if (peerEl) peerEl.innerText = (trunk.issabel_config && trunk.issabel_config.peer_details) || '';

  if (userEl) {
    const userDetails = (trunk.issabel_config && trunk.issabel_config.user_details) || '';
    userEl.innerText = userDetails;
    if (userBox) {
      if (userDetails.trim()) {
        userBox.classList.remove('hidden');
      } else {
        userBox.classList.add('hidden');
      }
    }
  }

  if (trunk.issabel_config && trunk.issabel_config.register_string && trunk.issabel_config.register_string.trim()) {
    if (regBox) regBox.classList.remove('hidden');
    if (regEl) regEl.innerText = trunk.issabel_config.register_string;
  } else {
    if (regBox) regBox.classList.add('hidden');
  }

  const modal = document.getElementById('issabel-code-modal');
  if (modal) modal.classList.remove('hidden');
}

function closeIssabelModal() {
  const modal = document.getElementById('issabel-code-modal');
  if (modal) modal.classList.add('hidden');
}

function copyIssabelSnippet(elementId, btn) {
  const text = document.getElementById(elementId).innerText;
  navigator.clipboard.writeText(text).then(() => {
    const originalText = btn.innerHTML;
    btn.innerHTML = '<span>✅ تم النسخ!</span>';
    setTimeout(() => {
      btn.innerHTML = originalText;
    }, 2000);
  });
}

document.addEventListener('DOMContentLoaded', () => {
  loadOutboundTrunk();
  loadPbxTrunks();
});
