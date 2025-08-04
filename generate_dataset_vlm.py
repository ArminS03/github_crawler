import os
import glob
import shutil
import re
import enum
from google import genai
from dotenv import load_dotenv
from pydantic import BaseModel
from tqdm import tqdm
import subprocess


from PIL import Image

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


class ScientificFormat(BaseModel):
    explanation: str
    scientific_figures: list[int]


class ReplicatedCode(BaseModel):
    generated: bool
    code: str
    code_description: str


client = genai.Client(api_key=GEMINI_API_KEY)

GEMINI_MODEL = "gemini-2.5-flash"

FIGURE_LIBRARIES = ["matplotlib", "seaborn", "plotly", "bokeh", "altair", "ggplot"]
IMAGE_EXTENSIONS = [".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".gif"]


def group_images_by_page(images):
    page_groups = {}
    pattern = r"page(\d+)_img(\d+)"
    for img in images:
        m = re.search(pattern, os.path.basename(img))
        if m:
            page = int(m.group(1))
            page_groups.setdefault(page, []).append((int(m.group(2)), img))

    for k in page_groups:
        page_groups[k] = sorted(page_groups[k])
    return page_groups


def select_images_from_page_group(img_tuples):
    if len(img_tuples) > 10:
        return [
            img_tuples[0][1],
            img_tuples[1][1],
            img_tuples[-2][1],
            img_tuples[-1][1],
        ]
    return [img[1] for img in img_tuples]


def batch_check_scientific_figures_gemini(image_paths):
    prompt = f"""
You will be given {len(image_paths)} images. Determine which of these images are plotted figures (meaning it was entirely created by any of these libraries: matplotlib, seaborn, plotly, bokeh, altair, ggplot.) and then return their indices. 
The indices you return should start from 0. (The first image has index 0 and the last image index {len(image_paths)-1})
List your answers in the same order as the images are presented.
Include a very brief explanation for your answer.

**If multiple images are very similar in styles (for example bar charts with similar number of lines but different data inside), return the index of only one of them to reduce the post processing burden.**
"""
    contents = [{"text": prompt}]
    for index in range(len(image_paths)):
        img_path = image_paths[index]
        with open(img_path, "rb") as img_file:
            img_bytes = img_file.read()

        contents.append({"text": f"Image {index}"})
        contents.append({"inline_data": {"mime_type": "image/png", "data": img_bytes}})

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[{"role": "user", "parts": contents}],
        config={
            "response_mime_type": "application/json",
            "response_schema": ScientificFormat,
        },
    )
    answers: ScientificFormat = response.parsed
    return answers.scientific_figures


def find_python_files(folder):
    return glob.glob(os.path.join(folder, "*.py"))


def get_image_files(folder):
    return [
        os.path.join(folder, fname)
        for fname in os.listdir(folder)
        if any(fname.lower().endswith(ext) for ext in IMAGE_EXTENSIONS)
        and fname.startswith("page")
        and "_img" in fname
    ]


def process_project(project, github_dir, output_dir):
    extracted_code_path = os.path.join(github_dir, project)
    extracted_image_path = os.path.join(output_dir, project)
    images = get_image_files(extracted_image_path)
    py_files = find_python_files(extracted_code_path)
    if (not images) or (not py_files) or len(images) > 16:
        return None
    print(f"Processing project: {project}")

    page_groups = group_images_by_page(images)
    images_to_check = []

    for img_tuples in page_groups.values():
        images_to_check.extend(select_images_from_page_group(img_tuples))

    batch_size = 4
    confirmed_figures = []
    for i in range(0, len(images_to_check), batch_size):
        batch = images_to_check[i : i + batch_size]
        passed_indices = batch_check_scientific_figures_gemini(batch)
        passed_figures = [
            batch[idx] for idx in passed_indices if idx < len(batch)
        ]
        confirmed_figures.extend(passed_figures)

    codes = []
    for py_file in py_files:
        with open(py_file, "r", encoding="utf-8") as f:
            codes.append(f"# File: {os.path.basename(py_file)}\n{f.read()}")
    all_codes = "\n\n".join(codes)

    for img_path in confirmed_figures:
        
        with open(img_path, "rb") as img_file:
            image_bytes = img_file.read()
        
        prompt = f"""
Given this scientific figure and the Python code below, determine if any of the provided code likely produce this figure? (Some differences in the overall style do NOT matter e.g. color, label name, ...)

If yes, then generate Python code (using matplotlib, seaborn, plotly, bokeh, altair, or ggplot).
You should try to mimic the style of the provided code and image as closely as possible. Furthermore, your code should save the figure to disk as 'output.png'.

If not, just state the reason in the code section instead.

If the code was generated you need to produce a description for the code else return empty. The Description is supposed to represent a request a human would make to generate such a code.
It should NOT be a details explanation of each line but rather an overall request to carry out a certain task.

PYTHON CODE:
{all_codes}
"""

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[
                {
                    "role": "user",
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": "image/png",
                                "data": image_bytes,
                            }
                        },
                    ],
                }
            ],
            config={
                "response_mime_type": "application/json",
                "response_schema": ReplicatedCode,
            },
        )
        parsed_response: ReplicatedCode = response.parsed
        print("^ " * 50)
        print(img_path)
        print(parsed_response.code)
        if (
            not parsed_response
            or not parsed_response.generated
            or not parsed_response.code
        ):
            continue

        out_proj_dir = os.path.join(output_dir, project)
        os.makedirs(out_proj_dir, exist_ok=True)
        base_img = os.path.splitext(os.path.basename(img_path))[0]
        code_filename = f"{base_img}_generated.py"
        image_filename = f"{base_img}_original{os.path.splitext(img_path)[-1]}"
        # Save original image
        shutil.copy(img_path, os.path.join(out_proj_dir, image_filename))
        # Save generated code
        gen_code_path = os.path.join(out_proj_dir, code_filename)

        with open(gen_code_path, "w", encoding="utf-8") as f:
            f.write(parsed_response.code)

        # Run the code to get the image
        subprocess.run(
            ["python", code_filename],
            cwd=out_proj_dir,
            timeout=30,
            check=True,
        )

        # After running, check if output.png was created
        replicated_image_path = os.path.join(
            out_proj_dir, f"{base_img}_replicated.png"
        )
        default_output = os.path.join(out_proj_dir, "output.png")

        if os.path.exists(default_output):
            os.rename(default_output, replicated_image_path)
            print(f"Replicated image saved as: {replicated_image_path}")
        else:
            print(f"[WARN] No output.png found for {img_path}")

        return parsed_response.code_description

def main(data_dir, output_dir):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for root, dirs, files in os.walk(data_dir):
        for project in tqdm(dirs):
            process_project(project, data_dir, output_dir)


if __name__ == "__main__":
    GATHER_DATA = "gather_data"
    OUTPUT_DIR = "matched_outputs"
    main(GATHER_DATA, OUTPUT_DIR)
