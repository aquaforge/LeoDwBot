from datetime import datetime

from sqlalchemy import Column, ForeignKey, Integer, String, DateTime, \
    Boolean, BigInteger, SmallInteger, Text
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """parent DB base class"""


class FilesData(Base):
    __tablename__ = "files_data"
    user_id = Column(BigInteger, nullable=False, primary_key=True)
    file_unique_id = Column(String, nullable=False, primary_key=True)
    performer = Column(String, nullable=True)
    title = Column(String, nullable=True)
    file_name = Column(String, nullable=True)
    mime_type = Column(String, nullable=True)
    short_file_name = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.now)

    def __repr__(self) -> str:
        return f"{self.performer}: {self.title[:50]} - {self.file_unique_id}"
