import csv
import enum
import gzip
import io
import json
import os
import shutil
import stat
from pathlib import Path

import pandas as pd
import requests

DATA_DIR = Path("./data")
GITHUB_DIR = Path("./data/git_snippets")
TMP_DIR = Path("./data/tmp")
PDF_DIR = Path("./data/PDF")
OUTPUT_DIR = Path("./data/output")
IMAGE_DIR = Path("./data/images")
CSV_FILE = "./manifest.csv"
CSV_FIELDS = [
    "index",
    "repo_url",
    "paper_url_pdf",
    "repo_name",
    "description",
    "status",
    "error",
]

from extract_code import check_for_plotting_libraries, clone_repo, find_python_files
from extract_images import extract_images_from_pdf

# from generate_dataset_vlm import process_project


class Format(str, enum.Enum):
    json = "json"
    json_gz = "json.gz"


def on_rm_error(func, path, exc_info):
    os.chmod(path, stat.S_IWRITE)
    func(path)


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
    flag = False
    for py_file in py_files:
        content = py_file.read_text(encoding="utf-8", errors="ignore")
        if not check_for_plotting_libraries(content):
            continue
        flag = True
        os.makedirs(f"{GITHUB_DIR}/{repo_path.name}", exist_ok=True)
        orig_code_output_file = f"{GITHUB_DIR}/{repo_path.name}/{py_file.stem}.py"

        with open(orig_code_output_file, "w", encoding="utf8") as f:
            f.write(content)
    if not flag:
        shutil.rmtree(repo_path, onerror=on_rm_error)
        raise ValueError("No Plotting Code!")


def download_pdf(download_link: str, name: str):
    pdf_response = requests.get(download_link, stream=True)
    pdf_filename = os.path.join(PDF_DIR, name + ".pdf")

    if os.path.exists(pdf_filename):
        return pdf_filename

    with open(pdf_filename, "wb") as f:
        for chunk in pdf_response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
    return pdf_filename


if __name__ == "__main__":
    data_points = load("./links-between-papers-and-code.json.gz", fmt=Format.json_gz)

    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            writer.writeheader()

    try:
        df = pd.read_csv(CSV_FILE)
        processed_indices = set(df["index"].tolist())
    except Exception as e:
        print("Error reading CSV log:", e)
        processed_indices = set()

    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(GITHUB_DIR, exist_ok=True)
    os.makedirs(TMP_DIR, exist_ok=True)
    os.makedirs(PDF_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(IMAGE_DIR, exist_ok=True)

    for index in range(len(data_points)):
        # df.loc[df["index"]==0, "status"].iloc[0] == "failed"
        if index in processed_indices:
            continue

        data = data_points[index]
        github_url = data["repo_url"]
        pdf_url = data["paper_url_pdf"]
        repo_name = github_url.rstrip("/").split("/")[-1]
        description = None

        try:
            process_repo(github_url)
            pdf_filename = download_pdf(pdf_url, repo_name)
            extract_images_from_pdf(
                pdf_filename,
                os.path.join(IMAGE_DIR, repo_name),
                os.path.join(IMAGE_DIR, repo_name),
            )
            # description = process_project(repo_name, GITHUB_DIR, OUTPUT_DIR)
            status = "success"
            error = ""
        except Exception as e:
            status = "failed"
            error = str(e)

        # Append to CSV
        with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            writer.writerow(
                {
                    "index": index,
                    "repo_url": github_url,
                    "paper_url_pdf": pdf_url,
                    "repo_name": repo_name,
                    "description": description,
                    "status": status,
                    "error": error[: min(len(error), 100)],
                }
            )
