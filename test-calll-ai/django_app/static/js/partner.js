/**
 * Partner & SaaS Portal JavaScript
 * Handles Partner KPIs, Headless API Access & Key Rotation, Webhook testing,
 * Shared MCP server configuration, Sub-clients management & spending caps, and Sub-clients CDR.
 */

let currentPartnerData = null;

async function checkPartnerStatusOnLoad() {
  try {
    const res = await fetch('/api/partner/v1/dashboard/');
    const data = await res.json();
    if (data.status === 'success') {
      currentPartnerData = data.partner;
      const banner = document.getElementById('partner-status-banner');
      if (banner) {
        if (data.partner.status === 'approved') {
          banner.className = 'hidden';
        } else if (data.partner.status === 'pending') {
          banner.className = 'p-4 rounded-2xl text-xs font-semibold bg-amber-50 text-amber-900 border border-amber-200 flex items-center justify-between gap-3';
          banner.innerHTML = `
            <div class="flex items-center gap-2">
              <span>⏳</span>
              <span>طلب الانضمام كشريك قيد المراجعة الإدارية. بمجرد الاعتماد ستتفعل مفاتيح الربط البرمجي وتسعير الجملة.</span>
            </div>
            <button type="button" onclick="openPartnerApplyModal(currentPartnerData)" class="px-3 py-1.5 rounded-lg bg-amber-100 hover:bg-amber-200 text-amber-900 text-xs font-bold transition">
              عرض الطلب
            </button>
          `;
        } else if (data.partner.status === 'rejected') {
          banner.className = 'p-4 rounded-2xl text-xs font-semibold bg-rose-50 text-rose-900 border border-rose-200 flex items-center justify-between gap-3';
          banner.innerHTML = `
            <div class="flex items-center gap-2">
              <span>❌</span>
              <span>تم رفض طلب الشراكة. يمكنك مراجعة البيانات وإعادة التقديم.</span>
            </div>
            <button type="button" onclick="openPartnerApplyModal(currentPartnerData)" class="px-3 py-1.5 rounded-lg bg-rose-100 hover:bg-rose-200 text-rose-900 text-xs font-bold transition">
              إعادة التقديم
            </button>
          `;
        }
      }
    } else {
      const banner = document.getElementById('partner-status-banner');
      if (banner) {
        banner.className = 'p-4 rounded-2xl text-xs font-semibold bg-[#FAF0F2] text-[#680E23] border border-[#EAE3D9] flex items-center justify-between gap-3';
        banner.innerHTML = `
          <div class="flex items-center gap-2">
            <span>💼</span>
            <span>لم تقم بالتقديم لبرنامج الشركاء والموزعين بعد. انضم الآن للحصول على خصومات تسعير الجملة ومفاتيح الربط البرمجي.</span>
          </div>
          <button type="button" onclick="openPartnerApplyModal(null)" class="px-4 py-1.5 rounded-xl bg-[#680E23] hover:bg-[#7E152F] text-white text-xs font-bold transition shadow-sm">
            تقديم طلب شراكة
          </button>
        `;
      }
    }
  } catch (e) {
    console.warn('Error checking partner status:', e);
  }
}

async function loadPartnerDashboard() {
  try {
    const res = await fetch('/api/partner/v1/dashboard/');
    const data = await res.json();

    if (data.status !== 'success') {
      await checkPartnerStatusOnLoad();
      return;
    }

    const partner = data.partner;
    const wallet = data.wallet || {};
    const kpis = data.kpis || {};
    const clients = data.clients || [];
    const calls = data.recent_calls || [];
    const mcpServers = data.mcp_servers || [];

    currentPartnerData = partner;
    await checkPartnerStatusOnLoad();

    // 1. KPIs
    const bEl = document.getElementById('partner-kpi-balance');
    const rEl = document.getElementById('partner-kpi-rate');
    const cEl = document.getElementById('partner-kpi-clients');
    const mEl = document.getElementById('partner-kpi-minutes');
    if (bEl) bEl.innerText = `$${(wallet.balance || 0).toFixed(2)}`;
    if (rEl) rEl.innerText = `$${(kpis.custom_rate || 0).toFixed(4)} / د`;
    if (cEl) cEl.innerText = kpis.total_clients || 0;
    if (mEl) mEl.innerText = `${kpis.total_minutes || 0} د`;

    // 2. Credentials
    const codeInp = document.getElementById('partner-code-input');
    const keyInp = document.getElementById('partner-api-key-input');
    const whInp = document.getElementById('partner-webhook-url-input');
    if (codeInp) codeInp.value = partner.partner_code || '';
    if (keyInp) keyInp.value = partner.api_key || '';
    if (whInp) whInp.value = partner.webhook_url || '';

    // 3. Shared MCP Servers dropdown
    const mcpSelect = document.getElementById('partner-shared-mcp-select');
    if (mcpSelect) {
      mcpSelect.innerHTML = '<option value="">-- بدون خادم موروث --</option>' +
        mcpServers.map(s => `<option value="${s.id}" ${partner.shared_mcp_server_id == s.id ? 'selected' : ''}>${escapeHtml(s.name)} (${escapeHtml(s.server_url)})</option>`).join('');
    }

    // 4. Clients Table
    const cTbody = document.getElementById('partner-clients-tbody');
    if (cTbody) {
      if (clients.length === 0) {
        cTbody.innerHTML = `<tr><td colspan="9" class="py-8 text-center text-[#8C827A]">لم يسجل أي عميل عبر الـ API الخلفي حتى الآن.</td></tr>`;
      } else {
        cTbody.innerHTML = clients.map(c => `
          <tr class="hover:bg-[#FAF7F2]/60 transition">
            <td class="py-3 px-4 font-mono font-bold text-[#680E23]">${c.client_id}</td>
            <td class="py-3 px-4 font-semibold text-[#1C1917]">${escapeHtml(c.name)} <span class="text-[10px] text-[#8C827A] block font-mono">${escapeHtml(c.email || '')}</span></td>
            <td class="py-3 px-4 font-mono text-[#443D39]">${escapeHtml(c.external_reference || '-')}</td>
            <td class="py-3 px-4 text-[#8C827A]">${escapeHtml(c.created_at || '')}</td>
            <td class="py-3 px-4 font-mono font-bold text-[#1C1917]">${c.total_minutes} د</td>
            <td class="py-3 px-4 font-mono font-bold text-emerald-700">$${c.total_spent ? c.total_spent.toFixed(2) : '0.00'}</td>
            <td class="py-3 px-4 text-[#443D39]">
              ${c.spending_cap ? '$' + c.spending_cap : 'بلا سقف'} 
              ${c.minute_cap ? '(' + c.minute_cap + 'د)' : ''}
            </td>
            <td class="py-3 px-4">
              <span class="px-2 py-0.5 rounded-full text-[10px] font-bold ${c.is_active ? 'bg-emerald-100 text-emerald-800' : 'bg-rose-100 text-rose-800'}">
                ${c.is_active ? 'مفعل' : 'موقوف'}
              </span>
            </td>
            <td class="py-3 px-4">
              <button type="button" onclick="openClientCapModal(${c.client_id}, ${c.spending_cap !== undefined && c.spending_cap !== null ? c.spending_cap : 'null'}, ${c.minute_cap !== undefined && c.minute_cap !== null ? c.minute_cap : 'null'}, ${c.is_active})" class="px-2.5 py-1 rounded-lg bg-[#FAF7F2] hover:bg-[#F5EFE6] text-[#680E23] border border-[#DDD5C7] text-xs font-semibold transition">
                ⚙️ تعديل السقف
              </button>
            </td>
          </tr>
        `).join('');
      }
    }

    // 5. CDR Table
    const callsTbody = document.getElementById('partner-calls-tbody');
    if (callsTbody) {
      if (calls.length === 0) {
        callsTbody.innerHTML = `<tr><td colspan="7" class="py-8 text-center text-[#8C827A]">لا توجد مكالمات مسجلة لعملاء الشريك حتى الآن.</td></tr>`;
      } else {
        callsTbody.innerHTML = calls.map(cl => `
          <tr class="hover:bg-[#FAF7F2]/60 transition">
            <td class="py-3 px-4 text-[#8C827A]">${escapeHtml(cl.started_at || '')}</td>
            <td class="py-3 px-4 font-bold text-[#1C1917]">${escapeHtml(cl.client_name)} <span class="text-[10px] text-[#680E23] block font-mono">ID: ${cl.client_id}</span></td>
            <td class="py-3 px-4 font-mono text-[#443D39]">${escapeHtml(cl.caller_phone || '-')}</td>
            <td class="py-3 px-4 font-mono text-[#443D39]">${cl.duration_seconds} ث</td>
            <td class="py-3 px-4 font-mono font-bold text-[#1C1917]">${cl.billed_minutes} د</td>
            <td class="py-3 px-4 font-mono font-bold text-emerald-700">$${cl.cost ? cl.cost.toFixed(2) : '0.00'}</td>
            <td class="py-3 px-4 text-xs text-[#443D39] max-w-xs truncate" title="${escapeHtml(cl.summary || '')}">${escapeHtml(cl.summary || 'لا يوجد ملخص')}</td>
          </tr>
        `).join('');
      }
    }

  } catch (e) {
    console.error('Error loading partner dashboard:', e);
  }
}

function togglePartnerKeyVisibility() {
  const inp = document.getElementById('partner-api-key-input');
  const btn = document.getElementById('btn-toggle-partner-key');
  if (!inp || !btn) return;
  if (inp.type === 'password') {
    inp.type = 'text';
    btn.innerText = 'إخفاء';
  } else {
    inp.type = 'password';
    btn.innerText = 'إظهار';
  }
}

function copyPartnerText(inputId) {
  const inp = document.getElementById(inputId);
  if (inp) {
    navigator.clipboard.writeText(inp.value);
    showToast('تم نسخ القيمة إلى الحافظة بنجاح!', 'success');
  }
}

async function regeneratePartnerApiKey() {
  if (!confirm('هل أنت متأكد من رغبتك في إعادة توليد مفتاح الـ API الرئيسي؟ سيتوقف المفتاح القديم عن العمل فوراً.')) return;
  try {
    const res = await fetch('/api/partner/v1/settings/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken')
      },
      body: JSON.stringify({ regenerate_api_key: true })
    });
    const data = await res.json();
    if (data.status === 'success') {
      showToast('تمت إعادة توليد المفتاح بنجاح.', 'success');
      const keyInp = document.getElementById('partner-api-key-input');
      if (keyInp && data.partner) keyInp.value = data.partner.api_key;
    } else {
      showToast(data.message || 'حدث خطأ أثناء إعادة التوليد', 'error');
    }
  } catch (e) {
    showToast('حدث خطأ أثناء إعادة التوليد', 'error');
  }
}

async function savePartnerSettings() {
  const whUrl = document.getElementById('partner-webhook-url-input').value.trim();
  const mcpSelect = document.getElementById('partner-shared-mcp-select');
  const mcpId = mcpSelect ? mcpSelect.value : null;

  try {
    const res = await fetch('/api/partner/v1/settings/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken')
      },
      body: JSON.stringify({ webhook_url: whUrl, shared_mcp_server_id: mcpId || null })
    });
    const data = await res.json();
    if (data.status === 'success') {
      showToast('تم حفظ إعدادات الشريك والـ Webhook بنجاح.', 'success');
    } else {
      showToast(data.message || 'حدث خطأ أثناء الحفظ.', 'error');
    }
  } catch (e) {
    showToast('تعذر حفظ الإعدادات', 'error');
  }
}

async function testPartnerWebhook() {
  try {
    const res = await fetch('/api/partner/v1/settings/test-webhook/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken')
      }
    });
    const data = await res.json();
    if (data.status === 'success') {
      showToast('تم إرسال اختبار Webhook بنجاح إلى رابطك!', 'success');
    } else {
      showToast(data.message || 'فشل إرسال اختبار الـ Webhook.', 'error');
    }
  } catch (e) {
    showToast('تعذر اختبار الـ Webhook.', 'error');
  }
}

function openClientCapModal(clientId, spendingCap, minuteCap, isActive) {
  document.getElementById('cap-modal-client-id').value = clientId;
  document.getElementById('cap-modal-spending').value = spendingCap !== null && spendingCap !== undefined ? spendingCap : '';
  document.getElementById('cap-modal-minutes').value = minuteCap !== null && minuteCap !== undefined ? minuteCap : '';
  document.getElementById('cap-modal-active').checked = isActive !== false;
  const alertBox = document.getElementById('cap-modal-alert');
  if (alertBox) alertBox.classList.add('hidden');
  document.getElementById('partner-cap-modal').classList.remove('hidden');
}

function closeClientCapModal() {
  document.getElementById('partner-cap-modal').classList.add('hidden');
}

async function saveClientCap() {
  const clientId = document.getElementById('cap-modal-client-id').value;
  const spending = document.getElementById('cap-modal-spending').value;
  const minutes = document.getElementById('cap-modal-minutes').value;
  const isActive = document.getElementById('cap-modal-active').checked;
  const alertBox = document.getElementById('cap-modal-alert');

  try {
    const res = await fetch('/api/partner/v1/clients/cap/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken')
      },
      body: JSON.stringify({
        client_id: clientId,
        spending_cap: spending !== '' ? parseFloat(spending) : null,
        minute_cap: minutes !== '' ? parseInt(minutes) : null,
        is_active: isActive
      })
    });
    const data = await res.json();
    if (data.status === 'success') {
      closeClientCapModal();
      showToast('تم تحديث سقف استهلاك العميل بنجاح.', 'success');
      await loadPartnerDashboard();
    } else {
      if (alertBox) {
        alertBox.className = 'p-2 rounded-xl text-xs bg-rose-100 text-rose-800 block';
        alertBox.innerText = data.message || 'حدث خطأ أثناء الحفظ.';
      }
    }
  } catch (e) {
    if (alertBox) {
      alertBox.className = 'p-2 rounded-xl text-xs bg-rose-100 text-rose-800 block';
      alertBox.innerText = 'تعذر الاتصال بالخادم.';
    }
  }
}

function openPartnerDocsModal() {
  const modal = document.getElementById('partner-docs-modal');
  if (modal) modal.classList.remove('hidden');
}

function closePartnerDocsModal() {
  const modal = document.getElementById('partner-docs-modal');
  if (modal) modal.classList.add('hidden');
}

function openPartnerApplyModal(existing) {
  const m = document.getElementById('partner-apply-modal');
  const alertBox = document.getElementById('partner-apply-alert');

  if (alertBox) {
    if (existing && existing.status === 'pending') {
      alertBox.className = 'p-3 rounded-xl text-xs bg-amber-50 text-amber-900 border border-amber-200 block';
      alertBox.innerHTML = `⚠️ <strong>طلبك قيد المراجعة:</strong> تم استلام طلبك لشركة <strong>${escapeHtml(existing.company_name)}</strong> وجاري مراجعته من الإدارة لتفعيل تسعير الجملة والمفاتيح.`;
    } else if (existing && existing.status === 'rejected') {
      alertBox.className = 'p-3 rounded-xl text-xs bg-rose-50 text-rose-900 border border-rose-200 block';
      alertBox.innerHTML = `❌ تم رفض الطلب السابق. يمكنك إعادة التقديم أدناه.`;
    } else {
      alertBox.className = 'hidden';
    }
  }

  if (existing) {
    const cInp = document.getElementById('partner-apply-company');
    const wInp = document.getElementById('partner-apply-website');
    const dInp = document.getElementById('partner-apply-desc');
    if (cInp) cInp.value = existing.company_name || '';
    if (wInp) wInp.value = existing.website || '';
    if (dInp) dInp.value = existing.description || '';
  }

  if (m) m.classList.remove('hidden');
}

function closePartnerApplyModal() {
  const m = document.getElementById('partner-apply-modal');
  if (m) m.classList.add('hidden');
}

async function submitPartnerApply(event) {
  event.preventDefault();
  const btn = document.getElementById('btn-submit-partner-apply');
  const company = document.getElementById('partner-apply-company').value.trim();
  const website = document.getElementById('partner-apply-website').value.trim();
  const description = document.getElementById('partner-apply-desc').value.trim();
  const alertBox = document.getElementById('partner-apply-alert');

  if (!company) return;

  btn.disabled = true;
  btn.innerText = 'جاري الإرسال...';

  try {
    const res = await fetch('/api/partner/v1/apply/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken')
      },
      body: JSON.stringify({ company_name: company, website: website, description: description })
    });
    const data = await res.json();
    if (data.status === 'success') {
      if (alertBox) {
        alertBox.className = 'p-3 rounded-xl text-xs bg-emerald-50 text-emerald-900 border border-emerald-200 block';
        alertBox.innerText = data.message;
      }
      showToast('تم إرسال الطلب بنجاح!', 'success');
      setTimeout(() => {
        closePartnerApplyModal();
        loadPartnerDashboard();
      }, 1500);
    } else {
      if (alertBox) {
        alertBox.className = 'p-3 rounded-xl text-xs bg-rose-50 text-rose-900 border border-rose-200 block';
        alertBox.innerText = data.message || 'حدث خطأ أثناء التقديم';
      }
    }
  } catch (err) {
    if (alertBox) {
      alertBox.className = 'p-3 rounded-xl text-xs bg-rose-50 text-rose-900 border border-rose-200 block';
      alertBox.innerText = 'تعذر الاتصال بالخادم';
    }
  } finally {
    btn.disabled = false;
    btn.innerText = 'إرسال الطلب للمراجعة';
  }
}

document.addEventListener('DOMContentLoaded', () => {
  loadPartnerDashboard();
});
