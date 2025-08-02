import enum
import gzip
import io
import json
import os

import requests

DATA_DIR = "./data"
GITHUB_DIR = "./data/git_repo"
TMP_DIR = "./data/tmp"
PDF_DIR = "./data/PDF"
OUTPUT_DIR = "./data/output"

from extract_code import check_for_plotting_libraries, clone_repo, find_python_files
from extract_images import extract_images_from_pdf


class Format(str, enum.Enum):
    json = "json"
    json_gz = "json.gz"


def load(filename, fmt=Format.json, encoding="utf-8"):
    if fmt == Format.json:
        with io.open(filename, mode="r", encoding=encoding) as fp:
            return json.load(fp)
    elif fmt == Format.json_gz:
        with gzip.open(filename, mode="rb") as fp:
            return json.loads(fp.read().decode(encoding))
    else:
        print("error")


def process_repo(url: str):
    repo_path = clone_repo(url, TMP_DIR)
    py_files = find_python_files(repo_path)
    for py_file in py_files:
        content = py_file.read_text(encoding="utf-8", errors="ignore")
        if not check_for_plotting_libraries(content):
            continue

        os.makedirs(f"{GITHUB_DIR}/{repo_path.name}", exist_ok=True)
        orig_code_output_file = f"{GITHUB_DIR}/{repo_path.name}/{py_file.stem}.py"

        with open(orig_code_output_file, "w", encoding="utf8") as f:
            f.write(content)

        print(f"-> Extracted plot code to {orig_code_output_file}")


def download_pdf(download_link: str, name: str):
    pdf_response = requests.get(download_link, stream=True)
    pdf_filename = os.path.join(PDF_DIR, name + ".pdf")
    with open(pdf_filename, "wb") as f:
        for chunk in pdf_response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
    return pdf_filename


if __name__ == "__main__":
    data_points = load("./links-between-papers-and-code.json.gz", fmt=Format.json_gz)
    print(data_points[0])

    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(GITHUB_DIR, exist_ok=True)
    os.makedirs(TMP_DIR, exist_ok=True)
    os.makedirs(PDF_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    counter = 0
    counter_file = "./counter.txt"
    if os.path.exists(counter_file):
        try:
            with open(counter_file, "r") as file:
                counter = int(file.read())
        except Exception as e:
            print(e)

    for index in range(counter, len(data_points)):
        if index % 10 == 0:
            with open(counter_file, "w") as file:
                file.write(str(counter))

        data = data_points[index]
        guthub_url = data["repo_url"]
        pdf_url = data["paper_url_pdf"]
        repo_name = guthub_url.rstrip("/").split("/")[-1]

        process_repo(guthub_url)
        pdf_filename = download_pdf(pdf_url, repo_name)
        extract_images_from_pdf(pdf_filename, os.path.join(OUTPUT_DIR, repo_name))

        counter += 1
