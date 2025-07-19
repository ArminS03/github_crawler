import requests
from bs4 import BeautifulSoup
from tqdm import tqdm
import pandas as pd
import os
import time

def crawl_page(page, pdf_dir):
    base_url = "https://paperswithcode.com/latest"
    results = []

    url = f"{base_url}?page={page}"
    response = requests.get(url)
    if response.status_code != 200:
        print(f"Failed to fetch page {page}")
        print(response.content)
        return results
    print(url)
    soup = BeautifulSoup(response.text, "html.parser")
    papers = soup.find_all("div", class_="infinite-item")
    os.makedirs(pdf_dir, exist_ok=True)
    for paper in tqdm(papers, total=len(papers)):
        time.sleep(2)
        page_link = paper.find("a", class_="badge badge-dark")
        github_url = None
        pdf_url = None
        local_pdf_path = None

        # Get GitHub repo URL
        if page_link:
            page_url = page_link.get("href", "")
            if page_url.startswith("/"):
                page_url = "https://paperswithcode.com" + page_url
            page_resp = requests.get(page_url)
            if page_resp.status_code == 200:
                page_soup = BeautifulSoup(page_resp.text, "html.parser")
                github_a = page_soup.find("a", href=lambda x: x and "github.com" in x)
                if github_a:
                    github_url = github_a["href"].strip()
            else:
                print(page_resp.content)
                continue
            
            try:
                download_a = page_soup.find("a", href=lambda x: x and ".pdf" in x)
                download_link = download_a["href"].strip()
                pdf_url = download_link
                pdf_response = requests.get(download_link, stream=True)
                pdf_filename = os.path.join(pdf_dir, github_url.split("/")[-1] + ".pdf")
                with open(pdf_filename, "wb") as f:
                    for chunk in pdf_response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                local_pdf_path = pdf_filename
            except Exception as e:
                print(f"Failed to download PDF: {e}")

        if github_url or pdf_url:
            results.append({
                "github_url": github_url,
                "pdf_url": pdf_url,
                "local_pdf_path": local_pdf_path
            })
    return results

def crawl_paperswithcode(num_pages, output_csv, pdf_dir):
    try:
        df = pd.read_csv(output_csv)
        existing_urls = set(df['github_url'].dropna())
    except FileNotFoundError:
        df = pd.DataFrame(columns=['github_url', 'pdf_url', 'local_pdf_path'])
        existing_urls = set()

    for page in range(1, num_pages + 1):
        page_results = []
        results = crawl_page(page, pdf_dir=pdf_dir)
        
        for result in results:
            if result['github_url'] and result['github_url'] not in existing_urls:
                page_results.append(result)
                existing_urls.add(result['github_url'])
        
        if page_results:
            new_df = pd.DataFrame(page_results)
            df = pd.concat([df, new_df], ignore_index=True)
            df.to_csv(output_csv, index=False)
            print(f"Saved {len(page_results)} new results to {output_csv}")
        else:
            print(f"No new results found on page {page}")

    print(f"Final results saved to {output_csv}, total entries: {len(df)}")

if __name__ == "__main__":
    crawl_paperswithcode(num_pages=30, output_csv="crawled_links.csv", pdf_dir="./PDFs")