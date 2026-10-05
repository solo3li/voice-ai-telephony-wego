/**
 * Developer API Portal JavaScript
 * Handles live API key retrieval, rotation, visibility toggling, and code samples.
 */

let currentDeveloperKey = '';

async function loadDeveloperKeys() {
  try {
    const res = await fetch('/api/v1/keys/');
    if (!res.ok) return;
    const data = await res.json();
    if (data.status === 'success' && data.keys && data.keys.length > 0) {
      const keyObj = data.keys[0];
      currentDeveloperKey = keyObj.key || keyObj.prefix;
      const keyInput = document.getElementById('dev-api-key-input');
      const createdEl = document.getElementById('dev-key-created-at');
      const usedEl = document.getElementById('dev-key-last-used');
      const curlSample = document.getElementById('dev-curl-sample');
      const curlDialSample = document.getElementById('dev-curl-dial-sample');

      if (keyInput) keyInput.value = currentDeveloperKey;
      if (createdEl) createdEl.innerText = keyObj.created_at || '--';
      if (usedEl) usedEl.innerText = keyObj.last_used_at || 'لم يُستخدم بعد';

      if (curlSample) {
        curlSample.innerText = `curl -X GET "${window.location.origin}/api/v1/account/" \\\n  -H "X-API-Key: ${currentDeveloperKey}" \\\n  -H "Accept: application/json"`;
      }
      if (curlDialSample) {
        curlDialSample.innerText = `curl -X POST "${window.location.origin}/api/v1/calls/dial/" \\\n  -H "X-API-Key: ${currentDeveloperKey}" \\\n  -H "Content-Type: application/json" \\\n  -d '{"phone_number": "+201012345678", "call_goal": "تأكيد تفاصيل الطلب رقم 1005"}'`;
      }
      const curlCtxSample = document.getElementById('dev-curl-context-sample');
      if (curlCtxSample) {
        curlCtxSample.innerText = `curl -X PUT "${window.location.origin}/api/v1/context/" \\\n  -H "X-API-Key: ${currentDeveloperKey}" \\\n  -H "Content-Type: application/json" \\\n  -d '{"restaurant_name": "مطعم البرجر الذهبي", "out_of_stock": ["برجر دبل بيف"], "branches": [{"name": "المعادي", "status": "مفتوح", "hours": "12 م - 2 ص"}]}'`;
      }
    }
  } catch (e) {
    console.error('Error loading developer keys:', e);
  }
}

// ==================== Structured Live Context Functions ====================

async function loadLiveContext() {
  const jsonInput = document.getElementById('live-context-json-input');
  if (!jsonInput) return;

  try {
    const res = await fetch('/api/agents/context/');
    if (!res.ok) return;
    const data = await res.json();
    if (data.status === 'success' && data.context) {
      const ctx = data.context;
      const rawData = ctx.data || {};
      const hasData = Object.keys(rawData).length > 0;
      jsonInput.value = hasData ? JSON.stringify(rawData, null, 2) : '';

      updateLiveContextBadges(data.cached_in_redis, ctx.size_bytes || 0, ctx.updated_at);
    }
  } catch (e) {
    console.error('Error loading live context:', e);
  }
}

function updateLiveContextBadges(cachedInRedis, sizeBytes, updatedAt) {
  const redisBadge = document.getElementById('live-context-redis-badge');
  const sizeBadge = document.getElementById('live-context-size-badge');
  const updatedBadge = document.getElementById('live-context-last-updated');

  if (redisBadge) {
    if (cachedInRedis) {
      redisBadge.className = 'px-2.5 py-0.5 text-xs font-bold rounded-full bg-emerald-100 text-emerald-800 border border-emerald-300 flex items-center gap-1';
      redisBadge.innerHTML = '<span>🟢</span> <span>متزامن في الذاكرة (Redis Active)</span>';
    } else {
      redisBadge.className = 'px-2.5 py-0.5 text-xs font-bold rounded-full bg-slate-100 text-slate-700 border border-slate-300 flex items-center gap-1';
      redisBadge.innerHTML = '<span>⚪</span> <span>فارغ / غير محمل</span>';
    }
  }

  if (sizeBadge) {
    const kb = (sizeBytes / 1024).toFixed(1);
    sizeBadge.innerText = `الحجم: ${kb} KB / 100 KB (${sizeBytes} بايت)`;
  }

  if (updatedBadge) {
    updatedBadge.innerText = updatedAt ? `آخر تحديث: ${updatedAt}` : 'آخر تحديث: لم يتم الحفظ بعد';
  }
}

function formatLiveContextJson() {
  const jsonInput = document.getElementById('live-context-json-input');
  if (!jsonInput) return;
  const val = jsonInput.value.trim();
  if (!val) {
    showToast('المحرر فارغ، لا يوجد JSON لتنسيقه.', 'info');
    return;
  }
  try {
    const parsed = JSON.parse(val);
    jsonInput.value = JSON.stringify(parsed, null, 2);
    showToast('تم تنسيق وترتيب الـ JSON بنجاح.', 'success');
  } catch (e) {
    showToast('صيغة JSON غير صحيحة: ' + e.message, 'error');
  }
}

function loadRestaurantTemplate() {
  const jsonInput = document.getElementById('live-context-json-input');
  if (!jsonInput) return;

  const template = {
    "restaurant_name": "مطعم بيسترو إيطاليانو",
    "out_of_stock": [
      "بيتزا باربيكيو دجاج حجم كبير",
      "سلطة سيزر بالدجاج"
    ],
    "branches": [
      {
        "name": "فرع المعادي (الرئيسي)",
        "status": "مفتوح حالياً",
        "hours": "11:00 ص حتى 02:00 ص",
        "address": "شارع 9، المعادي، القاهرة",
        "phone": "+201011112222"
      },
      {
        "name": "فرع التجمع الخامس",
        "status": "مفتوح حالياً",
        "hours": "12:00 م حتى 01:00 ص",
        "address": "شارع التسعين الشمالي، التجمع الخامس",
        "phone": "+201033334444"
      }
    ],
    "delivery_zones": [
      {
        "zone": "المعادي ودجلة",
        "fee": "20 جنيه",
        "min_order": "100 جنيه",
        "estimated_time": "35 - 45 دقيقة"
      },
      {
        "zone": "التجمع الخامس والرحاب",
        "fee": "35 جنيه",
        "min_order": "150 جنيه",
        "estimated_time": "45 - 60 دقيقة"
      }
    ],
    "offers": [
      {
        "title": "عرض الويك إند الذهبي",
        "price": "299 جنيه",
        "description": "2 بيتزا لارج + لتر كوكاكولا + بطاطس ويدجز مجاناً"
      }
    ],
    "menu": {
      "البيتزا الإيطالية": [
        { "name": "مارجريتا كلاسيك", "price": "140ج وسط / 190ج كبير", "description": "صلصة طماطم إيطالية وجبنة موتزاريلا وريحان" },
        { "name": "بيبروني سوبريم", "price": "170ج وسط / 230ج كبير", "description": "بيبروني لحم بقري مدخن وجبنة موتزاريلا" }
      ],
      "المعكرونة والباستا": [
        { "name": "فيتوتشيني ألفريدو", "price": "165 جنيه", "description": "صوص كريمة أبيض وجبنة بارميزان وفطر طازج" }
      ],
      "المشروبات": [
        { "name": "كوكاكولا / سبرايت", "price": "25 جنيه" },
        { "name": "عصير برتقال طبيعي طازج", "price": "45 جنيه" }
      ]
    }
  };

  jsonInput.value = JSON.stringify(template, null, 2);
  showToast('تم تحميل نموذج المطعم المنظم في المحرر. يمكنك تعديله والضغط على حفظ.', 'success');
}

async function saveLiveContext() {
  const jsonInput = document.getElementById('live-context-json-input');
  const btn = document.getElementById('btn-save-live-context');
  if (!jsonInput) return;

  const raw = jsonInput.value.trim();
  let parsed = {};
  if (raw) {
    try {
      parsed = JSON.parse(raw);
    } catch (e) {
      showToast('خطأ في صياغة JSON: ' + e.message, 'error');
      return;
    }
  }

  if (typeof parsed !== 'object' || Array.isArray(parsed) || parsed === null) {
    showToast('يجب أن يكون الـ JSON كائن (Object) يحتوي على مفاتيح وقيم.', 'error');
    return;
  }

  try {
    if (btn) {
      btn.disabled = true;
      btn.innerHTML = '<span>⏳</span> <span>جاري الحفظ والمزامنة...</span>';
    }

    const res = await fetch('/api/agents/context/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken')
      },
      body: JSON.stringify(parsed)
    });

    const data = await res.json();
    if (data.status === 'success') {
      showToast('تم حفظ واستبدال الذاكرة المنظمة ومزامنتها مع كاش Redis بنجاح! 🚀', 'success');
      const ctx = data.context || {};
      updateLiveContextBadges(true, ctx.size_bytes || 0, ctx.updated_at);
    } else {
      showToast(data.message || 'فشل حفظ الذاكرة المنظمة', 'error');
    }
  } catch (e) {
    console.error('Error saving live context:', e);
    showToast('حدث خطأ أثناء الاتصال بالخادم', 'error');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '<span>💾</span> <span>حفظ واستبدال فوري (Save &amp; Push to Redis)</span>';
    }
  }
}

async function clearLiveContext() {
  if (!confirm('هل أنت متأكد من رغبتك في مسح كافة بيانات الذاكرة المنظمة الحية من الـ DB وكاش الـ Redis؟')) {
    return;
  }
  try {
    const res = await fetch('/api/agents/context/', {
      method: 'DELETE',
      headers: {
        'X-CSRFToken': getCookie('csrftoken')
      }
    });
    const data = await res.json();
    if (data.status === 'success') {
      const jsonInput = document.getElementById('live-context-json-input');
      if (jsonInput) jsonInput.value = '';
      updateLiveContextBadges(false, 0, null);
      showToast('تم مسح الذاكرة المنظمة الحية بنجاح.', 'success');
      const previewBox = document.getElementById('live-context-prompt-preview-box');
      if (previewBox) previewBox.classList.add('hidden');
    } else {
      showToast(data.message || 'فشل مسح الذاكرة', 'error');
    }
  } catch (e) {
    console.error('Error clearing live context:', e);
    showToast('حدث خطأ أثناء الاتصال بالخادم', 'error');
  }
}

async function togglePromptPreview() {
  const box = document.getElementById('live-context-prompt-preview-box');
  const content = document.getElementById('live-context-prompt-preview-content');
  if (!box || !content) return;

  if (!box.classList.contains('hidden')) {
    box.classList.add('hidden');
    return;
  }

  box.classList.remove('hidden');
  content.innerText = 'جاري ترجمة ومعاينة التوجيهات الحية...';

  const jsonInput = document.getElementById('live-context-json-input');
  let payload = {};
  if (jsonInput && jsonInput.value.trim()) {
    try {
      payload = JSON.parse(jsonInput.value.trim());
    } catch (e) {
      content.innerText = '⚠️ الـ JSON الحالي غير صالح، لا يمكن توليد المعاينة: ' + e.message;
      return;
    }
  }

  try {
    const res = await fetch('/api/agents/context/preview/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken')
      },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (data.status === 'success') {
      content.innerText = data.preview || 'لا توجد بيانات مدخلة.';
    } else {
      content.innerText = 'فشل توليد المعاينة: ' + (data.message || '');
    }
  } catch (e) {
    content.innerText = 'حدث خطأ أثناء توليد المعاينة: ' + e.message;
  }
}

// ==================== End Live Context ====================

function toggleDevKeyVisibility() {

  const inp = document.getElementById('dev-api-key-input');
  const btn = document.getElementById('btn-toggle-dev-key');
  if (!inp || !btn) return;
  if (inp.type === 'password') {
    inp.type = 'text';
    btn.innerText = '🙈';
  } else {
    inp.type = 'password';
    btn.innerText = '👁️';
  }
}

function copyDevApiKey() {
  const inp = document.getElementById('dev-api-key-input');
  if (inp) {
    navigator.clipboard.writeText(inp.value);
    showToast('تم نسخ مفتاح API بنجاح لاستخدامه في تطبيقاتك!', 'success');
  }
}

function copyDevCurlSample() {
  const sample = document.getElementById('dev-curl-sample');
  if (sample) {
    navigator.clipboard.writeText(sample.innerText);
    showToast('تم نسخ مثال cURL إلى الحافظة!', 'success');
  }
}

async function rotateDeveloperKeyPrompt() {
  if (!confirm('هل أنت متأكد من رغبتك في تدوير مفتاح الـ API؟ سيتوقف المفتاح القديم عن العمل فوراً ولن تتمكن أي تطبيقات تستخدمه من الوصول.')) {
    return;
  }
  try {
    const res = await fetch('/api/v1/keys/rotate/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken')
      },
      body: JSON.stringify({ name: 'مفتاح التطبيق (مُحدّث)' })
    });
    const data = await res.json();
    if (data.status === 'success') {
      showToast('تم توليد مفتاح API جديد بنجاح.', 'success');
      await loadDeveloperKeys();
    } else {
      showToast(data.message || 'فشل تدوير المفتاح', 'error');
    }
  } catch (e) {
    console.error('Error rotating developer key:', e);
    showToast('حدث خطأ أثناء الاتصال بالخادم', 'error');
  }
}

document.addEventListener('DOMContentLoaded', () => {
  loadDeveloperKeys();
  loadLiveContext();
});

