
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

def scan_sql_injection(url):
    """
    Scans a given URL for SQL injection vulnerabilities by submitting malicious payloads to forms.
    """
    sqli_payloads = ["'", "\"", " ' OR 1=1 --", " OR 1=1 --", " OR '1'='1' --"]
    vulnerabilities = []

    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.content, 'html.parser')
        forms = soup.find_all('form')

        for form in forms:
            action = form.get('action')
            method = form.get('method', 'get').lower()
            inputs = form.find_all(['input', 'textarea'])

            for payload in sqli_payloads:
                data = {}
                for input_tag in inputs:
                    name = input_tag.get('name')
                    input_type = input_tag.get('type', 'text')
                    if name:
                        if input_type == 'text':
                            data[name] = payload
                        else:
                            data[name] = 'test'

                try:
                    if method == 'post':
                        res = requests.post(urljoin(url, action), data=data)
                    else:
                        res = requests.get(urljoin(url, action), params=data)

                    if any(error in res.text.lower() for error in ['sql', 'mysql', 'syntax', 'warning']):
                        vulnerabilities.append(f"Potential SQLi vulnerability found at {url} with payload: {payload}")
                except requests.exceptions.RequestException as e:
                    print(f"Error submitting form on {url}: {e}")

    except requests.exceptions.RequestException as e:
        print(f"Error fetching URL {url}: {e}")

    return vulnerabilities

def scan_xss(url):
    """
    Scans a given URL for XSS vulnerabilities by submitting test scripts to forms.
    """
    xss_payloads = ["<script>alert('XSS')</script>", "<img src=x onerror=alert('XSS')>", "<body onload=alert('XSS')>"]
    vulnerabilities = []

    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.content, 'html.parser')
        forms = soup.find_all('form')

        for form in forms:
            action = form.get('action')
            method = form.get('method', 'get').lower()
            inputs = form.find_all(['input', 'textarea'])

            for payload in xss_payloads:
                data = {}
                for input_tag in inputs:
                    name = input_tag.get('name')
                    input_type = input_tag.get('type', 'text')
                    if name:
                        if input_type == 'text':
                            data[name] = payload
                        else:
                            data[name] = 'test'

                try:
                    if method == 'post':
                        res = requests.post(urljoin(url, action), data=data)
                    else:
                        res = requests.get(urljoin(url, action), params=data)

                    if payload in res.text:
                        vulnerabilities.append(f"Potential XSS vulnerability found at {url} with payload: {payload}")
                except requests.exceptions.RequestException as e:
                    print(f"Error submitting form on {url}: {e}")

    except requests.exceptions.RequestException as e:
        print(f"Error fetching URL {url}: {e}")

    return vulnerabilities

def discover_directories_and_files(url, wordlist_path='wordlist.txt'):
    """
    Discovers hidden directories and files on a web server using a wordlist.
    """
    discovered_paths = []
    try:
        with open(wordlist_path, 'r') as f:
            for line in f:
                path = line.strip()
                full_url = urljoin(url, path)
                try:
                    response = requests.get(full_url, timeout=5)
                    if response.status_code == 200:
                        discovered_paths.append(full_url)
                except requests.exceptions.RequestException:
                    continue
    except FileNotFoundError:
        print(f"Wordlist not found at {wordlist_path}")
    return discovered_paths

def discover_subdomains(url, wordlist_path='subdomains.txt'):
    """
    Discovers subdomains of a given domain using a wordlist.
    """
    discovered_subdomains = []
    domain = urlparse(url).netloc

    try:
        with open(wordlist_path, 'r') as f:
            for line in f:
                subdomain = line.strip()
                full_url = f"http://{subdomain}.{domain}"
                try:
                    requests.get(full_url, timeout=5)
                    discovered_subdomains.append(full_url)
                except requests.exceptions.RequestException:
                    continue
    except FileNotFoundError:
        print(f"Subdomain wordlist not found at {wordlist_path}")

    return discovered_subdomains

def crawl(url, max_urls=30):
    """
    Crawls a web page and extracts all links, emails, and comments using an iterative approach.
    """
    if not is_valid_url(url):
        print(f"Invalid starting URL: {url}")
        return set(), set(), [], [], [], [], []

    queue = deque([url])
    visited = {url}

    emails = set()
    comments = []
    sqli_vulnerabilities = []
    xss_vulnerabilities = []

    # Discover directories and files
    discovered_paths = discover_directories_and_files(url)

    # Discover subdomains
    discovered_subdomains = discover_subdomains(url)

    # Process the starting URL first
    print(f"Crawling: {url}")
    found_emails = get_emails(url)
    if found_emails:
        emails.update(found_emails)
    found_comments = get_comments(url)
    if found_comments:
        comments.extend(found_comments)
    found_sqli = scan_sql_injection(url)
    if found_sqli:
        sqli_vulnerabilities.extend(found_sqli)
    found_xss = scan_xss(url)
    if found_xss:
        xss_vulnerabilities.extend(found_xss)

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
                found_sqli = scan_sql_injection(link)
                if found_sqli:
                    sqli_vulnerabilities.extend(found_sqli)
                found_xss = scan_xss(link)
                if found_xss:
                    xss_vulnerabilities.extend(found_xss)

    return visited, emails, comments, sqli_vulnerabilities, xss_vulnerabilities, discovered_paths, discovered_subdomains

def generate_report(crawled_urls, emails, comments, sqli_vulnerabilities, xss_vulnerabilities, discovered_paths, discovered_subdomains):
    """
    Generates a report of the crawl and scan results.
    """
    with open("report.txt", "w") as f:
        f.write("Crawl and Scan Report\n")
        f.write("="*30 + "\n\n")

        f.write(f"[+] Total URLs crawled: {len(crawled_urls)}\n")
        f.write("[+] URLs:\n")
        for url in crawled_urls:
            f.write(f"- {url}\n")
        f.write("\n")

        f.write(f"[+] Total Emails found: {len(emails)}\n")
        f.write("[+] Emails:\n")
        for email in emails:
            f.write(f"- {email}\n")
        f.write("\n")

        f.write(f"[+] Total Comments found: {len(comments)}\n")
        f.write("[+] Comments:\n")
        for comment in comments:
            f.write(f"- {comment.strip()}\n")
        f.write("\n")

        if sqli_vulnerabilities:
            f.write(f"[!] SQL Injection Vulnerabilities Found: {len(sqli_vulnerabilities)}\n")
            for vuln in sqli_vulnerabilities:
                f.write(f"- {vuln}\n")
            f.write("\n")

        if xss_vulnerabilities:
            f.write(f"[!] XSS Vulnerabilities Found: {len(xss_vulnerabilities)}\n")
            for vuln in xss_vulnerabilities:
                f.write(f"- {vuln}\n")
            f.write("\n")

        if discovered_paths:
            f.write(f"[+] Discovered Directories and Files: {len(discovered_paths)}\n")
            for path in discovered_paths:
                f.write(f"- {path}\n")
            f.write("\n")

        if discovered_subdomains:
            f.write(f"[+] Discovered Subdomains: {len(discovered_subdomains)}\n")
            for subdomain in discovered_subdomains:
                f.write(f"- {subdomain}\n")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Web Crawler and Information Extractor")
    parser.add_argument("url", help="The URL to crawl.")
    parser.add_argument("-m", "--max-urls", help="Number of max URLs to crawl, default is 30.", default=30, type=int)

    args = parser.parse_args()
    url = args.url
    max_urls = args.max_urls

    crawled_urls, emails, comments, sqli_vulnerabilities, xss_vulnerabilities, discovered_paths, discovered_subdomains = crawl(url, max_urls=max_urls)

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

    if sqli_vulnerabilities:
        print(f"\n[!] SQL Injection Vulnerabilities Found: {len(sqli_vulnerabilities)}")
        for vuln in sqli_vulnerabilities:
            print(vuln)

    if xss_vulnerabilities:
        print(f"\n[!] XSS Vulnerabilities Found: {len(xss_vulnerabilities)}")
        for vuln in xss_vulnerabilities:
            print(vuln)

    if discovered_paths:
        print(f"\n[+] Discovered Directories and Files: {len(discovered_paths)}")
        for path in discovered_paths:
            print(path)

    if discovered_subdomains:
        print(f"\n[+] Discovered Subdomains: {len(discovered_subdomains)}")
        for subdomain in discovered_subdomains:
            print(subdomain)

    generate_report(crawled_urls, emails, comments, sqli_vulnerabilities, xss_vulnerabilities, discovered_paths, discovered_subdomains)
    print("\n[+] Report generated and saved to report.txt")
