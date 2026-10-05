"""
OpenAPI 3.1 Specification for Headless B2B Voice SaaS Partner API.
Supports both Arabic ('ar') and English ('en') with complete schemas,
endpoint summaries, realistic examples, and security definitions.
"""

def get_partner_openapi_spec(server_url: str = "/api/partner/v1", lang: str = "ar") -> dict:
    lang = "en" if lang.lower() == "en" else "ar"
    is_ar = (lang == "ar")

    # 1. Info Definition
    info = {
        "title": "منظومة المساعد الصوتي للشركاء (Voice SaaS Partner API)" if is_ar else "Voice AI Partner Platform API (Headless Voice SaaS)",
        "version": "1.0.0",
        "description": (
            "دليل تكامل واجهات الشركاء وخدمات الـ SaaS (Headless Architecture). "
            "يتيح لك هذا الـ API بناء وتضمين خدمة المساعد الصوتي الذكي داخل تطبيقك أو متجرك "
            "أو نظامك السحابي دون أن يرى عميلك واجهتنا مطلقاً (White-Label). "
            "تتم محاسبتك بسعر الجملة المخفض المخصص لك بخصم مباشر من محفظتك المركزية مع التقريب الصارم لأعلى دقيقة."
            if is_ar else
            "Developer Integration Guide for SaaS Partners & Resellers (Headless Architecture). "
            "This API enables you to embed intelligent, dialect-aware conversational voice AI directly into your applications, "
            "e-commerce stores, or SaaS platforms with zero third-party branding (White-Label). "
            "Usage is billed at your negotiated wholesale per-minute rate directly from your central pooled wallet with strict ceiling minute rounding."
        ),
        "contact": {
            "name": "فريق الدعم الفني للمنظومة" if is_ar else "Voice AI Platform Partner Support",
            "url": "https://localhost/api/partner/v1/docs/"
        }
    }

    # 2. Tags Definition
    tags_ar = [
        {"name": "1. نظرة عامة والمصادقة والمحفظة المركزية", "description": "طريقة المصادقة عبر هيدر X-Partner-Key، إدارة المحفظة المركزية الموحدة للشريك، استعراض كشف الحساب والفوترة بسعر الجملة المخفض."},
        {"name": "2. تسجيل وإدارة العملاء", "description": "تسجيل المتاجر والعملاء الفرعيين وضبط سقوف الاستهلاك والدقائق."},
        {"name": "3. الصوت واللهجات والشخصيات ومواعيد العمل", "description": "إدارة بروفايلات الذكاء الاصطناعي، اللهجات (سعودي، مصري، شامي، فصحى)، ومواعيد العمل وخارج الدوام."},
        {"name": "4. ذاكرة وسياق العملاء CRM", "description": "سجلات الذاكرة التراكمية، إدارة بطاقات عملاء الـ CRM، ملاحظات المكالمات، والاستعلام برقم هاتف المتصل."},
        {"name": "5. قواعد المعرفة والاستعلام الدلالي RAG", "description": "رفع المستندات وفهرستها دلالياً بالمتجهات (pgvector) والبحث الذكي عبر Gemini."},
        {"name": "6. السنترالات والخطوط والأرقام", "description": "ربط سنترالات PBX (Issabel)، توليد إعدادات الربط ثنائي الاتجاه، خطوط SIP الصادرة، وربط أرقام الـ DIDs."},
        {"name": "7. دليل الموظفين والتحويلات", "description": "إدارة الموظفين والتحويلات الداخلية للعميل، حالات التوفر، وسجلات مكالمات الموظفين والتسجيلات."},
        {"name": "8. طوابير الانتظار والأعضاء", "description": "طوابير الكول سنتر واستراتيجيات التوزيع (Round Robin) وإدارة الأعضاء."},
        {"name": "9. سجلات المكالمات والفوترة", "description": "استعراض سجلات المكالمات CDR، تفاصيل المكالمة المفردة، التسجيلات الصوتية، الدقائق المفوترة، وملخصات المحادثة."},
        {"name": "10. الويبهوك والتوقيع المشفر", "description": "استقبال إشعارات انتهاء المكالمات والتحقق البرمجي من توقيع HMAC-SHA256."},
        {"name": "11. إدارة خوادم FastMCP للعملاء", "description": "ربط خوادم FastMCP الخارجية لعميل محدد عبر بروتوكول SSE ومزامنة أدوات الذكاء الاصطناعي الحية."},
        {"name": "12. حملات اتصال العملاء (Client Campaigns)", "description": "إنشاء وإدارة حملات الاتصال الآلي، التحكم بجهات الاتصال الفردية، إعادة المحاولات، والتصدير عبر Inngest."},
        {"name": "13. الذاكرة المنظمة الحية للعميل (Client Live Context)", "description": "حقن واستبدال فوري لبيانات المطاعم والمنيو والفروع لعملاء الشريك في كاش Redis فائق السرعة (< 2ms)."}
    ]

    tags_en = [
        {"name": "1. Overview, Authentication & Pooled Wallet", "description": "Authentication via X-Partner-Key header, central pooled partner wallet balance, and wholesale transaction ledger."},
        {"name": "2. Client Management", "description": "Sub-client store provisioning, account status, and spending/minute caps."},
        {"name": "3. Voice Profiles, Personas & Business Hours", "description": "AI voice agent profiles, regional dialects (Saudi, Egyptian, Levantine, Fusha, English), and client business hours."},
        {"name": "4. Customer CRM & Context Memory", "description": "Cumulative caller context, CRM customer memory, phone lookups, recent calls, and notes."},
        {"name": "5. Knowledge Base & Semantic RAG", "description": "Document ingestion, pgvector semantic indexing, and RAG knowledge search."},
        {"name": "6. Telephony, PBX & DIDs", "description": "PBX trunks (Issabel), bidirectional config generation, outbound SIP endpoints, and DID phone number mapping."},
        {"name": "7. Employee Directory & Extensions", "description": "Staff directory, internal SIP extensions, call transfers, agent availability, and employee call recordings."},
        {"name": "8. Call Queues & Routing", "description": "Call center queues, routing strategies (Round Robin), and queue membership."},
        {"name": "9. Call Logs & CDR", "description": "Call detail records (CDR), single call detail, direct audio recordings, billed minute deduction, and AI summaries."},
        {"name": "10. Webhooks & HMAC Signatures", "description": "Real-time call completion webhook notifications and HMAC-SHA256 signature verification."},
        {"name": "11. Client FastMCP Management", "description": "Manage external FastMCP SSE tool servers per sub-client and synchronize live tool schemas."},
        {"name": "12. Client Outbound Campaigns", "description": "Create and execute outbound calling campaigns, manage contacts, single dial triggers, and export leads."},
        {"name": "13. Client Structured Live Context", "description": "Manage sub-client real-time in-memory cache (< 2ms) for dynamic business data (menus, branches, delivery zones, out of stock)."}
    ]

    tags = tags_ar if is_ar else tags_en
    tag_map = {
        "tag_auth": tags[0]["name"],
        "tag_clients": tags[1]["name"],
        "tag_profiles": tags[2]["name"],
        "tag_crm": tags[3]["name"],
        "tag_rag": tags[4]["name"],
        "tag_telephony": tags[5]["name"],
        "tag_employees": tags[6]["name"],
        "tag_queues": tags[7]["name"],
        "tag_cdr": tags[8]["name"],
        "tag_webhooks": tags[9]["name"],
        "tag_mcp": tags[10]["name"],
        "tag_campaigns": tags[11]["name"],
        "tag_context": tags[12]["name"],
    }

    # 3. Path Operations
    paths = {
        "/clients/{client_id}/context/": {
            "get": {
                "tags": [tag_map["tag_context"]],
                "summary": "استعلام الذاكرة المنظمة الحية للعميل (Get Client Live Context)" if is_ar else "Get Client Structured Live Context",
                "description": "استرجاع الـ JSON المنظم المحفوظ حالياً للعميل وحالة كاش الـ Redis." if is_ar else "Retrieve currently active structured business context and Redis cache status for sub-client.",
                "parameters": [{"$ref": "#/components/parameters/ClientId"}],
                "responses": {"200": {"description": "بيانات الذاكرة المنظمة الحية للعميل" if is_ar else "Client structured context data"}}
            },
            "put": {
                "tags": [tag_map["tag_context"]],
                "summary": "تحديث واستبدال الذاكرة المنظمة للعميل بالكامل (Atomic Overwrite Client Context)" if is_ar else "Overwrite Client Structured Live Context",
                "description": "استبدال كامل وفوري لبيانات نشاط العميل (منيو، فروع، توصيل، نواقص) ومزامنتها في كاش Redis في أقل من 2ms." if is_ar else "Atomically replace sub-client structured business data and sync to in-memory Redis.",
                "parameters": [{"$ref": "#/components/parameters/ClientId"}],
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
                "responses": {"200": {"description": "تم تحديث الذاكرة المنظمة للعميل ومزامنة Redis بنجاح" if is_ar else "Client live context updated and synced successfully"}}
            },
            "delete": {
                "tags": [tag_map["tag_context"]],
                "summary": "مسح الذاكرة المنظمة الحية للعميل (Clear Client Live Context)" if is_ar else "Delete Client Live Context",
                "description": "مسح البيانات المنظمة للعميل من قاعدة البيانات وكاش الـ Redis." if is_ar else "Clear client structured live context from database and Redis cache.",
                "parameters": [{"$ref": "#/components/parameters/ClientId"}],
                "responses": {"200": {"description": "تم مسح بيانات العميل بنجاح" if is_ar else "Client context deleted successfully"}}
            }
        },

        "/wallet/": {
            "get": {
                "tags": [tag_map["tag_auth"]],
                "summary": "عرض رصيد المحفظة المركزية للشريك وسعر الجملة (Get Pooled Wallet)" if is_ar else "Get Partner Pooled Wallet & Wholesale Rates",
                "description": (
                    "يعيد تفاصيل المحفظة المجمعة المركزية للشريك (الرصيد المتاح، سعر الدقيقة المخفض بالجملة، إجمالي العملاء، وإجمالي الدقائق المستهلكة لجميع العملاء)."
                    if is_ar else
                    "Returns partner's central pooled wallet balance, wholesale discounted minute rate, total sub-clients, and aggregate usage metrics across all tenants."
                ),
                "responses": {
                    "200": {
                        "description": "بيانات المحفظة بنجاح" if is_ar else "Partner wallet retrieved successfully",
                        "content": {
                            "application/json": {
                                "example": {
                                    "status": "success",
                                    "partner": {
                                        "id": 1,
                                        "company_name": "شركة ساس السحابية",
                                        "partner_code": "PRT-9921",
                                        "status": "active",
                                        "custom_rate_per_minute": 0.03,
                                        "currency": "USD",
                                        "currency_symbol": "$",
                                        "total_clients": 5,
                                        "total_billed_minutes": 1420,
                                        "total_sub_spent": 42.60
                                    },
                                    "wallet": {
                                        "balance": 250.00,
                                        "currency": "USD",
                                        "total_deposited": 500.00,
                                        "total_spent": 250.00
                                    },
                                    "billing_rules": {
                                        "rounding_mode": "ceil",
                                        "min_balance_to_call": 1.0
                                    }
                                }
                            }
                        }
                    },
                    "403": {"$ref": "#/components/responses/403Error"}
                }
            }
        },
        "/transactions/": {
            "get": {
                "tags": [tag_map["tag_auth"]],
                "summary": "سجل حركات الفوترة بسعر الجملة (List Wholesale Transactions)" if is_ar else "List Wholesale Billing Transactions",
                "description": (
                    "استعراض كشف الحساب المالي لخصومات واستهلاك الرصيد بسعر الجملة من المحفظة المركزية للشريك، مع إمكانية التصفية بالعميل الفرعي أو نوع الحركة."
                    if is_ar else
                    "Paginated financial ledger of wholesale deductions from the partner's wallet with filters for sub-client and transaction type."
                ),
                "parameters": [
                    {
                        "name": "type",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "string", "enum": ["deposit", "deduction", "refund", "manual_adjustment"]},
                        "description": "تصفية بنوع الحركة المالية" if is_ar else "Filter by transaction type"
                    },
                    {
                        "name": "client_id",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "integer"},
                        "description": "تصفية بحركات عميل فرعي محدد" if is_ar else "Filter by sub-client ID"
                    },
                    {
                        "name": "limit",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "integer", "default": 50},
                        "description": "عدد السجلات في الصفحة" if is_ar else "Limit per page"
                    },
                    {
                        "name": "offset",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "integer", "default": 0},
                        "description": "إزاحة البداية" if is_ar else "Pagination offset"
                    }
                ],
                "responses": {
                    "200": {
                        "description": "سجل الحركات المالية بنجاح" if is_ar else "Transactions ledger retrieved successfully",
                        "content": {
                            "application/json": {
                                "example": {
                                    "status": "success",
                                    "total": 128,
                                    "limit": 50,
                                    "offset": 0,
                                    "transactions": [
                                        {
                                            "id": 1042,
                                            "transaction_type": "deduction",
                                            "amount": 0.06,
                                            "balance_after": 249.94,
                                            "description": "خصم مكالمة صادرة للعميل #19 (2 دقيقة بسعر $0.03)",
                                            "created_at": "2026-09-27 02:40:00"
                                        }
                                    ]
                                }
                            }
                        }
                    },
                    "403": {"$ref": "#/components/responses/403Error"}
                }
            }
        },
        "/clients/register/": {
            "post": {
                "tags": [tag_map["tag_clients"]],
                "summary": "تسجيل عميل فرعي جديد (Register Sub-Client)" if is_ar else "Register New Sub-Client",
                "description": (
                    "يسجل متجراً أو عميلاً فرعياً تابعاً لشركتك خلفياً ويعيد client_id لتقوم بتخزينه في قاعدة بياناتك."
                    if is_ar else
                    "Provisions a new tenant/client under your partner account and returns a unique client_id."
                ),
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ClientRegisterRequest"},
                            "example": {
                                "external_reference": "sub_store_9942",
                                "name": "متجر النور التجريبي" if is_ar else "Al-Noor Store Demo",
                                "email": "store9942@saas-demo.com",
                                "password": "OptionalCustomPassword123!",
                                "spending_cap": 25.0,
                                "minute_cap": 200
                            }
                        }
                    }
                },
                "responses": {
                    "201": {
                        "description": "تم تسجيل العميل بنجاح" if is_ar else "Sub-client registered successfully",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ClientRegisterResponse"},
                                "example": {
                                    "status": "success",
                                    "client_id": 19,
                                    "name": "متجر النور التجريبي" if is_ar else "Al-Noor Store Demo",
                                    "external_reference": "sub_store_9942",
                                    "partner_code": "PRT-9B1D97E0",
                                    "credentials": {
                                        "username": "store_9942",
                                        "password": "Pass_a1b2c3d4",
                                        "extension": "101"
                                    },
                                    "owner_employee": {
                                        "id": 12,
                                        "extension": "101",
                                        "display_name": "متجر النور التجريبي (المالك)" if is_ar else "Al-Noor Store Demo (Owner)",
                                        "department": "الإدارة العامة" if is_ar else "General Management",
                                        "status": "ready",
                                        "avatar_url": "https://api.dicebear.com/7.x/bottts/png?seed=101"
                                    },
                                    "spending_cap": 25.0,
                                    "minute_cap": 200
                                }
                            }
                        }
                    },
                    "400": {"$ref": "#/components/responses/400Error"},
                    "403": {"$ref": "#/components/responses/403Error"}
                }
            }
        },
        "/clients/": {
            "get": {
                "tags": [tag_map["tag_clients"]],
                "summary": "عرض جميع العملاء الفرعيين (List Clients)" if is_ar else "List All Sub-Clients",
                "description": (
                    "استعراض قائمة كافة عملاء الساس التابعين للشريك وإحصائيات استهلاك وسقوف كل عميل."
                    if is_ar else
                    "Retrieves a list of all sub-clients registered under the partner with usage and cap statistics."
                ),
                "responses": {
                    "200": {
                        "description": "قائمة العملاء بنجاح" if is_ar else "Clients list retrieved successfully",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ClientListResponse"},
                                "example": {
                                    "status": "success",
                                    "total_clients": 1,
                                    "clients": [
                                        {
                                            "client_id": 19,
                                            "name": "متجر النور التجريبي" if is_ar else "Al-Noor Store Demo",
                                            "external_reference": "sub_store_9942",
                                            "spending_cap": 25.0,
                                            "minute_cap": 200,
                                            "total_spent": 0.06,
                                            "total_minutes": 2,
                                            "is_active": True
                                        }
                                    ]
                                }
                            }
                        }
                    },
                    "403": {"$ref": "#/components/responses/403Error"}
                }
            }
        },
        "/clients/cap/": {
            "post": {
                "tags": [tag_map["tag_clients"]],
                "summary": "تحديث سقف استهلاك العميل (Update Usage Cap)" if is_ar else "Update Client Usage Cap",
                "description": (
                    "تعديل سقف الرصيد المالي وسقف الدقائق لعميل فرعي معين لمنع تجاوز الميزانية."
                    if is_ar else
                    "Updates the dollar and minute consumption ceiling for a designated client."
                ),
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["client_id"],
                                "properties": {
                                    "client_id": {"type": "integer", "example": 19},
                                    "spending_cap": {"type": "number", "example": 50.0},
                                    "minute_cap": {"type": "integer", "example": 500}
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "200": {"description": "تم تحديث السقف بنجاح" if is_ar else "Cap updated successfully"},
                    "403": {"$ref": "#/components/responses/403Error"},
                    "404": {"$ref": "#/components/responses/404Error"}
                }
            }
        },
        "/studio/": {
            "get": {
                "tags": [tag_map["tag_profiles"]],
                "summary": "استوديو تخصيص الشخصية والأصوات للشريك (Partner Persona Studio)" if is_ar else "Voice & Persona Studio Metadata",
                "description": "استرجاع قائمة كافة أصوات Google الـ 30 واللغات الـ 11 واللهجات الـ 29 ونماذج الأدوار والأساليب." if is_ar else "Get full studio catalog: 30 Google HD voices, 11 languages, 29 dialects, and sample roles/styles.",
                "responses": {"200": {"description": "بيانات استوديو الشخصيات" if is_ar else "Persona studio metadata"}}
            }
        },
        "/clients/{client_id}/profiles/studio/": {
            "get": {
                "tags": [tag_map["tag_profiles"]],
                "summary": "استوديو تخصيص الشخصية لصالح عميل فرعي (Client Persona Studio)" if is_ar else "Client Voice & Persona Studio Metadata",
                "parameters": [{"$ref": "#/components/parameters/ClientId"}],
                "responses": {"200": {"description": "بيانات استوديو الشخصيات" if is_ar else "Persona studio metadata"}}
            }
        },
        "/clients/{client_id}/profiles/": {
            "get": {
                "tags": [tag_map["tag_profiles"]],
                "summary": "استعراض بروفايلات الصوت والشخصيات (List Profiles)" if is_ar else "List Voice Agent Profiles",
                "description": (
                    "استعراض جميع شخصيات الذكاء الاصطناعي مع إمكانية التصفية عبر ?is_active=true."
                    if is_ar else
                    "Lists all AI voice profiles for the client with optional active filter (?is_active=true)."
                ),
                "parameters": [
                    {"$ref": "#/components/parameters/ClientId"},
                    {
                        "name": "is_active",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "boolean"},
                        "description": "تصفية البروفايلات النشطة فقط (true أو false)" if is_ar else "Filter active profiles only"
                    }
                ],
                "responses": {
                    "200": {
                        "description": "قائمة البروفايلات" if is_ar else "Profiles list",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ProfileListResponse"}
                            }
                        }
                    },
                    "403": {"$ref": "#/components/responses/403Error"},
                    "404": {"$ref": "#/components/responses/404Error"}
                }
            },
            "post": {
                "tags": [tag_map["tag_profiles"]],
                "summary": "إنشاء بروفايل صوتي وشخصية جديدة (Create Profile)" if is_ar else "Create Voice Agent Profile",
                "description": (
                    "إنشاء بروفايل صوتي جديد بلهجة محددة (سعودي، مصري، شامي، فصحى، إنجليزي) وتعليمات مخصصة."
                    if is_ar else
                    "Provisions a customized AI voice persona with regional dialect and system prompt instructions."
                ),
                "parameters": [
                    {"$ref": "#/components/parameters/ClientId"}
                ],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ProfileCreateRequest"},
                            "example": {
                                "name": "مساعد المبيعات السعودي" if is_ar else "Saudi Sales Advisor",
                                "voice_name": "Aoede",
                                "gender": "female",
                                "dialect": "saudi",
                                "persona_role": "sales_advisor",
                                "speaking_style": "friendly",
                                "custom_instructions": "أنت مستشار مبيعات ودود تتحدث باللهجة السعودية البيضاء وتقدم عروض المتجر." if is_ar else "You are a friendly sales advisor speaking Saudi dialect.",
                                "off_topic_response": "بعتذر جداً يا فندم، أنا بساعدك بس في خدمات المتجر، تحب تطلب حاجة؟" if is_ar else "Sorry, I can only help with store services. Would you like to order something?",
                                "is_active": True
                            }
                        }
                    }
                },
                "responses": {
                    "201": {
                        "description": "تم إنشاء البروفايل بنجاح" if is_ar else "Profile created successfully",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ProfileSingleResponse"}
                            }
                        }
                    },
                    "400": {"$ref": "#/components/responses/400Error"},
                    "403": {"$ref": "#/components/responses/403Error"}
                }
            }
        },
        "/clients/{client_id}/profiles/{profile_id}/": {
            "get": {
                "tags": [tag_map["tag_profiles"]],
                "summary": "جلب تفاصيل بروفايل صوتي (Retrieve Profile)" if is_ar else "Retrieve Voice Profile Details",
                "parameters": [
                    {"$ref": "#/components/parameters/ClientId"},
                    {"$ref": "#/components/parameters/ProfileId"}
                ],
                "responses": {
                    "200": {"description": "تفاصيل البروفايل" if is_ar else "Profile details"},
                    "404": {"$ref": "#/components/responses/404Error"}
                }
            },
            "patch": {
                "tags": [tag_map["tag_profiles"]],
                "summary": "تعديل بروفايل صوتي (Update Profile)" if is_ar else "Update Voice Profile",
                "parameters": [
                    {"$ref": "#/components/parameters/ClientId"},
                    {"$ref": "#/components/parameters/ProfileId"}
                ],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ProfileUpdateRequest"},
                            "example": {
                                "name": "مستشار الدعم الفني المصري" if is_ar else "Egyptian Tech Consultant",
                                "dialect": "egyptian",
                                "voice_name": "Fenrir",
                                "speaking_style": "formal",
                                "off_topic_response": "بعتذر، تخصصي محدود في دعم منتجات شركتك، تحب تسأل عن منتج معين؟" if is_ar else "Sorry, my expertise is limited to your company's products. Can I help with a specific product?"
                            }
                        }
                    }
                },
                "responses": {
                    "200": {"description": "تم تحديث البروفايل بنجاح" if is_ar else "Profile updated successfully"},
                    "404": {"$ref": "#/components/responses/404Error"}
                }
            },
            "delete": {
                "tags": [tag_map["tag_profiles"]],
                "summary": "حذف بروفايل صوتي (Delete Profile)" if is_ar else "Delete Voice Profile",
                "parameters": [
                    {"$ref": "#/components/parameters/ClientId"},
                    {"$ref": "#/components/parameters/ProfileId"}
                ],
                "responses": {
                    "200": {"description": "تم حذف البروفايل بنجاح" if is_ar else "Profile deleted successfully"},
                    "404": {"$ref": "#/components/responses/404Error"}
                }
            }
        },
        "/clients/{client_id}/profiles/{profile_id}/activate/": {
            "post": {
                "tags": [tag_map["tag_profiles"]],
                "summary": "تفعيل البروفايل الصوتي كافتراضي للمكالمات (Activate Profile)" if is_ar else "Set Profile as Active",
                "description": (
                    "يجعل هذا البروفايل هو الشخصية الافتراضية النشطة لجميع مكالمات العميل القادمة مع إلغاء تنشيط البقية."
                    if is_ar else
                    "Designates this profile as the sole active voice agent for all incoming and outbound calls."
                ),
                "parameters": [
                    {"$ref": "#/components/parameters/ClientId"},
                    {"$ref": "#/components/parameters/ProfileId"}
                ],
                "responses": {
                    "200": {"description": "تم تفعيل البروفايل بنجاح" if is_ar else "Profile activated successfully"},
                    "404": {"$ref": "#/components/responses/404Error"}
                }
            }
        },
        "/clients/{client_id}/memory/": {
            "get": {
                "tags": [tag_map["tag_crm"]],
                "summary": "استعراض ذاكرة وسياق العملاء مع البحث والترقيم (List/Search CRM Memories)" if is_ar else "List & Search CRM Memories",
                "description": (
                    "استرجاع بطاقات ذاكرة المتصلين مع دعم البحث بالاسم أو رقم الهاتف ?q= وبترقيم الصفحات ?page=1&limit=20."
                    if is_ar else
                    "Searches and paginates through CRM caller memories by name or phone (?q=, ?page=, ?limit=)."
                ),
                "parameters": [
                    {"$ref": "#/components/parameters/ClientId"},
                    {"name": "q", "in": "query", "schema": {"type": "string"}, "description": "بحث بالاسم أو الهاتف" if is_ar else "Search query by name or phone"},
                    {"name": "page", "in": "query", "schema": {"type": "integer", "default": 1}},
                    {"name": "limit", "in": "query", "schema": {"type": "integer", "default": 20}}
                ],
                "responses": {
                    "200": {
                        "description": "قائمة سجلات الذاكرة" if is_ar else "CRM memories list",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/MemoryListResponse"}
                            }
                        }
                    },
                    "404": {"$ref": "#/components/responses/404Error"}
                }
            },
            "post": {
                "tags": [tag_map["tag_crm"]],
                "summary": "إنشاء أو تحديث ذاكرة عميل بالهاتف (Upsert Memory)" if is_ar else "Create or Upsert Customer Memory",
                "description": (
                    "إنشاء بطاقة ذاكرة متصل جديدة أو تحديثها إذا كان رقم الهاتف مسجلاً مسبقاً (Upsert)."
                    if is_ar else
                    "Inserts or updates context data, notes, and profile attributes keyed by the customer phone number."
                ),
                "parameters": [
                    {"$ref": "#/components/parameters/ClientId"}
                ],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/MemoryUpsertRequest"}
                        }
                    }
                },
                "responses": {
                    "200": {"description": "تم حفظ الذاكرة بنجاح" if is_ar else "Memory saved successfully"},
                    "201": {"description": "تم إنشاء الذاكرة بنجاح" if is_ar else "Memory created successfully"},
                    "400": {"$ref": "#/components/responses/400Error"}
                }
            }
        },
        "/clients/{client_id}/memory/{memory_id}/": {
            "get": {
                "tags": [tag_map["tag_crm"]],
                "summary": "جلب تفاصيل ذاكرة عميل محددة (Retrieve Memory)" if is_ar else "Retrieve Single Customer Memory",
                "parameters": [
                    {"$ref": "#/components/parameters/ClientId"},
                    {"$ref": "#/components/parameters/MemoryId"}
                ],
                "responses": {
                    "200": {"description": "تفاصيل الذاكرة" if is_ar else "Memory details"},
                    "404": {"$ref": "#/components/responses/404Error"}
                }
            },
            "put": {
                "tags": [tag_map["tag_crm"]],
                "summary": "تحديث بطاقة ذاكرة المتصل (Update Memory)" if is_ar else "Update Customer Memory",
                "parameters": [
                    {"$ref": "#/components/parameters/ClientId"},
                    {"$ref": "#/components/parameters/MemoryId"}
                ],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/MemoryUpsertRequest"}
                        }
                    }
                },
                "responses": {
                    "200": {"description": "تم التحديث بنجاح" if is_ar else "Memory updated successfully"},
                    "404": {"$ref": "#/components/responses/404Error"}
                }
            },
            "delete": {
                "tags": [tag_map["tag_crm"]],
                "summary": "حذف بطاقة ذاكرة عميل (Delete Memory)" if is_ar else "Delete Customer Memory",
                "parameters": [
                    {"$ref": "#/components/parameters/ClientId"},
                    {"$ref": "#/components/parameters/MemoryId"}
                ],
                "responses": {
                    "200": {"description": "تم حذف سجل الذاكرة بنجاح" if is_ar else "Memory deleted successfully"},
                    "404": {"$ref": "#/components/responses/404Error"}
                }
            }
        },
        "/clients/{client_id}/crm/customers/": {
            "get": {
                "tags": [tag_map["tag_crm"]],
                "summary": "استعراض والبحث في عملاء الـ CRM (List & Search CRM Customers)" if is_ar else "List & Search CRM Customers",
                "description": (
                    "استعراض والبحث في قائمة سجلات ذاكرة العملاء وبياناتهم التراكمية الخاصة بالعميل الفرعي مع دعم الترقيم والبحث بالاسم أو الهاتف."
                    if is_ar else
                    "List and search customer profiles, phone numbers, and permanent CRM context for the designated sub-client."
                ),
                "parameters": [
                    {"$ref": "#/components/parameters/ClientId"},
                    {"name": "search", "in": "query", "schema": {"type": "string"}, "description": "بحث بالاسم، رقم الهاتف، أو الملاحظات" if is_ar else "Search query (name, phone, notes)"},
                    {"name": "limit", "in": "query", "schema": {"type": "integer", "default": 50}},
                    {"name": "offset", "in": "query", "schema": {"type": "integer", "default": 0}}
                ],
                "responses": {
                    "200": {"description": "قائمة العملاء بنجاح" if is_ar else "Customers list"}
                }
            },
            "post": {
                "tags": [tag_map["tag_crm"]],
                "summary": "إضافة أو تحديث عميل CRM برقم الهاتف (Create / Upsert CRM Customer)" if is_ar else "Create or Upsert CRM Customer",
                "description": (
                    "إنشاء سجل عميل جديد أو تحديث ملفه الدائم وملاحظات المساعد الصوتي الخاصة به لعميل فرعي محدد."
                    if is_ar else
                    "Create customer record or update permanent profile and memory notes for this sub-client."
                ),
                "parameters": [{"$ref": "#/components/parameters/ClientId"}],
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
                                    "permanent_profile": {"type": "object", "example": {"city": "الرياض", "vip_level": "VIP"}},
                                    "notes": {"type": "string", "example": "يفضل التواصل صباحاً"},
                                    "last_interaction_summary": {"type": "string", "example": "تم الاتفاق على موعد التسليم"}
                                }
                            }
                        }
                    }
                },
                "responses": {"201": {"description": "تم حفظ العميل بنجاح" if is_ar else "Customer saved successfully"}}
            }
        },
        "/clients/{client_id}/crm/customers/{phone}/": {
            "get": {
                "tags": [tag_map["tag_crm"]],
                "summary": "بطاقة العميل وسجل آخر 10 مكالمات (Get Customer & Call History)" if is_ar else "Get Customer Profile & Call History",
                "description": (
                    "يعيد بيانات العميل الدائمة مع آخر 10 مكالمات صوتية مسجلة بروابط الاستماع والتحميل المباشرة."
                    if is_ar else
                    "Returns customer permanent context and recent 10 call sessions with audio recording URLs for this sub-client."
                ),
                "parameters": [
                    {"$ref": "#/components/parameters/ClientId"},
                    {"name": "phone", "in": "path", "required": True, "schema": {"type": "string"}, "description": "رقم هاتف العميل" if is_ar else "Customer phone number"}
                ],
                "responses": {"200": {"description": "بيانات العميل والمكالمات" if is_ar else "Customer profile and calls"}}
            },
            "put": {
                "tags": [tag_map["tag_crm"]],
                "summary": "تحديث بطاقة العميل (Update Customer Profile)" if is_ar else "Update Customer Profile",
                "parameters": [
                    {"$ref": "#/components/parameters/ClientId"},
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
                    {"$ref": "#/components/parameters/ClientId"},
                    {"name": "phone", "in": "path", "required": True, "schema": {"type": "string"}}
                ],
                "responses": {"200": {"description": "تم الحذف بنجاح" if is_ar else "Customer deleted successfully"}}
            }
        },
        "/clients/{client_id}/documents/": {
            "get": {
                "tags": [tag_map["tag_rag"]],
                "summary": "استعراض مستندات قاعدة المعرفة (List Documents)" if is_ar else "List Knowledge Documents",
                "parameters": [{"$ref": "#/components/parameters/ClientId"}],
                "responses": {"200": {"description": "قائمة المستندات المفهرسة" if is_ar else "Indexed documents list"}}
            },
            "post": {
                "tags": [tag_map["tag_rag"]],
                "summary": "إضافة مستند للعميل عبر رابط خارجي أو نص وفهرسته بالمتجهات" if is_ar else "Index Client Document via file_url or Content",
                "description": "فهرسة مستند دلالياً بالمتجهات عبر تزويد رابط خارجي مباشر (file_url) مثل PDF, DOCX, CSV, TXT, MD أو إرسال نص مباشر (content)." if is_ar else "Index sub-client knowledge document semantically via public file_url (PDF, DOCX, CSV, TXT, MD) or raw content text.",
                "parameters": [{"$ref": "#/components/parameters/ClientId"}],
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
        "/clients/{client_id}/rag/query/": {
            "post": {
                "tags": [tag_map["tag_rag"]],
                "summary": "استعلام دلالي ذكي في قاعدة المعرفة (Semantic RAG Query)" if is_ar else "Semantic RAG Search Query",
                "description": "يبحث دلالياً عن أقرب المقاطع صلة بالسؤال باستخدام تشابه الجيب تماماً (Cosine Similarity) في pgvector." if is_ar else "Performs semantic vector cosine-similarity search against indexed client documents.",
                "parameters": [{"$ref": "#/components/parameters/ClientId"}],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["query"],
                                "properties": {
                                    "query": {"type": "string", "example": "ما هي مهلة إرجاع المنتجات؟" if is_ar else "What is the return policy window?"},
                                    "top_k": {"type": "integer", "default": 3, "example": 3}
                                }
                            }
                        }
                    }
                },
                "responses": {"200": {"description": "نتائج البحث الدلالي مع درجات التشابه" if is_ar else "Semantic search matches with similarity scores"}}
            }
        },
        "/clients/{client_id}/telephony/": {
            "get": {
                "tags": [tag_map["tag_telephony"]],
                "summary": "عرض السنترالات والخطوط المربوطة (List Trunks)" if is_ar else "List Telephony & PBX Trunks",
                "parameters": [{"$ref": "#/components/parameters/ClientId"}],
                "responses": {"200": {"description": "قائمة السنترالات والخطوط" if is_ar else "Trunks and PBX configurations"}}
            },
            "post": {
                "tags": [tag_map["tag_telephony"]],
                "summary": "ربط سنترال PBX أو خط خارجي (Register Trunk)" if is_ar else "Register PBX or SIP Trunk",
                "parameters": [{"$ref": "#/components/parameters/ClientId"}],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["trunk_type", "name", "host"],
                                "properties": {
                                    "trunk_type": {"type": "string", "enum": ["pbx", "sip"], "example": "pbx"},
                                    "name": {"type": "string", "example": "Issabel Main PBX"},
                                    "host": {"type": "string", "example": "192.168.1.100"},
                                    "port": {"type": "integer", "default": 5060},
                                    "username": {"type": "string", "example": "1001"},
                                    "secret": {"type": "string", "example": "TrunkSecret123"},
                                    "is_active": {"type": "boolean", "default": True}
                                }
                            }
                        }
                    }
                },
                "responses": {"201": {"description": "تم الربط بنجاح" if is_ar else "Trunk registered successfully"}}
            }
        },
        "/clients/{client_id}/telephony/numbers/": {
            "get": {
                "tags": [tag_map["tag_telephony"]],
                "summary": "عرض أرقام الـ DID المرتبطة (List DIDs)" if is_ar else "List DID Phone Numbers",
                "parameters": [{"$ref": "#/components/parameters/ClientId"}],
                "responses": {"200": {"description": "قائمة الأرقام" if is_ar else "DID phone numbers list"}}
            },
            "post": {
                "tags": [tag_map["tag_telephony"]],
                "summary": "ربط رقم هاتف بالسنترال (Assign DID)" if is_ar else "Assign Phone Number to PBX",
                "parameters": [{"$ref": "#/components/parameters/ClientId"}],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["phone_number", "pbx_trunk_id"],
                                "properties": {
                                    "phone_number": {"type": "string", "example": "+966112233445"},
                                    "pbx_trunk_id": {"type": "integer", "example": 1},
                                    "description": {"type": "string", "example": "الرقم الموحد الرئيسي للفرع" if is_ar else "Main office incoming hotline"}
                                }
                            }
                        }
                    }
                },
                "responses": {"201": {"description": "تم ربط الرقم بنجاح" if is_ar else "Number assigned successfully"}}
            }
        },
        "/clients/{client_id}/telephony/{trunk_type}/{trunk_id}/": {
            "delete": {
                "tags": [tag_map["tag_telephony"]],
                "summary": "حذف خط أو سنترال مربوط (Delete Trunk)" if is_ar else "Delete Telephony Trunk",
                "parameters": [
                    {"$ref": "#/components/parameters/ClientId"},
                    {"name": "trunk_type", "in": "path", "required": True, "schema": {"type": "string", "enum": ["pbx", "sip"]}},
                    {"name": "trunk_id", "in": "path", "required": True, "schema": {"type": "integer"}}
                ],
                "responses": {"200": {"description": "تم حذف الخط بنجاح" if is_ar else "Trunk deleted successfully"}}
            }
        },
        "/clients/{client_id}/telephony/pbx-trunks/": {
            "get": {
                "tags": [tag_map["tag_telephony"]],
                "summary": "عرض سنترالات PBX وإعدادات Issabel (List PBX Trunks)" if is_ar else "List Inbound PBX Trunks & Issabel Configs",
                "description": (
                    "يعيد قائمة سنترالات PBX المربوطة للعميل مع نصوص الضبط الجاهزة للنسخ في Issabel / FreePBX (PEER Details & USER Details)."
                    if is_ar else
                    "Returns registered PBX trunks with auto-generated Issabel / Asterisk configuration for this sub-client."
                ),
                "parameters": [{"$ref": "#/components/parameters/ClientId"}],
                "responses": {"200": {"description": "قائمة السنترالات بنجاح" if is_ar else "PBX trunks list"}}
            },
            "post": {
                "tags": [tag_map["tag_telephony"]],
                "summary": "ربط سنترال PBX وتوليد إعدادات Issabel (Create PBX Trunk)" if is_ar else "Create Bidirectional PBX Trunk",
                "description": (
                    "إنشاء جذع PBX جديد بربط IP أو بيانات مستخدم ومزامنة قواعد التوجيه في خادم LiveKit SIP لصالح العميل الفرعي."
                    if is_ar else
                    "Create PBX trunk via IP or SIP credentials and sync with LiveKit SIP dispatch for this sub-client."
                ),
                "parameters": [{"$ref": "#/components/parameters/ClientId"}],
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
        "/clients/{client_id}/telephony/pbx-trunks/{trunk_id}/": {
            "get": {
                "tags": [tag_map["tag_telephony"]],
                "summary": "تفاصيل سنترال PBX ونصوص الربط (Get PBX Trunk Detail)" if is_ar else "Get PBX Trunk Details & Issabel Config",
                "parameters": [
                    {"$ref": "#/components/parameters/ClientId"},
                    {"name": "trunk_id", "in": "path", "required": True, "schema": {"type": "integer"}}
                ],
                "responses": {"200": {"description": "تفاصيل السنترال وإعدادات Issabel" if is_ar else "PBX trunk details"}}
            },
            "put": {
                "tags": [tag_map["tag_telephony"]],
                "summary": "تعديل إعدادات سنترال PBX (Update PBX Trunk)" if is_ar else "Update PBX Trunk",
                "parameters": [
                    {"$ref": "#/components/parameters/ClientId"},
                    {"name": "trunk_id", "in": "path", "required": True, "schema": {"type": "integer"}}
                ],
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
                "parameters": [
                    {"$ref": "#/components/parameters/ClientId"},
                    {"name": "trunk_id", "in": "path", "required": True, "schema": {"type": "integer"}}
                ],
                "responses": {"200": {"description": "تم الحذف بنجاح" if is_ar else "Deleted successfully"}}
            }
        },
        "/clients/{client_id}/employees/": {
            "get": {
                "tags": [tag_map["tag_employees"]],
                "summary": "عرض دليل موظفي العميل (List Employees)" if is_ar else "List Client Employees",
                "parameters": [{"$ref": "#/components/parameters/ClientId"}],
                "responses": {"200": {"description": "قائمة الموظفين والتحويلات" if is_ar else "Employee directory and extensions"}}
            },
            "post": {
                "tags": [tag_map["tag_employees"]],
                "summary": "إضافة موظف جديد للعميل (Create Employee)" if is_ar else "Create Employee",
                "parameters": [{"$ref": "#/components/parameters/ClientId"}],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["name", "extension"],
                                "properties": {
                                    "name": {"type": "string", "example": "محمد السعيد" if is_ar else "Mohammed Saeed"},
                                    "extension": {"type": "string", "example": "104"},
                                    "department": {"type": "string", "example": "المبيعات" if is_ar else "Sales"},
                                    "email": {"type": "string", "example": "m.saeed@sub-client.com"},
                                    "status": {"type": "string", "enum": ["ready", "busy", "offline"], "default": "ready"}
                                }
                            }
                        }
                    }
                },
                "responses": {"201": {"description": "تم إنشاء الموظف بنجاح" if is_ar else "Employee created successfully"}}
            }
        },
        "/clients/{client_id}/employees/{employee_id}/": {
            "get": {
                "tags": [tag_map["tag_employees"]],
                "summary": "جلب بيانات موظف (Retrieve Employee)" if is_ar else "Retrieve Employee Details",
                "parameters": [
                    {"$ref": "#/components/parameters/ClientId"},
                    {"$ref": "#/components/parameters/EmployeeId"}
                ],
                "responses": {"200": {"description": "بيانات الموظف" if is_ar else "Employee details"}}
            },
            "patch": {
                "tags": [tag_map["tag_employees"]],
                "summary": "تعديل بيانات موظف أو حالته (Update Employee)" if is_ar else "Update Employee Details/Status",
                "parameters": [
                    {"$ref": "#/components/parameters/ClientId"},
                    {"$ref": "#/components/parameters/EmployeeId"}
                ],
                "responses": {"200": {"description": "تم التحديث بنجاح" if is_ar else "Employee updated successfully"}}
            },
            "delete": {
                "tags": [tag_map["tag_employees"]],
                "summary": "حذف موظف (Delete Employee)" if is_ar else "Delete Employee",
                "parameters": [
                    {"$ref": "#/components/parameters/ClientId"},
                    {"$ref": "#/components/parameters/EmployeeId"}
                ],
                "responses": {"200": {"description": "تم حذف الموظف بنجاح" if is_ar else "Employee deleted successfully"}}
            }
        },
        "/clients/{client_id}/employees/calls/": {
            "get": {
                "tags": [tag_map["tag_employees"]],
                "summary": "سجلات مكالمات الموظفين والتسجيلات (Employee Call Logs & Recordings)" if is_ar else "Employee Call Logs & Audio Recordings",
                "description": (
                    "استعراض سجل مكالمات موظفي العميل الفرعي مع روابط الاستماع للمكالمات المسجلة والفلترة بالتحويلة أو الموظف."
                    if is_ar else
                    "List internal employee call logs, durations, and audio recording URLs for this sub-client with filters by extension, employee, or call type."
                ),
                "parameters": [
                    {"$ref": "#/components/parameters/ClientId"},
                    {"name": "employee_id", "in": "query", "schema": {"type": "integer"}, "description": "تصفية بموظف محدد" if is_ar else "Filter by employee ID"},
                    {"name": "extension", "in": "query", "schema": {"type": "string"}, "description": "تصفية برقم التحويلة (مثال: 101)" if is_ar else "Filter by extension"},
                    {"name": "call_type", "in": "query", "schema": {"type": "string", "enum": ["internal", "queue_incoming", "outbound", "direct_incoming"]}, "description": "نوع المكالمة" if is_ar else "Call direction type"},
                    {"name": "search", "in": "query", "schema": {"type": "string"}, "description": "بحث باسم الموظف أو الطرف الآخر" if is_ar else "Search employee or caller"},
                    {"name": "limit", "in": "query", "schema": {"type": "integer", "default": 50}},
                    {"name": "offset", "in": "query", "schema": {"type": "integer", "default": 0}}
                ],
                "responses": {
                    "200": {"description": "سجلات مكالمات الموظفين" if is_ar else "Employee call logs"}
                }
            }
        },
        "/clients/{client_id}/queues/": {
            "get": {
                "tags": [tag_map["tag_queues"]],
                "summary": "عرض طوابير الانتظار للعميل (List Queues)" if is_ar else "List Call Center Queues",
                "parameters": [{"$ref": "#/components/parameters/ClientId"}],
                "responses": {"200": {"description": "قائمة الطوابير وأعضائها" if is_ar else "Queues list and active members"}}
            },
            "post": {
                "tags": [tag_map["tag_queues"]],
                "summary": "إنشاء طابور انتظار جديد (Create Queue)" if is_ar else "Create Call Queue",
                "parameters": [{"$ref": "#/components/parameters/ClientId"}],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["name"],
                                "properties": {
                                    "name": {"type": "string", "example": "طابور خدمة العملاء الرئيسي" if is_ar else "Main Support Queue"},
                                    "strategy": {"type": "string", "enum": ["round_robin", "least_recent", "random"], "default": "round_robin"},
                                    "timeout_seconds": {"type": "integer", "default": 30}
                                }
                            }
                        }
                    }
                },
                "responses": {"201": {"description": "تم إنشاء الطابور بنجاح" if is_ar else "Queue created successfully"}}
            }
        },
        "/clients/{client_id}/queues/{queue_id}/": {
            "get": {
                "tags": [tag_map["tag_queues"]],
                "summary": "جلب تفاصيل طابور انتظار (Retrieve Queue)" if is_ar else "Retrieve Queue Details",
                "parameters": [
                    {"$ref": "#/components/parameters/ClientId"},
                    {"$ref": "#/components/parameters/QueueId"}
                ],
                "responses": {"200": {"description": "تفاصيل الطابور" if is_ar else "Queue details"}}
            },
            "delete": {
                "tags": [tag_map["tag_queues"]],
                "summary": "حذف طابور انتظار (Delete Queue)" if is_ar else "Delete Queue",
                "parameters": [
                    {"$ref": "#/components/parameters/ClientId"},
                    {"$ref": "#/components/parameters/QueueId"}
                ],
                "responses": {"200": {"description": "تم حذف الطابور بنجاح" if is_ar else "Queue deleted successfully"}}
            }
        },
        "/clients/{client_id}/queues/{queue_id}/members/": {
            "get": {
                "tags": [tag_map["tag_queues"]],
                "summary": "عرض أعضاء طابور الانتظار (List Members)" if is_ar else "List Queue Members",
                "parameters": [
                    {"$ref": "#/components/parameters/ClientId"},
                    {"$ref": "#/components/parameters/QueueId"}
                ],
                "responses": {"200": {"description": "قائمة الموظفين في الطابور" if is_ar else "Assigned employee members"}}
            },
            "post": {
                "tags": [tag_map["tag_queues"]],
                "summary": "إضافة موظف إلى طابور الانتظار (Add Member)" if is_ar else "Add Member to Queue",
                "parameters": [
                    {"$ref": "#/components/parameters/ClientId"},
                    {"$ref": "#/components/parameters/QueueId"}
                ],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["employee_id"],
                                "properties": {
                                    "employee_id": {"type": "integer", "example": 1},
                                    "penalty": {"type": "integer", "default": 0}
                                }
                            }
                        }
                    }
                },
                "responses": {"201": {"description": "تمت إضافة الموظف للطابور" if is_ar else "Member added to queue"}}
            }
        },
        "/clients/{client_id}/calls/": {
            "get": {
                "tags": [tag_map["tag_cdr"]],
                "summary": "استعراض سجلات مكالمات العميل CDR (List Call Logs)" if is_ar else "List Client Call Logs (CDR)",
                "description": (
                    "يعيد قائمة مكالمات العميل الفرعي مع مدة كل مكالمة، الدقائق المفوترة، تكلفة المكالمة، والملخص الذكي."
                    if is_ar else
                    "Returns call records including duration, billed wholesale minutes, cost, and AI summaries."
                ),
                "parameters": [
                    {"$ref": "#/components/parameters/ClientId"}
                ],
                "responses": {
                    "200": {
                        "description": "قائمة السجلات بنجاح" if is_ar else "CDR records list",
                        "content": {
                            "application/json": {
                                "example": {
                                    "status": "success",
                                    "client_id": 19,
                                    "calls_count": 1,
                                    "calls": [
                                        {
                                            "call_id": "partner_1_19_a8b7c6",
                                            "direction": "inbound",
                                            "caller_phone": "+966551122334",
                                            "started_at": "2026-09-23 11:45:00",
                                            "duration_seconds": 65,
                                            "billed_minutes": 2,
                                            "cost": 0.06,
                                            "summary": "استفسر العميل عن المنتجات المتوفرة وتم الرد عليه بالكامل." if is_ar else "Customer inquired about available stock."
                                        }
                                    ]
                                }
                            }
                        }
                    }
                }
            }
        },
        "/clients/{client_id}/calls/dial/": {
            "post": {
                "tags": [tag_map["tag_cdr"]],
                "summary": "إجراء مكالمة صادرة بالذكاء الاصطناعي لعميل فرعي (Autonomous Outbound Dialing for Sub-Client)" if is_ar else "Initiate Autonomous Outbound AI Phone Call for Sub-Client",
                "description": (
                    "توجيه روبوت الصوت الذكي لإجراء اتصال هاتفي صادر لصالح هذا العميل الفرعي مع مراقبة سقف الاستهلاك (Spending/Minute Cap) وخصم الدقائق بسعر الجملة من محفظة الشريك المركزية. يدعم السنترالات السحابية والمحلية والتحويلات الداخلية."
                    if is_ar else
                    "Trigger an autonomous outbound phone call on behalf of a sub-client with strict spending/minute cap enforcement and wholesale rate deduction from the partner's central wallet. Supports external E.164 numbers and PBX extensions."
                ),
                "parameters": [
                    {"$ref": "#/components/parameters/ClientId"}
                ],
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
                                        "example": "+966551122334",
                                        "description": "رقم هاتف العميل بالصيغة الدولية أو تحويلة PBX (مثال: 101)" if is_ar else "Destination E.164 phone number or PBX extension (e.g. 101)"
                                    },
                                    "call_goal": {
                                        "type": "string",
                                        "example": "الاتصال بالعميل لتأكيد تفاصيل الشحنة واستلام الطلب #5502" if is_ar else "Call customer to verify shipment details for order #5502",
                                        "description": "الهدف أو التعليمات الفورية الموجهة للمساعد الصوتي للمكالمة الصادرة" if is_ar else "Goal or directive given to the AI voice agent for this outbound call"
                                    },
                                    "profile_id": {
                                        "type": "integer",
                                        "example": 3,
                                        "description": "معرف البروفايل الصوتي للعميل (اختياري - يستخدم الافتراضي)" if is_ar else "Client voice profile ID (optional - defaults to active profile)"
                                    },
                                    "gateway_type": {
                                        "type": "string",
                                        "enum": ["auto", "pbx", "cloud"],
                                        "default": "auto",
                                        "description": "مسار الاتصال: auto (تلقائي)، pbx (سنترال محلي)، cloud (جذع سحابي)" if is_ar else "Dialing gateway: auto, pbx, or cloud"
                                    },
                                    "gateway_id": {
                                        "type": "integer",
                                        "example": 1,
                                        "description": "معرف السنترال المحدد عند اختيار pbx" if is_ar else "Specific PBX trunk ID when gateway_type is pbx"
                                    }
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "201": {
                        "description": "تم بدء المكالمة الصادرة بنجاح" if is_ar else "Outbound call initiated successfully",
                        "content": {
                            "application/json": {
                                "example": {
                                    "status": "success",
                                    "message": "تم بدء الاتصال الصادر بالرقم +966551122334 بنجاح عبر سنترال الشريك (افتراضي)" if is_ar else "Sub-client AI outbound call initiated successfully",
                                    "client_id": 19,
                                    "call_id": "partner_1_19_ai_out_fa7b2c",
                                    "room_name": "partner_1_19_ai_out_fa7b2c",
                                    "session_id": 490,
                                    "destination_phone": "+966551122334",
                                    "call_goal": "الاتصال بالعميل لتأكيد تفاصيل الشحنة واستلام الطلب #5502",
                                    "trunk_name": "جذع الشريك Telnyx Primary",
                                    "gateway_used": "جذع الشريك Telnyx Primary",
                                    "caller_id": "+966112233445"
                                }
                            }
                        }
                    },
                    "400": {"description": "بيانات الاتصال غير صالحة أو رقم الهاتف مفقود" if is_ar else "Missing or invalid phone number"},
                    "402": {"description": "رصيد محفظة الشريك غير كافٍ" if is_ar else "Partner balance insufficient"},
                    "403": {"description": "تم تجاوز سقف الاستهلاك المحدد للعميل الفرعي" if is_ar else "Client spending or minute cap exceeded"},
                    "422": {"description": "لا يوجد مسار اتصال صادر مفعل" if is_ar else "No active outbound route configured"}
                }
            }
        },
        "/clients/{client_id}/calls/hangup/": {
            "post": {
                "tags": [tag_map["tag_cdr"]],
                "summary": "إنهاء مكالمة جارية لعميل فرعي (Hangup Client Call)" if is_ar else "Hang Up Client Call Session",
                "parameters": [{"$ref": "#/components/parameters/ClientId"}],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["call_id"],
                                "properties": {
                                    "call_id": {"type": "string", "example": "partner_1_19_ai_out_fa7b2c", "description": "معرف المكالمة أو اسم الغرفة"}
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "200": {"description": "تم إنهاء المكالمة بنجاح" if is_ar else "Call terminated successfully"}
                }
            }
        },
        "/clients/{client_id}/calls/{call_id}/": {
            "get": {
                "tags": [tag_map["tag_cdr"]],
                "summary": "تفاصيل مكالمة مفردة مع النص والتسجيل (Get Call Session Detail)" if is_ar else "Get Call Session Detail",
                "description": (
                    "استرجاع تفاصيل كاملة لمكالمة محددة للعميل الفرعي، تشمل نص الحوار الكامل (Transcript)، أدوار الحديث، التكلفة المحتسبة بسعر الجملة، الدقائق، ورابط التسجيل الصوتي."
                    if is_ar else
                    "Get complete single call session details for a sub-client including full dialogue turns, transcript, AI summary, wholesale billed cost, and direct audio recording URL."
                ),
                "parameters": [
                    {"$ref": "#/components/parameters/ClientId"},
                    {"name": "call_id", "in": "path", "required": True, "schema": {"type": "string"}, "description": "معرف المكالمة أو اسم الغرفة (room_name)" if is_ar else "Call session ID or room_name"}
                ],
                "responses": {
                    "200": {
                        "description": "تفاصيل المكالمة" if is_ar else "Call details",
                        "content": {
                            "application/json": {
                                "example": {
                                    "status": "success",
                                    "client_id": 19,
                                    "call": {
                                        "call_id": "partner_1_19_ai_out_fa7b2c",
                                        "session_id": 490,
                                        "direction": "outbound_ai",
                                        "direction_display": "صادرة (ذكاء اصطناعي)",
                                        "caller_phone": "+966112233445",
                                        "destination_phone": "+966551122334",
                                        "call_goal": "تأكيد تفاصيل الشحنة",
                                        "started_at": "2026-09-27 01:15:00",
                                        "ended_at": "2026-09-27 01:16:30",
                                        "duration_seconds": 90,
                                        "billed_minutes": 2,
                                        "cost": 0.06,
                                        "summary": "تم التواصل مع العميل وتأكيد استلام الطلب غداً بمشيئة الله.",
                                        "transcript_text": "المساعد: مرحباً بك... العميل: أهلاً، نعم أؤكد الطلب.",
                                        "recording_url": "https://app.169.58.32.179.nip.io/media/recordings/call_490.mp3",
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
        "/settings/test-webhook/": {
            "post": {
                "tags": [tag_map["tag_webhooks"]],
                "summary": "اختبار إرسال حدث ويبهوك تجريبي (Test Webhook & HMAC)" if is_ar else "Test Webhook & HMAC Dispatch",
                "description": (
                    "يرسل حدث call.completed تجريبي مشفر بتوقيع HMAC-SHA256 إلى رابط الويبهوك المسجل في إعدادات الشريك."
                    if is_ar else
                    "Triggers a mock call.completed event with HMAC-SHA256 signature to the registered partner webhook."
                ),
                "responses": {
                    "200": {
                        "description": "نتيجة إرسال الويبهوك" if is_ar else "Webhook delivery response",
                        "content": {
                            "application/json": {
                                "example": {
                                    "status": "success",
                                    "message": "Webhook test sent successfully (HTTP 200 OK)"
                                }
                            }
                        }
                    }
                }
            }
        },
        "/clients/{client_id}/mcp/": {
            "get": {
                "tags": [tag_map["tag_mcp"]],
                "summary": "استعراض خوادم FastMCP للعميل الفرعي (List Client MCP Servers)" if is_ar else "List Client FastMCP Servers",
                "description": (
                    "يعيد قائمة خوادم FastMCP المخصصة لهذا العميل مع الأدوات المتزامنة، بالإضافة إلى خادم الشريك المشترك إن وُجد."
                    if is_ar else
                    "Returns all FastMCP servers attached to this sub-client plus the partner shared fallback server."
                ),
                "parameters": [{"$ref": "#/components/parameters/ClientId"}],
                "responses": {
                    "200": {
                        "description": "قائمة خوادم MCP للعميل" if is_ar else "Client MCP servers list",
                        "content": {
                            "application/json": {
                                "example": {
                                    "status": "success",
                                    "client_id": 19,
                                    "total_servers": 1,
                                    "partner_shared_server": None,
                                    "servers": [
                                        {
                                            "id": 1,
                                            "name": "خادم المتجر والطلبات (FastMCP)",
                                            "server_url": "http://mock-store:8002/sse",
                                            "is_active": True,
                                            "tools_count": 2,
                                            "cached_tools": [
                                                {"name": "check_order_status", "description": "تحقق من حالة الطلب"},
                                                {"name": "check_product_inventory", "description": "التحقق من المخزون"}
                                            ],
                                            "last_synced_at": "2026-09-23 12:00:00"
                                        }
                                    ]
                                }
                            }
                        }
                    }
                }
            },
            "post": {
                "tags": [tag_map["tag_mcp"]],
                "summary": "إضافة خادم FastMCP جديد للعميل الفرعي (Create Client MCP Server)" if is_ar else "Create Client FastMCP Server",
                "description": (
                    "يربط خادم أدوات FastMCP خارجي (عبر بروتوكول SSE) بهذا العميل ليستخدمه المساعد الصوتي أثناء المكالمات."
                    if is_ar else
                    "Connects an external FastMCP SSE tool server to this client for live AI function calling during calls."
                ),
                "parameters": [{"$ref": "#/components/parameters/ClientId"}],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["server_url"],
                                "properties": {
                                    "name": {"type": "string", "example": "متجر سلة - أدوات المنتجات"},
                                    "server_url": {"type": "string", "example": "http://mock-store:8002/sse"},
                                    "auth_token": {"type": "string", "example": "Bearer salla_sec_xxx"},
                                    "is_active": {"type": "boolean", "default": True},
                                    "sync_now": {"type": "boolean", "default": True}
                                }
                            }
                        }
                    }
                },
                "responses": {"201": {"description": "تم إنشاء خادم MCP ومزامنة الأدوات" if is_ar else "MCP server created and tools synced"}}
            }
        },
        "/clients/{client_id}/mcp/{mcp_id}/": {
            "get": {
                "tags": [tag_map["tag_mcp"]],
                "summary": "جلب تفاصيل خادم FastMCP محدد (Get Client MCP Server)" if is_ar else "Get Client FastMCP Server",
                "parameters": [
                    {"$ref": "#/components/parameters/ClientId"},
                    {"$ref": "#/components/parameters/McpId"}
                ],
                "responses": {"200": {"description": "تفاصيل خادم FastMCP والأدوات" if is_ar else "MCP server details"}}
            },
            "patch": {
                "tags": [tag_map["tag_mcp"]],
                "summary": "تعديل بيانات خادم FastMCP للعميل (Update Client MCP Server)" if is_ar else "Update Client FastMCP Server",
                "parameters": [
                    {"$ref": "#/components/parameters/ClientId"},
                    {"$ref": "#/components/parameters/McpId"}
                ],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "server_url": {"type": "string"},
                                    "auth_token": {"type": "string"},
                                    "is_active": {"type": "boolean"}
                                }
                            }
                        }
                    }
                },
                "responses": {"200": {"description": "تم التحديث بنجاح" if is_ar else "Updated successfully"}}
            },
            "delete": {
                "tags": [tag_map["tag_mcp"]],
                "summary": "حذف خادم FastMCP للعميل (Delete Client MCP Server)" if is_ar else "Delete Client FastMCP Server",
                "parameters": [
                    {"$ref": "#/components/parameters/ClientId"},
                    {"$ref": "#/components/parameters/McpId"}
                ],
                "responses": {"200": {"description": "تم حذف الخادم بنجاح" if is_ar else "Deleted successfully"}}
            }
        },
        "/clients/{client_id}/mcp/{mcp_id}/sync/": {
            "post": {
                "tags": [tag_map["tag_mcp"]],
                "summary": "مزامنة الأدوات الحية فورياً عبر SSE (Sync Client MCP Tools)" if is_ar else "Sync Client FastMCP Tools via SSE",
                "description": (
                    "يتصل مباشرة برابط SSE لخادم FastMCP، ويستكشف الأدوات الحية وقوالب المدخلات، ويحدث قاعدة البيانات."
                    if is_ar else
                    "Performs an immediate SSE handshake to discover tools and schema signatures for this client's agent."
                ),
                "parameters": [
                    {"$ref": "#/components/parameters/ClientId"},
                    {"$ref": "#/components/parameters/McpId"}
                ],
                "responses": {
                    "200": {
                        "description": "تمت المزامنة بنجاح" if is_ar else "Tools synchronized successfully",
                        "content": {
                            "application/json": {
                                "example": {
                                    "status": "success",
                                    "message": "Successfully synchronized 2 tools from FastMCP server via SSE.",
                                    "client_id": 19,
                                    "mcp_id": 1,
                                    "server_name": "خادم المتجر والطلبات (FastMCP)",
                                    "tools_count": 2,
                                    "tools": [
                                        {"name": "check_order_status", "description": "التحقق من حالة الطلب برقم الطلب"},
                                        {"name": "check_product_inventory", "description": "التحقق من كميات المخزون"}
                                    ],
                                    "synced_at": "2026-09-23 12:00:00"
                                }
                            }
                        }
                    }
                }
            }
        },
        "/clients/{client_id}/campaigns/": {
            "get": {
                "tags": [tag_map["tag_campaigns"]],
                "summary": "استعراض حملات الاتصال الصادرة للعميل (List Client Campaigns)" if is_ar else "List Client Outbound Campaigns",
                "description": "يعيد قائمة بجميع حملات الاتصال الآلي الصادرة التابعة لهذا العميل وحالاتها ومؤشرات الإنجاز." if is_ar else "Returns a list of all outbound campaigns for this sub-client.",
                "parameters": [
                    {"$ref": "#/components/parameters/ClientId"}
                ],
                "responses": {"200": {"description": "قائمة الحملات" if is_ar else "Campaigns list"}}
            },
            "post": {
                "tags": [tag_map["tag_campaigns"]],
                "summary": "إنشاء حملة اتصال آلي جديدة للعميل (Create Client Campaign)" if is_ar else "Create Sub-Client Outbound Campaign",
                "description": (
                    "إنشاء حملة جديدة لعميل محدد مع تزويد رابط خارجي لملف جهات الاتصال (file_url) بصيغة Excel أو CSV، أو تمرير مصفوفة جهات الاتصال (contacts) مباشرة بصيغة JSON."
                    if is_ar else
                    "Creates an automated campaign for sub-client by passing a public file_url (Excel/CSV) or direct JSON contacts array."
                ),
                "parameters": [
                    {"$ref": "#/components/parameters/ClientId"}
                ],
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
        "/clients/{client_id}/campaigns/{campaign_id}/start/": {
            "post": {
                "tags": [tag_map["tag_campaigns"]],
                "summary": "بدء تشغيل حملة الاتصال الصادرة (Start Client Campaign)" if is_ar else "Start Client Outbound Campaign",
                "description": "يبدأ جدولة الاتصال التلقائي بالاعتماد على Inngest وحدود التزامن المسموحة لحساب العميل." if is_ar else "Launches parallel dial execution via Inngest respecting concurrency limits.",
                "parameters": [
                    {"$ref": "#/components/parameters/ClientId"},
                    {"name": "campaign_id", "in": "path", "required": True, "schema": {"type": "integer"}, "description": "معرف الحملة" if is_ar else "Campaign ID"}
                ],
                "responses": {"200": {"description": "تم بدء تشغيل الحملة بنجاح" if is_ar else "Campaign started successfully"}}
            }
        },
        "/clients/{client_id}/campaigns/{campaign_id}/": {
            "get": {
                "tags": [tag_map["tag_campaigns"]],
                "summary": "تفاصيل حملة محددة وقائمة العملاء (Get Campaign Details & Contacts)" if is_ar else "Get Campaign Details & Contacts",
                "description": "استرجاع بيانات الحملة التفصيلية، مؤشرات تقدم الاتصال، وقائمة العملاء وتصنيفات الاهتمام لصالح العميل الفرعي." if is_ar else "Returns campaign metrics, dial progress, and targeted customer contacts for sub-client.",
                "parameters": [
                    {"$ref": "#/components/parameters/ClientId"},
                    {"name": "campaign_id", "in": "path", "required": True, "schema": {"type": "integer"}}
                ],
                "responses": {"200": {"description": "تفاصيل الحملة" if is_ar else "Campaign details"}}
            },
            "delete": {
                "tags": [tag_map["tag_campaigns"]],
                "summary": "حذف حملة اتصال (Delete Campaign)" if is_ar else "Delete Outbound Campaign",
                "parameters": [
                    {"$ref": "#/components/parameters/ClientId"},
                    {"name": "campaign_id", "in": "path", "required": True, "schema": {"type": "integer"}}
                ],
                "responses": {"200": {"description": "تم حذف الحملة بنجاح" if is_ar else "Campaign deleted successfully"}}
            }
        },
        "/clients/{client_id}/campaigns/{campaign_id}/pause/": {
            "post": {
                "tags": [tag_map["tag_campaigns"]],
                "summary": "إيقاف الحملة مؤقتاً (Pause Campaign)" if is_ar else "Pause Outbound Campaign",
                "description": "إيقاف الاتصال الآلي للحملة مؤقتاً مع الحفاظ على تقدم المكالمات السابقة." if is_ar else "Temporarily pause campaign dialing queue for this sub-client.",
                "parameters": [
                    {"$ref": "#/components/parameters/ClientId"},
                    {"name": "campaign_id", "in": "path", "required": True, "schema": {"type": "integer"}}
                ],
                "responses": {"200": {"description": "تم إيقاف الحملة مؤقتاً" if is_ar else "Campaign paused successfully"}}
            }
        },
        "/clients/{client_id}/campaigns/{campaign_id}/reset/": {
            "post": {
                "tags": [tag_map["tag_campaigns"]],
                "summary": "إعادة تعيين العملاء لحالة الانتظار (Reset Campaign Contacts)" if is_ar else "Reset Failed Campaign Contacts",
                "description": "إعادة تعيين جهات الاتصال التي لم ترد أو فشل الاتصال بها لحالة الانتظار وإرجاع الحملة لمسودة جاهزة لإعادة الاتصال." if is_ar else "Resets unreached/failed contacts back to pending and sets campaign back to draft.",
                "parameters": [
                    {"$ref": "#/components/parameters/ClientId"},
                    {"name": "campaign_id", "in": "path", "required": True, "schema": {"type": "integer"}}
                ],
                "responses": {"200": {"description": "تمت إعادة التعيين بنجاح" if is_ar else "Contacts reset successfully"}}
            }
        },
        "/clients/{client_id}/campaigns/{campaign_id}/export/": {
            "get": {
                "tags": [tag_map["tag_campaigns"]],
                "summary": "تصدير نتائج الحملة وتصنيفات العملاء (Export Campaign Leads)" if is_ar else "Export Campaign Leads & Classifications",
                "description": "تصدير جهات اتصال ونتائج المكالمات بصيغة JSON أو ملف Excel/CSV جاهز للتحميل." if is_ar else "Export campaign contacts and AI classification results as JSON, CSV (UTF-8 BOM), or Excel XLSX.",
                "parameters": [
                    {"$ref": "#/components/parameters/ClientId"},
                    {"name": "campaign_id", "in": "path", "required": True, "schema": {"type": "integer"}},
                    {"name": "format", "in": "query", "schema": {"type": "string", "enum": ["json", "csv", "xlsx"], "default": "json"}, "description": "صيغة التصدير" if is_ar else "Export format"},
                    {"name": "filter", "in": "query", "schema": {"type": "string", "enum": ["all", "hot", "hot_warm", "answered"], "default": "all"}, "description": "تصفية العملاء" if is_ar else "Lead filter mode"}
                ],
                "responses": {"200": {"description": "بيانات التصدير أو الملف المرفق" if is_ar else "Exported leads or downloaded file"}}
            }
        },
        "/clients/{client_id}/campaigns/{campaign_id}/contacts/{contact_id}/": {
            "get": {
                "tags": [tag_map["tag_campaigns"]],
                "summary": "تفاصيل عميل محدد داخل الحملة (Get Campaign Contact Detail)" if is_ar else "Get Campaign Contact Details",
                "parameters": [
                    {"$ref": "#/components/parameters/ClientId"},
                    {"name": "campaign_id", "in": "path", "required": True, "schema": {"type": "integer"}},
                    {"name": "contact_id", "in": "path", "required": True, "schema": {"type": "integer"}}
                ],
                "responses": {"200": {"description": "بيانات العميل بالحملة" if is_ar else "Contact details"}}
            },
            "patch": {
                "tags": [tag_map["tag_campaigns"]],
                "summary": "تعديل بيانات عميل بالحملة (Update Campaign Contact)" if is_ar else "Update Campaign Contact",
                "parameters": [
                    {"$ref": "#/components/parameters/ClientId"},
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
                    {"$ref": "#/components/parameters/ClientId"},
                    {"name": "campaign_id", "in": "path", "required": True, "schema": {"type": "integer"}},
                    {"name": "contact_id", "in": "path", "required": True, "schema": {"type": "integer"}}
                ],
                "responses": {"200": {"description": "تم الحذف بنجاح" if is_ar else "Deleted successfully"}}
            }
        },
        "/clients/{client_id}/campaigns/{campaign_id}/contacts/{contact_id}/dial/": {
            "post": {
                "tags": [tag_map["tag_campaigns"]],
                "summary": "إجراء اتصال فوري بعميل محدد بالحملة (Dial Single Contact)" if is_ar else "Trigger Outbound Call to Single Contact",
                "description": "توجيه أمر فوري للاتصال بالعميل المحدد فردياً دون انتظار جدولة بقية الحملة لصالح العميل الفرعي." if is_ar else "Immediately triggers an autonomous AI outbound call to this specific contact.",
                "parameters": [
                    {"$ref": "#/components/parameters/ClientId"},
                    {"name": "campaign_id", "in": "path", "required": True, "schema": {"type": "integer"}},
                    {"name": "contact_id", "in": "path", "required": True, "schema": {"type": "integer"}}
                ],
                "responses": {"200": {"description": "تم بدء الاتصال بنجاح" if is_ar else "Call initiated successfully"}}
            }
        },
        "/clients/{client_id}/business-hours/": {
            "get": {
                "tags": [tag_map["tag_profiles"]],
                "summary": "عرض جدول أوقات العمل للعميل الفرعي (Get Client Business Hours)" if is_ar else "Get Client Business Hours Schedule",
                "description": "استعراض إعدادات أوقات العمل وساعات الدوام الأسبوعية وتصرف النظام خارج أوقات العمل." if is_ar else "Retrieves weekly business hours and off-hours auto-response configuration.",
                "parameters": [{"$ref": "#/components/parameters/ClientId"}],
                "responses": {"200": {"description": "جدول أوقات العمل" if is_ar else "Business hours schedule"}}
            },
            "post": {
                "tags": [tag_map["tag_profiles"]],
                "summary": "تحديث أوقات العمل ورسالة خارج الدوام (Update Business Hours)" if is_ar else "Update Client Business Hours & Off-Hours",
                "description": "تعديل جدول أوقات العمل للعميل وسلوك المكالمات خارج الدوام (رد الذكاء الاصطناعي بنص محدد أو تشغيل ملف صوتي عبر رابط file_url)." if is_ar else "Configure sub-client weekly hours, timezone, and off-hours behavior with custom AI text or audio file URL.",
                "parameters": [{"$ref": "#/components/parameters/ClientId"}],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "is_enabled": {"type": "boolean", "default": True},
                                    "timezone": {"type": "string", "example": "Asia/Riyadh"},
                                    "days_config": {
                                        "type": "object",
                                        "example": {
                                            "sunday": {"enabled": True, "open": "09:00", "close": "17:00"},
                                            "monday": {"enabled": True, "open": "09:00", "close": "17:00"},
                                            "tuesday": {"enabled": True, "open": "09:00", "close": "17:00"},
                                            "wednesday": {"enabled": True, "open": "09:00", "close": "17:00"},
                                            "thursday": {"enabled": True, "open": "09:00", "close": "17:00"},
                                            "friday": {"enabled": False, "open": "00:00", "close": "00:00"},
                                            "saturday": {"enabled": False, "open": "00:00", "close": "00:00"}
                                        }
                                    },
                                    "action_type": {"type": "string", "enum": ["ai_message", "audio_file"], "default": "ai_message"},
                                    "ai_message": {"type": "string", "example": "شكراً لاتصالكم، نسعد بخدمتكم خلال أوقات العمل الرسمية."},
                                    "file_url": {"type": "string", "example": "https://example.com/off_hours.mp3"}
                                }
                            }
                        }
                    }
                },
                "responses": {"200": {"description": "تم حفظ الإعدادات بنجاح" if is_ar else "Business hours updated successfully"}}
            }
        }
    }

    # 4. Parameters & Schemas
    components = {
        "securitySchemes": {
            "PartnerKey": {
                "type": "apiKey",
                "in": "header",
                "name": "X-Partner-Key",
                "description": (
                    "مفتاح الشريك السري (يبدأ بـ sk_live_prt_...). يجب تمريره في كل طلب."
                    if is_ar else
                    "Partner secret API key (starts with sk_live_prt_...). Required on all requests."
                )
            }
        },
        "parameters": {
            "ClientId": {
                "name": "client_id",
                "in": "path",
                "required": True,
                "schema": {"type": "integer"},
                "description": "المعرف الرقمي للعميل الفرعي (client_id)" if is_ar else "Numerical ID of the sub-client"
            },
            "McpId": {
                "name": "mcp_id",
                "in": "path",
                "required": True,
                "schema": {"type": "integer"},
                "description": "المعرف الرقمي لخادم FastMCP" if is_ar else "Numerical ID of the FastMCP server"
            },
            "ProfileId": {
                "name": "profile_id",
                "in": "path",
                "required": True,
                "schema": {"type": "integer"},
                "description": "المعرف الرقمي لبروفايل الصوت" if is_ar else "Numerical ID of the voice profile"
            },
            "MemoryId": {
                "name": "memory_id",
                "in": "path",
                "required": True,
                "schema": {"type": "integer"},
                "description": "المعرف الرقمي لسجل ذاكرة العميل" if is_ar else "Numerical ID of the customer memory record"
            },
            "EmployeeId": {
                "name": "employee_id",
                "in": "path",
                "required": True,
                "schema": {"type": "integer"},
                "description": "المعرف الرقمي للموظف" if is_ar else "Numerical ID of the employee"
            },
            "QueueId": {
                "name": "queue_id",
                "in": "path",
                "required": True,
                "schema": {"type": "integer"},
                "description": "المعرف الرقمي لطابور الانتظار" if is_ar else "Numerical ID of the queue"
            },
            "CampaignId": {
                "name": "campaign_id",
                "in": "path",
                "required": True,
                "schema": {"type": "integer"},
                "description": "المعرف الرقمي لحملة الاتصال" if is_ar else "Numerical ID of the outbound campaign"
            },
            "ContactId": {
                "name": "contact_id",
                "in": "path",
                "required": True,
                "schema": {"type": "integer"},
                "description": "المعرف الرقمي لجهة الاتصال" if is_ar else "Numerical ID of the campaign contact"
            },
            "TrunkId": {
                "name": "trunk_id",
                "in": "path",
                "required": True,
                "schema": {"type": "integer"},
                "description": "المعرف الرقمي لسنترال PBX" if is_ar else "Numerical ID of the PBX trunk"
            },
            "CallId": {
                "name": "call_id",
                "in": "path",
                "required": True,
                "schema": {"type": "string"},
                "description": "معرف المكالمة أو اسم الغرفة" if is_ar else "Call ID or room name"
            }
        },
        "responses": {
            "400Error": {
                "description": "طلب غير صالح (Bad Request)" if is_ar else "Bad Request",
                "content": {
                    "application/json": {
                        "example": {"status": "error", "message": "Invalid JSON body"}
                    }
                }
            },
            "403Error": {
                "description": "غير مصرح (مفتاح الشريك غير صالح أو غير مصرح له بهذا العميل)" if is_ar else "Forbidden / Invalid partner API key",
                "content": {
                    "application/json": {
                        "example": {"status": "error", "message": "Invalid partner API key"}
                    }
                }
            },
            "404Error": {
                "description": "العنصر غير موجود (Not Found)" if is_ar else "Resource Not Found",
                "content": {
                    "application/json": {
                        "example": {"status": "error", "message": "Resource not found"}
                    }
                }
            }
        },
        "schemas": {
            "ClientRegisterRequest": {
                "type": "object",
                "required": ["external_reference", "name"],
                "properties": {
                    "external_reference": {"type": "string", "example": "sub_store_9942"},
                    "name": {"type": "string", "example": "متجر النور التجريبي" if is_ar else "Al-Noor Store Demo"},
                    "email": {"type": "string", "format": "email", "example": "store9942@saas-demo.com"},
                    "password": {
                        "type": "string",
                        "description": "كلمة مرور العميل للدخول على تطبيق الموظف (اختياري - يتم توليد كلمة مرور عشوائية قوية تلقائياً في حال عدم إرسالها)"
                        if is_ar else
                        "Client password for employee app login (optional - auto-generated if omitted)",
                        "example": "SecretPass123!"
                    },
                    "spending_cap": {"type": "number", "default": 10.0, "example": 25.0},
                    "minute_cap": {"type": "integer", "default": 60, "example": 200}
                }
            },
            "ClientRegisterResponse": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "example": "success"},
                    "client_id": {"type": "integer", "example": 19},
                    "name": {"type": "string", "example": "متجر النور التجريبي" if is_ar else "Al-Noor Store Demo"},
                    "external_reference": {"type": "string", "example": "sub_store_9942"},
                    "partner_code": {"type": "string", "example": "PRT-9B1D97E0"},
                    "credentials": {
                        "type": "object",
                        "description": "بيانات الدخول الفورية لتطبيق الموظف (Username / Extension / Password)"
                        if is_ar else
                        "Instant credentials for employee mobile app login",
                        "properties": {
                            "username": {"type": "string", "example": "store_9942"},
                            "password": {"type": "string", "example": "Pass_a1b2c3d4"},
                            "extension": {"type": "string", "example": "101"}
                        }
                    },
                    "owner_employee": {
                        "type": "object",
                        "description": "بروفايل الموظف المالك المنشأ تلقائياً للعميل" if is_ar else "Auto-generated owner employee profile",
                        "properties": {
                            "id": {"type": "integer", "example": 12},
                            "extension": {"type": "string", "example": "101"},
                            "display_name": {"type": "string", "example": "متجر النور التجريبي (المالك)" if is_ar else "Al-Noor Store Demo (Owner)"},
                            "department": {"type": "string", "example": "الإدارة العامة" if is_ar else "General Management"},
                            "status": {"type": "string", "example": "ready"},
                            "avatar_url": {"type": "string", "example": "https://api.dicebear.com/7.x/bottts/png?seed=101"}
                        }
                    },
                    "client": {"type": "object"},
                    "spending_cap": {"type": "number", "example": 25.0},
                    "minute_cap": {"type": "integer", "example": 200}
                }
            },
            "ClientListResponse": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "example": "success"},
                    "total_clients": {"type": "integer", "example": 1},
                    "clients": {
                        "type": "array",
                        "items": {"type": "object"}
                    }
                }
            },
            "ProfileCreateRequest": {
                "type": "object",
                "required": ["name"],
                "properties": {
                    "name": {"type": "string", "example": "مساعد المبيعات السعودي" if is_ar else "Saudi Sales Advisor"},
                    "voice_name": {"type": "string", "default": "Aoede", "example": "Aoede"},
                    "gender": {"type": "string", "enum": ["female", "male"], "default": "female"},
                    "language": {"type": "string", "default": "arabic", "example": "arabic"},
                    "dialect": {"type": "string", "default": "saudi", "example": "saudi"},
                    "persona_role": {"type": "string", "description": "الدور والشخصية بكتابة حرة", "example": "ممثل خدمة عملاء محترف"},
                    "speaking_style": {"type": "string", "description": "أسلوب الإلقاء والنبرة بكتابة حرة", "example": "ودود ولطيف ومرح"},
                    "verbosity": {"type": "string", "enum": ["concise", "balanced", "detailed"], "default": "balanced", "description": "مستوى الإيجاز وسرعة الرد: concise (مختصر), balanced (متوازن), detailed (مفصل)", "example": "concise"},
                    "custom_instructions": {"type": "string", "example": "أنت مستشار مبيعات ودود تتحدث باللهجة السعودية البيضاء." if is_ar else "You are a friendly sales advisor speaking in Saudi dialect."},
                    "off_topic_response": {
                        "type": "string",
                        "description": (
                            "الرسالة التي يرددها المساعد لما يسأله العميل سؤالاً خارج نطاق عمل المساعد. "
                            "إذا تُرك فارغاً، يعتذر باختصار ويعيد توجيه العميل تلقائياً."
                            if is_ar else
                            "The message the assistant says when the customer asks something outside its scope. "
                            "If empty, the assistant apologies briefly and redirects automatically."
                        ),
                        "example": (
                            "بعتذر جداً يا فندم، أنا بساعدك بس في خدمات المتجر، تحب تطلب حاجة؟"
                            if is_ar else
                            "Sorry, I can only assist with store services. Would you like to order something?"
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
                            "رسالة الرد عند الأسئلة خارج النطاق (فارغة = رد افتراضي آمن)"
                            if is_ar else
                            "Off-topic reply message (empty = safe automatic apology)"
                        )
                    },
                    "is_active": {"type": "boolean"}
                }
            },
            "ProfileSingleResponse": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "example": "success"},
                    "message": {"type": "string", "example": "Agent profile created successfully"},
                    "client_id": {"type": "integer", "example": 19},
                    "profile": {"type": "object"}
                }
            },
            "ProfileListResponse": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "example": "success"},
                    "client_id": {"type": "integer", "example": 19},
                    "total": {"type": "integer", "example": 2},
                    "active_profile": {"type": "object"},
                    "profiles": {"type": "array", "items": {"type": "object"}}
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
                        "example": {
                            "city": "الرياض" if is_ar else "Riyadh",
                            "vip_tier": "Gold",
                            "notes": "يفضل الشحن السريع بالصباح" if is_ar else "Prefers morning express delivery"
                        }
                    },
                    "immediate_notes": {"type": "string", "example": "استفسر عن كود الخصم وتم إرساله له بنجاح" if is_ar else "Inquired about coupon code, delivered successfully"},
                    "total_calls_count": {"type": "integer", "example": 3}
                }
            },
            "MemoryListResponse": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "example": "success"},
                    "client_id": {"type": "integer", "example": 19},
                    "total": {"type": "integer", "example": 12},
                    "page": {"type": "integer", "example": 1},
                    "limit": {"type": "integer", "example": 20},
                    "total_pages": {"type": "integer", "example": 1},
                    "memories": {"type": "array", "items": {"type": "object"}}
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
                "description": "خادم الواجهة البرمجية للشريك" if is_ar else "Partner SaaS API Server"
            }
        ],
        "security": [
            {"PartnerKey": []}
        ],
        "tags": tags,
        "paths": paths,
        "components": components
    }
