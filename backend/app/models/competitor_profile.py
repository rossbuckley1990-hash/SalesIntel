from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class CompetitorProfile(Base):
    __tablename__ = "competitor_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    sectors: Mapped[list[str]] = mapped_column(JSON, default=list)
    strengths: Mapped[list[str]] = mapped_column(JSON, default=list)
    weaknesses: Mapped[list[str]] = mapped_column(JSON, default=list)
    pricing_behaviour: Mapped[str] = mapped_column(Text, default="")
    threat_level: Mapped[str] = mapped_column(String(40), default="unknown", index=True)
    counter_strategy: Mapped[str] = mapped_column(Text, default="")

