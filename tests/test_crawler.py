import pytest
import httpx
from unittest.mock import Mock, patch, AsyncMock
from bs4 import BeautifulSoup

from app.crawler import WebCrawler
from app.models import CrawlJob, CrawlStatus
from app.schemas import CrawlJobCreate

# Mock HTML content with links
MOCK_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Test Page</title>
</head>
<body>
    <a href="https://example.com/page1">Link 1</a>
    <a href="https://example.com/page2">Link 2</a>
    <a href="https://example.com/page3">Link 3</a>
    <a href="https://other-domain.com/page4">External Link</a>
    <a href="/relative-link">Relative Link</a>
</body>
</html>
"""

@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    session = Mock()
    session.commit = Mock()
    session.add = Mock()
    session.refresh = Mock()
    
    # Mock query functionality
    mock_query = Mock()
    session.query = Mock(return_value=mock_query)
    mock_filter = Mock()
    mock_query.filter = Mock(return_value=mock_filter)
    mock_filter.first = Mock()
    
    return session

@pytest.mark.asyncio
async def test_process_url(mock_db_session):
    """Test the _process_url method of WebCrawler."""
    # Create a mock crawler instance
    crawler = WebCrawler(db=mock_db_session)
    
    # Create a mock httpx client and response
    mock_client = AsyncMock()
    mock_response = AsyncMock()
    mock_response.text = MOCK_HTML
    mock_response.raise_for_status = Mock()
    mock_client.get = AsyncMock(return_value=mock_response)
    
    # Call the method with test data
    result = await crawler._process_url(
        client=mock_client,
        job_id=1,
        url="https://example.com",
        depth=0
    )
    
    # Verify the client was called correctly
    mock_client.get.assert_called_once_with("https://example.com", follow_redirects=True)
    
    # Check that the URL was stored in the database
    mock_db_session.add.assert_called_once()
    mock_db_session.commit.assert_called_once()
    
    # Check the returned URLs (should only include URLs from the same domain)
    assert result is not None
    assert "depth" in result
    assert "new_urls" in result
    
    # There should be 3 internal URLs plus 1 relative URL that gets absolutized
    expected_urls = {
        "https://example.com/page1",
        "https://example.com/page2", 
        "https://example.com/page3",
        "https://example.com/relative-link"
    }
    
    # Convert lists to sets for comparison (order doesn't matter)
    actual_urls = set(result["new_urls"])
    
    # Check if expected URLs are found in the results
    assert len(actual_urls.intersection(expected_urls)) == 4
    
    # External domain URL should not be included
    assert "https://other-domain.com/page4" not in actual_urls
