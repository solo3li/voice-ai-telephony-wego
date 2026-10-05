from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from agents.models import UserMCPServer

class Command(BaseCommand):
    help = 'Setup FastMCP store server for user hamo'

    def handle(self, *args, **options):
        hamo = User.objects.filter(username='hamo').first()
        if not hamo:
            self.stdout.write(self.style.ERROR("User 'hamo' does not exist."))
            return

        default_tools = [
            {
                "name": "search_store_products",
                "description": "البحث في كتالوج منتجات المتجر الإلكتروني واسترجاع تفاصيل المنتجات والأسعار والمخزون المتوفر.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "query": {
                            "type": "STRING",
                            "description": "كلمة البحث أو اسم المنتج المراد الاستعلام عنه (مثل: سماعة، شاحن، ساعة)."
                        }
                    }
                }
            },
            {
                "name": "get_order_status",
                "description": "الاستعلام عن حالة شحن وتوصيل طلبية محددة وموعد التسليم المتوقع عبر رقم الطلب.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "order_id": {
                            "type": "STRING",
                            "description": "رقم الطلبية (مثل 1001)."
                        }
                    },
                    "required": ["order_id"]
                }
            },
            {
                "name": "create_store_order",
                "description": "إنشاء وتسجيل طلبية شراء جديدة لمنتج في المتجر الإلكتروني.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "product_name": {
                            "type": "STRING",
                            "description": "اسم المنتج المطلوب شراؤه (مثال: سماعة بلوتوث لاسلكية برو)."
                        },
                        "quantity": {
                            "type": "INTEGER",
                            "description": "الكمية المطلوبة من المنتج."
                        },
                        "customer_name": {
                            "type": "STRING",
                            "description": "اسم العميل صاحب الطلب."
                        },
                        "customer_phone": {
                            "type": "STRING",
                            "description": "رقم هاتف العميل للتواصل والتوصيل."
                        },
                        "customer_address": {
                            "type": "STRING",
                            "description": "عنوان التوصيل بالتفصيل."
                        }
                    },
                    "required": ["product_name"]
                }
            }
        ]

        server, created = UserMCPServer.objects.update_or_create(
            user=hamo,
            defaults={
                "name": "خادم متجر hamo الإلكتروني (FastMCP)",
                "server_url": "http://mock-store:8002/sse",
                "auth_token": "",
                "is_active": True,
                "cached_tools": default_tools,
                "last_synced_at": timezone.now(),
            }
        )

        status_text = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(
            f"{status_text} FastMCP server configuration for 'hamo': {server.server_url} with {len(default_tools)} tools."
        ))
