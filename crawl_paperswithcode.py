import requests
from bs4 import BeautifulSoup
from tqdm import tqdm
import time

def crawl_page(page):
    base_url = "https://paperswithcode.com/latest"
    github_links = set()

    url = f"{base_url}?page={page}"
    response = requests.get(url)
    if response.status_code != 200:
        print(f"Failed to fetch page {page}")
        return github_links
    print(url)
    soup = BeautifulSoup(response.text, "html.parser")
    papers = soup.find_all("div", class_="infinite-item")
    for paper in tqdm(papers, total=len(papers)):
        code_link = paper.find("a", class_="badge badge-dark")
        if code_link:
            code_page_url = code_link.get("href", "")
            if code_page_url.startswith("/"):
                code_page_url = "https://paperswithcode.com" + code_page_url
            code_page_resp = requests.get(code_page_url)
            if code_page_resp.status_code == 200:
                code_page_soup = BeautifulSoup(code_page_resp.text, "html.parser")
                github_a = code_page_soup.find("a", href=lambda x: x and "github.com" in x)
                if github_a:
                    github_links.add(github_a["href"].strip())
            else:
                print("Failed to fetch code page for paper")
                continue
    return github_links

def crawl_paperswithcode_github_links(num_pages, output_file="github_links.txt"):
    all_urls = set()
    for page in range(1, num_pages + 1):
        page_links = crawl_page(page)
        all_urls.update(page_links)
        print(all_urls)
        with open(output_file, "a") as f:
            for link in page_links:
                f.write(link + "\n")
        print(f"Saved new links from page {page}")

if __name__ == "__main__":
    crawl_paperswithcode_github_links(num_pages=10, output_file="github_links.txt")