import io
import re
import csv
import json
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

PHONE_HEADER_CANDIDATES = {
    'phone', 'phone_number', 'phonenumber', 'mobile', 'tel', 'cell',
    'telephone', 'contact_number', 'contact', 'msisdn',
    'هاتف', 'الهاتف', 'موبايل', 'الموبايل', 'تليفون', 'التليفون',
    'جوال', 'الجوال', 'رقم', 'رقم الهاتف', 'رقم الموبايل', 'رقم الجوال'
}

NAME_HEADER_CANDIDATES = {
    'name', 'customer_name', 'customer', 'full_name', 'fullname',
    'first_name', 'client', 'lead_name', 'lead',
    'اسم', 'الاسم', 'اسم العميل', 'العميل', 'المستخدم', 'الاسم الكامل'
}

def normalize_phone(raw_phone: str) -> str:
    """Normalize phone number to international E.164 format."""
    cleaned = re.sub(r'[\s\-\(\)\.]', '', str(raw_phone or '').strip())
    if not cleaned:
        return ""
    if cleaned.startswith('00'):
        cleaned = '+' + cleaned[2:]
    elif cleaned.startswith('01') and len(cleaned) == 11 and cleaned.isdigit():
        cleaned = '+20' + cleaned[1:]
    elif cleaned.startswith('201') and len(cleaned) == 12 and cleaned.isdigit():
        cleaned = '+' + cleaned
    elif not cleaned.startswith('+') and re.match(r'^[1-9]\d{6,14}$', cleaned):
        cleaned = '+' + cleaned
    return cleaned

def is_valid_phone(phone: str) -> bool:
    if not phone:
        return False
    # Standard E.164 or numeric local extension
    if phone.startswith('+') and len(phone) >= 8 and phone[1:].isdigit():
        return True
    if phone.isdigit() and 3 <= len(phone) <= 15:
        return True
    return False

def _find_header_match(headers: List[str], candidates: set) -> str | None:
    for h in headers:
        normalized_h = str(h).strip().lower().replace('_', '').replace(' ', '')
        for c in candidates:
            if normalized_h == c.replace('_', '').replace(' ', ''):
                return h
    # Substring search
    for h in headers:
        normalized_h = str(h).strip().lower()
        for c in candidates:
            if c in normalized_h:
                return h
    return None

def parse_leads_file(file_bytes: bytes, filename: str) -> Dict[str, Any]:
    """
    Universal multi-format parser supporting CSV, Excel (.xlsx/.xls), JSON, and TXT.
    Returns parsed valid contacts with custom attributes preserved.
    """
    ext = filename.lower().split('.')[-1] if '.' in filename else ''
    valid_contacts = []
    invalid_rows = 0
    detected_headers = []

    try:
        if ext in ['csv', 'txt']:
            # Decode file content with fallback
            content = None
            for encoding in ['utf-8-sig', 'utf-8', 'cp1256', 'latin-1']:
                try:
                    content = file_bytes.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            if content is None:
                content = file_bytes.decode('utf-8', errors='ignore')

            lines = [l for l in content.splitlines() if l.strip()]
            if not lines:
                return {"status": "error", "message": "الملف المرفوع فارغ / Uploaded file is empty"}

            # If TXT and might be plain lines with numbers only
            if ext == 'txt' and not any(sep in lines[0] for sep in [',', '\t', ';', '|']):
                detected_headers = ['الهاتف']
                for line in lines:
                    phone = normalize_phone(line.strip())
                    if is_valid_phone(phone):
                        valid_contacts.append({
                            "customer_name": f"عميل ({phone})",
                            "phone_number": phone,
                            "attributes": {}
                        })
                    else:
                        invalid_rows += 1
            else:
                # Delimiter sniffing
                first_line = lines[0]
                delimiter = ','
                for sep in [',', '\t', ';', '|']:
                    if sep in first_line:
                        delimiter = sep
                        break

                reader = csv.reader(lines, delimiter=delimiter)
                raw_rows = list(reader)
                if not raw_rows:
                    return {"status": "error", "message": "لم يتم العثور على أسطر صالحة في الملف"}

                header_row = [str(col).strip() for col in raw_rows[0]]
                phone_col = _find_header_match(header_row, PHONE_HEADER_CANDIDATES)
                name_col = _find_header_match(header_row, NAME_HEADER_CANDIDATES)

                has_header = (phone_col is not None or name_col is not None)
                data_rows = raw_rows[1:] if has_header else raw_rows
                detected_headers = header_row if has_header else [f"عمود {i+1}" for i in range(len(raw_rows[0]))]

                phone_idx = header_row.index(phone_col) if phone_col else 0
                name_idx = header_row.index(name_col) if name_col else (1 if len(header_row) > 1 else None)

                for row in data_rows:
                    if not row or not any(row):
                        continue
                    raw_phone = row[phone_idx] if len(row) > phone_idx else ""
                    norm_phone = normalize_phone(raw_phone)
                    if not is_valid_phone(norm_phone):
                        invalid_rows += 1
                        continue

                    cust_name = ""
                    if name_idx is not None and len(row) > name_idx:
                        cust_name = str(row[name_idx]).strip()
                    if not cust_name:
                        cust_name = f"عميل ({norm_phone})"

                    # Capture remaining custom columns
                    attributes = {}
                    for idx, val in enumerate(row):
                        if idx != phone_idx and idx != name_idx:
                            col_name = detected_headers[idx] if idx < len(detected_headers) else f"Field_{idx+1}"
                            val_str = str(val).strip()
                            if val_str:
                                attributes[col_name] = val_str

                    valid_contacts.append({
                        "customer_name": cust_name,
                        "phone_number": norm_phone,
                        "attributes": attributes
                    })

        elif ext in ['xlsx', 'xls']:
            import openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
            sheet = wb.active
            rows = list(sheet.iter_rows(values_only=True))
            if not rows:
                return {"status": "error", "message": "شيت الإكسل المرفوع فارغ"}

            raw_header = [str(col or '').strip() for col in rows[0]]
            phone_col = _find_header_match(raw_header, PHONE_HEADER_CANDIDATES)
            name_col = _find_header_match(raw_header, NAME_HEADER_CANDIDATES)

            has_header = (phone_col is not None or name_col is not None)
            data_rows = rows[1:] if has_header else rows
            detected_headers = [h or f"Column_{i+1}" for i, h in enumerate(raw_header)] if has_header else [f"عمود {i+1}" for i in range(len(rows[0]))]

            phone_idx = raw_header.index(phone_col) if phone_col else 0
            name_idx = raw_header.index(name_col) if name_col else (1 if len(raw_header) > 1 else None)

            for row in data_rows:
                if not row or not any(row):
                    continue
                raw_phone = str(row[phone_idx] or '').strip() if len(row) > phone_idx else ""
                norm_phone = normalize_phone(raw_phone)
                if not is_valid_phone(norm_phone):
                    invalid_rows += 1
                    continue

                cust_name = ""
                if name_idx is not None and len(row) > name_idx and row[name_idx]:
                    cust_name = str(row[name_idx]).strip()
                if not cust_name:
                    cust_name = f"عميل ({norm_phone})"

                attributes = {}
                for idx, val in enumerate(row):
                    if idx != phone_idx and idx != name_idx and val is not None:
                        col_name = detected_headers[idx] if idx < len(detected_headers) else f"Field_{idx+1}"
                        val_str = str(val).strip()
                        if val_str:
                            attributes[col_name] = val_str

                valid_contacts.append({
                    "customer_name": cust_name,
                    "phone_number": norm_phone,
                    "attributes": attributes
                })

        elif ext == 'json':
            text = file_bytes.decode('utf-8', errors='ignore')
            data = json.loads(text)
            items = []
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                for k in ['contacts', 'leads', 'data', 'customers', 'users', 'items']:
                    if isinstance(data.get(k), list):
                        items = data[k]
                        break
                if not items and data:
                    items = [data]

            if not items:
                return {"status": "error", "message": "لم يتم العثور على مصفوفة بيانات صالحة في ملف JSON"}

            # Detect keys
            first_item = items[0] if isinstance(items[0], dict) else {}
            keys = list(first_item.keys()) if isinstance(first_item, dict) else ['phone']
            detected_headers = keys
            phone_key = _find_header_match(keys, PHONE_HEADER_CANDIDATES) or 'phone'
            name_key = _find_header_match(keys, NAME_HEADER_CANDIDATES) or 'name'

            for item in items:
                if not isinstance(item, dict):
                    invalid_rows += 1
                    continue
                raw_phone = str(item.get(phone_key) or item.get('phone') or item.get('mobile') or '').strip()
                norm_phone = normalize_phone(raw_phone)
                if not is_valid_phone(norm_phone):
                    invalid_rows += 1
                    continue

                cust_name = str(item.get(name_key) or item.get('name') or item.get('customer_name') or '').strip()
                if not cust_name:
                    cust_name = f"عميل ({norm_phone})"

                attributes = {k: v for k, v in item.items() if k not in [phone_key, name_key, 'phone', 'name']}
                valid_contacts.append({
                    "customer_name": cust_name,
                    "phone_number": norm_phone,
                    "attributes": attributes
                })
        else:
            return {"status": "error", "message": f"صيغة الملف غير مدعومة ({ext}). الصيغ المدعومة هي: CSV, XLSX, XLS, JSON, TXT"}

        return {
            "status": "success",
            "total_extracted": len(valid_contacts),
            "invalid_rows_count": invalid_rows,
            "detected_headers": detected_headers,
            "valid_contacts": valid_contacts,
            "preview_sample": valid_contacts[:5]
        }
    except Exception as e:
        logger.exception("Error parsing leads file")
        return {"status": "error", "message": f"حدث خطأ أثناء قراءة الملف: {str(e)}"}
