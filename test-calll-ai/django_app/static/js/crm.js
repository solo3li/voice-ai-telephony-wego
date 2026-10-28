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
    let html = '<option value="+201000000000">💻 +201000000000 (جلسة المتصفح الافتراضية)</option>';

    let hasSelectedInList = (currentSelectedPhone === '+201000000000');

    customers.forEach(c => {
      if (c.phone_number === 'web_dashboard' || c.phone_number === '+201000000000') return;
      const isSel = (c.phone_number === currentSelectedPhone);
      if (isSel) hasSelectedInList = true;
      const displayName = c.customer_name ? `${c.phone_number} (${c.customer_name})` : c.phone_number;
      html += `<option value="${escapeHtml(c.phone_number)}" ${isSel ? 'selected' : ''}>📞 ${escapeHtml(displayName)}</option>`;
    });

    if (!hasSelectedInList && currentSelectedPhone && currentSelectedPhone !== '+201000000000' && currentSelectedPhone !== 'web_dashboard') {
      html += `<option value="${escapeHtml(currentSelectedPhone)}" selected>📞 ${escapeHtml(currentSelectedPhone)}</option>`;
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
        permEl.innerHTML = `
          <div class="text-center py-4 text-slate-400">
            لا توجد بيانات دائمة مسجلة لهذا الرقم بعد. سيتعلم المساعد اسمه وتفضيلاته تلقائياً أثناء المكالمات!
          </div>
        `;
      } else {
        let itemsHtml = '';
        if (prof.customer_name) {
          itemsHtml += `<div class="flex items-center gap-2"><span class="text-slate-500 font-medium">الاسم:</span> <span class="text-slate-900 font-semibold">${escapeHtml(prof.customer_name)}</span></div>`;
        }
        if (prof.phone || memory.phone_number) {
          itemsHtml += `<div class="flex items-center gap-2"><span class="text-slate-500 font-medium">الهاتف:</span> <span class="text-slate-800 font-mono">${escapeHtml(prof.phone || memory.phone_number)}</span></div>`;
        }
        if (prof.address || prof.city) {
          itemsHtml += `<div class="flex items-center gap-2"><span class="text-slate-500 font-medium">العنوان:</span> <span class="text-slate-800">${escapeHtml(prof.address || prof.city)}</span></div>`;
        }
        if (prof.preferences && Array.isArray(prof.preferences) && prof.preferences.length > 0) {
          const tags = prof.preferences.map(p => `<span class="px-2 py-0.5 rounded-md bg-slate-100 border border-slate-200 text-slate-700 text-[10px]">${escapeHtml(p)}</span>`).join(' ');
          itemsHtml += `<div class="flex items-start gap-2 pt-1"><span class="text-slate-500 font-medium">التفضيلات:</span> <div class="flex flex-wrap gap-1">${tags}</div></div>`;
        }
        if (prof.notes) {
          itemsHtml += `<div class="flex items-start gap-2 pt-1 text-[11px] text-slate-500"><span class="text-slate-500 font-medium">ملاحظات:</span> <span class="text-slate-700">${escapeHtml(prof.notes)}</span></div>`;
        }
        permEl.innerHTML = itemsHtml || '<div class="text-slate-400">لا توجد تفاصيل محددة بعد.</div>';
      }
    }

    // 2. Render Call Memory
    const callEl = document.getElementById('memory-call-content');
    const badgeEl = document.getElementById('memory-calls-badge');
    if (badgeEl) {
      badgeEl.innerText = `${memory.total_calls_count || 0} مكالمات`;
    }

    const cm = memory.call_memory || {};
    if (callEl) {
      const callSummary = cm.last_call_summary || memory.last_interaction_summary;
      if (callSummary) {
        const timeStr = cm.last_call_at || memory.last_interaction_at || 'مكالمة سابقة';
        let callHtml = `
          <div class="space-y-2">
            <div class="text-[10px] text-slate-500">آخر مكالمة: <span class="text-slate-700 font-mono">${escapeHtml(timeStr)}</span></div>
            <p class="text-slate-800 leading-relaxed bg-slate-50/60 p-2.5 rounded-lg border border-slate-200 shadow-2xs">
              ${escapeHtml(callSummary)}
            </p>
        `;
        if (cm.intent) {
          callHtml += `<div class="text-[11px]"><span class="font-medium text-slate-700">النية:</span> <span class="text-slate-900">${escapeHtml(cm.intent)}</span></div>`;
        }
        if (cm.customer_sentiment) {
          callHtml += `<div class="text-[11px]"><span class="font-medium text-slate-700">الانطباع:</span> <span class="text-slate-900">${escapeHtml(cm.customer_sentiment)}</span></div>`;
        }
        if (cm.agreed_next_steps) {
          callHtml += `<div class="text-[11px] bg-rose-50/80 p-2 rounded-lg border border-rose-100 text-rose-900"><span class="font-semibold">ما تم الاتفاق عليه:</span> ${escapeHtml(cm.agreed_next_steps)}</div>`;
        }
        callHtml += `</div>`;
        callEl.innerHTML = callHtml;
      } else {
        callEl.innerHTML = `
          <div class="text-center py-4 text-slate-400">
            لا توجد مكالمات هاتفية مسجلة لهذا الرقم حتى الآن.
          </div>
        `;
      }
    }

    // 3. Render WhatsApp Memory
    const waEl = document.getElementById('memory-whatsapp-content');
    const wm = memory.whatsapp_memory || {};
    if (waEl) {
      if (wm.conversation_summary || wm.last_received_message || wm.last_sent_message) {
        const timeStr = wm.last_interaction_at || 'مؤخراً';
        let waHtml = `
          <div class="space-y-2">
            <div class="text-[10px] text-slate-500">آخر تفاعل شات: <span class="text-emerald-700 font-mono">${escapeHtml(timeStr)}</span></div>
        `;
        if (wm.customer_stage) {
          waHtml += `<div class="text-[11px]"><span class="font-medium text-slate-700">مرحلة العميل:</span> <span class="px-2 py-0.5 rounded-md bg-emerald-50 text-emerald-700 font-medium text-[10px] border border-emerald-200">${escapeHtml(wm.customer_stage)}</span></div>`;
        }
        if (wm.conversation_summary) {
          waHtml += `<p class="text-slate-800 leading-relaxed bg-slate-50/60 p-2.5 rounded-lg border border-slate-200 shadow-2xs">${escapeHtml(wm.conversation_summary)}</p>`;
        }
        if (wm.last_received_message) {
          waHtml += `<div class="text-[11px] bg-sky-50/80 p-2 rounded-lg border border-sky-100 text-sky-900"><span class="font-medium">آخر رسالة واردة:</span> ${escapeHtml(wm.last_received_message)}</div>`;
        }
        if (wm.last_sent_message) {
          waHtml += `<div class="text-[11px] bg-emerald-50/80 p-2 rounded-lg border border-emerald-100 text-emerald-900"><span class="font-medium">آخر رد مرسل:</span> ${escapeHtml(wm.last_sent_message)}</div>`;
        }
        waHtml += `</div>`;
        waEl.innerHTML = waHtml;
      } else {
        waEl.innerHTML = `
          <div class="text-center py-4 text-slate-400">
            لا توجد محادثات واتساب مسجلة بعد لهذا الرقم.
          </div>
        `;
      }
    }

    // 3. Render Recent Calls
    const callsEl = document.getElementById('memory-recent-calls');
    if (callsEl) {
      if (!calls || calls.length === 0) {
        callsEl.innerHTML = '<div class="text-slate-400 text-center py-2">لا توجد مكالمات سابقة مسجلة لهذا الرقم.</div>';
      } else {
        callsEl.innerHTML = calls.map(c => {
          let dirBadge = '<span class="text-[10px] px-2 py-0.5 rounded-md bg-slate-100 border border-slate-200 text-slate-700 font-medium">واردة</span>';
          if (c.direction === 'outbound_ai') {
            dirBadge = '<span class="text-[10px] px-2 py-0.5 rounded-md bg-slate-100 border border-slate-200 text-slate-700 font-medium">صادرة (AI)</span>';
          } else if (c.direction === 'outbound_agent') {
            dirBadge = '<span class="text-[10px] px-2 py-0.5 rounded-md bg-slate-100 border border-slate-200 text-slate-700 font-medium">صادرة (موظف)</span>';
          }
          const callerBadge = c.caller_phone ? `<span class="text-[10px] px-2 py-0.5 rounded-md bg-slate-100 border border-slate-200 font-mono text-slate-700">${escapeHtml(c.caller_phone)}</span>` : '';
          const destHtml = c.destination_phone ? `<span class="text-[10px] px-2 py-0.5 rounded-md bg-slate-100 border border-slate-200 font-mono text-slate-700">${escapeHtml(c.destination_phone)}</span>` : '';
          return `
          <div class="p-3 rounded-xl bg-white border border-[#eaedf0] shadow-2xs flex flex-col md:flex-row md:items-center justify-between gap-2.5">
            <div class="space-y-1">
              <div class="flex flex-wrap items-center gap-2">
                ${dirBadge}
                ${callerBadge}
                ${destHtml}
                <span class="font-mono text-xs text-slate-700 font-medium">${escapeHtml(c.room_name)}</span>
                <span class="text-[10px] text-slate-400 font-mono">${escapeHtml(c.started_at)}</span>
                <span class="text-[10px] px-1.5 py-0.5 rounded-md bg-slate-100 text-slate-700 border border-slate-200 font-mono">${c.duration_seconds} ثانية</span>
              </div>
              <p class="text-[11px] text-slate-600 mt-1">${escapeHtml(c.summary || (c.call_goal ? 'الهدف: ' + c.call_goal : 'مكالمة مكتملة بدون ملخص'))}</p>
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
