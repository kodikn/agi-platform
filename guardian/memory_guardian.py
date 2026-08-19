"""Level 2: Memory Guardian - Memory validation and approval workflow"""

from typing import List, Dict, Any, Optional, Callable
from enum import Enum
from datetime import datetime
import logging
import uuid

from memory.layer import MemoryEntry, MemoryType

logger = logging.getLogger(__name__)


class ApprovalStatus(str, Enum):
    """Memory approval status"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVIEW_REQUIRED = "review_required"


class RiskLevel(str, Enum):
    """Memory risk level"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class GuardianRule:
    """Memory Guardian rule"""
    
    def __init__(
        self,
        name: str,
        validator: Callable[[MemoryEntry], bool],
        risk_level: RiskLevel = RiskLevel.MEDIUM,
        auto_reject: bool = False
    ):
        self.name = name
        self.validator = validator
        self.risk_level = risk_level
        self.auto_reject = auto_reject

    async def validate(self, entry: MemoryEntry) -> bool:
        """Validate memory against rule"""
        return self.validator(entry)


class MemoryGuardianApproval:
    """Memory approval workflow"""
    
    def __init__(self):
        self.id = str(uuid.uuid4())
        self.memory_id: Optional[str] = None
        self.content: Dict[str, Any] = {}
        self.status = ApprovalStatus.PENDING
        self.risk_level = RiskLevel.MEDIUM
        self.validation_errors: List[str] = []
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self.approved_by: Optional[str] = None
        self.approval_notes: str = ""
        self.version = 1

    def approve(self, approved_by: str, notes: str = ""):
        """Approve memory"""
        self.status = ApprovalStatus.APPROVED
        self.approved_by = approved_by
        self.approval_notes = notes
        self.updated_at = datetime.utcnow()
        logger.info(f"Approved memory {self.memory_id} by {approved_by}")

    def reject(self, reason: str):
        """Reject memory"""
        self.status = ApprovalStatus.REJECTED
        self.approval_notes = reason
        self.updated_at = datetime.utcnow()
        logger.info(f"Rejected memory {self.memory_id}: {reason}")


class DuplicateDetector:
    """Detect duplicate memories"""
    
    def __init__(self, similarity_threshold: float = 0.85):
        self.similarity_threshold = similarity_threshold

    async def find_duplicates(
        self,
        entry: MemoryEntry,
        existing_memories: List[MemoryEntry]
    ) -> List[MemoryEntry]:
        """Find duplicate memories"""
        
        duplicates = []
        
        for existing in existing_memories:
            # Simple similarity check based on content overlap
            if existing.memory_type == entry.memory_type:
                similarity = self._calculate_similarity(
                    entry.content,
                    existing.content
                )
                
                if similarity >= self.similarity_threshold:
                    duplicates.append(existing)
        
        return duplicates

    def _calculate_similarity(self, content1: Dict, content2: Dict) -> float:
        """Calculate similarity between two content dictionaries"""
        
        keys1 = set(str(content1).lower().split())
        keys2 = set(str(content2).lower().split())
        
        if not keys1 or not keys2:
            return 0.0
        
        intersection = len(keys1 & keys2)
        union = len(keys1 | keys2)
        
        return intersection / union if union > 0 else 0.0


class ConflictDetector:
    """Detect memory conflicts"""
    
    async def find_conflicts(
        self,
        entry: MemoryEntry,
        existing_memories: List[MemoryEntry]
    ) -> List[Dict[str, Any]]:
        """Find conflicting memories"""
        
        conflicts = []
        
        for existing in existing_memories:
            if self._has_conflict(entry, existing):
                conflicts.append({
                    "memory_id": existing.id,
                    "conflict_type": "semantic_conflict",
                    "existing_content": existing.content,
                    "new_content": entry.content
                })
        
        return conflicts

    def _has_conflict(self, entry1: MemoryEntry, entry2: MemoryEntry) -> bool:
        """Check if two memories conflict"""
        
        # Conflict detection logic
        if entry1.memory_type != entry2.memory_type:
            return False
        
        # Simple check: if both have tags and they're contradictory
        conflicting_tags = {"true", "false", "yes", "no"}
        tags1 = set(entry1.tags)
        tags2 = set(entry2.tags)
        
        if (tags1 & conflicting_tags) and (tags2 & conflicting_tags):
            if tags1 != tags2:
                return True
        
        return False


class MemoryGuardian:
    """Level 2: Memory Guardian - Memory validation and approval"""
    
    def __init__(self):
        self.rules: Dict[str, GuardianRule] = {}
        self.duplicate_detector = DuplicateDetector()
        self.conflict_detector = ConflictDetector()
        self.approval_queue: Dict[str, MemoryGuardianApproval] = {}
        self.approved_memories: Dict[str, MemoryGuardianApproval] = {}

    def register_rule(self, rule: GuardianRule):
        """Register a validation rule"""
        self.rules[rule.name] = rule
        logger.info(f"Registered guardian rule: {rule.name}")

    async def validate_memory(
        self,
        entry: MemoryEntry,
        existing_memories: List[MemoryEntry]
    ) -> MemoryGuardianApproval:
        """Validate memory and create approval workflow"""
        
        approval = MemoryGuardianApproval()
        approval.memory_id = entry.id
        approval.content = entry.content
        
        # Run all validation rules
        for rule_name, rule in self.rules.items():
            try:
                is_valid = await rule.validate(entry)
                if not is_valid:
                    approval.validation_errors.append(f"Failed rule: {rule_name}")
                    approval.risk_level = rule.risk_level
                    
                    if rule.auto_reject:
                        approval.reject(f"Auto-rejected by rule: {rule_name}")
                        return approval
            except Exception as e:
                logger.error(f"Error validating rule {rule_name}: {str(e)}")
                approval.validation_errors.append(f"Error: {str(e)}")

        # Check for duplicates
        duplicates = await self.duplicate_detector.find_duplicates(
            entry,
            existing_memories
        )
        
        if duplicates:
            approval.validation_errors.append(f"Found {len(duplicates)} duplicate(s)")
            approval.status = ApprovalStatus.REVIEW_REQUIRED

        # Check for conflicts
        conflicts = await self.conflict_detector.find_conflicts(
            entry,
            existing_memories
        )
        
        if conflicts:
            approval.validation_errors.append(f"Found {len(conflicts)} conflict(s)")
            approval.risk_level = RiskLevel.HIGH
            approval.status = ApprovalStatus.REVIEW_REQUIRED

        # Set approval status if no issues
        if not approval.validation_errors:
            approval.status = ApprovalStatus.APPROVED
        
        return approval

    async def approve_memory(
        self,
        approval_id: str,
        approved_by: str,
        notes: str = ""
    ) -> bool:
        """Approve memory"""
        
        approval = self.approval_queue.get(approval_id)
        if not approval:
            logger.error(f"Approval not found: {approval_id}")
            return False
        
        approval.approve(approved_by, notes)
        self.approved_memories[approval_id] = approval
        del self.approval_queue[approval_id]
        
        return True

    async def reject_memory(
        self,
        approval_id: str,
        reason: str
    ) -> bool:
        """Reject memory"""
        
        approval = self.approval_queue.get(approval_id)
        if not approval:
            logger.error(f"Approval not found: {approval_id}")
            return False
        
        approval.reject(reason)
        del self.approval_queue[approval_id]
        
        return True

    async def get_approval_status(self, approval_id: str) -> Optional[MemoryGuardianApproval]:
        """Get approval status"""
        
        return (
            self.approval_queue.get(approval_id)
            or self.approved_memories.get(approval_id)
        )

    async def audit_trail(self, memory_id: str) -> List[Dict[str, Any]]:
        """Get memory audit trail"""
        
        trail = []
        
        for approval_id, approval in self.approved_memories.items():
            if approval.memory_id == memory_id:
                trail.append({
                    "approval_id": approval_id,
                    "status": approval.status.value,
                    "created_at": approval.created_at.isoformat(),
                    "updated_at": approval.updated_at.isoformat(),
                    "approved_by": approval.approved_by,
                    "notes": approval.approval_notes,
                    "version": approval.version
                })
        
        return trail
