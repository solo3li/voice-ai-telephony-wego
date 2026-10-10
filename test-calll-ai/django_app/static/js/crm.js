/**
 * CRM & Customer Memory JavaScript
 * Handles multi-customer switching, permanent profile view, immediate call summaries, and call archives.
 */

let currentSelectedPhone = 'web_dashboard';
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
    let html = '<option value="web_dashboard">💻 web_dashboard (جلسة المتصفح)</option>';

    let hasSelectedInList = (currentSelectedPhone === 'web_dashboard');

    customers.forEach(c => {
      if (c.phone_number === 'web_dashboard') return;
      const isSel = (c.phone_number === currentSelectedPhone);
      if (isSel) hasSelectedInList = true;
      const displayName = c.customer_name ? `${c.phone_number} (${c.customer_name})` : c.phone_number;
      html += `<option value="${escapeHtml(c.phone_number)}" ${isSel ? 'selected' : ''}>📞 ${escapeHtml(displayName)}</option>`;
    });

    if (!hasSelectedInList && currentSelectedPhone && currentSelectedPhone !== 'web_dashboard') {
      html += `<option value="${escapeHtml(currentSelectedPhone)}" selected>📞 ${escapeHtml(currentSelectedPhone)}</option>`;
    }

    selectEl.innerHTML = html;
    selectEl.value = currentSelectedPhone;
  } catch (err) {
    console.error('Error loading customers list:', err);
  }
}

function onCustomerSelectChange(phone) {
  currentSelectedPhone = phone || 'web_dashboard';
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
          <div class="text-center py-4 text-[#8C827A]">
            لا توجد بيانات دائمة مسجلة لهذا الرقم بعد. سيتعلم المساعد اسمه وتفضيلاته تلقائياً أثناء المكالمات!
          </div>
        `;
      } else {
        let itemsHtml = '';
        if (prof.customer_name) {
          itemsHtml += `<div class="flex items-center gap-2"><span class="text-[#680E23] font-semibold">👤 الاسم:</span> <span class="text-[#1C1917] font-bold">${escapeHtml(prof.customer_name)}</span></div>`;
        }
        if (prof.phone || memory.phone_number) {
          itemsHtml += `<div class="flex items-center gap-2"><span class="text-[#680E23] font-semibold">📞 الهاتف:</span> <span class="text-[#2D2825] font-mono">${escapeHtml(prof.phone || memory.phone_number)}</span></div>`;
        }
        if (prof.address || prof.city) {
          itemsHtml += `<div class="flex items-center gap-2"><span class="text-[#680E23] font-semibold">📍 العنوان:</span> <span class="text-[#2D2825]">${escapeHtml(prof.address || prof.city)}</span></div>`;
        }
        if (prof.preferences && Array.isArray(prof.preferences) && prof.preferences.length > 0) {
          const tags = prof.preferences.map(p => `<span class="px-2 py-0.5 rounded-md bg-[#FAF0F2]/60 border border-[#EAE3D9] text-[#680E23] text-[10px]">${escapeHtml(p)}</span>`).join(' ');
          itemsHtml += `<div class="flex items-start gap-2 pt-1"><span class="text-[#680E23] font-semibold">🏷️ التفضيلات:</span> <div class="flex flex-wrap gap-1">${tags}</div></div>`;
        }
        if (prof.notes) {
          itemsHtml += `<div class="flex items-start gap-2 pt-1 text-[11px] text-[#6E645D]"><span class="text-[#680E23] font-semibold">📝 ملاحظات:</span> <span>${escapeHtml(prof.notes)}</span></div>`;
        }
        permEl.innerHTML = itemsHtml || '<div class="text-[#8C827A]">لا توجد تفاصيل محددة بعد.</div>';
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
            <div class="text-[10px] text-[#6E645D]">📅 آخر مكالمة: <span class="text-[#680E23] font-mono">${escapeHtml(timeStr)}</span></div>
            <p class="text-[#2D2825] leading-relaxed bg-white p-2.5 rounded-xl border border-[#DDD5C7] shadow-sm">
              ${escapeHtml(callSummary)}
            </p>
        `;
        if (cm.intent) {
          callHtml += `<div class="text-[11px]"><span class="font-bold text-[#680E23]">🎯 النية:</span> <span class="text-[#1C1917]">${escapeHtml(cm.intent)}</span></div>`;
        }
        if (cm.customer_sentiment) {
          callHtml += `<div class="text-[11px]"><span class="font-bold text-[#680E23]">😊 الانطباع:</span> <span class="text-[#1C1917]">${escapeHtml(cm.customer_sentiment)}</span></div>`;
        }
        if (cm.agreed_next_steps) {
          callHtml += `<div class="text-[11px] bg-rose-50/80 p-2 rounded-lg border border-rose-100 text-rose-900"><span class="font-bold">🤝 ما تم الاتفاق عليه:</span> ${escapeHtml(cm.agreed_next_steps)}</div>`;
        }
        callHtml += `</div>`;
        callEl.innerHTML = callHtml;
      } else {
        callEl.innerHTML = `
          <div class="text-center py-4 text-[#8C827A]">
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
            <div class="text-[10px] text-[#6E645D]">📅 آخر تفاعل شات: <span class="text-emerald-700 font-mono">${escapeHtml(timeStr)}</span></div>
        `;
        if (wm.customer_stage) {
          waHtml += `<div class="text-[11px]"><span class="font-bold text-emerald-800">📊 مرحلة العميل:</span> <span class="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 font-bold text-[10px]">${escapeHtml(wm.customer_stage)}</span></div>`;
        }
        if (wm.conversation_summary) {
          waHtml += `<p class="text-[#2D2825] leading-relaxed bg-white p-2.5 rounded-xl border border-[#DDD5C7] shadow-sm">${escapeHtml(wm.conversation_summary)}</p>`;
        }
        if (wm.last_received_message) {
          waHtml += `<div class="text-[11px] bg-blue-50/80 p-2 rounded-lg border border-blue-100 text-blue-900"><span class="font-bold">📥 آخر رسالة واردة:</span> ${escapeHtml(wm.last_received_message)}</div>`;
        }
        if (wm.last_sent_message) {
          waHtml += `<div class="text-[11px] bg-emerald-50/80 p-2 rounded-lg border border-emerald-100 text-emerald-900"><span class="font-bold">🤖 آخر رد مرسل:</span> ${escapeHtml(wm.last_sent_message)}</div>`;
        }
        waHtml += `</div>`;
        waEl.innerHTML = waHtml;
      } else {
        waEl.innerHTML = `
          <div class="text-center py-4 text-[#8C827A]">
            لا توجد محادثات واتساب مسجلة بعد لهذا الرقم.
          </div>
        `;
      }
    }

    // 3. Render Recent Calls
    const callsEl = document.getElementById('memory-recent-calls');
    if (callsEl) {
      if (!calls || calls.length === 0) {
        callsEl.innerHTML = '<div class="text-[#8C827A] text-center py-2">لا توجد مكالمات سابقة مسجلة لهذا الرقم.</div>';
      } else {
        callsEl.innerHTML = calls.map(c => {
          let dirBadge = '<span class="text-[10px] px-2 py-0.5 rounded-full bg-[#FAF0F2] border border-[#EAE3D9] text-[#680E23] font-semibold">📞 واردة</span>';
          if (c.direction === 'outbound_ai') {
            dirBadge = '<span class="text-[10px] px-2 py-0.5 rounded-full bg-[#FAF0F2] border border-[#EAE3D9] text-[#680E23] font-semibold">🤖 صادرة (AI)</span>';
          } else if (c.direction === 'outbound_agent') {
            dirBadge = '<span class="text-[10px] px-2 py-0.5 rounded-full bg-[#FAF0F2] border border-[#EAE3D9] text-[#680E23] font-semibold">👤 صادرة (موظف)</span>';
          }
          const callerBadge = c.caller_phone ? `<span class="text-[10px] px-2 py-0.5 rounded bg-[#FAF0F2] border border-[#E8CCD2] font-mono text-[#680E23]">📱 ${escapeHtml(c.caller_phone)}</span>` : '';
          const destHtml = c.destination_phone ? `<span class="text-[10px] px-2 py-0.5 rounded bg-[#FAF0F2] border border-[#E8CCD2] font-mono text-[#680E23]">🎯 ${escapeHtml(c.destination_phone)}</span>` : '';
          return `
          <div class="p-3 rounded-2xl bg-white border border-[#EAE3D9] border border-[#E8CCD2]/40 flex flex-col md:flex-row md:items-center justify-between gap-2.5">
            <div class="space-y-1">
              <div class="flex flex-wrap items-center gap-2">
                ${dirBadge}
                ${callerBadge}
                ${destHtml}
                <span class="font-mono text-xs text-[#443D39] font-semibold">${escapeHtml(c.room_name)}</span>
                <span class="text-[10px] text-[#8C827A] font-mono">📅 ${escapeHtml(c.started_at)}</span>
                <span class="text-[10px] px-1.5 py-0.5 rounded bg-[#FAF0F2] text-[#680E23] border border-[#E8CCD2] font-mono">⏱️ ${c.duration_seconds} ثانية</span>
              </div>
              <p class="text-[11px] text-[#443D39] mt-1">${escapeHtml(c.summary || (c.call_goal ? 'الهدف: ' + c.call_goal : 'مكالمة مكتملة بدون ملخص'))}</p>
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
