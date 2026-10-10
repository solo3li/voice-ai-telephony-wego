/**
 * Outbound Campaigns & CRM Leads Engine JavaScript
 * Supports Multi-channel Campaigns: Voice Calls, WhatsApp, and Hybrid (Calls + WhatsApp).
 * Powered by Inngest for concurrent queuing, LiveKit telephony, and Evolution API.
 */

let campaignsList = [];
let currentCampaignId = null;
let currentCampaignData = null;
let currentCampaignContacts = [];
let currentContactFilter = 'all';
let currentContactSearch = '';
let hasActiveOutboundGateway = false;
let hasWhatsAppConnected = false;
let selectedCampaignChannel = 'calls';
let campaignSearchDebounceTimer = null;
let campaignAutoPollTimer = null;

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function updateGatewayAlertUI() {
  const gwAlertEl = document.getElementById('camp-no-gateway-alert');
  const waAlertEl = document.getElementById('camp-no-whatsapp-alert');
  const btnStart = document.getElementById('btn-start-campaign');

  const channel = currentCampaignData ? currentCampaignData.channel : 'calls';

  // SIP Trunk Alert: only relevant if campaign includes Voice Calls
  if (gwAlertEl) {
    if (['calls', 'hybrid'].includes(channel) && !hasActiveOutboundGateway) {
      gwAlertEl.classList.remove('hidden');
    } else {
      gwAlertEl.classList.add('hidden');
    }
  }

  // WhatsApp Alert: only relevant if campaign includes WhatsApp
  if (waAlertEl) {
    if (['whatsapp', 'hybrid'].includes(channel) && !hasWhatsAppConnected) {
      waAlertEl.classList.remove('hidden');
    } else {
      waAlertEl.classList.add('hidden');
    }
  }

  // Start Button state & tooltips
  if (btnStart) {
    let warning = '';
    if (['calls', 'hybrid'].includes(channel) && !hasActiveOutboundGateway) {
      warning = 'لا يوجد خط اتصال صادر (SIP Trunk) مفعل حالياً';
    } else if (['whatsapp', 'hybrid'].includes(channel) && !hasWhatsAppConnected) {
      warning = 'حساب الواتساب غير متصل في لوحة التحكم';
    }

    if (warning) {
      btnStart.title = warning;
      btnStart.classList.add('opacity-80');
    } else {
      btnStart.title = '';
      btnStart.classList.remove('opacity-80');
    }
  }
}

async function loadCampaignsList(selectCampaignId = null) {
  try {
    const res = await fetch('/api/crm/campaigns/');
    const data = await res.json();
    if (data.status !== 'success') return;

    campaignsList = data.campaigns || [];
    const userLimit = data.user_concurrency_limit || 1;
    hasActiveOutboundGateway = Boolean(data.has_outbound_gateway);
    hasWhatsAppConnected = Boolean(data.has_whatsapp_connected);

    // Update global stats
    const totalCampsEl = document.getElementById('camp-stat-total-campaigns');
    if (totalCampsEl) totalCampsEl.innerText = campaignsList.length;

    const modalLimitText = document.getElementById('camp-modal-limit-text');
    if (modalLimitText) modalLimitText.innerText = `${userLimit} عمليات متزامنة`;

    // Populate dropdown
    const select = document.getElementById('campaign-select');
    if (!select) return;

    if (campaignsList.length === 0) {
      select.innerHTML = '<option value="">لا توجد حملات منشأة بعد</option>';
      resetCampaignDetailsUI();
      updateGatewayAlertUI();
      return;
    }

    let targetId = selectCampaignId || currentCampaignId;
    if (!targetId || !campaignsList.find(c => c.id == targetId)) {
      targetId = campaignsList[0].id;
    }

    select.innerHTML = campaignsList.map(c => `
      <option value="${c.id}" ${c.id == targetId ? 'selected' : ''}>
        ${escapeHtml(c.name)} (${c.total_contacts} عميل - ${c.channel_display || c.channel} - ${getStatusLabel(c.status)})
      </option>
    `).join('');

    await onCampaignSelected(targetId);
  } catch (err) {
    console.error('Error loading campaigns list:', err);
  }
}

function getStatusLabel(status) {
  switch (status) {
    case 'running': return '⚡ قيد التنفيذ';
    case 'paused': return '⏸️ متوقفة مؤقتاً';
    case 'completed': return '✅ مكتملة';
    case 'cancelled': return '⛔ ملغية';
    default: return '📝 مسودة';
  }
}

function getStatusBadgeHtml(status) {
  switch (status) {
    case 'running':
      return '<span class="px-2.5 py-1 rounded-full text-[10px] font-bold bg-amber-100 text-amber-800 border border-amber-300 animate-pulse">⚡ قيد التنفيذ التلقائي</span>';
    case 'paused':
      return '<span class="px-2.5 py-1 rounded-full text-[10px] font-bold bg-slate-100 text-slate-700 border border-slate-300">⏸️ متوقفة مؤقتاً</span>';
    case 'completed':
      return '<span class="px-2.5 py-1 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-200">✅ مكتملة بنجاح</span>';
    default:
      return '<span class="px-2.5 py-1 rounded-full text-[10px] font-bold bg-[#FAF0F2] text-[#680E23] border border-[#E8CCD2]">📝 مسودة (جاهزة للإطلاق)</span>';
  }
}

function resetCampaignDetailsUI() {
  const tbody = document.getElementById('camp-contacts-tbody');
  if (tbody) {
    tbody.innerHTML = '<tr><td colspan="8" class="text-center py-8 text-[#8C827A]">اختر حملة أو أنشئ حملة جديدة لرفع وعرض قائمة العملاء.</td></tr>';
  }
  const progressBar = document.getElementById('camp-progress-bar');
  if (progressBar) progressBar.style.width = '0%';
  const progressText = document.getElementById('camp-progress-text');
  if (progressText) progressText.innerText = '0% (0 / 0)';
}

async function onCampaignSelected(campaignId) {
  if (!campaignId) return;
  currentCampaignId = campaignId;

  try {
    let url = `/api/crm/campaigns/${campaignId}/?limit=300`;
    if (currentContactFilter && currentContactFilter !== 'all') {
      if (['hot', 'warm', 'cold'].includes(currentContactFilter)) {
        url += `&interest=${currentContactFilter}`;
      } else if (currentContactFilter === 'wa_sent') {
        url += `&whatsapp_status=sent`;
      } else {
        url += `&call_status=${currentContactFilter}`;
      }
    }
    if (currentContactSearch) {
      url += `&q=${encodeURIComponent(currentContactSearch)}`;
    }

    const res = await fetch(url);
    const data = await res.json();
    if (data.status !== 'success') {
      console.error('Failed to load campaign detail:', data.message);
      return;
    }

    currentCampaignData = data.campaign;
    currentCampaignContacts = data.contacts || [];

    if (data.has_outbound_gateway !== undefined) {
      hasActiveOutboundGateway = Boolean(data.has_outbound_gateway);
    }
    if (data.has_whatsapp_connected !== undefined) {
      hasWhatsAppConnected = Boolean(data.has_whatsapp_connected);
    }

    updateGatewayAlertUI();
    renderCampaignHeaderAndStats(data.campaign);
    renderCampaignContactsTable(currentCampaignContacts);

    // Auto polling if campaign is currently running
    if (data.campaign.status === 'running') {
      if (!campaignAutoPollTimer) {
        campaignAutoPollTimer = setInterval(() => {
          if (currentCampaignId) {
            onCampaignSelected(currentCampaignId);
          }
        }, 5000);
      }
    } else {
      if (campaignAutoPollTimer) {
        clearInterval(campaignAutoPollTimer);
        campaignAutoPollTimer = null;
      }
    }
  } catch (err) {
    console.error('Error fetching campaign detail:', err);
  }
}

function renderCampaignHeaderAndStats(camp) {
  const statusBadge = document.getElementById('camp-status-badge');
  if (statusBadge) statusBadge.outerHTML = `<span id="camp-status-badge">${getStatusBadgeHtml(camp.status)}</span>`;

  // Channel badge
  const chBadge = document.getElementById('camp-channel-badge');
  if (chBadge) {
    if (camp.channel === 'whatsapp') {
      chBadge.className = 'px-2.5 py-1 rounded-full text-[10px] font-bold bg-teal-100 text-teal-800 border border-teal-300';
      chBadge.innerText = '💬 واتساب فقط';
    } else if (camp.channel === 'hybrid') {
      chBadge.className = 'px-2.5 py-1 rounded-full text-[10px] font-bold bg-purple-100 text-purple-800 border border-purple-300';
      chBadge.innerText = '⚡ هجينة (اتصال + واتساب)';
    } else {
      chBadge.className = 'px-2.5 py-1 rounded-full text-[10px] font-bold bg-[#FAF0F2] text-[#680E23] border border-[#E8CCD2]';
      chBadge.innerText = '📞 مكالمات فقط';
    }
  }

  // Start / Pause button visibility & label
  const btnStart = document.getElementById('btn-start-campaign');
  const btnPause = document.getElementById('btn-pause-campaign');
  const btnStartLabel = document.getElementById('btn-start-campaign-label');

  if (btnStartLabel) {
    if (camp.channel === 'whatsapp') {
      btnStartLabel.innerText = 'بدء إرسال رسائل الواتساب';
    } else if (camp.channel === 'hybrid') {
      btnStartLabel.innerText = 'بدء الحملة الهجينة';
    } else {
      btnStartLabel.innerText = 'بدء الاتصال التلقائي';
    }
  }

  if (camp.status === 'running') {
    if (btnStart) btnStart.classList.add('hidden');
    if (btnPause) btnPause.classList.remove('hidden');
  } else {
    if (btnStart) btnStart.classList.remove('hidden');
    if (btnPause) btnPause.classList.add('hidden');
  }

  const total = camp.total_contacts || 0;
  const completed = camp.completed_contacts || 0;
  const pct = camp.progress_percent || (total > 0 ? Math.round((completed / total) * 100) : 0);

  const pBar = document.getElementById('camp-progress-bar');
  if (pBar) pBar.style.width = `${pct}%`;

  const pText = document.getElementById('camp-progress-text');
  if (pText) pText.innerText = `${pct}% (${completed} / ${total})`;

  const chText = document.getElementById('camp-channel-text');
  if (chText) chText.innerText = camp.channel_display || (camp.channel === 'whatsapp' ? 'واتساب' : camp.channel === 'hybrid' ? 'هجينة' : 'مكالمات');

  const agentNameEl = document.getElementById('camp-agent-name');
  if (agentNameEl) agentNameEl.innerText = camp.agent_profile_name || 'افتراضي';

  const promptPreview = document.getElementById('camp-prompt-preview');
  if (promptPreview) {
    let pTxt = '';
    if (camp.channel === 'whatsapp') {
      pTxt = camp.whatsapp_prompt ? `رسالة الواتساب: "${camp.whatsapp_prompt}"` : 'توجيهات الواتساب الافتراضية';
    } else if (camp.channel === 'hybrid') {
      pTxt = `المكالمة: "${camp.call_prompt || '-'}" | الواتساب: "${camp.whatsapp_prompt || '-'}"`;
    } else {
      pTxt = camp.call_prompt ? `السيناريو: "${camp.call_prompt}"` : 'السيناريو: السيناريو الافتراضي';
    }
    promptPreview.innerText = pTxt;
  }

  // Stats numbers
  const statContacts = document.getElementById('camp-stat-total-contacts');
  if (statContacts) statContacts.innerText = total;

  const statAnswered = document.getElementById('camp-stat-answered-contacts');
  if (statAnswered) statAnswered.innerText = camp.answered_contacts || 0;

  const statWaSent = document.getElementById('camp-stat-whatsapp-sent');
  if (statWaSent) statWaSent.innerText = camp.whatsapp_sent_contacts || 0;

  const statHot = document.getElementById('camp-stat-total-hot');
  if (statHot) statHot.innerText = camp.hot_leads_count || 0;

  // Filter counters
  const fAll = document.getElementById('count-filter-all');
  if (fAll) fAll.innerText = total;
  const fPending = document.getElementById('count-filter-pending');
  if (fPending) fPending.innerText = camp.pending_calls || 0;
  const fAnswered = document.getElementById('count-filter-answered');
  if (fAnswered) fAnswered.innerText = camp.answered_contacts || 0;
  const fWaSent = document.getElementById('count-filter-wa-sent');
  if (fWaSent) fWaSent.innerText = camp.whatsapp_sent_contacts || 0;
  const fHot = document.getElementById('count-filter-hot');
  if (fHot) fHot.innerText = camp.hot_leads_count || 0;
  const fWarm = document.getElementById('count-filter-warm');
  if (fWarm) fWarm.innerText = camp.warm_leads_count || 0;
  const fCold = document.getElementById('count-filter-cold');
  if (fCold) fCold.innerText = camp.cold_leads_count || 0;
}

function renderCampaignContactsTable(contacts) {
  const tbody = document.getElementById('camp-contacts-tbody');
  if (!tbody) return;

  if (!contacts || contacts.length === 0) {
    tbody.innerHTML = '<tr><td colspan="8" class="text-center py-8 text-[#8C827A]">لا توجد نتائج مطابقة لفلتر البحث.</td></tr>';
    return;
  }

  tbody.innerHTML = contacts.map(c => {
    // 1. Call Status Badge
    let callBadge = '<span class="px-2 py-0.5 rounded-full text-[10px] bg-slate-100 text-slate-700">⏳ في الانتظار</span>';
    if (c.call_status === 'in_progress') {
      callBadge = '<span class="px-2 py-0.5 rounded-full text-[10px] bg-amber-100 text-amber-800 animate-pulse font-bold">📞 جاري الاتصال</span>';
    } else if (c.call_status === 'answered') {
      callBadge = '<span class="px-2 py-0.5 rounded-full text-[10px] bg-emerald-100 text-emerald-800 font-bold">✅ تم الرد</span>';
    } else if (c.call_status === 'failed' || c.call_status === 'no_answer' || c.call_status === 'busy') {
      callBadge = `<span class="px-2 py-0.5 rounded-full text-[10px] bg-rose-100 text-rose-800">❌ لم يرد (${c.retries_count} محاولة)</span>`;
    }

    // 2. WhatsApp Status Badge
    let waBadge = '<span class="px-2 py-0.5 rounded-full text-[10px] bg-slate-100 text-slate-500">لم يُرسل</span>';
    if (c.whatsapp_status === 'in_progress') {
      waBadge = '<span class="px-2 py-0.5 rounded-full text-[10px] bg-teal-100 text-teal-800 animate-pulse font-bold">💬 جاري الإرسال</span>';
    } else if (c.whatsapp_status === 'sent' || c.whatsapp_status === 'delivered') {
      waBadge = '<span class="px-2 py-0.5 rounded-full text-[10px] bg-teal-100 text-teal-900 font-bold">💬 تم الإرسال</span>';
    } else if (c.whatsapp_status === 'replied') {
      waBadge = '<span class="px-2 py-0.5 rounded-full text-[10px] bg-emerald-100 text-emerald-900 font-bold">💬 تم الرد</span>';
    } else if (c.whatsapp_status === 'failed') {
      waBadge = `<span class="px-2 py-0.5 rounded-full text-[10px] bg-rose-100 text-rose-800 font-semibold" title="${escapeHtml(c.whatsapp_message_text)}">❌ فشل الإرسال</span>`;
    }

    // 3. AI Lead Score Badge
    let aiBadge = '<span class="text-[#8C827A] text-[10px]">لم يتحدد</span>';
    if (c.interest_level === 'hot') {
      aiBadge = '<span class="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-rose-100 text-rose-800 border border-rose-300 shadow-sm flex items-center gap-1 w-fit"><span>🔥</span><span>مهتم جداً</span></span>';
    } else if (c.interest_level === 'warm') {
      aiBadge = '<span class="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-800 border border-amber-300 w-fit"><span>🟡</span><span>متابعة</span></span>';
    } else if (c.interest_level === 'cold') {
      aiBadge = '<span class="px-2.5 py-0.5 rounded-full text-[10px] bg-slate-100 text-slate-700 w-fit"><span>❄️</span><span>غير مهتم</span></span>';
    }

    // 4. Attributes Preview
    let attrsHtml = '<span class="text-[#8C827A] text-[10px]">-</span>';
    if (c.attributes && typeof c.attributes === 'object' && Object.keys(c.attributes).length > 0) {
      attrsHtml = Object.entries(c.attributes).slice(0, 3).map(([k, v]) => `
        <span class="inline-block px-1.5 py-0.5 text-[9px] rounded bg-[#FAF7F2] border border-[#DDD5C7] text-[#443D39] mr-1 mb-1">
          <strong>${escapeHtml(k)}:</strong> ${escapeHtml(String(v))}
        </span>
      `).join('');
    }

    // 5. Summary / Message Preview
    let summaryHtml = '';
    if (c.call_summary) {
      summaryHtml = `<div class="truncate text-[#1C1917]" title="${escapeHtml(c.call_summary)}"><strong>📞</strong> ${escapeHtml(c.call_summary)}</div>`;
    }
    if (c.whatsapp_message_text) {
      summaryHtml += `<div class="truncate text-teal-800 text-[11px] mt-0.5" title="${escapeHtml(c.whatsapp_message_text)}"><strong>💬</strong> ${escapeHtml(c.whatsapp_message_text)}</div>`;
    }
    if (!summaryHtml) {
      summaryHtml = '<span class="text-[#8C827A] italic">لا يوجد ملخص أو رسالة بعد</span>';
    }

    return `
      <tr class="hover:bg-[#FAF7F2]/50 transition">
        <td class="py-3 px-4 font-bold text-[#1C1917] whitespace-nowrap">
          <div class="flex items-center gap-2">
            <span class="w-6 h-6 rounded-full bg-[#FAF0F2] text-[#680E23] flex items-center justify-center text-[10px] font-bold">👤</span>
            <span>${escapeHtml(c.customer_name)}</span>
          </div>
        </td>
        <td class="py-3 px-3 font-mono text-[#2D2825] text-xs whitespace-nowrap dir-ltr text-start">${escapeHtml(c.phone_number)}</td>
        <td class="py-3 px-3 whitespace-nowrap">${callBadge}</td>
        <td class="py-3 px-3 whitespace-nowrap">${waBadge}</td>
        <td class="py-3 px-3 whitespace-nowrap">${aiBadge}</td>
        <td class="py-3 px-4 text-[#443D39] max-w-[260px]">
          ${summaryHtml}
        </td>
        <td class="py-3 px-3 max-w-[160px]">
          ${attrsHtml}
        </td>
        <td class="py-3 px-3 text-center whitespace-nowrap">
          <div class="flex items-center justify-center gap-1.5">
            <button type="button" onclick="dialSingleContact(${c.id})" class="px-2.5 py-1 rounded-lg bg-emerald-50 hover:bg-emerald-100 text-emerald-800 border border-emerald-200 text-[11px] font-semibold transition" title="إجراء مكالمة هاتفية فورية">
              📞 اتصال
            </button>
            <button type="button" onclick="sendSingleContactWhatsApp(${c.id})" class="px-2.5 py-1 rounded-lg bg-teal-50 hover:bg-teal-100 text-teal-800 border border-teal-200 text-[11px] font-semibold transition" title="إرسال رسالة واتساب مخصصة فورية">
              💬 واتساب
            </button>
            <button type="button" onclick="openContactDetailsModal(${c.id})" class="px-2 py-1 rounded-lg bg-[#FAF0F2] hover:bg-[#F3DCE1] text-[#680E23] border border-[#E8CCD2] text-[11px] font-semibold transition" title="عرض التفاصيل الكاملة">
              🔍
            </button>
          </div>
        </td>
      </tr>
    `;
  }).join('');
}

function onCampaignChannelChanged(channel) {
  selectedCampaignChannel = channel;

  // Radio cards visual feedback
  ['calls', 'whatsapp', 'hybrid'].forEach(ch => {
    const card = document.getElementById(`card-channel-${ch}`);
    if (card) {
      if (ch === channel) {
        card.className = 'channel-card flex flex-col items-center justify-center p-3 rounded-2xl border-2 border-[#680E23] bg-[#FAF0F2] cursor-pointer transition text-center shadow-sm';
      } else {
        card.className = 'channel-card flex flex-col items-center justify-center p-3 rounded-2xl border border-[#DDD5C7] bg-[#FAF7F2] hover:border-[#680E23]/40 cursor-pointer transition text-center';
      }
    }
  });

  const agentContainer = document.getElementById('container-camp-agent');
  const callPromptContainer = document.getElementById('container-call-prompt');
  const waPromptContainer = document.getElementById('container-whatsapp-prompt');
  const retriesContainer = document.getElementById('container-camp-retries');
  const callPromptInput = document.getElementById('camp-input-prompt');
  const waPromptInput = document.getElementById('camp-input-wa-prompt');

  if (channel === 'whatsapp') {
    if (agentContainer) agentContainer.classList.add('hidden');
    if (callPromptContainer) callPromptContainer.classList.add('hidden');
    if (waPromptContainer) waPromptContainer.classList.remove('hidden');
    if (retriesContainer) retriesContainer.classList.add('hidden');
    if (callPromptInput) callPromptInput.required = false;
    if (waPromptInput) waPromptInput.required = true;
  } else if (channel === 'calls') {
    if (agentContainer) agentContainer.classList.remove('hidden');
    if (callPromptContainer) callPromptContainer.classList.remove('hidden');
    if (waPromptContainer) waPromptContainer.classList.add('hidden');
    if (retriesContainer) retriesContainer.classList.remove('hidden');
    if (callPromptInput) callPromptInput.required = true;
    if (waPromptInput) waPromptInput.required = false;
  } else { // hybrid
    if (agentContainer) agentContainer.classList.remove('hidden');
    if (callPromptContainer) callPromptContainer.classList.remove('hidden');
    if (waPromptContainer) waPromptContainer.classList.remove('hidden');
    if (retriesContainer) retriesContainer.classList.remove('hidden');
    if (callPromptInput) callPromptInput.required = true;
    if (waPromptInput) waPromptInput.required = false;
  }
}

async function populateCampaignAgentOptions() {
  const agentSelect = document.getElementById('camp-input-agent');
  if (!agentSelect) return;
  try {
    const res = await fetch('/api/agents/profiles/');
    const data = await res.json();
    if (data.status === 'success' && data.profiles) {
      agentSelect.innerHTML = data.profiles.map(p => `
        <option value="${p.id}" ${p.is_active ? 'selected' : ''}>${escapeHtml(p.name)} (${p.dialect_display || p.dialect})</option>
      `).join('');
    } else {
      agentSelect.innerHTML = '<option value="">المساعد الافتراضي</option>';
    }
  } catch (e) {
    agentSelect.innerHTML = '<option value="">المساعد الافتراضي</option>';
  }
}

function openNewCampaignModal() {
  const modal = document.getElementById('modal-create-campaign');
  if (!modal) return;

  populateCampaignAgentOptions();

  const nameInput = document.getElementById('camp-input-name');
  if (nameInput) {
    const d = new Date();
    nameInput.value = `حملة ${d.getFullYear()}/${d.getMonth()+1}/${d.getDate()} - ${d.getHours()}:${String(d.getMinutes()).padStart(2, '0')}`;
  }

  // Default to Calls channel
  const callsRadio = document.querySelector('input[name="camp_channel"][value="calls"]');
  if (callsRadio) callsRadio.checked = true;
  onCampaignChannelChanged('calls');

  const promptInput = document.getElementById('camp-input-prompt');
  if (promptInput) {
    promptInput.value = 'أنت ممثل خدمة عملاء محترف ومستشار أعمال ودود. ابدأ بالترحيب بالعميل {name} بأسلوب لبق، واعرض عليه تفاصيل العرض والفرصة المميزة، واستمع باهتمام لاستفساراته، ودون ملاحظاته وقراره بدقة.';
  }

  const waPromptInput = document.getElementById('camp-input-wa-prompt');
  if (waPromptInput) {
    waPromptInput.value = 'مرحباً {name}، يسعدنا تواصلنا معكم لتقديم عرض حصري وخاص بكم. تفضلوا بالاطلاع والتواصل معنا للرد على أي استفسار.';
  }

  const fileInput = document.getElementById('camp-input-file');
  if (fileInput) fileInput.value = '';

  const filePreview = document.getElementById('camp-file-preview');
  if (filePreview) filePreview.classList.add('hidden');

  const fileLabel = document.getElementById('camp-file-label');
  if (fileLabel) fileLabel.innerText = 'اضغط لاختيار ملف من جهازك أو اسحبه وأفلته هنا';

  const errorBox = document.getElementById('camp-modal-error');
  if (errorBox) {
    errorBox.classList.add('hidden');
    errorBox.innerText = '';
  }

  modal.classList.remove('hidden');
}

function closeNewCampaignModal() {
  const modal = document.getElementById('modal-create-campaign');
  if (modal) modal.classList.add('hidden');
}

function onCampaignFileSelected(input) {
  if (!input.files || input.files.length === 0) return;
  const file = input.files[0];
  const preview = document.getElementById('camp-file-preview');
  const nameEl = document.getElementById('camp-file-name');
  const sizeEl = document.getElementById('camp-file-size');
  const labelEl = document.getElementById('camp-file-label');

  if (nameEl) nameEl.innerText = file.name;
  if (sizeEl) sizeEl.innerText = `${(file.size / 1024).toFixed(1)} KB`;
  if (labelEl) labelEl.innerText = `تم اختيار: ${file.name}`;
  if (preview) preview.classList.remove('hidden');
}

async function submitNewCampaign(event) {
  event.preventDefault();

  const btnSubmit = document.getElementById('camp-btn-submit');
  const errorBox = document.getElementById('camp-modal-error');
  if (errorBox) errorBox.classList.add('hidden');

  const fileInput = document.getElementById('camp-input-file');
  if (!fileInput.files || fileInput.files.length === 0) {
    if (errorBox) {
      errorBox.innerText = 'يرجى اختيار ملف بيانات العملاء أولاً.';
      errorBox.classList.remove('hidden');
    }
    return;
  }

  const selectedChannelEl = document.querySelector('input[name="camp_channel"]:checked');
  const channel = selectedChannelEl ? selectedChannelEl.value : 'calls';

  const formData = new FormData();
  formData.append('file', fileInput.files[0]);
  formData.append('name', document.getElementById('camp-input-name').value.trim());
  formData.append('channel', channel);

  const callPrompt = document.getElementById('camp-input-prompt')?.value.trim() || '';
  const waPrompt = document.getElementById('camp-input-wa-prompt')?.value.trim() || '';
  formData.append('call_prompt', callPrompt);
  formData.append('whatsapp_prompt', waPrompt);

  const agentSelect = document.getElementById('camp-input-agent');
  if (agentSelect && agentSelect.value && channel !== 'whatsapp') {
    formData.append('agent_profile_id', agentSelect.value);
  }

  const retries = document.getElementById('camp-input-retries');
  if (retries && channel !== 'whatsapp') formData.append('max_retries', retries.value);

  const delay = document.getElementById('camp-input-delay');
  if (delay && channel !== 'whatsapp') formData.append('retry_delay_minutes', delay.value);

  if (btnSubmit) {
    btnSubmit.disabled = true;
    btnSubmit.innerHTML = '<span>⏳</span><span>جاري رفع وتحليل الملف...</span>';
  }

  try {
    const res = await fetch('/api/crm/campaigns/upload/', {
      method: 'POST',
      body: formData,
      headers: {
        'X-CSRFToken': getCookie('csrftoken')
      }
    });

    const data = await res.json();
    if (data.status === 'success') {
      if (typeof showToast === 'function') {
        showToast(`تم استيراد ${data.total_extracted} عميل بنجاح وتنظيمهم في الـ CRM!`, 'success');
      }
      closeNewCampaignModal();
      await loadCampaignsList(data.campaign.id);
    } else {
      if (errorBox) {
        errorBox.innerText = data.message || 'فشل استيراد الملف.';
        errorBox.classList.remove('hidden');
      }
    }
  } catch (err) {
    console.error('Error uploading campaign:', err);
    if (errorBox) {
      errorBox.innerText = 'حدث خطأ في الاتصال أثناء رفع الملف: ' + err.message;
      errorBox.classList.remove('hidden');
    }
  } finally {
    if (btnSubmit) {
      btnSubmit.disabled = false;
      btnSubmit.innerHTML = '<span>🚀</span><span>رفع وتنظيم العملاء في الـ CRM</span>';
    }
  }
}

async function startCurrentCampaign() {
  if (!currentCampaignId) return;

  const channel = currentCampaignData ? currentCampaignData.channel : 'calls';

  // Strict Pre-flight Checks
  if (['calls', 'hybrid'].includes(channel) && !hasActiveOutboundGateway) {
    if (typeof showToast === 'function') showToast('لا يمكن بدء الحملة: لا يوجد خط اتصال صادر (SIP Trunk) مفعل.', 'error');
    alert('تنبيه هام: لا يوجد مسار اتصال صادر (SIP Trunk) مفعل حالياً في حسابك.\n\nيرجى التوجه لتبويب "الربط الهاتفي والسنترال" وإعداد خط صادر أولاً للتمكن من الاتصال بالعملاء.');
    return;
  }

  if (['whatsapp', 'hybrid'].includes(channel) && !hasWhatsAppConnected) {
    if (typeof showToast === 'function') showToast('لا يمكن بدء الحملة: حساب الواتساب غير متصل.', 'error');
    alert('تنبيه هام: حساب الواتساب غير متصل حالياً (Evolution API).\n\nيرجى التوجه لتبويب "الواتساب والذكاء الاصطناعي" ومسح كود الربط أولاً.');
    return;
  }

  let promptMsg = 'هل تريد بالتأكيد بدء حملة الاتصال التلقائي الآن؟';
  if (channel === 'whatsapp') {
    promptMsg = 'هل تريد بالتأكيد بدء إرسال رسائل الواتساب الذكية لكافة العملاء في الحملة الآن؟';
  } else if (channel === 'hybrid') {
    promptMsg = 'هل تريد بالتأكيد بدء الحملة الهجينة (اتصال أولاً ومتابعة فورية بالواتساب) الآن؟';
  }

  if (!confirm(promptMsg)) {
    return;
  }

  try {
    const res = await fetch(`/api/crm/campaigns/${currentCampaignId}/start/`, {
      method: 'POST',
      headers: {
        'X-CSRFToken': getCookie('csrftoken')
      }
    });
    const data = await res.json();
    if (data.status === 'success') {
      if (typeof showToast === 'function') showToast(data.message, 'success');
      await onCampaignSelected(currentCampaignId);
    } else {
      alert(data.message || 'فشل بدء الحملة');
    }
  } catch (err) {
    console.error('Error starting campaign:', err);
    alert('حدث خطأ أثناء إطلاق الحملة: ' + err.message);
  }
}

async function pauseCurrentCampaign() {
  if (!currentCampaignId) return;

  try {
    const res = await fetch(`/api/crm/campaigns/${currentCampaignId}/pause/`, {
      method: 'POST',
      headers: {
        'X-CSRFToken': getCookie('csrftoken')
      }
    });
    const data = await res.json();
    if (data.status === 'success') {
      if (typeof showToast === 'function') showToast(data.message, 'info');
      await onCampaignSelected(currentCampaignId);
    } else {
      alert(data.message || 'فشل إيقاف الحملة');
    }
  } catch (err) {
    console.error('Error pausing campaign:', err);
    alert('حدث خطأ أثناء إيقاف الحملة: ' + err.message);
  }
}

async function resetCurrentCampaignContacts() {
  if (!currentCampaignId) return;
  if (!confirm('هل تريد إعادة تعيين كافة جهات الاتصال في هذه الحملة إلى حالة "في الانتظار" (Pending) وتصفير المحاولات والرسائل السابقة؟')) {
    return;
  }

  try {
    const res = await fetch(`/api/crm/campaigns/${currentCampaignId}/reset/`, {
      method: 'POST',
      headers: {
        'X-CSRFToken': getCookie('csrftoken')
      }
    });
    const data = await res.json();
    if (data.status === 'success') {
      if (typeof showToast === 'function') showToast(data.message, 'success');
      await onCampaignSelected(currentCampaignId);
    } else {
      alert(data.message || 'فشلت إعادة الضبط');
    }
  } catch (err) {
    console.error('Error resetting campaign contacts:', err);
    alert('حدث خطأ أثناء إعادة ضبط جهات الاتصال: ' + err.message);
  }
}

async function dialSingleContact(contactId) {
  if (!contactId) return;

  if (!hasActiveOutboundGateway) {
    if (typeof showToast === 'function') showToast('لا يمكن الاتصال: لا يوجد خط اتصال صادر (SIP Trunk) مفعل.', 'error');
    alert('تنبيه: لا يوجد خط صادر (SIP Trunk) مفعل لإجراء هذا الاتصال. يرجى إعداد خط صادر أولاً من تبويب "الربط الهاتفي والسنترال".');
    return;
  }

  try {
    const res = await fetch(`/api/crm/campaigns/contacts/${contactId}/dial/`, {
      method: 'POST',
      headers: {
        'X-CSRFToken': getCookie('csrftoken')
      }
    });
    const data = await res.json();
    if (data.status === 'success') {
      if (typeof showToast === 'function') showToast(data.message, 'success');
      setTimeout(() => {
        if (currentCampaignId) onCampaignSelected(currentCampaignId);
      }, 1500);
    } else {
      alert(data.message || 'تعذر إجراء المكالمة');
    }
  } catch (err) {
    console.error('Error dialing contact:', err);
    alert('حدث خطأ أثناء الاتصال: ' + err.message);
  }
}

async function sendSingleContactWhatsApp(contactId) {
  if (!contactId) return;

  if (!hasWhatsAppConnected) {
    if (typeof showToast === 'function') showToast('لا يمكن الإرسال: حساب الواتساب غير متصل في لوحة التحكم.', 'error');
    alert('تنبيه: حساب الواتساب غير متصل حالياً (Evolution API).\n\nيرجى التوجه إلى تبويب "الواتساب والذكاء الاصطناعي" ومسح كود الربط أولاً.');
    return;
  }

  try {
    const res = await fetch(`/api/crm/campaigns/contacts/${contactId}/whatsapp/`, {
      method: 'POST',
      headers: {
        'X-CSRFToken': getCookie('csrftoken')
      }
    });
    const data = await res.json();
    if (data.status === 'success') {
      if (typeof showToast === 'function') showToast(data.message, 'success');
      if (currentCampaignId) onCampaignSelected(currentCampaignId);
    } else {
      alert(data.message || 'فشل إرسال رسالة الواتساب');
    }
  } catch (err) {
    console.error('Error sending WhatsApp message:', err);
    alert('حدث خطأ أثناء إرسال الواتساب: ' + err.message);
  }
}

function exportCurrentCampaign(format = 'xlsx') {
  if (!currentCampaignId) {
    alert('يرجى اختيار حملة أولاً.');
    return;
  }
  const filter = currentContactFilter || 'all';
  const url = `/api/crm/campaigns/${currentCampaignId}/export/?format=${format}&filter=${filter}`;
  window.open(url, '_blank');
}

function filterCampaignContacts(status) {
  currentContactFilter = status;

  document.querySelectorAll('.camp-filter-btn').forEach(btn => {
    if (btn.getAttribute('data-filter') === status) {
      btn.className = 'camp-filter-btn px-3 py-1 rounded-xl bg-[#680E23] text-white font-semibold transition';
    } else {
      btn.className = 'camp-filter-btn px-3 py-1 rounded-xl bg-[#F5EFE6] text-[#6E645D] hover:bg-[#EAE3D9] font-semibold transition';
    }
  });

  if (currentCampaignId) {
    onCampaignSelected(currentCampaignId);
  }
}

function searchCampaignContacts(val) {
  currentContactSearch = val.trim();
  clearTimeout(campaignSearchDebounceTimer);
  campaignSearchDebounceTimer = setTimeout(() => {
    if (currentCampaignId) {
      onCampaignSelected(currentCampaignId);
    }
  }, 350);
}

function openContactDetailsModal(contactId) {
  const contact = currentCampaignContacts.find(c => c.id == contactId);
  if (!contact) return;

  const modal = document.getElementById('modal-contact-details');
  if (!modal) return;

  document.getElementById('contact-modal-name').innerText = contact.customer_name;
  document.getElementById('contact-modal-phone').innerText = contact.phone_number;

  const statusEl = document.getElementById('contact-modal-status');
  if (statusEl) statusEl.innerText = contact.call_status_display || contact.call_status;

  const waStatusEl = document.getElementById('contact-modal-wa-status');
  if (waStatusEl) waStatusEl.innerText = contact.whatsapp_status_display || contact.whatsapp_status;

  const interestEl = document.getElementById('contact-modal-interest');
  if (interestEl) {
    if (contact.interest_level === 'hot') interestEl.innerText = '🔥 مهتم جداً';
    else if (contact.interest_level === 'warm') interestEl.innerText = '🟡 للمتابعة';
    else if (contact.interest_level === 'cold') interestEl.innerText = '❄️ غير مهتم';
    else interestEl.innerText = 'لم يتحدد بعد';
  }

  const retriesEl = document.getElementById('contact-modal-retries');
  if (retriesEl) retriesEl.innerText = contact.retries_count || 0;

  // WhatsApp Box
  const waBox = document.getElementById('contact-modal-wa-box');
  const waTextEl = document.getElementById('contact-modal-wa-text');
  const waTimeEl = document.getElementById('contact-modal-wa-time');
  if (contact.whatsapp_message_text) {
    if (waBox) waBox.classList.remove('hidden');
    if (waTextEl) waTextEl.innerText = contact.whatsapp_message_text;
    if (waTimeEl) waTimeEl.innerText = contact.whatsapp_sent_at || '';
  } else {
    if (waBox) waBox.classList.add('hidden');
  }

  const summaryEl = document.getElementById('contact-modal-summary');
  if (summaryEl) summaryEl.innerText = contact.call_summary || 'لم تجرَ المكالمة بعد.';

  const insightsEl = document.getElementById('contact-modal-insights');
  if (insightsEl) {
    const ext = contact.extracted_data || {};
    if (ext.customer_intent || ext.key_answers || ext.action_required) {
      insightsEl.innerHTML = `
        <div><strong>🎯 نية العميل:</strong> ${escapeHtml(ext.customer_intent || '-')}</div>
        <div><strong>💡 الإجابات الرئيسية:</strong> ${escapeHtml(ext.key_answers || '-')}</div>
        <div><strong>📌 الإجراء المطلوب:</strong> ${escapeHtml(ext.action_required || '-')}</div>
      `;
    } else {
      insightsEl.innerHTML = '<span class="text-[#8C827A] italic">لا توجد استخلاصات ذكية بعد.</span>';
    }
  }

  const attrsEl = document.getElementById('contact-modal-attrs');
  if (attrsEl) {
    const attrs = contact.attributes || {};
    if (Object.keys(attrs).length > 0) {
      attrsEl.innerHTML = `
        <table class="w-full text-start text-[11px]">
          ${Object.entries(attrs).map(([k, v]) => `
            <tr class="border-b border-[#EAE3D9]/60">
              <td class="font-bold py-1 text-[#680E23] w-1/3">${escapeHtml(k)}</td>
              <td class="py-1 text-[#2D2825]">${escapeHtml(String(v))}</td>
            </tr>
          `).join('')}
        </table>
      `;
    } else {
      attrsEl.innerHTML = '<span class="text-[#8C827A] italic">لا توجد حقول إضافية.</span>';
    }
  }

  const dialBtn = document.getElementById('contact-modal-dial-btn');
  if (dialBtn) {
    dialBtn.onclick = () => {
      dialSingleContact(contact.id);
      closeContactModal();
    };
  }

  const waBtn = document.getElementById('contact-modal-wa-btn');
  if (waBtn) {
    waBtn.onclick = () => {
      sendSingleContactWhatsApp(contact.id);
      closeContactModal();
    };
  }

  modal.classList.remove('hidden');
}

function closeContactModal() {
  const modal = document.getElementById('modal-contact-details');
  if (modal) modal.classList.add('hidden');
}

document.addEventListener('DOMContentLoaded', () => {
  loadCampaignsList();
});
