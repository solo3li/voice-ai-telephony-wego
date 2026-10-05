/**
 * Business Hours & Off-Hours Schedule JavaScript
 * Manages weekly schedule table, timezone calculation, audio preview, and settings persistence.
 */

const DAYS_ORDER = [
  { key: 'saturday', label: 'السبت' },
  { key: 'sunday', label: 'الأحد' },
  { key: 'monday', label: 'الاثنين' },
  { key: 'tuesday', label: 'الثلاثاء' },
  { key: 'wednesday', label: 'الأربعاء' },
  { key: 'thursday', label: 'الخميس' },
  { key: 'friday', label: 'الجمعة' },
];

let currentSchedule = null;
let selectedAudioFile = null;

const DEFAULT_AI_MSG = "مرحباً بك، نتأسف لاتصالك خارج أوقات العمل الرسمية. نسعد بتواصلك معنا مجدداً خلال أوقات العمل الرسمية من التاسعة صباحاً وحتى الخامسة مساءً.";

async function loadBusinessHours() {
  try {
    const res = await fetch('/api/business-hours/');
    const data = await res.json();
    if (data.status === 'success') {
      currentSchedule = data.schedule;
      populateScheduleForm(currentSchedule);
    }
  } catch (err) {
    console.error('Error loading business hours:', err);
    showToast('حدث خطأ أثناء تحميل مواعيد العمل', 'error');
  }
}

function populateScheduleForm(sched) {
  if (!sched) return;

  // Master switch
  const masterSwitch = document.getElementById('master-enable-schedule');
  const masterLabel = document.getElementById('master-enable-label');
  if (masterSwitch) {
    masterSwitch.checked = Boolean(sched.is_enabled);
    if (masterLabel) {
      masterLabel.innerText = sched.is_enabled ? 'مفعل' : 'معطل';
      masterLabel.className = sched.is_enabled ? 'text-xs font-bold text-[#680E23]' : 'text-xs font-bold text-[#443D39]';
    }
  }

  // Timezone
  const tzSelect = document.getElementById('field-timezone');
  if (tzSelect && sched.timezone) {
    tzSelect.value = sched.timezone;
  }

  // Days table
  renderDaysTable(sched.days_config || {});

  // Action type
  const actionType = sched.action_type || 'ai_message';
  const radioAi = document.getElementById('action-ai-message');
  const radioAudio = document.getElementById('action-audio-file');
  if (actionType === 'audio_file' && radioAudio) {
    radioAudio.checked = true;
  } else if (radioAi) {
    radioAi.checked = true;
  }
  switchActionType(actionType);

  // AI Message
  const aiMsgField = document.getElementById('field-ai-message');
  if (aiMsgField) {
    aiMsgField.value = sched.ai_message || DEFAULT_AI_MSG;
  }

  // Audio preview
  const audioPreview = document.getElementById('audio-preview-container');
  const audioPlayer = document.getElementById('audio-player-preview');
  if (sched.audio_file_url) {
    if (audioPlayer) audioPlayer.src = sched.audio_file_url;
    if (audioPreview) audioPreview.classList.remove('hidden');
    const fileNameEl = document.getElementById('audio-file-name');
    if (fileNameEl) fileNameEl.innerText = 'ملف صوتي معتمد مسجل مسبقاً (مرفوع)';
  }

  // Update status badge
  updateStatusBadge(sched.is_enabled, sched.is_open_now);
}

function updateStatusBadge(isEnabled, isOpenNow) {
  const badge = document.getElementById('current-status-badge');
  if (!badge) return;

  if (!isEnabled) {
    badge.innerHTML = `
      <span class="w-2 h-2 rounded-full bg-gray-400"></span>
      <span class="text-gray-600">الجدول غير مفعل (المساعد يستقبل دائماً)</span>
    `;
    return;
  }

  if (isOpenNow) {
    badge.innerHTML = `
      <span class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
      <span class="text-emerald-700">مفتوح الآن لاستقبال المكالمات 🟢</span>
    `;
  } else {
    badge.innerHTML = `
      <span class="w-2 h-2 rounded-full bg-rose-500"></span>
      <span class="text-rose-700">مغلق حالياً (الرد الآلي مفعل) 🔴</span>
    `;
  }
}

function renderDaysTable(config) {
  const tbody = document.getElementById('days-table-body');
  if (!tbody) return;

  tbody.innerHTML = DAYS_ORDER.map(d => {
    const dayData = config[d.key] || {
      is_workday: d.key !== 'friday',
      start_time: '09:00',
      end_time: '17:00'
    };

    const isWorkday = Boolean(dayData.is_workday);
    const startVal = dayData.start_time || '09:00';
    const endVal = dayData.end_time || '17:00';

    return `
      <tr class="hover:bg-[#FAF7F2]/60 transition py-2" id="row-day-${d.key}">
        <td class="py-2.5 font-bold text-[#1C1917]">${d.label}</td>
        <td class="py-2.5 text-center">
          <label class="inline-flex items-center cursor-pointer gap-2">
            <input type="checkbox" id="check-workday-${d.key}" onchange="toggleDayWorkday('${d.key}')" ${isWorkday ? 'checked' : ''} class="w-4 h-4 text-[#680E23] rounded accent-[#680E23] cursor-pointer">
            <span class="text-xs ${isWorkday ? 'text-[#1C1917] font-semibold' : 'text-[#8C827A]'}" id="label-workday-${d.key}">
              ${isWorkday ? 'يوم عمل' : 'عطلة'}
            </span>
          </label>
        </td>
        <td class="py-2.5 text-center">
          <input type="time" id="start-time-${d.key}" value="${startVal}" ${!isWorkday ? 'disabled' : ''} class="px-2 py-1 bg-white border border-[#DDD5C7] rounded-lg text-xs text-[#1C1917] font-mono focus:outline-none focus:border-[#680E23] disabled:opacity-40 disabled:bg-gray-100">
        </td>
        <td class="py-2.5 text-center">
          <input type="time" id="end-time-${d.key}" value="${endVal}" ${!isWorkday ? 'disabled' : ''} class="px-2 py-1 bg-white border border-[#DDD5C7] rounded-lg text-xs text-[#1C1917] font-mono focus:outline-none focus:border-[#680E23] disabled:opacity-40 disabled:bg-gray-100">
        </td>
        <td class="py-2.5 text-center">
          <span id="badge-day-${d.key}" class="px-2 py-0.5 rounded-full text-[10px] font-bold ${isWorkday ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-rose-50 text-rose-700 border border-rose-200'}">
            ${isWorkday ? 'دوام رسمي' : 'عطلة رسمية'}
          </span>
        </td>
      </tr>
    `;
  }).join('');
}

function toggleDayWorkday(dayKey) {
  const check = document.getElementById(`check-workday-${dayKey}`);
  const label = document.getElementById(`label-workday-${dayKey}`);
  const startInput = document.getElementById(`start-time-${dayKey}`);
  const endInput = document.getElementById(`end-time-${dayKey}`);
  const badge = document.getElementById(`badge-day-${dayKey}`);

  const isWorkday = check ? check.checked : false;

  if (label) {
    label.innerText = isWorkday ? 'يوم عمل' : 'عطلة';
    label.className = isWorkday ? 'text-xs text-[#1C1917] font-semibold' : 'text-xs text-[#8C827A]';
  }

  if (startInput) startInput.disabled = !isWorkday;
  if (endInput) endInput.disabled = !isWorkday;

  if (badge) {
    badge.innerText = isWorkday ? 'دوام رسمي' : 'عطلة رسمية';
    badge.className = `px-2 py-0.5 rounded-full text-[10px] font-bold ${isWorkday ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-rose-50 text-rose-700 border border-rose-200'}`;
  }
}

function toggleScheduleActive() {
  const masterSwitch = document.getElementById('master-enable-schedule');
  const masterLabel = document.getElementById('master-enable-label');
  const isChecked = masterSwitch ? masterSwitch.checked : false;

  if (masterLabel) {
    masterLabel.innerText = isChecked ? 'مفعل' : 'معطل';
    masterLabel.className = isChecked ? 'text-xs font-bold text-[#680E23]' : 'text-xs font-bold text-[#443D39]';
  }

  if (currentSchedule) {
    currentSchedule.is_enabled = isChecked;
    updateStatusBadge(isChecked, currentSchedule.is_open_now);
  }
}

function switchActionType(type) {
  const secAi = document.getElementById('section-ai-message');
  const secAudio = document.getElementById('section-audio-file');

  if (type === 'audio_file') {
    if (secAi) secAi.classList.add('hidden');
    if (secAudio) secAudio.classList.remove('hidden');
  } else {
    if (secAi) secAi.classList.remove('hidden');
    if (secAudio) secAudio.classList.add('hidden');
  }
}

function resetDefaultAiMessage() {
  const field = document.getElementById('field-ai-message');
  if (field) {
    field.value = DEFAULT_AI_MSG;
  }
}

function handleAudioFileSelect(e) {
  const file = e.target.files[0];
  if (!file) return;

  selectedAudioFile = file;
  const fileNameEl = document.getElementById('audio-file-name');
  if (fileNameEl) {
    fileNameEl.innerText = `الملف المختار: ${file.name} (${(file.size / 1024 / 1024).toFixed(2)} MB)`;
  }

  const audioPreview = document.getElementById('audio-preview-container');
  const audioPlayer = document.getElementById('audio-player-preview');
  if (audioPlayer) {
    audioPlayer.src = URL.createObjectURL(file);
    if (audioPreview) audioPreview.classList.remove('hidden');
  }
}

async function saveBusinessHoursSchedule() {
  const btn = document.getElementById('btn-save-schedule');
  const statusMsg = document.getElementById('save-status-msg');

  if (btn) {
    btn.disabled = true;
    btn.innerText = 'جاري الحفظ...';
  }

  // 1. Collect Days Config
  const daysConfig = {};
  DAYS_ORDER.forEach(d => {
    const isWorkday = document.getElementById(`check-workday-${d.key}`)?.checked ?? false;
    const startTime = document.getElementById(`start-time-${d.key}`)?.value || '09:00';
    const endTime = document.getElementById(`end-time-${d.key}`)?.value || '17:00';
    daysConfig[d.key] = {
      is_workday: isWorkday,
      start_time: startTime,
      end_time: endTime
    };
  });

  const masterEnabled = document.getElementById('master-enable-schedule')?.checked ?? false;
  const timezone = document.getElementById('field-timezone')?.value || 'Africa/Cairo';
  const actionType = document.querySelector('input[name="action_type"]:checked')?.value || 'ai_message';
  const aiMessage = document.getElementById('field-ai-message')?.value?.trim() || DEFAULT_AI_MSG;

  const csrfToken = getCookie('csrftoken');

  try {
    let res;
    if (selectedAudioFile) {
      // Use FormData for multipart audio upload
      const formData = new FormData();
      formData.append('is_enabled', masterEnabled);
      formData.append('timezone', timezone);
      formData.append('days_config', JSON.stringify(daysConfig));
      formData.append('action_type', actionType);
      formData.append('ai_message', aiMessage);
      formData.append('audio_file', selectedAudioFile);

      res = await fetch('/api/business-hours/save/', {
        method: 'POST',
        headers: { 'X-CSRFToken': csrfToken },
        body: formData
      });
    } else {
      // Use JSON
      res = await fetch('/api/business-hours/save/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({
          is_enabled: masterEnabled,
          timezone,
          days_config: daysConfig,
          action_type: actionType,
          ai_message: aiMessage
        })
      });
    }

    const data = await res.json();
    if (data.status === 'success') {
      currentSchedule = data.schedule;
      selectedAudioFile = null;
      updateStatusBadge(currentSchedule.is_enabled, currentSchedule.is_open_now);
      showToast('تم حفظ وتطبيق جدول مواعيد العمل بنجاح!', 'success');
      if (statusMsg) {
        statusMsg.innerText = 'تم الحفظ وتطبيق الإعدادات على المكالمات فوراً.';
        statusMsg.className = 'text-xs text-emerald-700 font-semibold';
      }
    } else {
      showToast(data.message || 'فشل حفظ الإعدادات', 'error');
    }
  } catch (err) {
    console.error('Error saving business hours:', err);
    showToast('حدث خطأ في الاتصال بالخادم', 'error');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `
        <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
        </svg>
        <span>حفظ وتطبيق مواعيد العمل</span>
      `;
    }
  }
}

document.addEventListener('DOMContentLoaded', () => {
  loadBusinessHours();
});
