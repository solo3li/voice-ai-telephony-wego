"""
Models for voice_assistant app.
The underlying models have been modularized into independent domain apps:
- knowledge: Document, DocumentChunk
- agents: AgentProfile, UserMCPServer
- call_center: EmployeeProfile, CallQueue, QueueMembership
- telephony: OutboundSIPTrunk
- crm: CustomerMemory, CallSession

They are re-exported here for backward compatibility.
"""
from django.db import models
from django.contrib.auth.models import User
from knowledge.models import Document, DocumentChunk
from agents.models import AgentProfile, UserMCPServer
from call_center.models import EmployeeProfile, CallQueue, QueueMembership
from telephony.models import OutboundSIPTrunk, InboundPBXTrunk
from crm.models import CustomerMemory, CallSession

# Backward compatibility alias
UserSIPAccount = EmployeeProfile


class TenantChatwootConfig(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='chatwoot_config')
    account_id = models.PositiveIntegerField(default=2, db_index=True)
    chatwoot_user_id = models.PositiveIntegerField(null=True, blank=True)
    assistant_id = models.PositiveIntegerField(null=True, blank=True)
    is_provisioned = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'voice_assistant_tenant_chatwoot_config'
        verbose_name = 'Tenant Chatwoot Config'
        verbose_name_plural = 'Tenant Chatwoot Configs'

    def __str__(self):
        return f"Chatwoot Config for {self.user.username} (Account {self.account_id})"


__all__ = [
    'TenantChatwootConfig',
    'Document',
    'DocumentChunk',
    'AgentProfile',
    'UserMCPServer',
    'EmployeeProfile',
    'UserSIPAccount',
    'CallQueue',
    'QueueMembership',
    'OutboundSIPTrunk',
    'InboundPBXTrunk',
    'CustomerMemory',
    'CallSession',
]

