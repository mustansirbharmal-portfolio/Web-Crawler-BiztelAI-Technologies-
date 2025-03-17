from enum import Enum as PythonEnum
from sqlalchemy import Column, Integer, String, Enum, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from typing import List
from app.database import Base

class CrawlStatus(str, PythonEnum):
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class CrawlJob(Base):
    __tablename__ = "crawl_jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    seed_url = Column(String(2048), nullable=False)
    status = Column(Enum(CrawlStatus), default=CrawlStatus.IN_PROGRESS, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    error_message = Column(Text, nullable=True)
    
    # Relationship to crawled URLs
    crawled_urls = relationship("CrawledUrl", back_populates="crawl_job", cascade="all, delete-orphan")

class CrawledUrl(Base):
    __tablename__ = "crawled_urls"
    
    id = Column(Integer, primary_key=True, index=True)
    url = Column(String(2048), nullable=False)
    title = Column(String(512), nullable=True)
    crawl_job_id = Column(Integer, ForeignKey("crawl_jobs.id", ondelete="CASCADE"), nullable=False)
    
    # Relationship to the parent crawl job
    crawl_job = relationship("CrawlJob", back_populates="crawled_urls")
