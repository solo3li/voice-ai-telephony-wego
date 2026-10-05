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
        <td colspan="8" class="py-8 text-center text-[#8C827A]">
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

      if (sTotal) sTotal.innerText = data.stats.total_calls;
      if (sMins) sMins.innerText = `${data.stats.total_billed_minutes} د`;
      if (sCost) sCost.innerText = `$${data.stats.total_cost.toFixed(2)}`;
      if (sSecs) sSecs.innerText = `${data.stats.total_duration_seconds} ث`;

      renderCallsTable(cachedCalls);
    }
  } catch (err) {
    console.error('Error loading calls list:', err);
    if (tbody) {
      tbody.innerHTML = `
        <tr>
          <td colspan="8" class="py-8 text-center text-rose-600">
            فشل تحميل سجل المكالمات. يرجى إعادة المحاولة.
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
    tbody.innerHTML = `
      <tr>
        <td colspan="8" class="py-8 text-center text-[#8C827A]">
          لا توجد مكالمات تطابق معايير البحث والتصفية المحددة.
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = calls.map(c => {
    let dirBadge = '';
    if (c.direction === 'inbound') {
      dirBadge = `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-sky-100 text-sky-800 border border-sky-300">📥 واردة</span>`;
    } else if (c.direction === 'outbound_ai') {
      dirBadge = `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-[#FAF0F2] text-[#680E23] border border-[#E8CCD2]">🤖 صادرة AI</span>`;
    } else {
      dirBadge = `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-800 border border-amber-300">👤 صادرة موظف</span>`;
    }

    const party = c.destination_phone || c.caller_phone || 'Web Dashboard';
    const m = Math.floor(c.duration_seconds / 60);
    const s = c.duration_seconds % 60;
    const durFormatted = `${m < 10 ? '0' : ''}${m}:${s < 10 ? '0' : ''}${s}`;

    return `
      <tr class="hover:bg-[#F5EFE6]/50 transition">
        <td class="py-3 px-4 text-[#6E645D] font-mono text-[11px] whitespace-nowrap">${c.started_at}</td>
        <td class="py-3 px-4">${dirBadge}</td>
        <td class="py-3 px-4 font-mono font-bold text-[#1C1917]">${escapeHtml(party)}</td>
        <td class="py-3 px-4 text-[#443D39] max-w-[130px] truncate" title="${escapeHtml(c.room_name)}">${escapeHtml(c.room_name)}</td>
        <td class="py-3 px-4 font-mono text-[#6E645D]">${durFormatted}</td>
        <td class="py-3 px-4">
          <span class="px-2 py-0.5 rounded-md font-mono font-bold bg-[#FAF0F2] text-[#680E23] border border-[#E8CCD2] text-[11px]">${c.billed_minutes || 0} دقيقة</span>
        </td>
        <td class="py-3 px-4 font-mono font-bold text-emerald-700">$${(c.cost || 0).toFixed(2)}</td>
        <td class="py-3 px-4 whitespace-nowrap">
          <button type="button" onclick="openCallDetailModal(${c.id})" class="px-2.5 py-1 rounded-lg bg-[#FAF7F2] hover:bg-[#F5EFE6] border border-[#DDD5C7] text-[#680E23] text-xs font-semibold transition inline-flex items-center gap-1 shadow-sm">
            <span>👁️ التفاصيل</span>
          </button>
          ${c.recording_url ? `
            <a href="${c.recording_url}" target="_blank" class="ms-1 px-2 py-1 rounded-lg bg-emerald-50 hover:bg-emerald-100 border border-emerald-200 text-emerald-800 text-xs font-bold transition inline-flex items-center gap-1 shadow-sm" title="استماع للتسجيل">
              <span>▶️</span> <span>تسجيل</span>
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

function setCallsDatePreset(preset) {
  currentCallsDatePreset = preset;
  document.querySelectorAll('.preset-date-btn').forEach(b => {
    b.className = 'preset-date-btn px-3 py-1 rounded-lg text-xs font-semibold bg-[#FAF7F2] border border-[#DDD5C7] text-[#443D39] hover:bg-[#F5EFE6] transition';
  });
  const activeBtn = document.getElementById('btn-preset-' + preset);
  if (activeBtn) {
    activeBtn.className = 'preset-date-btn px-3 py-1 rounded-lg text-xs font-semibold bg-[#680E23] text-white transition';
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
}

function closeCallDetailModal() {
  const audioEl = document.getElementById('cdm-audio-player');
  if (audioEl) { audioEl.pause(); }
  const mBox = document.getElementById('call-detail-modal');
  if (mBox) mBox.classList.add('hidden');
}

document.addEventListener('DOMContentLoaded', () => {
  loadCallsList();
});
