import asyncio
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import logging
from sqlalchemy.orm import Session
from typing import List, Set, Dict, Optional
from concurrent.futures import ThreadPoolExecutor
import time

from app.models import CrawlJob, CrawledUrl, CrawlStatus
from app.schemas import CrawlJobCreate

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WebCrawler:
    def __init__(self, db: Session, max_workers: int = 10, max_depth: int = 2, timeout: int = 10):
        self.db = db
        self.max_workers = max_workers
        self.max_depth = max_depth
        self.timeout = timeout
    
    async def start_crawl_job(self, job_data: CrawlJobCreate) -> CrawlJob:
        """Create a new crawl job and start the crawling process."""
        # Create new job record
        job = CrawlJob(seed_url=job_data.seed_url, status=CrawlStatus.IN_PROGRESS)
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        
        # Start crawling in a background task
        asyncio.create_task(self._crawl(job.id))
        
        return job
    
    async def _crawl(self, job_id: int) -> None:
        """Main crawling function running as an async task."""
        job = self.db.query(CrawlJob).filter(CrawlJob.id == job_id).first()
        if not job:
            logger.error(f"Job {job_id} not found")
            return
            
        try:
            seed_url = job.seed_url
            visited_urls: Set[str] = set()
            urls_to_visit: List[Dict[str, any]] = [{"url": seed_url, "depth": 0}]
            
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
            self.db.commit()
            
        except Exception as e:
            logger.exception(f"Error during crawl job {job_id}: {str(e)}")
            job.status = CrawlStatus.FAILED
            job.error_message = str(e)
            self.db.commit()
    
    async def _process_url(self, client: httpx.AsyncClient, job_id: int, url: str, depth: int) -> Optional[Dict]:
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
            crawled_url = CrawledUrl(url=url, title=title, crawl_job_id=job_id)
            self.db.add(crawled_url)
            self.db.commit()
            
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
