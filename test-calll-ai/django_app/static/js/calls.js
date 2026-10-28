/**
 * Calls & CDR JavaScript Controller
 * Handles call detail records, audio streaming, MP3 download, and search filtering.
 */

let cachedCalls = [];
let currentCallsDatePreset = 'all';
let callsSearchTimeout = null;

async function loadCallsList() {
  const searchVal = (document.getElementById('filter-calls-search')?.value || '').trim();
  const dirVal = document.getElementById('filter-calls-direction')?.value || 'all';
  const durVal = document.getElementById('filter-calls-duration')?.value || 'all';

  const params = new URLSearchParams();
  if (searchVal) params.set('search', searchVal);
  if (dirVal && dirVal !== 'all') params.set('direction', dirVal);
  if (durVal && durVal !== 'all') params.set('duration', durVal);
  if (currentCallsDatePreset && currentCallsDatePreset !== 'all') {
    params.set('date_preset', currentCallsDatePreset);
  }

  const tbody = document.getElementById('calls-table-tbody');
  if (tbody && (!cachedCalls || cachedCalls.length === 0)) {
    tbody.innerHTML = `
      <tr>
        <td colspan="8" class="py-8 text-center text-slate-400">
          <span class="inline-block animate-spin mr-2">🔄</span> جاري تحميل سجل المكالمات...
        </td>
      </tr>
    `;
  }

  try {
    const res = await fetch('/api/crm/calls/?' + params.toString());
    const data = await res.json();
    if (data.status === 'success') {
      cachedCalls = data.calls || [];

      // Update stats banner
      const sTotal = document.getElementById('calls-stat-total');
      const sMins = document.getElementById('calls-stat-minutes');
      const sCost = document.getElementById('calls-stat-cost');
      const sSecs = document.getElementById('calls-stat-seconds');

      const minUnit = window.t ? window.t('minute_short', 'د') : 'د';
      const secUnit = window.t ? window.t('second_short', 'ث') : 'ث';
      if (sTotal) sTotal.innerText = data.stats.total_calls;
      if (sMins) sMins.innerText = `${data.stats.total_billed_minutes} ${minUnit}`;
      if (sCost) sCost.innerText = `$${data.stats.total_cost.toFixed(2)}`;
      if (sSecs) sSecs.innerText = `${data.stats.total_duration_seconds} ${secUnit}`;

      renderCallsTable(cachedCalls);
    }
  } catch (err) {
    console.error('Error loading calls list:', err);
    if (tbody) {
      const failMsg = window.t ? window.t('calls_load_failed', 'فشل تحميل سجل المكالمات. يرجى إعادة المحاولة.') : 'فشل تحميل سجل المكالمات. يرجى إعادة المحاولة.';
      tbody.innerHTML = `
        <tr>
          <td colspan="8" class="py-8 text-center text-rose-600">
            ${failMsg}
          </td>
        </tr>
      `;
    }
  }
}

function renderCallsTable(calls) {
  const tbody = document.getElementById('calls-table-tbody');
  if (!tbody) return;

  if (!calls || calls.length === 0) {
    const emptyMsg = window.t ? window.t('no_calls_found', 'لا توجد مكالمات تطابق معايير البحث والتصفية المحددة.') : 'لا توجد مكالمات تطابق معايير البحث والتصفية المحددة.';
    tbody.innerHTML = `
      <tr>
        <td colspan="8" class="py-8 text-center text-slate-400">
          ${emptyMsg}
        </td>
      </tr>
    `;
    return;
  }

  const badgeInbound = window.t ? window.t('badge_inbound', 'واردة') : 'واردة';
  const badgeOutAi = window.t ? window.t('badge_outbound_ai', 'صادرة AI') : 'صادرة AI';
  const badgeOutAgent = window.t ? window.t('badge_outbound_agent', 'صادرة موظف') : 'صادرة موظف';
  const badgeInternal = window.t ? window.t('badge_internal', 'داخلية (موظفين)') : 'داخلية (موظفين)';
  const badgeInternalTest = window.t ? window.t('badge_internal_test', 'اختبار داخلي') : 'اختبار داخلي';
  const badgeTransferred = window.t ? window.t('badge_transferred', 'محولة لموظف') : 'محولة لموظف';
  const minSuffix = window.t ? window.t('minute_suffix', 'دقيقة') : 'دقيقة';
  const btnDetails = window.t ? window.t('btn_details', 'التفاصيل') : 'التفاصيل';

  tbody.innerHTML = calls.map(c => {
    let dirBadge = '';
    if (c.is_internal_test || c.direction === 'internal_test') {
      const extLabel = c.caller_extension ? ` (${c.caller_extension})` : '';
      dirBadge = `<span class="px-2 py-0.5 rounded-md text-[10px] font-medium bg-purple-50 text-purple-700 border border-purple-200">${badgeInternalTest}${extLabel}</span>`;
    } else if (c.direction === 'internal_employee') {
      dirBadge = `<span class="px-2 py-0.5 rounded-md text-[10px] font-medium bg-indigo-50 text-indigo-700 border border-indigo-200">${badgeInternal}</span>`;
    } else if (c.direction === 'inbound') {
      dirBadge = `<span class="px-2 py-0.5 rounded-md text-[10px] font-medium bg-sky-50 text-sky-700 border border-sky-200">${badgeInbound}</span>`;
    } else if (c.direction === 'outbound_ai') {
      dirBadge = `<span class="px-2 py-0.5 rounded-md text-[10px] font-medium bg-slate-100 text-slate-700 border border-slate-200">${badgeOutAi}</span>`;
    } else {
      dirBadge = `<span class="px-2 py-0.5 rounded-md text-[10px] font-medium bg-amber-50 text-amber-700 border border-amber-200">${badgeOutAgent}</span>`;
    }

    const party = c.destination_phone || c.caller_phone || 'Web Dashboard';
    const isTransferred = !!c.transferred_recording_url;
    const m = Math.floor(c.duration_seconds / 60);
    const s = c.duration_seconds % 60;
    const durFormatted = `${m < 10 ? '0' : ''}${m}:${s < 10 ? '0' : ''}${s}`;

    return `
      <tr class="hover:bg-slate-50/60 transition">
        <td class="py-3 px-4 text-slate-500 font-mono text-[11px] whitespace-nowrap">${c.started_at}</td>
        <td class="py-3 px-4">
          ${dirBadge}
          ${isTransferred ? `<span class="mt-1 block px-2 py-0.5 rounded-md text-[9px] font-medium bg-purple-50 text-purple-700 border border-purple-200 w-fit">${badgeTransferred}</span>` : ''}
        </td>
        <td class="py-3 px-4 font-mono font-medium text-slate-900">${escapeHtml(party)}</td>
        <td class="py-3 px-4 text-slate-700 max-w-[130px] truncate" title="${escapeHtml(c.room_name)}">${escapeHtml(c.room_name)}</td>
        <td class="py-3 px-4 font-mono text-slate-500">${durFormatted}</td>
        <td class="py-3 px-4">
          <span class="px-2 py-0.5 rounded-md font-mono font-medium bg-slate-100 text-slate-700 border border-slate-200 text-[11px]">${c.billed_minutes || 0} ${minSuffix}</span>
        </td>
        <td class="py-3 px-4 font-mono font-medium text-emerald-700">$${(c.cost || 0).toFixed(2)}</td>
        <td class="py-3 px-4 whitespace-nowrap">
          <button type="button" onclick="openCallDetailModal(${c.id})" class="px-2.5 py-1 rounded-md bg-white hover:bg-slate-50 border border-slate-200 text-slate-700 text-xs font-medium transition inline-flex items-center gap-1 shadow-2xs">
            <span>${btnDetails}</span>
          </button>
          ${c.recording_url ? `
            <a href="${c.recording_url}" target="_blank" class="ms-1 px-2 py-1 rounded-md bg-emerald-50 hover:bg-emerald-100 border border-emerald-200 text-emerald-800 text-xs font-medium transition inline-flex items-center gap-1 shadow-2xs" title="استماع لتسجيل الـ AI">
              <span>AI</span>
            </a>
          ` : ''}
          ${c.transferred_recording_url ? `
            <a href="${c.transferred_recording_url}" target="_blank" class="ms-1 px-2 py-1 rounded-md bg-purple-50 hover:bg-purple-100 border border-purple-200 text-purple-800 text-xs font-medium transition inline-flex items-center gap-1 shadow-2xs" title="استماع لتسجيل الموظف البشري">
              <span>موظف</span>
            </a>
          ` : ''}
        </td>
      </tr>
    `;
  }).join('');
}

function debounceCallsFilter() {
  if (callsSearchTimeout) clearTimeout(callsSearchTimeout);
  callsSearchTimeout = setTimeout(loadCallsList, 300);
}

function setCallsTypeFilter(type) {
  const dirSel = document.getElementById('filter-calls-direction');
  if (dirSel) {
    if (type === 'all') dirSel.value = 'all';
    else if (type === 'ai') dirSel.value = 'ai';
    else if (type === 'internal') dirSel.value = 'internal';
  }
  document.querySelectorAll('.call-type-btn').forEach(b => {
    b.className = 'call-type-btn px-3 py-1.5 rounded-lg text-xs font-medium bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 transition';
  });
  const activeBtn = document.getElementById('btn-type-' + type);
  if (activeBtn) {
    activeBtn.className = 'call-type-btn px-3 py-1.5 rounded-lg text-xs font-semibold bg-[#eff8ff] border border-[#b2ddff] text-[#1f93ff] transition';
  }
  loadCallsList();
}

function setCallsDatePreset(preset) {
  currentCallsDatePreset = preset;
  document.querySelectorAll('.preset-date-btn').forEach(b => {
    b.className = 'preset-date-btn px-3 py-1 rounded-lg text-xs font-medium bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 transition';
  });
  const activeBtn = document.getElementById('btn-preset-' + preset);
  if (activeBtn) {
    activeBtn.className = 'preset-date-btn px-3 py-1 rounded-lg text-xs font-semibold bg-[#eff8ff] border border-[#b2ddff] text-[#1f93ff] transition';
  }
  loadCallsList();
}

function resetCallsFilter() {
  const sInp = document.getElementById('filter-calls-search');
  const dirSel = document.getElementById('filter-calls-direction');
  const durSel = document.getElementById('filter-calls-duration');
  if (sInp) sInp.value = '';
  if (dirSel) dirSel.value = 'all';
  if (durSel) durSel.value = 'all';
  setCallsTypeFilter('all');
  setCallsDatePreset('all');
}

function openCallDetailModal(callId) {
  const call = cachedCalls.find(c => c.id === callId);
  if (!call) return;

  const titleEl = document.getElementById('cdm-title');
  const subEl = document.getElementById('cdm-subtitle');
  const durEl = document.getElementById('cdm-duration');
  const bMinsEl = document.getElementById('cdm-billed-mins');
  const costEl = document.getElementById('cdm-cost');
  const dirEl = document.getElementById('cdm-direction');
  const sumEl = document.getElementById('cdm-summary');
  const trEl = document.getElementById('cdm-transcript');

  const m = Math.floor(call.duration_seconds / 60);
  const s = call.duration_seconds % 60;
  const durFormatted = `${m < 10 ? '0' : ''}${m}:${s < 10 ? '0' : ''}${s}`;

  if (titleEl) titleEl.innerText = `تفاصيل المكالمة: ${call.room_name}`;
  if (subEl) subEl.innerText = `التاريخ: ${call.started_at} | الطرف: ${call.destination_phone || call.caller_phone || 'Web'}`;
  if (durEl) durEl.innerText = durFormatted;
  if (bMinsEl) bMinsEl.innerText = `${call.billed_minutes || 0} دقيقة (Ceiling)`;
  if (costEl) costEl.innerText = `$${(call.cost || 0).toFixed(2)}`;
  if (dirEl) dirEl.innerText = call.direction_display || call.direction;
  if (sumEl) sumEl.innerText = call.summary || 'لا يوجد ملخص تراكمي مسجل لهذه المكالمة.';
  if (trEl) trEl.innerText = call.transcript_text || 'لا يوجد نص محادثة مفرغ.';

  const mBox = document.getElementById('call-detail-modal');
  if (mBox) mBox.classList.remove('hidden');

  // AI Recording
  const recSec = document.getElementById('cdm-recording-section');
  const audioEl = document.getElementById('cdm-audio-player');
  const dlBtn = document.getElementById('cdm-download-btn');
  if (call.recording_url) {
    if (audioEl) audioEl.src = call.recording_url;
    if (dlBtn) dlBtn.href = call.recording_url;
    if (recSec) recSec.classList.remove('hidden');
  } else {
    if (audioEl) { audioEl.pause(); audioEl.src = ''; }
    if (recSec) recSec.classList.add('hidden');
  }

  // Transferred Human Employee Recording
  const transRecSec = document.getElementById('cdm-transferred-recording-section');
  const transAudioEl = document.getElementById('cdm-transferred-audio-player');
  const transDlBtn = document.getElementById('cdm-transferred-download-btn');
  const transTitle = document.getElementById('cdm-transferred-title');
  if (call.transferred_recording_url) {
    if (transAudioEl) transAudioEl.src = call.transferred_recording_url;
    if (transDlBtn) transDlBtn.href = call.transferred_recording_url;
    if (transTitle && call.transferred_to_extension) {
      transTitle.innerText = `تسجيل محادثة الموظف البشري (${call.transferred_to_extension}):`;
    }
    if (transRecSec) transRecSec.classList.remove('hidden');
  } else {
    if (transAudioEl) { transAudioEl.pause(); transAudioEl.src = ''; }
    if (transRecSec) transRecSec.classList.add('hidden');
  }
}

function closeCallDetailModal() {
  const audioEl = document.getElementById('cdm-audio-player');
  if (audioEl) { audioEl.pause(); }
  const transAudioEl = document.getElementById('cdm-transferred-audio-player');
  if (transAudioEl) { transAudioEl.pause(); }
  const mBox = document.getElementById('call-detail-modal');
  if (mBox) mBox.classList.add('hidden');
}

document.addEventListener('DOMContentLoaded', () => {
  loadCallsList();
});

window.addEventListener('appLanguageChanged', () => {
  loadCallsList();
});
