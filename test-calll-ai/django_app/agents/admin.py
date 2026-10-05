from django.contrib import admin
from .models import AgentProfile, UserMCPServer, SystemSetting, AgentToolCallLog, TenantLiveContext

@admin.register(SystemSetting)
class SystemSettingAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'masked_api_key', 'updated_at')
    readonly_fields = ('updated_at',)

    def masked_api_key(self, obj):
        key = (obj.gemini_api_key or "").strip()
        if len(key) > 8:
            return f"{key[:4]}...{key[-4:]}"
        return "غير محدد" if not key else "******"
    masked_api_key.short_description = "Google Gemini API Key"

    def has_add_permission(self, request):
        return not SystemSetting.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(AgentProfile)
class AgentProfileAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'user', 'voice_name', 'gender', 'dialect', 'persona_role', 'speaking_style', 'is_active', 'updated_at')
    list_filter = ('is_active', 'gender', 'dialect', 'persona_role', 'user')
    search_fields = ('name', 'custom_instructions', 'user__username')
    readonly_fields = ('created_at', 'updated_at')

from django.urls import path, reverse
from django.http import HttpResponseRedirect
from django.contrib import messages
from django.utils import timezone
from .mcp_service import test_mcp_connection_sync

@admin.register(UserMCPServer)
class UserMCPServerAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'user', 'server_url', 'is_active', 'tools_count', 'last_synced_at', 'connection_test_badge')
    list_filter = ('is_active', 'user')
    search_fields = ('name', 'server_url', 'user__username')
    readonly_fields = ('created_at', 'updated_at', 'last_synced_at', 'test_connection_action', 'tools_preview')
    actions = ['test_selected_servers', 'activate_selected_servers', 'deactivate_selected_servers']

    def tools_count(self, obj):
        tools = obj.cached_tools
        if isinstance(tools, list):
            return len(tools)
        return 0
    tools_count.short_description = "الأدوات المتوفرة"

    def connection_test_badge(self, obj):
        test_url = reverse('admin:agents_usermcpserver_test', args=[obj.id])
        return format_html(
            '<a class="button" style="padding:4px 10px; font-size:11px; font-weight:600; background:#FAF0F2; color:#680E23; border:1px solid #E8CCD2; border-radius:8px; text-decoration:none; display:inline-flex; align-items:center; gap:4px;" href="{}" title="اختبار الاتصال بالخادم وتحديث أدواته فوراً">'
            '<span>🔌</span> <span>فحص الآن</span>'
            '</a>',
            test_url
        )
    connection_test_badge.short_description = "فحص حي"

    def test_connection_action(self, obj):
        if not obj or not obj.id:
            return "احفظ الخادم أولاً لإجراء الفحص من لوحة التحكم، أو استخدم الفحص المباشر في صفحة المتجر."
        test_url = reverse('admin:agents_usermcpserver_test', args=[obj.id])
        return format_html(
            '<div style="margin: 6px 0;">'
            '<a class="button" style="background:#680E23; color:#fff; font-weight:bold; padding:9px 18px; border-radius:10px; text-decoration:none; display:inline-flex; align-items:center; gap:8px; box-shadow: 0 2px 8px rgba(104,14,35,0.25);" href="{}">'
            '<span>🔌</span> <span>فحص الاتصال وتحديث الأدوات الحية الآن (Live Test & Sync)</span>'
            '</a>'
            '<p style="margin: 6px 0 0 0; font-size:11px; color:#6E645D;">يقوم هذا الإجراء بالاتصال الفوري بنقطة نهاية SSE للخادم، وقياس سرعة الاستجابة، وتحديث قائمة الأدوات تلقائياً.</p>'
            '</div>',
            test_url
        )
    test_connection_action.short_description = "إجراء الفحص المباشر"

    def tools_preview(self, obj):
        if not obj or not obj.id:
            return "احفظ الخادم أولاً لإظهار جدول الأدوات وإمكانية اختبارها."
        tools = obj.cached_tools or []
        if not tools:
            return mark_safe(
                "<div style='padding:14px; background:#FAF7F2; border:1px dashed #DDD5C7; border-radius:12px; color:#6E645D; font-size:12px;'>"
                "لا توجد أدوات مكتشفة حتى الآن. اضغط على زر <strong>'فحص الاتصال وتحديث الأدوات الحية الآن'</strong> أعلاه لقراءة دوال الخادم."
                "</div>"
            )

        tools_json = json.dumps(tools)

        rows = []
        for idx, t in enumerate(tools, start=1):
            name = t.get('name', 'بدون اسم')
            desc = t.get('description', '') or 'بدون وصف توضيحي'
            params = t.get('parameters', {})
            props = params.get('properties', {}) if isinstance(params, dict) else {}
            required = params.get('required', []) if isinstance(params, dict) else []

            param_badges = []
            if props and isinstance(props, dict):
                for p_name in props.keys():
                    is_req = p_name in required
                    if is_req:
                        param_badges.append(
                            f'<span style="background:#FAF0F2; color:#680E23; border:1px solid #E8CCD2; padding:2px 7px; border-radius:5px; font-size:10px; font-weight:bold; margin:2px;" title="حقل إلزامي">{p_name}*</span>'
                        )
                    else:
                        param_badges.append(
                            f'<span style="background:#F5EFE6; color:#6E645D; border:1px solid #DDD5C7; padding:2px 7px; border-radius:5px; font-size:10px; margin:2px;">{p_name}</span>'
                        )
            params_html = "".join(param_badges) if param_badges else '<span style="color:#8C827A; font-size:11px;">بدون معاملات</span>'

            test_res = t.get('test_result', {})
            st = test_res.get('status')
            if st == 'success':
                exec_time = test_res.get('execution_time_ms', 0)
                tested_at = test_res.get('tested_at', '')
                status_html = (
                    f'<span id="status-badge-{idx}" style="background:#ECFDF5; color:#065F46; border:1px solid #A7F3D0; padding:3px 9px; border-radius:6px; font-weight:bold; font-size:11px; display:inline-flex; align-items:center; gap:4px;" title="آخر فحص: {tested_at}">'
                    f'<span>🟢 يعمل</span> <small style="color:#047857; font-family:monospace;">({exec_time}ms)</small>'
                    f'</span>'
                )
            elif st == 'error':
                err_type = test_res.get('error_type', 'error')
                err_msg = test_res.get('error_message', '')[:60]
                status_html = (
                    f'<span id="status-badge-{idx}" style="background:#FEF2F2; color:#991B1B; border:1px solid #FECACA; padding:3px 9px; border-radius:6px; font-weight:bold; font-size:11px; display:inline-flex; align-items:center; gap:4px;" title="{err_msg}">'
                    f'<span>🔴 فشل</span> <small style="color:#B91C1C;">({err_type})</small>'
                    f'</span>'
                )
            else:
                status_html = (
                    f'<span id="status-badge-{idx}" style="background:#F5EFE6; color:#6E645D; border:1px solid #DDD5C7; padding:3px 9px; border-radius:6px; font-weight:600; font-size:11px; display:inline-flex; align-items:center; gap:4px;">'
                    f'<span>⚪ لم يُختبر</span>'
                    f'</span>'
                )

            rows.append(f"""
            <tr style="border-bottom:1px solid #EAE3D9; transition:background 0.2s;" onmouseover="this.style.background='#FAF7F2'" onmouseout="this.style.background='#fff'">
              <td style="padding:10px 8px; text-align:center; color:#8C827A; font-weight:bold;">{idx}</td>
              <td style="padding:10px 12px; font-family:monospace; font-weight:bold; color:#680E23; font-size:12px;">{name}</td>
              <td style="padding:10px 12px; color:#443D39; line-height:1.4;">{desc}</td>
              <td style="padding:10px 12px; display:flex; flex-wrap:wrap; gap:3px;">{params_html}</td>
              <td style="padding:10px 12px; text-align:center;">{status_html}</td>
              <td style="padding:10px 12px; text-align:center;">
                <button type="button" onclick="adminOpenTestToolModal({obj.id}, '{name}', {idx})" style="background:#680E23; color:#fff; border:none; padding:6px 14px; border-radius:8px; font-size:11px; font-weight:bold; cursor:pointer; display:inline-flex; align-items:center; gap:4px; box-shadow:0 1px 3px rgba(104,14,35,0.25);" onmouseover="this.style.background='#7E152F'" onmouseout="this.style.background='#680E23'">
                  <span>⚡</span> <span>اختبار الأداة</span>
                </button>
              </td>
            </tr>
            """)

        rows_html = "".join(rows)

        html = f"""
        <script id="mcp-admin-tools-data" type="application/json">{tools_json}</script>
        <div style="overflow-x:auto; margin-top:8px; border-radius:14px; border:1px solid #EAE3D9; box-shadow:0 2px 10px rgba(0,0,0,0.02);">
          <table id="mcp-admin-tools-table" style="width:100%; border-collapse:collapse; background:#fff; font-size:12px; text-align:right;">
            <thead>
              <tr style="background:#FAF7F2; border-bottom:2px solid #EAE3D9; color:#443D39;">
                <th style="padding:12px 10px; width:35px; text-align:center;">#</th>
                <th style="padding:12px 12px; width:210px;">اسم الأداة</th>
                <th style="padding:12px 12px;">الوصف والغرض</th>
                <th style="padding:12px 12px; width:220px;">المعاملات المطلوبة</th>
                <th style="padding:12px 12px; width:160px; text-align:center;">حالة الفحص</th>
                <th style="padding:12px 12px; width:130px; text-align:center;">إجراء</th>
              </tr>
            </thead>
            <tbody>
              {rows_html}
            </tbody>
          </table>
        </div>

        <!-- Testing Modal -->
        <div id="admin-tool-modal-overlay" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(28,25,23,0.6); backdrop-filter:blur(3px); z-index:99999; align-items:center; justify-content:center; padding:15px; direction:rtl; box-sizing:border-box;">
          <div style="background:#fff; border-radius:20px; width:100%; max-width:620px; box-shadow:0 25px 50px rgba(0,0,0,0.25); overflow:hidden; font-family:inherit; border:1px solid #EAE3D9;">
            <div style="background:#FAF7F2; padding:16px 22px; border-bottom:1px solid #EAE3D9; display:flex; justify-content:space-between; align-items:center;">
              <h3 style="margin:0; font-size:15px; color:#1C1917; font-weight:bold; display:flex; align-items:center; gap:8px;">
                <span>⚡</span> <span>اختبار الأداة حياً:</span> <code id="admin-modal-tool-name" style="color:#680E23; font-size:14px; font-family:monospace;"></code>
              </h3>
              <button type="button" onclick="adminCloseTestToolModal()" style="background:none; border:none; font-size:24px; color:#8C827A; cursor:pointer; line-height:1;">&times;</button>
            </div>

            <div style="padding:22px; max-height:75vh; overflow-y:auto; font-size:12px; box-sizing:border-box;">
              <div style="margin-bottom:14px;">
                <label style="font-weight:bold; color:#443D39; display:block; margin-bottom:4px;">وصف الأداة:</label>
                <p id="admin-modal-tool-desc" style="margin:0; color:#1C1917; line-height:1.5; background:#FAF7F2; padding:10px 14px; border-radius:10px; border:1px solid #DDD5C7;"></p>
              </div>

              <div style="margin-bottom:14px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                  <label style="font-weight:bold; color:#1C1917;">مُدخلات الاختبار (JSON Arguments):</label>
                  <button type="button" onclick="adminFillSampleArgs()" style="background:none; border:none; color:#680E23; font-weight:bold; font-size:11px; cursor:pointer; text-decoration:underline;">🪄 ملء تلقائي للبيانات</button>
                </div>
                <textarea id="admin-modal-args" rows="4" style="width:100%; padding:10px; border:1px solid #DDD5C7; border-radius:10px; font-family:monospace; font-size:12px; box-sizing:border-box; outline:none; background:#FAF7F2; color:#1C1917;" placeholder="{{}}"></textarea>
              </div>

              <div style="display:flex; justify-content:flex-end; gap:8px; margin-bottom:16px;">
                <button type="button" onclick="adminCloseTestToolModal()" style="padding:8px 16px; border:1px solid #DDD5C7; border-radius:10px; background:#F5EFE6; color:#443D39; font-weight:bold; cursor:pointer;">إلغاء</button>
                <button type="button" id="btn-admin-modal-run" onclick="adminExecuteToolTest()" style="padding:8px 20px; border:none; border-radius:10px; background:#680E23; color:#fff; font-weight:bold; cursor:pointer; display:inline-flex; align-items:center; gap:6px; box-shadow:0 2px 6px rgba(104,14,35,0.2);">
                  <span>⚡</span> <span id="btn-admin-modal-run-text">تنفيذ الاستدعاء الحَي</span>
                </button>
              </div>

              <!-- Execution Result -->
              <div id="admin-modal-res-container" style="display:none; border-top:1px solid #EAE3D9; padding-top:14px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                  <strong style="color:#1C1917;">نتيجة الاستجابة من الخادم:</strong>
                  <span id="admin-modal-res-badge" style="padding:3px 10px; border-radius:6px; font-weight:bold; font-size:11px; font-family:monospace;"></span>
                </div>
                <pre id="admin-modal-res-output" style="background:#FAF7F2; border:1px solid #DDD5C7; padding:12px; border-radius:10px; font-size:11px; font-family:monospace; max-height:180px; overflow-y:auto; white-space:pre-wrap; word-break:break-all; margin:0; line-height:1.5; color:#1C1917;"></pre>
              </div>
            </div>
          </div>
        </div>

        <script>
        (function() {{
          var currentServerId = null;
          var currentToolName = null;
          var currentToolIdx = null;
          var currentTools = [];

          try {{
            var el = document.getElementById('mcp-admin-tools-data');
            if (el) {{
              currentTools = JSON.parse(el.textContent || '[]');
            }}
          }} catch(e) {{}}

          window.adminOpenTestToolModal = function(serverId, toolName, idx) {{
            currentServerId = serverId;
            currentToolName = toolName;
            currentToolIdx = idx;

            var modal = document.getElementById('admin-tool-modal-overlay');
            var nameEl = document.getElementById('admin-modal-tool-name');
            var descEl = document.getElementById('admin-modal-tool-desc');
            var resContainer = document.getElementById('admin-modal-res-container');

            if (resContainer) resContainer.style.display = 'none';
            if (nameEl) nameEl.innerText = toolName;

            var tool = currentTools[idx - 1] || {{}};
            if (descEl) descEl.innerText = tool.description || 'بدون وصف توضيحي';

            window.adminFillSampleArgs();

            if (modal) {{
              modal.style.display = 'flex';
            }}
          }};

          window.adminCloseTestToolModal = function() {{
            var modal = document.getElementById('admin-tool-modal-overlay');
            if (modal) modal.style.display = 'none';
          }};

          window.adminFillSampleArgs = function() {{
            var argsEl = document.getElementById('admin-modal-args');
            if (!argsEl || currentToolIdx === null) return;
            var tool = currentTools[currentToolIdx - 1] || {{}};
            var schema = tool.parameters || {{}};
            var props = schema.properties || {{}};
            var required = schema.required || [];

            var sample = {{}};
            for (var k in props) {{
              var prop = props[k] || {{}};
              var pType = (prop.type || 'string').toLowerCase();
              if (pType === 'string') {{
                sample[k] = prop.default !== undefined ? prop.default : (required.indexOf(k) !== -1 ? "قيمة تجريبية" : "");
              }} else if (pType === 'integer' || pType === 'number') {{
                sample[k] = prop.default !== undefined ? prop.default : 1;
              }} else if (pType === 'boolean') {{
                sample[k] = prop.default !== undefined ? prop.default : true;
              }} else if (pType === 'array') {{
                sample[k] = [];
              }} else if (pType === 'object') {{
                sample[k] = {{}};
              }} else {{
                sample[k] = "";
              }}
            }}
            argsEl.value = JSON.stringify(sample, null, 2);
          }};

          window.adminExecuteToolTest = function() {{
            var argsEl = document.getElementById('admin-modal-args');
            var btn = document.getElementById('btn-admin-modal-run');
            var btnText = document.getElementById('btn-admin-modal-run-text');
            var resContainer = document.getElementById('admin-modal-res-container');
            var badge = document.getElementById('admin-modal-res-badge');
            var output = document.getElementById('admin-modal-res-output');

            var argsVal = {{}};
            if (argsEl && argsEl.value.trim()) {{
              try {{
                argsVal = JSON.parse(argsEl.value.trim());
              }} catch(e) {{
                alert('صيغة المُدخلات غير صالحة. يرجى التأكد من كتابة JSON صالح.');
                return;
              }}
            }}

            if (btn) btn.disabled = true;
            if (btnText) btnText.innerText = 'جاري التنفيذ...';
            if (resContainer) resContainer.style.display = 'block';
            if (badge) {{
              badge.innerText = '⏳ جاري الاستدعاء...';
              badge.style.background = '#FAF7F2';
              badge.style.color = '#443D39';
              badge.style.border = '1px solid #DDD5C7';
            }}
            if (output) output.innerText = 'جاري انتظار استجابة خادم MCP...';

            function getCookie(name) {{
              var value = "; " + document.cookie;
              var parts = value.split("; " + name + "=");
              if (parts.length == 2) return parts.pop().split(";").shift();
              return "";
            }}

            fetch('/api/agents/mcp/test-tool/', {{
              method: 'POST',
              headers: {{
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
              }},
              body: JSON.stringify({{
                id: currentServerId,
                tool_name: currentToolName,
                arguments: argsVal
              }})
            }})
            .then(function(res) {{ return res.json(); }})
            .then(function(data) {{
              if (data.ok) {{
                if (badge) {{
                  badge.innerText = '✅ ناجح (' + data.execution_time_ms + ' ms)';
                  badge.style.background = '#ECFDF5';
                  badge.style.color = '#065F46';
                  badge.style.border = '1px solid #A7F3D0';
                }}
                if (output) output.innerText = data.result || 'تم التنفيذ بنجاح بدون نص مخرجات.';

                var rowBadge = document.getElementById('status-badge-' + currentToolIdx);
                if (rowBadge) {{
                  rowBadge.innerHTML = '<span>🟢 يعمل</span> <small style="color:#047857; font-family:monospace;">(' + data.execution_time_ms + 'ms)</small>';
                  rowBadge.style.background = '#ECFDF5';
                  rowBadge.style.color = '#065F46';
                  rowBadge.style.border = '1px solid #A7F3D0';
                }}
              }} else {{
                var errType = data.error_type || 'error';
                var errMsg = data.error_message || data.result || 'فشل استدعاء الأداة';
                if (badge) {{
                  badge.innerText = '❌ فشل (' + errType + ')';
                  badge.style.background = '#FEF2F2';
                  badge.style.color = '#991B1B';
                  badge.style.border = '1px solid #FECACA';
                }}
                if (output) output.innerText = errMsg;

                var rowBadge = document.getElementById('status-badge-' + currentToolIdx);
                if (rowBadge) {{
                  rowBadge.innerHTML = '<span>🔴 فشل</span> <small style="color:#B91C1C;">(' + errType + ')</small>';
                  rowBadge.style.background = '#FEF2F2';
                  rowBadge.style.color = '#991B1B';
                  rowBadge.style.border = '1px solid #FECACA';
                  rowBadge.title = errMsg;
                }}
              }}
            }})
            .catch(function(err) {{
              if (badge) {{
                badge.innerText = '❌ خطأ شبكة';
                badge.style.background = '#FEF2F2';
                badge.style.color = '#991B1B';
                badge.style.border = '1px solid #FECACA';
              }}
              if (output) output.innerText = 'حدث خطأ أثناء إرسال الطلب: ' + (err.message || '');
            }})
            .finally(function() {{
              if (btn) btn.disabled = false;
              if (btnText) btnText.innerText = 'تنفيذ الاستدعاء الحَي';
            }});
          }};
        }})();
        </script>
        """
        return mark_safe(html)
    tools_preview.short_description = "معاينة واختبار الأدوات المكتشفة"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('<int:object_id>/test/', self.admin_site.admin_view(self.test_single_server_view), name='agents_usermcpserver_test'),
        ]
        return custom_urls + urls

    def test_single_server_view(self, request, object_id):
        from django.shortcuts import get_object_or_404
        obj = get_object_or_404(UserMCPServer, pk=object_id)
        res = test_mcp_connection_sync(obj.server_url, obj.auth_token, timeout=6.0)
        if res.get("ok"):
            obj.cached_tools = res.get("tools", [])
            obj.last_synced_at = timezone.now()
            obj.save(update_fields=['cached_tools', 'last_synced_at'])
            self.message_user(
                request,
                format_html(
                    "✅ <strong>نجح الاتصال بخادم '{}':</strong> تم فحص البروتوكول في {}ms واكتشاف {} أداة متاحة.",
                    obj.name, res.get('latency_ms'), res.get('tools_count')
                ),
                level=messages.SUCCESS
            )
        else:
            self.message_user(
                request,
                format_html(
                    "❌ <strong>فشل الاتصال بخادم '{}':</strong> {} (النوع: {})",
                    obj.name, res.get('error_message'), res.get('error_type')
                ),
                level=messages.ERROR
            )
        return HttpResponseRedirect(reverse('admin:agents_usermcpserver_change', args=[object_id]))

    def test_selected_servers(self, request, queryset):
        success_count = 0
        fail_count = 0
        details = []

        for server in queryset:
            res = test_mcp_connection_sync(server.server_url, server.auth_token, timeout=6.0)
            if res.get("ok"):
                server.cached_tools = res.get("tools", [])
                server.last_synced_at = timezone.now()
                server.save(update_fields=['cached_tools', 'last_synced_at'])
                success_count += 1
                details.append(f"🟢 {server.name}: متصل ({res.get('latency_ms')}ms, {res.get('tools_count')} أداة)")
            else:
                fail_count += 1
                details.append(f"🔴 {server.name}: تعذر الاتصال ({res.get('error_type')})")

        msg = f"تم فحص {queryset.count()} خادم. الناجحة: {success_count}، الفاشلة: {fail_count}."
        if details:
            msg += "<br>" + "<br>".join(details)

        level = messages.SUCCESS if fail_count == 0 else (messages.WARNING if success_count > 0 else messages.ERROR)
        self.message_user(request, format_html(msg), level=level)
    test_selected_servers.short_description = "🔌 فحص واختبار اتصال الخوادم المحددة (Test Connection & Tools)"

    def activate_selected_servers(self, request, queryset):
        cnt = queryset.update(is_active=True)
        self.message_user(request, f"تم تفعيل {cnt} خادم MCP بنجاح للمكالمات الصوتية.", level=messages.SUCCESS)
    activate_selected_servers.short_description = "تفعيل الخوادم المحددة للمكالمات"

    def deactivate_selected_servers(self, request, queryset):
        cnt = queryset.update(is_active=False)
        self.message_user(request, f"تم تعطيل {cnt} خادم MCP.", level=messages.INFO)
    deactivate_selected_servers.short_description = "تعطيل الخوادم المحددة"


import json
from django.utils.html import format_html, mark_safe
from django.db.models import Avg, Count
from .models import AgentToolCallLog


@admin.register(AgentToolCallLog)
class AgentToolCallLogAdmin(admin.ModelAdmin):
    change_list_template = "admin/agents/agenttoolcalllog/change_list.html"
    list_display = (
        'id',
        'status_badge',
        'tool_badge',
        'user',
        'caller_display',
        'execution_time_badge',
        'short_error_message',
        'created_at_formatted'
    )
    list_filter = ('status', 'tool_type', 'tool_name', 'created_at', 'user')
    search_fields = (
        'tool_name',
        'room_name',
        'caller_phone',
        'error_message',
        'server_name',
        'user__username'
    )
    date_hierarchy = 'created_at'
    list_per_page = 30

    readonly_fields = (
        'id',
        'user',
        'call_session',
        'room_name',
        'caller_phone',
        'tool_name',
        'tool_type',
        'server_name',
        'server_url',
        'status',
        'error_type',
        'error_message',
        'execution_time_ms',
        'formatted_arguments',
        'response_preview',
        'formatted_raw_response',
        'created_at'
    )

    fieldsets = (
        ('معلومات الاستدعاء والحالة', {
            'fields': (
                ('status', 'error_type'),
                ('tool_name', 'tool_type'),
                ('user', 'caller_phone'),
                ('room_name', 'call_session'),
                ('server_name', 'server_url'),
                ('execution_time_ms', 'created_at'),
            )
        }),
        ('تفاصيل الخطأ (إن وُجد)', {
            'fields': ('error_message',),
        }),
        ('المدخلات والردود البرمجية', {
            'fields': ('formatted_arguments', 'response_preview', 'formatted_raw_response')
        }),
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return True

    def changelist_view(self, request, extra_context=None):
        # Calculate high-level KPIs for superadmin banner
        qs = self.get_queryset(request)
        total_count = qs.count()
        success_count = qs.filter(status='success').count()
        failed_count = qs.exclude(status='success').count()
        success_rate = round((success_count / total_count * 100), 1) if total_count > 0 else 0
        avg_ms = qs.aggregate(avg=Avg('execution_time_ms'))['avg'] or 0

        # Most failing tool
        failing_tool = (
            qs.exclude(status='success')
            .values('tool_name')
            .annotate(cnt=Count('id'))
            .order_by('-cnt')
            .first()
        )
        failing_tool_name = failing_tool['tool_name'] if failing_tool else "لا توجد أخطاء"
        failing_tool_count = failing_tool['cnt'] if failing_tool else 0

        kpi_html = f"""
        <div style="display:flex;gap:16px;margin-bottom:20px;flex-wrap:wrap;font-family:sans-serif;">
            <div style="flex:1;min-width:180px;background:#ffffff;border:1px solid #e5e7eb;border-radius:10px;padding:14px 18px;box-shadow:0 1px 3px rgba(0,0,0,0.05);border-top:4px solid #3b82f6;">
                <div style="font-size:12px;color:#6b7280;font-weight:600;margin-bottom:4px;">إجمالي الاستدعاءات</div>
                <div style="font-size:24px;font-weight:700;color:#111827;">{total_count:,}</div>
                <div style="font-size:11px;color:#9ca3af;margin-top:2px;">كافة الأدوات المسجلة</div>
            </div>
            <div style="flex:1;min-width:180px;background:#ffffff;border:1px solid #e5e7eb;border-radius:10px;padding:14px 18px;box-shadow:0 1px 3px rgba(0,0,0,0.05);border-top:4px solid #10b981;">
                <div style="font-size:12px;color:#047857;font-weight:600;margin-bottom:4px;">الاستدعاءات الناجحة</div>
                <div style="font-size:24px;font-weight:700;color:#065f46;">{success_count:,} <span style="font-size:14px;font-weight:600;color:#10b981;">({success_rate}%)</span></div>
                <div style="font-size:11px;color:#059669;margin-top:2px;">معدل النجاح الإجمالي</div>
            </div>
            <div style="flex:1;min-width:180px;background:#ffffff;border:1px solid #e5e7eb;border-radius:10px;padding:14px 18px;box-shadow:0 1px 3px rgba(0,0,0,0.05);border-top:4px solid #ef4444;">
                <div style="font-size:12px;color:#b91c1c;font-weight:600;margin-bottom:4px;">الاستدعاءات الفاشلة</div>
                <div style="font-size:24px;font-weight:700;color:#991b1b;">{failed_count:,}</div>
                <div style="font-size:11px;color:#dc2626;margin-top:2px;">أكثر أداة بها أخطاء: {failing_tool_name} ({failing_tool_count})</div>
            </div>
            <div style="flex:1;min-width:180px;background:#ffffff;border:1px solid #e5e7eb;border-radius:10px;padding:14px 18px;box-shadow:0 1px 3px rgba(0,0,0,0.05);border-top:4px solid #8b5cf6;">
                <div style="font-size:12px;color:#6d28d9;font-weight:600;margin-bottom:4px;">متوسط سرعة الاستجابة</div>
                <div style="font-size:24px;font-weight:700;color:#5b21b6;">{int(avg_ms)} <span style="font-size:13px;font-weight:500;">ms</span></div>
                <div style="font-size:11px;color:#7c3aed;margin-top:2px;">زمن المعالجة الفعلي</div>
            </div>
        </div>
        """

        extra_context = extra_context or {}
        extra_context['kpi_banner'] = mark_safe(kpi_html)
        return super().changelist_view(request, extra_context=extra_context)

    def status_badge(self, obj):
        colors = {
            'success': ('#def7ec', '#03543f', '✓ ناجح'),
            'failed': ('#fde8e8', '#9b1c1c', '✕ فشل أداة'),
            'timeout': ('#fef08a', '#713f12', '⏱ انتهاء مهلة'),
            'connection_error': ('#f3e8ff', '#6b21a8', '⚡ فشل اتصال'),
            'validation_error': ('#ffedd5', '#9a3412', '⚠ خطأ مدخلات'),
        }
        bg, text_color, label = colors.get(obj.status, ('#f3f4f6', '#374151', obj.status))
        return format_html(
            '<span style="background:{};color:{};font-weight:600;padding:3px 9px;border-radius:12px;font-size:11px;display:inline-block;white-space:nowrap;">{}</span>',
            bg, text_color, label
        )
    status_badge.short_description = "الحالة"

    def tool_badge(self, obj):
        type_colors = {
            'mcp': ('#e1effe', '#1e429f', 'FastMCP'),
            'rag': ('#fef9c3', '#854d0e', 'RAG'),
            'memory': ('#dcfce7', '#166534', 'ذاكرة CRM'),
            'transfer': ('#e0e7ff', '#3730a3', 'تحويل طابور'),
        }
        bg, text_color, type_label = type_colors.get(obj.tool_type, ('#f3f4f6', '#374151', obj.tool_type))
        return format_html(
            '<div style="font-weight:700;font-size:12px;color:#111827;">{}</div>'
            '<span style="background:{};color:{};font-size:10px;font-weight:600;padding:1px 6px;border-radius:6px;display:inline-block;margin-top:2px;">{}</span>',
            obj.tool_name, bg, text_color, type_label
        )
    tool_badge.short_description = "الأداة والنوع"

    def caller_display(self, obj):
        phone = obj.caller_phone or "لوحة التحكم"
        return format_html(
            '<div style="font-size:12px;font-weight:600;color:#1f2937;">{}</div>'
            '<div style="font-size:10px;color:#6b7280;font-family:monospace;">{}</div>',
            phone, obj.room_name[:22]
        )
    caller_display.short_description = "المتصل / الغرفة"

    def execution_time_badge(self, obj):
        ms = obj.execution_time_ms
        if ms < 500:
            color = "#057a55"
        elif ms < 1500:
            color = "#d97706"
        else:
            color = "#e02424"
        return format_html('<span style="color:{};font-weight:700;font-size:11px;">{} ms</span>', color, ms)
    execution_time_badge.short_description = "زمن التنفيذ"

    def short_error_message(self, obj):
        if not obj.error_message:
            return format_html('<span style="color:#9ca3af;font-size:11px;">—</span>')
        return format_html(
            '<div style="max-width:240px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:11px;color:#b91c1c;" title="{}">{}</div>',
            obj.error_message, obj.error_message[:45] + ("..." if len(obj.error_message) > 45 else "")
        )
    short_error_message.short_description = "سبب الخطأ"

    def created_at_formatted(self, obj):
        return obj.created_at.strftime("%Y-%m-%d %H:%M:%S")
    created_at_formatted.short_description = "التوقيت"

    def formatted_arguments(self, obj):
        content = json.dumps(obj.arguments or {}, ensure_ascii=False, indent=2)
        return format_html('<pre style="background:#1e293b;color:#f8fafc;padding:12px;border-radius:8px;font-size:12px;max-height:300px;overflow:auto;">{}</pre>', content)
    formatted_arguments.short_description = "المدخلات (JSON)"

    def formatted_raw_response(self, obj):
        raw = obj.raw_response
        if isinstance(raw, (dict, list)):
            content = json.dumps(raw, ensure_ascii=False, indent=2)
        else:
            content = str(raw or "")
        return format_html('<pre style="background:#0f172a;color:#38bdf8;padding:12px;border-radius:8px;font-size:12px;max-height:400px;overflow:auto;">{}</pre>', content)
    formatted_raw_response.short_description = "الرد الكامل (JSON/Raw)"


@admin.register(TenantLiveContext)
class TenantLiveContextAdmin(admin.ModelAdmin):
    list_display = ('user', 'size_badge', 'redis_status_badge', 'updated_at_formatted', 'created_at_formatted')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('size_badge', 'redis_status_badge', 'created_at', 'updated_at', 'compiled_prompt_preview')
    actions = ['sync_to_redis_action', 'clear_from_redis_action']

    fieldsets = (
        ("بيانات العميل والحالة", {
            'fields': ('user', ('size_badge', 'redis_status_badge'), ('created_at', 'updated_at'))
        }),
        ("البيانات المنظمة اللحظية (Structured JSON)", {
            'fields': ('data',),
            'description': "أدخل البيانات بصيغة JSON نظيفة (مثل فروع المطعم، المنيو، مناطق ورسوم التوصيل، والأصناف غير المتاحة)."
        }),
        ("معاينة توجيهات الذكاء الاصطناعي (Prompt Preview)", {
            'fields': ('compiled_prompt_preview',),
            'description': "كيف يتم ترجمة وتحويل هذا الـ JSON إلى توجيهات فورية لنموذج Gemini Live أثناء المكالمة."
        }),
    )

    def size_badge(self, obj):
        kb = round(obj.size_bytes / 1024, 2)
        color = "#057a55" if obj.size_bytes < 50 * 1024 else "#d97706"
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:12px;font-weight:bold;font-size:11px;">{} KB ({} بايت)</span>',
            color, kb, obj.size_bytes
        )
    size_badge.short_description = "حجم البيانات"

    def redis_status_badge(self, obj):
        from .live_context_service import get_redis_client, REDIS_KEY_TEMPLATE
        r = get_redis_client()
        redis_key = REDIS_KEY_TEMPLATE.format(user_id=obj.user_id)
        exists = bool(r and r.exists(redis_key))
        if exists:
            return format_html('<span style="color:#057a55;font-weight:bold;">🟢 متزامن في الذاكرة (Redis Active)</span>')
        return format_html('<span style="color:#6b7280;font-weight:bold;">⚪ غير محمل (Cache Miss / Needs Sync)</span>')
    redis_status_badge.short_description = "حالة الـ Redis"

    def updated_at_formatted(self, obj):
        return obj.updated_at.strftime("%Y-%m-%d %H:%M:%S") if obj.updated_at else "—"
    updated_at_formatted.short_description = "آخر تحديث"

    def created_at_formatted(self, obj):
        return obj.created_at.strftime("%Y-%m-%d %H:%M:%S") if obj.created_at else "—"
    created_at_formatted.short_description = "تاريخ الإنشاء"

    def compiled_prompt_preview(self, obj):
        from .live_context_service import format_live_context_for_prompt
        compiled = format_live_context_for_prompt(obj.data or {})
        if not compiled:
            return format_html('<em style="color:#9ca3af;">لا توجد بيانات منظمة لتوليد التوجيهات</em>')
        return format_html(
            '<pre style="background:#1e1e2e;color:#a6e3a1;padding:14px;border-radius:10px;font-family:monospace;font-size:12px;line-height:1.6;white-space:pre-wrap;max-height:400px;overflow:auto;">{}</pre>',
            compiled
        )
    compiled_prompt_preview.short_description = "معاينة التوجيهات الحية"

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        # Auto-sync to Redis on save
        from .live_context_service import set_user_live_context
        try:
            set_user_live_context(obj.user_id, obj.data or {})
            self.message_user(request, "تم حفظ البيانات ومزامنتها في كاش الـ Redis فورياً بنجاح.", level=messages.SUCCESS)
        except Exception as e:
            self.message_user(request, f"تم حفظ البيانات في DB لكن فشلت مزامنة Redis: {e}", level=messages.WARNING)

    def sync_to_redis_action(self, request, queryset):
        from .live_context_service import set_user_live_context
        count = 0
        for item in queryset:
            try:
                set_user_live_context(item.user_id, item.data or {})
                count += 1
            except Exception:
                pass
        self.message_user(request, f"تمت إعادة مزامنة {count} سجل بنجاح في كاش الـ Redis اللحظي.")
    sync_to_redis_action.short_description = "⚡ مزامنة السجلات المحددة إلى كاش Redis الآن"

    def clear_from_redis_action(self, request, queryset):
        from .live_context_service import delete_user_live_context
        count = 0
        for item in queryset:
            delete_user_live_context(item.user_id)
            count += 1
        self.message_user(request, f"تم مسح {count} سجل من كاش Redis.")
    clear_from_redis_action.short_description = "🗑️ مسح السجلات المحددة من كاش Redis"

