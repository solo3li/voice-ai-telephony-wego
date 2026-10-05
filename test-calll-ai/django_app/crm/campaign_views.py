import io
import csv
import json
import logging
from datetime import datetime, timezone
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt

import inngest
from .models import OutboundCampaign, CampaignContact, UserCampaignLimit
from .file_parser import parse_leads_file
from .inngest_jobs import inngest_client, broadcast_campaign_update
from agents.models import AgentProfile

logger = logging.getLogger(__name__)


@login_required(login_url='/login/')
def api_upload_and_create_campaign(request):
    """
    Accepts an uploaded file (CSV, XLSX, XLS, JSON, TXT) along with campaign configuration,
    creates the OutboundCampaign, stores and organizes contacts in the CRM, and leaves it in 'draft'
    status so the user can review before dialing.
    """
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)

    try:
        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            return JsonResponse({"status": "error", "message": "يرجى اختيار ملف لرفعه (CSV, Excel, JSON, TXT)"}, status=400)

        campaign_name = request.POST.get('name', '').strip()
        if not campaign_name:
            campaign_name = f"حملة {uploaded_file.name} - {datetime.now().strftime('%Y/%m/%d %H:%M')}"

        call_prompt = request.POST.get('call_prompt', '').strip()
        profile_id = request.POST.get('agent_profile_id')
        agent_profile = AgentProfile.objects.filter(id=profile_id, user=request.user).first() if profile_id else None

        max_retries = int(request.POST.get('max_retries', 1))
        retry_delay = int(request.POST.get('retry_delay_minutes', 15))
        gateway_type = request.POST.get('gateway_type', 'auto')
        gateway_id = request.POST.get('gateway_id')
        gateway_id_int = int(gateway_id) if gateway_id and str(gateway_id).isdigit() else None

        file_bytes = uploaded_file.read()
        parse_res = parse_leads_file(file_bytes, uploaded_file.name)

        if parse_res.get("status") != "success":
            return JsonResponse({"status": "error", "message": parse_res.get("message", "فشل تحليل الملف")}, status=400)

        valid_contacts = parse_res.get("valid_contacts", [])
        if not valid_contacts:
            return JsonResponse({
                "status": "error",
                "message": "لم يتم العثور على أي أرقام هواتف صالحة داخل الملف المرفوع. يرجى التأكد من محتوى الملف."
            }, status=400)

        # Create Campaign
        campaign = OutboundCampaign.objects.create(
            user=request.user,
            name=campaign_name,
            agent_profile=agent_profile,
            call_prompt=call_prompt,
            max_retries=max(0, min(5, max_retries)),
            retry_delay_minutes=max(1, min(1440, retry_delay)),
            gateway_type=gateway_type,
            gateway_id=gateway_id_int,
            status='draft'
        )

        # Bulk create contacts
        contact_objs = [
            CampaignContact(
                campaign=campaign,
                customer_name=c.get("customer_name") or f"عميل ({c.get('phone_number')})",
                phone_number=c.get("phone_number"),
                attributes=c.get("attributes", {}),
                call_status='pending',
                interest_level='uncontacted'
            )
            for c in valid_contacts
        ]
        CampaignContact.objects.bulk_create(contact_objs)
        campaign.update_metrics()

        return JsonResponse({
            "status": "success",
            "message": f"تم استيراد {len(valid_contacts)} عميل بنجاح وتنظيمهم داخل الحملة.",
            "campaign": campaign.to_dict(),
            "detected_headers": parse_res.get("detected_headers", []),
            "total_extracted": len(valid_contacts),
            "invalid_rows_count": parse_res.get("invalid_rows_count", 0),
            "preview_sample": [c.to_dict() for c in campaign.contacts.all()[:10]]
        })

    except Exception as e:
        logger.exception("Error creating campaign from file")
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@login_required(login_url='/login/')
def api_list_campaigns(request):
    """List all outbound campaigns for the authenticated user."""
    from telephony.services import check_has_active_outbound_gateway
    campaigns = OutboundCampaign.objects.filter(user=request.user)
    limit = UserCampaignLimit.get_limit_for_user(request.user)
    has_gw, _, _, _, _ = check_has_active_outbound_gateway(user=request.user)
    return JsonResponse({
        "status": "success",
        "user_concurrency_limit": limit,
        "has_outbound_gateway": has_gw,
        "campaigns": [c.to_dict() for c in campaigns]
    })


@login_required(login_url='/login/')
def api_get_campaign_detail(request, campaign_id):
    """Retrieve campaign details and filtered CRM contact list."""
    from telephony.services import check_has_active_outbound_gateway
    campaign = get_object_or_404(OutboundCampaign, id=campaign_id, user=request.user)
    contacts_qs = campaign.contacts.all()

    has_gw, _, _, _, _ = check_has_active_outbound_gateway(
        user=request.user,
        gateway_type=campaign.gateway_type,
        gateway_id=campaign.gateway_id
    )

    # Filters
    call_status = request.GET.get('call_status', '').strip()
    if call_status and call_status != 'all':
        contacts_qs = contacts_qs.filter(call_status=call_status)

    interest = request.GET.get('interest', '').strip()
    if interest and interest != 'all':
        contacts_qs = contacts_qs.filter(interest_level=interest)

    search = request.GET.get('q', '').strip()
    if search:
        from django.db.models import Q
        contacts_qs = contacts_qs.filter(
            Q(customer_name__icontains=search) |
            Q(phone_number__icontains=search) |
            Q(call_summary__icontains=search)
        )

    limit_count = int(request.GET.get('limit', 200))
    contacts_data = [c.to_dict() for c in contacts_qs[:limit_count]]

    return JsonResponse({
        "status": "success",
        "campaign": campaign.to_dict(),
        "user_concurrency_limit": UserCampaignLimit.get_limit_for_user(request.user),
        "has_outbound_gateway": has_gw,
        "contacts": contacts_data,
        "total_filtered": contacts_qs.count()
    })


@login_required(login_url='/login/')
def api_start_campaign(request, campaign_id):
    """Start or resume the auto-dialer for an outbound campaign via Inngest."""
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)

    campaign = get_object_or_404(OutboundCampaign, id=campaign_id, user=request.user)

    # 1. Strict Pre-flight Check: Verify Outbound SIP Trunk / Gateway exists BEFORE doing anything
    from telephony.services import check_has_active_outbound_gateway
    has_gw, _, _, _, err_msg = check_has_active_outbound_gateway(
        user=request.user,
        gateway_type=campaign.gateway_type,
        gateway_id=campaign.gateway_id
    )
    if not has_gw:
        return JsonResponse({
            "status": "error",
            "code": "no_outbound_gateway",
            "message": "لا يمكن بدء الحملة: لا يوجد خط اتصال صادر (SIP Trunk) مفعل في حسابك. يرجى إعداد وتفعيل خط صادر أولاً من تبويب 'الربط الهاتفي والسنترال' لتتمكن من إجراء المكالمات الصادرة."
        }, status=422)

    limit = UserCampaignLimit.get_limit_for_user(request.user)

    campaign.status = 'running'
    campaign.save(update_fields=['status', 'updated_at'])

    pending_contacts = list(campaign.contacts.filter(call_status='pending').values_list('id', flat=True))
    if not pending_contacts:
        return JsonResponse({
            "status": "error",
            "message": "لا يوجد عملاء في قائمة الانتظار للاتصال بهم في هذه الحملة."
        }, status=400)

    try:
        from asgiref.sync import async_to_sync
        events = [
            inngest.Event(
                name="campaign/contact.dial",
                data={
                    "campaign_id": campaign.id,
                    "contact_id": cid,
                    "user_id": campaign.user_id,
                    "concurrency_limit": limit
                }
            )
            for cid in pending_contacts
        ]
        async_to_sync(inngest_client.send)(events)
        broadcast_campaign_update(campaign.id, "campaign_started", {
            "queued": len(pending_contacts),
            "concurrency_limit": limit
        })

        return JsonResponse({
            "status": "success",
            "message": f"تم بدء الحملة بنجاح وجدولة الاتصال بـ {len(pending_contacts)} عميل بمعدل تزامن ({limit} مكالمات متزامنة).",
            "campaign": campaign.to_dict()
        })
    except Exception as e:
        logger.exception("Error starting campaign via Inngest")
        return JsonResponse({"status": "error", "message": f"حدث خطأ أثناء إطلاق الحملة: {str(e)}"}, status=500)


@login_required(login_url='/login/')
def api_pause_campaign(request, campaign_id):
    """Pause an active outbound campaign."""
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)

    campaign = get_object_or_404(OutboundCampaign, id=campaign_id, user=request.user)
    campaign.status = 'paused'
    campaign.save(update_fields=['status', 'updated_at'])

    broadcast_campaign_update(campaign.id, "campaign_paused", {})
    return JsonResponse({
        "status": "success",
        "message": "تم إيقاف الحملة مؤقتاً. يمكنك استئنافها في أي وقت.",
        "campaign": campaign.to_dict()
    })


@login_required(login_url='/login/')
def api_reset_campaign_contacts(request, campaign_id):
    """
    Resets all contacts in a campaign back to 'pending',
    zeroes retries and clears failure summaries, setting campaign back to 'draft'.
    """
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)

    campaign = get_object_or_404(OutboundCampaign, id=campaign_id, user=request.user)
    campaign.status = 'draft'
    campaign.save(update_fields=['status', 'updated_at'])

    updated_count = campaign.contacts.filter(call_status__in=['failed', 'busy', 'no_answer', 'in_progress']).update(
        call_status='pending',
        interest_level='uncontacted',
        retries_count=0,
        call_summary='',
        extracted_data={}
    )
    campaign.update_metrics()

    return JsonResponse({
        "status": "success",
        "message": f"تمت إعادة تعيين {updated_count} عميل لحالة 'في الانتظار' بنجاح وجاهزيتهم للاتصال.",
        "campaign": campaign.to_dict()
    })


@login_required(login_url='/login/')
def api_dial_single_contact(request, contact_id):
    """Manually trigger an outbound call for a single contact in the CRM table."""
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)

    contact = get_object_or_404(CampaignContact, id=contact_id, campaign__user=request.user)

    # Strict Pre-flight Check: Verify Outbound SIP Trunk / Gateway exists
    from telephony.services import check_has_active_outbound_gateway
    has_gw, _, _, _, err_msg = check_has_active_outbound_gateway(
        user=request.user,
        gateway_type=contact.campaign.gateway_type,
        gateway_id=contact.campaign.gateway_id
    )
    if not has_gw:
        return JsonResponse({
            "status": "error",
            "code": "no_outbound_gateway",
            "message": "لا يمكن إجراء المكالمة: لا يوجد خط اتصال صادر (SIP Trunk) مفعل حالياً. يرجى إعداد وتفعيل خط صادر أولاً من تبويب 'الربط الهاتفي والسنترال'."
        }, status=422)

    limit = UserCampaignLimit.get_limit_for_user(request.user)

    try:
        from asgiref.sync import async_to_sync
        async_to_sync(inngest_client.send)(
            inngest.Event(
                name="campaign/contact.dial",
                data={
                    "campaign_id": contact.campaign_id,
                    "contact_id": contact.id,
                    "user_id": request.user.id,
                    "concurrency_limit": limit
                }
            )
        )
        return JsonResponse({
            "status": "success",
            "message": f"تم توجيه أمر الاتصال بالعميل '{contact.customer_name}' ({contact.phone_number})."
        })
    except Exception as e:
        logger.exception("Error manually dialing contact")
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@login_required(login_url='/login/')
def api_export_campaign_contacts(request, campaign_id):
    """
    Exports campaign leads with AI classification, call summary, duration, and metadata
    to a beautifully formatted Excel (.xlsx) or CSV file.
    Supports filtering (all, hot_warm, hot).
    """
    campaign = get_object_or_404(OutboundCampaign, id=campaign_id, user=request.user)
    filter_mode = request.GET.get('filter', 'all').strip().lower()
    export_format = request.GET.get('format', 'xlsx').strip().lower()

    contacts_qs = campaign.contacts.all()
    if filter_mode == 'hot':
        contacts_qs = contacts_qs.filter(interest_level='hot')
    elif filter_mode == 'hot_warm':
        contacts_qs = contacts_qs.filter(interest_level__in=['hot', 'warm'])
    elif filter_mode == 'answered':
        contacts_qs = contacts_qs.filter(call_status='answered')

    # Determine all unique attribute keys
    extra_keys = []
    for c in contacts_qs[:200]:
        if c.attributes and isinstance(c.attributes, dict):
            for k in c.attributes.keys():
                if k not in extra_keys:
                    extra_keys.append(k)

    timestamp_str = datetime.now().strftime('%Y%m%d_%H%M')
    clean_campaign_name = "".join(x for x in campaign.name if x.isalnum() or x in [' ', '_', '-']).strip().replace(' ', '_')
    filename = f"leads_{clean_campaign_name}_{filter_mode}_{timestamp_str}"

    if export_format == 'csv':
        response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
        response['Content-Disposition'] = f'attachment; filename="{filename}.csv"'

        # Write UTF-8 BOM so Excel opens Arabic correctly
        response.write('\ufeff')
        writer = csv.writer(response)

        headers = [
            "اسم العميل", "رقم الهاتف", "حالة الاتصال", "تصنيف الاهتمام",
            "ملخص المكالمة", "استخلاصات الذكاء الاصطناعي", "الإجراء المطلوب",
            "مدة المكالمة (ثواني)", "عدد المحاولات", "تاريخ آخر اتصال"
        ] + extra_keys
        writer.writerow(headers)

        for c in contacts_qs:
            ext_data = c.extracted_data or {}
            key_ans = ext_data.get("key_answers") or ext_data.get("customer_intent") or ""
            act_req = ext_data.get("action_required") or ""
            row = [
                c.customer_name,
                c.phone_number,
                c.get_call_status_display(),
                c.get_interest_level_display(),
                c.call_summary,
                key_ans,
                act_req,
                c.duration_seconds,
                c.retries_count,
                c.last_attempt_at.strftime('%Y-%m-%d %H:%M') if c.last_attempt_at else "لم يتم بعد"
            ] + [str(c.attributes.get(k, '') if isinstance(c.attributes, dict) else '') for k in extra_keys]
            writer.writerow(row)

        return response

    else:
        # Default to Excel XLSX
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "نتائج الحملة والعملاء"
        ws.views.sheetView[0].rightToLeft = True  # Arabic RTL Excel layout!

        # Define Styles
        header_fill = PatternFill(start_color="680E23", end_color="680E23", fill_type="solid")
        header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
        regular_font = Font(name="Segoe UI", size=10)
        bold_font = Font(name="Segoe UI", size=10, bold=True)

        thin_border = Border(
            left=Side(style='thin', color='E0E0E0'),
            right=Side(style='thin', color='E0E0E0'),
            top=Side(style='thin', color='E0E0E0'),
            bottom=Side(style='thin', color='E0E0E0')
        )

        headers = [
            "اسم العميل", "رقم الهاتف", "حالة الاتصال", "تصنيف الاهتمام (AI)",
            "ملخص المكالمة", "استخلاصات الذكاء الاصطناعي", "الإجراء المطلوب",
            "مدة المكالمة (ثانية)", "عدد المحاولات", "تاريخ الاتصال"
        ] + extra_keys

        ws.append(headers)

        for col_num in range(1, len(headers) + 1):
            cell = ws.cell(row=1, column=col_num)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

        # Interest Color Fills
        hot_fill = PatternFill(start_color="FDE8E8", end_color="FDE8E8", fill_type="solid")      # Light Red/Hot
        warm_fill = PatternFill(start_color="FEF3C7", end_color="FEF3C7", fill_type="solid")     # Light Amber/Warm
        cold_fill = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")     # Slate/Cold

        row_idx = 2
        for c in contacts_qs:
            ext_data = c.extracted_data or {}
            key_ans = ext_data.get("key_answers") or ext_data.get("customer_intent") or ""
            act_req = ext_data.get("action_required") or ""
            row_data = [
                c.customer_name,
                c.phone_number,
                c.get_call_status_display(),
                c.get_interest_level_display(),
                c.call_summary,
                key_ans,
                act_req,
                c.duration_seconds,
                c.retries_count,
                c.last_attempt_at.strftime('%Y-%m-%d %H:%M') if c.last_attempt_at else "لم يتم بعد"
            ] + [str(c.attributes.get(k, '') if isinstance(c.attributes, dict) else '') for k in extra_keys]

            ws.append(row_data)

            # Style the row
            for col_idx, val in enumerate(row_data, start=1):
                cell = ws.cell(row=row_idx, column=col_idx)
                cell.font = regular_font
                cell.border = thin_border
                cell.alignment = Alignment(vertical="center")

                # Highlight interest column
                if col_idx == 4:
                    if c.interest_level == 'hot':
                        cell.fill = hot_fill
                        cell.font = bold_font
                    elif c.interest_level == 'warm':
                        cell.fill = warm_fill
                        cell.font = bold_font
                    elif c.interest_level == 'cold':
                        cell.fill = cold_fill

            row_idx += 1

        # Auto-adjust column widths
        for col in ws.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = max(12, min(max_len + 4, 50))

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

        response = HttpResponse(
            output.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}.xlsx"'
        return response
