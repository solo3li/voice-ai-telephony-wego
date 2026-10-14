"""Background customer memory distillation and profile persistence."""
import time
import asyncio
import json
from typing import Dict, Any, List, Optional
from google.genai import types
from agent.config import logger, GEMINI_FLASH_MODEL
from agent.clients.django_client import save_call_session_and_update_memory_async


async def distill_and_update_memory(
    user_id: int,
    room_name: str,
    started_at: float,
    messages: List[Dict[str, Any]],
    current_profile: Dict[str, Any],
    caller_phone: str = "web_dashboard",
    genai_client = None,
    outbound_context: Optional[Dict[str, Any]] = None,
    api_key: Optional[str] = None,
):
    """Background task to extract permanent profile facts and distill short-term episode summary."""
    try:
        user_msgs = [m for m in messages if m.get("speaker") == "user"]
        calc_dur = max(1, int(time.time() - started_at)) if started_at else 0
        if not user_msgs or len(messages) < 2:
            logger.info(f"Call in room {room_name} had insufficient user speech turns ({len(messages)}). Finalizing session in Django.")
            await save_call_session_and_update_memory_async(
                user_id=user_id,
                room_name=room_name,
                started_at=started_at,
                transcript_text="",
                summary="لم يرد العميل على المكالمة أو تم إغلاقها فوراً.",
                updated_profile=dict(current_profile or {}),
                caller_phone=caller_phone,
                outbound_context=outbound_context,
                duration_seconds=calc_dur
            )
            return

        lines = []
        for m in messages:
            speaker_label = "العميل" if m.get("speaker") == "user" else "المساعد"
            lines.append(f"{speaker_label}: {m.get('text', '')}")
        transcript_text = "\n".join(lines)

        distillation_prompt = f"""أنت محلل ذكاء اصطناعي خبير في استخلاص ملفات وذاكرة العملاء لمساعد صوتي ذكي لخدمة العملاء والمطاعم.
المطلوب منك تحليل نص هذه المكالمة الصوتية واستخراج نقطتين فقط بدقة وإيجاز:

1. "summary": ملخص دقيق ومركز في سطرين فقط (لا يتعدى 50 كلمة) لما دار في المكالمة، المنتجات أو الأسئلة، وموقف العميل وحالة طلبه.
   - قاعدة إلزامية: يُمنع منعاً باتاً تسجيل أي عبارات مثل 'عطل في السيستم' أو 'مشكلة فنية' في الملخص! ركز فقط على احتياج العميل وما طلبه.

2. "new_permanent_facts": أي حقائق وتفاصيل مستفادة من كلام العميل لتحديث ملفه الدائم:
   - "customer_name": اسم العميل إذا ذكره أو عُرف به.
   - "phone": رقم هاتف العميل إذا ذكره صراحة.
   - "vip_tier": تصنيف العميل ("vip" للعملاء المهمين أو كثيري الطلب، "regular" للمتكرر، "new" للجديد).
   - "personality": طبيعة وأسلوب المتصل:
       - "pace": ("fast" إذا كان مستعجلاً ويطلب الإنجاز السريع، "relaxed" إذا كان هادئاً، "detailed" إذا كان يسأل عن أدق التفاصيل).
       - "communication_style": ("direct" إيجاز مباشر، أو "friendly" ودود ويحب الحديث).
       - "price_sensitivity": ("bargain_seeker" يبحث عن عروض وخصومات، أو "quality_focused" مهتم بالجودة، أو "normal").
   - "preferences":
       - "favorite_items": قائمة الأصناف أو الوجبات التي يفضلها أو كرر طلبها.
       - "dietary_restrictions": ملاحظات غذائية واشتراطات خاصة (مثل: "بدون مايونيز"، "بدون شطة"، "دايت"، "حساسية من الجلوتين").
       - "payment_method": طريقة الدفع المفضلة (كاش عند الاستلام، بطاقة/فيزا عند الاستلام، دفع إلكتروني).
   - "addresses": قائمة العناوين التي ذكرها العميل للتوصيل (إن ذكر أي عنوان)، كل عنوان ككائن:
       - "label": تصنيف العنوان (مثل "المنزل"، "العمل"، "الفيلا"، أو المنطقة).
       - "address": تفاصيل الشارع والمنطقة/المدينة.
       - "landmarks": علامة مميزة (مسجد، صيدلية، مول).
       - "apartment_details": تفاصيل الدور ورقم الشقة أو العمارة.
       - "instructions": تعليمات الاستلام (مثل: الاتصال هاتفياً عند الوصول، عدم رن الجرس).
   - "past_issues": أي شكوى أو مشكلة سابقة ذكرها العميل في المكالمة (مثال: تأخر الطلب سابقاً، صوص مفقود). (تنبيه حاسم: يُمنع منعاً باتاً تسجيل أي وعود قطعها المساعد!).
   - "sentiment": انطباع ورضا العميل العام ("positive", "neutral", "unhappy").
   - "notes": أي ملاحظة شخصية أخرى هامة تفيد خدمة العميل.

إذا لم يذكر العميل أي معلومة جديدة لحقل معين، لا تضعه أو اتركه فارغاً.

البروفايل الدائم الحالي للعميل:
{json.dumps(current_profile, ensure_ascii=False)}

نص المكالمة:
{transcript_text}

أجب بصيغة JSON فقط بهذا الشكل:
{{
  "summary": "...",
  "new_permanent_facts": {{
    "customer_name": "...",
    "phone": "...",
    "vip_tier": "regular",
    "personality": {{
      "pace": "fast",
      "communication_style": "direct",
      "price_sensitivity": "normal"
    }},
    "preferences": {{
      "favorite_items": ["..."],
      "dietary_restrictions": ["..."],
      "payment_method": "..."
    }},
    "addresses": [
      {{
        "label": "المنزل",
        "address": "...",
        "landmarks": "...",
        "apartment_details": "...",
        "instructions": "..."
      }}
    ],
    "past_issues": "...",
    "sentiment": "positive",
    "notes": "..."
  }}
}}"""

        if genai_client is None:
            try:
                from google import genai
                from agent.config import GEMINI_API_KEY
                active_key = api_key or (current_profile.get("gemini_api_key") if isinstance(current_profile, dict) else None) or GEMINI_API_KEY
                if active_key and not active_key.startswith("your_"):
                    genai_client = genai.Client(api_key=active_key)
            except Exception as client_err:
                logger.warning(f"Could not initialize genai.Client for memory distillation: {client_err}")

        summary = ""
        new_facts = {}
        if genai_client is not None:
            try:
                response = await genai_client.aio.models.generate_content(
                    model=GEMINI_FLASH_MODEL,
                    contents=distillation_prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json"
                    )
                )
                resp_text = response.text or "{}"
                data = json.loads(resp_text)
                summary = data.get("summary", "").strip()
                new_facts = data.get("new_permanent_facts", {})
            except Exception as dist_err:
                logger.warning(f"Distillation LLM error: {dist_err}")
                summary = f"مكالمة مكتملة ({len(user_msgs)} ردود)."
        else:
            summary = f"مكالمة مكتملة ({len(user_msgs)} ردود)."

        updated_profile = dict(current_profile or {})
        if new_facts and isinstance(new_facts, dict):
            # 1. Basic top-level customer fields
            for k in ["customer_name", "phone", "vip_tier", "notes", "sentiment"]:
                val = new_facts.get(k)
                if val and str(val).strip() and str(val).strip().lower() not in ["null", "none", "..."]:
                    updated_profile[k] = str(val).strip()

            # 2. Personality & Behavioral profile
            new_pers = new_facts.get("personality")
            if new_pers and isinstance(new_pers, dict):
                curr_pers = dict(updated_profile.get("personality") or {})
                for pk in ["pace", "communication_style", "price_sensitivity"]:
                    pval = new_pers.get(pk)
                    if pval and str(pval).strip() and str(pval).strip().lower() not in ["null", "none", "..."]:
                        curr_pers[pk] = str(pval).strip()
                if curr_pers:
                    updated_profile["personality"] = curr_pers

            # 3. Preferences (Favorite items, dietary restrictions, payment method)
            new_prefs = new_facts.get("preferences")
            curr_prefs = dict(updated_profile.get("preferences") or {}) if isinstance(updated_profile.get("preferences"), dict) else {}
            if new_prefs and isinstance(new_prefs, dict):
                # Favorite items
                if new_prefs.get("favorite_items") and isinstance(new_prefs["favorite_items"], list):
                    existing_items = list(curr_prefs.get("favorite_items") or [])
                    for item in new_prefs["favorite_items"]:
                        item_str = str(item).strip()
                        if item_str and item_str not in existing_items and item_str.lower() not in ["...", "none"]:
                            existing_items.append(item_str)
                    curr_prefs["favorite_items"] = existing_items[:8]

                # Dietary restrictions (e.g. without spicy, without mayo)
                if new_prefs.get("dietary_restrictions") and isinstance(new_prefs["dietary_restrictions"], list):
                    existing_diet = list(curr_prefs.get("dietary_restrictions") or [])
                    for diet in new_prefs["dietary_restrictions"]:
                        d_str = str(diet).strip()
                        if d_str and d_str not in existing_diet and d_str.lower() not in ["...", "none"]:
                            existing_diet.append(d_str)
                    curr_prefs["dietary_restrictions"] = existing_diet[:6]

                # Payment method
                if new_prefs.get("payment_method"):
                    pm = str(new_prefs["payment_method"]).strip()
                    if pm and pm.lower() not in ["null", "none", "..."]:
                        curr_prefs["payment_method"] = pm

            # Backward compatibility with legacy preferences array
            if isinstance(new_facts.get("preferences"), list):
                existing_prefs = list(updated_profile.get("legacy_preferences") or [])
                for p in new_facts["preferences"]:
                    p_str = str(p).strip()
                    if p_str and p_str not in existing_prefs:
                        existing_prefs.append(p_str)
                updated_profile["legacy_preferences"] = existing_prefs[:6]

            if curr_prefs:
                updated_profile["preferences"] = curr_prefs

            # 4. Multi-Address List Management
            existing_addresses = list(updated_profile.get("addresses") or [])
            # Migrate legacy single address if exists
            legacy_addr = updated_profile.get("address") or updated_profile.get("city")
            if legacy_addr and not any(a.get("address") == legacy_addr for a in existing_addresses if isinstance(a, dict)):
                existing_addresses.insert(0, {
                    "label": "العنوان السابق",
                    "address": str(legacy_addr).strip(),
                    "landmarks": "",
                    "apartment_details": "",
                    "instructions": ""
                })

            raw_new_addresses = new_facts.get("addresses") or []
            if isinstance(raw_new_addresses, dict):
                raw_new_addresses = [raw_new_addresses]
            elif isinstance(raw_new_addresses, str) and raw_new_addresses.strip():
                raw_new_addresses = [{"label": "عنوان التوصيل", "address": raw_new_addresses.strip()}]

            for n_addr in raw_new_addresses:
                if isinstance(n_addr, dict) and n_addr.get("address"):
                    clean_addr_text = str(n_addr.get("address", "")).strip()
                    if not clean_addr_text or clean_addr_text.lower() in ["null", "none", "..."]:
                        continue
                    # Match or update existing address
                    matched = False
                    for ex in existing_addresses:
                        if isinstance(ex, dict) and (ex.get("address") == clean_addr_text or ex.get("label") == n_addr.get("label")):
                            # Update with richer details if available
                            for f in ["landmarks", "apartment_details", "instructions", "label"]:
                                if n_addr.get(f) and str(n_addr[f]).strip():
                                    ex[f] = str(n_addr[f]).strip()
                            matched = True
                            break
                    if not matched:
                        existing_addresses.insert(0, {
                            "label": str(n_addr.get("label") or f"عنوان {len(existing_addresses) + 1}").strip(),
                            "address": clean_addr_text,
                            "landmarks": str(n_addr.get("landmarks") or "").strip(),
                            "apartment_details": str(n_addr.get("apartment_details") or "").strip(),
                            "instructions": str(n_addr.get("instructions") or "").strip(),
                        })

            if existing_addresses:
                updated_profile["addresses"] = existing_addresses[:6]

            # 5. Past Issues & Complaints (No promises!)
            new_issue = new_facts.get("past_issues")
            if new_issue and str(new_issue).strip() and str(new_issue).strip().lower() not in ["null", "none", "لا يوجد", "..."]:
                curr_issues = list(updated_profile.get("past_issues") or [])
                if isinstance(curr_issues, str):
                    curr_issues = [curr_issues]
                clean_issue = str(new_issue).strip()
                if clean_issue not in curr_issues:
                    curr_issues.append(clean_issue)
                updated_profile["past_issues"] = curr_issues[-3:]

        # Dynamic binding: if caller was anonymous/web but explicitly stated their phone number in the call
        extracted_phone = updated_profile.get("phone")
        final_phone = caller_phone
        if extracted_phone and str(extracted_phone).strip() and caller_phone in ['web_dashboard', 'anonymous', 'unknown', '']:
            final_phone = str(extracted_phone).strip()
            logger.info(f"Dynamically bound call in room {room_name} to extracted phone '{final_phone}'")

        logger.info(f"Distillation complete for ({user_id}, {final_phone}). Summary: {summary[:80]}...")

        calc_dur = max(1, int(time.time() - started_at)) if started_at else 0
        await save_call_session_and_update_memory_async(
            user_id=user_id,
            room_name=room_name,
            started_at=started_at,
            transcript_text=transcript_text,
            summary=summary,
            updated_profile=updated_profile,
            caller_phone=final_phone,
            outbound_context=outbound_context,
            duration_seconds=calc_dur
        )
    except Exception as e:
        logger.error(f"Error in distill_and_update_memory for user {user_id}: {e}", exc_info=True)
