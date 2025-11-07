
import requests
import re
from collections import deque
from bs4 import BeautifulSoup, Comment
from urllib.parse import urljoin, urlparse

def is_valid_url(url):
    """
    Checks whether `url` is a valid URL.
    """
    parsed = urlparse(url)
    return bool(parsed.netloc) and bool(parsed.scheme)

def get_all_website_links(url):
    """
    Returns all URLs that are found on `url` in which it belongs to the same website
    """
    urls = set()
    domain_name = urlparse(url).netloc
    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.content, "html.parser")
        for a_tag in soup.findAll("a"):
            href = a_tag.attrs.get("href")
            if href == "" or href is None:
                continue
            href = urljoin(url, href)
            parsed_href = urlparse(href)
            href = parsed_href.scheme + "://" + parsed_href.netloc + parsed_href.path
            if not is_valid_url(href):
                continue
            # More robust domain check
            if urlparse(href).netloc != domain_name:
                continue
            urls.add(href)
    except requests.exceptions.RequestException as e:
        print(f"Error getting links from {url}: {e}")
    return urls

def get_emails(url):
    """
    Returns all email addresses found on a single web page.
    """
    try:
        response = requests.get(url)
        emails = set(re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", response.text))
        return emails
    except requests.exceptions.RequestException as e:
        print(f"Error getting emails from {url}: {e}")
        return set()

def get_comments(url):
    """
    Returns all comments on a single web page.
    """
    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.content, 'html.parser')
        comments = soup.find_all(string=lambda text: isinstance(text, Comment))
        return comments
    except requests.exceptions.RequestException as e:
        print(f"Error getting comments from {url}: {e}")
        return []

def crawl(url, max_urls=30):
    """
    Crawls a web page and extracts all links, emails, and comments using an iterative approach.
    """
    if not is_valid_url(url):
        print(f"Invalid starting URL: {url}")
        return set(), set(), []

    queue = deque([url])
    visited = {url}

    emails = set()
    comments = []

    # Process the starting URL first
    print(f"Crawling: {url}")
    found_emails = get_emails(url)
    if found_emails:
        emails.update(found_emails)
    found_comments = get_comments(url)
    if found_comments:
        comments.extend(found_comments)

    while queue and len(visited) < max_urls:
        current_url = queue.popleft()

        links = get_all_website_links(current_url)

        for link in links:
            if link not in visited and len(visited) < max_urls:
                visited.add(link)
                queue.append(link)

                print(f"Crawling: {link}")
                found_emails = get_emails(link)
                if found_emails:
                    emails.update(found_emails)
                found_comments = get_comments(link)
                if found_comments:
                    comments.extend(found_comments)

    return visited, emails, comments

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Web Crawler and Information Extractor")
    parser.add_argument("url", help="The URL to crawl.")
    parser.add_argument("-m", "--max-urls", help="Number of max URLs to crawl, default is 30.", default=30, type=int)

    args = parser.parse_args()
    url = args.url
    max_urls = args.max_urls

    crawled_urls, emails, comments = crawl(url, max_urls=max_urls)

    print(f"\n[+] Total URLs crawled: {len(crawled_urls)}")
    print("[+] URLs:")
    for crawled_url in crawled_urls:
        print(crawled_url)

    print(f"\n[+] Total Emails found: {len(emails)}")
    print("[+] Emails:")
    for email in emails:
        print(email)

    print(f"\n[+] Total Comments found: {len(comments)}")
    print("[+] Comments:")
    for comment in comments:
        print(comment.strip())
