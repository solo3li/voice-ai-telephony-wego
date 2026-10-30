/**
 * CRM & Customer Memory JavaScript
 * Handles multi-customer switching, permanent profile view, immediate call summaries, and call archives.
 */

let currentSelectedPhone = '+201000000000';
let customerSearchTimer = null;

function debounceCustomerSearch(query) {
  clearTimeout(customerSearchTimer);
  customerSearchTimer = setTimeout(() => {
    loadCustomersList(query);
  }, 300);
}

async function loadCustomersList(query = '') {
  try {
    const url = query ? `/api/crm/customers/?q=${encodeURIComponent(query)}` : '/api/crm/customers/';
    const res = await fetch(url);
    const data = await res.json();
    if (data.status !== 'success') return;

    const selectEl = document.getElementById('crm-customer-select');
    if (!selectEl) return;

    const customers = data.customers || [];
    const defSession = window.t ? window.t('crm_default_browser_session', 'جلسة المتصفح الافتراضية') : 'جلسة المتصفح الافتراضية';
    let html = `<option value="+201000000000">+201000000000 (${defSession})</option>`;

    let hasSelectedInList = (currentSelectedPhone === '+201000000000');

    customers.forEach(c => {
      if (c.phone_number === 'web_dashboard' || c.phone_number === '+201000000000') return;
      const isSel = (c.phone_number === currentSelectedPhone);
      if (isSel) hasSelectedInList = true;
      const displayName = c.customer_name ? `${c.phone_number} (${c.customer_name})` : c.phone_number;
      html += `<option value="${escapeHtml(c.phone_number)}" ${isSel ? 'selected' : ''}>${escapeHtml(displayName)}</option>`;
    });

    if (!hasSelectedInList && currentSelectedPhone && currentSelectedPhone !== '+201000000000' && currentSelectedPhone !== 'web_dashboard') {
      html += `<option value="${escapeHtml(currentSelectedPhone)}" selected>${escapeHtml(currentSelectedPhone)}</option>`;
    }

    selectEl.innerHTML = html;
    selectEl.value = currentSelectedPhone;
  } catch (err) {
    console.error('Error loading customers list:', err);
  }
}

function onCustomerSelectChange(phone) {
  currentSelectedPhone = phone || '+201000000000';
  const badge = document.getElementById('crm-active-customer-badge');
  if (badge) badge.innerText = currentSelectedPhone;
  loadCustomerMemory(currentSelectedPhone);
}

async function loadCustomerMemory(phone) {
  const targetPhone = phone || currentSelectedPhone || 'web_dashboard';
  currentSelectedPhone = targetPhone;

  const badge = document.getElementById('crm-active-customer-badge');
  if (badge) badge.innerText = targetPhone;

  try {
    const res = await fetch(`/api/crm/memory/?phone=${encodeURIComponent(targetPhone)}`);
    const data = await res.json();
    if (data.status !== 'success') return;

    const memory = data.memory || {};
    const prof = memory.permanent_profile || {};
    const calls = data.recent_calls || [];

    // 1. Render Permanent Profile
    const permEl = document.getElementById('memory-permanent-content');
    if (permEl) {
      if (!prof || Object.keys(prof).length === 0) {
        const noDataMsg = window.t ? window.t('crm_no_permanent_data', 'لا توجد بيانات دائمة مسجلة لهذا الرقم بعد. سيتعلم المساعد اسمه وتفضيلاته تلقائياً أثناء المكالمات!') : 'لا توجد بيانات دائمة مسجلة لهذا الرقم بعد. سيتعلم المساعد اسمه وتفضيلاته تلقائياً أثناء المكالمات!';
        permEl.innerHTML = `
          <div class="text-center py-4 text-slate-400">
            ${noDataMsg}
          </div>
        `;
      } else {
        let itemsHtml = '';
        const nameLabel = window.t ? window.t('crm_label_name', 'الاسم:') : 'الاسم:';
        const phoneLabel = window.t ? window.t('crm_label_phone', 'الهاتف:') : 'الهاتف:';
        const addrLabel = window.t ? window.t('crm_label_address', 'العنوان:') : 'العنوان:';
        const prefsLabel = window.t ? window.t('crm_label_prefs', 'التفضيلات:') : 'التفضيلات:';
        const notesLabel = window.t ? window.t('crm_label_notes', 'ملاحظات:') : 'ملاحظات:';
        const noDetailsMsg = window.t ? window.t('crm_no_specific_details', 'لا توجد تفاصيل محددة بعد.') : 'لا توجد تفاصيل محددة بعد.';

        if (prof.customer_name) {
          itemsHtml += `<div class="flex items-center gap-2"><span class="text-slate-500 font-medium">${nameLabel}</span> <span class="text-slate-900 font-semibold">${escapeHtml(prof.customer_name)}</span></div>`;
        }
        if (prof.phone || memory.phone_number) {
          itemsHtml += `<div class="flex items-center gap-2"><span class="text-slate-500 font-medium">${phoneLabel}</span> <span class="text-slate-800 font-mono">${escapeHtml(prof.phone || memory.phone_number)}</span></div>`;
        }
        if (prof.address || prof.city) {
          itemsHtml += `<div class="flex items-center gap-2"><span class="text-slate-500 font-medium">${addrLabel}</span> <span class="text-slate-800">${escapeHtml(prof.address || prof.city)}</span></div>`;
        }
        if (prof.preferences && Array.isArray(prof.preferences) && prof.preferences.length > 0) {
          const tags = prof.preferences.map(p => `<span class="px-2 py-0.5 rounded-md bg-slate-100 border border-slate-200 text-slate-700 text-xs">${escapeHtml(p)}</span>`).join(' ');
          itemsHtml += `<div class="flex items-start gap-2 pt-1"><span class="text-slate-500 font-medium">${prefsLabel}</span> <div class="flex flex-wrap gap-1">${tags}</div></div>`;
        }
        if (prof.notes) {
          itemsHtml += `<div class="flex items-start gap-2 pt-1 text-xs text-slate-500"><span class="text-slate-500 font-medium">${notesLabel}</span> <span class="text-slate-700">${escapeHtml(prof.notes)}</span></div>`;
        }
        permEl.innerHTML = itemsHtml || `<div class="text-slate-400">${noDetailsMsg}</div>`;
      }
    }

    // 2. Render Call Memory
    const callEl = document.getElementById('memory-call-content');
    const badgeEl = document.getElementById('memory-calls-badge');
    if (badgeEl) {
      const callsSuffix = window.t ? window.t('crm_calls_count_suffix', 'مكالمات') : 'مكالمات';
      badgeEl.innerText = `${memory.total_calls_count || 0} ${callsSuffix}`;
    }

    const cm = memory.call_memory || {};
    if (callEl) {
      const callSummary = cm.last_call_summary || memory.last_interaction_summary;
      if (callSummary) {
        const timeStr = cm.last_call_at || memory.last_interaction_at || (window.t ? window.t('crm_prev_call', 'مكالمة سابقة') : 'مكالمة سابقة');
        const lastCallLabel = window.t ? window.t('crm_last_call_label', 'آخر مكالمة:') : 'آخر مكالمة:';
        const intentLabel = window.t ? window.t('crm_intent_label', 'النية:') : 'النية:';
        const sentLabel = window.t ? window.t('crm_sentiment_label', 'الانطباع:') : 'الانطباع:';
        const agreedLabel = window.t ? window.t('crm_agreed_label', 'ما تم الاتفاق عليه:') : 'ما تم الاتفاق عليه:';

        let callHtml = `
          <div class="space-y-2">
            <div class="text-xs text-slate-500">${lastCallLabel} <span class="text-slate-700 font-mono">${escapeHtml(timeStr)}</span></div>
            <p class="text-slate-800 leading-relaxed bg-slate-50/60 p-2.5 rounded-lg border border-slate-200/80 shadow-2xs">
              ${escapeHtml(callSummary)}
            </p>
        `;
        if (cm.intent) {
          callHtml += `<div class="text-xs"><span class="font-medium text-slate-700">${intentLabel}</span> <span class="text-slate-900">${escapeHtml(cm.intent)}</span></div>`;
        }
        if (cm.customer_sentiment) {
          callHtml += `<div class="text-xs"><span class="font-medium text-slate-700">${sentLabel}</span> <span class="text-slate-900">${escapeHtml(cm.customer_sentiment)}</span></div>`;
        }
        if (cm.agreed_next_steps) {
          callHtml += `<div class="text-xs bg-rose-50/80 p-2 rounded-lg border border-rose-100 text-rose-900"><span class="font-semibold">${agreedLabel}</span> ${escapeHtml(cm.agreed_next_steps)}</div>`;
        }
        callHtml += `</div>`;
        callEl.innerHTML = callHtml;
      } else {
        const noCallsMsg = window.t ? window.t('crm_no_calls_recorded', 'لا توجد مكالمات هاتفية مسجلة لهذا الرقم حتى الآن.') : 'لا توجد مكالمات هاتفية مسجلة لهذا الرقم حتى الآن.';
        callEl.innerHTML = `
          <div class="text-center py-4 text-slate-400">
            ${noCallsMsg}
          </div>
        `;
      }
    }

    // 3. Render WhatsApp Memory
    const waEl = document.getElementById('memory-whatsapp-content');
    const wm = memory.whatsapp_memory || {};
    if (waEl) {
      if (wm.conversation_summary || wm.last_received_message || wm.last_sent_message) {
        const timeStr = wm.last_interaction_at || (window.t ? window.t('recent_time', 'مؤخراً') : 'مؤخراً');
        const lastChatLabel = window.t ? window.t('crm_last_chat_label', 'آخر تفاعل شات:') : 'آخر تفاعل شات:';
        const stageLabel = window.t ? window.t('crm_stage_label', 'مرحلة العميل:') : 'مرحلة العميل:';
        const lastInLabel = window.t ? window.t('crm_last_incoming_label', 'آخر رسالة واردة:') : 'آخر رسالة واردة:';
        const lastOutLabel = window.t ? window.t('crm_last_outgoing_label', 'آخر رد مرسل:') : 'آخر رد مرسل:';

        let waHtml = `
          <div class="space-y-2">
            <div class="text-xs text-slate-500">${lastChatLabel} <span class="text-emerald-700 font-mono">${escapeHtml(timeStr)}</span></div>
        `;
        if (wm.customer_stage) {
          waHtml += `<div class="text-xs"><span class="font-medium text-slate-700">${stageLabel}</span> <span class="px-2 py-0.5 rounded-md bg-emerald-50 text-emerald-700 font-medium text-xs border border-emerald-200">${escapeHtml(wm.customer_stage)}</span></div>`;
        }
        if (wm.conversation_summary) {
          waHtml += `<p class="text-slate-800 leading-relaxed bg-slate-50/60 p-2.5 rounded-lg border border-slate-200/80 shadow-2xs">${escapeHtml(wm.conversation_summary)}</p>`;
        }
        if (wm.last_received_message) {
          waHtml += `<div class="text-xs bg-sky-50/80 p-2 rounded-lg border border-sky-100 text-sky-900"><span class="font-medium">${lastInLabel}</span> ${escapeHtml(wm.last_received_message)}</div>`;
        }
        if (wm.last_sent_message) {
          waHtml += `<div class="text-xs bg-emerald-50/80 p-2 rounded-lg border border-emerald-100 text-emerald-900"><span class="font-medium">${lastOutLabel}</span> ${escapeHtml(wm.last_sent_message)}</div>`;
        }
        waHtml += `</div>`;
        waEl.innerHTML = waHtml;
      } else {
        const noWaMsg = window.t ? window.t('crm_no_wa_recorded', 'لا توجد محادثات واتساب مسجلة بعد لهذا الرقم.') : 'لا توجد محادثات واتساب مسجلة بعد لهذا الرقم.';
        waEl.innerHTML = `
          <div class="text-center py-4 text-slate-400">
            ${noWaMsg}
          </div>
        `;
      }
    }

    // 4. Render Recent Calls
    const callsEl = document.getElementById('memory-recent-calls');
    if (callsEl) {
      if (!calls || calls.length === 0) {
        const noPrevCalls = window.t ? window.t('crm_no_prev_calls', 'لا توجد مكالمات سابقة مسجلة لهذا الرقم.') : 'لا توجد مكالمات سابقة مسجلة لهذا الرقم.';
        callsEl.innerHTML = `<div class="text-slate-400 text-center py-2">${noPrevCalls}</div>`;
      } else {
        callsEl.innerHTML = calls.map(c => {
          const inLabel = window.t ? window.t('call_dir_inbound', 'واردة') : 'واردة';
          const outAiLabel = window.t ? window.t('call_dir_outbound_ai', 'صادرة (AI)') : 'صادرة (AI)';
          const outAgentLabel = window.t ? window.t('call_dir_outbound_agent', 'صادرة (موظف)') : 'صادرة (موظف)';
          let dirBadge = `<span class="text-xs px-2 py-0.5 rounded-md bg-slate-100 border border-slate-200 text-slate-700 font-medium">${inLabel}</span>`;
          if (c.direction === 'outbound_ai') {
            dirBadge = `<span class="text-xs px-2 py-0.5 rounded-md bg-slate-100 border border-slate-200 text-slate-700 font-medium">${outAiLabel}</span>`;
          } else if (c.direction === 'outbound_agent') {
            dirBadge = `<span class="text-xs px-2 py-0.5 rounded-md bg-slate-100 border border-slate-200 text-slate-700 font-medium">${outAgentLabel}</span>`;
          }
          const callerBadge = c.caller_phone ? `<span class="text-xs px-2 py-0.5 rounded-md bg-slate-100 border border-slate-200 font-mono text-slate-700">${escapeHtml(c.caller_phone)}</span>` : '';
          const destHtml = c.destination_phone ? `<span class="text-xs px-2 py-0.5 rounded-md bg-slate-100 border border-slate-200 font-mono text-slate-700">${escapeHtml(c.destination_phone)}</span>` : '';
          const secUnit = window.t ? window.t('second_suffix', 'ثانية') : 'ثانية';
          const goalPrefix = window.t ? window.t('crm_call_goal_prefix', 'الهدف: ') : 'الهدف: ';
          const noSummary = window.t ? window.t('crm_completed_no_summary', 'مكالمة مكتملة بدون ملخص') : 'مكالمة مكتملة بدون ملخص';
          return `
          <div class="p-3 rounded-xl bg-white border border-slate-200/80 shadow-2xs flex flex-col md:flex-row md:items-center justify-between gap-2.5">
            <div class="space-y-1">
              <div class="flex flex-wrap items-center gap-2">
                ${dirBadge}
                ${callerBadge}
                ${destHtml}
                <span class="font-mono text-xs text-slate-700 font-medium">${escapeHtml(c.room_name)}</span>
                <span class="text-xs text-slate-400 font-mono">${escapeHtml(c.started_at)}</span>
                <span class="text-xs px-1.5 py-0.5 rounded-md bg-slate-100 text-slate-700 border border-slate-200 font-mono">${c.duration_seconds} ${secUnit}</span>
              </div>
              <p class="text-xs text-slate-600 mt-1">${escapeHtml(c.summary || (c.call_goal ? goalPrefix + c.call_goal : noSummary))}</p>
            </div>
          </div>
          `;
        }).join('');
      }
    }
  } catch (err) {
    console.error('Error loading customer memory:', err);
  }
}

async function resetCustomerMemory() {
  const targetPhone = currentSelectedPhone || 'web_dashboard';
  if (!confirm(`هل أنت متأكد من تصفير ذاكرة العميل للرقم (${targetPhone})؟ سيتم مسح البيانات الدائمة والملخص الخاص به.`)) return;
  try {
    const res = await fetch('/api/crm/memory/reset/', {
      method: 'POST',
      headers: { 
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken') 
      },
      body: JSON.stringify({ phone: targetPhone })
    });
    const data = await res.json();
    if (data.status === 'success') {
      showToast('تم تصفير ذاكرة العميل بنجاح', 'success');
      await loadCustomerMemory(targetPhone);
      await loadCustomersList();
    } else {
      showToast('فشل تصفير الذاكرة: ' + (data.message || ''), 'error');
    }
  } catch (err) {
    showToast('حدث خطأ أثناء تصفير الذاكرة.', 'error');
  }
}

document.addEventListener('DOMContentLoaded', () => {
  loadCustomersList();
  loadCustomerMemory('web_dashboard');
});

window.addEventListener('appLanguageChanged', () => {
  loadCustomersList();
  loadCustomerMemory(currentSelectedPhone);
});
