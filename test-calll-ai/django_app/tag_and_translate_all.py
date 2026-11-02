# SPDX-License-Identifier: Apache-2.0
"""
Extract all untagged Arabic texts from room.html and sub-pages,
generate translation keys and accurate 6-language dictionaries,
insert data-i18n attributes into the templates, and update common.js.
"""

import os
import re
import json

BASE_DIR = '/root/voice-ai-telephony/test-calll-ai/django_app'
ROOM_PATH = os.path.join(BASE_DIR, 'voice_assistant/templates/voice_assistant/room.html')
COMMON_JS_PATH = os.path.join(BASE_DIR, 'static/js/common.js')

# Comprehensive dictionary mapping Arabic text to translations across 6 languages
TRANSLATIONS = {
    # Off topic & Personas
    "لو تركتها فارغة، سيعتذر المساعد باختصار ثم يعيد توجيه العميل لنطاق الخدمة تلقائياً.": {
        "en": "If left empty, the assistant will briefly apologize and redirect the customer to the service scope.",
        "tr": "Boş bırakılırsa, asistan kısaca özür diler ve müşteriyi hizmet kapsamına yönlendirir.",
        "fr": "Si laissé vide, l'assistant s'excusera brièvement et redirigera le client vers le périmètre du service.",
        "de": "Wenn leer gelassen, entschuldigt sich der Assistent kurz und leitet den Kunden zum Servicebereich weiter.",
        "es": "Si se deja vacío, el asistente se disculpará brevemente y redirigirá al cliente al alcance del servicio."
    },
    "نظام الاتصال الهاتفي وسوفت فون WebRTC المباشر": {
        "en": "Telephony System & Direct WebRTC Softphone",
        "tr": "Telefon Sistemi ve Doğrudan WebRTC Softphone",
        "fr": "Système de téléphonie et Softphone WebRTC direct",
        "de": "Telefoniesystem & Direktes WebRTC-Softphone",
        "es": "Sistema de Telefonía y Softphone WebRTC Directo"
    },
    "أضف موظفين جدد وتحويلات داخلية، واتصل مباشرة بأي موظف أو طابور عبر": {
        "en": "Add new employees and internal extensions, and call any employee or queue directly via",
        "tr": "Yeni çalışanlar ve dahili hatlar ekleyin, herhangi bir çalışanı veya kuyruğu doğrudan arayın",
        "fr": "Ajoutez de nouveaux employés et postes internes, et appelez directement n'importe quel employé ou file d'attente via",
        "de": "Fügen Sie neue Mitarbeiter und interne Durchwahlen hinzu und rufen Sie Mitarbeiter oder Warteschlangen direkt an über",
        "es": "Agregue nuevos empleados y extensiones internas, y llame directamente a cualquier empleado o cola a través de"
    },
    "WebRTC المباشر": {
        "en": "Direct WebRTC",
        "tr": "Doğrudan WebRTC",
        "fr": "WebRTC direct",
        "de": "Direktes WebRTC",
        "es": "WebRTC Directo"
    },
    "من المتصفح.": {
        "en": "from your browser.",
        "tr": "tarayıcınızdan.",
        "fr": "depuis votre navigateur.",
        "de": "aus Ihrem Browser.",
        "es": "desde su navegador."
    },
    "طوابير الانتظار ومجموعات الاتصال (Call Queues & Routing)": {
        "en": "Call Queues & Ring Groups (Routing)",
        "tr": "Çağrı Kuyrukları ve Çağrı Grupları (Yönlendirme)",
        "fr": "Files d'attente et groupes d'appel (Routage)",
        "de": "Warteschlangen & Anrufgruppen (Routing)",
        "es": "Colas de Llamadas y Grupos de Timbrado (Enrutamiento)"
    },
    "أنشئ طوابير فرق العمل مع نظام الرنين بالتناوب (Round-Robin)، موسيقى انتظار مخصصة، والتحويل التلقائي للذكاء الاصطناعي.": {
        "en": "Create team queues with Round-Robin ringing, custom hold music, and automatic AI escalation.",
        "tr": "Round-Robin zil sistemi, özel bekleme müziği ve otomatik yapay zeka aktarımı ile ekip kuyrukları oluşturun.",
        "fr": "Créez des files d'attente d'équipe avec sonnerie alternée (Round-Robin), musique d'attente personnalisée et escalade IA.",
        "de": "Erstellen Sie Team-Warteschlangen mit Round-Robin-Klingeln, individueller Wartemusik und automatischer KI-Weiterleitung.",
        "es": "Cree colas de equipo con timbrado rotativo (Round-Robin), música de espera personalizada y transferencia automática de IA."
    },
    "كود الطابور": {
        "en": "Queue Code",
        "tr": "Kuyruk Kodu",
        "fr": "Code de la file",
        "de": "Warteschlangen-Code",
        "es": "Código de Cola"
    },
    "الموظفون المسندون والحالة الحية": {
        "en": "Assigned Agents & Live Status",
        "tr": "Atanan Temsilciler ve Canlı Durum",
        "fr": "Agents assignés et statut en direct",
        "de": "Zugewiesene Mitarbeiter & Live-Status",
        "es": "Agentes Asignados y Estado en Vivo"
    },
    "المكالمات المنتظرة": {
        "en": "Waiting Calls",
        "tr": "Bekleyen Çağrılar",
        "fr": "Appels en attente",
        "de": "Wartende Anrufe",
        "es": "Llamadas en Espera"
    },
    "إدارة بوابات الاتصال الصادر والربط مع السنترالات المحلية": {
        "en": "Outbound Gateways & PBX Integrations Management",
        "tr": "Giden Arama Ağ Geçitleri ve PBX Entegrasyon Yönetimi",
        "fr": "Gestion des passerelles d'appels sortants et intégration PBX",
        "de": "Verwaltung von Outbound-Gateways und PBX-Integrationen",
        "es": "Gestión de Pasarelas de Salida e Integración PBX"
    },
    "المكالمات الصادرة والجذع الخارجي (Generic Outbound SIP Trunk & AI Auto-Dialer)": {
        "en": "Outbound SIP Trunk & AI Auto-Dialer",
        "tr": "Giden SIP Trunk ve Yapay Zeka Otomatik Arayıcı",
        "fr": "Trunk SIP sortant et numéroteur automatique IA",
        "de": "Ausgehender SIP-Trunk & KI-Auto-Dialer",
        "es": "Trunk SIP Saliente y Marcador Automático con IA"
    },
    "اربط أي مزود اتصالات سحابي خارجي مثل": {
        "en": "Connect any cloud telephony provider such as",
        "tr": "Gibi herhangi bir bulut telekom sağlayıcısını bağlayın",
        "fr": "Connectez tout fournisseur de téléphonie cloud tel que",
        "de": "Verbinden Sie einen beliebigen Cloud-Telefonieanbieter wie",
        "es": "Conecte cualquier proveedor de telefonía en la nube como"
    },
    "أو": {
        "en": "or",
        "tr": "veya",
        "fr": "ou",
        "de": "oder",
        "es": "o"
    },
    "لتمكين الذكاء الاصطناعي والموظفين من الاتصال بأرقام الهواتف المحمولة والأرضية مباشرة مع التصحيح التلقائي للأرقام المحلية والدولية.": {
        "en": "to enable AI and agents to place direct calls to mobile and landline numbers with automatic E.164 normalization.",
        "tr": "yapay zeka ve temsilcilerin cep ve sabit hatları otomatik E.164 düzeltmesiyle doğrudan aramasını sağlamak için.",
        "fr": "pour permettre à l'IA et aux agents d'appeler directement des numéros mobiles et fixes avec normalisation E.164.",
        "de": "damit KI und Agenten Mobil- und Festnetznummern direkt mit automatischer E.164-Korrektur anrufen können.",
        "es": "para permitir que la IA y los agentes llamen a teléfonos móviles y fijos con normalización E.164 automática."
    },
    "حفظ وتفعيل الجذع الخارجي": {
        "en": "Save & Activate Outbound Trunk",
        "tr": "Giden Trunk'ı Kaydet ve Etkinleştir",
        "fr": "Enregistrer et activer le trunk sortant",
        "de": "Ausgehenden Trunk speichern & aktivieren",
        "es": "Guardar y Activar Trunk Saliente"
    },
    "ربط السنترالات المحلية والأنظمة الخارجية (Inbound PBX Trunks - Issabel / Asterisk)": {
        "en": "Inbound PBX Trunks (Issabel / Asterisk Integration)",
        "tr": "Gelen PBX Trunk'ları (Issabel / Asterisk Entegrasyonu)",
        "fr": "Trunks PBX entrants (Intégration Issabel / Asterisk)",
        "de": "Eingehende PBX-Trunks (Issabel / Asterisk Integration)",
        "es": "Trunks PBX Entrantes (Integración Issabel / Asterisk)"
    },
    "اربط سنترال شركتك الحالي (": {
        "en": "Connect your existing company PBX (",
        "tr": "Mevcut şirket santralinizi bağlayın (",
        "fr": "Connectez votre PBX d'entreprise existant (",
        "de": "Verbinden Sie Ihre bestehende Telefonanlage (",
        "es": "Conecte la centralita PBX actual de su empresa ("
    },
    ") دون المساس بهواتف الموظفين الفعلية. استقبل المكالمات وحوّلها للمساعد الذكي كـ": {
        "en": ") without disrupting physical agent phones. Receive calls and route to Smart IVR as",
        "tr": ") çalışanların fiziksel telefonlarını etkilemeden. Çağrıları Akıllı IVR olarak karşılayın:",
        "fr": ") sans perturber les téléphones physiques. Recevez et transférez les appels vers le Smart IVR :",
        "de": ") ohne die Telefone der Mitarbeiter zu beeinträchtigen. Nehmen Sie Anrufe als Smart IVR an:",
        "es": ") sin alterar los teléfonos físicos del personal. Reciba llamadas y desvíelas a Smart IVR como"
    },
    "مع الذاكرة الثنائية (Distilled Memory)، أو لطوابير الانتظار، مع إمكانية التحويل العكسي (": {
        "en": "with two-tier distilled memory, or to queues, with reverse transfer capability (",
        "tr": "iki katmanlı damıtılmış hafıza veya kuyruklar ile, geri aktarma özelliğiyle (",
        "fr": "avec mémoire distillée à deux niveaux, ou vers des files d'attente, avec transfert inverse (",
        "de": "mit zweistufigem Speicher oder zu Warteschlangen, mit Rückübertragungsfunktion (",
        "es": "con memoria destilada de dos niveles, o a colas, con capacidad de transferencia inversa ("
    },
    "ربط سنترال Issabel / Asterisk جديد": {
        "en": "Connect New Issabel / Asterisk PBX",
        "tr": "Yeni Issabel / Asterisk Santrali Bağla",
        "fr": "Connecter un nouveau PBX Issabel / Asterisk",
        "de": "Neue Issabel / Asterisk Telefonanlage verbinden",
        "es": "Conectar Nueva Centralita Issabel / Asterisk"
    },
    "الذاكرة الدائمة": {
        "en": "Permanent Memory",
        "tr": "Kalıcı Hafıza",
        "fr": "Mémoire permanente",
        "de": "Dauerhafter Speicher",
        "es": "Memoria Permanente"
    },
    "الذاكرة اللحظية": {
        "en": "Session Memory",
        "tr": "Anlık Hafıza",
        "fr": "Mémoire de session",
        "de": "Sitzungsspeicher",
        "es": "Memoria de Sesión"
    },
    "تجمع بين": {
        "en": "Combines",
        "tr": "Birleştirir:",
        "fr": "Combine",
        "de": "Kombiniert",
        "es": "Combina"
    },
    "و": {
        "en": "and",
        "tr": "ve",
        "fr": "et",
        "de": "und",
        "es": "y"
    },
    "معزولة ومخصصة لكل رقم عميل يتصل بالنظام.": {
        "en": "isolated and customized for every caller number contacting the system.",
        "tr": "sistemle iletişim kuran her müşteri numarası için izole ve özelleştirilmiş.",
        "fr": "isolée et dédiée à chaque numéro de client appelant le système.",
        "de": "isoliert und individuell für jede anrufende Kundennummer.",
        "es": "aislada y dedicada para cada número de cliente que llama al sistema."
    },
    "الذاكرة الدائمة (Permanent Profile)": {
        "en": "Permanent Profile Memory",
        "tr": "Kalıcı Profil Hafızası",
        "fr": "Mémoire de profil permanent",
        "de": "Dauerhaftes Profilgedächtnis",
        "es": "Memoria de Perfil Permanente"
    },
    "تراكمية ومحدثة": {
        "en": "Cumulative & Up-to-date",
        "tr": "Kümülatif ve Güncel",
        "fr": "Cumulative et à jour",
        "de": "Kumulativ & Aktuell",
        "es": "Acumulativa y Actualizada"
    },
    "جاري تحميل الذاكرة الدائمة...": {
        "en": "Loading permanent memory...",
        "tr": "Kalıcı hafıza yükleniyor...",
        "fr": "Chargement de la mémoire permanente...",
        "de": "Dauerhafter Speicher wird geladen...",
        "es": "Cargando memoria permanente..."
    },
    "الذاكرة اللحظية (آخر مكالمة)": {
        "en": "Immediate Memory (Latest Call)",
        "tr": "Anlık Hafıza (Son Çağrı)",
        "fr": "Mémoire immédiate (Dernier appel)",
        "de": "Unmittelbarer Speicher (Letzter Anruf)",
        "es": "Memoria Inmediata (Última Llamada)"
    },
    "0 مكالمات مسجلة": {
        "en": "0 Recorded Calls",
        "tr": "0 Kayıtlı Çağrı",
        "fr": "0 Appels enregistrés",
        "de": "0 Aufgezeichnete Anrufe",
        "es": "0 Llamadas Registradas"
    },
    "جاري تحميل ملخص آخر مكالمة...": {
        "en": "Loading latest call summary...",
        "tr": "Son çağrı özeti yükleniyor...",
        "fr": "Chargement du résumé du dernier appel...",
        "de": "Zusammenfassung des letzten Anrufs wird geladen...",
        "es": "Cargando resumen de la última llamada..."
    },
    "معدل التزامن المسموح (Limit)": {
        "en": "Allowed Concurrency Limit",
        "tr": "İzin Verilen Eşzamanlılık Sınırı",
        "fr": "Limite de simultanéité autorisée",
        "de": "Erlaubtes Gleichzeitigkeitslimit",
        "es": "Límite de Concurrencia Permitido"
    },
    "1 مكالمة": {
        "en": "1 Call",
        "tr": "1 Çağrı",
        "fr": "1 Appel",
        "de": "1 Anruf",
        "es": "1 Llamada"
    },
    "عملاء مهتمون (Hot Leads)": {
        "en": "Hot Leads",
        "tr": "Sıcak Müşteri Adayları",
        "fr": "Prospects très intéressés (Hot Leads)",
        "de": "Heiße Interessenten (Hot Leads)",
        "es": "Clientes Muy Interesados (Hot Leads)"
    },
    "تنبيه هام: لا يوجد مسار اتصال صادر (SIP Trunk) مفعل حالياً": {
        "en": "Important: No outbound SIP Trunk is currently active",
        "tr": "Önemli Uyarı: Şu anda aktif giden SIP Trunk bulunmuyor",
        "fr": "Alerte importante : Aucun Trunk SIP sortant n'est actif",
        "de": "Wichtiger Hinweis: Derzeit ist kein ausgehender SIP-Trunk aktiv",
        "es": "Aviso Importante: No hay ningún Trunk SIP saliente activo actualmente"
    },
    "لن يتم الاتصال بالعملاء حتى تقوم بإعداد وتفعيل خط اتصال صادر (سحابي أو سنترال PBX) من تبويب الربط الهاتفي.": {
        "en": "Customers will not be called until you configure and activate an outbound SIP Trunk (Cloud or PBX) in the Telephony tab.",
        "tr": "Telefoni sekmesinden giden bir hat (Bulut veya PBX) kurup etkinleştirene kadar müşteriler aranmayacaktır.",
        "fr": "Les clients ne seront pas appelés tant que vous n'aurez pas configuré un trunk sortant dans l'onglet Téléphonie.",
        "de": "Kunden werden nicht angerufen, bis Sie im Reiter Telefonie einen ausgehenden Trunk konfiguriert haben.",
        "es": "No se llamará a los clientes hasta que configure y active una línea saliente (Nube o PBX) en la pestaña Telefonía."
    },
    "إعداد مسار الاتصال (SIP Trunk)": {
        "en": "Setup SIP Trunk",
        "tr": "SIP Trunk Yapılandır",
        "fr": "Configurer le Trunk SIP",
        "de": "SIP-Trunk einrichten",
        "es": "Configurar Trunk SIP"
    },
    "تصدير Excel (XLSX)": {
        "en": "Export Excel (XLSX)",
        "tr": "Excel'e Aktar (XLSX)",
        "fr": "Exporter en Excel (XLSX)",
        "de": "Excel exportieren (XLSX)",
        "es": "Exportar Excel (XLSX)"
    },
    "نسبة الإنجاز:": {
        "en": "Progress Rate:",
        "tr": "Tamamlanma Oranı:",
        "fr": "Taux d'avancement :",
        "de": "Fortschrittsrate:",
        "es": "Tasa de Progreso:"
    },
    "المساعد:": {
        "en": "Assistant:",
        "tr": "Asistan:",
        "fr": "Assistant :",
        "de": "Assistent:",
        "es": "Asistente:"
    },
    "| محاولات الإعادة:": {
        "en": "| Retries:",
        "tr": "| Yeniden Denemeler:",
        "fr": "| Tentatives :",
        "de": "| Wiederholungen:",
        "es": "| Reintentos:"
    },
    "السيناريو: -": {
        "en": "Scenario: -",
        "tr": "Senaryo: -",
        "fr": "Scénario : -",
        "de": "Szenario: -",
        "es": "Escenario: -"
    },
    "الكل (": {
        "en": "All (",
        "tr": "Tümü (",
        "fr": "Tous (",
        "de": "Alle (",
        "es": "Todos ("
    },
    "في الانتظار (": {
        "en": "Pending (",
        "tr": "Beklemede (",
        "fr": "En attente (",
        "de": "Ausstehend (",
        "es": "En espera ("
    },
    "تم الرد (": {
        "en": "Answered (",
        "tr": "Cevaplandı (",
        "fr": "Répondu (",
        "de": "Beantwortet (",
        "es": "Respondido ("
    },
    "مهتم جداً (": {
        "en": "Hot (",
        "tr": "Çok İlgili (",
        "fr": "Très intéressé (",
        "de": "Sehr interessiert (",
        "es": "Muy interesado ("
    },
    "متابعة (": {
        "en": "Follow-up (",
        "tr": "Takip (",
        "fr": "À relancer (",
        "de": "Nachverfolgung (",
        "es": "Seguimiento ("
    },
    "غير مهتم (": {
        "en": "Not Interested (",
        "tr": "İlgilenmiyor (",
        "fr": "Pas intéressé (",
        "de": "Nicht interessiert (",
        "es": "No interesado ("
    },
    "الهاتف": {
        "en": "Phone",
        "tr": "Telefon",
        "fr": "Téléphone",
        "de": "Telefon",
        "es": "Teléfono"
    },
    "التصنيف (AI)": {
        "en": "AI Classification",
        "tr": "Yapay Zeka Sınıflandırması",
        "fr": "Classification IA",
        "de": "KI-Klassifizierung",
        "es": "Clasificación de IA"
    },
    "ملخص المكالمة": {
        "en": "Call Summary",
        "tr": "Çağrı Özeti",
        "fr": "Résumé de l'appel",
        "de": "Anruf-Zusammenfassung",
        "es": "Resumen de la Llamada"
    },
    "ربط وإدارة خوادم الأدوات الخارجية (Multi-MCP Support)": {
        "en": "Connect & Manage External Tool Servers (Multi-MCP Support)",
        "tr": "Harici Araç Sunucularını Bağlayın ve Yönetin (Multi-MCP)",
        "fr": "Connexion et gestion des serveurs d'outils externes (Support Multi-MCP)",
        "de": "Externe Tool-Server verbinden & verwalten (Multi-MCP-Unterstützung)",
        "es": "Conectar y Gestionar Servidores de Herramientas Externas (Soporte Multi-MCP)"
    },
    "ربط عدة خوادم MCP مستقلة (عبر SSE) في نفس الوقت لتمكين المساعد الصوتي من استدعاء دوالها مجتمعة أثناء المكالمات الحية.": {
        "en": "Connect multiple independent MCP servers (via SSE) simultaneously to enable the voice assistant to call their functions during live calls.",
        "tr": "Sesli asistanın canlı aramalarda fonksiyonları birlikte çağırabilmesi için birden fazla bağımsız MCP sunucusunu (SSE aracılığıyla) bağlayın.",
        "fr": "Connectez plusieurs serveurs MCP indépendants (via SSE) simultanément pour permettre à l'assistant d'exécuter leurs fonctions lors des appels.",
        "de": "Verbinden Sie mehrere unabhängige MCP-Server (über SSE) gleichzeitig, damit der Sprachassistent deren Funktionen live aufrufen kann.",
        "es": "Conecte múltiples servidores MCP independientes (vía SSE) al mismo tiempo para permitir que el asistente invoque sus funciones en llamadas."
    },
    "خوادم نشطة:": {
        "en": "Active Servers:",
        "tr": "Aktif Sunucular:",
        "fr": "Serveurs actifs :",
        "de": "Aktive Server:",
        "es": "Servidores Activos:"
    },
    "إجمالي الدوال:": {
        "en": "Total Tools:",
        "tr": "Toplam Araçlar:",
        "fr": "Total des outils :",
        "de": "Gesamte Tools:",
        "es": "Total de Herramientas:"
    },
    "الدور والشخصية (20 دور + أدوارك)": {
        "en": "Role & Persona (20 Catalog Roles + Custom)",
        "tr": "Rol ve Persona (20 Katalog Rolü + Özel)",
        "fr": "Rôle et Persona (20 rôles catalogue + personnalisés)",
        "de": "Rolle & Persona (20 Katalog-Rollen + Eigene)",
        "es": "Rol y Personalidad (20 Roles de Catálogo + Personalizados)"
    },
    "-- اختر من الكتالوج أو مكتبتك المخصصة --": {
        "en": "-- Select from catalog or your custom library --",
        "tr": "-- Katalogdan veya özel kütüphanenizden seçin --",
        "fr": "-- Sélectionner dans le catalogue ou votre bibliothèque --",
        "de": "-- Aus Katalog oder eigener Bibliothek wählen --",
        "es": "-- Seleccione del catálogo o su biblioteca personalizada --"
    },
    "خدمة عملاء ومبيعات المتجر": {
        "en": "Store Customer Service & Sales",
        "tr": "Mağaza Müşteri Hizmetleri ve Satış",
        "fr": "Service client et ventes du magasin",
        "de": "Kundenservice & Verkauf im Geschäft",
        "es": "Atención al Cliente y Ventas de Tienda"
    },
    "ودود ولطيف ومرح": {
        "en": "Friendly, polite, and lively",
        "tr": "Dost canlısı, kibar ve neşeli",
        "fr": "Amical, poli et chaleureux",
        "de": "Freundlich, höflich und lebendig",
        "es": "Amable, educado y entusiasta"
    },
    "الأدوار المخصصة المحفوظة (": {
        "en": "Saved Custom Roles (",
        "tr": "Kayıtlı Özel Roller (",
        "fr": "Rôles personnalisés enregistrés (",
        "de": "Gespeicherte benutzerdefinierte Rollen (",
        "es": "Roles Personalizados Guardados ("
    },
    "البروفايل الصوتي للـ AI": {
        "en": "AI Voice Persona",
        "tr": "Yapay Zeka Ses Profili",
        "fr": "Profil vocal de l'IA",
        "de": "KI-Sprachprofil",
        "es": "Perfil de Voz con IA"
    },
    "البروفايل الصوتي للـ AI (اختياري)": {
        "en": "AI Voice Persona (Optional)",
        "tr": "Yapay Zeka Ses Profili (İsteğe Bağlı)",
        "fr": "Profil vocal de l'IA (Optionnel)",
        "de": "KI-Sprachprofil (Optional)",
        "es": "Perfil de Voz con IA (Opcional)"
    },
    "إنشاء وتفعيل خط الاتصال السحابي": {
        "en": "Create & Activate Cloud Trunk",
        "tr": "Bulut Trunk'ı Oluştur ve Etkinleştir",
        "fr": "Créer et activer la ligne cloud",
        "de": "Cloud-Trunk erstellen & aktivieren",
        "es": "Crear y Activar Línea en la Nube"
    },
    "انسخ الإعدادات التالية وضعها في لوحة تحكم السنترال (PBX -> Trunks -> Add SIP Trunk)": {
        "en": "Copy the following settings into your PBX control panel (PBX -> Trunks -> Add SIP Trunk)",
        "tr": "Aşağıdaki ayarları kopyalayın ve santral kontrol paneline yapıştırın (PBX -> Trunks -> Add SIP Trunk)",
        "fr": "Copiez les paramètres ci-dessous dans votre panneau PBX (PBX -> Trunks -> Add SIP Trunk)",
        "de": "Kopieren Sie die Einstellungen in Ihre PBX (PBX -> Trunks -> Add SIP Trunk)",
        "es": "Copie los ajustes en su panel PBX (PBX -> Trunks -> Add SIP Trunk)"
    },
    "نسخ الكود": {
        "en": "Copy Code",
        "tr": "Kodu Kopyala",
        "fr": "Copier le code",
        "de": "Code kopieren",
        "es": "Copiar Código"
    },
    "نسخ": {
        "en": "Copy",
        "tr": "Kopyala",
        "fr": "Copier",
        "de": "Kopieren",
        "es": "Copiar"
    },
    "كود الطابور (Extension Code)": {
        "en": "Queue Extension Code",
        "tr": "Kuyruk Dahili Kodu",
        "fr": "Code d'extension de la file",
        "de": "Warteschlangen-Durchwahl",
        "es": "Código de Extensión de Cola"
    },
    "إذا لم يُرفع ملف، سيعزف النظام نغمة انتظار متناغمة وهادئة افتراضياً.": {
        "en": "If no file is uploaded, the system will play a gentle default hold melody.",
        "tr": "Dosya yüklenmezse, sistem varsayılan olarak sakin bir bekleme müziği çalar.",
        "fr": "Si aucun fichier n'est téléversé, le système jouera une mélodie d'attente par défaut.",
        "de": "Wenn keine Datei hochgeladen wird, spielt das System standardmäßig ruhige Wartemusik.",
        "es": "Si no se sube un archivo, el sistema reproducirá una suave melodía de espera predeterminada."
    },
    "حفظ الطابور وتفعيل الكود": {
        "en": "Save Queue & Activate Code",
        "tr": "Kuyruğu Kaydet ve Kodu Etkinleştir",
        "fr": "Enregistrer la file et activer le code",
        "de": "Warteschlange speichern & Code aktivieren",
        "es": "Guardar Cola y Activar Código"
    },
    "تعديل اختصاصات وتوجيهات الطابور للـ AI": {
        "en": "Edit Queue Directives & AI Escalation Rules",
        "tr": "Kuyruk Görevlerini ve Yapay Zeka Yönergelerini Düzenle",
        "fr": "Modifier les directives de la file et règles de transfert IA",
        "de": "Warteschlangen-Aufgaben & KI-Regeln bearbeiten",
        "es": "Editar Directivas de Cola y Reglas de Desvío con IA"
    },
    "طابور الدعم": {
        "en": "Support Queue",
        "tr": "Destek Kuyruğu",
        "fr": "File de support",
        "de": "Support-Warteschlange",
        "es": "Cola de Soporte"
    },
    "وصف واختصاصات الطابور للذكاء الاصطناعي:": {
        "en": "Queue Scope Description for Voice AI:",
        "tr": "Yapay Zeka İçin Kuyruk Açıklaması ve Görevleri:",
        "fr": "Description du périmètre de la file pour l'IA :",
        "de": "Beschreibung des Warteschlangenbereichs für die KI:",
        "es": "Descripción del Ámbito de la Cola para la IA:"
    },
    "يقرأ الذكاء الاصطناعي هذا الوصف أثناء الحوار مع المتصل ليحول إليه تلقائياً عند مطابقة المشكلة.": {
        "en": "The AI reads this description during conversations to automatically escalate when a matching issue occurs.",
        "tr": "Yapay zeka, eşleşen bir sorun olduğunda otomatik aktarmak için bu açıklamayı okur.",
        "fr": "L'IA lit cette description pour transférer automatiquement lors d'un problème correspondant.",
        "de": "Die KI liest diese Beschreibung, um bei passendem Anliegen automatisch weiterzuleiten.",
        "es": "La IA lee esta descripción para desviar automáticamente al detectar un problema coincidente."
    },
    "إضافة موظف وتحويلة داخلية جديدة": {
        "en": "Add New Employee & Extension",
        "tr": "Yeni Çalışan ve Dahili Hat Ekle",
        "fr": "Ajouter un employé et une nouvelle extension",
        "de": "Neuen Mitarbeiter & Durchwahl hinzufügen",
        "es": "Agregar Nuevo Empleado y Extensión"
    },
    "حفظ وإنشاء التحويلة": {
        "en": "Save & Create Extension",
        "tr": "Kaydet ve Dahili Hat Oluştur",
        "fr": "Enregistrer et créer l'extension",
        "de": "Speichern & Durchwahl erstellen",
        "es": "Guardar y Crear Extensión"
    },
    "اسم الخادم": {
        "en": "Server Name",
        "tr": "Sunucu Adı",
        "fr": "Nom du serveur",
        "de": "Servername",
        "es": "Nombre del Servidor"
    },
    "رابط الـ SSE Endpoint (Server URL)": {
        "en": "SSE Endpoint URL (Server URL)",
        "tr": "SSE Uç Noktası Bağlantısı (Server URL)",
        "fr": "URL du point de terminaison SSE",
        "de": "SSE-Endpunkt-URL (Server-URL)",
        "es": "URL del Endpoint SSE (Server URL)"
    },
    "يجب أن يدعم الخادم وسيلة نقل SSE (Server-Sent Events) على شبكة النظام.": {
        "en": "The server must support SSE (Server-Sent Events) transport on the network.",
        "tr": "Sunucu, ağ üzerinde SSE (Server-Sent Events) aktarımını desteklemelidir.",
        "fr": "Le serveur doit supporter le transport SSE (Server-Sent Events).",
        "de": "Der Server muss SSE (Server-Sent Events) im Netzwerk unterstützen.",
        "es": "El servidor debe admitir transporte SSE (Server-Sent Events) en la red."
    },
    "مفتاح الحماية / Bearer Token (اختياري)": {
        "en": "Security Key / Bearer Token (Optional)",
        "tr": "Güvenlik Anahtarı / Bearer Token (İsteğe Bağlı)",
        "fr": "Clé de sécurité / Bearer Token (Optionnel)",
        "de": "Sicherheitsschlüssel / Bearer Token (Optional)",
        "es": "Clave de Seguridad / Bearer Token (Opcional)"
    },
    "فحص الاتصال واكتشاف الأدوات": {
        "en": "Test Connection & Discover Tools",
        "tr": "Bağlantıyı Test Et ve Araçları Keşfet",
        "fr": "Tester la connexion et découvrir les outils",
        "de": "Verbindung testen & Tools entdecken",
        "es": "Probar Conexión y Descubrir Herramientas"
    },
    "إنشاء حملة اتصال ورفع قائمة العملاء": {
        "en": "Create Outbound Campaign & Upload Leads",
        "tr": "Arama Kampanyası Oluştur ve Müşteri Listesi Yükle",
        "fr": "Créer une campagne d'appels et importer des prospects",
        "de": "Ausgehende Kampagne erstellen & Kontakte hochladen",
        "es": "Crear Campaña Saliente y Subir Clientes"
    },
    "ارفع ملف العملاء وحدد سيناريو المكالمة لفرزهم وتنظيمهم في الـ CRM": {
        "en": "Upload contact list and define call scenario to qualify leads in CRM",
        "tr": "Müşteri dosyasını yükleyin ve CRM'de düzenlemek için arama senaryosunu belirleyin",
        "fr": "Téléversez la liste de contacts et définissez le scénario pour qualifier dans le CRM",
        "de": "Laden Sie die Kundenliste hoch und definieren Sie das Szenario zur Qualifizierung im CRM",
        "es": "Suba la lista de clientes y defina el escenario de llamada para clasificarlos en el CRM"
    },
    "المساعد الصوتي المنفذ للحملة": {
        "en": "Voice Assistant for Campaign",
        "tr": "Kampanyayı Yürütecek Sesli Asistan",
        "fr": "Assistant vocal exécutant la campagne",
        "de": "Sprachassistent für die Kampagne",
        "es": "Asistente de Voz para la Campaña"
    },
    "سيناريو وتوجيهات المكالمة (Call Scenario Prompt) *": {
        "en": "Call Scenario Prompt & Directives *",
        "tr": "Arama Senaryosu ve Yönergeleri (Prompt) *",
        "fr": "Scénario et directives d'appel (Prompt) *",
        "de": "Anrufszenario & Anweisungen (Prompt) *",
        "es": "Escenario y Directivas de Llamada (Prompt) *"
    },
    "يمكنك استخدام المتغيرات مثل {name} داخل السيناريو وسيتم استبدالها ببيانات كل عميل تلقائياً.": {
        "en": "You can use variables like {name} which will be automatically replaced with customer data.",
        "tr": "Senaryo içinde {name} gibi değişkenler kullanabilirsiniz, bunlar müşteri verileriyle değiştirilir.",
        "fr": "Vous pouvez utiliser des variables comme {name} qui seront remplacées par les données clients.",
        "de": "Sie können Variablen wie {name} verwenden, die automatisch durch Kundendaten ersetzt werden.",
        "es": "Puede usar variables como {name} que se sustituirán automáticamente con los datos del cliente."
    },
    "ملف بيانات العملاء (Excel, CSV, TXT, JSON) *": {
        "en": "Customer Data File (Excel, CSV, TXT, JSON) *",
        "tr": "Müşteri Veri Dosyası (Excel, CSV, TXT, JSON) *",
        "fr": "Fichier de données clients (Excel, CSV, TXT, JSON) *",
        "de": "Kundendatendatei (Excel, CSV, TXT, JSON) *",
        "es": "Archivo de Datos de Clientes (Excel, CSV, TXT, JSON) *"
    },
    "اضغط لاختيار ملف من جهازك أو اسحبه وأفلته هنا": {
        "en": "Click to select a file or drag and drop here",
        "tr": "Cihazınızdan dosya seçmek için tıklayın veya buraya sürükleyip bırakın",
        "fr": "Cliquez pour choisir un fichier ou glissez-déposez ici",
        "de": "Klicken Sie zum Auswählen oder ziehen Sie die Datei hierher",
        "es": "Haga clic para elegir un archivo o arrástrelo y suéltelo aquí"
    },
    "يدعم: Excel (.xlsx, .xls), CSV, نصي (.txt), JSON - بترميز UTF-8 أو عربي": {
        "en": "Supports: Excel (.xlsx, .xls), CSV, Text (.txt), JSON - UTF-8 encoded",
        "tr": "Desteklenen: Excel (.xlsx, .xls), CSV, Metin (.txt), JSON - UTF-8 kodlu",
        "fr": "Supporte : Excel (.xlsx, .xls), CSV, Texte (.txt), JSON - Encodage UTF-8",
        "de": "Unterstützt: Excel (.xlsx, .xls), CSV, Text (.txt), JSON - UTF-8-Codierung",
        "es": "Soporta: Excel (.xlsx, .xls), CSV, Texto (.txt), JSON - Codificación UTF-8"
    },
    "إدارة التزامن والجدولة الذكية:": {
        "en": "Concurrency Management & Smart Scheduling:",
        "tr": "Eşzamanlılık Yönetimi ve Akıllı Zamanlama:",
        "fr": "Gestion de la simultanéité et planification intelligente :",
        "de": "Parallelitätsverwaltung & Intelligente Terminierung:",
        "es": "Gestión de Concurrencia y Programación Inteligente:"
    },
    "رفع وتنظيم العملاء في الـ CRM": {
        "en": "Upload & Organize Leads in CRM",
        "tr": "Müşterileri Yükle ve CRM'de Düzenle",
        "fr": "Téléverser et organiser les prospects dans le CRM",
        "de": "Kunden hochladen & im CRM organisieren",
        "es": "Subir y Organizar Clientes en el CRM"
    },
    "تصنيف الاهتمام (AI)": {
        "en": "Interest Score (AI)",
        "tr": "İlgi Düzeyi (Yapay Zeka)",
        "fr": "Niveau d'intérêt (IA)",
        "de": "Interessen-Einstufung (KI)",
        "es": "Nivel de Interés (IA)"
    },
    "0 ثانية": {
        "en": "0 seconds",
        "tr": "0 saniye",
        "fr": "0 seconde",
        "de": "0 Sekunden",
        "es": "0 segundos"
    },
    "لا يوجد ملخص بعد.": {
        "en": "No summary available yet.",
        "tr": "Henüz özet bulunmuyor.",
        "fr": "Aucun résumé disponible pour le moment.",
        "de": "Noch keine Zusammenfassung verfügbar.",
        "es": "Aún no hay resumen disponible."
    },
    "شحن المحفظة": {
        "en": "Top-up Wallet",
        "tr": "Cüzdanı Doldur",
        "fr": "Recharger le portefeuille",
        "de": "Guthaben aufladen",
        "es": "Recargar Billetera"
    },
    "0 دقيقة": {
        "en": "0 minutes",
        "tr": "0 dakika",
        "fr": "0 minute",
        "de": "0 Minuten",
        "es": "0 minutos"
    },
    "توثيق كامل لكل عملية شحن وخصم مكالمة وتحديث رصيد لحظي": {
        "en": "Complete audit trail for wallet top-ups, call deductions, and real-time balance updates",
        "tr": "Her yükleme, çağrı ücretlendirmesi ve anlık bakiye güncellemesi için tam denetim kaydı",
        "fr": "Historique complet des recharges, déductions d'appels et mises à jour de solde en direct",
        "de": "Vollständige Dokumentation aller Aufladungen, Anrufgebühren und Echtzeit-Salden",
        "es": "Registro completo de cada recarga, deducción de llamada y actualización de saldo en tiempo real"
    },
    "جميع الحركات": {
        "en": "All Transactions",
        "tr": "Tüm İşlemler",
        "fr": "Toutes les transactions",
        "de": "Alle Transaktionen",
        "es": "Todas las Transacciones"
    },
    "خصم مكالمات صوتية": {
        "en": "Voice Calls Deductions",
        "tr": "Sesli Çağrı Kesintileri",
        "fr": "Déductions d'appels vocaux",
        "de": "Sprachanruf-Abzüge",
        "es": "Deducción de Llamadas de Voz"
    },
    "رصيد ترحيبي": {
        "en": "Welcome Bonus",
        "tr": "Hoş Geldin Bakiyesi",
        "fr": "Crédit de bienvenue",
        "de": "Willkommensguthaben",
        "es": "Saldo de Bienvenida"
    },
    "الدقائق / الثواني": {
        "en": "Minutes / Seconds",
        "tr": "Dakika / Saniye",
        "fr": "Minutes / Secondes",
        "de": "Minuten / Sekunden",
        "es": "Minutos / Segundos"
    },
    "السعر المطبق": {
        "en": "Applied Rate",
        "tr": "Uygulanan Ücret",
        "fr": "Tarif appliqué",
        "de": "Angewandter Tarif",
        "es": "Tarifa Aplicada"
    },
    "جاري تحميل سجل الحركات المالية...": {
        "en": "Loading billing transactions...",
        "tr": "Finansal işlemler geçmişi yükleniyor...",
        "fr": "Chargement de l'historique des transactions...",
        "de": "Transaktionsverlauf wird geladen...",
        "es": "Cargando historial de transacciones financieras..."
    },
    "برنامج الشركاء وحلول الـ SaaS (Partner & Reseller Portal)": {
        "en": "Partner & Reseller SaaS Portal",
        "tr": "İş Ortakları ve SaaS Bayi Portalı",
        "fr": "Portail Partenaires & Revendeurs SaaS",
        "de": "Partner- & Reseller-SaaS-Portal",
        "es": "Portal de Socios y Revendedores SaaS"
    },
    "إدارة عملاء الساس التابعين (Sub-Clients)": {
        "en": "Manage SaaS Sub-Clients",
        "tr": "Bağlı SaaS Müşterilerini Yönetin",
        "fr": "Gérer les sous-clients SaaS",
        "de": "SaaS-Unterkunden verwalten",
        "es": "Gestionar Sub-Clientes SaaS"
    },
    "قائمة بجميع حسابات العملاء التي تم إنشاؤها عبر الـ API الخلفي التابع لنظامك": {
        "en": "List of all client accounts created via your backend system API",
        "tr": "Sisteminizin arka uç API'si aracılığıyla oluşturulan tüm müşteri hesapları",
        "fr": "Liste de tous les comptes clients créés via l'API backend de votre système",
        "de": "Liste aller über Ihre Backend-API erstellten Kundenkonten",
        "es": "Lista de todas las cuentas de clientes creadas a través de la API de su sistema"
    },
    "معرف العميل (ID)": {
        "en": "Client ID",
        "tr": "Müşteri Kimliği (ID)",
        "fr": "ID Client",
        "de": "Kunden-ID",
        "es": "ID de Cliente"
    },
    "الاسم والبيانات": {
        "en": "Name & Details",
        "tr": "İsim ve Detaylar",
        "fr": "Nom et détails",
        "de": "Name & Details",
        "es": "Nombre y Detalles"
    },
    "المعرف الخارجي (Ref)": {
        "en": "External Ref",
        "tr": "Harici Referans",
        "fr": "Réf. externe",
        "de": "Externe Referenz",
        "es": "Referencia Externa"
    },
    "الدقائق المستهلكة": {
        "en": "Minutes Used",
        "tr": "Kullanılan Dakika",
        "fr": "Minutes consommées",
        "de": "Verbrauchte Minuten",
        "es": "Minutos Consumidos"
    },
    "إجمالي التكلفة": {
        "en": "Total Cost",
        "tr": "Toplam Maliyet",
        "fr": "Coût total",
        "de": "Gesamtkosten",
        "es": "Costo Total"
    },
    "سقف الاستهلاك (Cap)": {
        "en": "Usage Cap",
        "tr": "Tüketim Üst Sınırı",
        "fr": "Plafond d'utilisation",
        "de": "Verbrauchslimit (Cap)",
        "es": "Límite de Consumo (Cap)"
    },
    "جاري تحميل عملاء الساس...": {
        "en": "Loading SaaS clients...",
        "tr": "SaaS müşterileri yükleniyor...",
        "fr": "Chargement des clients SaaS...",
        "de": "SaaS-Kunden werden geladen...",
        "es": "Cargando clientes SaaS..."
    },
    "سجل مكالمات عملاء الساس (Partner Sub-Clients CDR)": {
        "en": "Partner Sub-Clients CDR Log",
        "tr": "İş Ortağı Müşterileri Çağrı Kayıtları (CDR)",
        "fr": "Historique des appels des sous-clients (CDR)",
        "de": "Anrufprotokoll der Partnerkunden (CDR)",
        "es": "Registro de Llamadas de Sub-Clientes (CDR)"
    },
    "تفاصيل استهلاك مكالمات عملائك والدقائق المخصومة من رصيدك بالسعر المخفض": {
        "en": "Call usage details and minutes deducted from your balance at the discounted wholesale rate",
        "tr": "Müşterilerinizin çağrı kullanım detayları ve indirimli fiyattan bakiyenizden düşülen dakikalar",
        "fr": "Détails de consommation d'appels et minutes déduites de votre solde au tarif réduit",
        "de": "Verbrauchsdetails und vom Guthaben abgezogene Minuten zum ermäßigten Partnertarif",
        "es": "Detalles del consumo de llamadas y minutos deducidos de su saldo a tarifa mayorista"
    },
    "العميل التابع": {
        "en": "Sub-Client",
        "tr": "Bağlı Müşteri",
        "fr": "Sous-client",
        "de": "Unterkunde",
        "es": "Sub-Cliente"
    },
    "الاتجاه والطرف": {
        "en": "Direction & Party",
        "tr": "Yön ve Taraf",
        "fr": "Direction et tiers",
        "de": "Richtung & Teilnehmer",
        "es": "Dirección y Parte"
    },
    "المدة بالثواني": {
        "en": "Duration (Sec)",
        "tr": "Süre (Saniye)",
        "fr": "Durée (sec)",
        "de": "Dauer (Sek.)",
        "es": "Duración (Seg.)"
    },
    "الدقائق (Ceiling)": {
        "en": "Billed Minutes",
        "tr": "Faturalandırılan Dakika",
        "fr": "Minutes facturées",
        "de": "Abgerechnete Minuten",
        "es": "Minutos Facturados"
    },
    "التكلفة المخصومة": {
        "en": "Cost Deducted",
        "tr": "Düşülen Maliyet",
        "fr": "Coût déduit",
        "de": "Abgezogene Kosten",
        "es": "Costo Deducido"
    },
    "الملخص الذكي": {
        "en": "AI Summary",
        "tr": "Akıllı Özet",
        "fr": "Résumé IA",
        "de": "KI-Zusammenfassung",
        "es": "Resumen de IA"
    },
    "لا توجد مكالمات مسجلة لعملاء الشريك حتى الآن.": {
        "en": "No calls recorded for partner clients yet.",
        "tr": "İş ortağı müşterileri için henüz kayıtlı çağrı bulunmuyor.",
        "fr": "Aucun appel enregistré pour les sous-clients pour le moment.",
        "de": "Bisher keine Anrufe für Partnerkunden verzeichnet.",
        "es": "No hay llamadas registradas para los clientes asociados todavía."
    },
    "صندوق المحادثات الموحدة (Omnichannel Inbox)": {
        "en": "Omnichannel Inbox (Chatwoot Integration)",
        "tr": "Birleşik İletişim Kutusu (Omnichannel Inbox)",
        "fr": "Boîte de réception omnicanale (Chatwoot)",
        "de": "Omnichannel-Postfach (Chatwoot-Integration)",
        "es": "Bandeja Omnicanal Unificada (Chatwoot)"
    },
    "إدارة كافة القنوات (واتساب، ويب، تليجرام، فيسبوك) مع استمرار المكالمة الصوتية بدون انقطاع": {
        "en": "Manage all channels (WhatsApp, Web, Telegram, Facebook) without interrupting voice calls",
        "tr": "Sesli aramayı kesintiye uğratmadan tüm kanalları (WhatsApp, Web, Telegram, Facebook) yönetin",
        "fr": "Gérez tous les canaux (WhatsApp, Web, Telegram, Facebook) sans interruption des appels vocaux",
        "de": "Verwalten Sie alle Kanäle (WhatsApp, Web, Telegram, Facebook) ohne Unterbrechung der Sprachverbindung",
        "es": "Gestione todos los canales (WhatsApp, Web, Telegram, Facebook) sin interrumpir las llamadas de voz"
    },
    "المساعد الصوتي قيد التشغيل": {
        "en": "Voice Assistant Active",
        "tr": "Sesli Asistan Çalışıyor",
        "fr": "Assistant vocal en cours d'exécution",
        "de": "Sprachassistent aktiv",
        "es": "Asistente de Voz en Funcionamiento"
    }
}

def clean_key(txt):
    k = re.sub(r'[^a-zA-Z0-9]+', '_', txt[:30]).strip('_').lower()
    return f"auto_{k}"

def run():
    print(f"Loaded {len(TRANSLATIONS)} master translations.")

    # 1. Update room.html with data-i18n attributes
    with open(ROOM_PATH, 'r', encoding='utf-8') as f:
        html = f.read()

    replacements_count = 0
    new_keys_for_common = {}

    for ar_txt, trans in TRANSLATIONS.items():
        key = clean_key(trans['en'])
        new_keys_for_common[key] = {
            'ar': ar_txt,
            'en': trans['en'],
            'tr': trans['tr'],
            'fr': trans['fr'],
            'de': trans['de'],
            'es': trans['es']
        }

        # Match exact tags containing this arabic text without data-i18n
        # Escape special characters in ar_txt for regex
        escaped_ar = re.escape(ar_txt)
        # Search for <tag attrs>ar_txt</tag> where data-i18n is not in attrs
        pattern = re.compile(r'<([a-zA-Z0-9]+)([^>]*?)>' + escaped_ar + r'</\1>')
        
        def replace_match(m):
            tag = m.group(1)
            attrs = m.group(2)
            if 'data-i18n' in attrs or 'data-lang-option' in attrs:
                return m.group(0)
            return f'<{tag}{attrs} data-i18n="{key}">{ar_txt}</{tag}>'

        new_html, count = pattern.subn(replace_match, html)
        if count > 0:
            replacements_count += count
            html = new_html

    with open(ROOM_PATH, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"Tagged {replacements_count} HTML elements in room.html.")

    # 2. Inject new keys into common.js
    with open(COMMON_JS_PATH, 'r', encoding='utf-8') as f:
        js = f.read()

    addition_block = "\n// AUTO-GENERATED EXPANDED 6-LANGUAGE DICTIONARY ADDITIONS\nconst ROOM_EXPANDED_I18N = {\n"
    for l in ['ar', 'en', 'tr', 'fr', 'de', 'es']:
        addition_block += f"  {l}: {{\n"
        for k, v_dict in new_keys_for_common.items():
            val = v_dict[l].replace('"', '\\"').replace('\n', ' ')
            addition_block += f'    "{k}": "{val}",\n'
        addition_block += "  },\n"
    addition_block += "};\n"
    addition_block += """
for (const l of Object.keys(ROOM_EXPANDED_I18N)) {
  if (APP_I18N[l]) {
    Object.assign(APP_I18N[l], ROOM_EXPANDED_I18N[l]);
  }
}
"""

    if '// AUTO-GENERATED EXPANDED 6-LANGUAGE DICTIONARY ADDITIONS' in js:
        # replace existing
        js = re.sub(
            r'// AUTO-GENERATED EXPANDED 6-LANGUAGE DICTIONARY ADDITIONS.*?(?=window\.SUPPORTED_LANGUAGES)',
            addition_block + '\n',
            js,
            flags=re.DOTALL
        )
    else:
        # insert before window.SUPPORTED_LANGUAGES
        js = js.replace('window.SUPPORTED_LANGUAGES = SUPPORTED_LANGUAGES;', addition_block + '\nwindow.SUPPORTED_LANGUAGES = SUPPORTED_LANGUAGES;')

    with open(COMMON_JS_PATH, 'w', encoding='utf-8') as f:
        f.write(js)
    print(f"Added {len(new_keys_for_common)} keys across 6 languages to common.js.")

if __name__ == '__main__':
    run()
