"""phase 1 baseline

Revision ID: 0001_phase_1_baseline
Revises:
Create Date: 2026-04-29 00:00:00.000000

Hand-edited after autogenerate to add:
- ``ix_users_email_lower`` functional UNIQUE on ``LOWER(email)``.
- ``ix_medication_interactions_pair`` UNIQUE on the unordered pair via
  ``LEAST/GREATEST`` (autogen cannot emit expression indexes).
- ``doses_check_user_id`` PL/pgSQL trigger asserting
  ``doses.user_id == medications.user_id`` (D4).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_phase_1_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_DOSES_TRIGGER_FN = """
CREATE OR REPLACE FUNCTION doses_check_user_id() RETURNS trigger AS $$
DECLARE
    med_user_id uuid;
BEGIN
    SELECT user_id INTO med_user_id FROM medications WHERE id = NEW.medication_id;
    IF med_user_id IS NULL THEN
        RAISE EXCEPTION 'doses.medication_id % does not reference a medication',
            NEW.medication_id;
    END IF;
    IF NEW.user_id <> med_user_id THEN
        RAISE EXCEPTION 'doses.user_id (%) must equal medications.user_id (%)',
            NEW.user_id, med_user_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

_DOSES_TRIGGER = """
CREATE TRIGGER doses_user_id_match
BEFORE INSERT OR UPDATE ON doses
FOR EACH ROW EXECUTE FUNCTION doses_check_user_id();
"""


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    user_role = postgresql.ENUM("admin", "user", name="user_role")
    timer_preference = postgresql.ENUM(
        "none", "count_up", "count_down", "multi_sub_dose",
        name="timer_preference",
    )
    reminder_type = postgresql.ENUM("dose", "refill", name="reminder_type")
    reminder_status = postgresql.ENUM(
        "pending", "sent", "snoozed", "dismissed", name="reminder_status"
    )
    for enum in (user_role, timer_preference, reminder_type, reminder_status):
        enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "role",
            postgresql.ENUM(name="user_role", create_type=False),
            nullable=False,
        ),
        sa.Column("timezone", sa.Text(), nullable=False),
        sa.Column("quiet_hours_start", sa.Time(), nullable=True),
        sa.Column("quiet_hours_end", sa.Time(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    # D8: case-insensitive uniqueness via functional UNIQUE index.
    op.execute(
        "CREATE UNIQUE INDEX ix_users_email_lower ON users (LOWER(email))"
    )

    op.create_table(
        "sessions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.Text(), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])

    op.create_table(
        "push_subscriptions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("p256dh", sa.Text(), nullable=False),
        sa.Column("auth", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "user_id", "endpoint", name="uq_push_user_endpoint"
        ),
    )
    op.create_index(
        "ix_push_subscriptions_user_id", "push_subscriptions", ["user_id"]
    )

    op.create_table(
        "medications",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("times_per_day", sa.SmallInteger(), nullable=False),
        sa.Column("quantity_per_dose", sa.Numeric(10, 3), nullable=False),
        sa.Column("unit", sa.Text(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("total_doses", sa.Integer(), nullable=True),
        sa.Column(
            "timer_preference",
            postgresql.ENUM(name="timer_preference", create_type=False),
            nullable=False,
        ),
        sa.Column("min_interval_minutes", sa.Integer(), nullable=True),
        sa.Column("window_duration_minutes", sa.Integer(), nullable=True),
        sa.Column(
            "total_doses_filled",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "doses_remaining",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "times_per_day >= 0", name="ck_medications_times_per_day_nonneg"
        ),
        sa.CheckConstraint(
            "quantity_per_dose > 0", name="ck_medications_quantity_per_dose_pos"
        ),
        sa.CheckConstraint(
            "total_doses IS NULL OR total_doses > 0",
            name="ck_medications_total_doses_pos",
        ),
        sa.CheckConstraint(
            "total_doses_filled >= 0",
            name="ck_medications_total_doses_filled_nonneg",
        ),
        sa.CheckConstraint(
            "doses_remaining >= 0", name="ck_medications_doses_remaining_nonneg"
        ),
        sa.CheckConstraint(
            "(timer_preference <> 'count_down') "
            "OR (min_interval_minutes IS NOT NULL "
            "AND min_interval_minutes > 0)",
            name="ck_medications_count_down_requires_interval",
        ),
        sa.CheckConstraint(
            "(timer_preference <> 'multi_sub_dose') "
            "OR (window_duration_minutes IS NOT NULL "
            "AND window_duration_minutes > 0)",
            name="ck_medications_multi_sub_dose_requires_window",
        ),
    )
    op.create_index("ix_medications_user_id", "medications", ["user_id"])

    op.create_table(
        "medication_interactions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "medication_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("medications.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "conflicting_medication_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("medications.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("cooldown_minutes", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "cooldown_minutes > 0", name="ck_interactions_cooldown_pos"
        ),
        sa.CheckConstraint(
            "medication_id <> conflicting_medication_id",
            name="ck_interactions_distinct_pair",
        ),
    )
    op.create_index(
        "ix_medication_interactions_medication_id",
        "medication_interactions",
        ["medication_id"],
    )
    op.create_index(
        "ix_medication_interactions_conflicting_medication_id",
        "medication_interactions",
        ["conflicting_medication_id"],
    )
    # D5: UNIQUE on the unordered pair.
    op.execute(
        "CREATE UNIQUE INDEX ix_medication_interactions_pair "
        "ON medication_interactions ("
        "LEAST(medication_id, conflicting_medication_id), "
        "GREATEST(medication_id, conflicting_medication_id))"
    )

    op.create_table(
        "schedules",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("time_of_day", sa.Time(), nullable=False),
        sa.Column(
            "days_of_week",
            sa.SmallInteger(),
            nullable=False,
            server_default="127",
        ),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "days_of_week BETWEEN 0 AND 127",
            name="ck_schedules_days_of_week_range",
        ),
    )
    op.create_index("ix_schedules_user_id", "schedules", ["user_id"])

    op.create_table(
        "schedule_medications",
        sa.Column(
            "schedule_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("schedules.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "medication_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("medications.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_table(
        "doses",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "medication_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("medications.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "schedule_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("schedules.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("taken_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("quantity", sa.Numeric(10, 3), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("quantity > 0", name="ck_doses_quantity_pos"),
    )
    op.create_index("ix_doses_user_id", "doses", ["user_id"])
    op.create_index("ix_doses_medication_id", "doses", ["medication_id"])
    op.create_index("ix_doses_schedule_id", "doses", ["schedule_id"])

    # D4: enforce doses.user_id == medications.user_id via DB trigger.
    op.execute(_DOSES_TRIGGER_FN)
    op.execute(_DOSES_TRIGGER)

    op.create_table(
        "reminders",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "type",
            postgresql.ENUM(name="reminder_type", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "medication_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("medications.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "schedule_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("schedules.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(name="reminder_status", create_type=False),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(type = 'dose' AND schedule_id IS NOT NULL "
            "AND medication_id IS NULL) "
            "OR (type = 'refill' AND medication_id IS NOT NULL "
            "AND schedule_id IS NULL)",
            name="ck_reminders_type_refs",
        ),
    )
    op.create_index("ix_reminders_user_id", "reminders", ["user_id"])
    op.create_index(
        "ix_reminders_medication_id", "reminders", ["medication_id"]
    )
    op.create_index("ix_reminders_schedule_id", "reminders", ["schedule_id"])


def downgrade() -> None:
    op.drop_index("ix_reminders_schedule_id", table_name="reminders")
    op.drop_index("ix_reminders_medication_id", table_name="reminders")
    op.drop_index("ix_reminders_user_id", table_name="reminders")
    op.drop_table("reminders")

    op.execute("DROP TRIGGER IF EXISTS doses_user_id_match ON doses")
    op.execute("DROP FUNCTION IF EXISTS doses_check_user_id()")
    op.drop_index("ix_doses_schedule_id", table_name="doses")
    op.drop_index("ix_doses_medication_id", table_name="doses")
    op.drop_index("ix_doses_user_id", table_name="doses")
    op.drop_table("doses")

    op.drop_table("schedule_medications")

    op.drop_index("ix_schedules_user_id", table_name="schedules")
    op.drop_table("schedules")

    op.execute("DROP INDEX IF EXISTS ix_medication_interactions_pair")
    op.drop_index(
        "ix_medication_interactions_conflicting_medication_id",
        table_name="medication_interactions",
    )
    op.drop_index(
        "ix_medication_interactions_medication_id",
        table_name="medication_interactions",
    )
    op.drop_table("medication_interactions")

    op.drop_index("ix_medications_user_id", table_name="medications")
    op.drop_table("medications")

    op.drop_index(
        "ix_push_subscriptions_user_id", table_name="push_subscriptions"
    )
    op.drop_table("push_subscriptions")

    op.drop_index("ix_sessions_user_id", table_name="sessions")
    op.drop_table("sessions")

    op.execute("DROP INDEX IF EXISTS ix_users_email_lower")
    op.drop_table("users")

    for enum_name in (
        "reminder_status",
        "reminder_type",
        "timer_preference",
        "user_role",
    ):
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
