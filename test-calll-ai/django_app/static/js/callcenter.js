/**
 * Call Center & Queues Management JavaScript
 * Handles employee extensions directory, queue groups routing, round-robin rules, and WebRTC softphone.
 */

let currentEmployees = [];
let currentCallQueues = [];
let dashboardLivekitRoom = null;
let dashboardAttachedAudio = null;
let dashboardCurrentRoomName = null;

function switchCallcenterSubtab(sub) {
  document.querySelectorAll('.callcenter-subtab-panel').forEach(el => el.classList.add('hidden'));
  document.querySelectorAll('.subtab-btn').forEach(btn => {
    btn.classList.remove('bg-white', 'text-slate-900', 'border', 'border-slate-200/80', 'shadow-2xs', 'font-medium', 'text-white', 'shadow-sm');
    btn.classList.add('text-slate-600', 'hover:text-slate-900', 'font-normal');
  });
  const target = document.getElementById('subtab-content-' + sub);
  if (target) target.classList.remove('hidden');
  const activeBtn = document.getElementById('subtab-btn-' + sub);
  if (activeBtn) {
    activeBtn.classList.remove('text-slate-600', 'hover:text-slate-900', 'font-normal');
    activeBtn.classList.add('bg-white', 'text-slate-900', 'border', 'border-slate-200/80', 'shadow-2xs', 'font-medium');
  }
  if (sub === 'recordings') {
    loadEmployeeCallLogs();
  }
}

async function loadEmployees() {
  const tbody = document.getElementById('employees-tbody');
  if (!tbody) return;
  try {
    const res = await fetch('/api/call-center/employees/');
    const data = await res.json();
    if (data.status !== 'success') return;

    currentEmployees = data.employees || [];
    populateEmployeeFilter();
    if (currentEmployees.length === 0) {
      const noEmpText = window.t ? window.t('cc_no_employees', 'لا يوجد موظفون مسجلون بعد في النظام.') : 'لا يوجد موظفون مسجلون بعد في النظام.';
      tbody.innerHTML = `
        <tr>
          <td colspan="6" class="text-center py-6 text-slate-500 text-xs">
            ${noEmpText}
          </td>
        </tr>
      `;
      return;
    }

    const readyText = window.t ? window.t('cc_status_ready', 'متاح (Ready)') : 'متاح (Ready)';
    const breakText = window.t ? window.t('cc_status_break', 'استراحة (Break)') : 'استراحة (Break)';
    const busyText = window.t ? window.t('cc_status_busy', 'مشغول (Busy)') : 'مشغول (Busy)';
    const offlineText = window.t ? window.t('cc_status_offline', 'غير متصل') : 'غير متصل';
    const sipDataLabel = window.t ? window.t('cc_sip_data', 'بيانات SIP') : 'بيانات SIP';
    const dialLabel = window.t ? window.t('cc_dial', 'اتصال') : 'اتصال';
    const generalDept = window.t ? window.t('general_dept', 'عام') : 'عام';

    const statusBadges = {
      'ready': `<span class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200"><span class="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>${readyText}</span>`,
      'break': `<span class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200"><span class="w-1.5 h-1.5 rounded-full bg-amber-500"></span>${breakText}</span>`,
      'busy': `<span class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-rose-50 text-rose-700 border border-rose-200"><span class="w-1.5 h-1.5 rounded-full bg-rose-500"></span>${busyText}</span>`,
      'offline': `<span class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-600 border border-slate-200">${offlineText}</span>`
    };

    tbody.innerHTML = currentEmployees.map(emp => `
      <tr class="hover:bg-slate-50/70 transition">
        <td class="py-3 px-3 font-medium text-slate-900 flex items-center gap-2">
          <span class="w-8 h-8 rounded-full bg-slate-100 border border-slate-200 text-slate-600 flex items-center justify-center text-xs font-medium shadow-2xs">
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            </svg>
          </span>
          <span>${escapeHtml(emp.display_name)}</span>
        </td>
        <td class="py-3 px-3 text-center">
          <span class="font-mono font-medium text-slate-900 bg-slate-50 border border-slate-200 px-2.5 py-1 rounded-lg text-sm shadow-2xs">
            ${escapeHtml(emp.extension)}
          </span>
        </td>
        <td class="py-3 px-3 text-slate-700 font-medium">${escapeHtml(emp.department || generalDept)}</td>
        <td class="py-3 px-3 text-center">
          ${statusBadges[emp.status] || statusBadges['offline']}
        </td>
        <td class="py-3 px-3">
          <span class="inline-flex items-center gap-1 text-xs text-emerald-800 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded-full font-mono font-medium">
            <span class="w-1.5 h-1.5 rounded-full bg-emerald-600 animate-pulse"></span> Wazo PJSIP
          </span>
        </td>
        <td class="py-3 px-3 text-center">
          <div class="flex items-center justify-center gap-1.5">
            <button 
              type="button" 
              onclick="openSipCredentialsModal(${emp.id})"
              class="px-2.5 py-1 rounded-lg bg-slate-50 hover:bg-slate-100 text-slate-700 border border-slate-200 text-xs font-medium transition inline-flex items-center gap-1 shadow-2xs"
              title="بيانات اتصال SIP للسوفت فون والهاتف المكتبي"
            >
              <span>${sipDataLabel}</span>
            </button>
            <button 
              type="button" 
              onclick="dialTargetFromDashboard('${escapeHtml(emp.extension)}', '${escapeHtml(emp.display_name)}')"
              class="px-2.5 py-1 rounded-lg bg-violet-50 hover:bg-violet-100 text-violet-700 border border-violet-200 text-xs font-medium transition inline-flex items-center gap-1 shadow-2xs"
              title="اتصال مباشر بالموظف عبر WebRTC"
            >
              <svg class="w-3 h-3 text-violet-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"/>
              </svg>
              <span>${dialLabel}</span>
            </button>
            <button 
              type="button" 
              onclick="deleteEmployee(${emp.id}, '${escapeHtml(emp.display_name)}')"
              class="p-1 rounded-lg hover:bg-rose-100 hover:text-rose-700 text-slate-400 transition"
              title="حذف الموظف"
            >
              <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </button>
          </div>
        </td>
      </tr>
    `).join('');
  } catch (err) {
    console.error('Error loading employees:', err);
  }
}

async function loadQueues() {
  const tbody = document.getElementById('queues-tbody');
  if (!tbody) return;
  try {
    const res = await fetch('/api/call-center/queues/');
    const data = await res.json();
    if (data.status !== 'success') return;

    currentCallQueues = data.queues || [];
    if (currentCallQueues.length === 0) {
      const noQueuesText = window.t ? window.t('cc_no_queues', 'لا توجد طوابير انتظار مسجلة بعد. اضغط "طابور جديد" لإنشاء طابور.') : 'لا توجد طوابير انتظار مسجلة بعد. اضغط "طابور جديد" لإنشاء طابور.';
      tbody.innerHTML = `
        <tr>
          <td colspan="6" class="text-center py-6 text-slate-500 text-xs">
            ${noQueuesText}
          </td>
        </tr>
      `;
      return;
    }

    const readyState = window.t ? window.t('presence_ready', 'متاح') : 'متاح';
    const ringingState = window.t ? window.t('presence_ringing', 'يرن...') : 'يرن...';
    const busyState = window.t ? window.t('presence_busy', 'مشغول') : 'مشغول';
    const extPrefix = window.t ? window.t('cc_ext_prefix', 'تحويلة') : 'تحويلة';
    const noMembersAssigned = window.t ? window.t('cc_no_members_assigned', 'لا يوجد موظفون مسندون') : 'لا يوجد موظفون مسندون';

    tbody.innerHTML = currentCallQueues.map(q => {
      const membersHtml = (q.members && q.members.length > 0)
        ? q.members.map(m => {
            let badgeColor = 'bg-slate-50 text-slate-700 border-slate-200';
            let dotColor = 'bg-emerald-500';
            let stateLabel = readyState;
            if (m.presence_state === 'RINGING') {
              badgeColor = 'bg-amber-50 text-amber-700 border-amber-200';
              dotColor = 'bg-amber-500 animate-ping';
              stateLabel = ringingState;
            } else if (m.presence_state === 'BUSY') {
              badgeColor = 'bg-rose-50 text-rose-700 border-rose-200';
              dotColor = 'bg-rose-500';
              stateLabel = busyState;
            }
            return `
              <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-medium ${badgeColor} border mr-1 mb-1 shadow-2xs">
                <span class="w-1.5 h-1.5 rounded-full ${dotColor}"></span>
                <span>${escapeHtml(m.sip_account_name || m.sip_username)}</span>
                <span class="text-slate-500 font-mono text-xs font-medium">[${extPrefix} ${escapeHtml(m.extension || '')}]</span>
                <span class="opacity-75 font-mono text-xs">(${stateLabel})</span>
              </span>
            `;
          }).join('')
        : `<span class="text-slate-400 text-xs">${noMembersAssigned}</span>`;

      const waitingBadge = q.waiting_calls_count > 0
        ? `<span class="px-2 py-0.5 rounded-full text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200 animate-pulse">${q.waiting_calls_count} مكالمة</span>`
        : `<span class="px-2 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-600 border border-slate-200">0</span>`;

      const strategyLabel = q.strategy === 'round_robin' 
        ? `رنين بالتناوب (${q.ring_timeout_seconds || 15}ث)` 
        : 'رنين متزامن للكل';

      return `
        <tr class="hover:bg-slate-50/70 transition">
          <td class="py-3 px-3">
            <span class="font-mono font-medium text-slate-900 bg-slate-50 px-2 py-1 rounded-lg border border-slate-200 text-sm shadow-2xs">
              ${escapeHtml(q.code)}
            </span>
          </td>
          <td class="py-3 px-3">
            <div class="font-semibold text-slate-900 flex items-center gap-1.5">
              <span>${escapeHtml(q.name)}</span>
            </div>
            <div class="text-xs text-slate-500 font-normal mt-0.5 max-w-xs leading-snug line-clamp-2" title="${escapeHtml(q.description || 'لا يوجد وصف')}">
              ${q.description ? `<span class="text-violet-700 font-medium">اختصاص المساعد:</span> ${escapeHtml(q.description)}` : `<span class="text-slate-400 italic">لم يُحدد وصف لاختصاص الطابور للـ AI</span>`}
            </div>
          </td>
          <td class="py-3 px-3 text-slate-700 font-mono text-xs">${strategyLabel}</td>
          <td class="py-3 px-3">
            <div class="flex flex-wrap items-center">${membersHtml}</div>
          </td>
          <td class="py-3 px-3 text-center">${waitingBadge}</td>
          <td class="py-3 px-3 text-center">
            <div class="flex items-center justify-center gap-1.5 flex-wrap">
              <button 
                type="button" 
                onclick="dialTargetFromDashboard('${escapeHtml(q.code)}', '${escapeHtml(q.name)}')"
                class="px-2.5 py-1 rounded-lg bg-violet-50 hover:bg-violet-100 text-violet-700 border border-violet-200 text-xs font-medium transition inline-flex items-center gap-1 shadow-2xs"
                title="اتصال وتجربة الطابور عبر WebRTC"
              >
                <svg class="w-3 h-3 text-violet-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"/>
                </svg>
                <span>اتصال</span>
              </button>
              <button 
                type="button" 
                onclick="openEditQueueModal('${q.id}', '${escapeHtml(q.name)}', '${escapeHtml(q.description || '')}')"
                class="px-2 py-1 rounded-lg bg-slate-50 hover:bg-slate-100 text-slate-700 border border-slate-200 text-xs font-medium transition inline-flex items-center gap-1 shadow-2xs"
                title="تعديل اختصاصات ووصف الطابور للذكاء الاصطناعي"
              >
                <svg class="w-3 h-3 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                </svg>
                <span>وصف التوجيه</span>
              </button>
              <button 
                type="button" 
                onclick="deleteQueue('${q.id}', '${escapeHtml(q.name)}')"
                class="p-1 rounded-lg hover:bg-rose-100 hover:text-rose-700 text-slate-400 transition"
                title="حذف الطابور"
              >
                <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              </button>
            </div>
          </td>
        </tr>
      `;
    }).join('');
  } catch (err) {
    console.error('Error loading call queues:', err);
  }
}

function openEditQueueModal(id, name, desc) {
  document.getElementById('edit-queue-id').value = id;
  document.getElementById('edit-queue-title-label').innerText = `طابور: ${name}`;
  document.getElementById('edit-queue-description').value = desc || '';
  document.getElementById('edit-queue-error').classList.add('hidden');
  document.getElementById('edit-queue-modal').classList.remove('hidden');
}

function closeEditQueueModal() {
  document.getElementById('edit-queue-modal').classList.add('hidden');
}

async function saveQueueDescription() {
  const id = document.getElementById('edit-queue-id').value;
  const desc = document.getElementById('edit-queue-description').value.trim();
  const btn = document.getElementById('btn-save-queue-desc');
  const errEl = document.getElementById('edit-queue-error');

  btn.disabled = true;
  btn.innerText = 'جاري الحفظ...';
  errEl.classList.add('hidden');

  try {
    const res = await fetch(`/api/call-center/queues/${id}/update/`, {
      method: 'POST',
      headers: {
        'X-CSRFToken': getCookie('csrftoken'),
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ description: desc })
    });
    const data = await res.json();
    if (data.status === 'success') {
      closeEditQueueModal();
      showToast('تم حفظ وصف الطابور بنجاح', 'success');
      await loadQueues();
    } else {
      errEl.innerText = data.message || 'فشل تحديث الوصف';
      errEl.classList.remove('hidden');
    }
  } catch (err) {
    errEl.innerText = 'حدث خطأ أثناء حفظ التعديلات.';
    errEl.classList.remove('hidden');
  } finally {
    btn.disabled = false;
    btn.innerText = 'حفظ التعديلات';
  }
}

function openNewQueueModal() {
  document.getElementById('new-queue-form').reset();
  document.getElementById('new-queue-error').classList.add('hidden');

  const membersListEl = document.getElementById('queue-members-list');
  if (currentEmployees && currentEmployees.length > 0) {
    membersListEl.innerHTML = currentEmployees.map(emp => `
      <label class="flex items-center gap-2 p-1.5 rounded-lg bg-slate-50 border border-slate-200 hover:bg-white cursor-pointer transition">
        <input type="checkbox" name="member_employee_ids" value="${emp.id}" class="rounded border-slate-300 text-[#7c3aed] focus:ring-[#7c3aed]">
        <span class="text-slate-800 font-medium">${escapeHtml(emp.display_name)}</span>
        <span class="font-mono text-slate-600 font-medium text-xs mr-1">[تحويلة: ${escapeHtml(emp.extension || '')}]</span>
        <span class="text-slate-500 text-xs">(${escapeHtml(emp.department || '')})</span>
      </label>
    `).join('');
  } else {
    membersListEl.innerHTML = `
      <span class="text-slate-400 text-xs">
        جاري مزامنة الموظفين من جدول التحويلات...
      </span>
    `;
  }

  document.getElementById('new-queue-modal').classList.remove('hidden');
}

function closeNewQueueModal() {
  document.getElementById('new-queue-modal').classList.add('hidden');
}

async function handleCreateQueue(e) {
  e.preventDefault();
  const btn = document.getElementById('btn-submit-queue');
  const errEl = document.getElementById('new-queue-error');
  const name = document.getElementById('queue-name').value.trim();
  const code = document.getElementById('queue-code').value.trim();
  const description = (document.getElementById('queue-description')?.value || '').trim();
  const strategy = document.getElementById('queue-strategy').value;
  const ringTimeout = document.getElementById('queue-ring-timeout').value;
  const totalTimeout = document.getElementById('queue-total-timeout').value;

  btn.disabled = true;
  btn.innerText = 'جاري إنشاء الطابور...';
  errEl.classList.add('hidden');

  const formData = new FormData();
  formData.append('name', name);
  formData.append('code', code);
  formData.append('description', description);
  formData.append('strategy', strategy);
  formData.append('ring_timeout_seconds', ringTimeout);
  formData.append('total_timeout_seconds', totalTimeout);

  const musicFile = document.getElementById('queue-hold-music').files[0];
  if (musicFile) {
    formData.append('hold_music', musicFile);
  }

  const checkedMembers = document.querySelectorAll('input[name="member_employee_ids"]:checked');
  checkedMembers.forEach(cb => {
    formData.append('member_ids', cb.value);
  });

  try {
    const res = await fetch('/api/call-center/queues/create/', {
      method: 'POST',
      headers: {
        'X-CSRFToken': getCookie('csrftoken')
      },
      body: formData
    });
    const data = await res.json();
    if (data.status === 'success') {
      closeNewQueueModal();
      showToast('تم إنشاء الطابور بنجاح!', 'success');
      await loadQueues();
    } else {
      errEl.innerText = data.message || 'فشل إنشاء الطابور';
      errEl.classList.remove('hidden');
    }
  } catch (err) {
    errEl.innerText = 'حدث خطأ أثناء الاتصال بالخادم.';
    errEl.classList.remove('hidden');
  } finally {
    btn.disabled = false;
    btn.innerText = 'حفظ الطابور وتفعيل الكود';
  }
}

async function deleteQueue(id, name) {
  if (!confirm(`هل أنت متأكد من حذف طابور "${name}"؟ سيتم إلغاء كود الطابور وتوجيه الاتصال.`)) return;
  try {
    const res = await fetch(`/api/call-center/queues/${id}/delete/`, {
      method: 'POST',
      headers: { 'X-CSRFToken': getCookie('csrftoken') }
    });
    const data = await res.json();
    if (data.status === 'success') {
      showToast('تم حذف الطابور بنجاح', 'success');
      await loadQueues();
    } else {
      showToast('فشل الحذف: ' + (data.message || ''), 'error');
    }
  } catch (err) {
    showToast('حدث خطأ أثناء حذف الطابور.', 'error');
  }
}

function openNewEmployeeModal() {
  const form = document.getElementById('new-employee-form');
  if (form) form.reset();
  const err = document.getElementById('new-employee-error');
  if (err) err.classList.add('hidden');
  const modal = document.getElementById('new-employee-modal');
  if (modal) modal.classList.remove('hidden');
}

function closeNewEmployeeModal() {
  const modal = document.getElementById('new-employee-modal');
  if (modal) modal.classList.add('hidden');
}

async function handleCreateEmployee(e) {
  e.preventDefault();
  const btn = document.getElementById('btn-submit-employee');
  const errEl = document.getElementById('new-employee-error');
  const name = document.getElementById('emp-name').value.trim();
  const ext = document.getElementById('emp-extension').value.trim();
  const dept = document.getElementById('emp-department').value.trim();
  const username = document.getElementById('emp-username').value.trim();
  const password = document.getElementById('emp-password').value.trim();

  btn.disabled = true;
  btn.innerText = 'جاري حفظ وإنشاء التحويلة...';
  errEl.classList.add('hidden');

  try {
    const res = await fetch('/api/call-center/employees/create/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken')
      },
      body: JSON.stringify({
        display_name: name,
        extension: ext,
        department: dept,
        username: username,
        password: password
      })
    });
    const data = await res.json();
    if (data.status === 'success') {
      closeNewEmployeeModal();
      showToast('تم إنشاء تحويلة الموظف بنجاح!', 'success');
      await loadEmployees();
      await loadQueues();
    } else {
      errEl.innerText = data.message || 'حدث خطأ أثناء إضافة الموظف';
      errEl.classList.remove('hidden');
    }
  } catch (err) {
    errEl.innerText = 'فشل الاتصال بالخادم.';
    errEl.classList.remove('hidden');
  } finally {
    btn.disabled = false;
    btn.innerText = 'حفظ وإنشاء التحويلة';
  }
}

async function deleteEmployee(id, name) {
  if (!confirm(`هل أنت متأكد من حذف الموظف "${name}" وإلغاء تحويلته؟`)) return;
  try {
    const res = await fetch(`/api/call-center/employees/${id}/delete/`, {
      method: 'POST',
      headers: { 'X-CSRFToken': getCookie('csrftoken') }
    });
    const data = await res.json();
    if (data.status === 'success') {
      showToast('تم حذف الموظف بنجاح', 'success');
      await loadEmployees();
      await loadQueues();
    } else {
      showToast('فشل الحذف: ' + (data.message || ''), 'error');
    }
  } catch (err) {
    showToast('حدث خطأ أثناء حذف الموظف.', 'error');
  }
}

async function dialTargetFromDashboard(target, targetName) {
  if (dashboardLivekitRoom) {
    alert('توجد مكالمة نشطة بالفعل في لوحة التحكم. يرجى إنهاؤها أولاً.');
    return;
  }

  const banner = document.getElementById('dashboard-active-call-banner');
  const callTitle = document.getElementById('dashboard-call-title');
  const callSub = document.getElementById('dashboard-call-sub');

  if (banner) banner.classList.remove('hidden');
  if (callTitle) callTitle.innerText = `جاري الاتصال بـ: ${targetName} [${target}]...`;
  if (callSub) callSub.innerText = 'يتم إنشاء غرفة WebRTC وتنبيه الموظفين عبر الشبكة الداخلية...';

  try {
    const res = await fetch('/api/call-center/calls/dial/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken')
      },
      body: JSON.stringify({ target: target })
    });
    const data = await res.json();

    if (data.status !== 'success') {
      alert(data.message || 'فشل بدء المكالمة');
      if (banner) banner.classList.add('hidden');
      return;
    }

    dashboardCurrentRoomName = data.room_name;
    const agentsInfo = (data.notified_agents !== undefined)
      ? `(تم تنبيه ${data.notified_agents} موظف متاح)`
      : '';

    if (callTitle) callTitle.innerText = `مكالمة جارية: ${data.target_name || targetName} [${data.target_number || target}]`;
    if (callSub) callSub.innerText = `متصل صوتياً ${agentsInfo} - بانتظار رد الموظف...`;

    if (typeof LivekitClient !== 'undefined') {
      dashboardLivekitRoom = new LivekitClient.Room({
        adaptiveStream: true,
        dynacast: true
      });

      dashboardLivekitRoom.on(LivekitClient.RoomEvent.ParticipantConnected, (p) => {
        if (callSub) callSub.innerText = `انضم للمكالمة: ${p.name || p.identity}`;
      });

      dashboardLivekitRoom.on(LivekitClient.RoomEvent.ParticipantDisconnected, (p) => {
        endDashboardCall();
      });

      dashboardLivekitRoom.on(LivekitClient.RoomEvent.TrackSubscribed, (track, publication, participant) => {
        if (track.kind === LivekitClient.Track.Kind.Audio) {
          if (dashboardAttachedAudio) dashboardAttachedAudio.remove();
          dashboardAttachedAudio = track.attach();
          document.body.appendChild(dashboardAttachedAudio);
        }
      });

      dashboardLivekitRoom.on(LivekitClient.RoomEvent.Disconnected, () => {
        if (banner) banner.classList.add('hidden');
        if (dashboardAttachedAudio) {
          dashboardAttachedAudio.remove();
          dashboardAttachedAudio = null;
        }
        dashboardLivekitRoom = null;
        dashboardCurrentRoomName = null;
      });

      await dashboardLivekitRoom.connect(data.livekit_url, data.livekit_token);
      await dashboardLivekitRoom.localParticipant.setMicrophoneEnabled(true, {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      });
    }

  } catch (err) {
    console.error('Failed to dial from dashboard:', err);
    alert('حدث خطأ في الاتصال عبر WebRTC: ' + err.message);
    if (banner) banner.classList.add('hidden');
    if (dashboardLivekitRoom) {
      dashboardLivekitRoom.disconnect();
      dashboardLivekitRoom = null;
    }
    dashboardCurrentRoomName = null;
  }
}

async function endDashboardCall() {
  const banner = document.getElementById('dashboard-active-call-banner');
  if (banner) banner.classList.add('hidden');

  const roomToClose = dashboardCurrentRoomName;

  if (dashboardLivekitRoom) {
    try {
      await dashboardLivekitRoom.disconnect();
    } catch (e) {
      console.error(e);
    }
    dashboardLivekitRoom = null;
  }

  if (dashboardAttachedAudio) {
    dashboardAttachedAudio.remove();
    dashboardAttachedAudio = null;
  }

  dashboardCurrentRoomName = null;

  try {
    await fetch('/api/call-center/calls/hangup/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken')
      },
      body: JSON.stringify({ room_name: roomToClose })
    });
  } catch (e) {
    // ignore
  }
}

// ── Call Logs & Recordings Management ──────────────────────────────────────────

let logSearchDebounceTimer = null;
function debounceLogSearch() {
  clearTimeout(logSearchDebounceTimer);
  logSearchDebounceTimer = setTimeout(() => {
    loadEmployeeCallLogs();
  }, 350);
}

function populateEmployeeFilter() {
  const select = document.getElementById('filter-log-employee');
  if (!select) return;
  const currentVal = select.value;
  let html = '<option value="">جميع الموظفين</option>';
  currentEmployees.forEach(emp => {
    html += `<option value="${emp.id}" ${currentVal == emp.id ? 'selected' : ''}>${escapeHtml(emp.display_name)} (${escapeHtml(emp.extension)})</option>`;
  });
  select.innerHTML = html;
}

function formatLogDuration(secs) {
  if (!secs || secs < 1) return '0 ث';
  if (secs < 60) return `${secs} ث`;
  const m = Math.floor(secs / 60);
  const s = secs % 60;
  if (m < 60) return s > 0 ? `${m} د ${s} ث` : `${m} د`;
  const h = Math.floor(m / 60);
  const remM = m % 60;
  return `${h} س ${remM} د`;
}

async function loadEmployeeCallLogs() {
  const tbody = document.getElementById('recordings-tbody');
  if (!tbody) return;

  const empSelect = document.getElementById('filter-log-employee');
  const typeSelect = document.getElementById('filter-log-type');
  const recSelect = document.getElementById('filter-log-recording');
  const searchInput = document.getElementById('filter-log-search');

  const params = new URLSearchParams();
  if (empSelect && empSelect.value) params.set('employee_id', empSelect.value);
  if (typeSelect && typeSelect.value) params.set('call_type', typeSelect.value);
  if (recSelect && recSelect.value) params.set('has_recording', recSelect.value);
  if (searchInput && searchInput.value.trim()) params.set('search', searchInput.value.trim());

  try {
    const res = await fetch(`/api/call-center/calls/logs/?${params.toString()}`);
    const data = await res.json();
    if (data.status !== 'success') {
      tbody.innerHTML = `<tr><td colspan="6" class="text-center py-6 text-rose-500">حدث خطأ في تحميل السجل: ${escapeHtml(data.message || '')}</td></tr>`;
      return;
    }

    const logs = data.logs || [];

    // Calculate Summary Stats
    const totalCalls = logs.length;
    let recordedCalls = 0;
    let totalSecs = 0;
    let missedCalls = 0;

    logs.forEach(l => {
      if (l.recording_url) recordedCalls++;
      totalSecs += (l.duration_secs || 0);
      if (l.call_type === 'missed') missedCalls++;
    });

    const statTotalEl = document.getElementById('stat-total-calls');
    const statRecEl = document.getElementById('stat-recorded-calls');
    const statDurEl = document.getElementById('stat-total-duration');
    const statMissEl = document.getElementById('stat-missed-calls');

    if (statTotalEl) statTotalEl.innerText = totalCalls;
    if (statRecEl) statRecEl.innerText = recordedCalls;
    if (statDurEl) statDurEl.innerText = formatLogDuration(totalSecs);
    if (statMissEl) statMissEl.innerText = missedCalls;

    if (logs.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="6" class="text-center py-8 text-slate-500">
            لا توجد مكالمات تطابق معايير البحث الحالية.
          </td>
        </tr>
      `;
      return;
    }

    const typeBadges = {
      'inbound': '<span class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">واردة</span>',
      'outbound': '<span class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-violet-50 text-violet-700 border border-violet-200">صادرة</span>',
      'missed': '<span class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-rose-50 text-rose-700 border border-rose-200">فائتة</span>',
      'transfer': '<span class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200">محولة</span>'
    };

    tbody.innerHTML = logs.map(log => {
      const typeBadge = typeBadges[log.call_type] || `<span class="px-2 py-0.5 rounded bg-slate-100 text-slate-700">${escapeHtml(log.call_type)}</span>`;
      
      let recordingCell = '';
      if (log.recording_url) {
        const isWav = log.recording_url && log.recording_url.endsWith('.wav');
        const dlExt = isWav ? 'wav' : 'mp3';
        recordingCell = `
          <div class="flex items-center justify-center gap-2">
            <audio controls preload="none" class="h-8 max-w-[210px]" style="filter: drop-shadow(0 1px 2px rgba(0,0,0,0.05));">
              <source src="${escapeHtml(log.recording_url)}" type="${isWav ? 'audio/wav' : 'audio/mpeg'}">
              <source src="${escapeHtml(log.recording_url)}">
              متصفحك لا يدعم مشغل الصوت.
            </audio>
            <a 
              href="${escapeHtml(log.recording_url)}" 
              download="recording_${log.id}.${dlExt}" 
              target="_blank" 
              class="p-1.5 rounded-lg bg-slate-50 hover:bg-slate-100 border border-slate-200 text-slate-700 transition flex items-center justify-center shadow-2xs"
              title="تحميل ملف التسجيل الصوتي"
            >
              <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
            </a>
          </div>
        `;
      } else if (log.call_type === 'missed') {
        recordingCell = '<span class="text-rose-600 text-xs font-medium">مكالمة لم يُرد عليها</span>';
      } else {
        recordingCell = '<span class="text-slate-400 text-xs">غير مسجلة</span>';
      }

      return `
        <tr class="hover:bg-slate-50/60 transition">
          <td class="py-3 px-3">
            <div class="flex items-center gap-2">
              <span class="w-7 h-7 rounded-full bg-slate-100 border border-slate-200 text-slate-600 flex items-center justify-center text-xs font-medium shadow-2xs">
                <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                </svg>
              </span>
              <div>
                <div class="font-medium text-slate-900">${escapeHtml(log.employee_name || 'موظف')}</div>
                <div class="text-xs text-slate-500 font-mono font-medium">#${escapeHtml(log.employee_ext || '')} ${log.employee_department ? '· ' + escapeHtml(log.employee_department) : ''}</div>
              </div>
            </div>
          </td>
          <td class="py-3 px-3 font-medium text-slate-800">
            <div class="flex items-center gap-1.5">
              <svg class="w-3.5 h-3.5 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"/>
              </svg>
              <span>${escapeHtml(log.other_party || 'غير محدد')}</span>
              ${log.extension && log.extension !== log.other_party ? `<span class="text-xs text-slate-400 font-mono">(${escapeHtml(log.extension)})</span>` : ''}
            </div>
          </td>
          <td class="py-3 px-3 text-center">
            ${typeBadge}
          </td>
          <td class="py-3 px-3 text-slate-600 font-mono text-xs">
            ${escapeHtml(log.started_at || '')}
          </td>
          <td class="py-3 px-3 text-center font-mono font-medium text-slate-900">
            ${formatLogDuration(log.duration_secs)}
          </td>
          <td class="py-3 px-3 text-center">
            ${recordingCell}
          </td>
        </tr>
      `;
    }).join('');

  } catch (err) {
    console.error('Error loading employee call logs:', err);
    tbody.innerHTML = `<tr><td colspan="6" class="text-center py-6 text-rose-500">فشل الاتصال بالخادم لجلب السجلات.</td></tr>`;
  }
}

function openSipCredentialsModal(empId) {
  const emp = currentEmployees.find(e => e.id === empId);
  if (!emp) return;

  const modal = document.getElementById('sip-credentials-modal');
  if (!modal) return;

  const creds = emp.sip_credentials || {};
  document.getElementById('sip-modal-name').textContent = emp.display_name || 'الموظف';
  document.getElementById('sip-modal-ext').textContent = emp.extension || '';
  let srvHost = creds.host || emp.sip_host;
  if (!srvHost || srvHost === 'asterisk' || srvHost === '127.0.0.1' || srvHost === 'localhost') {
    srvHost = '169.58.32.179';
  }
  document.getElementById('sip-modal-server').value = srvHost;
  document.getElementById('sip-modal-port').value = creds.port || emp.sip_port || 5070;
  document.getElementById('sip-modal-username').value = creds.username || emp.sip_username || ('emp' + emp.extension);
  document.getElementById('sip-modal-password').value = creds.password || emp.sip_password || '********';

  modal.classList.remove('hidden');
}

function closeSipCredentialsModal() {
  const modal = document.getElementById('sip-credentials-modal');
  if (modal) modal.classList.add('hidden');
}

function copyToClipboard(elementId) {
  const input = document.getElementById(elementId);
  if (!input) return;
  input.select();
  input.setSelectionRange(0, 99999);
  navigator.clipboard.writeText(input.value).then(() => {
    const origBg = input.style.backgroundColor;
    input.style.backgroundColor = '#E8F5E9';
    setTimeout(() => {
      input.style.backgroundColor = origBg;
    }, 600);
  }).catch(err => {
    console.error('Failed to copy text: ', err);
  });
}

document.addEventListener('DOMContentLoaded', () => {
  loadEmployees();
  loadQueues();
  loadEmployeeCallLogs();
  setInterval(loadQueues, 8000);
  setInterval(loadEmployees, 8000);
});

window.addEventListener('appLanguageChanged', () => {
  loadEmployees();
  loadQueues();
});


