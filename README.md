# Web Crawler API

A high-performance web crawler API built with Python, Flask, and PostgreSQL that efficiently fetches and stores links from websites.

## Project Overview

This project implements a web crawler service that:

- Crawls websites starting from a seed URL and follows links to discover more pages
- Extracts and stores page titles and URLs in a PostgreSQL database
- Provides a RESTful API to start crawl jobs and retrieve results
- Implements pagination for efficient retrieval of large datasets
- Uses asynchronous processing to improve performance
- Includes automatic cleanup of old data to prevent database bloat

## Tech Stack

- **Python 3.11**: Modern Python version with improved performance and features
- **Flask**: Lightweight web framework for building the API endpoints
- **PostgreSQL**: Robust relational database for persistent storage
- **SQLAlchemy**: ORM (Object-Relational Mapping) for database interactions
- **BeautifulSoup4**: HTML parsing library for extracting data from web pages
- **httpx**: Asynchronous HTTP client for efficient web requests
- **APScheduler**: Task scheduler for periodic database cleanup
- **Gunicorn**: WSGI HTTP server for production deployment

## Why This Tech Stack?

- **Flask**: Chosen for its simplicity, flexibility, and extensive ecosystem of extensions. It's lightweight yet powerful enough for our API needs.
- **PostgreSQL**: Provides robust data integrity, excellent performance for complex queries, and supports advanced indexing for fast lookups.
- **Asynchronous Processing**: Using httpx and asyncio allows the crawler to process multiple URLs concurrently, significantly improving performance.
- **SQLAlchemy**: Provides a high-level, Pythonic API for database operations while allowing for complex queries when needed.
- **APScheduler**: Enables automatic background tasks like database cleanup without requiring separate cron jobs.
- **BeautifulSoup4**: Industry-standard HTML parsing library with excellent performance and ease of use.

## Features

- **Asynchronous Crawling**: Process multiple URLs concurrently for improved performance
- **Rate Limiting**: Built-in mechanisms to prevent overloading target websites
- **Domain Restriction**: Crawls only stay within the original website domain
- **Depth Control**: Configure the maximum crawl depth to control the scope
- **Automatic Cleanup**: Periodically removes old crawl jobs to prevent database bloat
- **Detailed API Documentation**: Interactive documentation available at `/docs`
- **Pagination**: Efficiently retrieve large result sets with pagination
- **Error Handling**: Robust error handling for various HTTP status codes and network issues

## Setup Instructions

### Prerequisites

- Python 3.11 or higher
- PostgreSQL database (Railway PostgreSQL is currently configured)

### Environment Variables

The application uses the following environment variables:

- `DATABASE_URL`: PostgreSQL connection string (required)
  - Currently using Railway PostgreSQL: `postgresql://postgres:***@crossover.proxy.rlwy.net:32028/railway`
- `SESSION_SECRET`: Secret key for session management (optional)

### Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd web-crawler-api
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up the PostgreSQL database:
   ```bash
   # Create a database in PostgreSQL
   createdb web_crawler
   
   # Set environment variable
   export DATABASE_URL="postgresql://username:password@localhost/web_crawler"
   ```

4. Run the application:
   ```bash
   # For development
   python main.py
   
   # For production
   gunicorn --bind 0.0.0.0:5000 main:app
   ```

## API Endpoints

### Start a Crawl Job

```
POST /api/crawl
```

Request Body:
```json
{
  "seed_url": "https://example.com"
}
```

Response:
```json
{
  "id": 1,
  "seed_url": "https://example.com",
  "status": "IN_PROGRESS",
  "created_at": "2023-04-01T12:00:00Z",
  "error_message": null
}
```

### Get Crawl Job Status

```
GET /api/crawl/{job_id}
```

Response:
```json
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
```

### Get Paginated URLs for a Crawl Job

```
GET /api/crawl/{job_id}/urls?page=1&page_size=50
```

Response:
```json
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
```

### List All Crawl Jobs

```
GET /api/crawl?limit=10&offset=0
```

Response:
```json
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
```

## Usage Examples

### Starting a Crawl Job

```bash
curl -X POST http://localhost:5000/api/crawl \
  -H "Content-Type: application/json" \
  -d '{"seed_url": "https://quotes.toscrape.com/"}'
```

### Checking Job Status

```bash
curl http://localhost:5000/api/crawl/1
```

### Getting Paginated Results

```bash
curl "http://localhost:5000/api/crawl/1/urls?page=1&page_size=10"
```

## Deployment

The application is configured to run on Replit and can be deployed with a single click. It is using a Railway PostgreSQL database for persistent storage across deployments.

## Accessing the Data

The web crawler stores all data in a PostgreSQL database. There are two primary ways to access this data:

### 1. Using the API Endpoints

As described in the API Endpoints section above, you can access the crawled data through HTTP requests:

```bash
# Get information about a specific crawl job
curl http://localhost:5000/api/crawl/5

# Get paginated list of URLs for a specific job
curl "http://localhost:5000/api/crawl/5/urls?page=1&page_size=10"

# List all crawl jobs
curl "http://localhost:5000/api/crawl?limit=10&offset=0"
```

### 2. Direct Database Access

You can also query the PostgreSQL database directly using SQL to perform more complex analysis:

#### Example Queries:

```sql
-- Get all crawl jobs
SELECT * FROM crawl_jobs;

-- Get the number of URLs crawled for each job
SELECT 
    cj.id as job_id, 
    cj.seed_url, 
    cj.status, 
    COUNT(cu.id) as urls_crawled
FROM 
    crawl_jobs cj
LEFT JOIN 
    crawled_urls cu ON cj.id = cu.crawl_job_id
GROUP BY 
    cj.id, cj.seed_url, cj.status
ORDER BY 
    cj.id;

-- Find URLs containing specific keywords
SELECT 
    id, 
    url, 
    title
FROM 
    crawled_urls
WHERE 
    url LIKE '%keyword%' AND crawl_job_id = 5;
```

In Replit, you can run SQL queries using the built-in SQL tool or by connecting to the PostgreSQL database using the environment variables provided.

## Limitations

- The crawler respects robots.txt rules and may be blocked by websites with strict anti-bot measures
- Maximum crawl depth is set to 2 by default to prevent excessive crawling
- Total number of crawled URLs is limited to 1000 per job to prevent infinite crawling
- Some websites may return 403 Forbidden errors if they detect automated crawling

## Future Enhancements

- Support for authenticated crawling (for websites requiring login)
- Advanced content extraction beyond just titles
- Support for sitemaps to improve crawling efficiency
- Full-text search capabilities for crawled content
- Analytics dashboard for visualizing crawl results

## License

[MIT License](LICENSE)
