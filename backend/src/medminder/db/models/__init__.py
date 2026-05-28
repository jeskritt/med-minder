"""Re-export every model class.

Importing this package is what populates ``Base.metadata`` — Alembic's
``env.py`` does ``import medminder.db`` which in turn imports this
module, ensuring every table is visible to autogenerate.
"""

from medminder.db.models.admin_audit import AdminAuditLog
from medminder.db.models.dose_interaction_overrides import (
    DoseInteractionOverride,
)
from medminder.db.models.dose_voids import DoseVoid
from medminder.db.models.doses import Dose
from medminder.db.models.medication_interactions import MedicationInteraction
from medminder.db.models.medications import Medication
from medminder.db.models.push_subscriptions import PushSubscription
from medminder.db.models.reminders import Reminder
from medminder.db.models.schedule_medications import ScheduleMedication
from medminder.db.models.schedules import Schedule
from medminder.db.models.sessions import Session as SessionModel
from medminder.db.models.users import User

__all__ = [
    "AdminAuditLog",
    "Dose",
    "DoseInteractionOverride",
    "DoseVoid",
    "Medication",
    "MedicationInteraction",
    "PushSubscription",
    "Reminder",
    "Schedule",
    "ScheduleMedication",
    "SessionModel",
    "User",
]
