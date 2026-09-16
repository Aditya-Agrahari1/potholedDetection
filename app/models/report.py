from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.database import Base


def utc_now() -> datetime:
    """Helper returning UTC timestamp without timezone offset for database storage."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Report(Base):
    """SQLAlchemy model representing an inspection report for a pothole at a location."""

    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    location_id = Column(Integer, ForeignKey("locations.id", ondelete="CASCADE"), nullable=False, index=True)
    photo_path = Column(Text, nullable=False)
    timestamp = Column(DateTime, nullable=False, index=True)
    detection_data = Column(JSON, nullable=False)
    status = Column(String(50), nullable=False, index=True)  # 'new', 'worsened', 'improved', 'persistent', 'resolved'
    compared_to_id = Column(Integer, ForeignKey("reports.id", ondelete="SET NULL"), nullable=True)
    pdf_path = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    # Relationships
    location = relationship("Location", back_populates="reports", foreign_keys=[location_id])
    compared_to_report = relationship("Report", remote_side=[id], foreign_keys=[compared_to_id])

    def __repr__(self) -> str:
        return f"<Report id={self.id} location_id={self.location_id} status={self.status}>"
