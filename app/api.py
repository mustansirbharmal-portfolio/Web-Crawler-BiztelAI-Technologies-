from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List
from sqlalchemy.exc import SQLAlchemyError
import logging

from app.database import get_db
from app.models import CrawlJob, CrawledUrl, CrawlStatus
from app.schemas import (
    CrawlJobCreate, 
    CrawlJobResponse, 
    CrawlJobWithUrls,
    CrawledUrl as CrawledUrlSchema,
    PaginatedUrlsResponse
)
from app.crawler import WebCrawler

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create API router
router = APIRouter()

@router.post("/crawl", response_model=CrawlJobResponse, status_code=201)
async def start_crawl(
    job_data: CrawlJobCreate,
    db: Session = Depends(get_db)
):
    """
    Start a new web crawling job with the given seed URL.
    
    The crawling process runs asynchronously in the background.
    """
    try:
        crawler = WebCrawler(db)
        job = await crawler.start_crawl_job(job_data)
        return job
    except Exception as e:
        logger.exception(f"Error starting crawl job: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to start crawl job: {str(e)}")

@router.get("/crawl/{job_id}", response_model=CrawlJobWithUrls)
async def get_crawl_status(
    job_id: int,
    db: Session = Depends(get_db)
):
    """
    Get the status and results of a crawl job by ID.
    
    Returns the job details including all crawled URLs.
    """
    job = db.query(CrawlJob).filter(CrawlJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Crawl job with id {job_id} not found")
    
    return job

@router.get("/crawl/{job_id}/urls", response_model=PaginatedUrlsResponse)
async def get_crawled_urls(
    job_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Get paginated list of URLs crawled for a specific job.
    """
    job = db.query(CrawlJob).filter(CrawlJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Crawl job with id {job_id} not found")
    
    # Calculate pagination
    offset = (page - 1) * page_size
    
    # Get total count
    total = db.query(CrawledUrl).filter(CrawledUrl.crawl_job_id == job_id).count()
    
    # Get paginated results
    urls = db.query(CrawledUrl).filter(
        CrawledUrl.crawl_job_id == job_id
    ).offset(offset).limit(page_size).all()
    
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": urls
    }

@router.get("/crawl", response_model=List[CrawlJobResponse])
async def list_crawl_jobs(
    db: Session = Depends(get_db),
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """
    List all crawl jobs with pagination.
    """
    jobs = db.query(CrawlJob).order_by(CrawlJob.created_at.desc()).offset(offset).limit(limit).all()
    return jobs
