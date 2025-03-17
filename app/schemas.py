from typing import List, Optional
from pydantic import BaseModel, HttpUrl, validator
from datetime import datetime
from app.models import CrawlStatus

class CrawledUrlBase(BaseModel):
    url: str
    title: Optional[str] = None

class CrawledUrlCreate(CrawledUrlBase):
    pass

class CrawledUrl(CrawledUrlBase):
    id: int
    crawl_job_id: int
    
    class Config:
        orm_mode = True

class CrawlJobBase(BaseModel):
    seed_url: str
    
    @validator('seed_url')
    def validate_url(cls, v):
        # Simple validation for URL format
        if not v.startswith(('http://', 'https://')):
            raise ValueError('URL must start with http:// or https://')
        return v

class CrawlJobCreate(CrawlJobBase):
    pass

class CrawlJobResponse(CrawlJobBase):
    id: int
    status: CrawlStatus
    created_at: datetime
    error_message: Optional[str] = None
    
    class Config:
        orm_mode = True

class CrawlJobWithUrls(CrawlJobResponse):
    crawled_urls: List[CrawledUrl] = []
    
    class Config:
        orm_mode = True

class PaginatedUrlsResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[CrawledUrl]
