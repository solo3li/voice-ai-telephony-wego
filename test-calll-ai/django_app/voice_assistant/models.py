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
from knowledge.models import Document, DocumentChunk
from agents.models import AgentProfile, UserMCPServer
from call_center.models import EmployeeProfile, CallQueue, QueueMembership
from telephony.models import OutboundSIPTrunk, InboundPBXTrunk
from crm.models import CustomerMemory, CallSession

# Backward compatibility alias
UserSIPAccount = EmployeeProfile

__all__ = [
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
