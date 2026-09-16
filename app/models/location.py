from datetime import datetime, timezone
from sqlalchemy import Column, Integer, Float, DateTime
from sqlalchemy.orm import relationship
from app.database import Base


def utc_now() -> datetime:
    """Helper returning UTC timestamp without timezone offset for database storage."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Location(Base):
    """SQLAlchemy model representing a unique geographic location where potholes are monitored."""

    __tablename__ = "locations"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    latitude = Column(Float, nullable=False, index=True)
    longitude = Column(Float, nullable=False, index=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    # Relationship to all reports at this location
    reports = relationship(
        "Report",
        back_populates="location",
        cascade="all, delete-orphan",
        order_by="Report.timestamp.asc()",
        foreign_keys="Report.location_id",
    )

    def __repr__(self) -> str:
        return f"<Location id={self.id} lat={self.latitude} lon={self.longitude}>"
