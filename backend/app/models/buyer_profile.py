from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class BuyerProfile(Base):
    __tablename__ = "buyer_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    buyer_name: Mapped[str] = mapped_column(String(255), index=True)
    sector: Mapped[str] = mapped_column(String(120), index=True)
    region: Mapped[str] = mapped_column(String(120), index=True)
    estate_size: Mapped[str | None] = mapped_column(String(120), nullable=True)
    procurement_drivers: Mapped[list[str]] = mapped_column(JSON, default=list)
    pain_points: Mapped[list[str]] = mapped_column(JSON, default=list)
    decision_criteria: Mapped[list[str]] = mapped_column(JSON, default=list)
    relationship_status: Mapped[str] = mapped_column(String(120), default="unknown", index=True)
    next_best_action: Mapped[str] = mapped_column(Text, default="")

