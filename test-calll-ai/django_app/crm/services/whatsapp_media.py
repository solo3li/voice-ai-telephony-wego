import os
import json
import base64
import logging
import requests
from typing import Tuple, Optional, Dict, Any
from pathlib import Path
from django.conf import settings
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

EVOLUTION_API_URL = os.getenv("EVOLUTION_API_URL", "http://evolution_api:8080")
EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY", "evolution_secret_key_123")


def get_media_dir() -> Path:
    """Ensure whatsapp_media directory exists in MEDIA_ROOT."""
    media_dir = Path(settings.MEDIA_ROOT) / "whatsapp_media"
    media_dir.mkdir(parents=True, exist_ok=True)
    return media_dir


def extract_media_info_from_message(raw_msg: dict, msg_type: str = "") -> dict:
    """Extract media type, mimetype, duration, filename, waveform from raw message dict."""
    if not isinstance(raw_msg, dict):
        return {"has_media": False}

    media_info = {"has_media": False}

    if "audioMessage" in raw_msg:
        aud = raw_msg["audioMessage"]
        media_info = {
            "has_media": True,
            "media_type": "audio",
            "mimetype": aud.get("mimetype", "audio/ogg; codecs=opus"),
            "duration": aud.get("seconds", 0),
            "ptt": aud.get("ptt", True),
            "waveform": aud.get("waveform", ""),
            "file_name": "voice_note.opus",
        }
    elif "imageMessage" in raw_msg:
        img = raw_msg["imageMessage"]
        media_info = {
            "has_media": True,
            "media_type": "image",
            "mimetype": img.get("mimetype", "image/jpeg"),
            "caption": img.get("caption", ""),
            "width": img.get("width"),
            "height": img.get("height"),
            "file_name": "image.jpeg",
        }
    elif "videoMessage" in raw_msg:
        vid = raw_msg["videoMessage"]
        media_info = {
            "has_media": True,
            "media_type": "video",
            "mimetype": vid.get("mimetype", "video/mp4"),
            "duration": vid.get("seconds", 0),
            "caption": vid.get("caption", ""),
            "file_name": "video.mp4",
        }
    elif "documentMessage" in raw_msg:
        doc = raw_msg["documentMessage"]
        media_info = {
            "has_media": True,
            "media_type": "document",
            "mimetype": doc.get("mimetype", "application/pdf"),
            "file_name": doc.get("fileName", "document.pdf"),
            "caption": doc.get("caption", ""),
        }
    elif "stickerMessage" in raw_msg:
        stk = raw_msg["stickerMessage"]
        media_info = {
            "has_media": True,
            "media_type": "sticker",
            "mimetype": stk.get("mimetype", "image/webp"),
            "file_name": "sticker.webp",
        }

    return media_info


def get_or_download_whatsapp_media(message_obj, instance_name: str = "default_workspace") -> Tuple[Optional[str], str]:
    """
    Fetch decrypted media from local cache or Evolution API.
    Returns (absolute_file_path, mimetype).
    """
    meta = message_obj.metadata or {}
    if not meta.get("has_media"):
        return None, ""

    # Resolve instance name to user_ID if available
    if (instance_name == "default_workspace" or not instance_name) and getattr(message_obj, "user_id", None):
        instance_name = f"user_{message_obj.user_id}"

    media_dir = get_media_dir()
    cached_path = meta.get("media_cached_path")
    if cached_path and os.path.exists(cached_path):
        return cached_path, meta.get("mimetype", "application/octet-stream")

    raw_key = meta.get("raw_key") or meta.get("raw_data", {}).get("key") or {}
    raw_msg = meta.get("raw_msg") or meta.get("raw_data", {}).get("message") or {}
    if not raw_key and not raw_msg:
        return None, ""

    # Call Evolution API getBase64FromMediaMessage
    url = f"{EVOLUTION_API_URL}/chat/getBase64FromMediaMessage/{instance_name}"
    payload = {
        "message": {
            "key": raw_key,
            "message": raw_msg
        },
        "convertToMp4": False
    }

    try:
        resp = requests.post(
            url,
            json=payload,
            headers={"apikey": EVOLUTION_API_KEY, "Content-Type": "application/json"},
            timeout=20.0
        )
        if resp.status_code in (200, 201):
            data = resp.json()
            b64_data = data.get("base64")
            if not b64_data:
                logger.warning(f"Empty base64 returned for message {message_obj.id}")
                return None, ""

            mimetype = data.get("mimetype") or meta.get("mimetype", "application/octet-stream")
            # Determine extension
            ext = ".bin"
            if "jpeg" in mimetype or "jpg" in mimetype:
                ext = ".jpg"
            elif "png" in mimetype:
                ext = ".png"
            elif "ogg" in mimetype or "opus" in mimetype:
                ext = ".opus"
            elif "mp4" in mimetype:
                ext = ".mp4"
            elif "pdf" in mimetype:
                ext = ".pdf"
            elif "webp" in mimetype:
                ext = ".webp"

            file_name = f"wa_{message_obj.id}_{raw_key.get('id', 'media')}{ext}"
            target_path = media_dir / file_name

            raw_bytes = base64.b64decode(b64_data)
            with open(target_path, "wb") as f:
                f.write(raw_bytes)

            # Update message metadata
            meta["media_cached_path"] = str(target_path)
            meta["mimetype"] = mimetype
            meta["media_size"] = len(raw_bytes)
            message_obj.metadata = meta
            message_obj.save(update_fields=["metadata"])

            logger.info(f"Cached WhatsApp media for msg {message_obj.id} at {target_path} ({len(raw_bytes)} bytes)")
            return str(target_path), mimetype
        else:
            logger.warning(f"Failed to fetch media for msg {message_obj.id}: {resp.status_code} - {resp.text[:150]}")
    except Exception as e:
        logger.error(f"Error fetching media for message {message_obj.id}: {e}", exc_info=True)

    return None, ""


def analyze_media_with_gemini(media_bytes: bytes, mimetype: str, media_type: str, caption: str = "") -> Dict[str, Any]:
    """
    Run Gemini 2.5 Flash Multimodal analysis for voice notes, images, or videos.
    Returns dict with transcription, vision_analysis, or summary.
    """
    from agents.models import SystemSetting
    api_key = SystemSetting.get_gemini_api_key() or os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        logger.warning("No GEMINI_API_KEY available for multimodal analysis")
        return {}

    try:
        client = genai.Client(api_key=api_key)

        if media_type == "audio":
            # Gemini Native Audio Transcription & Intent Extraction
            prompt = (
                "أنت خبير ذكاء اصطناعي في خدمة عملاء المطاعم في العالم العربي ومصر. "
                "استمع بعناية فائقة لهذا التسجيل الصوتي الوارد من العميل. "
                "قم بإنتاج إجابة بتنسيق JSON حصراً يحتوي على المفاتيح التالية:\n"
                "- transcription: التفريغ النصي الدقيق والشامل للكلمات التي قالها العميل بالعامية العربية أو المصرية.\n"
                "- summary: ملخص طلب أو استفسار العميل في جملة واحدة.\n"
                "- intent: نوع الطلب (طلب_أوردر / استفسار_منيو / شكوى / تعديل_طلب / غير_محدد).\n"
                "لا تكتب أي مقدمات خارج الـ JSON."
            )
            part = types.Part.from_bytes(data=media_bytes, mime_type=mimetype or "audio/ogg")
            res = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[part, prompt]
            )
            raw_text = res.text.strip()
            # Clean JSON
            if raw_text.startswith("```json"):
                raw_text = raw_text.replace("```json", "", 1)
            if raw_text.endswith("```"):
                raw_text = raw_text.rsplit("```", 1)[0]
            raw_text = raw_text.strip()
            try:
                parsed = json.loads(raw_text)
                return parsed
            except Exception:
                return {"transcription": res.text.strip(), "summary": res.text.strip(), "intent": "عام"}

        elif media_type in ("image", "video"):
            # Gemini Vision Analysis for Receipts, Menus, Complaints, Dishes
            prompt = (
                "أنت خبير ذكاء اصطناعي لمطاعم وخدمة عملاء. حلل هذه الصورة/الفيديو بدقة عالية. "
                f"شرح العميل المرفق: '{caption}'. "
                "قم بإنتاج إجابة بتنسيق JSON حصراً يحتوي على:\n"
                "- image_type: نوع الصورة (إيصال_تحويل_بنكي_أو_محفظة / صورة_طبق_أو_منيو / شكوى_جودة_أو_تغليف / أخرى)\n"
                "- description: وصف دقيق لما تحتويه الصورة/الفيديو باللغة العربية.\n"
                "- payment_details: كائن يحتوي على (المبلغ المحول، رقم العملية، اسم أو رقم المحول، التاريخ والوقت) إذا كانت الصورة إيصال تحويل InstaPay أو فودافون كاش أو بطاقة، وإلا null.\n"
                "- action_needed: الإجراء المقترح للمطعم.\n"
                "لا تكتب أي مقدمات خارج الـ JSON."
            )
            part = types.Part.from_bytes(data=media_bytes, mime_type=mimetype or ("video/mp4" if media_type == "video" else "image/jpeg"))
            res = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[part, prompt]
            )
            raw_text = res.text.strip()
            if raw_text.startswith("```json"):
                raw_text = raw_text.replace("```json", "", 1)
            if raw_text.endswith("```"):
                raw_text = raw_text.rsplit("```", 1)[0]
            raw_text = raw_text.strip()
            try:
                parsed = json.loads(raw_text)
                return parsed
            except Exception:
                return {"description": res.text.strip(), "image_type": "أخرى"}

    except Exception as e:
        logger.error(f"Error during Gemini multimodal analysis: {e}", exc_info=True)

    return {}
