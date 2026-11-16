"""Research chats: a rep's conversation with the research model, kept exactly as the model produced it.

`messages` is the conversation as sent to the provider, block for block: a continued conversation must send it
back unchanged (the model's reasoning is tied to it), so it is only ever appended to. `turns` is what the
screen shows. `system` and `tools` are frozen when the chat starts, so a later release cannot alter an earlier
conversation. `cards` are the opportunities the model offered, each checked by code before it was shown.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.tenancy import TenantScoped


class ResearchChat(TenantScoped, Base):
    __tablename__ = 'si_research_chats'
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    requested_by: Mapped[int | None] = mapped_column(Integer)
    model: Mapped[str] = mapped_column(String(80), nullable=False)
    system: Mapped[str] = mapped_column(Text, nullable=False)
    tools: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    messages: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    turns: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    cards: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    sources: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False, default=dict)  # every page searched or read: url -> title
    cost_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
