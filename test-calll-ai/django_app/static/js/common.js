/**
 * Common JavaScript for Enterprise Voice AI
 * Handles CSRF, Centrifugo Realtime, Global Header Balance, Language Toggle, and Sidebar.
 */

// CSRF Token Helper
function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === (name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

// Sidebar Collapse / Expand Toggle
function toggleSidebar() {
  const sidebar = document.getElementById('sidebar');
  const icon = document.getElementById('sidebar-toggle-icon');
  if (!sidebar) return;

  const isExpanded = sidebar.classList.contains('sidebar-expanded');
  if (isExpanded) {
    sidebar.classList.remove('sidebar-expanded');
    sidebar.classList.add('sidebar-collapsed');
    if (icon) icon.classList.add('rotate-180');
    localStorage.setItem('sidebar_collapsed', 'true');
  } else {
    sidebar.classList.remove('sidebar-collapsed');
    sidebar.classList.add('sidebar-expanded');
    if (icon) icon.classList.remove('rotate-180');
    localStorage.setItem('sidebar_collapsed', 'false');
  }
}

// Initialize Sidebar state from localStorage
function initSidebarState() {
  if (localStorage.getItem('sidebar_collapsed') === 'true') {
    const sidebar = document.getElementById('sidebar');
    const icon = document.getElementById('sidebar-toggle-icon');
    if (sidebar) {
      sidebar.classList.remove('sidebar-expanded');
      sidebar.classList.add('sidebar-collapsed');
    }
    if (icon) icon.classList.add('rotate-180');
  }
}

// Global Wallet Balance in Header
async function loadHeaderBalance() {
  try {
    const res = await fetch('/api/billing/wallet/');
    const data = await res.json();
    if (data.status === 'success') {
      const w = data.wallet;
      const hVal = document.getElementById('header-balance-val');
      const hCurr = document.getElementById('header-balance-curr');
      if (hVal) hVal.innerText = w.balance.toFixed(2);
      if (hCurr) hCurr.innerText = w.currency;
    }
  } catch (err) {
    console.debug('Header balance fetch error:', err);
  }
}

// Centrifugo Real-Time Connection
let globalCentrifugeClient = null;

async function initGlobalCentrifugo() {
  const statusEl = document.getElementById('centrifugo-status');
  try {
    const res = await fetch('/api/token/');
    const data = await res.json();
    if (data.status === 'success' && data.centrifugo_token && typeof Centrifuge !== 'undefined') {
      globalCentrifugeClient = new Centrifuge(data.centrifugo_ws_url, {
        token: data.centrifugo_token
      });

      globalCentrifugeClient.on('connecting', function() {
        if (statusEl) {
          statusEl.innerHTML = '<span class="w-2 h-2 rounded-full bg-amber-400"></span> Centrifugo: جاري الاتصال...';
        }
      });

      globalCentrifugeClient.on('connected', function() {
        if (statusEl) {
          statusEl.className = 'inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 font-medium shadow-sm';
          statusEl.innerHTML = '<span class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span> Centrifugo: متصل';
        }
      });

      globalCentrifugeClient.on('disconnected', function() {
        if (statusEl) {
          statusEl.className = 'inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-rose-50 text-rose-700 border border-rose-200 font-medium shadow-sm';
          statusEl.innerHTML = '<span class="w-2 h-2 rounded-full bg-rose-500"></span> Centrifugo: غير متصل';
        }
      });

      globalCentrifugeClient.connect();
    }
  } catch (e) {
    console.debug('Centrifugo init error:', e);
  }
}

// Toast Notifications Helper
function showToast(message, type = 'info') {
  let toastContainer = document.getElementById('toast-container');
  if (!toastContainer) {
    toastContainer = document.createElement('div');
    toastContainer.id = 'toast-container';
    toastContainer.className = 'fixed bottom-5 end-5 z-50 flex flex-col gap-2 pointer-events-none max-w-sm';
    document.body.appendChild(toastContainer);
  }

  const toast = document.createElement('div');
  const bgClass = type === 'success' 
    ? 'bg-emerald-800 text-white' 
    : type === 'error' 
    ? 'bg-rose-800 text-white' 
    : 'bg-[#680E23] text-white';

  toast.className = `p-3.5 rounded-2xl shadow-xl border border-white/20 text-xs font-semibold flex items-center gap-2 pointer-events-auto transition-all duration-300 transform translate-y-4 opacity-0 ${bgClass}`;
  toast.innerHTML = `<span>${type === 'success' ? '✅' : type === 'error' ? '⚠️' : 'ℹ️'}</span> <span>${escapeHtml(message)}</span>`;

  toastContainer.appendChild(toast);
  requestAnimationFrame(() => {
    toast.classList.remove('translate-y-4', 'opacity-0');
  });

  setTimeout(() => {
    toast.classList.add('translate-y-4', 'opacity-0');
    setTimeout(() => toast.remove(), 350);
  }, 4000);
}

// Bilingual Dictionary
const COMMON_I18N = {
  ar: {
    app_title: "المساعد الصوتي الذكي",
    app_subtitle: "منظومة الذكاء الاصطناعي",
    nav_voice: "غرفة المساعد الصوتي",
    nav_personas: "الشخصيات واللهجات",
    nav_rag: "قاعدة المعرفة RAG",
    nav_callcenter: "مركز الاتصالات والطوابير",
    nav_telephony: "الربط الهاتفي والسنترال",
    nav_crm: "ذاكرة وسجل العملاء",
    nav_campaigns: "حملات الاتصال والعملاء",
    nav_store: "متجر وأدوات MCP",
    nav_billing: "الرصيد والفواتير",
    nav_calls: "سجل المكالمات (CDR)",
    nav_partner: "الشريك والـ SaaS",
    nav_developer: "واجهات المطورين (API)",
    header_balance: "الرصيد:",
    role_admin: "مدير النظام",
    btn_logout: "🚪 خروج",
    switch_to: "English"
  },
  en: {
    app_title: "AI Voice Assistant",
    app_subtitle: "Enterprise Conversational AI",
    nav_voice: "Voice Room",
    nav_personas: "Personas & Dialects",
    nav_rag: "Knowledge Base (RAG)",
    nav_callcenter: "Call Center & Queues",
    nav_telephony: "SIP & PBX Trunks",
    nav_crm: "Customer Memory",
    nav_campaigns: "AI Campaigns",
    nav_store: "Tools & MCP Store",
    nav_billing: "Usage & Billing",
    nav_calls: "Call Logs (CDR)",
    nav_partner: "Partner Portal",
    nav_developer: "Developer APIs",
    header_balance: "Balance:",
    role_admin: "Super Admin",
    btn_logout: "🚪 Logout",
    switch_to: "العربية"
  }
};

let currentLang = localStorage.getItem('voice_app_lang') || 'ar';

function applyCommonLanguage(lang) {
  currentLang = lang;
  localStorage.setItem('voice_app_lang', lang);
  const isRtl = lang === 'ar';
  document.documentElement.dir = isRtl ? 'rtl' : 'ltr';
  document.documentElement.lang = lang;

  const langText = document.getElementById('lang-text');
  if (langText && COMMON_I18N[lang]) {
    langText.innerText = COMMON_I18N[lang].switch_to;
  }

  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    if (COMMON_I18N[lang] && COMMON_I18N[lang][key]) {
      el.innerText = COMMON_I18N[lang][key];
    }
  });
}

function toggleLanguage() {
  const next = currentLang === 'ar' ? 'en' : 'ar';
  applyCommonLanguage(next);
}

document.addEventListener('DOMContentLoaded', () => {
  initSidebarState();
  applyCommonLanguage(currentLang);
  loadHeaderBalance();
  initGlobalCentrifugo();
});
