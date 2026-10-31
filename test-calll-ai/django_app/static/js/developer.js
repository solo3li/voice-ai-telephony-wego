/**
 * Developer API Portal JavaScript
 * Handles live API key retrieval, rotation, visibility toggling, code samples,
 * tab switching, and structured live context synchronisation.
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
      const origin = window.location.origin;

      const keyInput = document.getElementById('dev-api-key-input');
      const createdEl = document.getElementById('dev-key-created-at');
      const usedEl = document.getElementById('dev-key-last-used');
      const curlSample = document.getElementById('dev-curl-sample');
      const curlDialSample = document.getElementById('dev-curl-dial-sample');

      if (keyInput) keyInput.value = currentDeveloperKey;
      if (createdEl) createdEl.innerText = keyObj.created_at || '--';
      if (usedEl) usedEl.innerText = keyObj.last_used_at || (window.t ? window.t('dev_never_used', 'لم يُستخدم بعد') : 'لم يُستخدم بعد');

      if (curlSample) {
        curlSample.innerText = `curl -X GET "${origin}/api/v1/account/" \\\n  -H "X-API-Key: ${currentDeveloperKey}" \\\n  -H "Accept: application/json"`;
      }
      if (curlDialSample) {
        curlDialSample.innerText = `curl -X POST "${origin}/api/v1/calls/dial/" \\\n  -H "X-API-Key: ${currentDeveloperKey}" \\\n  -H "Content-Type: application/json" \\\n  -d '{"phone_number": "+201012345678", "call_goal": "تأكيد تفاصيل الطلب رقم 1005"}'`;
      }
      const curlCtxSample = document.getElementById('dev-curl-context-sample');
      if (curlCtxSample) {
        curlCtxSample.innerText = `curl -X PUT "${origin}/api/v1/context/" \\\n  -H "X-API-Key: ${currentDeveloperKey}" \\\n  -H "Content-Type: application/json" \\\n  -d '{"restaurant_name": "مطعم البرجر الذهبي", "out_of_stock": ["برجر دبل بيف"], "branches": [{"name": "المعادي", "status": "مفتوح", "hours": "12 م - 2 ص"}]}'`;
      }

      // Zero-Code Iframes & Automation APIs
      const embedCallCenterSnippet = document.getElementById('dev-embed-callcenter-snippet');
      const previewCallCenter = document.getElementById('dev-embed-callcenter-preview-btn');
      const embedChatSnippet = document.getElementById('dev-embed-chat-snippet');
      const embedChatChannelsSnippet = document.getElementById('dev-embed-chat-channels-snippet');
      const embedChatSettingsSnippet = document.getElementById('dev-embed-chat-settings-snippet');
      const previewChat = document.getElementById('dev-embed-chat-preview-btn');
      const previewChatLive = document.getElementById('dev-embed-chat-live-preview-btn');
      const previewChatChannels = document.getElementById('dev-embed-chat-channels-preview-btn');
      const previewChatSettings = document.getElementById('dev-embed-chat-settings-preview-btn');
      const embedVoiceSnippet = document.getElementById('dev-embed-voice-snippet');
      const previewVoice = document.getElementById('dev-embed-voice-preview-btn');
      const curlChatSend = document.getElementById('dev-curl-chat-send-sample');
      const curlDial2 = document.getElementById('dev-curl-dial-sample-2');

      if (embedCallCenterSnippet) {
        embedCallCenterSnippet.innerText = `<iframe src="${origin}/embed/call-center/?token=${currentDeveloperKey}&locale=ar" width="100%" height="800" frameborder="0" allow="microphone; camera; clipboard-read; clipboard-write;" style="border-radius: 16px; border: 1px solid #e2e8f0; width: 100%; min-height: 800px;"></iframe>`;
      }
      if (previewCallCenter) {
        previewCallCenter.href = `/embed/call-center/?token=${encodeURIComponent(currentDeveloperKey)}&locale=ar`;
      }
      if (embedChatSnippet) {
        embedChatSnippet.innerText = `<iframe src="${origin}/embed/chat-hub/?token=${currentDeveloperKey}&locale=ar" width="100%" height="800" frameborder="0" allow="camera; microphone; clipboard-read; clipboard-write;" style="border-radius: 16px; border: 1px solid #e2e8f0; width: 100%; min-height: 800px;"></iframe>`;
      }
      if (embedChatChannelsSnippet) {
        embedChatChannelsSnippet.innerText = `<iframe src="${origin}/embed/chat-hub/?tab=channels&token=${currentDeveloperKey}&locale=ar" width="100%" height="800" frameborder="0" allow="camera; microphone; clipboard-read; clipboard-write;" style="border-radius: 16px; border: 1px solid #e2e8f0; width: 100%; min-height: 800px;"></iframe>`;
      }
      if (embedChatSettingsSnippet) {
        embedChatSettingsSnippet.innerText = `<iframe src="${origin}/embed/chat-hub/?tab=settings&token=${currentDeveloperKey}&locale=ar" width="100%" height="800" frameborder="0" allow="camera; microphone; clipboard-read; clipboard-write;" style="border-radius: 16px; border: 1px solid #e2e8f0; width: 100%; min-height: 800px;"></iframe>`;
      }
      if (previewChat) {
        previewChat.href = `/embed/chat-hub/?token=${encodeURIComponent(currentDeveloperKey)}&locale=ar`;
      }
      if (previewChatLive) {
        previewChatLive.href = `/embed/chat-hub/?token=${encodeURIComponent(currentDeveloperKey)}&locale=ar`;
      }
      if (previewChatChannels) {
        previewChatChannels.href = `/embed/chat-hub/?tab=channels&token=${encodeURIComponent(currentDeveloperKey)}&locale=ar`;
      }
      if (previewChatSettings) {
        previewChatSettings.href = `/embed/chat-hub/?tab=settings&token=${encodeURIComponent(currentDeveloperKey)}&locale=ar`;
      }
      if (embedVoiceSnippet) {
        embedVoiceSnippet.innerText = `<iframe src="${origin}/embed/call-center/room/?token=${currentDeveloperKey}&locale=ar" width="100%" height="800" frameborder="0" allow="microphone; camera; clipboard-read; clipboard-write;" style="border-radius: 16px; border: 1px solid #e2e8f0; width: 100%; min-height: 800px;"></iframe>`;
      }
      if (previewVoice) {
        previewVoice.href = `/embed/call-center/room/?token=${encodeURIComponent(currentDeveloperKey)}&locale=ar`;
      }
      if (curlChatSend) {
        curlChatSend.innerText = `curl -X POST "${origin}/api/v1/chat/send/" \\\n  -H "X-API-Key: ${currentDeveloperKey}" \\\n  -H "Content-Type: application/json" \\\n  -d '{"to": "+201012345678", "message": "مرحباً بك! كود التحقق هو 5491", "channel": "whatsapp"}'`;
      }
      if (curlDial2) {
        curlDial2.innerText = `curl -X POST "${origin}/api/v1/calls/dial/" \\\n  -H "X-API-Key: ${currentDeveloperKey}" \\\n  -H "Content-Type: application/json" \\\n  -d '{"phone_number": "+201012345678", "call_goal": "تأكيد تفاصيل الطلب رقم 1005"}'`;
      }

      // Dynamic update of advanced snippet cards
      const webrtcCurl = document.getElementById('dev-webrtc-curl-sample');
      if (webrtcCurl) {
        webrtcCurl.innerText = `curl -X POST "${origin}/api/v1/calls/webrtc/" \\\n  -H "X-API-Key: ${currentDeveloperKey}" \\\n  -H "Content-Type: application/json" \\\n  -d '{\n    "customer_name": "أحمد عبد الله",\n    "phone_number": "+201012345678",\n    "profile_id": 1,\n    "custom_welcome_message": "أهلاً بك يا أحمد في متجرنا! كيف أقدر أساعدك اليوم؟"\n  }'`;
      }

      const tokenCurl = document.getElementById('dev-token-curl-sample');
      if (tokenCurl) {
        tokenCurl.innerText = `curl -X POST "${origin}/api/token/" \\\n  -H "X-API-Key: ${currentDeveloperKey}" \\\n  -H "Content-Type: application/json" \\\n  -d '{"room": "room_support_${keyObj.prefix || 'usr'}", "identity": "client_web"}'`;
      }

      const webhookCurl = document.getElementById('dev-webhook-config-sample');
      if (webhookCurl) {
        webhookCurl.innerText = `curl -X POST "${origin}/api/v1/webhooks/" \\\n  -H "X-API-Key: ${currentDeveloperKey}" \\\n  -H "Content-Type: application/json" \\\n  -d '{\n    "webhook_url": "https://your-crm.com/api/webhooks/voice-ai/",\n    "webhook_secret": "whsec_your_custom_secret_key",\n    "is_active": true\n  }'`;
      }

      const whatsappDirect = document.getElementById('dev-whatsapp-direct-sample');
      if (whatsappDirect) {
        whatsappDirect.innerText = `curl -X POST "${origin}/api/v1/whatsapp/send/" \\\n  -H "X-API-Key: ${currentDeveloperKey}" \\\n  -H "Content-Type: application/json" \\\n  -d '{\n    "to": "+201012345678",\n    "message": "عزيزي العميل، تم تجهيز طلبك رقم 1005 وهو في طريقه إليك الآن!"\n  }'`;
      }

      const whatsappInternal = document.getElementById('dev-whatsapp-internal-sample');
      if (whatsappInternal) {
        whatsappInternal.innerText = `curl -X POST "${origin}/api/agents/internal/whatsapp/send/" \\\n  -H "Content-Type: application/json" \\\n  -d '{\n    "to": "+201012345678",\n    "message": "تنبيه آلي من المساعد الصوتي: تم تسجيل حجزك بنجاح.",\n    "user_id": 1\n  }'`;
      }

      const whatsappFollowup = document.getElementById('dev-whatsapp-followup-sample');
      if (whatsappFollowup) {
        whatsappFollowup.innerText = `curl -X POST "${origin}/api/v1/whatsapp/followup/" \\\n  -H "X-API-Key: ${currentDeveloperKey}" \\\n  -H "Content-Type: application/json" \\\n  -d '{\n    "phone_number": "+201012345678",\n    "message": "شكراً لاتصالك! إليك رابط تأكيد التفاصيل: https://example.com/order"\n  }'`;
      }

      const whatsappEscalate = document.getElementById('dev-whatsapp-escalate-sample');
      if (whatsappEscalate) {
        whatsappEscalate.innerText = `curl -X POST "${origin}/api/v1/whatsapp/conversations/+201012345678/escalate/" \\\n  -H "X-API-Key: ${currentDeveloperKey}" \\\n  -H "Content-Type: application/json" \\\n  -d '{"reason": "العميل طلب التحدث مع مسؤول الحسابات", "urgency": "high"}'`;
      }

      const whatsappClaim = document.getElementById('dev-whatsapp-claim-sample');
      if (whatsappClaim) {
        whatsappClaim.innerText = `curl -X POST "${origin}/api/v1/whatsapp/conversations/+201012345678/claim/" \\\n  -H "X-API-Key: ${currentDeveloperKey}" \\\n  -H "Content-Type: application/json" \\\n  -d '{"agent_name": "سارة أحمد"}'`;
      }

      const whatsappReply = document.getElementById('dev-whatsapp-reply-sample');
      if (whatsappReply) {
        whatsappReply.innerText = `curl -X POST "${origin}/api/v1/whatsapp/conversations/+201012345678/reply/" \\\n  -H "X-API-Key: ${currentDeveloperKey}" \\\n  -H "Content-Type: application/json" \\\n  -d '{"message": "أهلاً بك يا فندم، أنا سارة من خدمة العملاء وسأقوم بمساعدتك الآن."}'`;
      }

      const whatsappResolve = document.getElementById('dev-whatsapp-resolve-sample');
      if (whatsappResolve) {
        whatsappResolve.innerText = `curl -X POST "${origin}/api/v1/whatsapp/conversations/+201012345678/resolve/" \\\n  -H "X-API-Key: ${currentDeveloperKey}" \\\n  -H "Content-Type: application/json" \\\n  -d '{"resolution_notes": "تم حل مشكلة الفاتورة وتأكيد الدفع", "resume_ai": true}'`;
      }

      // Update React snippets with real API key
      const voiceReact = document.getElementById('dev-voice-widget-react-snippet');
      if (voiceReact) {
        voiceReact.innerText = `import React, { useState, useEffect, useRef } from 'react';

export default function VoiceAIWidget({ apiKey = "${currentDeveloperKey}", locale = "ar" }) {
  const [isOpen, setIsOpen] = useState(false);
  const [isCalling, setIsCalling] = useState(false);
  const iframeRef = useRef(null);

  useEffect(() => {
    const handleMessage = (e) => {
      if (!e.data || typeof e.data !== 'object') return;
      if (e.data.type === 'VOICE_CALL_STARTED') {
        setIsCalling(true);
        console.log('Voice call started for:', e.data.phone);
      } else if (e.data.type === 'VOICE_CALL_ENDED') {
        setIsCalling(false);
        console.log('Voice call ended. Duration seconds:', e.data.duration_seconds);
      }
    };
    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, []);

  const triggerDial = (phone) => {
    if (iframeRef.current && iframeRef.current.contentWindow) {
      iframeRef.current.contentWindow.postMessage({ type: 'VOICE_DIAL', phone }, '*');
    }
  };

  return (
    <div style={{ position: 'fixed', bottom: '24px', left: locale === 'ar' ? '24px' : 'auto', right: locale === 'ar' ? 'auto' : '24px', zIndex: 9999 }}>
      {isOpen && (
        <div style={{ marginBottom: '12px', borderRadius: '16px', overflow: 'hidden', boxShadow: '0 20px 40px rgba(0,0,0,0.2)' }}>
          <iframe
            ref={iframeRef}
            src={\`${origin}/embed/voice/?token=\${apiKey}&locale=\${locale}\`}
            width="380"
            height="540"
            frameBorder="0"
            allow="microphone;"
            title="Voice AI Assistant"
          />
        </div>
      )}
      <button
        onClick={() => setIsOpen(!isOpen)}
        style={{
          width: '56px', height: '56px', borderRadius: '50%',
          backgroundColor: '#7c3aed', color: '#fff', border: 'none',
          cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
          boxShadow: '0 8px 20px rgba(124,58,237,0.4)', fontSize: '24px'
        }}
      >
        {isOpen ? '✕' : '🎙️'}
      </button>
    </div>
  );
}`;
      }

      const chatReact = document.getElementById('dev-chat-widget-react-snippet');
      if (chatReact) {
        chatReact.innerText = `import React, { useState, useEffect } from 'react';

export default function OmnichannelChatHub({ apiKey = "${currentDeveloperKey}", tab = "live", locale = "ar" }) {
  const [unreadCount, setUnreadCount] = useState(0);

  useEffect(() => {
    const handleMessage = (e) => {
      if (!e.data || typeof e.data !== 'object') return;
      if (e.data.event === 'unread_message_count') {
        setUnreadCount(e.data.count || 0);
      }
    };
    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, []);

  const tabQuery = tab && tab !== 'live' ? \`&tab=\${tab}\` : '';
  const embedUrl = \`${origin}/embed/chat-hub/?token=\${apiKey}\${tabQuery}&locale=\${locale}\`;

  return (
    <div style={{ width: '100%', height: '800px', borderRadius: '16px', overflow: 'hidden', border: '1px solid #e2e8f0' }}>
      <iframe
        src={embedUrl}
        width="100%"
        height="100%"
        frameBorder="0"
        allow="camera; microphone; clipboard-read; clipboard-write;"
        title="Chatwoot Omnichannel Hub"
      />
    </div>
  );
}`;
      }

      const ccReact = document.getElementById('dev-cc-widget-react-snippet');
      if (ccReact) {
        ccReact.innerText = `import React from 'react';

export default function CallCenterSuiteEmbed({ apiKey = "${currentDeveloperKey}", section = "room", locale = "ar" }) {
  return (
    <div className="w-full h-full min-h-[800px] rounded-2xl overflow-hidden border border-slate-200">
      <iframe
        src={\`${origin}/embed/call-center/\${section}/?token=\${apiKey}&locale=\${locale}\`}
        width="100%"
        height="800"
        frameBorder="0"
        allow="microphone; camera; clipboard-read; clipboard-write;"
        title="Call Center AI Suite"
      />
    </div>
  );
}`;
      }
    }
  } catch (e) {
    console.error('Error loading developer keys:', e);
  }
}

// ==================== Tab Switching Helper ====================

function switchDevTab(tabGroupId, targetTabId) {
  const navContainer = document.getElementById(tabGroupId + '-nav');
  const panesContainer = document.getElementById(tabGroupId + '-panes');
  if (!navContainer || !panesContainer) return;

  // Update nav buttons: toggle active color classes while preserving custom sizing/font
  const buttons = navContainer.querySelectorAll('[data-tab-target]');
  buttons.forEach(btn => {
    const isTarget = btn.getAttribute('data-tab-target') === targetTabId;
    if (isTarget) {
      btn.classList.remove('bg-slate-100', 'bg-slate-200', 'hover:bg-slate-200', 'text-slate-700');
      btn.classList.add('bg-[#7c3aed]', 'text-white', 'shadow-2xs');
    } else {
      btn.classList.remove('bg-[#7c3aed]', 'text-white', 'shadow-2xs');
      btn.classList.add('bg-slate-100', 'hover:bg-slate-200', 'text-slate-700');
    }
  });

  // Update panes
  const panes = panesContainer.querySelectorAll('[data-tab-pane]');
  panes.forEach(pane => {
    if (pane.getAttribute('data-tab-pane') === targetTabId) {
      pane.classList.remove('hidden');
    } else {
      pane.classList.add('hidden');
    }
  });
}

// ==================== Snippet Copy Helper ====================

function copySnippet(elementId, successMsg) {
  const el = document.getElementById(elementId);
  if (!el) return;
  const text = (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') ? el.value : (el.innerText || el.textContent);
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(() => {
      showToast(successMsg || 'تم نسخ الكود بنجاح إلى الحافظة!', 'success');
    }).catch(() => {
      fallbackCopy(text, successMsg);
    });
  } else {
    fallbackCopy(text, successMsg);
  }
}

function fallbackCopy(text, successMsg) {
  const ta = document.createElement('textarea');
  ta.value = text;
  ta.style.position = 'fixed';
  ta.style.opacity = '0';
  document.body.appendChild(ta);
  ta.focus();
  ta.select();
  try {
    document.execCommand('copy');
    showToast(successMsg || 'تم نسخ الكود بنجاح!', 'success');
  } catch(e) {
    showToast('تعذر نسخ الكود تلقائياً', 'error');
  }
  document.body.removeChild(ta);
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
      redisBadge.className = 'px-2.5 py-0.5 text-xs font-bold rounded-full bg-emerald-100 text-emerald-800 border border-emerald-300 flex items-center gap-1.5';
      redisBadge.innerHTML = '<span class="w-2 h-2 rounded-full bg-emerald-500"></span><span>' + (window.t ? window.t('dev_redis_active', 'متزامن في الذاكرة (Redis Active)') : 'متزامن في الذاكرة (Redis Active)') + '</span>';
    } else {
      redisBadge.className = 'px-2.5 py-0.5 text-xs font-bold rounded-full bg-slate-100 text-slate-700 border border-slate-300 flex items-center gap-1.5';
      redisBadge.innerHTML = '<span class="w-2 h-2 rounded-full bg-slate-400"></span><span>' + (window.t ? window.t('dev_redis_empty', 'فارغ / غير محمل') : 'فارغ / غير محمل') + '</span>';
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
      btn.innerHTML = '<svg class="w-4 h-4 animate-spin inline-block mr-1.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10" stroke-opacity="0.25"></circle><path d="M12 2a10 10 0 0 1 10 10"></path></svg> <span>جاري الحفظ والمزامنة...</span>';
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
      showToast('تم حفظ واستبدال الذاكرة المنظمة ومزامنتها مع كاش Redis بنجاح!', 'success');
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
      btn.innerHTML = '<span>حفظ واستبدال فوري</span>';
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
      content.innerText = 'الـ JSON الحالي غير صالح، لا يمكن توليد المعاينة: ' + e.message;
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
    btn.innerHTML = '<svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>';
  } else {
    inp.type = 'password';
    btn.innerHTML = '<svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>';
  }
}

function copyDevApiKey() {
  copySnippet('dev-api-key-input', window.t ? window.t('dev_key_copied', 'تم نسخ مفتاح الـ API بنجاح لاستخدامه في تطبيقاتك!') : 'تم نسخ مفتاح الـ API بنجاح لاستخدامه في تطبيقاتك!');
}

function copyDevCurlSample() {
  copySnippet('dev-curl-sample', window.t ? window.t('dev_curl_copied', 'تم نسخ مثال cURL إلى الحافظة!') : 'تم نسخ مثال cURL إلى الحافظة!');
}

function copyEmbedChatSnippet() {
  copySnippet('dev-embed-chat-snippet', window.t ? window.t('dev_embed_chat_copied', 'تم نسخ كود تضمين الشات بنجاح') : 'تم نسخ كود تضمين الشات بنجاح');
}

function copyEmbedVoiceSnippet() {
  copySnippet('dev-embed-voice-snippet', window.t ? window.t('dev_embed_voice_copied', 'تم نسخ كود تضمين المساعد الصوتي بنجاح') : 'تم نسخ كود تضمين المساعد الصوتي بنجاح');
}

function copyDevCurlChatSendSample() {
  copySnippet('dev-curl-chat-send-sample', window.t ? window.t('dev_curl_chat_copied', 'تم نسخ كود إرسال الرسالة بنجاح') : 'تم نسخ كود إرسال الرسالة بنجاح');
}

function copyDevCurlDialSample2() {
  copySnippet('dev-curl-dial-sample-2', window.t ? window.t('dev_curl_dial_copied', 'تم نسخ كود المكالمة بنجاح') : 'تم نسخ كود المكالمة بنجاح');
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

// Re-render developer live context on language toggle
window.addEventListener('appLanguageChanged', () => {
  loadLiveContext();
});
