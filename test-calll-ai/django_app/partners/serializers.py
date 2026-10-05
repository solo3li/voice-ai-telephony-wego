"""
Serializers for Partner SaaS Multi-Tenant RESTful API (v1).
Used by Django REST Framework and drf-spectacular for auto-generated OpenAPI documentation.
"""
from rest_framework import serializers


class BaseSuccessResponseSerializer(serializers.Serializer):
    status = serializers.CharField(default="success")
    message = serializers.CharField(required=False)


class BaseErrorResponseSerializer(serializers.Serializer):
    status = serializers.CharField(default="error")
    message = serializers.CharField()


# ============================================================================
# Partner Dashboard & Settings
# ============================================================================

class PartnerDashboardResponseSerializer(serializers.Serializer):
    status = serializers.CharField(default="success")
    partner_id = serializers.IntegerField()
    company_name = serializers.CharField()
    brand_name = serializers.CharField()
    api_key = serializers.CharField()
    client_cap = serializers.IntegerField()
    total_clients = serializers.IntegerField()
    active_clients = serializers.IntegerField()
    total_calls_today = serializers.IntegerField()
    webhook_url = serializers.URLField(allow_blank=True)


class PartnerSettingsUpdateRequestSerializer(serializers.Serializer):
    brand_name = serializers.CharField(required=False, allow_blank=True)
    webhook_url = serializers.URLField(required=False, allow_blank=True)
    webhook_secret = serializers.CharField(required=False, allow_blank=True)


# ============================================================================
# Managed Clients (Multi-Tenant SaaS)
# ============================================================================

class PartnerClientRegisterRequestSerializer(serializers.Serializer):
    external_client_id = serializers.CharField(required=True, help_text="المعرف الفريد للعميل في نظام الشريك (External ID)")
    name = serializers.CharField(required=True, help_text="اسم العميل أو المؤسسة الفرعية")
    email = serializers.EmailField(required=False, allow_blank=True)
    phone_number = serializers.CharField(required=False, allow_blank=True)
    concurrent_call_limit = serializers.IntegerField(default=1, help_text="الحد الأقصى للمكالمات المتزامنة لهذا العميل")
    is_active = serializers.BooleanField(default=True)


class PartnerClientResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    external_client_id = serializers.CharField()
    name = serializers.CharField()
    email = serializers.EmailField()
    phone_number = serializers.CharField()
    concurrent_call_limit = serializers.IntegerField()
    is_active = serializers.BooleanField()
    total_calls = serializers.IntegerField(read_only=True)
    total_documents = serializers.IntegerField(read_only=True)
    total_employees = serializers.IntegerField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)


class PartnerClientsListResponseSerializer(serializers.Serializer):
    status = serializers.CharField(default="success")
    total = serializers.IntegerField()
    clients = PartnerClientResponseSerializer(many=True)


# ============================================================================
# Client Voice Personas & Studio
# ============================================================================

class PartnerClientProfileSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField()
    voice_name = serializers.CharField(default="Aoede")
    gender = serializers.ChoiceField(choices=[('female', 'أنثى'), ('male', 'ذكر')])
    language = serializers.CharField(default="arabic")
    dialect = serializers.CharField(default="egyptian")
    persona_role = serializers.CharField(required=False, allow_blank=True)
    speaking_style = serializers.CharField(required=False, allow_blank=True)
    verbosity = serializers.ChoiceField(choices=[('concise', 'موجز'), ('balanced', 'متوازن'), ('detailed', 'مفصل')])
    welcome_message = serializers.CharField(required=False, allow_blank=True)
    is_welcome_message_enabled = serializers.BooleanField(default=True, required=False)
    custom_instructions = serializers.CharField(required=False, allow_blank=True)
    is_active = serializers.BooleanField(default=True)


class PartnerClientProfileCreateRequestSerializer(serializers.Serializer):
    name = serializers.CharField(required=True)
    voice_name = serializers.CharField(default="Aoede")
    gender = serializers.ChoiceField(choices=[('female', 'أنثى'), ('male', 'ذكر')], default='female')
    language = serializers.CharField(default="arabic")
    dialect = serializers.CharField(default="egyptian")
    persona_role = serializers.CharField(required=False, default="خدمة عملاء ومبيعات")
    speaking_style = serializers.CharField(required=False, default="ودود ومهذب")
    verbosity = serializers.ChoiceField(choices=[('concise', 'موجز'), ('balanced', 'متوازن'), ('detailed', 'مفصل')], default='balanced')
    welcome_message = serializers.CharField(required=False, allow_blank=True)
    is_welcome_message_enabled = serializers.BooleanField(default=True, required=False)
    custom_instructions = serializers.CharField(required=False, allow_blank=True)
    is_active = serializers.BooleanField(default=True)


# ============================================================================
# Client Customer Memory & CRM
# ============================================================================

class PartnerClientMemorySerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    phone_number = serializers.CharField()
    customer_name = serializers.CharField(required=False, allow_blank=True)
    permanent_facts = serializers.CharField(required=False, allow_blank=True)
    immediate_context = serializers.CharField(required=False, allow_blank=True)
    last_call_at = serializers.DateTimeField(read_only=True, allow_null=True)
    call_count = serializers.IntegerField(read_only=True)


class PartnerClientMemoryCreateRequestSerializer(serializers.Serializer):
    phone_number = serializers.CharField(required=True)
    customer_name = serializers.CharField(required=False, allow_blank=True)
    permanent_facts = serializers.CharField(required=False, allow_blank=True)
    immediate_context = serializers.CharField(required=False, allow_blank=True)


# ============================================================================
# Client RAG Knowledge Base
# ============================================================================

class PartnerClientDocumentSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    file_name = serializers.CharField()
    file_type = serializers.CharField()
    file_size = serializers.IntegerField()
    chunk_count = serializers.IntegerField()
    status = serializers.CharField()
    created_at = serializers.DateTimeField(read_only=True)


class PartnerClientDocumentUploadRequestSerializer(serializers.Serializer):
    file = serializers.FileField(required=False, help_text="ملف المستند المراد رفعه للعميل (PDF, DOCX, TXT, MD, CSV, JSON)")
    file_url = serializers.URLField(required=False, help_text="رابط مباشر لمستند خارجي (PDF, DOCX, CSV, TXT, MD, JSON)")
    title = serializers.CharField(required=False, help_text="عنوان مخصص للمستند (اختياري - يتم استخدام اسم الملف تلقائياً)")
    content = serializers.CharField(required=False, help_text="نص مباشر كبديل في حال عدم إرفاق ملف أو رابط")


class PartnerClientRAGQueryRequestSerializer(serializers.Serializer):
    query = serializers.CharField(required=True)
    limit = serializers.IntegerField(default=4, required=False)


# ============================================================================
# Client Telephony & Trunks
# ============================================================================

class PartnerClientTrunkSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField()
    trunk_type = serializers.CharField()
    host = serializers.CharField()
    port = serializers.IntegerField()
    username = serializers.CharField()
    is_active = serializers.BooleanField()


class PartnerClientNumberSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    phone_number = serializers.CharField()
    trunk_id = serializers.IntegerField(allow_null=True)
    route_to = serializers.CharField()
    is_active = serializers.BooleanField()


# ============================================================================
# Client Call Center: Employees & Queues
# ============================================================================

class PartnerClientEmployeeSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField()
    extension = serializers.CharField()
    department = serializers.CharField(required=False, allow_blank=True)
    protocol = serializers.CharField(default="webrtc_livekit")
    status = serializers.CharField(default="ready")
    is_available = serializers.BooleanField(default=True)


class PartnerClientQueueSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField()
    queue_number = serializers.CharField()
    strategy = serializers.CharField(default="round_robin")
    timeout = serializers.IntegerField(default=30)
    members_count = serializers.IntegerField(read_only=True)


# ============================================================================
# Client FastMCP Servers
# ============================================================================

class PartnerClientMCPServerSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField()
    url = serializers.URLField()
    is_active = serializers.BooleanField()
    last_synced_at = serializers.DateTimeField(allow_null=True, read_only=True)
    tools = serializers.ListField(child=serializers.DictField(), read_only=True)


# ============================================================================
# Client WebRTC & Calls
# ============================================================================

class PartnerClientTokenResponseSerializer(serializers.Serializer):
    status = serializers.CharField(default="success")
    token = serializers.CharField()
    room = serializers.CharField()
    identity = serializers.CharField()
    livekit_url = serializers.CharField()


class PartnerClientDialRequestSerializer(serializers.Serializer):
    to_number = serializers.CharField(required=True)
    from_number = serializers.CharField(required=False, allow_blank=True)
    persona_id = serializers.IntegerField(required=False, allow_null=True)
    scenario_prompt = serializers.CharField(required=False, allow_blank=True)


class PartnerClientCallSessionSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    call_id = serializers.CharField()
    from_number = serializers.CharField()
    to_number = serializers.CharField()
    status = serializers.CharField()
    duration = serializers.IntegerField()
    started_at = serializers.DateTimeField()
    ended_at = serializers.DateTimeField(allow_null=True)
    recording_url = serializers.URLField(allow_null=True)
    summary = serializers.CharField(allow_blank=True)


# ============================================================================
# Client Campaigns & Outbound Dialing (Inngest Powered)
# ============================================================================

class PartnerClientCampaignContactItemSerializer(serializers.Serializer):
    phone_number = serializers.CharField(required=True)
    name = serializers.CharField(required=False, allow_blank=True, default="")
    attributes = serializers.DictField(required=False, default=dict)


class PartnerClientCampaignCreateRequestSerializer(serializers.Serializer):
    name = serializers.CharField(required=False, help_text="اسم الحملة التسويقية أو التشغيلية (اختياري في حال رفع ملف)")
    file = serializers.FileField(required=False, help_text="ملف جهات الاتصال المراد رفعه (Excel: .xlsx, .xls أو CSV: .csv أو TXT أو JSON)")
    file_url = serializers.URLField(required=False, help_text="رابط مباشر لملف جهات الاتصال (Excel: .xlsx, .xls أو CSV: .csv أو TXT أو JSON)")
    agent_profile_id = serializers.IntegerField(required=False, allow_null=True)
    call_prompt = serializers.CharField(required=False, allow_blank=True)
    max_retries = serializers.IntegerField(default=1, required=False)
    retry_delay_minutes = serializers.IntegerField(default=15, required=False)
    gateway_type = serializers.CharField(default='auto', required=False)
    gateway_id = serializers.IntegerField(required=False, allow_null=True)
    contacts = PartnerClientCampaignContactItemSerializer(many=True, required=False)


class PartnerClientCampaignSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField()
    agent_profile_id = serializers.IntegerField(allow_null=True)
    agent_profile_name = serializers.CharField()
    call_prompt = serializers.CharField()
    status = serializers.CharField()
    status_display = serializers.CharField()
    total_contacts = serializers.IntegerField()
    completed_contacts = serializers.IntegerField()
    answered_contacts = serializers.IntegerField()
    hot_leads_count = serializers.IntegerField()
    warm_leads_count = serializers.IntegerField()
    cold_leads_count = serializers.IntegerField()
    progress_percent = serializers.FloatField()
    created_at = serializers.CharField()
    updated_at = serializers.CharField()


class PartnerClientCampaignsListResponseSerializer(serializers.Serializer):
    status = serializers.CharField(default="success")
    total = serializers.IntegerField()
    campaigns = PartnerClientCampaignSerializer(many=True)


class PartnerClientCampaignDetailResponseSerializer(serializers.Serializer):
    status = serializers.CharField(default="success")
    campaign = PartnerClientCampaignSerializer()
    contacts = serializers.ListField(child=serializers.DictField())
    total_contacts_count = serializers.IntegerField()

