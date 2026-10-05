"""
OpenAPI 3.1 Specification for Direct Platform User Developer API (/api/v1/).
Supports bilingual Arabic ('ar') and English ('en') with complete schemas,
endpoint summaries, realistic examples, and security definitions.
"""

def get_user_openapi_spec(server_url: str = "/api/v1", lang: str = "ar") -> dict:
    lang = "en" if lang.lower() == "en" else "ar"
    is_ar = (lang == "ar")

    info = {
        "title": "واجهة برمجة تطبيقات المساعد الصوتي (Developer Voice API)" if is_ar else "Voice AI Developer API (Platform REST Reference)",
        "version": "1.0.0",
        "description": (
            "دليل تكامل واجهات المطورين المباشرة (Direct Developer API). "
            "يتيح لك هذا الـ API ربط وتضمين المساعد الصوتي الذكي داخل موقعك أو تطبيقك أو نظامك الخاص مباشرة "
            "باستخدام مفتاح الـ API الشخصي الخاص بك (X-API-Key). "
            "تتم إدارة الموارد التابعة لحسابك (الشخصيات، المستندات، خوادم FastMCP، الموظفين، واستخراج توكنات WebRTC لبدء المكالمات الحية) بكل سلاسة."
            if is_ar else
            "Direct Developer Integration Guide for Platform Users. "
            "This API enables you to embed intelligent, dialect-aware conversational voice AI directly into your apps and web services "
            "using your personal API key (X-API-Key). "
            "Effortlessly manage your voice personas, CRM customer memories, FastMCP servers, and issue ephemeral WebRTC LiveKit tokens for live calling."
        ),
        "contact": {
            "name": "فريق دعم المطورين" if is_ar else "Developer API Support",
            "url": "https://localhost/api/v1/docs/"
        }
    }

    tags_ar = [
        {"name": "1. الحساب والرصيد (Account & Balance)", "description": "استعراض تفاصيل الحساب، الرصيد المالي الحالي بالدولار، والشخصية المفعلة وإحصائيات النظام."},
        {"name": "2. الصوت واللهجات والشخصيات", "description": "إدارة بروفايلات الذكاء الاصطناعي، اللهجات (سعودي، مصري، شامي، فصحى)، وتفعيل الشخصيات."},
        {"name": "3. ذاكرة وسياق العملاء CRM", "description": "سجلات الذاكرة التراكمية، ملاحظات المكالمات، والاستعلام برقم هاتف المتصل."},
        {"name": "4. قواعد المعرفة والاستعلام الدلالي RAG", "description": "رفع المستندات وفهرستها دلالياً بالمتجهات (pgvector) والبحث الذكي عبر Gemini."},
        {"name": "5. خوادم FastMCP والأدوات الحية", "description": "ربط خوادم FastMCP الخارجية عبر بروتوكول SSE ومزامنة أدوات الذكاء الاصطناعي."},
        {"name": "6. السنترالات والخطوط والأرقام", "description": "ربط سنترالات PBX (Issabel)، خطوط SIP الصادرة، وربط أرقام الـ DIDs."},
        {"name": "7. دليل الموظفين والتحويلات", "description": "إدارة الموظفين والتحويلات الداخلية للعميل وحالات التوفر (Ready, Busy, Offline)."},
        {"name": "8. طوابير الانتظار والكول سنتر", "description": "طوابير الكول سنتر واستراتيجيات التوزيع (Round Robin) وإدارة الأعضاء."},
        {"name": "9. حملات الاتصال والعملاء (Campaigns)", "description": "إنشاء وإدارة حملات الاتصال الآلي الصادرة وجدولة الاتصال المتوازي عبر Inngest."},
        {"name": "10. سجلات المكالمات والفوترة", "description": "استعراض سجلات المكالمات CDR، الدقائق المفوترة، تكلفة المكالمة، وملخصات المحادثة."},
        {"name": "11. إشعارات الويبهوك", "description": "استقبال إشعارات انتهاء المكالمات والتحقق البرمجي من الأحداث الموقعة."},
        {"name": "12. الذاكرة المنظمة اللحظية للنشاط (Live Context)", "description": "حقن واستبدال فوري لبيانات المطاعم والمنيو والفروع في كاش Redis فائق السرعة (< 2ms) لمنع الهلوسة في المكالمات."}
    ]

    tags_en = [
        {"name": "1. Account & Balance", "description": "Retrieve account details, available wallet balance, and active persona status."},
        {"name": "2. Voice Profiles & Personas", "description": "Create and manage AI agent personalities, dialects, and activation."},
        {"name": "3. Customer CRM & Context Memory", "description": "Cumulative caller history, CRM customer memory, phone lookups, and notes."},
        {"name": "4. Knowledge Base & Semantic RAG", "description": "Document ingestion, pgvector semantic indexing, and RAG knowledge search."},
        {"name": "5. FastMCP Servers & Live Tools", "description": "Connect external FastMCP SSE servers and synchronize live AI tools."},
        {"name": "6. Telephony, PBX & DIDs", "description": "PBX trunks (Issabel), outbound SIP endpoints, and DID phone number mapping."},
        {"name": "7. Employee Directory & Extensions", "description": "Staff directory, internal SIP extensions, call transfers, and agent availability status."},
        {"name": "8. Call Queues & Routing", "description": "Call center queues, routing strategies (Round Robin), and queue membership."},
        {"name": "9. Outbound Campaigns", "description": "Create and manage automated outbound calling campaigns and dial execution via Inngest."},
        {"name": "10. Call Logs & CDR", "description": "Call detail records (CDR), billed minute deduction, call recordings, and AI conversation summaries."},
        {"name": "11. Webhooks & Events", "description": "Configure webhook endpoints for call.completed notifications and event payloads."},
        {"name": "12. Structured Live Context", "description": "Real-time in-memory cache (< 2ms) for dynamic business data (menus, branches, delivery zones, out of stock)."}
    ]

    tags = tags_ar if is_ar else tags_en
    tag_map = {
        "tag_account": tags[0]["name"],
        "tag_profiles": tags[1]["name"],
        "tag_crm": tags[2]["name"],
        "tag_rag": tags[3]["name"],
        "tag_mcp": tags[4]["name"],
        "tag_telephony": tags[5]["name"],
        "tag_employees": tags[6]["name"],
        "tag_queues": tags[7]["name"],
        "tag_campaigns": tags[8]["name"],
        "tag_cdr": tags[9]["name"],
        "tag_webhooks": tags[10]["name"],
        "tag_context": tags[11]["name"],
    }

    paths = {
        "/context/": {
            "get": {
                "tags": [tag_map["tag_context"]],
                "summary": "استعلام الذاكرة المنظمة الحية للنشاط (Get Live Context)" if is_ar else "Get Structured Live Context",
                "description": "استرجاع الـ JSON المنظم المحفوظ حالياً وحالة الكاش في Redis." if is_ar else "Retrieve currently active structured business context and Redis cache status.",
                "responses": {"200": {"description": "بيانات الذاكرة المنظمة الحية" if is_ar else "Structured context data"}}
            },
            "put": {
                "tags": [tag_map["tag_context"]],
                "summary": "تحديث واستبدال الذاكرة المنظمة بالكامل (Atomic Overwrite Live Context)" if is_ar else "Overwrite Structured Live Context",
                "description": "استبدال كامل وفوري لبيانات النشاط (منيو، فروع، توصيل، نواقص) ومزامنتها في كاش Redis في أقل من 2ms." if is_ar else "Atomically replace structured business data and sync to in-memory Redis.",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "example": {
                                "restaurant_name": "مطعم بيسترو إيطاليانو",
                                "out_of_stock": ["بيتزا باربيكيو دجاج"],
                                "branches": [{"name": "المعادي", "status": "مفتوح", "hours": "11:00 ص - 02:00 ص"}],
                                "delivery_zones": [{"zone": "المعادي", "fee": "20 جنيه", "min_order": "100 جنيه"}]
                            }
                        }
                    }
                },
                "responses": {"200": {"description": "تم تحديث الذاكرة المنظمة ومزامنة Redis بنجاح" if is_ar else "Live context updated and synced successfully"}}
            },
            "delete": {
                "tags": [tag_map["tag_context"]],
                "summary": "مسح الذاكرة المنظمة الحية (Clear Live Context)" if is_ar else "Delete Live Context",
                "description": "مسح البيانات المنظمة من قاعدة البيانات وكاش الـ Redis." if is_ar else "Clear structured live context from database and Redis cache.",
                "responses": {"200": {"description": "تم مسح البيانات بنجاح" if is_ar else "Context deleted successfully"}}
            }
        },
        "/account/": {

            "get": {
                "tags": [tag_map["tag_account"]],
                "summary": "عرض بيانات الحساب والمحفظة (Get Account)" if is_ar else "Get Account & Wallet Info",
                "description": "يعيد بيانات الحساب ورصيد المحفظة المتاح واسم البروفايل الصوتي النشط." if is_ar else "Returns account details, wallet balance, active voice persona, and usage counters.",
                "responses": {
                    "200": {
                        "description": "بيانات الحساب" if is_ar else "Account info",
                        "content": {
                            "application/json": {
                                "example": {
                                    "status": "success",
                                    "user_id": 1,
                                    "username": "admin",
                                    "email": "admin@example.com",
                                    "wallet_balance": 50.0,
                                    "active_profile": {"id": 1, "name": "مساعد المبيعات السعودي", "dialect": "saudi"},
                                    "total_calls": 12,
                                    "total_documents": 3,
                                    "total_employees": 4,
                                    "total_mcp_servers": 1
                                }
                            }
                        }
                    },
                    "401": {"$ref": "#/components/responses/401Error"}
                }
            }
        },
        "/billing/wallet/": {
            "get": {
                "tags": [tag_map["tag_account"]],
                "summary": "عرض رصيد المحفظة وتسعيرة الدقائق (Get Wallet & Rates)" if is_ar else "Get Wallet Balance & Minute Rates",
                "description": (
                    "يعيد رصيد المحفظة المسبقة الدفع الحالي، العملة، إجمالي المشحون والمستهلك، وسعر الدقيقة وطريقة التقريب لأعلى دقيقة كاملة."
                    if is_ar else
                    "Returns current prepaid balance, currency, deposit/spending totals, per-minute billing rates, and ceiling rounding mode."
                ),
                "responses": {
                    "200": {
                        "description": "بيانات المحفظة والتسعير" if is_ar else "Wallet and pricing details",
                        "content": {
                            "application/json": {
                                "example": {
                                    "status": "success",
                                    "wallet": {
                                        "id": 1,
                                        "user_id": 1,
                                        "username": "admin",
                                        "balance": 24.50,
                                        "currency": "USD",
                                        "currency_symbol": "$",
                                        "total_spent": 5.50,
                                        "total_deposited": 30.00,
                                        "updated_at": "2026-09-27 02:40"
                                    },
                                    "rates": {
                                        "cost_per_minute": 0.05,
                                        "currency": "USD",
                                        "currency_symbol": "$",
                                        "rounding_mode": "ceil",
                                        "min_balance_to_call": 0.05
                                    }
                                }
                            }
                        }
                    },
                    "401": {"$ref": "#/components/responses/401Error"}
                }
            }
        },
        "/billing/transactions/": {
            "get": {
                "tags": [tag_map["tag_account"]],
                "summary": "سجل الحركات المالية وشحن الرصيد (Billing Ledger)" if is_ar else "Billing Transactions & Ledger",
                "description": (
                    "استعراض سجل الحركات المالية التفصيلية (خصومات المكالمات، شحن الرصيد، والتعديلات الإدارية) مع التقسيم لصفحات."
                    if is_ar else
                    "Paginated ledger of all financial transactions (call deductions, top-ups, adjustments)."
                ),
                "parameters": [
                    {"name": "type", "in": "query", "schema": {"type": "string", "enum": ["call_deduction", "topup", "admin_adjustment", "welcome_bonus"]}, "description": "تصفية بنوع الحركة" if is_ar else "Filter by transaction type"},
                    {"name": "limit", "in": "query", "schema": {"type": "integer", "default": 50}},
                    {"name": "offset", "in": "query", "schema": {"type": "integer", "default": 0}}
                ],
                "responses": {
                    "200": {
                        "description": "قائمة الحركات المالية" if is_ar else "Transactions list",
                        "content": {
                            "application/json": {
                                "example": {
                                    "status": "success",
                                    "total": 45,
                                    "limit": 50,
                                    "offset": 0,
                                    "transactions": [
                                        {
                                            "id": 102,
                                            "transaction_type": "call_deduction",
                                            "transaction_type_display": "خصم مكالمة صوتية",
                                            "amount": -0.10,
                                            "amount_formatted": "-0.10 $",
                                            "balance_after": 24.50,
                                            "balance_after_formatted": "24.50 $",
                                            "currency": "USD",
                                            "currency_symbol": "$",
                                            "actual_seconds": 75,
                                            "billed_minutes": 2,
                                            "rate_applied": 0.05,
                                            "description": "مكالمة صادرة (2 دقيقة تقريب لأعلى - 75 ثانية)",
                                            "room_name": "room_user_1_ai_out_ab12cd34",
                                            "created_at": "2026-09-27 01:15:30"
                                        }
                                    ]
                                }
                            }
                        }
                    }
                }
            }
        },
        "/profiles/studio/": {
            "get": {
                "tags": [tag_map["tag_profiles"]],
                "summary": "استوديو تخصيص الشخصية والأصوات (Persona Studio Metadata)" if is_ar else "Voice & Persona Studio Metadata",
                "description": "استرجاع قائمة كافة أصوات Google الرسمية الـ 30، اللغات الـ 11، اللهجات الـ 29، ونماذج الأدوار والأساليب الحرة." if is_ar else "Get full studio catalog: 30 Google HD voices, 11 languages, 29 dialects, and inspiration roles/styles.",
                "responses": {"200": {"description": "بيانات استوديو الشخصيات" if is_ar else "Persona studio metadata"}}
            }
        },
        "/profiles/": {
            "get": {
                "tags": [tag_map["tag_profiles"]],
                "summary": "استعراض بروفايلات الصوت والشخصيات (List Profiles)" if is_ar else "List Voice Agent Profiles",
                "parameters": [
                    {"name": "is_active", "in": "query", "required": False, "schema": {"type": "boolean"}, "description": "تصفية البروفايلات النشطة فقط" if is_ar else "Filter active only"}
                ],
                "responses": {"200": {"description": "قائمة البروفايلات" if is_ar else "Profiles list"}}
            },
            "post": {
                "tags": [tag_map["tag_profiles"]],
                "summary": "إنشاء بروفايل صوتي وشخصية جديدة (Create Profile)" if is_ar else "Create Voice Agent Profile",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ProfileCreateRequest"}
                        }
                    }
                },
                "responses": {"201": {"description": "تم الإنشاء بنجاح" if is_ar else "Profile created successfully"}}
            }
        },
        "/profiles/{profile_id}/": {
            "get": {
                "tags": [tag_map["tag_profiles"]],
                "summary": "جلب تفاصيل بروفايل محدد (Get Profile)" if is_ar else "Get Voice Profile Details",
                "parameters": [{"$ref": "#/components/parameters/ProfileId"}],
                "responses": {"200": {"description": "تفاصيل البروفايل" if is_ar else "Profile details"}}
            },
            "patch": {
                "tags": [tag_map["tag_profiles"]],
                "summary": "تعديل بروفايل صوتي (Update Profile)" if is_ar else "Update Voice Profile",
                "parameters": [{"$ref": "#/components/parameters/ProfileId"}],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ProfileUpdateRequest"}
                        }
                    }
                },
                "responses": {"200": {"description": "تم التحديث بنجاح" if is_ar else "Profile updated successfully"}}
            },
            "delete": {
                "tags": [tag_map["tag_profiles"]],
                "summary": "حذف بروفايل صوتي (Delete Profile)" if is_ar else "Delete Voice Profile",
                "parameters": [{"$ref": "#/components/parameters/ProfileId"}],
                "responses": {"200": {"description": "تم الحذف بنجاح" if is_ar else "Profile deleted successfully"}}
            }
        },
        "/profiles/{profile_id}/activate/": {
            "post": {
                "tags": [tag_map["tag_profiles"]],
                "summary": "تفعيل البروفايل الصوتي كافتراضي (Activate Profile)" if is_ar else "Set Profile as Active",
                "parameters": [{"$ref": "#/components/parameters/ProfileId"}],
                "responses": {"200": {"description": "تم التفعيل بنجاح" if is_ar else "Profile activated successfully"}}
            }
        },
        "/memory/": {
            "get": {
                "tags": [tag_map["tag_crm"]],
                "summary": "استعراض وبحث ذاكرة العملاء (List & Search CRM)" if is_ar else "List & Search CRM Memories",
                "parameters": [
                    {"name": "q", "in": "query", "schema": {"type": "string"}, "description": "بحث بالاسم أو الهاتف" if is_ar else "Search query"},
                    {"name": "phone", "in": "query", "schema": {"type": "string"}, "description": "جلب مباشر برقم هاتف محدد" if is_ar else "Direct phone lookup"},
                    {"name": "page", "in": "query", "schema": {"type": "integer", "default": 1}},
                    {"name": "limit", "in": "query", "schema": {"type": "integer", "default": 20}}
                ],
                "responses": {"200": {"description": "سجلات الذاكرة" if is_ar else "Customer memories list"}}
            },
            "post": {
                "tags": [tag_map["tag_crm"]],
                "summary": "إنشاء أو تحديث ذاكرة عميل (Upsert Memory)" if is_ar else "Create or Upsert Customer Memory",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/MemoryUpsertRequest"}
                        }
                    }
                },
                "responses": {"200": {"description": "تم الحفظ بنجاح" if is_ar else "Memory saved successfully"}}
            }
        },
        "/memory/{memory_id}/": {
            "get": {
                "tags": [tag_map["tag_crm"]],
                "summary": "جلب تفاصيل ذاكرة عميل (Get Memory)" if is_ar else "Get Customer Memory Details",
                "parameters": [{"$ref": "#/components/parameters/MemoryId"}],
                "responses": {"200": {"description": "تفاصيل الذاكرة" if is_ar else "Memory details"}}
            },
            "put": {
                "tags": [tag_map["tag_crm"]],
                "summary": "تحديث ذاكرة عميل (Update Memory)" if is_ar else "Update Customer Memory",
                "parameters": [{"$ref": "#/components/parameters/MemoryId"}],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/MemoryUpsertRequest"}
                        }
                    }
                },
                "responses": {"200": {"description": "تم التحديث بنجاح" if is_ar else "Memory updated successfully"}}
            },
            "delete": {
                "tags": [tag_map["tag_crm"]],
                "summary": "حذف ذاكرة عميل (Delete Memory)" if is_ar else "Delete Customer Memory",
                "parameters": [{"$ref": "#/components/parameters/MemoryId"}],
                "responses": {"200": {"description": "تم الحذف بنجاح" if is_ar else "Memory deleted successfully"}}
            }
        },
        "/crm/customers/": {
            "get": {
                "tags": [tag_map["tag_crm"]],
                "summary": "استعراض وبحث قائمة عملاء الـ CRM (List CRM Customers)" if is_ar else "List & Search CRM Customers",
                "description": "استعراض والبحث في قائمة العملاء، أرقام الهواتف، والذاكرة التراكمية الدائمة." if is_ar else "List and search customer profiles, phone numbers, and permanent CRM context.",
                "parameters": [
                    {"name": "search", "in": "query", "schema": {"type": "string"}, "description": "بحث بالاسم، رقم الهاتف، أو الملاحظات" if is_ar else "Search query (name, phone, notes)"},
                    {"name": "limit", "in": "query", "schema": {"type": "integer", "default": 50}},
                    {"name": "offset", "in": "query", "schema": {"type": "integer", "default": 0}}
                ],
                "responses": {"200": {"description": "قائمة العملاء" if is_ar else "Customers list"}}
            },
            "post": {
                "tags": [tag_map["tag_crm"]],
                "summary": "إضافة أو تحديث عميل CRM برقم الهاتف (Create / Upsert Customer)" if is_ar else "Create or Upsert CRM Customer",
                "description": "إنشاء سجل عميل جديد أو تحديث ملفه الدائم وملاحظات التعامل." if is_ar else "Create customer record or update permanent profile and memory notes.",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["phone_number"],
                                "properties": {
                                    "phone_number": {"type": "string", "example": "+966551234567"},
                                    "customer_name": {"type": "string", "example": "فيصل المطيري" if is_ar else "Faisal Al-Mutairi"},
                                    "permanent_profile": {"type": "object", "example": {"city": "الرياض", "vip_level": "VIP", "preferences": "يفضل التواصل صباحاً"}},
                                    "notes": {"type": "string", "example": "عميل متكرر - مهتم بمنتجات التقنية"},
                                    "last_interaction_summary": {"type": "string", "example": "تم الاتفاق على شحن الطلب غداً"}
                                }
                            }
                        }
                    }
                },
                "responses": {"201": {"description": "تم حفظ العميل بنجاح" if is_ar else "Customer saved successfully"}}
            }
        },
        "/crm/customers/{phone}/": {
            "get": {
                "tags": [tag_map["tag_crm"]],
                "summary": "بطاقة العميل وسجل آخر 10 مكالمات (Get Customer & Call History)" if is_ar else "Get Customer Profile & Call History",
                "description": "يعيد بيانات العميل الدائمة مع آخر 10 مكالمات صوتية مسجلة بروابط التسجيل الصوتي." if is_ar else "Returns customer permanent context and recent 10 call sessions with audio recording URLs.",
                "parameters": [
                    {"name": "phone", "in": "path", "required": True, "schema": {"type": "string"}, "description": "رقم هاتف العميل" if is_ar else "Customer phone number"}
                ],
                "responses": {"200": {"description": "بيانات العميل والمكالمات" if is_ar else "Customer profile and calls"}}
            },
            "put": {
                "tags": [tag_map["tag_crm"]],
                "summary": "تحديث بطاقة العميل (Update Customer Profile)" if is_ar else "Update Customer Profile",
                "parameters": [
                    {"name": "phone", "in": "path", "required": True, "schema": {"type": "string"}}
                ],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "customer_name": {"type": "string", "example": "فيصل المطيري"},
                                    "permanent_profile": {"type": "object"},
                                    "notes": {"type": "string"},
                                    "last_interaction_summary": {"type": "string"}
                                }
                            }
                        }
                    }
                },
                "responses": {"200": {"description": "تم التحديث بنجاح" if is_ar else "Customer updated successfully"}}
            },
            "delete": {
                "tags": [tag_map["tag_crm"]],
                "summary": "حذف ذاكرة وبطاقة العميل (Delete Customer Memory)" if is_ar else "Delete Customer Memory",
                "parameters": [
                    {"name": "phone", "in": "path", "required": True, "schema": {"type": "string"}}
                ],
                "responses": {"200": {"description": "تم الحذف بنجاح" if is_ar else "Customer deleted successfully"}}
            }
        },
        "/documents/": {
            "get": {
                "tags": [tag_map["tag_rag"]],
                "summary": "استعراض مستندات قاعدة المعرفة (List Documents)" if is_ar else "List Knowledge Documents",
                "responses": {"200": {"description": "المستندات المفهرسة" if is_ar else "Indexed documents"}}
            },
            "post": {
                "tags": [tag_map["tag_rag"]],
                "summary": "إضافة مستند عبر رابط خارجي أو نص وفهرسته بالمتجهات" if is_ar else "Index Document via file_url or Content",
                "description": "فهرسة مستند دلالياً بالمتجهات عبر تزويد رابط خارجي مباشر (file_url) مثل PDF, DOCX, CSV, TXT, MD أو إرسال نص مباشر (content)." if is_ar else "Index knowledge document semantically via public file_url (PDF, DOCX, CSV, TXT, MD) or raw content text.",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "title": {"type": "string", "example": "سياسة الاسترجاع والشحن" if is_ar else "Return & Shipping Policy"},
                                    "file_url": {"type": "string", "example": "https://example.com/company_policy.pdf", "description": "رابط مباشر لمستند خارجي بصيغة PDF, DOCX, CSV, TXT, MD" if is_ar else "Direct public URL to document"},
                                    "content": {"type": "string", "example": "يمكن استرجاع المنتجات خلال 14 يوماً من الشراء بحالتها الأصلية." if is_ar else "Products can be returned within 14 days of purchase.", "description": "نص مباشر كبديل في حال عدم تزويد رابط" if is_ar else "Raw text content alternative"}
                                }
                            }
                        }
                    }
                },
                "responses": {"201": {"description": "تمت الفهرسة بنجاح" if is_ar else "Document indexed successfully"}}
            }
        },
        "/rag/query/": {
            "post": {
                "tags": [tag_map["tag_rag"]],
                "summary": "استعلام دلالي ذكي بالمتجهات (Semantic RAG Query)" if is_ar else "Semantic RAG Search Query",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["query"],
                                "properties": {
                                    "query": {"type": "string", "example": "كم مدة استرجاع البضاعة؟" if is_ar else "How long is the return window?"},
                                    "top_k": {"type": "integer", "default": 3}
                                }
                            }
                        }
                    }
                },
                "responses": {"200": {"description": "نتائج البحث الدلالي" if is_ar else "Semantic search matches"}}
            }
        },
        "/mcp/": {
            "get": {
                "tags": [tag_map["tag_mcp"]],
                "summary": "استعراض خوادم الـ FastMCP المسجلة (List MCP Servers)" if is_ar else "List FastMCP Servers",
                "description": "يعيد قائمة خوادم FastMCP والأدوات المكتشفة لكل خادم." if is_ar else "Returns list of configured FastMCP servers and cached tools.",
                "responses": {"200": {"description": "خوادم MCP" if is_ar else "MCP servers list"}}
            },
            "post": {
                "tags": [tag_map["tag_mcp"]],
                "summary": "تسجيل خادم FastMCP ومصادقته (Register MCP Server)" if is_ar else "Register FastMCP Server",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["server_url"],
                                "properties": {
                                    "name": {"type": "string", "example": "خادم متجر سلة (FastMCP)" if is_ar else "Main Store FastMCP"},
                                    "server_url": {"type": "string", "example": "http://mock-store:8002/sse"},
                                    "auth_token": {"type": "string", "example": "secret_token_123"},
                                    "is_active": {"type": "boolean", "default": True}
                                }
                            }
                        }
                    }
                },
                "responses": {"201": {"description": "تم تسجيل الخادم بنجاح" if is_ar else "MCP server registered successfully"}}
            }
        },
        "/mcp/{mcp_id}/sync/": {
            "post": {
                "tags": [tag_map["tag_mcp"]],
                "summary": "مزامنة أدوات خادم الـ MCP فورياً (Sync Tools)" if is_ar else "Sync MCP Server Tools",
                "parameters": [{"name": "mcp_id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                "responses": {"200": {"description": "تمت المزامنة بنجاح" if is_ar else "Tools synced successfully"}}
            }
        },
        "/mcp/{mcp_id}/": {
            "get": {
                "tags": [tag_map["tag_mcp"]],
                "summary": "تفاصيل خادم الـ MCP والأدوات (Get MCP Server)" if is_ar else "Get MCP Server Details",
                "parameters": [{"name": "mcp_id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                "responses": {"200": {"description": "تفاصيل خادم MCP" if is_ar else "MCP server details"}}
            },
            "patch": {
                "tags": [tag_map["tag_mcp"]],
                "summary": "تعديل إعدادات خادم MCP (Update MCP Server)" if is_ar else "Update MCP Server",
                "parameters": [{"name": "mcp_id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                "responses": {"200": {"description": "تم التعديل بنجاح" if is_ar else "Updated successfully"}}
            },
            "delete": {
                "tags": [tag_map["tag_mcp"]],
                "summary": "حذف خادم الـ MCP (Delete MCP Server)" if is_ar else "Delete MCP Server",
                "parameters": [{"name": "mcp_id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                "responses": {"200": {"description": "تم الحذف بنجاح" if is_ar else "Deleted successfully"}}
            }
        },
        "/telephony/": {
            "get": {
                "tags": [tag_map["tag_telephony"]],
                "summary": "عرض السنترالات وخطوط SIP (List Trunks)" if is_ar else "List Telephony & PBX Trunks",
                "responses": {"200": {"description": "السنترالات والخطوط" if is_ar else "Trunks list"}}
            },
            "post": {
                "tags": [tag_map["tag_telephony"]],
                "summary": "ربط سنترال أو خط خارجي (Register Trunk)" if is_ar else "Register PBX or SIP Trunk",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["name", "host"],
                                "properties": {
                                    "trunk_type": {"type": "string", "enum": ["pbx", "sip"], "default": "pbx"},
                                    "name": {"type": "string", "example": "Issabel PBX"},
                                    "host": {"type": "string", "example": "192.168.1.100"},
                                    "port": {"type": "integer", "default": 5060},
                                    "username": {"type": "string", "example": "1001"},
                                    "secret": {"type": "string", "example": "secret123"}
                                }
                            }
                        }
                    }
                },
                "responses": {"201": {"description": "تم الربط بنجاح" if is_ar else "Trunk registered successfully"}}
            }
        },
        "/telephony/numbers/": {
            "get": {
                "tags": [tag_map["tag_telephony"]],
                "summary": "استعراض أرقام الـ DID المرتبطة (List DIDs)" if is_ar else "List Assigned DID Numbers",
                "responses": {"200": {"description": "قائمة الأرقام" if is_ar else "DID numbers list"}}
            },
            "post": {
                "tags": [tag_map["tag_telephony"]],
                "summary": "ربط رقم هاتف بالسنترال (Assign DID)" if is_ar else "Assign Phone Number to PBX",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["phone_number"],
                                "properties": {
                                    "phone_number": {"type": "string", "example": "+966112233445"},
                                    "pbx_trunk_id": {"type": "integer", "example": 1},
                                    "description": {"type": "string", "example": "الرقم الموحد" if is_ar else "Main hotline"}
                                }
                            }
                        }
                    }
                },
                "responses": {"201": {"description": "تم التعيين بنجاح" if is_ar else "Number assigned successfully"}}
            }
        },
        "/telephony/pbx-trunks/": {
            "get": {
                "tags": [tag_map["tag_telephony"]],
                "summary": "استعراض سنترالات الـ PBX وإعدادات Issabel الجاهزة (List PBX Trunks)" if is_ar else "List Inbound PBX Trunks",
                "description": "يعيد قائمة جذوع وسنترالات PBX المسجلة مع نصوص الضبط الجاهزة للنسخ في Issabel (PEER Details & USER Details)." if is_ar else "Returns registered PBX trunks with auto-generated Issabel / Asterisk configuration.",
                "responses": {"200": {"description": "قائمة السنترالات" if is_ar else "PBX trunks list"}}
            },
            "post": {
                "tags": [tag_map["tag_telephony"]],
                "summary": "ربط سنترال PBX ثنائي الاتجاه جديد (Create PBX Trunk)" if is_ar else "Create Bidirectional PBX Trunk",
                "description": "إنشاء جذع PBX جديد بربط IP أو بيانات مستخدم ومزامنة قواعد التوجيه في خادم LiveKit SIP." if is_ar else "Create PBX trunk via IP or SIP credentials and sync with LiveKit SIP dispatch.",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["name", "auth_mode"],
                                "properties": {
                                    "name": {"type": "string", "example": "سنترال المقر الرئيسي (Issabel PBX)"},
                                    "auth_mode": {"type": "string", "enum": ["ip", "credentials"], "default": "ip"},
                                    "pbx_ip": {"type": "string", "example": "192.168.1.50", "description": "مطلوب في حال auth_mode=ip"},
                                    "auth_username": {"type": "string", "example": "issabel_trunk_101", "description": "مطلوب في حال auth_mode=credentials"},
                                    "auth_password": {"type": "string", "example": "SuperSecretPass123"},
                                    "inbound_numbers": {"type": "string", "example": "100,200", "description": "أرقام الاستقبال مفصولة بفواصل"},
                                    "destination_type": {"type": "string", "enum": ["ai_assistant", "call_queue"], "default": "ai_assistant"},
                                    "target_queue_id": {"type": "integer", "description": "مطلوب عند اختيار call_queue"},
                                    "target_profile_id": {"type": "integer"},
                                    "enable_outbound": {"type": "boolean", "default": True},
                                    "outbound_port": {"type": "integer", "default": 5060},
                                    "outbound_transport": {"type": "string", "enum": ["UDP", "TCP", "TLS"], "default": "UDP"},
                                    "is_default_outbound": {"type": "boolean", "default": False}
                                }
                            }
                        }
                    }
                },
                "responses": {"201": {"description": "تم الربط وتوليد إعدادات Issabel بنجاح" if is_ar else "PBX Trunk created successfully"}}
            }
        },
        "/telephony/pbx-trunks/{trunk_id}/": {
            "get": {
                "tags": [tag_map["tag_telephony"]],
                "summary": "تفاصيل سنترال PBX محدد ونصوص الربط (Get PBX Trunk Detail)" if is_ar else "Get PBX Trunk Details",
                "parameters": [{"name": "trunk_id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                "responses": {"200": {"description": "تفاصيل السنترال وإعدادات Issabel" if is_ar else "PBX trunk details"}}
            },
            "put": {
                "tags": [tag_map["tag_telephony"]],
                "summary": "تعديل إعدادات سنترال PBX (Update PBX Trunk)" if is_ar else "Update PBX Trunk",
                "parameters": [{"name": "trunk_id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "auth_mode": {"type": "string", "enum": ["ip", "credentials"]},
                                    "pbx_ip": {"type": "string"},
                                    "auth_username": {"type": "string"},
                                    "auth_password": {"type": "string"},
                                    "inbound_numbers": {"type": "string"},
                                    "destination_type": {"type": "string", "enum": ["ai_assistant", "call_queue"]},
                                    "target_queue_id": {"type": "integer"},
                                    "target_profile_id": {"type": "integer"},
                                    "enable_outbound": {"type": "boolean"},
                                    "outbound_port": {"type": "integer"},
                                    "outbound_transport": {"type": "string"},
                                    "is_default_outbound": {"type": "boolean"},
                                    "is_active": {"type": "boolean"}
                                }
                            }
                        }
                    }
                },
                "responses": {"200": {"description": "تم التحديث وإعادة المزامنة بنجاح" if is_ar else "Updated successfully"}}
            },
            "delete": {
                "tags": [tag_map["tag_telephony"]],
                "summary": "حذف سنترال PBX وإلغاء حجز LiveKit SIP (Delete PBX Trunk)" if is_ar else "Delete PBX Trunk",
                "parameters": [{"name": "trunk_id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                "responses": {"200": {"description": "تم الحذف بنجاح" if is_ar else "Deleted successfully"}}
            }
        },
        "/employees/": {
            "get": {
                "tags": [tag_map["tag_employees"]],
                "summary": "عرض دليل الموظفين والتحويلات (List Employees)" if is_ar else "List Employees & Extensions",
                "responses": {"200": {"description": "دليل الموظفين" if is_ar else "Employee directory"}}
            },
            "post": {
                "tags": [tag_map["tag_employees"]],
                "summary": "إضافة موظف جديد (Create Employee)" if is_ar else "Create Employee",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["name", "extension"],
                                "properties": {
                                    "name": {"type": "string", "example": "سارة أحمد" if is_ar else "Sara Ahmed"},
                                    "extension": {"type": "string", "example": "105"},
                                    "department": {"type": "string", "example": "خدمة العملاء" if is_ar else "Customer Support"},
                                    "status": {"type": "string", "enum": ["ready", "busy", "offline"], "default": "ready"}
                                }
                            }
                        }
                    }
                },
                "responses": {"201": {"description": "تم إنشاء الموظف بنجاح" if is_ar else "Employee created successfully"}}
            }
        },
        "/employees/{employee_id}/": {
            "get": {
                "tags": [tag_map["tag_employees"]],
                "summary": "بيانات موظف محدد (Get Employee)" if is_ar else "Get Employee Details",
                "parameters": [{"$ref": "#/components/parameters/EmployeeId"}],
                "responses": {"200": {"description": "بيانات الموظف" if is_ar else "Employee details"}}
            },
            "delete": {
                "tags": [tag_map["tag_employees"]],
                "summary": "حذف موظف (Delete Employee)" if is_ar else "Delete Employee",
                "parameters": [{"$ref": "#/components/parameters/EmployeeId"}],
                "responses": {"200": {"description": "تم الحذف بنجاح" if is_ar else "Deleted successfully"}}
            }
        },
        "/employees/calls/": {
            "get": {
                "tags": [tag_map["tag_employees"]],
                "summary": "سجل مكالمات الموظفين وتطبيقات الهواتف (Employee Call Logs & Recordings)" if is_ar else "Employee Call Logs & Audio Recordings",
                "description": (
                    "استعراض سجل كافة مكالمات الموظفين والوكلاء الداخليين (مكالمات واردة، صادرة، محولة) مع روابط الاستماع للمكالمات المسجلة والفلترة بالتحويلة أو الموظف."
                    if is_ar else
                    "List internal employee call logs, durations, and audio recording URLs with filters by extension, employee, or call type."
                ),
                "parameters": [
                    {"name": "employee_id", "in": "query", "schema": {"type": "integer"}, "description": "تصفية بموظف محدد" if is_ar else "Filter by employee ID"},
                    {"name": "extension", "in": "query", "schema": {"type": "string"}, "description": "تصفية برقم التحويلة (مثال: 101)" if is_ar else "Filter by extension"},
                    {"name": "call_type", "in": "query", "schema": {"type": "string", "enum": ["inbound", "outbound", "missed", "transfer"]}, "description": "نوع المكالمة" if is_ar else "Call direction type"},
                    {"name": "search", "in": "query", "schema": {"type": "string"}, "description": "بحث باسم الموظف أو الطرف الآخر" if is_ar else "Search employee or caller"},
                    {"name": "limit", "in": "query", "schema": {"type": "integer", "default": 50}},
                    {"name": "offset", "in": "query", "schema": {"type": "integer", "default": 0}}
                ],
                "responses": {
                    "200": {
                        "description": "سجلات مكالمات الموظفين" if is_ar else "Employee call logs",
                        "content": {
                            "application/json": {
                                "example": {
                                    "status": "success",
                                    "total": 12,
                                    "limit": 50,
                                    "offset": 0,
                                    "calls": [
                                        {
                                            "id": 14,
                                            "employee_id": 2,
                                            "employee_name": "أحمد علي",
                                            "employee_extension": "101",
                                            "other_party": "102",
                                            "extension": "102",
                                            "room_name": "room_emp_101_102_a1b2",
                                            "call_type": "outbound",
                                            "call_type_display": "مكالمة صادرة",
                                            "started_at": "2026-09-27 02:10:00",
                                            "ended_at": "2026-09-27 02:12:45",
                                            "duration_secs": 165,
                                            "recording_url": "https://app.169.58.32.179.nip.io/media/recordings/emp_14.mp3"
                                        }
                                    ]
                                }
                            }
                        }
                    }
                }
            }
        },
        "/queues/": {
            "get": {
                "tags": [tag_map["tag_queues"]],
                "summary": "عرض طوابير الانتظار (List Queues)" if is_ar else "List Call Queues",
                "responses": {"200": {"description": "قائمة الطوابير" if is_ar else "Queues list"}}
            },
            "post": {
                "tags": [tag_map["tag_queues"]],
                "summary": "إنشاء طابور انتظار (Create Queue)" if is_ar else "Create Call Queue",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["name"],
                                "properties": {
                                    "name": {"type": "string", "example": "طابور الدعم الفني" if is_ar else "Technical Support Queue"},
                                    "code": {"type": "string", "example": "200", "description": "كود الطابور للتحويل"},
                                    "description": {"type": "string", "example": "طابور استفسارات المنتجات والشحن والمبيعات"},
                                    "strategy": {"type": "string", "enum": ["round_robin", "ring_all"], "default": "round_robin"},
                                    "ring_timeout_seconds": {"type": "integer", "default": 15},
                                    "total_timeout_seconds": {"type": "integer", "default": 60},
                                    "fallback_action": {"type": "string", "enum": ["ai_assistant", "hangup"], "default": "ai_assistant"},
                                    "members": {"type": "array", "items": {"type": "integer"}, "description": "قائمة معرفات الموظفين"}
                                }
                            }
                        }
                    }
                },
                "responses": {"201": {"description": "تم إنشاء الطابور بنجاح" if is_ar else "Queue created successfully"}}
            }
        },
        "/queues/{queue_id}/members/": {
            "get": {
                "tags": [tag_map["tag_queues"]],
                "summary": "استعراض أعضاء الطابور (List Queue Members)" if is_ar else "List Queue Members",
                "parameters": [{"name": "queue_id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                "responses": {"200": {"description": "أعضاء الطابور" if is_ar else "Queue members list"}}
            },
            "post": {
                "tags": [tag_map["tag_queues"]],
                "summary": "إضافة موظف إلى الطابور (Add Queue Member)" if is_ar else "Add Employee to Queue",
                "parameters": [{"name": "queue_id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["employee_id"],
                                "properties": {
                                    "employee_id": {"type": "integer", "example": 1},
                                    "order": {"type": "integer", "default": 0}
                                }
                            }
                        }
                    }
                },
                "responses": {"201": {"description": "تمت إضافة الموظف للطابور" if is_ar else "Employee added to queue"}}
            },
            "delete": {
                "tags": [tag_map["tag_queues"]],
                "summary": "إزالة موظف من الطابور (Remove Queue Member)" if is_ar else "Remove Employee from Queue",
                "parameters": [
                    {"name": "queue_id", "in": "path", "required": True, "schema": {"type": "integer"}},
                    {"name": "employee_id", "in": "query", "required": True, "schema": {"type": "integer"}}
                ],
                "responses": {"200": {"description": "تمت الإزالة بنجاح" if is_ar else "Member removed successfully"}}
            }
        },
        "/calls/": {
            "get": {
                "tags": [tag_map["tag_cdr"]],
                "summary": "استعراض سجلات المكالمات والـ CDR (List Call Logs)" if is_ar else "List Call Detail Records (CDR)",
                "description": "يعيد قائمة المكالمات الأخيرة وتكلفتها والدقائق المفوترة وملخص المحادثة الذكي." if is_ar else "Returns recent call history, duration, billed minutes, cost, and AI summaries.",
                "responses": {"200": {"description": "سجلات المكالمات" if is_ar else "Call records list"}}
            }
        },
        "/calls/dial/": {
            "post": {
                "tags": [tag_map["tag_cdr"]],
                "summary": "بدء مكالمة هاتفية صادرة بالذكاء الاصطناعي (Autonomous Outbound Dialing)" if is_ar else "Initiate Autonomous Outbound AI Phone Call",
                "description": (
                    "توجيه روبوت الصوت الذكي للاتصال تلقائياً برقم هاتف خارجي أو تحويلة سنترال PBX داخلية، والتحدث مع العميل فور فتح الخط لتحقيق هدف محدد (مثل تأكيد الطلبات، التذكير بالمواعيد، أو خدمة العملاء)."
                    if is_ar else
                    "Trigger an autonomous outbound AI phone call to an external customer phone number or internal PBX extension. The AI assistant immediately initiates dialogue to achieve the specified goal once answered."
                ),
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["phone_number"],
                                "properties": {
                                    "phone_number": {
                                        "type": "string",
                                        "example": "+201012345678",
                                        "description": "رقم هاتف العميل بالصيغة الدولية أو رقم تحويلة PBX (مثال: 101)" if is_ar else "Destination E.164 phone number or PBX extension (e.g. 101)"
                                    },
                                    "call_goal": {
                                        "type": "string",
                                        "example": "تأكيد تفاصيل الطلب رقم 1042 ومعالجة استفسارات التوصيل" if is_ar else "Confirm details of order #1042 and delivery schedule",
                                        "description": "الهدف أو التعليمات الفورية للمكالمة الصادرة" if is_ar else "Goal or instructions given to the AI voice agent for this outbound call"
                                    },
                                    "profile_id": {
                                        "type": "integer",
                                        "example": 1,
                                        "description": "معرف البروفايل الصوتي (اختياري - يستخدم الافتراضي إن تُرك فارغاً)" if is_ar else "Voice persona profile ID (optional - defaults to active profile)"
                                    },
                                    "gateway_type": {
                                        "type": "string",
                                        "enum": ["auto", "pbx", "cloud"],
                                        "default": "auto",
                                        "description": "مسار الاتصال: auto (تلقائي)، pbx (سنترال محلي)، cloud (جذع سحابي)" if is_ar else "Dialing gateway: auto, pbx, or cloud"
                                    },
                                    "gateway_id": {
                                        "type": "integer",
                                        "example": 2,
                                        "description": "معرف السنترال أو الجذع المحدد عند اختيار pbx" if is_ar else "Specific PBX trunk ID when gateway_type is pbx"
                                    }
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "201": {
                        "description": "تم بدء الاتصال بنجاح" if is_ar else "Outbound call initiated successfully",
                        "content": {
                            "application/json": {
                                "example": {
                                    "status": "success",
                                    "message": "تم بدء الاتصال الصادر بالرقم +201012345678 بنجاح عبر سنترال Issabel (افتراضي)" if is_ar else "AI outbound call initiated successfully",
                                    "call_id": "room_user_1_ai_out_ab12cd34",
                                    "room_name": "room_user_1_ai_out_ab12cd34",
                                    "session_id": 482,
                                    "destination_phone": "+201012345678",
                                    "call_goal": "تأكيد تفاصيل الطلب رقم 1042 ومعالجة استفسارات التوصيل",
                                    "trunk_name": "سنترال Issabel (افتراضي)",
                                    "gateway_used": "سنترال Issabel (افتراضي)",
                                    "caller_id": "+201234567890"
                                }
                            }
                        }
                    },
                    "400": {"description": "بيانات الاتصال غير صالحة أو رقم الهاتف مفقود" if is_ar else "Missing or invalid phone number"},
                    "402": {"description": "رصيد المحفظة غير كافٍ لبدء المكالمة الصادرة" if is_ar else "Insufficient balance for outbound call"},
                    "422": {"description": "لا يوجد مسار اتصال صادر مفعل (سحابي أو سنترال)" if is_ar else "No active outbound route configured"}
                }
            }
        },
        "/calls/hangup/": {
            "post": {
                "tags": [tag_map["tag_cdr"]],
                "summary": "إنهاء مكالمة جارية فورياً (Hangup Active Call)" if is_ar else "Hang Up Active Call Session",
                "description": (
                    "إنهاء مكالمة هاتفية أو صوتية جارية فورياً وفصل المتصل والذكاء الاصطناعي وحذف غرفة LiveKit وتسجيل مدة المكالمة."
                    if is_ar else
                    "Immediately terminates an active voice/phone call session, closes the LiveKit room, notifies presence channels, and finalizes call logs."
                ),
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["call_id"],
                                "properties": {
                                    "call_id": {"type": "string", "example": "user_1_8f9e", "description": "معرف المكالمة أو اسم الغرفة"}
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "200": {"description": "تم إنهاء المكالمة بنجاح" if is_ar else "Call terminated successfully"},
                    "400": {"description": "معرف المكالمة غير محدد" if is_ar else "call_id is required"}
                }
            }
        },
        "/calls/{call_id}/": {
            "get": {
                "tags": [tag_map["tag_cdr"]],
                "summary": "تفاصيل جلسة مكالمة محددة مع النص والملخص والتسجيل (Get Call Session Detail)" if is_ar else "Get Call Session Detail",
                "description": (
                    "استرجاع تفاصيل كاملة لمكالمة محددة عبر معرف المكالمة أو اسم الغرفة، تشمل نص الحوار الكامل (Transcript)، أدوار الحديث، التكلفة المحتسبة، الدقائق، ورابط التسجيل الصوتي."
                    if is_ar else
                    "Get complete single call session details including full dialogue turns, transcript, AI summary, billed cost, and direct audio recording URL."
                ),
                "parameters": [
                    {"name": "call_id", "in": "path", "required": True, "schema": {"type": "string"}, "description": "معرف المكالمة أو اسم الغرفة (room_name)" if is_ar else "Call session ID or room_name"}
                ],
                "responses": {
                    "200": {
                        "description": "تفاصيل المكالمة" if is_ar else "Call details",
                        "content": {
                            "application/json": {
                                "example": {
                                    "status": "success",
                                    "call": {
                                        "call_id": "room_user_1_ai_out_ab12cd34",
                                        "session_id": 482,
                                        "direction": "outbound_ai",
                                        "direction_display": "صادرة (ذكاء اصطناعي)",
                                        "caller_phone": "+201234567890",
                                        "destination_phone": "+201012345678",
                                        "call_goal": "تأكيد الطلب رقم 1005",
                                        "started_at": "2026-09-27 01:15:00",
                                        "ended_at": "2026-09-27 01:16:30",
                                        "duration_seconds": 90,
                                        "billed_minutes": 2,
                                        "cost": 0.10,
                                        "summary": "تم التواصل مع العميل وتأكيد استلام الطلب غداً بمشيئة الله.",
                                        "transcript_text": "المساعد: مرحباً بك... العميل: أهلاً، نعم أؤكد الطلب.",
                                        "recording_url": "https://app.169.58.32.179.nip.io/media/recordings/call_482.mp3",
                                        "dialogue_turns": 4
                                    }
                                }
                            }
                        }
                    },
                    "404": {"$ref": "#/components/responses/404Error"}
                }
            }
        },
        "/webhooks/": {
            "get": {
                "tags": [tag_map["tag_webhooks"]],
                "summary": "عرض إعدادات الويبهوك الحالية (Get Webhook)" if is_ar else "Get Webhook Settings",
                "responses": {"200": {"description": "إعدادات الويبهوك" if is_ar else "Webhook settings"}}
            },
            "post": {
                "tags": [tag_map["tag_webhooks"]],
                "summary": "حفظ أو تحديث رابط الويبهوك (Save Webhook)" if is_ar else "Save Webhook Settings",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["webhook_url"],
                                "properties": {
                                    "webhook_url": {"type": "string", "example": "https://api.mywebsite.com/voice-events/"},
                                    "webhook_secret": {"type": "string", "example": "my_hmac_secret_key"}
                                }
                            }
                        }
                    }
                },
                "responses": {"200": {"description": "تم الحفظ بنجاح" if is_ar else "Webhook saved successfully"}}
            }
        },
        "/business-hours/": {
            "get": {
                "tags": [tag_map["tag_telephony"]],
                "summary": "استعراض جدول مواعيد العمل وساعات الدوام (Get Business Hours)" if is_ar else "Get Business Hours Schedule",
                "description": "استعراض إعدادات ساعات العمل للأسبوع وسلوك المكالمات خارج الدوام (رد آلي أو رسالة صوتية)." if is_ar else "Get weekly business hours schedule and off-hours auto-responder behavior.",
                "responses": {"200": {"description": "جدول مواعيد العمل" if is_ar else "Business hours schedule"}}
            },
            "post": {
                "tags": [tag_map["tag_telephony"]],
                "summary": "تحديث جدول ساعات العمل وسلوك خارج الدوام (Update Business Hours)" if is_ar else "Update Business Hours Schedule",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "is_enabled": {"type": "boolean", "default": True},
                                    "timezone": {"type": "string", "example": "Africa/Cairo"},
                                    "action_type": {"type": "string", "enum": ["ai_message", "audio_file"], "default": "ai_message"},
                                    "ai_message": {"type": "string", "example": "مرحباً بكم، نتأسف لاتصالكم خارج أوقات العمل الرسمية."},
                                    "audio_file_url": {"type": "string", "example": "https://example.com/audio/closed.mp3", "description": "رابط مباشر لملف صوتي خارجي بصيغة MP3 أو WAV"},
                                    "days_config": {
                                        "type": "object",
                                        "example": {
                                            "sunday": {"is_workday": True, "start_time": "09:00", "end_time": "17:00"},
                                            "monday": {"is_workday": True, "start_time": "09:00", "end_time": "17:00"},
                                            "friday": {"is_workday": False, "start_time": "09:00", "end_time": "17:00"}
                                        }
                                    }
                                }
                            }
                        }
                    }
                },
                "responses": {"200": {"description": "تم حفظ مواعيد العمل بنجاح" if is_ar else "Business hours updated successfully"}}
            }
        },
        "/campaigns/": {
            "get": {
                "tags": [tag_map["tag_campaigns"]],
                "summary": "استعراض حملات الاتصال الصادرة (List Campaigns)" if is_ar else "List Outbound Calling Campaigns",
                "description": "يعيد قائمة بجميع حملات الاتصال الآلي الصادرة وحالاتها ومؤشرات الإنجاز وتصنيف العملاء." if is_ar else "Returns a list of all outbound campaigns, their progress, and lead classifications.",
                "responses": {"200": {"description": "قائمة الحملات" if is_ar else "Campaigns list"}}
            },
            "post": {
                "tags": [tag_map["tag_campaigns"]],
                "summary": "إنشاء حملة اتصال آلي جديدة مع جهات الاتصال (Create Campaign)" if is_ar else "Create Outbound Calling Campaign",
                "description": (
                    "إنشاء حملة جديدة مع تزويد رابط خارجي لملف جهات الاتصال (file_url) بصيغة Excel أو CSV، أو تمرير مصفوفة جهات الاتصال (contacts) مباشرة بصيغة JSON."
                    if is_ar else
                    "Creates an automated campaign by passing a public file_url (Excel/CSV) or direct JSON contacts array."
                ),
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["name"],
                                "properties": {
                                    "name": {"type": "string", "example": "حملة تأكيد حجوزات رمضان" if is_ar else "Ramadan Booking Campaign"},
                                    "file_url": {"type": "string", "example": "https://example.com/leads.xlsx", "description": "رابط مباشر لملف Excel/CSV يحتوي على أرقام جهات الاتصال" if is_ar else "Direct URL to Excel/CSV contacts file"},
                                    "contacts": {
                                        "type": "array",
                                        "description": "مصفوفة جهات اتصال كبديل في حال عدم تزويد file_url" if is_ar else "JSON contacts array alternative",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "phone_number": {"type": "string", "example": "+966551234567"},
                                                "name": {"type": "string", "example": "أحمد الشمري"},
                                                "attributes": {"type": "object", "example": {"city": "الرياض", "order_id": 1042}}
                                            }
                                        }
                                    },
                                    "call_prompt": {"type": "string", "example": "تأكيد موعد الحجز وتفاصيل الوصول" if is_ar else "Confirm booking and arrival details"},
                                    "agent_profile_id": {"type": "integer", "example": 1},
                                    "max_retries": {"type": "integer", "default": 1},
                                    "retry_delay_minutes": {"type": "integer", "default": 15},
                                    "gateway_type": {"type": "string", "default": "auto"}
                                }
                            }
                        }
                    }
                },
                "responses": {"201": {"description": "تم إنشاء الحملة بنجاح" if is_ar else "Campaign created successfully"}}
            }
        },
        "/campaigns/{campaign_id}/start/": {
            "post": {
                "tags": [tag_map["tag_campaigns"]],
                "summary": "بدء أو استئناف إطلاق الحملة آلياً (Start Campaign)" if is_ar else "Start or Resume Outbound Campaign",
                "description": "يبدأ جدولة الاتصال التلقائي بالاعتماد على Inngest وحدود التزامن المسموحة لحساب المستخدم." if is_ar else "Launches parallel dial execution via Inngest respecting concurrency limits.",
                "parameters": [
                    {"name": "campaign_id", "in": "path", "required": True, "schema": {"type": "integer"}}
                ],
                "responses": {"200": {"description": "تم بدء تشغيل الحملة بنجاح" if is_ar else "Campaign started successfully"}}
            }
        },
        "/campaigns/{campaign_id}/": {
            "get": {
                "tags": [tag_map["tag_campaigns"]],
                "summary": "تفاصيل حملة محددة وقائمة العملاء (Get Campaign Details & Contacts)" if is_ar else "Get Campaign Details & Contacts",
                "description": "استرجاع بيانات الحملة التفصيلية، مؤشرات تقدم الاتصال، وقائمة العملاء وتصنيفات الاهتمام." if is_ar else "Returns campaign metrics, dial progress, and targeted customer contacts.",
                "parameters": [
                    {"name": "campaign_id", "in": "path", "required": True, "schema": {"type": "integer"}}
                ],
                "responses": {"200": {"description": "تفاصيل الحملة" if is_ar else "Campaign details"}}
            },
            "delete": {
                "tags": [tag_map["tag_campaigns"]],
                "summary": "حذف حملة اتصال (Delete Campaign)" if is_ar else "Delete Outbound Campaign",
                "parameters": [
                    {"name": "campaign_id", "in": "path", "required": True, "schema": {"type": "integer"}}
                ],
                "responses": {"200": {"description": "تم حذف الحملة بنجاح" if is_ar else "Campaign deleted successfully"}}
            }
        },
        "/campaigns/{campaign_id}/pause/": {
            "post": {
                "tags": [tag_map["tag_campaigns"]],
                "summary": "إيقاف الحملة مؤقتاً (Pause Campaign)" if is_ar else "Pause Outbound Campaign",
                "description": "إيقاف الاتصال الآلي للحملة مؤقتاً مع الحفاظ على تقدم المكالمات السابقة." if is_ar else "Temporarily pause campaign dialing queue.",
                "parameters": [
                    {"name": "campaign_id", "in": "path", "required": True, "schema": {"type": "integer"}}
                ],
                "responses": {"200": {"description": "تم إيقاف الحملة مؤقتاً" if is_ar else "Campaign paused successfully"}}
            }
        },
        "/campaigns/{campaign_id}/reset/": {
            "post": {
                "tags": [tag_map["tag_campaigns"]],
                "summary": "إعادة تعيين العملاء لحالة الانتظار (Reset Campaign Contacts)" if is_ar else "Reset Failed Campaign Contacts",
                "description": "إعادة تعيين جهات الاتصال التي لم ترد أو فشل الاتصال بها لحالة الانتظار وإرجاع الحملة لمسودة جاهزة لإعادة الاتصال." if is_ar else "Resets unreached/failed contacts back to pending and sets campaign back to draft.",
                "parameters": [
                    {"name": "campaign_id", "in": "path", "required": True, "schema": {"type": "integer"}}
                ],
                "responses": {"200": {"description": "تمت إعادة التعيين بنجاح" if is_ar else "Contacts reset successfully"}}
            }
        },
        "/campaigns/{campaign_id}/export/": {
            "get": {
                "tags": [tag_map["tag_campaigns"]],
                "summary": "تصدير نتائج الحملة وتصنيفات العملاء (Export Campaign Leads)" if is_ar else "Export Campaign Leads & Classifications",
                "description": "تصدير جهات اتصال ونتائج المكالمات بصيغة JSON أو ملف Excel/CSV جاهز للتحميل." if is_ar else "Export campaign contacts and AI classification results as JSON, CSV (UTF-8 BOM), or Excel XLSX.",
                "parameters": [
                    {"name": "campaign_id", "in": "path", "required": True, "schema": {"type": "integer"}},
                    {"name": "format", "in": "query", "schema": {"type": "string", "enum": ["json", "csv", "xlsx"], "default": "json"}, "description": "صيغة التصدير" if is_ar else "Export format"},
                    {"name": "filter", "in": "query", "schema": {"type": "string", "enum": ["all", "hot", "hot_warm", "answered"], "default": "all"}, "description": "تصفية العملاء" if is_ar else "Lead filter mode"}
                ],
                "responses": {"200": {"description": "بيانات التصدير أو الملف المرفق" if is_ar else "Exported leads or downloaded file"}}
            }
        },
        "/campaigns/{campaign_id}/contacts/{contact_id}/": {
            "get": {
                "tags": [tag_map["tag_campaigns"]],
                "summary": "تفاصيل عميل محدد داخل الحملة (Get Campaign Contact Detail)" if is_ar else "Get Campaign Contact Details",
                "parameters": [
                    {"name": "campaign_id", "in": "path", "required": True, "schema": {"type": "integer"}},
                    {"name": "contact_id", "in": "path", "required": True, "schema": {"type": "integer"}}
                ],
                "responses": {"200": {"description": "بيانات العميل بالحملة" if is_ar else "Contact details"}}
            },
            "patch": {
                "tags": [tag_map["tag_campaigns"]],
                "summary": "تعديل بيانات عميل بالحملة (Update Campaign Contact)" if is_ar else "Update Campaign Contact",
                "parameters": [
                    {"name": "campaign_id", "in": "path", "required": True, "schema": {"type": "integer"}},
                    {"name": "contact_id", "in": "path", "required": True, "schema": {"type": "integer"}}
                ],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "customer_name": {"type": "string", "example": "محمد الغامدي"},
                                    "phone_number": {"type": "string", "example": "+966551234567"},
                                    "attributes": {"type": "object"},
                                    "call_status": {"type": "string", "enum": ["pending", "in_progress", "answered", "busy", "no_answer", "failed"]},
                                    "interest_level": {"type": "string", "enum": ["uncontacted", "hot", "warm", "cold", "callback", "unreached"]},
                                    "call_summary": {"type": "string"}
                                }
                            }
                        }
                    }
                },
                "responses": {"200": {"description": "تم التحديث بنجاح" if is_ar else "Updated successfully"}}
            },
            "delete": {
                "tags": [tag_map["tag_campaigns"]],
                "summary": "حذف عميل من الحملة (Delete Campaign Contact)" if is_ar else "Delete Campaign Contact",
                "parameters": [
                    {"name": "campaign_id", "in": "path", "required": True, "schema": {"type": "integer"}},
                    {"name": "contact_id", "in": "path", "required": True, "schema": {"type": "integer"}}
                ],
                "responses": {"200": {"description": "تم الحذف بنجاح" if is_ar else "Deleted successfully"}}
            }
        },
        "/campaigns/{campaign_id}/contacts/{contact_id}/dial/": {
            "post": {
                "tags": [tag_map["tag_campaigns"]],
                "summary": "إجراء اتصال فوري بعميل محدد بالحملة (Dial Single Contact)" if is_ar else "Trigger Outbound Call to Single Contact",
                "description": "توجيه أمر فوري للاتصال بالعميل المحدد فردياً دون انتظار جدولة بقية الحملة." if is_ar else "Immediately triggers an autonomous AI outbound call to this specific contact.",
                "parameters": [
                    {"name": "campaign_id", "in": "path", "required": True, "schema": {"type": "integer"}},
                    {"name": "contact_id", "in": "path", "required": True, "schema": {"type": "integer"}}
                ],
                "responses": {"200": {"description": "تم بدء الاتصال بنجاح" if is_ar else "Call initiated successfully"}}
            }
        }
    }

    components = {
        "securitySchemes": {
            "UserApiKey": {
                "type": "apiKey",
                "in": "header",
                "name": "X-API-Key",
                "description": (
                    "مفتاح الـ API الشخصي للمستخدم (يبدأ بـ sk_live_usr_...). يجب تمريره في هيدر كل طلب."
                    if is_ar else
                    "Personal User API key (starts with sk_live_usr_...). Required on all requests."
                )
            }
        },
        "parameters": {
            "ProfileId": {
                "name": "profile_id",
                "in": "path",
                "required": True,
                "schema": {"type": "integer"},
                "description": "المعرف الرقمي للبروفايل" if is_ar else "Numerical ID of the profile"
            },
            "MemoryId": {
                "name": "memory_id",
                "in": "path",
                "required": True,
                "schema": {"type": "integer"},
                "description": "المعرف الرقمي لسجل الذاكرة" if is_ar else "Numerical ID of the memory record"
            },
            "EmployeeId": {
                "name": "employee_id",
                "in": "path",
                "required": True,
                "schema": {"type": "integer"},
                "description": "المعرف الرقمي للموظف" if is_ar else "Numerical ID of the employee"
            }
        },
        "responses": {
            "401Error": {
                "description": "غير مصرح (مفتاح الـ API مفقود)" if is_ar else "Unauthorized (Missing API key)",
                "content": {"application/json": {"example": {"status": "error", "message": "Missing user API key"}}}
            },
            "403Error": {
                "description": "ممنوع (مفتاح الـ API غير صالح)" if is_ar else "Forbidden (Invalid API key)",
                "content": {"application/json": {"example": {"status": "error", "message": "Invalid or inactive API key"}}}
            },
            "404Error": {
                "description": "العنصر غير موجود (Not Found)" if is_ar else "Not Found",
                "content": {"application/json": {"example": {"status": "error", "message": "Resource not found"}}}
            }
        },
        "schemas": {
            "ProfileCreateRequest": {
                "type": "object",
                "required": ["name"],
                "properties": {
                    "name": {"type": "string", "example": "مساعد المبيعات السعودي" if is_ar else "Saudi Sales Advisor"},
                    "voice_name": {"type": "string", "default": "Aoede", "example": "Aoede"},
                    "gender": {"type": "string", "enum": ["female", "male"], "default": "female"},
                    "language": {"type": "string", "default": "arabic", "example": "arabic"},
                    "dialect": {"type": "string", "default": "egyptian", "example": "egyptian"},
                    "persona_role": {"type": "string", "description": "الدور والشخصية المحددة بكتابة حرة مفتوحة", "example": "ممثل خدمة عملاء ومبيعات متجر الكتروني"},
                    "speaking_style": {"type": "string", "description": "أسلوب الإلقاء والنبرة المطلوب الالتزام بها بكتابة حرة", "example": "ودود ولطيف ومرح"},
                    "verbosity": {"type": "string", "enum": ["concise", "balanced", "detailed"], "default": "balanced", "description": "مستوى الإيجاز وسرعة الرد: concise (مختصر 1-2 جملة), balanced (متوازن 2-3 جمل), detailed (مفصل)", "example": "concise"},
                    "custom_instructions": {"type": "string", "example": "أنت مستشار مبيعات ودود وذكي." if is_ar else "You are a friendly and smart sales advisor."},
                    "off_topic_response": {
                        "type": "string",
                        "description": (
                            "الرسالة التي يرددها المساعد لما يسأله العميل سؤالاً خارج نطاق عمل المساعد. "
                            "إذا تُرك فارغاً، يعتذر المساعد باختصار ويعيد توجيه العميل تلقائياً."
                            if is_ar else
                            "The message the assistant will say when the customer asks something outside its scope. "
                            "If left empty, the assistant apologizes briefly and redirects automatically."
                        ),
                        "example": (
                            "بعتذر جداً يا فندم، أنا بساعدك بس في طلبات المتجر، تحب تطلب حاجة؟"
                            if is_ar else
                            "Sorry, I can only help with store orders. Would you like to place one?"
                        )
                    },
                    "is_active": {"type": "boolean", "default": True}
                }
            },
            "ProfileUpdateRequest": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "voice_name": {"type": "string"},
                    "gender": {"type": "string", "enum": ["female", "male"]},
                    "language": {"type": "string"},
                    "dialect": {"type": "string"},
                    "persona_role": {"type": "string", "description": "الدور والشخصية بكتابة حرة"},
                    "speaking_style": {"type": "string", "description": "أسلوب الإلقاء والنبرة بكتابة حرة"},
                    "verbosity": {"type": "string", "enum": ["concise", "balanced", "detailed"], "description": "مستوى الإيجاز وسرعة الرد"},
                    "custom_instructions": {"type": "string"},
                    "off_topic_response": {
                        "type": "string",
                        "description": (
                            "رسالة الرد عند الأسئلة خارج النطاق (فارغة = رد افتراضي)"
                            if is_ar else
                            "Off-topic reply message (empty = automatic generic apology)"
                        )
                    },
                    "is_active": {"type": "boolean"}
                }
            },
            "MemoryUpsertRequest": {
                "type": "object",
                "required": ["phone_number"],
                "properties": {
                    "phone_number": {"type": "string", "example": "+966501234567"},
                    "customer_name": {"type": "string", "example": "عبدالله الشمري" if is_ar else "Abdullah Al-Shammari"},
                    "permanent_profile": {
                        "type": "object",
                        "example": {"city": "الرياض" if is_ar else "Riyadh", "vip_tier": "Gold"}
                    },
                    "immediate_notes": {"type": "string", "example": "يفضل الشحن الصباحي" if is_ar else "Prefers morning dispatch"},
                    "total_calls_count": {"type": "integer", "example": 2}
                }
            }
        }
    }

    return {
        "openapi": "3.1.0",
        "info": info,
        "servers": [
            {
                "url": server_url,
                "description": "خادم الواجهة البرمجية المباشر للمطورين" if is_ar else "Direct Developer API Server"
            }
        ],
        "security": [
            {"UserApiKey": []}
        ],
        "tags": tags,
        "paths": paths,
        "components": components
    }
