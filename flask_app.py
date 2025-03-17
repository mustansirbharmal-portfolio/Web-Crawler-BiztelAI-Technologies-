from flask import Flask, jsonify, request, redirect, render_template_string
from contextlib import asynccontextmanager
import httpx
import asyncio
import threading
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

app = Flask(__name__)

# Configure database
import os
from flask_sqlalchemy import SQLAlchemy
from apscheduler.schedulers.background import BackgroundScheduler

app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "postgresql://postgres:jeLXOrrcfYJUnJekHHSOSFAODYUxrWMN@crossover.proxy.rlwy.net:32028/railway")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True  # This helps reconnect to the database if connection is lost
}
db = SQLAlchemy(app)

# Model definitions
from sqlalchemy import Column, Integer, String, Text, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from enum import Enum as PythonEnum
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CrawlStatus(str, PythonEnum):
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class CrawlJob(db.Model):
    __tablename__ = "crawl_jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    seed_url = Column(String(2048), nullable=False)
    status = Column(db.Enum(CrawlStatus), default=CrawlStatus.IN_PROGRESS, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    error_message = Column(Text, nullable=True)
    
    crawled_urls = relationship("CrawledUrl", back_populates="crawl_job", cascade="all, delete-orphan")

class CrawledUrl(db.Model):
    __tablename__ = "crawled_urls"
    
    id = Column(Integer, primary_key=True, index=True)
    url = Column(String(2048), nullable=False)
    title = Column(String(512), nullable=True)
    crawl_job_id = Column(Integer, ForeignKey("crawl_jobs.id", ondelete="CASCADE"), nullable=False)
    
    crawl_job = relationship("CrawlJob", back_populates="crawled_urls")

# Create tables
with app.app_context():
    db.create_all()

# Crawler class
class WebCrawler:
    def __init__(self, max_workers=10, max_depth=2, timeout=10):
        self.max_workers = max_workers
        self.max_depth = max_depth
        self.timeout = timeout
    
    def crawl_in_thread(self, job_id):
        """Run the crawler in a separate thread"""
        # Create a new event loop for the thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Run the crawler
        loop.run_until_complete(self._crawl(job_id))
        loop.close()
    
    async def _crawl(self, job_id):
        """Main crawling function running as an async task."""
        with app.app_context():
            job = CrawlJob.query.get(job_id)
            if not job:
                logger.error(f"Job {job_id} not found")
                return
                
            try:
                seed_url = job.seed_url
                visited_urls = set()
                urls_to_visit = [{"url": seed_url, "depth": 0}]
                
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    while urls_to_visit and len(visited_urls) < 1000:  # Limit total URLs to prevent infinite crawling
                        # Process up to max_workers URLs concurrently
                        batch = urls_to_visit[:self.max_workers]
                        urls_to_visit = urls_to_visit[self.max_workers:]
                        
                        # Create tasks for concurrent processing
                        tasks = []
                        for item in batch:
                            if item["url"] not in visited_urls:
                                visited_urls.add(item["url"])
                                tasks.append(self._process_url(client, job_id, item["url"], item["depth"]))
                        
                        if not tasks:
                            continue
                            
                        # Wait for all tasks to complete and collect new URLs
                        results = await asyncio.gather(*tasks, return_exceptions=True)
                        
                        # Process results and add new URLs to visit
                        for result in results:
                            if isinstance(result, Exception):
                                logger.error(f"Error during crawling: {result}")
                                continue
                                
                            if result and "new_urls" in result:
                                for url in result["new_urls"]:
                                    if url not in visited_urls and result["depth"] < self.max_depth:
                                        urls_to_visit.append({"url": url, "depth": result["depth"] + 1})
                
                # Update job status to completed
                job.status = CrawlStatus.COMPLETED
                db.session.commit()
                logger.info(f"Completed crawl job {job_id}")
                
            except Exception as e:
                logger.exception(f"Error during crawl job {job_id}: {str(e)}")
                job.status = CrawlStatus.FAILED
                job.error_message = str(e)
                db.session.commit()
    
    async def _process_url(self, client, job_id, url, depth):
        """Process a single URL: fetch it, extract links, and store in the database."""
        try:
            logger.info(f"Crawling URL: {url} (depth: {depth})")
            
            # Fetch the URL
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()
            
            # Parse HTML content
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract page title
            title = soup.title.string if soup.title else None
            
            # Store the URL in the database
            with app.app_context():
                crawled_url = CrawledUrl(url=url, title=title, crawl_job_id=job_id)
                db.session.add(crawled_url)
                db.session.commit()
            
            # Only extract more links if we haven't reached max depth
            if depth < self.max_depth:
                # Extract all links
                links = soup.find_all('a', href=True)
                
                # Process and normalize links
                new_urls = []
                base_url_parsed = urlparse(url)
                
                for link in links:
                    href = link['href']
                    
                    # Create absolute URL
                    absolute_url = urljoin(url, href)
                    
                    # Parse the URL
                    parsed_url = urlparse(absolute_url)
                    
                    # Only keep URLs from the same domain and with http/https scheme
                    if (parsed_url.scheme in ('http', 'https') and 
                        parsed_url.netloc == base_url_parsed.netloc):
                        # Normalize URL by removing fragments
                        normalized_url = parsed_url._replace(fragment='').geturl()
                        new_urls.append(normalized_url)
                
                return {"depth": depth, "new_urls": list(set(new_urls))}
            
            return {"depth": depth, "new_urls": []}
            
        except httpx.RequestError as e:
            logger.error(f"Request error while crawling {url}: {str(e)}")
            return {"depth": depth, "new_urls": []}
        except Exception as e:
            logger.exception(f"Error processing URL {url}: {str(e)}")
            return {"depth": depth, "new_urls": []}

# Create crawler instance
crawler = WebCrawler()

# Setup periodic cleanup task
def cleanup_old_jobs():
    with app.app_context():
        # Delete jobs older than 7 days
        from datetime import datetime, timedelta
        cutoff_date = datetime.utcnow() - timedelta(days=7)
        old_jobs = CrawlJob.query.filter(CrawlJob.created_at < cutoff_date).all()
        
        count = 0
        for job in old_jobs:
            db.session.delete(job)
            count += 1
            
        if count > 0:
            db.session.commit()
            logger.info(f"Deleted {count} old crawl jobs")

# Start the scheduler
scheduler = BackgroundScheduler()
scheduler.add_job(cleanup_old_jobs, 'interval', hours=24)
scheduler.start()

# HTML Template for the documentation page
DOCS_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Web Crawler API Documentation</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link href="https://cdn.replit.com/agent/bootstrap-agent-dark-theme.min.css" rel="stylesheet">
    <style>
        .endpoint {
            margin-bottom: 30px;
            border-bottom: 1px solid var(--bs-gray-700);
            padding-bottom: 20px;
        }
        .method {
            display: inline-block;
            padding: 3px 6px;
            border-radius: 3px;
            margin-right: 10px;
        }
        .method-get {
            background-color: var(--bs-info);
            color: var(--bs-dark);
        }
        .method-post {
            background-color: var(--bs-success);
            color: var(--bs-light);
        }
        pre {
            background-color: var(--bs-gray-800);
            padding: 15px;
            border-radius: 5px;
        }
    </style>
</head>
<body>
    <div class="container py-4">
        <h1>Web Crawler API Documentation</h1>
        <p class="lead">This API allows you to crawl websites and retrieve their links.</p>
        
        <div class="endpoint">
            <h2><span class="method method-post">POST</span> /api/crawl</h2>
            <p>Start a new web crawling job</p>
            <h5>Request Body:</h5>
            <pre>
{
  "seed_url": "https://example.com"
}
            </pre>
            <h5>Response:</h5>
            <pre>
{
  "id": 1,
  "seed_url": "https://example.com",
  "status": "IN_PROGRESS",
  "created_at": "2023-04-01T12:00:00Z",
  "error_message": null
}
            </pre>
        </div>
        
        <div class="endpoint">
            <h2><span class="method method-get">GET</span> /api/crawl/{job_id}</h2>
            <p>Get the status and results of a crawl job</p>
            <h5>Response:</h5>
            <pre>
{
  "id": 1,
  "seed_url": "https://example.com",
  "status": "COMPLETED",
  "created_at": "2023-04-01T12:00:00Z",
  "error_message": null,
  "crawled_urls": [
    {
      "id": 1,
      "url": "https://example.com",
      "title": "Example Domain",
      "crawl_job_id": 1
    },
    ...
  ]
}
            </pre>
        </div>
        
        <div class="endpoint">
            <h2><span class="method method-get">GET</span> /api/crawl/{job_id}/urls</h2>
            <p>Get paginated list of URLs crawled for a specific job</p>
            <h5>Query Parameters:</h5>
            <ul>
                <li><code>page</code>: Page number (default: 1)</li>
                <li><code>page_size</code>: Number of items per page (default: 50, max: 100)</li>
            </ul>
            <h5>Response:</h5>
            <pre>
{
  "total": 150,
  "page": 1,
  "page_size": 50,
  "items": [
    {
      "id": 1,
      "url": "https://example.com",
      "title": "Example Domain",
      "crawl_job_id": 1
    },
    ...
  ]
}
            </pre>
        </div>
        
        <div class="endpoint">
            <h2><span class="method method-get">GET</span> /api/crawl</h2>
            <p>List all crawl jobs with pagination</p>
            <h5>Query Parameters:</h5>
            <ul>
                <li><code>limit</code>: Maximum number of items (default: 10, max: 100)</li>
                <li><code>offset</code>: Offset for pagination (default: 0)</li>
            </ul>
            <h5>Response:</h5>
            <pre>
{
  "total": 25,
  "limit": 10,
  "offset": 0,
  "items": [
    {
      "id": 1,
      "seed_url": "https://example.com",
      "status": "COMPLETED",
      "created_at": "2023-04-01T12:00:00Z",
      "error_message": null
    },
    ...
  ]
}
            </pre>
        </div>
    </div>
</body>
</html>
"""

# Root endpoint for health check
@app.route("/")
def root():
    return jsonify({"status": "ok", "message": "Web Crawler API is running"})

# API documentation route
@app.route("/docs")
def docs():
    return render_template_string(DOCS_TEMPLATE)

# API routes
@app.route("/api/crawl", methods=["POST"])
def start_crawl():
    data = request.json
    if not data or "seed_url" not in data:
        return jsonify({"error": "Invalid request data"}), 400

    seed_url = data["seed_url"]
    
    # Validate URL
    try:
        parsed_url = urlparse(seed_url)
        if not all([parsed_url.scheme, parsed_url.netloc]):
            return jsonify({"error": "Invalid URL format"}), 400
    except Exception:
        return jsonify({"error": "Invalid URL format"}), 400
    
    # Create a new crawl job
    job = CrawlJob(seed_url=seed_url, status=CrawlStatus.IN_PROGRESS)
    db.session.add(job)
    db.session.commit()
    
    # Start crawling in a background thread
    thread = threading.Thread(target=crawler.crawl_in_thread, args=(job.id,))
    thread.daemon = True
    thread.start()
    
    # Return job info
    return jsonify({
        "id": job.id,
        "seed_url": job.seed_url,
        "status": job.status.value,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "error_message": job.error_message
    }), 201

@app.route("/api/crawl/<int:job_id>", methods=["GET"])
def get_crawl_status(job_id):
    job = CrawlJob.query.get(job_id)
    if not job:
        return jsonify({"error": "Crawl job not found"}), 404
    
    # Get all URLs for this job
    urls = CrawledUrl.query.filter_by(crawl_job_id=job_id).all()
    
    # Format the response
    return jsonify({
        "id": job.id,
        "seed_url": job.seed_url,
        "status": job.status.value,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "error_message": job.error_message,
        "crawled_urls": [
            {
                "id": url.id,
                "url": url.url,
                "title": url.title,
                "crawl_job_id": url.crawl_job_id
            } for url in urls
        ]
    })

@app.route("/api/crawl/<int:job_id>/urls", methods=["GET"])
def get_crawled_urls(job_id):
    job = CrawlJob.query.get(job_id)
    if not job:
        return jsonify({"error": "Crawl job not found"}), 404
    
    # Get pagination parameters
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("page_size", 50, type=int)
    
    # Validate pagination parameters
    if page < 1:
        page = 1
    if page_size < 1 or page_size > 100:
        page_size = 50
    
    # Calculate offset
    offset = (page - 1) * page_size
    
    # Get paginated URLs
    total = CrawledUrl.query.filter_by(crawl_job_id=job_id).count()
    urls = CrawledUrl.query.filter_by(crawl_job_id=job_id).offset(offset).limit(page_size).all()
    
    # Format the response
    return jsonify({
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": url.id,
                "url": url.url,
                "title": url.title,
                "crawl_job_id": url.crawl_job_id
            } for url in urls
        ]
    })

@app.route("/api/crawl", methods=["GET"])
def list_crawl_jobs():
    # Get pagination parameters
    limit = request.args.get("limit", 10, type=int)
    offset = request.args.get("offset", 0, type=int)
    
    # Validate pagination parameters
    if limit < 1 or limit > 100:
        limit = 10
    if offset < 0:
        offset = 0
    
    # Get paginated jobs
    total = CrawlJob.query.count()
    jobs = CrawlJob.query.offset(offset).limit(limit).all()
    
    # Format the response
    return jsonify({
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [
            {
                "id": job.id,
                "seed_url": job.seed_url,
                "status": job.status.value,
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "error_message": job.error_message
            } for job in jobs
        ]
    })