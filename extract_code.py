import os
import re
import shutil
from pathlib import Path
from git import Repo
from openai import OpenAI
import json
from typing import List
from dotenv import load_dotenv
from pydantic import BaseModel


load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

FIGURE_LIBRARIES = [
    'matplotlib', 
    'seaborn', 
    'plotly', 
    'bokeh', 
    'altair',
    'ggplot'
]


class CodeStructure(BaseModel):
    produces_plot: bool
    code: str
    description: str



def clone_repo(url: str, dest: str) -> Path:
    """Clone a repository unless it already exists, then return its path."""
    repo_name = url.rstrip("/").split("/")[-1]
    clone_path = dest / repo_name

    if clone_path.exists():
        print(f"Repository already exists {repo_name}, skipping clone.")
        return clone_path
    print(f"Cloning {url}...")
    try:
        Repo.clone_from(url, clone_path)
    except Exception as e:
        print(f"Error cloning repository: {e}")
        raise

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
            rf"import\s+.*\s+as\s+{lib}\b"
        ]
        import_patterns.extend(patterns)
    return any(re.search(pattern, file_content, re.MULTILINE) for pattern in import_patterns)

def analyze_with_llm(file_content: str) -> dict:
    prompt = f"""
Analyze this Python code and identify ALL parts related to generating plots or figures.
Do not modify or clean up the code, just extract the relevant parts exactly as they appear.

Code to analyze:
{file_content}

1. Confirm whether this snippet generates a plot or figure (yes/no).
2. If yes, return ONLY the minimal code lines needed to generate that figure (including imports if needed).

Respond with fields:
- "produces_plot": "yes" or "no"
- "code": string (the code, or empty string if no)
- "description": string (brief description of what the plot shows)
"""
    resp = client.chat.completions.parse(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a code analysis assistant."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2,
        response_format=CodeStructure,
    )
    event = resp.choices[0].message.parsed
    # print(event.dict())
    return event.model_dump()

def process_repository(url: str, temp_dir: Path, output_dir: str) -> None:
    repo_path = clone_repo(url, temp_dir)
    py_files = find_python_files(repo_path)
    for py_file in py_files:
        try:
            content = py_file.read_text(encoding='utf-8', errors='ignore')
            if not check_for_plotting_libraries(content):
                continue
                
            analysis = analyze_with_llm(content)
            if not analysis["produces_plot"]:
                continue
            print("^"*130)
            os.makedirs(f"{output_dir}/{repo_path.name}", exist_ok=True)
            code_output_file = f"{output_dir}/{repo_path.name}/{py_file.stem}_code.py"
            orig_code_output_file = f"{output_dir}/{repo_path.name}/{py_file.stem}_code_orig.py"
            description_output_file = f"{output_dir}/{repo_path.name}/{py_file.stem}_description.py"
            
            
            
            with open(code_output_file, "w", encoding="utf8") as f:
                f.write(analysis["code"])
                
            with open(orig_code_output_file, "w", encoding="utf8") as f:
                f.write(content)  
                  
            with open(description_output_file, "w", encoding="utf8") as f:
                f.write(analysis['description'])  
                
            print(f"  ↳ Extracted plot code to {code_output_file}")
                
        except Exception as e:
            print(f"Error processing {py_file}: {e}")

def main():
    url_file = "github_links.txt"
    temp_dir = Path("./tmp")
    output_dir = "./gather_data"
    os.makedirs(output_dir, exist_ok=True)

    # try:
    with open(url_file, "r") as f:
        urls = [u.strip() for u in f if u.strip()]
    
    for url in urls:
        process_repository(url, temp_dir, output_dir)
        # print(f"url: {url} done")
            
    # finally:
    #     shutil.rmtree(temp_dir)

if __name__ == "__main__":
    main()
