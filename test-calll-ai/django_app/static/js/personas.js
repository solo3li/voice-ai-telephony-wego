/**
 * Personas & Voices Studio JavaScript
 * Handles persona profiles catalog, voice preview, dialect customization, and Google voices sync.
 */

let userProfiles = [];
let activeProfile = null;
let googleVoices = [];
let availableLanguages = [];
let languageDialectsMap = {};

let profileSelect = null;
let fieldGender = null;
let fieldLanguage = null;
let fieldDialect = null;
let fieldVoice = null;
let fieldRole = null;
let fieldStyle = null;
let fieldVerbosity = null;
let fieldWelcome = null;
let fieldWelcomeEnabled = null;
let welcomeToggleStatus = null;
let fieldCustom = null;
let fieldOffTopic = null;
let voiceTagBadge = null;
let profileStatusMsg = null;

let profileModal = null;
let newProfVoice = null;
let newProfGender = null;
let newProfLanguage = null;
let newProfDialect = null;
let newProfVerbosity = null;
let newProfWelcome = null;
let newProfWelcomeEnabled = null;
let newProfOffTopic = null;

function toggleWelcomeInput(target) {
  if (target === 'active') {
    const isChecked = fieldWelcomeEnabled ? fieldWelcomeEnabled.checked : true;
    if (welcomeToggleStatus) {
      welcomeToggleStatus.innerText = isChecked ? 'مفعلة' : 'معطلة';
      welcomeToggleStatus.className = isChecked ? 'ms-2 text-xs font-semibold text-[#680E23]' : 'ms-2 text-xs font-semibold text-[#8C827A]';
    }
    if (fieldWelcome) {
      fieldWelcome.disabled = !isChecked;
      fieldWelcome.classList.toggle('opacity-50', !isChecked);
    }
  } else {
    const isChecked = newProfWelcomeEnabled ? newProfWelcomeEnabled.checked : true;
    if (newProfWelcome) {
      newProfWelcome.disabled = !isChecked;
      newProfWelcome.classList.toggle('opacity-50', !isChecked);
    }
  }
}

async function loadProfiles() {
  try {
    const res = await fetch('/api/agents/profiles/');
    const data = await res.json();
    if (data.status === 'success') {
      userProfiles = data.profiles;
      activeProfile = data.active_profile;
      googleVoices = data.google_voices;
      availableLanguages = data.languages || [];
      languageDialectsMap = data.language_dialects_map || {};

      renderProfileDropdown();
      renderProfileCards();
      syncGenderVoiceOptions();
      if (activeProfile) {
        populateProfileForm(activeProfile);
      }
    }
  } catch (err) {
    console.error('Error loading profiles:', err);
  }
}

function renderProfileCards() {
  const container = document.getElementById('personas-cards-grid');
  if (!container) return;

  if (!userProfiles || userProfiles.length === 0) {
    container.innerHTML = `
      <div class="col-span-2 text-center py-10 bg-white rounded-3xl border border-[#EAE3D9] text-[#8C827A] text-xs">
        لا توجد شخصيات مسجلة حالياً. اضغط على "+ إنشاء شخصية جديدة" للبدء.
      </div>
    `;
    return;
  }

  container.innerHTML = userProfiles.map(p => {
    const isActive = Boolean(p.is_active);
    const isFemale = p.gender === 'female';
    const avatarBg = isActive ? 'from-[#680E23] to-[#8C1633]' : 'from-[#78716C] to-[#57534E]';
    const avatarEmoji = isFemale ? '👩🏻‍💼' : '👨🏻‍💼';

    return `
      <div class="bg-white rounded-3xl p-5 border ${isActive ? 'border-2 border-[#D4AF37] shadow-lg shadow-[#680E23]/10 ring-2 ring-[#680E23]/10' : 'border border-[#EAE3D9] shadow-sm hover:border-[#C5A880]'} transition-all duration-300 flex flex-col justify-between gap-4">
        <!-- Card Header -->
        <div class="flex items-start justify-between gap-3">
          <div class="flex items-center gap-3">
            <div class="w-12 h-12 rounded-2xl bg-gradient-to-tr ${avatarBg} text-2xl flex items-center justify-center text-white shadow shrink-0">
              ${avatarEmoji}
            </div>
            <div>
              <h4 class="text-sm font-bold text-[#1C1917] flex items-center gap-2">
                <span>${escapeHtml(p.name)}</span>
                ${isActive ? '<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-[#FAF0F2] text-[#680E23] border border-[#E8CCD2]">معتمد للمكالمات الحية ⭐</span>' : ''}
              </h4>
              <p class="text-xs text-[#6E645D] mt-0.5 font-medium">
                ${escapeHtml(p.role_display || p.role || p.persona_role)} &bull; ${escapeHtml(p.dialect_display || p.dialect)}
              </p>
            </div>
          </div>
        </div>

        <!-- Card Voice Timber & Details -->
        <div class="bg-[#FAF7F2] p-3 rounded-2xl border border-[#EAE3D9] text-xs space-y-1.5">
          <div class="flex justify-between items-center">
            <span class="text-[#8C827A]">صوت Google:</span>
            <span class="font-mono font-bold text-[#680E23] bg-white px-2 py-0.5 rounded-md border border-[#E8CCD2] text-[11px]">${escapeHtml(p.voice || p.voice_name)}</span>
          </div>
          <div class="flex justify-between items-center">
            <span class="text-[#8C827A]">الأسلوب:</span>
            <span class="text-[#2D2825] font-medium">${escapeHtml(p.style_display || p.style || p.speaking_style)}</span>
          </div>
          <div class="flex justify-between items-center">
            <span class="text-[#8C827A]">الترحيب الافتتاحي:</span>
            <span class="text-[11px] font-semibold ${p.is_welcome_message_enabled !== false ? 'text-[#680E23]' : 'text-[#8C827A]'}">
              ${p.is_welcome_message_enabled !== false ? (p.welcome_message ? `💬 "${escapeHtml(p.welcome_message.substring(0, 30))}${p.welcome_message.length > 30 ? '...' : ''}"` : '✨ ترحيب تلقائي ذكي') : '🤫 انتظار المتصل أولاً'}
            </span>
          </div>
          ${p.off_topic_response ? `
            <div class="flex justify-between items-center">
              <span class="text-[#8C827A]">الرد خارج النطاق:</span>
              <span class="text-[11px] font-medium text-[#680E23] truncate max-w-[200px]" title="${escapeHtml(p.off_topic_response)}">
                🛡️ "${escapeHtml(p.off_topic_response)}"
              </span>
            </div>
          ` : ''}
          ${p.custom_instructions ? `
            <div class="pt-1.5 border-t border-[#EAE3D9] text-[11px] text-[#6E645D] italic line-clamp-2">
              "${escapeHtml(p.custom_instructions)}"
            </div>
          ` : ''}
        </div>

        <!-- Card Actions -->
        <div class="flex items-center justify-between gap-2 pt-2 border-t border-[#EAE3D9]">
          <button type="button" onclick="selectAndScrollToProfile(${p.id})" class="px-3 py-1.5 rounded-xl bg-[#F5EFE6] hover:bg-[#EAE3D9] text-[#443D39] text-xs font-semibold transition flex items-center gap-1">
            <span>⚙️ تعديل التفاصيل</span>
          </button>
          ${isActive ? `
            <span class="text-xs text-emerald-700 font-bold flex items-center gap-1">
              <span>✓</span> مفعل حالياً
            </span>
          ` : `
            <button type="button" onclick="activateProfileById(${p.id})" class="px-3.5 py-1.5 rounded-xl bg-[#680E23] hover:bg-[#7E152F] text-white text-xs font-bold transition shadow-sm flex items-center gap-1">
              <span>🚀</span> تفعيل للمكالمات
            </button>
          `}
        </div>
      </div>
    `;
  }).join('');
}

function renderProfileDropdown() {
  if (!profileSelect) return;
  if (!userProfiles || userProfiles.length === 0) {
    profileSelect.innerHTML = '<option value="">لا توجد بروفايلات</option>';
    return;
  }
  profileSelect.innerHTML = userProfiles.map(p => `
    <option value="${p.id}" ${p.is_active ? 'selected' : ''}>
      ${p.name} ${p.is_active ? '⭐ [نشط للمكالمات]' : ''}
    </option>
  `).join('');
}

function populateDialectSelect(selectElem, selectedLang, selectedDialect) {
  if (!selectElem) return;
  const list = (languageDialectsMap && languageDialectsMap[selectedLang]) || [
    { id: 'egyptian', label: 'لهجة مصرية عامية (مصر)' }
  ];
  selectElem.innerHTML = list.map(d => `
    <option value="${d.id}" ${d.id === selectedDialect ? 'selected' : ''}>
      ${d.label}
    </option>
  `).join('');
}

function handleLanguageChange(context) {
  if (context === 'field') {
    const lang = fieldLanguage ? fieldLanguage.value : 'arabic';
    populateDialectSelect(fieldDialect, lang);
  } else if (context === 'new') {
    const lang = newProfLanguage ? newProfLanguage.value : 'arabic';
    populateDialectSelect(newProfDialect, lang);
  }
}

function populateVoiceSelect(selectElem, targetGender, selectedVoice) {
  if (!selectElem || !googleVoices || googleVoices.length === 0) return;
  
  const filtered = targetGender 
    ? googleVoices.filter(v => v.gender === targetGender)
    : googleVoices;
  const other = targetGender 
    ? googleVoices.filter(v => v.gender !== targetGender)
    : [];

  let html = '';
  if (filtered.length > 0) {
    html += `<optgroup label="أصوات (${targetGender === 'female' ? 'نسائية' : 'رجالية'})">`;
    filtered.forEach(v => {
      html += `<option value="${v.name}" ${v.name === selectedVoice ? 'selected' : ''}>${v.name} - ${v.style}</option>`;
    });
    html += '</optgroup>';
  }

  if (other.length > 0) {
    html += `<optgroup label="أصوات أخرى">`;
    other.forEach(v => {
      html += `<option value="${v.name}" ${v.name === selectedVoice ? 'selected' : ''}>${v.name} - ${v.style}</option>`;
    });
    html += '</optgroup>';
  }

  selectElem.innerHTML = html;
}

function syncGenderVoiceOptions() {
  if (!fieldGender || !fieldVoice) return;
  const g = fieldGender.value;
  const currentVoice = fieldVoice.value || (activeProfile ? (activeProfile.voice_name || activeProfile.voice) : 'Aoede');
  populateVoiceSelect(fieldVoice, g, currentVoice);
  updateVoiceTag();
}

function syncNewProfileVoices() {
  if (!newProfGender || !newProfVoice) return;
  const g = newProfGender.value;
  populateVoiceSelect(newProfVoice, g, g === 'female' ? 'Aoede' : 'Puck');
}

function updateVoiceTag() {
  if (!fieldVoice || !voiceTagBadge) return;
  const selectedName = fieldVoice.value;
  const v = googleVoices.find(x => x.name === selectedName);
  if (v) {
    voiceTagBadge.innerText = `${v.tag} | ${v.style.split('(')[0].trim()}`;
  }
}

function populateProfileForm(p) {
  if (!p) return;
  if (fieldGender) fieldGender.value = p.gender;
  if (fieldLanguage) fieldLanguage.value = p.language || 'arabic';
  populateDialectSelect(fieldDialect, p.language || 'arabic', p.dialect);
  populateVoiceSelect(fieldVoice, p.gender, p.voice_name || p.voice);
  if (fieldRole) fieldRole.value = p.persona_role || p.role || '';
  if (fieldStyle) fieldStyle.value = p.speaking_style || p.style || '';
  if (fieldVerbosity) fieldVerbosity.value = p.verbosity || 'balanced';
  if (fieldWelcomeEnabled) fieldWelcomeEnabled.checked = p.is_welcome_message_enabled !== false;
  if (fieldWelcome) fieldWelcome.value = p.welcome_message || '';
  toggleWelcomeInput('active');
  if (fieldCustom) fieldCustom.value = p.custom_instructions || '';
  if (fieldOffTopic) fieldOffTopic.value = p.off_topic_response || '';
  updateVoiceTag();

  if (profileStatusMsg) {
    profileStatusMsg.innerText = `البروفايل المطبق: "${p.name}" (${p.voice_name || p.voice} / ${p.dialect_display || p.dialect})`;
    profileStatusMsg.className = 'text-xs text-[#680E23] font-semibold';
  }
}

function selectAndScrollToProfile(profileId) {
  if (profileSelect) {
    profileSelect.value = profileId;
    handleProfileSelect(profileId);
  }
  const editor = document.getElementById('profile-editor-card');
  if (editor) {
    editor.scrollIntoView({ behavior: 'smooth', block: 'center' });
    editor.classList.add('ring-2', 'ring-[#680E23]');
    setTimeout(() => editor.classList.remove('ring-2', 'ring-[#680E23]'), 1500);
  }
}

async function activateProfileById(profileId) {
  try {
    const csrf = getCookie('csrftoken');
    const res = await fetch(`/api/agents/profiles/${profileId}/activate/`, {
      method: 'POST',
      headers: {
        'X-CSRFToken': csrf,
        'Content-Type': 'application/json'
      }
    });
    if (res.ok) {
      showToast('تم تفعيل الشخصية بنجاح للمكالمات الحية', 'success');
      await loadProfiles();
    } else {
      showToast('فشل تفعيل البروفايل', 'error');
    }
  } catch (err) {
    showToast('حدث خطأ أثناء تفعيل البروفايل.', 'error');
  }
}

async function handleProfileSelect(profileId) {
  if (!profileId) return;
  try {
    const res = await fetch(`/api/agents/profiles/${profileId}/activate/`, {
      method: 'POST',
      headers: { 'X-CSRFToken': getCookie('csrftoken') }
    });
    const data = await res.json();
    if (data.status === 'success') {
      activeProfile = data.profile;
      userProfiles = userProfiles.map(p => ({ ...p, is_active: p.id === activeProfile.id }));
      renderProfileDropdown();
      renderProfileCards();
      populateProfileForm(activeProfile);
      showToast(`تم تفعيل بروفايل "${activeProfile.name}"!`, 'success');
    }
  } catch (err) {
    console.error('Error activating profile:', err);
  }
}

async function saveActiveProfileChanges() {
  if (!activeProfile) return;
  const btn = document.getElementById('btn-save-profile');
  if (btn) {
    btn.disabled = true;
    btn.innerText = 'جاري الحفظ...';
  }

  const payload = {
    gender: fieldGender ? fieldGender.value : 'female',
    language: fieldLanguage ? fieldLanguage.value : 'arabic',
    dialect: fieldDialect ? fieldDialect.value : 'egyptian',
    voice_name: fieldVoice ? fieldVoice.value : 'Aoede',
    persona_role: fieldRole ? fieldRole.value : '',
    speaking_style: fieldStyle ? fieldStyle.value : '',
    verbosity: fieldVerbosity ? fieldVerbosity.value : 'balanced',
    welcome_message: fieldWelcome ? fieldWelcome.value.trim() : '',
    is_welcome_message_enabled: fieldWelcomeEnabled ? fieldWelcomeEnabled.checked : true,
    custom_instructions: fieldCustom ? fieldCustom.value.trim() : '',
    off_topic_response: fieldOffTopic ? fieldOffTopic.value.trim() : ''
  };

  try {
    const res = await fetch(`/api/agents/profiles/${activeProfile.id}/update/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken')
      },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (data.status === 'success') {
      activeProfile = data.profile;
      userProfiles = userProfiles.map(p => p.id === activeProfile.id ? activeProfile : p);
      renderProfileCards();
      showToast(`تم حفظ وتطبيق إعدادات "${activeProfile.name}" بنجاح!`, 'success');
    } else {
      showToast('فشل الحفظ: ' + (data.message || ''), 'error');
    }
  } catch (err) {
    showToast('حدث خطأ أثناء حفظ البروفايل.', 'error');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" /></svg> حفظ وتطبيق على المكالمات`;
    }
  }
}

function openNewProfileModal() {
  const form = document.getElementById('new-profile-form');
  if (form) form.reset();
  if (newProfLanguage) newProfLanguage.value = 'arabic';
  populateDialectSelect(newProfDialect, 'arabic', 'egyptian');
  syncNewProfileVoices();
  if (newProfWelcomeEnabled) newProfWelcomeEnabled.checked = true;
  if (newProfWelcome) newProfWelcome.value = '';
  if (newProfOffTopic) newProfOffTopic.value = '';
  toggleWelcomeInput('new');
  if (profileModal) profileModal.classList.remove('hidden');
}

function closeNewProfileModal() {
  if (profileModal) profileModal.classList.add('hidden');
}

async function createNewProfile(e) {
  e.preventDefault();
  const name = document.getElementById('new-prof-name').value.trim();
  const gender = document.getElementById('new-prof-gender').value;
  const language = newProfLanguage ? newProfLanguage.value : 'arabic';
  const dialect = newProfDialect.value;
  const voice_name = document.getElementById('new-prof-voice').value;
  const persona_role = document.getElementById('new-prof-role').value;
  const speaking_style = document.getElementById('new-prof-style').value;
  const verbosity = newProfVerbosity ? newProfVerbosity.value : 'balanced';
  const welcome_message = newProfWelcome ? newProfWelcome.value.trim() : '';
  const is_welcome_message_enabled = newProfWelcomeEnabled ? newProfWelcomeEnabled.checked : true;
  const off_topic_response = newProfOffTopic ? newProfOffTopic.value.trim() : '';

  const btn = document.getElementById('btn-create-prof');
  if (btn) {
    btn.disabled = true;
    btn.innerText = 'جاري الحفظ...';
  }

  try {
    const res = await fetch('/api/agents/profiles/create/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken')
      },
      body: JSON.stringify({
        name,
        gender,
        language,
        dialect,
        voice_name,
        persona_role,
        speaking_style,
        verbosity,
        welcome_message,
        is_welcome_message_enabled,
        off_topic_response,
        is_active: true
      })
    });
    const data = await res.json();
    if (data.status === 'success') {
      closeNewProfileModal();
      showToast('تم إنشاء وتفعيل الشخصية بنجاح!', 'success');
      await loadProfiles();
    } else {
      showToast('فشل إنشاء البروفايل: ' + (data.message || ''), 'error');
    }
  } catch (err) {
    showToast('حدث خطأ في الاتصال بالخادم.', 'error');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerText = 'حفظ البروفايل';
    }
  }
}

async function deleteCurrentProfile() {
  if (!activeProfile) return;
  if (userProfiles.length <= 1) {
    alert('لا يمكنك حذف البروفايل الوحيد لديك.');
    return;
  }
  if (!confirm(`هل أنت متأكد من حذف بروفايل "${activeProfile.name}"؟`)) return;

  try {
    const res = await fetch(`/api/agents/profiles/${activeProfile.id}/delete/`, {
      method: 'POST',
      headers: { 'X-CSRFToken': getCookie('csrftoken') }
    });
    const data = await res.json();
    if (data.status === 'success') {
      showToast('تم حذف البروفايل بنجاح', 'success');
      await loadProfiles();
    } else {
      showToast('فشل الحذف: ' + (data.message || ''), 'error');
    }
  } catch (err) {
    showToast('حدث خطأ أثناء حذف البروفايل.', 'error');
  }
}

document.addEventListener('DOMContentLoaded', () => {
  profileSelect = document.getElementById('profile-select');
  fieldGender = document.getElementById('field-gender');
  fieldLanguage = document.getElementById('field-language');
  fieldDialect = document.getElementById('field-dialect');
  fieldVoice = document.getElementById('field-voice');
  fieldRole = document.getElementById('field-role');
  fieldStyle = document.getElementById('field-style');
  fieldVerbosity = document.getElementById('field-verbosity');
  fieldWelcome = document.getElementById('field-welcome');
  fieldWelcomeEnabled = document.getElementById('field-welcome-enabled');
  welcomeToggleStatus = document.getElementById('welcome-toggle-status');
  fieldCustom = document.getElementById('field-custom');
  fieldOffTopic = document.getElementById('field-off-topic');
  voiceTagBadge = document.getElementById('voice-tag-badge');
  profileStatusMsg = document.getElementById('profile-status-msg');

  profileModal = document.getElementById('profile-modal');
  newProfVoice = document.getElementById('new-prof-voice');
  newProfGender = document.getElementById('new-prof-gender');
  newProfLanguage = document.getElementById('new-prof-language');
  newProfDialect = document.getElementById('new-prof-dialect');
  newProfVerbosity = document.getElementById('new-prof-verbosity');
  newProfWelcome = document.getElementById('new-prof-welcome');
  newProfWelcomeEnabled = document.getElementById('new-prof-welcome-enabled');
  newProfOffTopic = document.getElementById('new-prof-off-topic');

  loadProfiles();
});
