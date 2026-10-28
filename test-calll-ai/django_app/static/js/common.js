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
window.globalCentrifugeClient = null;
let currentCentrifugoState = 'connected';

async function initGlobalCentrifugo() {
  const statusEl = document.getElementById('centrifugo-status');
  try {
    const res = await fetch('/api/token/');
    const data = await res.json();
    if (data.status === 'success' && data.centrifugo_token && typeof Centrifuge !== 'undefined') {
      globalCentrifugeClient = new Centrifuge(data.centrifugo_ws_url, {
        token: data.centrifugo_token
      });
      window.globalCentrifugeClient = globalCentrifugeClient;

      globalCentrifugeClient.on('connecting', function() {
        currentCentrifugoState = 'connecting';
        updateCentrifugoStatusBadge();
      });

      globalCentrifugeClient.on('connected', function() {
        currentCentrifugoState = 'connected';
        updateCentrifugoStatusBadge();
      });

      globalCentrifugeClient.on('disconnected', function() {
        currentCentrifugoState = 'disconnected';
        updateCentrifugoStatusBadge();
      });

      globalCentrifugeClient.connect();
    }
  } catch (e) {
    console.debug('Centrifugo init error:', e);
  }
}

function updateCentrifugoStatusBadge() {
  const statusEl = document.getElementById('centrifugo-status');
  if (!statusEl) return;
  const lang = getCurrentLanguage();
  if (currentCentrifugoState === 'connecting') {
    statusEl.className = 'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-50 border border-slate-200 text-slate-600 font-medium text-[11px] shadow-2xs';
    statusEl.innerHTML = `<span class="w-2 h-2 rounded-full bg-amber-400"></span> ${window.t('centrifugo_connecting', 'Centrifugo: جاري الاتصال...')}`;
  } else if (currentCentrifugoState === 'connected') {
    statusEl.className = 'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-50 border border-slate-200 text-slate-600 font-medium text-[11px] shadow-2xs';
    statusEl.innerHTML = `<span class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span> ${window.t('centrifugo_connected', 'Centrifugo: متصل')}`;
  } else {
    statusEl.className = 'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-50 border border-slate-200 text-slate-600 font-medium text-[11px] shadow-2xs';
    statusEl.innerHTML = `<span class="w-2 h-2 rounded-full bg-rose-500"></span> ${window.t('centrifugo_disconnected', 'Centrifugo: غير متصل')}`;
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
    ? 'bg-slate-900 text-white border border-emerald-500/30' 
    : type === 'error' 
    ? 'bg-slate-900 text-white border border-rose-500/30' 
    : 'bg-slate-900 text-white border border-slate-700';

  toast.className = `p-3 rounded-lg shadow-lg text-xs font-medium flex items-center gap-2 pointer-events-auto transition-all duration-300 transform translate-y-4 opacity-0 ${bgClass}`;
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

// Master Comprehensive Bilingual Dictionary (Arabic & English)
const APP_I18N = {
  ar: {
    // App & Header Branding
    app_title: "المساعد الصوتي الذكي",
    app_subtitle: "منظومة الذكاء الاصطناعي",
    header_system_title: "منظومة الذكاء الاصطناعي الهاتفي",
    header_balance: "الرصيد:",
    topup_balance: "شحن الرصيد",
    role_admin: "مدير النظام",
    btn_logout: "تسجيل الخروج",
    switch_to: "English",
    scroll_left: "تمرير لليسار",
    scroll_right: "تمرير لليمين",

    // Live Service Badges
    livekit_connected: "LiveKit: متصل",
    livekit_connecting: "LiveKit: جاري الاتصال...",
    livekit_disconnected: "LiveKit: غير متصل",
    centrifugo_connected: "Centrifugo: متصل",
    centrifugo_connecting: "Centrifugo: جاري الاتصال...",
    centrifugo_disconnected: "Centrifugo: غير متصل",

    // Sidebar & Navigation Portals
    nav_telephony_suite: "المساعد الصوتي والاتصالات",
    nav_chat_hub: "شات (Chatwoot Hub)",
    nav_billing: "الرصيد والفواتير",
    nav_developer: "واجهات المطورين (API)",
    nav_partner: "الشريك والـ SaaS",
    nav_voice: "غرفة المساعد الصوتي",
    nav_calls: "سجل المكالمات (CDR)",
    nav_rag: "قاعدة المعرفة RAG",
    nav_personas: "الشخصيات واللهجات",
    nav_crm: "ذاكرة وسجل العملاء",
    nav_store: "متجر وأدوات MCP",
    nav_campaigns: "حملات الاتصال والعملاء",
    nav_callcenter: "مركز الاتصالات والطوابير",
    nav_telephony: "الربط الهاتفي والسنترال",
    nav_hours: "مواعيد العمل والخطة البديلة",
    nav_business_hours: "مواعيد العمل والخطة البديلة",
    nav_whatsapp: "واتساب والمحادثات",
    nav_whatsapp_desk: "مكتب دعم الواتساب",

    // Common Buttons & Actions
    btn_save: "حفظ",
    btn_cancel: "إلغاء",
    btn_delete: "حذف",
    btn_edit: "تعديل",
    btn_close: "إغلاق",
    btn_update: "تحديث",
    btn_refresh: "تحديث السجل",
    btn_copy: "نسخ",
    btn_search: "بحث",
    btn_view_details: "عرض التفاصيل",
    btn_back: "رجوع",
    btn_confirm: "تأكيد",
    btn_apply: "تطبيق",

    // Voice Room
    metric_calls: "المكالمات النشطة",
    metric_latency: "زمن استجابة الـ AI",
    metric_rag: "فهرس المعرفة",
    metric_rag_status: "متصل ومحدث",
    metric_queue: "جاهزية الطوابير",
    voice_guardrail_title: "نطاق الإجابة المعتمد:",
    voice_guardrail_desc: "المساعدة الصوتية تستند حصرياً إلى مستندات قاعدة المعرفة وإجراءات الـ API المربوطة (Actions Engine)، وتعتذر فوراً بلهجة مصرية عن أي أسئلة خارج نطاقهما.",
    voice_status_ready: "جاهز لبدء المحادثة الصوتية الفورية",
    voice_sub_ready: "اضغط على زر \"بدء المحادثة\" لتفعيل الصوت والتواصل المباشر مع مستنداتك",
    voice_mic_label: "المايكروفون",
    voice_btn_start: "بدء المحادثة الصوتية",
    voice_btn_end: "إنهاء المحادثة",
    voice_btn_mute: "كتم المايك",
    voice_btn_unmute: "تفعيل المايك",
    voice_agent_speaking: "المساعد الصوتي يتحدث الآن...",
    voice_user_speaking: "جاري الاستماع لصوتك...",
    voice_connected: "المحادثة الصوتية نشطة ومباشرة",
    voice_connecting: "جاري الاتصال بغرفة الصوت...",
    voice_subtitles_empty: "اضغط على زر بدء المحادثة للتحدث فوراً مع المساعد الذكي",
    btn_outbound_ai_call: "📞 مكالمة هاتفية صادرة (AI Call)",
    floating_hint: "محادثة مستمرة عبر LiveKit",
    btn_full_room: "غرفة الصوت",

    // Usage & Billing
    billing_title: "حساب الاستخدام والرصيد",
    billing_subtitle: "نظام رصيد مسبق الدفع مع احتساب تكلفة الدقائق بالتقريب لأعلى دقيقة",
    billing_btn_refresh: "تحديث الرصيد",
    billing_btn_topup: "شحن الرصيد",
    billing_balance_title: "الرصيد المتاح حالياً",
    billing_ready_badge: "جاهز للاتصال",
    billing_rate_label: "التسعيرة الحالية للدقيقة:",
    billing_minute_ceiling: "(تقريب لأعلى دقيقة مرتفع)",
    billing_add_funds: "+ إضافة رصيد للمحفظة",
    billing_deposited: "إجمالي المبالغ المشحونة",
    billing_spent: "إجمالي المستهلك بالمكالمات",
    billing_minutes: "إجمالي الدقائق المحتسبة",
    billing_ledger_title: "سجل الحركات المالية (Ledger)",
    billing_ledger_filter_all: "كافة الحركات",
    billing_ledger_filter_topup: "عمليات الشحن فقط",
    billing_ledger_filter_calls: "استهلاك المكالمات فقط",
    billing_th_date: "التاريخ والوقت",
    billing_th_type: "نوع الحركة",
    billing_th_amount: "المبلغ",
    billing_th_balance: "الرصيد بعد الحركة",
    billing_th_billed_mins: "الدقائق المحتسبة",
    billing_th_rate: "التسعيرة المطبقة",
    billing_th_desc: "البيان والتفاصيل",
    billing_modal_topup_title: "شحن رصيد المحفظة الفوري",
    billing_modal_amt_label: "حدد مبلغ الشحن (USD $):",
    billing_modal_confirm: "تأكيد الشحن الفوري",
    badge_topup: "شحن رصيد",
    badge_deduction: "خصم مكالمة",
    no_transactions: "لا توجد حركات مالية مسجلة حتى الآن.",

    // CDR / Call Logs
    calls_title: "سجل كافة المكالمات (CDR)",
    calls_subtitle: "عرض شامل لكافة المكالمات الواردة والصادرة مع فلاتر ذكية وإحصائيات الاستهلاك المالي ومشغل التسجيلات",
    calls_btn_refresh: "تحديث السجل",
    calls_stat_total: "إجمالي المكالمات",
    calls_stat_minutes: "الدقائق المحتسبة",
    calls_stat_cost: "التكلفة الإجمالية",
    calls_stat_seconds: "إجمالي الثواني الصوتية",
    calls_filters_title: "فلاتر البحث والتصفية المتقدمة (CDR Filters)",
    calls_filters_reset: "✕ إعادة تعيين الفلاتر",
    calls_filter_search_label: "بحث نصي",
    calls_filter_search_placeholder: "رقم الهاتف، اسم العميل، اسم الغرفة، أو الهدف...",
    calls_filter_direction: "اتجاه المكالمة",
    calls_filter_duration: "مدة المكالمة",
    calls_filter_type_label: "تصفية المكالمات:",
    calls_type_all: "الكل",
    calls_type_ai: "مكالمات الذكاء الاصطناعي",
    calls_type_internal: "مكالمات الموظفين الداخلية",
    calls_filter_date: "النطاق الزمني:",
    calls_date_all: "الكل",
    calls_date_today: "اليوم",
    calls_date_7days: "آخر 7 أيام",
    calls_date_month: "هذا الشهر",
    calls_th_time: "وقت المكالمة",
    calls_th_direction: "الاتجاه",
    calls_th_party: "الطرف / العميل",
    calls_th_room: "الغرفة / المساعد",
    calls_th_duration: "المدة الفعلية",
    calls_th_billed_mins: "الدقائق المحتسبة",
    calls_th_cost: "التكلفة",
    calls_th_actions: "الإجراءات",
    calls_dir_all: "جميع الاتجاهات",
    calls_dir_inbound: "مكالمة واردة",
    calls_dir_outbound_ai: "صادرة (ذكاء اصطناعي)",
    calls_dir_outbound_agent: "صادرة (موظف)",
    calls_dir_internal: "مكالمة داخلية (موظفين / سنترال)",
    calls_dur_all: "جميع المدد",
    calls_dur_under_1m: "أقل من دقيقة (< 60ث)",
    calls_dur_1m_5m: "من 1 إلى 5 دقائق",
    calls_dur_over_5m: "أكثر من 5 دقائق",
    calls_modal_title: "تفاصيل المكالمة والملخص الذكي",
    calls_modal_subtitle: "جلسة المكالمة",
    calls_modal_rec_ai: "تسجيل محادثة الذكاء الاصطناعي (AI Agent):",
    calls_modal_rec_human: "تسجيل محادثة الموظف البشري بعد التحويل:",
    calls_modal_mp3_download: "تحميل MP3",
    calls_modal_wav_download: "تحميل التسجيل (WAV)",
    calls_modal_summary_title: "ملخص المكالمة التراكمي (AI Summary):",
    calls_modal_transcript_title: "نص المحادثة الكامل (Full Transcript):",
    calls_modal_close: "إغلاق",
    badge_inbound: "واردة",
    badge_outbound_ai: "صادرة AI",
    badge_outbound_agent: "صادرة موظف",
    badge_internal: "داخلية (موظفين)",
    badge_internal_test: "اختبار داخلي",
    badge_transferred: "محولة لموظف",
    minute_suffix: "دقيقة",
    btn_details: "التفاصيل",
    no_calls_found: "لا توجد مكالمات تطابق معايير البحث والتصفية المحددة.",

    // CRM / Customer Memory
    crm_title: "ذاكرة العميل الذكية (Two-Tier Distilled Memory)",
    crm_subtitle: "تجمع بين الذاكرة الدائمة والذاكرة اللحظية معزولة ومخصصة لكل رقم عميل يتصل بالنظام.",
    crm_refresh: "تحديث",
    crm_reset: "تصفير الذاكرة",
    crm_check_label: "فحص ذاكرة رقم:",
    crm_search_placeholder: "بحث برقم الهاتف أو الاسم...",
    crm_active_badge: "العميل المعروض:",
    crm_card_permanent_title: "الملف والبيانات الدائمة",
    crm_card_permanent_tag: "تراكمية",
    crm_card_call_title: "ذاكرة المكالمات (Call Memory)",
    crm_card_wa_title: "ذاكرة الواتساب (WhatsApp Memory)",
    crm_card_wa_tag: "24/7 نشط",
    crm_accordion_title: "أرشيف المكالمات السابقة والمستخلصة",
    crm_no_calls: "لا توجد مكالمات سابقة مسجلة.",

    // RAG / Knowledge Base
    rag_title: "مستندات قاعدة المعرفة (RAG Knowledge Base)",
    rag_subtitle: "ارفع ملفاتك (PDF, DOCX, TXT) ليتم تضمينها وفهرستها دلالياً في PostgreSQL باستخدام Gemini text-embedding-004.",
    rag_btn_choose: "اختر ملفاً (PDF/DOCX/TXT)",
    rag_btn_upload: "رفع ومعالجة",
    rag_th_name: "اسم المستند",
    rag_th_type: "النوع",
    rag_th_chunks: "المقاطع الدلالية (Chunks)",
    rag_th_date: "تاريخ الفهرسة",
    rag_th_actions: "إجراءات",
    rag_empty: "جاري تحميل المستندات...",

    // Personas & Voices
    personas_title: "إدارة الشخصيات واللهجات وأصوات الذكاء الاصطناعي",
    personas_subtitle: "اختر من بين الشخصيات المتاحة لتفعيلها فوراً في المكالمات الحية، أو خصص النبرة واللهجة والصوت",
    personas_catalog_title: "الشخصيات المتاحة للمحادثات (Available AI Personas)",
    personas_catalog_hint: "اضغط \"تفعيل للمكالمات\" لاختيار الشخصية المعتمدة للمساعد",
    personas_btn_new: "إنشاء شخصية جديدة",
    personas_studio_title: "استوديو تخصيص الشخصية المحددة",
    personas_studio_subtitle: "تعديل الخامة الصوتية من Google (30 خامة)، الدور، والتعليمات البرمجية",
    personas_current_label: "الشخصية الحالية:",
    personas_field_gender_dialect: "النوع واللغة واللهجة",
    personas_field_gender: "النوع",
    personas_field_lang: "اللغة",
    personas_field_dialect: "اللهجة",
    personas_field_voice: "صوت Google الرسمي",
    personas_field_role: "الدور والشخصية",
    personas_field_style: "أسلوب الإلقاء والنبرة",
    personas_field_instructions: "تعليمات وتوجيهات خاصة إضافية للشخصية (Custom Prompt Instructions - اختياري):",
    personas_btn_save: "حفظ وتطبيق على المكالمات",
    personas_btn_delete: "حذف البروفايل",

    // Call Center & Queues
    cc_subtab_employees: "دليل الموظفين والتحويلات",
    cc_subtab_queues: "طوابير الانتظار ومجموعات العمل",
    cc_subtab_recordings: "سجل مكالمات الموظفين والتسجيلات",
    cc_softphone_title: "دليل تحويلات الموظفين ومنظومة الاتصال الداخلي (WebRTC Softphone)",
    cc_softphone_desc: "أضف موظفين جدد وتحويلات داخلية، واتصل مباشرة بأي موظف أو طابور عبر WebRTC المباشر من المتصفح.",
    cc_btn_new_employee: "موظف جديد",
    cc_btn_new_queue: "طابور جديد",
    cc_call_calling: "جاري الاتصال...",
    cc_call_sync: "يتم الاتصال والمزامنة عبر WebRTC...",
    cc_call_end: "إنهاء المكالمة",
    cc_th_employee: "الموظف",
    cc_th_extension: "التحويلة الداخلية",
    cc_th_dept: "القسم",
    cc_th_presence: "حالة التواجد",
    cc_th_protocol: "بروتوكول الصوت",
    cc_th_actions: "إجراءات",
    cc_th_queue_name: "اسم الطابور",
    cc_th_strategy: "استراتيجية التوزيع",
    cc_th_members: "الأعضاء الملحقين",
    cc_th_waiting: "المكالمات بالانتظار",
    cc_th_completed: "المكالمات المنجزة",

    // Telephony & PBX
    tel_subtab_outbound: "المكالمات الصادرة والجذع الخارجي (SIP Trunk)",
    tel_subtab_pbx: "سنترالات Issabel و Asterisk",
    tel_subtab_dids: "أرقام DID المخصصة والمستأجرين",
    tel_outbound_title: "المكالمات الصادرة والجذع الخارجي (Generic Outbound SIP Trunk & AI Auto-Dialer)",
    tel_outbound_desc: "اربط أي مزود اتصالات سحابي خارجي مثل Telnyx أو Twilio لتمكين الذكاء الاصطناعي والموظفين من الاتصال بأرقام الهواتف مباشرة.",
    tel_btn_ai_call: "اتصال جديد عبر الـ AI",
    tel_trunk_status_title: "حالة الجذع في LiveKit",
    tel_trunk_not_configured: "غير مهيأ",
    tel_field_name: "اسم الجذع / المزود",
    tel_field_host: "خادم الـ SIP (Host / Termination URI) *",
    tel_field_user: "اسم مستخدم المصادقة (SIP Username)",
    tel_field_pass: "كلمة المرور (SIP Password)",
    tel_field_caller_id: "الرقم المعتمد كمتصل (Caller ID Number)",
    tel_field_transport: "بروتوكول النقل (Transport) والمنفذ",
    tel_btn_save_trunk: "حفظ وتفعيل مسار الاتصال",
    tel_pbx_title: "ربط سنترالات PBX المحلية (Issabel & Asterisk)",
    tel_pbx_btn_new: "ربط سنترال PBX جديد",
    tel_issabel_code_btn: "كود إعدادات Issabel الجاهز",

    // Business Hours
    hours_title: "مواعيد العمل والخطة البديلة (Business Hours)",
    hours_subtitle: "حدد أيام وساعات العمل الرسمية، وكيفية تعامل النظام تلقائياً مع المكالمات الواردة خارج ساعات العمل.",
    hours_status_label: "الحالة الآن:",
    hours_disabled: "معطل",
    hours_enabled: "مفعل",
    hours_schedule_title: "جدول أيام وساعات العمل الأسبوعية",
    hours_timezone: "المنطقة الزمنية:",
    hours_th_day: "اليوم",
    hours_th_type: "نوع اليوم",
    hours_th_start: "وقت البدء",
    hours_th_end: "وقت الانتهاء",
    hours_th_status: "الحالة",
    hours_plan_title: "خطة التعامل خارج أوقات العمل",
    hours_choose_action: "اختر إجراء الرد على المتصل خارج أوقات العمل:",
    hours_action_ai: "نطق رسالة ذكية بصوت الذكاء الاصطناعي (AI Message)",
    hours_action_ai_desc: "ينطق المساعد الصوتي رسالة اعتذار رسمية مخصصة للعميل ثم يغلق المكالمة بلباقة.",
    hours_action_audio: "تشغيل ملف صوتي مسجل مسبقاً (Audio File)",
    hours_action_audio_desc: "يتم بث ملف صوتي مرفوع (MP3/WAV) مباشرة للمتصل ثم إنهاء المكالمة.",
    hours_ai_msg_label: "نص الرسالة المنطوقة للمتصل:",
    hours_restore_default: "استعادة النص الافتراضي",
    hours_audio_upload_label: "رفع ملف صوتي مسجل (MP3 أو WAV):",
    hours_btn_choose_audio: "اختر ملف صوتي من جهازك",
    hours_btn_save: "حفظ وتطبيق مواعيد العمل",
    day_saturday: "السبت",
    day_sunday: "الأحد",
    day_monday: "الاثنين",
    day_tuesday: "الثلاثاء",
    day_wednesday: "الأربعاء",
    day_thursday: "الخميس",
    day_friday: "الجمعة",
    day_workday: "يوم عمل",
    day_holiday: "عطلة",
    day_official_work: "دوام رسمي",
    day_official_holiday: "عطلة رسمية",
    hours_open_now: "مفتوح الآن لاستقبال المكالمات 🟢",
    hours_closed_now: "مغلق حالياً (الرد الآلي مفعل) 🔴",
    hours_not_active: "الجدول غير مفعل (المساعد يستقبل دائماً)",

    // Campaigns
    camp_title: "حملات الاتصال وإدارة العملاء (Campaigns & Leads CRM)",
    camp_subtitle: "ارفع قوائم العملاء بصيغ متعددة (Excel, CSV, TXT, JSON)، ونظمهم داخل CRM تفاعلي، وأطلق حملات الاتصال المتوازية بفرز واستخلاص ذكي فوري.",
    camp_btn_inngest: "مراقبة Inngest",
    camp_btn_refresh: "تحديث",
    camp_btn_dnc: "قائمة عدم الاتصال (DNC)",
    camp_btn_new: "إنشاء حملة جديدة",
    camp_stat_total: "إجمالي الحملات",
    camp_stat_contacts: "إجمالي جهات الاتصال",
    camp_stat_answered: "تم الرد هاتفياً",
    camp_stat_whatsapp: "رسائل واتساب مرسلة",
    camp_stat_hot: "عملاء مهتمون",
    camp_select_label: "اختر الحملة:",
    camp_btn_start: "بدء التنفيذ",
    camp_btn_pause: "إيقاف مؤقت",
    camp_btn_reset: "إعادة ضبط",
    camp_btn_export: "تصدير CSV",
    camp_th_name: "الاسم",
    camp_th_phone: "رقم الهاتف",
    camp_th_status: "حالة الاتصال",
    camp_th_interest: "مستوى الاهتمام",
    camp_th_duration: "المدة",
    camp_th_retries: "المحاولات",
    camp_th_actions: "إجراءات",

    // Store / MCP
    store_title: "متجر وأدوات MCP",
    store_subtitle: "ربط وإدارة خوادم الأدوات الخارجية (Multi-MCP Support) لتمكين المساعد الصوتي من استدعاء دوالها أثناء المكالمات.",
    store_btn_sync_all: "تحديث الكل",
    store_btn_new_server: "إضافة خادم MCP جديد",
    store_servers_title: "خوادم MCP المربوطة:",
    store_tools_title: "الدوال المكتشفة من الخوادم النشطة:",
    store_tools_hint: "متاحة تلقائياً للمساعد الصوتي أثناء المكالمات الصوتية",
    store_modal_title: "إعدادات خادم FastMCP الخارجي",

    // Developer API
    dev_title: "واجهات المطورين المباشرة (Direct Developer API & Keys)",
    dev_subtitle: "ادمج المساعد الصوتي والذكاء الاصطناعي وخوادم FastMCP وبدء مكالمات WebRTC مباشرة في موقعك أو تطبيقاتك الخاصة.",
    dev_btn_docs: "فتح التوثيق التفاعلي (Scalar Docs)",
    dev_btn_refresh: "تحديث",
    dev_key_title: "مفتاح الـ API النشط للتطبيقات (Personal Live API Key)",
    dev_btn_rotate: "تدوير المفتاح (Regenerate Key)",
    dev_btn_copy: "نسخ",
    dev_created_at: "تاريخ الإنشاء:",
    dev_last_used: "آخر استخدام:",
    dev_account_sample: "استعلام الحساب (Get Account):",
    dev_dial_sample: "إجراء مكالمة صادرة بالذكاء الاصطناعي (Dial Call):",
    dev_context_title: "الذاكرة المنظمة الحية للنشاط (Structured Live Context)",
    dev_context_desc: "بيانات نشاطك الحية والمنظمة (الفروع، مناطق التوصيل، المنيو). تُحقن فوراً في بداية كل مكالمة من الذاكرة اللحظية (Redis < 2ms).",
    dev_template_restaurant: "قالب مطعم",
    dev_format_json: "تنسيق الـ JSON",
    dev_preview_prompt: "معاينة ما يراه الـ AI",
    dev_clear: "مسح",
    dev_save_context: "حفظ واستبدال فوري",

    // Partner Portal
    partner_title: "برنامج الشركاء وحلول الـ SaaS (Partner & Reseller Portal)",
    partner_subtitle: "إدارة عملاء الساس التابعين، مفاتيح الربط البرمجي (Headless API)، وتتبع استهلاك المكالمات المجمعة.",
    partner_btn_docs: "وثائق الـ API للمطورين",
    partner_btn_quickguide: "الدليل السريع",
    partner_btn_refresh: "تحديث البيانات",
    partner_kpi_balance: "رصيد محفظة الشريك المتاحة",
    partner_kpi_rate: "سعر الدقيقة المخصص لك",
    partner_kpi_clients: "إجمالي عملاء الساس النشطين",
    partner_kpi_minutes: "إجمالي الدقائق المستهلكة لعملائك",
    partner_api_title: "بيانات الربط البرمجي الخلفي (Headless API Access)",
    partner_code_label: "كود الشريك (Partner Code)",
    partner_key_label: "مفتاح الوصول الرئيسي (X-Partner-Key)",
    partner_webhook_label: "رابط استقبال الـ Webhook الخاص بنظامك",
    partner_shared_mcp_title: "خادم الـ MCP الموروث لعملائك (Shared SaaS Tools)",

    // WhatsApp Omnichannel & Desk
    whatsapp_page_title: "محادثات الواتساب والموظف الذكي 24/7",
    whatsapp_page_desc: "صندوق محادثات الواتساب الموحد (Omnichannel Inbox): استعراض كامل لمحادثات العملاء، مراقبة ردود الذكاء الاصطناعي، والرد البشري المباشر.",
    whatsapp_gateway_checking: "جارٍ التحقق من البوابة...",
    whatsapp_gateway_connected: "بوابة الواتساب: متصلة 🟢",
    whatsapp_gateway_disconnected: "بوابة الواتساب: غير متصلة 🔴",
    whatsapp_gateway_error: "خطأ في فحص البوابة",
    whatsapp_sync_phone: "مزامنة شات الهاتف",
    whatsapp_syncing: "جارٍ المزامنة...",
    whatsapp_sync_title: "مزامنة كافة محادثات ورسائل هاتفك الحقيقية المسجلة في واتساب",
    whatsapp_connect_qr: "ربط واتساب (QR Code)",
    whatsapp_refresh_chats: "تحديث المحادثات",
    whatsapp_test_send: "تجربة إرسال",
    whatsapp_search_placeholder: "بحث بالاسم أو رقم الهاتف...",
    whatsapp_filter_all: "الكل",
    whatsapp_filter_ai: "AI نشط",
    whatsapp_filter_manual: "يدوي",
    whatsapp_loading_convs: "جارٍ تحميل المحادثات...",
    whatsapp_active_convs: "المحادثات النشطة:",
    whatsapp_auto_refresh: "تحديث تلقائي",
    whatsapp_no_convs: "لا توجد محادثات مطابقة",
    whatsapp_no_convs_desc: "ستظهر المحادثات هنا فور بدء العملاء بمراسلتكم على الواتساب.",
    whatsapp_new_customer: "عميل واتساب جديد",
    whatsapp_start_conv: "بدء المحادثة",
    whatsapp_messages_count: "رسائل",
    whatsapp_badge_escalation: "⚠️ شكوى عميل",
    whatsapp_badge_call: "📞 مكالمة",
    whatsapp_badge_ai: "🟢 AI",
    whatsapp_badge_manual: "⏸️ يدوي",
    whatsapp_empty_title: "اختر محادثة من القائمة للبدء",
    whatsapp_empty_desc: "اضغط على أي عميل من القائمة الجانبية للاطلاع على تاريخ المحادثة بالكامل، ومتابعة ردود الموظف الذكي، أو التدخل والرد يدوياً في أي وقت.",
    whatsapp_edit_contact: "تعديل",
    whatsapp_edit_contact_title: "تعديل اسم أو رقم العميل",
    whatsapp_call_history: "مكالمات سابقة مسجلة (اضغط للعرض)",
    whatsapp_active_status: "محادثة نشطة",
    whatsapp_ai_active: "الرد الذكي: نشط",
    whatsapp_ai_manual: "وضع الموظف البشري (AI متوقف)",
    whatsapp_ai_toggle_title: "تفعيل أو إيقاف الرد الآلي للذكاء الاصطناعي لهذا العميل",
    whatsapp_refresh_messages: "تحديث الرسائل",
    whatsapp_call_context: "سياق المكالمات الهاتفية السابقة:",
    whatsapp_escalated_tag: "محول للدعم البشري",
    whatsapp_escalation_reason: "سبب التصعيد:",
    whatsapp_escalation_fallback: "طلب دعم بشري / شكوى",
    whatsapp_ai_summary_prefix: "📌 ملخص الذكاء الاصطناعي: ",
    whatsapp_escalation_summary_fallback: "العميل بانتظار استلام الموظف البشري للمحادثة.",
    whatsapp_ai_active_btn: "الرد الذكي: نشط (اضغط للإيقاف)",
    whatsapp_ai_manual_btn: "وضع الموظف البشري (AI متوقف)",
    whatsapp_resolve_ai: "حل المشكلة واستئناف الـ AI",
    whatsapp_resolve_ai_title: "حل المشكلة وإعادة تفعيل الرد الآلي للذكاء الاصطناعي",
    whatsapp_loading_messages: "جارٍ جلب المحادثة...",
    whatsapp_no_messages: "لا توجد رسائل سابقة في هذه المحادثة بعد.",
    whatsapp_reply_placeholder: "اكتب رداً يدوياً على العميل عبر الواتساب...",
    whatsapp_btn_send: "إرسال",
    whatsapp_gateway_notice: "يتم الإرسال فوراً لرقم العميل عبر بوابة Evolution API المربوطة.",
    whatsapp_sent_success: "✓ تم إرسال رسالتك وتوصيلها للواتساب بنجاح",
    whatsapp_customer: "العميل",
    whatsapp_bubble_ai: "🤖 الموظف الذكي",
    whatsapp_bubble_human: "👤 موظف بشري",
    whatsapp_bubble_sent: "✓ تم الإرسال للواتساب",
    whatsapp_generating: "جارٍ التوليد...",
    whatsapp_qr_title: "ربط رقم الواتساب (QR Code)",
    whatsapp_qr_desc: "امسح الكود لربط رقمك الشخصي أو رقم العمل",
    whatsapp_qr_checking: "جارٍ فحص حالة الاتصال بالسيرفر...",
    whatsapp_qr_btn_generate: "توليد كود QR للربط",
    whatsapp_qr_btn_disconnect: "قطع الاتصال",
    whatsapp_qr_connected_title: "واتساب متصل ويعمل بنجاح",
    whatsapp_qr_connected_desc: "البوابة جاهزة لإرسال واستقبال الرسائل على مدار الساعة.",
    whatsapp_qr_scan_inst1: "امسح الكود بكاميرا تطبيق واتساب",
    whatsapp_qr_scan_inst2: "الإعدادات > الأجهزة المرتبطة > ربط جهاز",
    whatsapp_qr_error_prefix: "تعذر جلب رمز QR:",
    whatsapp_edit_title: "تعديل بيانات العميل",
    whatsapp_label_name: "اسم العميل / النشاط:",
    whatsapp_placeholder_name: "مثال: أحمد السيد / شركة النور",
    whatsapp_label_phone: "رقم هاتف العميل (الصريح):",
    whatsapp_placeholder_phone: "مثال: 01019431866 أو 201019431866+",
    whatsapp_phone_hint: "يُستخدم لتحديد رقم الهاتف الفعلي للعميل وعرضه في بطاقة المحادثة.",
    whatsapp_btn_save_changes: "حفظ التعديلات",
    whatsapp_test_title: "تجربة محرك الواتساب و LangGraph",
    whatsapp_test_phone_label: "رقم هاتف العميل (مع كود الدولة):",
    whatsapp_test_phone_placeholder: "مثال: 201012345678 أو 966501234567",
    whatsapp_test_name_label: "اسم العميل (اختياري):",
    whatsapp_test_type_label: "نوع الاختبار:",
    whatsapp_test_opt_langgraph: "تشغيل LangGraph تلقائياً (محاكاة متابعة ما بعد المكالمة)",
    whatsapp_test_opt_direct: "إرسال رسالة مباشرة مخصصة",
    whatsapp_test_msg_label: "نص الرسالة المخصصة:",
    whatsapp_test_msg_placeholder: "اكتب نص الرسالة التجريبية هنا...",
    whatsapp_test_btn_send: "إرسال التجربة",
    whatsapp_support_request: "طلب دعم بشري",
    whatsapp_waiting_reply: "بانتظار الرد",
    whatsapp_active_conv: "محادثة نشطة",

    // Desk Tier 2
    desk_page_title: "مكتب دعم عملاء الواتساب (الدعم البشري Tier 2)",
    desk_badge_ring: "رنين جماعي & استلام فوري",
    desk_page_desc: "شاشة العمل الموحدة لموظفي الدعم لاستقبال وتوزيع محادثات الشكاوى والتحويل من الذكاء الاصطناعي",
    desk_presence_online: "حالتي: متصل ومستعد للاستلام",
    desk_presence_break: "حالتي: في استراحة (الصوت متوقف)",
    desk_sound_on: "الصوت مفعل",
    desk_sound_off: "الصوت مكتوم",
    desk_sound_title: "كتم/تفعيل صوت الرنين",
    desk_queue_title: "طابور الرنين العام",
    desk_queue_subtitle: "ترن لدى الجميع (الأسبقية للاستلام)",
    desk_queue_empty: "لا توجد محادثات معلقة في الطابور حالياً.",
    desk_queue_empty_desc: "عند حدوث أي شكوى أو طلب تحويل، سترن المحادثة هنا فوراً.",
    desk_badge_urgent: "عاجل جداً",
    desk_badge_support: "طلب دعم",
    desk_btn_claim: "استلام المحادثة",
    desk_my_chats_title: "محادثاتي المستلمة",
    desk_my_chats_subtitle: "محادثات قيد الدعم المباشر",
    desk_my_chats_empty: "لم تستلم أي محادثة بعد. اضغط «استلام» على أي محادثة واردة من الطابور لبدء خدمتها.",
    desk_empty_title: "اختر محادثة من قائمة «محادثاتي المستلمة»",
    desk_empty_desc: "أو اضغط «استلام المحادثة» من طابور الرنين العام على اليمين لسحب طلب العميل والرد عليه مباشرة.",
    desk_active_badge: "قيد الدعم البشري المباشر",
    desk_btn_release: "إعادة للطابور",
    desk_btn_release_title: "إعادة المحادثة للطابور العام لترن عند الزملاء",
    desk_btn_resolve: "حل المشكلة واستئناف الـ AI",
    desk_btn_resolve_title: "إنهاء التذكرة واستئناف الرد الآلي للذكاء الاصطناعي",
    desk_brief_escalation: "شكوى / تصعيد",
    desk_brief_reason: "سبب التصعيد:",
    desk_brief_sla: "مهلة الرد:",
    desk_reply_placeholder: "اكتب رداً مباشراً على العميل على الواتساب...",
    desk_bubble_customer: "👤 العميل",
    desk_bubble_agent: "👨‍💻 أنت (الموظف البشري)",
    desk_bubble_ai: "🤖 الذكاء الاصطناعي",
    desk_summary_fallback: "العميل بانتظار استجابتك ومساعدتك.",

    // Dynamic Module Strings (Billing, CRM, RAG, Store, Call Center)
    billing_per_minute: "/ دقيقة",
    billing_status_ready: "جاهز للاتصال",
    billing_status_low: "رصيد غير كافٍ - يرجى الشحن",
    billing_no_transactions: "لا توجد حركات مالية مسجلة حتى الآن.",
    billing_type_topup: "شحن رصيد",
    billing_type_deduction: "خصم مكالمة",
    billing_type_adjustment: "تسوية رصيد",
    billing_btn_depositing: "جاري الإيداع...",
    billing_ledger_failed: "فشل تحميل سجل المعاملات.",
    minute_short: "د",
    second_short: "ث",
    second_suffix: "ثانية",
    recent_time: "مؤخراً",

    // CRM Dynamic Strings
    crm_default_browser_session: "جلسة المتصفح الافتراضية",
    crm_no_permanent_data: "لا توجد بيانات دائمة مسجلة لهذا الرقم بعد. سيتعلم المساعد اسمه وتفضيلاته تلقائياً أثناء المكالمات!",
    crm_label_name: "الاسم:",
    crm_label_phone: "الهاتف:",
    crm_label_address: "العنوان:",
    crm_label_prefs: "التفضيلات:",
    crm_label_notes: "ملاحظات:",
    crm_no_specific_details: "لا توجد تفاصيل محددة بعد.",
    crm_calls_count_suffix: "مكالمات",
    crm_prev_call: "مكالمة سابقة",
    crm_last_call_label: "آخر مكالمة:",
    crm_intent_label: "النية:",
    crm_sentiment_label: "الانطباع:",
    crm_agreed_label: "ما تم الاتفاق عليه:",
    crm_no_calls_recorded: "لا توجد مكالمات هاتفية مسجلة لهذا الرقم حتى الآن.",
    crm_last_chat_label: "آخر تفاعل شات:",
    crm_stage_label: "مرحلة العميل:",
    crm_last_incoming_label: "آخر رسالة واردة:",
    crm_last_outgoing_label: "آخر رد مرسل:",
    crm_no_wa_recorded: "لا توجد محادثات واتساب مسجلة بعد لهذا الرقم.",
    crm_no_prev_calls: "لا توجد مكالمات سابقة مسجلة لهذا الرقم.",
    call_dir_inbound: "واردة",
    call_dir_outbound_ai: "صادرة (AI)",
    call_dir_outbound_agent: "صادرة (موظف)",
    crm_call_goal_prefix: "الهدف: ",
    crm_completed_no_summary: "مكالمة مكتملة بدون ملخص",

    // Store Dynamic Strings
    store_no_servers_title: "لا توجد خوادم MCP مربوطة حالياً",
    store_no_servers_desc: "يمكنك ربط خادم أدوات خارجي عبر بروتوكول FastMCP SSE لتمكين المساعد الصوتي من استدعاء دواله أثناء المكالمات.",
    store_btn_new_server_link: "ربط خادم MCP جديد",
    store_status_active: "مفعل للمكالمات",
    store_status_disabled: "معطل",
    store_btn_disable: "تعطيل",
    store_btn_enable: "تفعيل",
    store_discovered_tools: "الدوال المكتشفة:",
    store_synced_at: "مزامنة:",
    store_never_synced: "لم تتم المزامنة",
    store_btn_sync_hint: "فحص وتحديث الأدوات",
    store_btn_edit_hint: "تعديل الإعدادات",
    store_btn_delete_hint: "حذف الخادم",
    store_no_tools_discovered: "لا توجد أدوات مكتشفة من الخوادم المفعلة حالياً. اضغط على زر التحديث 🔄 لأي خادم لقراءة دواله.",
    store_no_desc: "بدون وصف",
    store_params_label: "المعاملات:",
    store_tools_count_suffix: "أداة",

    // RAG Dynamic Strings
    rag_no_docs: "لا توجد مستندات مرفوعة بعد. ارفع أول ملف لبدء الإجابة منه!",
    rag_status_pending: "قيد الفهرسة",
    rag_status_failed: "فشل",
    rag_status_ready: "جاهز",
    rag_chunks_suffix: "مقطع",
    rag_delete_doc: "حذف المستند",
    rag_processing: "جاري المعالجة والتضمين...",
    rag_extracting: "جاري استخراج النصوص وتوليد التضمينات الدلالية عبر Gemini...",
    rag_confirm_delete: "هل أنت متأكد من رغبتك في حذف هذا المستند وحذف جميع مقاطعه الدلالية؟",

    // Call Center Dynamic Strings
    cc_no_employees: "لا يوجد موظفون مسجلون بعد في النظام.",
    cc_status_ready: "متاح (Ready)",
    cc_status_break: "استراحة (Break)",
    cc_status_busy: "مشغول (Busy)",
    cc_status_offline: "غير متصل",
    general_dept: "عام",
    cc_sip_data: "بيانات SIP",
    cc_dial: "اتصال",
    cc_no_queues: "لا توجد طوابير انتظار مسجلة بعد. اضغط \"طابور جديد\" لإنشاء طابور.",
    presence_ready: "متاح",
    presence_ringing: "يرن...",
    presence_busy: "مشغول",
    cc_ext_prefix: "تحويلة",
    cc_no_members_assigned: "لا يوجد موظفون مسندون",

    // Auth (Login & Register)
    login_title: "تسجيل الدخول",
    login_subtitle: "مرحباً بك مجدداً في منصة المساعد الصوتي الفوري",
    login_badge: "منظومة الذكاء الاصطناعي الصوتي",
    login_username_label: "اسم المستخدم",
    login_username_placeholder: "أدخل اسم المستخدم الخاص بك",
    login_password_label: "كلمة المرور",
    login_password_placeholder: "••••••••",
    login_btn_submit: "تسجيل الدخول",
    login_no_account: "ليس لديك حساب بعد؟",
    login_create_account: "أنشئ حساباً جديداً",
    register_title: "إنشاء حساب جديد",
    register_subtitle: "انضم وابدأ محادثتك الصوتية الذكية وخدماتك فوراً",
    register_badge: "حساب منصة جديد",
    register_email_label: "البريد الإلكتروني",
    register_email_placeholder: "name@example.com",
    register_password_confirm_label: "تأكيد كلمة المرور",
    register_btn_submit: "إنشاء الحساب وبدء الاستخدام",
    register_has_account: "لديك حساب مسجل بالفعل؟",
    register_login_here: "تسجيل الدخول هنا",
    chat_loading: "جاري تحميل منصة المحادثات..."
  },
  en: {
    // App & Header Branding
    app_title: "AI Voice Assistant",
    app_subtitle: "Enterprise Conversational AI",
    header_system_title: "Enterprise Telephony & Voice AI System",
    header_balance: "Balance:",
    topup_balance: "Top-up Balance",
    role_admin: "Super Admin",
    btn_logout: "Logout",
    switch_to: "العربية",
    scroll_left: "Scroll Left",
    scroll_right: "Scroll Right",

    // Live Service Badges
    livekit_connected: "LiveKit: Connected",
    livekit_connecting: "LiveKit: Connecting...",
    livekit_disconnected: "LiveKit: Disconnected",
    centrifugo_connected: "Centrifugo: Connected",
    centrifugo_connecting: "Centrifugo: Connecting...",
    centrifugo_disconnected: "Centrifugo: Disconnected",

    // Sidebar & Navigation Portals
    nav_telephony_suite: "Voice Assistant & Telephony",
    nav_chat_hub: "Chat (Chatwoot Hub)",
    nav_billing: "Usage & Billing",
    nav_developer: "Developer APIs",
    nav_partner: "Partner Portal",
    nav_voice: "Voice Room",
    nav_calls: "Call Logs (CDR)",
    nav_rag: "Knowledge Base (RAG)",
    nav_personas: "Personas & Dialects",
    nav_crm: "Customer Memory",
    nav_store: "Tools & MCP Store",
    nav_campaigns: "AI Campaigns",
    nav_callcenter: "Call Center & Queues",
    nav_telephony: "SIP & PBX Trunks",
    nav_hours: "Business Hours & Schedule",
    nav_business_hours: "Business Hours & Schedule",
    nav_whatsapp: "WhatsApp & Omnichannel",
    nav_whatsapp_desk: "Support Desk",

    // Common Buttons & Actions
    btn_save: "Save",
    btn_cancel: "Cancel",
    btn_delete: "Delete",
    btn_edit: "Edit",
    btn_close: "Close",
    btn_update: "Update",
    btn_refresh: "Refresh",
    btn_copy: "Copy",
    btn_search: "Search",
    btn_view_details: "View Details",
    btn_back: "Back",
    btn_confirm: "Confirm",
    btn_apply: "Apply",

    // Voice Room
    metric_calls: "Active Calls",
    metric_latency: "AI Latency",
    metric_rag: "Knowledge Index",
    metric_rag_status: "Online & Indexed",
    metric_queue: "Queue Readiness",
    voice_guardrail_title: "Authorized Scope:",
    voice_guardrail_desc: "Voice Assistant answers strictly from RAG documents and connected MCP tools, politely declining inquiries outside this boundary.",
    voice_status_ready: "Ready for live voice conversation",
    voice_sub_ready: "Click \"Start Conversation\" to activate microphone and talk directly with your AI Assistant",
    voice_mic_label: "Microphone",
    voice_btn_start: "Start Conversation",
    voice_btn_end: "End Conversation",
    voice_btn_mute: "Mute Mic",
    voice_btn_unmute: "Unmute Mic",
    voice_agent_speaking: "Assistant is speaking...",
    voice_user_speaking: "Listening to your voice...",
    voice_connected: "Voice call active & live",
    voice_connecting: "Connecting to voice room...",
    voice_subtitles_empty: "Click start conversation to speak immediately with your AI Assistant",
    btn_outbound_ai_call: "📞 Outbound Phone Call (AI Dial)",
    floating_hint: "Live session streaming via LiveKit",
    btn_full_room: "Voice Room",

    // Usage & Billing
    billing_title: "Usage & Account Balance",
    billing_subtitle: "Prepaid wallet management with strict minute-ceiling calculation",
    billing_btn_refresh: "Refresh Balance",
    billing_btn_topup: "Top-up Balance",
    billing_balance_title: "Available Balance",
    billing_ready_badge: "Ready to Call",
    billing_rate_label: "Current Minute Rate:",
    billing_minute_ceiling: "(Ceiling rounded to nearest minute)",
    billing_add_funds: "+ Add Funds to Wallet",
    billing_deposited: "Total Deposited",
    billing_spent: "Total Spent on Calls",
    billing_minutes: "Total Billed Minutes",
    billing_ledger_title: "Financial Ledger",
    billing_ledger_filter_all: "All Transactions",
    billing_ledger_filter_topup: "Top-ups Only",
    billing_ledger_filter_calls: "Call Usage Only",
    billing_th_date: "Date & Time",
    billing_th_type: "Type",
    billing_th_amount: "Amount",
    billing_th_balance: "Balance After",
    billing_th_billed_mins: "Billed Mins",
    billing_th_rate: "Applied Rate",
    billing_th_desc: "Description & Details",
    billing_modal_topup_title: "Instant Wallet Top-up",
    billing_modal_amt_label: "Enter amount (USD $):",
    billing_modal_confirm: "Confirm Top-up",
    badge_topup: "Top-up",
    badge_deduction: "Call Deduction",
    no_transactions: "No financial transactions recorded yet.",

    // CDR / Call Logs
    calls_title: "Call Detail Records (CDR)",
    calls_subtitle: "Comprehensive call log with advanced filtering, metrics, and audio player",
    calls_btn_refresh: "Refresh Logs",
    calls_stat_total: "Total Calls",
    calls_stat_minutes: "Billed Minutes",
    calls_stat_cost: "Total Cost",
    calls_stat_seconds: "Total Audio Seconds",
    calls_filters_title: "Advanced Search & CDR Filters",
    calls_filters_reset: "✕ Reset Filters",
    calls_filter_search_label: "Text Search",
    calls_filter_search_placeholder: "Phone number, customer name, room, or goal...",
    calls_filter_direction: "Call Direction",
    calls_filter_duration: "Call Duration",
    calls_filter_type_label: "Call Types:",
    calls_type_all: "All",
    calls_type_ai: "AI Calls",
    calls_type_internal: "Internal Agent Calls",
    calls_filter_date: "Date Range:",
    calls_date_all: "All Time",
    calls_date_today: "Today",
    calls_date_7days: "Last 7 Days",
    calls_date_month: "This Month",
    calls_th_time: "Call Time",
    calls_th_direction: "Direction",
    calls_th_party: "Party / Customer",
    calls_th_room: "Room / Agent",
    calls_th_duration: "Actual Duration",
    calls_th_billed_mins: "Billed Minutes",
    calls_th_cost: "Cost",
    calls_th_actions: "Actions",
    calls_dir_all: "All Directions",
    calls_dir_inbound: "Inbound Call",
    calls_dir_outbound_ai: "Outbound (AI Agent)",
    calls_dir_outbound_agent: "Outbound (Human Agent)",
    calls_dir_internal: "Internal Call (PBX / Employees)",
    calls_dur_all: "All Durations",
    calls_dur_under_1m: "Under 1 min (< 60s)",
    calls_dur_1m_5m: "1 to 5 minutes",
    calls_dur_over_5m: "Over 5 minutes",
    calls_modal_title: "Call Details & AI Summary",
    calls_modal_subtitle: "Call Session",
    calls_modal_rec_ai: "AI Agent Audio Recording:",
    calls_modal_rec_human: "Human Agent Audio Recording (Post-Transfer):",
    calls_modal_mp3_download: "Download MP3",
    calls_modal_wav_download: "Download WAV",
    calls_modal_summary_title: "Cumulative AI Summary:",
    calls_modal_transcript_title: "Full Conversation Transcript:",
    calls_modal_close: "Close",
    badge_inbound: "Inbound",
    badge_outbound_ai: "Outbound AI",
    badge_outbound_agent: "Outbound Agent",
    badge_internal: "Internal",
    badge_internal_test: "Internal Test",
    badge_transferred: "Transferred to Agent",
    minute_suffix: "min",
    btn_details: "Details",
    no_calls_found: "No calls matching filter criteria.",

    // CRM / Customer Memory
    crm_title: "Customer Memory (Two-Tier Distilled Memory)",
    crm_subtitle: "Combines permanent distilled memory with real-time per-channel memory isolated by caller phone number.",
    crm_refresh: "Refresh",
    crm_reset: "Reset Memory",
    crm_check_label: "Inspect Phone Number:",
    crm_search_placeholder: "Search by phone or name...",
    crm_active_badge: "Active Customer:",
    crm_card_permanent_title: "Permanent Profile & Facts",
    crm_card_permanent_tag: "Cumulative",
    crm_card_call_title: "Call Memory",
    crm_card_wa_title: "WhatsApp Memory",
    crm_card_wa_tag: "24/7 Active",
    crm_accordion_title: "Call Sessions & Extracted Insights Archive",
    crm_no_calls: "No previous calls recorded.",

    // RAG / Knowledge Base
    rag_title: "RAG Knowledge Base Documents",
    rag_subtitle: "Upload PDF, DOCX, or TXT documents to be semantically embedded and indexed in PostgreSQL via Gemini embeddings.",
    rag_btn_choose: "Choose File (PDF/DOCX/TXT)",
    rag_btn_upload: "Upload & Process",
    rag_th_name: "Document Name",
    rag_th_type: "Type",
    rag_th_chunks: "Semantic Chunks",
    rag_th_date: "Indexed Date",
    rag_th_actions: "Actions",
    rag_empty: "Loading documents...",

    // Personas & Voices
    personas_title: "AI Personas, Dialects & Voices Management",
    personas_subtitle: "Select an active persona for live calls or customize voice timber, dialect, and prompt instructions",
    personas_catalog_title: "Available AI Personas",
    personas_catalog_hint: "Click \"Activate for Calls\" to set default persona",
    personas_btn_new: "+ New AI Persona",
    personas_studio_title: "Active Persona Studio Editor",
    personas_studio_subtitle: "Fine-tune Google voice timber (30 options), system prompt, and role",
    personas_current_label: "Current Persona:",
    personas_field_gender_dialect: "Gender, Language & Dialect",
    personas_field_gender: "Gender",
    personas_field_lang: "Language",
    personas_field_dialect: "Dialect",
    personas_field_voice: "Official Google Voice",
    personas_field_role: "Persona Role",
    personas_field_style: "Speaking Style & Pacing",
    personas_field_instructions: "Custom Prompt Instructions (Optional):",
    personas_btn_save: "Save & Apply to Calls",
    personas_btn_delete: "Delete Persona",

    // Call Center & Queues
    cc_subtab_employees: "Employees & Extensions",
    cc_subtab_queues: "Call Queues & Routing",
    cc_subtab_recordings: "Agent Calls & Recordings",
    cc_softphone_title: "Employee Extensions & Softphone Directory (WebRTC)",
    cc_softphone_desc: "Add employees, assign internal extensions, and make direct browser WebRTC calls to agents or queues.",
    cc_btn_new_employee: "+ New Employee",
    cc_btn_new_queue: "+ New Queue",
    cc_call_calling: "Calling...",
    cc_call_sync: "Connecting & synchronizing via WebRTC...",
    cc_call_end: "End Call",
    cc_th_employee: "Employee",
    cc_th_extension: "Extension",
    cc_th_dept: "Department",
    cc_th_presence: "Presence",
    cc_th_protocol: "Voice Protocol",
    cc_th_actions: "Actions",
    cc_th_queue_name: "Queue Name",
    cc_th_strategy: "Strategy",
    cc_th_members: "Assigned Members",
    cc_th_waiting: "Waiting Calls",
    cc_th_completed: "Completed Calls",

    // Telephony & PBX
    tel_subtab_outbound: "Outbound SIP Trunk & Auto-Dialer",
    tel_subtab_pbx: "Issabel & Asterisk PBX",
    tel_subtab_dids: "Dedicated DIDs & Tenants",
    tel_outbound_title: "Generic Outbound SIP Trunk & AI Auto-Dialer",
    tel_outbound_desc: "Connect any cloud carrier (Telnyx, Twilio, etc.) to enable direct outbound dialing for AI and human agents.",
    tel_btn_ai_call: "New AI Outbound Call",
    tel_trunk_status_title: "Trunk Status in LiveKit",
    tel_trunk_not_configured: "Not Configured",
    tel_field_name: "Trunk / Provider Name",
    tel_field_host: "SIP Host / Termination URI *",
    tel_field_user: "SIP Username",
    tel_field_pass: "SIP Password",
    tel_field_caller_id: "Caller ID Number",
    tel_field_transport: "Transport & Port",
    tel_btn_save_trunk: "Save & Activate Trunk",
    tel_pbx_title: "Connect On-Premise PBX (Issabel & Asterisk)",
    tel_pbx_btn_new: "+ Connect New PBX",
    tel_issabel_code_btn: "Issabel Configuration Snippet",

    // Business Hours
    hours_title: "Business Hours & Fallback Schedule",
    hours_subtitle: "Configure official business schedule and define automated handling for off-hours incoming calls.",
    hours_status_label: "Current Status:",
    hours_disabled: "Disabled",
    hours_enabled: "Enabled",
    hours_schedule_title: "Weekly Days & Hours Schedule",
    hours_timezone: "Timezone:",
    hours_th_day: "Day",
    hours_th_type: "Day Type",
    hours_th_start: "Start Time",
    hours_th_end: "End Time",
    hours_th_status: "Status",
    hours_plan_title: "Off-Hours Handling Plan",
    hours_choose_action: "Choose off-hours call response behavior:",
    hours_action_ai: "Speak Intelligent AI Message",
    hours_action_ai_desc: "The AI assistant speaks a tailored polite apology and gracefully ends the call.",
    hours_action_audio: "Play Pre-Recorded Audio File",
    hours_action_audio_desc: "Streams an uploaded audio file (MP3/WAV) directly to the caller, then hangs up.",
    hours_ai_msg_label: "Spoken Message Text:",
    hours_restore_default: "Restore Default Message",
    hours_audio_upload_label: "Upload Recorded Audio File (MP3 or WAV):",
    hours_btn_choose_audio: "Choose Audio File",
    hours_btn_save: "Save & Apply Schedule",
    day_saturday: "Saturday",
    day_sunday: "Sunday",
    day_monday: "Monday",
    day_tuesday: "Tuesday",
    day_wednesday: "Wednesday",
    day_thursday: "Thursday",
    day_friday: "Friday",
    day_workday: "Workday",
    day_holiday: "Holiday",
    day_official_work: "Official Hours",
    day_official_holiday: "Closed / Holiday",
    hours_open_now: "Open for Calls Now 🟢",
    hours_closed_now: "Currently Closed (Auto-Response Active) 🔴",
    hours_not_active: "Schedule Disabled (Always Accepting)",

    // Campaigns
    camp_title: "Calling Campaigns & Leads CRM",
    camp_subtitle: "Upload contact lists (Excel, CSV, TXT, JSON), organize in interactive CRM, and run parallel AI campaigns.",
    camp_btn_inngest: "Inngest Dashboard",
    camp_btn_refresh: "Refresh",
    camp_btn_dnc: "DNC List",
    camp_btn_new: "+ New Campaign",
    camp_stat_total: "Total Campaigns",
    camp_stat_contacts: "Total Contacts",
    camp_stat_answered: "Answered Calls",
    camp_stat_whatsapp: "WhatsApp Sent",
    camp_stat_hot: "Interested Leads",
    camp_select_label: "Select Campaign:",
    camp_btn_start: "Start Campaign",
    camp_btn_pause: "Pause",
    camp_btn_reset: "Reset",
    camp_btn_export: "Export CSV",
    camp_th_name: "Name",
    camp_th_phone: "Phone Number",
    camp_th_status: "Call Status",
    camp_th_interest: "Interest Level",
    camp_th_duration: "Duration",
    camp_th_retries: "Retries",
    camp_th_actions: "Actions",

    // Store / MCP
    store_title: "MCP Tools & Servers Store",
    store_subtitle: "Connect and manage external FastMCP tool servers via SSE to empower live voice calls with tool calling.",
    store_btn_sync_all: "Sync All",
    store_btn_new_server: "+ Add MCP Server",
    store_servers_title: "Connected MCP Servers:",
    store_tools_title: "Discovered Tools from Active Servers:",
    store_tools_hint: "Automatically available to AI Assistant during calls",
    store_modal_title: "FastMCP Server Configuration",

    // Developer API
    dev_title: "Direct Developer APIs & Keys",
    dev_subtitle: "Integrate Voice AI, FastMCP tools, and direct WebRTC calling into your external applications with your personal API key.",
    dev_btn_docs: "Open Interactive Docs (Scalar)",
    dev_btn_refresh: "Refresh",
    dev_key_title: "Personal Live API Key",
    dev_btn_rotate: "Regenerate Key",
    dev_btn_copy: "Copy",
    dev_created_at: "Created:",
    dev_last_used: "Last Used:",
    dev_account_sample: "Get Account Details:",
    dev_dial_sample: "Trigger AI Outbound Call:",
    dev_context_title: "Structured Live Context",
    dev_context_desc: "Real-time structured business data (branches, menus, delivery zones) injected in < 2ms via Redis at the start of each call.",
    dev_template_restaurant: "Restaurant Template",
    dev_format_json: "Format JSON",
    dev_preview_prompt: "Preview Prompt View",
    dev_clear: "Clear",
    dev_save_context: "Save & Replace",

    // Partner Portal
    partner_title: "Partner & Reseller Portal (SaaS Solutions)",
    partner_subtitle: "Manage sub-clients, headless API access keys, shared MCP tools, and aggregated call analytics.",
    partner_btn_docs: "Developer API Docs",
    partner_btn_quickguide: "Quick Guide",
    partner_btn_refresh: "Refresh Data",
    partner_kpi_balance: "Partner Wallet Balance",
    partner_kpi_rate: "Assigned Minute Rate",
    partner_kpi_clients: "Active SaaS Sub-Clients",
    partner_kpi_minutes: "Total Consumed Minutes",
    partner_api_title: "Headless API Access Credentials",
    partner_code_label: "Partner Code",
    partner_key_label: "Master Access Key (X-Partner-Key)",
    partner_webhook_label: "Webhook Event Receiver URL",
    partner_shared_mcp_title: "Shared SaaS MCP Tools Server",

    // WhatsApp Omnichannel & Desk
    whatsapp_page_title: "WhatsApp Conversations & 24/7 AI Agent",
    whatsapp_page_desc: "Unified Omnichannel Inbox: comprehensive view of customer chats, AI reply monitoring, and real-time human intervention.",
    whatsapp_gateway_checking: "Checking gateway...",
    whatsapp_gateway_connected: "WhatsApp Gateway: Connected 🟢",
    whatsapp_gateway_disconnected: "WhatsApp Gateway: Disconnected 🔴",
    whatsapp_gateway_error: "Gateway Check Error",
    whatsapp_sync_phone: "Sync Phone Chats",
    whatsapp_syncing: "Syncing...",
    whatsapp_sync_title: "Sync all chats and messages from your connected WhatsApp device",
    whatsapp_connect_qr: "Connect WhatsApp (QR Code)",
    whatsapp_refresh_chats: "Refresh Conversations",
    whatsapp_test_send: "Test Send",
    whatsapp_search_placeholder: "Search by name or phone...",
    whatsapp_filter_all: "All",
    whatsapp_filter_ai: "AI Active",
    whatsapp_filter_manual: "Manual",
    whatsapp_loading_convs: "Loading conversations...",
    whatsapp_active_convs: "Active Conversations:",
    whatsapp_auto_refresh: "Auto Refresh",
    whatsapp_no_convs: "No matching conversations",
    whatsapp_no_convs_desc: "Conversations will appear here once customers message on WhatsApp.",
    whatsapp_new_customer: "New WhatsApp Customer",
    whatsapp_start_conv: "Start of conversation",
    whatsapp_messages_count: "messages",
    whatsapp_badge_escalation: "⚠️ Escalation",
    whatsapp_badge_call: "📞 Call",
    whatsapp_badge_ai: "🟢 AI",
    whatsapp_badge_manual: "⏸️ Manual",
    whatsapp_empty_title: "Select a conversation to start",
    whatsapp_empty_desc: "Click on any customer from the list to view their full chat history, monitor AI replies, or intervene manually at any time.",
    whatsapp_edit_contact: "Edit",
    whatsapp_edit_contact_title: "Edit customer name or phone",
    whatsapp_call_history: "Recorded call history (click to view)",
    whatsapp_active_status: "Active Conversation",
    whatsapp_ai_active: "Smart Reply: Active",
    whatsapp_ai_manual: "Human Agent Mode (AI Paused)",
    whatsapp_ai_toggle_title: "Toggle AI auto-reply for this customer",
    whatsapp_refresh_messages: "Refresh Messages",
    whatsapp_call_context: "Previous Call Context:",
    whatsapp_escalated_tag: "Escalated to Human",
    whatsapp_escalation_reason: "Escalation Reason:",
    whatsapp_escalation_fallback: "Human support request / Complaint",
    whatsapp_ai_summary_prefix: "📌 AI Summary: ",
    whatsapp_escalation_summary_fallback: "Customer is waiting for a human agent to handle the conversation.",
    whatsapp_ai_active_btn: "Smart Reply: Active (Click to pause)",
    whatsapp_ai_manual_btn: "Human Mode (AI paused)",
    whatsapp_resolve_ai: "Resolve & Resume AI",
    whatsapp_resolve_ai_title: "Resolve customer ticket and reactivate AI auto-reply",
    whatsapp_loading_messages: "Loading conversation...",
    whatsapp_no_messages: "No previous messages in this conversation yet.",
    whatsapp_reply_placeholder: "Type a manual reply to the customer via WhatsApp...",
    whatsapp_btn_send: "Send",
    whatsapp_gateway_notice: "Sent immediately to customer via connected Evolution API gateway.",
    whatsapp_sent_success: "✓ Message sent and delivered to WhatsApp successfully",
    whatsapp_customer: "Customer",
    whatsapp_bubble_ai: "🤖 AI Assistant",
    whatsapp_bubble_human: "👤 Human Agent",
    whatsapp_bubble_sent: "✓ Sent to WhatsApp",
    whatsapp_generating: "Generating...",
    whatsapp_qr_title: "Link WhatsApp Number (QR Code)",
    whatsapp_qr_desc: "Scan the QR code to link your business or personal WhatsApp",
    whatsapp_qr_checking: "Checking server connection status...",
    whatsapp_qr_btn_generate: "Generate QR Code",
    whatsapp_qr_btn_disconnect: "Disconnect Session",
    whatsapp_qr_connected_title: "WhatsApp Connected & Operational",
    whatsapp_qr_connected_desc: "Gateway is ready to send and receive messages 24/7.",
    whatsapp_qr_scan_inst1: "Scan the QR code with WhatsApp camera",
    whatsapp_qr_scan_inst2: "Settings > Linked Devices > Link a Device",
    whatsapp_qr_error_prefix: "Failed to fetch QR Code:",
    whatsapp_edit_title: "Edit Customer Information",
    whatsapp_label_name: "Customer / Business Name:",
    whatsapp_placeholder_name: "e.g. John Doe / Acme Corp",
    whatsapp_label_phone: "Customer Phone Number:",
    whatsapp_placeholder_phone: "e.g. +1234567890 or +201012345678",
    whatsapp_phone_hint: "Used to identify the customer phone and display on chat card.",
    whatsapp_btn_save_changes: "Save Changes",
    whatsapp_test_title: "Test WhatsApp & LangGraph Engine",
    whatsapp_test_phone_label: "Customer Phone (with country code):",
    whatsapp_test_phone_placeholder: "e.g. 201012345678 or 966501234567",
    whatsapp_test_name_label: "Customer Name (optional):",
    whatsapp_test_type_label: "Test Type:",
    whatsapp_test_opt_langgraph: "Run LangGraph automatically (Simulate post-call follow-up)",
    whatsapp_test_opt_direct: "Send custom direct message",
    whatsapp_test_msg_label: "Custom Message Text:",
    whatsapp_test_msg_placeholder: "Type test message here...",
    whatsapp_test_btn_send: "Send Test",
    whatsapp_support_request: "Human Support Request",
    whatsapp_waiting_reply: "Awaiting Reply",
    whatsapp_active_conv: "Active Chat",

    // Desk Tier 2
    desk_page_title: "WhatsApp Customer Support Desk (Tier 2 Human Support)",
    desk_badge_ring: "Broadcast Ringing & Instant Claim",
    desk_page_desc: "Unified support agent cockpit to receive, claim, and resolve escalated WhatsApp conversations.",
    desk_presence_online: "Status: Online & Ready",
    desk_presence_break: "Status: On Break (Muted)",
    desk_sound_on: "Sound Enabled",
    desk_sound_off: "Sound Muted",
    desk_sound_title: "Mute/Unmute ring sound",
    desk_queue_title: "Broadcast Ringing Queue",
    desk_queue_subtitle: "Rings across all agents (first-come first-served)",
    desk_queue_empty: "No pending conversations in queue.",
    desk_queue_empty_desc: "When an escalation occurs, incoming chats will ring here instantly.",
    desk_badge_urgent: "Urgent",
    desk_badge_support: "Support",
    desk_btn_claim: "Claim Conversation",
    desk_my_chats_title: "My Claimed Chats",
    desk_my_chats_subtitle: "Conversations under active support",
    desk_my_chats_empty: "No claimed chats yet. Click 'Claim' on an incoming queue item to begin servicing.",
    desk_empty_title: "Select a conversation from 'My Claimed Chats'",
    desk_empty_desc: "Or click 'Claim' from the broadcast queue on the right to pull the ticket and reply live.",
    desk_active_badge: "Under Active Human Support",
    desk_btn_release: "Return to Queue",
    desk_btn_release_title: "Return conversation back to broadcast queue for colleagues",
    desk_btn_resolve: "Resolve & Resume AI",
    desk_btn_resolve_title: "Resolve ticket and reactivate AI auto-replies",
    desk_brief_escalation: "Complaint / Escalation",
    desk_brief_reason: "Escalation Reason:",
    desk_brief_sla: "SLA Deadline:",
    desk_reply_placeholder: "Type a direct reply to customer via WhatsApp...",
    desk_bubble_customer: "👤 Customer",
    desk_bubble_agent: "👨‍💻 You (Human Agent)",
    desk_bubble_ai: "🤖 AI Assistant",
    desk_summary_fallback: "Customer is waiting for your assistance and reply.",

    // Dynamic Module Strings (Billing, CRM, RAG, Store, Call Center)
    billing_per_minute: "/ min",
    billing_status_ready: "Ready to Call",
    billing_status_low: "Low Balance - Please Top-up",
    billing_no_transactions: "No transactions recorded yet.",
    billing_type_topup: "Top-up",
    billing_type_deduction: "Call Deduction",
    billing_type_adjustment: "Adjustment",
    billing_btn_depositing: "Depositing...",
    billing_ledger_failed: "Failed to load transactions ledger.",
    minute_short: "m",
    second_short: "s",
    second_suffix: "seconds",
    recent_time: "Recently",

    // CRM Dynamic Strings
    crm_default_browser_session: "Default Browser Session",
    crm_no_permanent_data: "No permanent profile recorded for this number yet. Assistant will learn their name and preferences during calls!",
    crm_label_name: "Name:",
    crm_label_phone: "Phone:",
    crm_label_address: "Address:",
    crm_label_prefs: "Preferences:",
    crm_label_notes: "Notes:",
    crm_no_specific_details: "No specific details recorded yet.",
    crm_calls_count_suffix: "calls",
    crm_prev_call: "Previous Call",
    crm_last_call_label: "Last Call:",
    crm_intent_label: "Intent:",
    crm_sentiment_label: "Sentiment:",
    crm_agreed_label: "Agreed Next Steps:",
    crm_no_calls_recorded: "No voice calls recorded for this number yet.",
    crm_last_chat_label: "Last Chat Activity:",
    crm_stage_label: "Customer Stage:",
    crm_last_incoming_label: "Last Received:",
    crm_last_outgoing_label: "Last Sent:",
    crm_no_wa_recorded: "No WhatsApp chats recorded yet for this number.",
    crm_no_prev_calls: "No previous calls recorded for this number.",
    call_dir_inbound: "Inbound",
    call_dir_outbound_ai: "Outbound (AI)",
    call_dir_outbound_agent: "Outbound (Agent)",
    crm_call_goal_prefix: "Goal: ",
    crm_completed_no_summary: "Completed call without summary",

    // Store Dynamic Strings
    store_no_servers_title: "No MCP Servers Connected",
    store_no_servers_desc: "You can connect an external tool server via FastMCP SSE protocol to empower voice calls with live tool calling.",
    store_btn_new_server_link: "Connect New MCP Server",
    store_status_active: "Active for Calls",
    store_status_disabled: "Disabled",
    store_btn_disable: "Disable",
    store_btn_enable: "Enable",
    store_discovered_tools: "Discovered Tools:",
    store_synced_at: "Synced:",
    store_never_synced: "Never Synced",
    store_btn_sync_hint: "Check and refresh tools",
    store_btn_edit_hint: "Edit settings",
    store_btn_delete_hint: "Delete server",
    store_no_tools_discovered: "No tools discovered from active servers yet. Click refresh 🔄 on any server to fetch its tools.",
    store_no_desc: "No description provided",
    store_params_label: "Parameters:",
    store_tools_count_suffix: "tools",

    // RAG Dynamic Strings
    rag_no_docs: "No documents uploaded yet. Upload your first file to start answering questions from it!",
    rag_status_pending: "Indexing",
    rag_status_failed: "Failed",
    rag_status_ready: "Ready",
    rag_chunks_suffix: "chunks",
    rag_delete_doc: "Delete Document",
    rag_processing: "Processing & Embedding...",
    rag_extracting: "Extracting text and generating semantic embeddings via Gemini...",
    rag_confirm_delete: "Are you sure you want to delete this document and all its semantic chunks?",

    // Call Center Dynamic Strings
    cc_no_employees: "No employees registered in the system yet.",
    cc_status_ready: "Ready",
    cc_status_break: "Break",
    cc_status_busy: "Busy",
    cc_status_offline: "Offline",
    general_dept: "General",
    cc_sip_data: "SIP Credentials",
    cc_dial: "Call",
    cc_no_queues: "No queues registered yet. Click \"New Queue\" to create one.",
    presence_ready: "Ready",
    presence_ringing: "Ringing...",
    presence_busy: "Busy",
    cc_ext_prefix: "Ext.",
    cc_no_members_assigned: "No agents assigned",

    // Auth (Login & Register)
    login_title: "Sign In",
    login_subtitle: "Welcome back to Enterprise Voice AI",
    login_badge: "Enterprise Voice Platform",
    login_username_label: "Username",
    login_username_placeholder: "Enter your username",
    login_password_label: "Password",
    login_password_placeholder: "••••••••",
    login_btn_submit: "Sign In",
    login_no_account: "Don't have an account yet?",
    login_create_account: "Create an Account",
    register_title: "Create an Account",
    register_subtitle: "Join and launch your conversational voice AI assistant today",
    register_badge: "New Platform Account",
    register_email_label: "Email Address",
    register_email_placeholder: "name@example.com",
    register_password_confirm_label: "Confirm Password",
    register_btn_submit: "Create Account & Start",
    register_has_account: "Already have an account?",
    register_login_here: "Sign in here",
    chat_loading: "Loading conversation platform..."
  }
};

// Aliases for compatibility
const COMMON_I18N = APP_I18N;
window.APP_I18N = APP_I18N;
window.COMMON_I18N = APP_I18N;

// Current Language Resolution
let currentLang = localStorage.getItem('app_lang') || localStorage.getItem('voice_app_lang') || 'ar';

function getCurrentLanguage() {
  return currentLang;
}
window.getCurrentLanguage = getCurrentLanguage;

function getI18nText(key, lang) {
  const l = lang || currentLang || 'ar';
  if (APP_I18N[l] && APP_I18N[l][key] !== undefined) {
    return APP_I18N[l][key];
  }
  if (APP_I18N['ar'] && APP_I18N['ar'][key] !== undefined) {
    return APP_I18N['ar'][key];
  }
  return null;
}
window.getI18nText = getI18nText;

window.t = function(key, fallback) {
  const val = getI18nText(key, currentLang);
  return (val !== null && val !== undefined) ? val : (fallback !== undefined ? fallback : key);
};

function applyCommonLanguage(lang) {
  if (lang !== 'ar' && lang !== 'en') {
    lang = 'ar';
  }
  currentLang = lang;

  try {
    localStorage.setItem('app_lang', lang);
    localStorage.setItem('voice_app_lang', lang);
  } catch (e) {
    console.debug('localStorage error:', e);
  }

  const isRtl = (lang === 'ar');
  document.documentElement.dir = isRtl ? 'rtl' : 'ltr';
  document.documentElement.lang = lang;

  // Apply font family
  if (document.body) {
    document.body.style.fontFamily = isRtl ? "'Cairo', sans-serif" : "'Inter', sans-serif";
  }

  // Update language switcher button text in header
  const langText = document.getElementById('lang-text');
  if (langText && APP_I18N[lang]) {
    langText.innerText = APP_I18N[lang].switch_to;
  }

  // Update all [data-i18n] text elements
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    const val = getI18nText(key, lang);
    if (val !== null && val !== undefined) {
      el.innerText = val;
    }
  });

  // Update all [data-i18n-placeholder] input elements
  document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
    const key = el.getAttribute('data-i18n-placeholder');
    const val = getI18nText(key, lang);
    if (val !== null && val !== undefined) {
      el.placeholder = val;
    }
  });

  // Update all [data-i18n-title] elements
  document.querySelectorAll('[data-i18n-title]').forEach(el => {
    const key = el.getAttribute('data-i18n-title');
    const val = getI18nText(key, lang);
    if (val !== null && val !== undefined) {
      el.title = val;
    }
  });

  // Update all [data-i18n-value] button/input elements
  document.querySelectorAll('[data-i18n-value]').forEach(el => {
    const key = el.getAttribute('data-i18n-value');
    const val = getI18nText(key, lang);
    if (val !== null && val !== undefined) {
      el.value = val;
    }
  });

  // Update live status badges
  const livekitBadge = document.getElementById('livekit-status');
  if (livekitBadge) {
    livekitBadge.innerHTML = `<span class="w-2 h-2 rounded-full bg-[#1f93ff]"></span> ${window.t('livekit_connected', 'LiveKit: متصل')}`;
  }
  updateCentrifugoStatusBadge();

  // Dispatch custom event for child / modular page controllers
  window.dispatchEvent(new CustomEvent('appLanguageChanged', { detail: { lang: lang, isRtl: isRtl } }));
}

function toggleLanguage() {
  const next = (currentLang === 'ar') ? 'en' : 'ar';
  applyCommonLanguage(next);
}

// Expose globally
window.applyCommonLanguage = applyCommonLanguage;
window.toggleLanguage = toggleLanguage;

// Self-executing setup on script load
(function initEarlyLanguage() {
  const saved = localStorage.getItem('app_lang') || localStorage.getItem('voice_app_lang') || 'ar';
  currentLang = saved;
  document.documentElement.lang = saved;
  document.documentElement.dir = (saved === 'ar') ? 'rtl' : 'ltr';
})();

document.addEventListener('DOMContentLoaded', () => {
  initSidebarState();
  applyCommonLanguage(currentLang);
  loadHeaderBalance();
  initGlobalCentrifugo();
});
