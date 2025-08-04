import os
import re
from pathlib import Path
from git import Repo
from typing import List
import pandas as pd
from tqdm import tqdm


FIGURE_LIBRARIES = ["matplotlib", "seaborn", "plotly", "bokeh", "altair", "ggplot"]


# class CodeStructure(BaseModel):
#     produces_plot: bool
#     code: str
#     description: str


def clone_repo(url: Path, dest: Path) -> Path:
    repo_name = url.rstrip("/").split("/")[-1]
    clone_path = dest / repo_name

    if clone_path.exists():
        print(f"Repository already exists {repo_name}, skipping clone.")
        return clone_path

    Repo.clone_from(url, clone_path)
    return clone_path


def find_python_files(root: str) -> List[Path]:
    """Find all Python files in the repository."""
    return list(root.rglob("*.py"))


def check_for_plotting_libraries(file_content: str) -> bool:
    """Check if any plotting libraries are imported in the file."""
    import_patterns = []
    for lib in FIGURE_LIBRARIES:
        patterns = [
            rf"import\s+{lib}",
            rf"from\s+{lib}",
            rf"import\s+.*\s+as\s+{lib}\b",
        ]
        import_patterns.extend(patterns)
    return any(
        re.search(pattern, file_content, re.MULTILINE) for pattern in import_patterns
    )


def process_repository(url: str, temp_dir: Path, output_dir: str) -> None:
    repo_path = clone_repo(url, temp_dir)
    py_files = find_python_files(repo_path)
    for py_file in py_files:
        try:
            content = py_file.read_text(encoding="utf-8", errors="ignore")
            if not check_for_plotting_libraries(content):
                continue

            os.makedirs(f"{output_dir}/{repo_path.name}", exist_ok=True)
            orig_code_output_file = (
                f"{output_dir}/{repo_path.name}/{py_file.stem}_code_orig.py"
            )

            with open(orig_code_output_file, "w", encoding="utf8") as f:
                f.write(content)

            print(f"  ↳ Extracted plot code to {orig_code_output_file}")

        except Exception as e:
            print(f"Error processing {py_file}: {e}")


def main():
    file_addr = "crawled_links.csv"
    temp_dir = Path("./tmp")
    output_dir = "./gather_data"
    os.makedirs(output_dir, exist_ok=True)

    # try:
    df = pd.read_csv(file_addr, usecols=["github_url", "local_pdf_path"])

    for index, row in tqdm(df.iterrows(), total=df.shape[0]):
        url = row["github_url"]
        title = row["local_pdf_path"]
        process_repository(url, temp_dir, output_dir)
        # print(f"url: {url} done")

    # finally:
    #     shutil.rmtree(temp_dir)


if __name__ == "__main__":
    main()
