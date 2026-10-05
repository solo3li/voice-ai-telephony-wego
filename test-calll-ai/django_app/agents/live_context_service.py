"""Structured Live Context Service for AI Voice Agent.

Provides dual-write persistence in PostgreSQL and sub-millisecond in-memory
retrieval via Redis for dynamic, structured business data (restaurant menus,
branches, delivery zones, out-of-stock items, daily specials).
"""
import json
import logging
import redis
from typing import Dict, Any, Optional
from django.conf import settings
from .models import TenantLiveContext

logger = logging.getLogger(__name__)

# Max payload size: 100 KB
MAX_LIVE_CONTEXT_BYTES = 100 * 1024
REDIS_KEY_TEMPLATE = "tenant:{user_id}:live_context"


def get_redis_client() -> Optional[redis.Redis]:
    """Obtain synchronous Redis connection client with graceful fallback."""
    redis_url = getattr(settings, 'REDIS_URL', 'redis://redis:6379/0')
    try:
        return redis.Redis.from_url(redis_url, decode_responses=True)
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
        return None


def get_user_live_context_cached(user_id: int) -> Dict[str, Any]:
    """Retrieve user's structured live context from Redis (< 2ms) with DB fallback & automatic hydration."""
    if not user_id:
        return {}

    r = get_redis_client()
    redis_key = REDIS_KEY_TEMPLATE.format(user_id=user_id)

    # 1. Try In-Memory Cache (Redis)
    if r:
        try:
            cached_val = r.get(redis_key)
            if cached_val:
                if isinstance(cached_val, str):
                    try:
                        return json.loads(cached_val)
                    except Exception:
                        pass
        except Exception as e:
            logger.warning(f"Redis get error for {redis_key}: {e}")

    # 2. Cache Miss: Fallback to PostgreSQL
    try:
        ctx_obj = TenantLiveContext.objects.filter(user_id=user_id).first()
        if ctx_obj and ctx_obj.data:
            data = ctx_obj.data
            # Hydrate Redis asynchronously / directly for subsequent calls
            if r:
                try:
                    serialized = json.dumps(data, ensure_ascii=False)
                    r.set(redis_key, serialized)
                except Exception as e:
                    logger.warning(f"Failed to hydrate Redis key {redis_key}: {e}")
            return data
    except Exception as e:
        logger.error(f"Database lookup error for TenantLiveContext (user_id={user_id}): {e}")

    return {}


def set_user_live_context(user_id: int, new_data: Dict[str, Any]) -> Dict[str, Any]:
    """Atomically overwrite user's structured live context in Postgres and Redis simultaneously.

    The new data completely replaces old data (Atomic Overwrite / Single Source of Truth).
    """
    if not user_id:
        raise ValueError("user_id is required")

    if not isinstance(new_data, dict):
        raise ValueError("Data must be a valid JSON dictionary")

    # Serialize & check payload size guardrail
    serialized = json.dumps(new_data, ensure_ascii=False)
    encoded_bytes = serialized.encode('utf-8')
    size_bytes = len(encoded_bytes)

    if size_bytes > MAX_LIVE_CONTEXT_BYTES:
        raise ValueError(
            f"Payload size ({size_bytes} bytes) exceeds maximum allowed limit of {MAX_LIVE_CONTEXT_BYTES} bytes (100 KB)"
        )

    # 1. Dual-Write: Update or create in PostgreSQL
    ctx_obj, _ = TenantLiveContext.objects.update_or_create(
        user_id=user_id,
        defaults={
            'data': new_data,
            'size_bytes': size_bytes
        }
    )

    # 2. Dual-Write: Atomic SET in Redis
    r = get_redis_client()
    redis_key = REDIS_KEY_TEMPLATE.format(user_id=user_id)
    if r:
        try:
            r.set(redis_key, serialized)
            logger.info(f"Updated live context in Redis ({redis_key}, {size_bytes} bytes)")
        except Exception as e:
            logger.error(f"Failed to write live context to Redis key {redis_key}: {e}")

    return ctx_obj.to_dict()


def delete_user_live_context(user_id: int) -> bool:
    """Atomically clear user's structured live context from Postgres and Redis."""
    if not user_id:
        return False

    # 1. Delete from PostgreSQL
    try:
        TenantLiveContext.objects.filter(user_id=user_id).delete()
    except Exception as e:
        logger.error(f"Failed to delete TenantLiveContext in DB: {e}")

    # 2. Delete from Redis
    r = get_redis_client()
    redis_key = REDIS_KEY_TEMPLATE.format(user_id=user_id)
    if r:
        try:
            r.delete(redis_key)
            logger.info(f"Deleted live context key from Redis: {redis_key}")
        except Exception as e:
            logger.error(f"Failed to delete Redis key {redis_key}: {e}")

    return True


def format_live_context_for_prompt(context_data: Dict[str, Any]) -> str:
    """Compile structured JSON into a compact, token-efficient, unambiguous Markdown prompt.

    Specifically optimized for Gemini Live audio streaming to prevent latency and hallucinations.
    """
    if not context_data or not isinstance(context_data, dict):
        return ""

    blocks = []

    # Business Name / Identity
    b_name = context_data.get("restaurant_name") or context_data.get("business_name") or context_data.get("اسم_النشاط")
    if b_name:
        blocks.append(f"اسم المنشأة / النشاط: {b_name}")

    # 1. Out of stock / Unavailable Items (CRITICAL PRIORITY)
    oos_list = (
        context_data.get("out_of_stock")
        or context_data.get("unavailable_today")
        or context_data.get("النواقص")
        or context_data.get("غير_متوفر")
    )
    if oos_list:
        if isinstance(oos_list, list):
            oos_items = [f"• {str(item).strip()}" for item in oos_list if str(item).strip()]
            oos_str = "\n".join(oos_items)
        else:
            oos_str = f"• {str(oos_list).strip()}"
        blocks.append(
            f"⚠️ أصناف غير متوفرة اليوم نهائياً (Out of Stock):\n"
            f"{oos_str}\n"
            f"- تنبيه إلزامي صارم: إذا طلب العميل أي صنف من هذه القائمة، اعتذر له بلطف ولباقة فوراً وأخبره أنه غير متوفر اليوم واقترح عليه بديلاً متوفراً."
        )

    # 2. Branches & Working Hours
    branches = context_data.get("branches") or context_data.get("locations") or context_data.get("الفروع")
    if branches:
        branch_lines = []
        if isinstance(branches, list):
            for b in branches:
                if isinstance(b, dict):
                    name = b.get("name") or b.get("branch") or b.get("الفرع") or "فرع"
                    status = b.get("status") or b.get("الحالة") or "مفتوح"
                    hours = b.get("hours") or b.get("working_hours") or b.get("المواعيد") or ""
                    phone = b.get("phone") or b.get("الهاتف") or ""
                    address = b.get("address") or b.get("العنوان") or ""
                    details = []
                    if status: details.append(f"الحالة: {status}")
                    if hours: details.append(f"مواعيد العمل: {hours}")
                    if address: details.append(f"العنوان: {address}")
                    if phone: details.append(f"الهاتف: {phone}")
                    branch_lines.append(f"- فرع {name}: ({'، '.join(details)})" if details else f"- فرع {name}")
                else:
                    branch_lines.append(f"- {str(b)}")
        elif isinstance(branches, dict):
            for k, v in branches.items():
                branch_lines.append(f"- فرع {k}: {v}")
        if branch_lines:
            blocks.append("🏢 الفروع ومواعيد العمل المباشرة:\n" + "\n".join(branch_lines))

    # 3. Delivery Zones & Fees
    delivery = context_data.get("delivery_zones") or context_data.get("delivery") or context_data.get("مناطق_التوصيل")
    if delivery:
        delivery_lines = []
        if isinstance(delivery, list):
            for d in delivery:
                if isinstance(d, dict):
                    zone = d.get("zone") or d.get("area") or d.get("name") or d.get("المنطقة") or ""
                    fee = d.get("fee") or d.get("cost") or d.get("رسوم_التوصيل") or ""
                    min_order = d.get("min_order") or d.get("minimum") or d.get("الحد_الأدنى") or ""
                    time_est = d.get("estimated_time") or d.get("time") or d.get("الوقت_المتوقع") or ""
                    details = []
                    if fee: details.append(f"رسوم: {fee}")
                    if min_order: details.append(f"حد أدنى: {min_order}")
                    if time_est: details.append(f"الوقت المتوقع: {time_est}")
                    delivery_lines.append(f"- منطقة {zone}: ({'، '.join(details)})" if details else f"- منطقة {zone}")
                else:
                    delivery_lines.append(f"- {str(d)}")
        elif isinstance(delivery, dict):
            for k, v in delivery.items():
                delivery_lines.append(f"- {k}: {v}")
        if delivery_lines:
            blocks.append("🛵 مناطق ورسوم التوصيل المعتمدة:\n" + "\n".join(delivery_lines))

    # 4. Offers & Specials
    offers = context_data.get("offers") or context_data.get("deals") or context_data.get("عروض") or context_data.get("العروض")
    if offers:
        offer_lines = []
        if isinstance(offers, list):
            for o in offers:
                if isinstance(o, dict):
                    title = o.get("title") or o.get("name") or o.get("العرض") or ""
                    price = o.get("price") or o.get("السعر") or ""
                    desc = o.get("description") or o.get("الوصف") or ""
                    parts = [title]
                    if price: parts.append(f"بسعر {price}")
                    if desc: parts.append(f"({desc})")
                    offer_lines.append(f"• {' '.join(parts)}")
                else:
                    offer_lines.append(f"• {str(o)}")
        elif isinstance(offers, dict):
            for k, v in offers.items():
                offer_lines.append(f"• {k}: {v}")
        if offer_lines:
            blocks.append("🎁 العروض والخصومات النشطة حالياً:\n" + "\n".join(offer_lines))

    # 5. Menu / Products
    menu = context_data.get("menu") or context_data.get("menu_items") or context_data.get("منيو") or context_data.get("قائمة_الطعام")
    if menu:
        menu_lines = []
        if isinstance(menu, list):
            for item in menu:
                if isinstance(item, dict):
                    i_name = item.get("name") or item.get("الصنف") or ""
                    i_price = item.get("price") or item.get("السعر") or ""
                    i_cat = item.get("category") or item.get("القسم") or ""
                    i_sizes = item.get("sizes") or item.get("الأحجام") or ""
                    i_desc = item.get("description") or item.get("الوصف") or ""
                    line_parts = [i_name]
                    if i_cat: line_parts.append(f"[{i_cat}]")
                    if i_price: line_parts.append(f"السعر: {i_price}")
                    if i_sizes:
                        if isinstance(i_sizes, dict):
                            sizes_str = "، ".join([f"{k}: {v}" for k, v in i_sizes.items()])
                            line_parts.append(f"(الأحجام: {sizes_str})")
                        else:
                            line_parts.append(f"(الأحجام: {i_sizes})")
                    if i_desc: line_parts.append(f"- {i_desc}")
                    menu_lines.append(f"- {' '.join(line_parts)}")
                else:
                    menu_lines.append(f"- {str(item)}")
        elif isinstance(menu, dict):
            # Categorized Menu: { "بيتزا": [...], "مشروبات": [...] }
            for cat, items in menu.items():
                menu_lines.append(f"  * قسم {cat}:")
                if isinstance(items, list):
                    for it in items:
                        if isinstance(it, dict):
                            it_name = it.get("name") or it.get("الصنف") or ""
                            it_price = it.get("price") or it.get("السعر") or ""
                            it_sizes = it.get("sizes") or ""
                            s_str = f" ({it_sizes})" if it_sizes else ""
                            menu_lines.append(f"    - {it_name}: {it_price}{s_str}")
                        else:
                            menu_lines.append(f"    - {str(it)}")
                else:
                    menu_lines.append(f"    - {str(items)}")
        if menu_lines:
            blocks.append("📋 قائمة الطعام والأسعار المعتمدة (Menu):\n" + "\n".join(menu_lines))

    # 6. Any other remaining freeform keys
    standard_keys = {
        "restaurant_name", "business_name", "اسم_النشاط",
        "out_of_stock", "unavailable_today", "النواقص", "غير_متوفر",
        "branches", "locations", "الفروع",
        "delivery_zones", "delivery", "مناطق_التوصيل",
        "offers", "deals", "عروض", "العروض",
        "menu", "menu_items", "منيو", "قائمة_الطعام"
    }
    other_lines = []
    for k, v in context_data.items():
        if k in standard_keys:
            continue
        label = k.replace("_", " ").title()
        if isinstance(v, (dict, list)):
            other_lines.append(f"- {label}:\n  {json.dumps(v, ensure_ascii=False)}")
        else:
            other_lines.append(f"- {label}: {v}")
    if other_lines:
        blocks.append("📌 معلومات إضافية من النظام:\n" + "\n".join(other_lines))

    if not blocks:
        return ""

    body = "\n\n".join(blocks)
    return (
        f"\n\n==================== [بيانات النشاط اللحظية المحدثة والمنظمة (Ground Truth)] ====================\n"
        f"المعلومات التالية هي الحقيقة الحالية المباشرة لنشاط العميل (فروع، أسعار، منيو، توصيل، نواقص).\n"
        f"استخدم هذه البيانات فوراً للإجابة عن استفسارات المتصل بدقة وسرعة دون تخمين ودون الحاجة لأي أداة خارجية:\n\n"
        f"{body}\n"
        f"=================================================================================================\n"
    )
