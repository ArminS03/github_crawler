import os
import fitz


def extract_images_from_pdf(pdf_path, output_folder):
    doc = fitz.open(pdf_path)
    for page_num, page in enumerate(doc, start=1):
        images = page.get_images(full=True)
        for img_index, img in enumerate(images, start=1):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            image_ext = base_image["ext"]
            image_filename = f"page{page_num}_img{img_index}.{image_ext}"
            image_path = os.path.join(output_folder, image_filename)
            with open(image_path, "wb") as img_file:
                img_file.write(image_bytes)
    doc.close()


def process_pdfs(gather_data_folder, pdfs_folder):
    for folder_name in os.listdir(gather_data_folder):
        folder_path = os.path.join(gather_data_folder, folder_name)
        if not os.path.isdir(folder_path):
            continue

        pdf_filename = f"{folder_name}.pdf"
        pdf_path = os.path.join(pdfs_folder, pdf_filename)

        if os.path.exists(pdf_path):
            print(f"Processing {pdf_filename}...")
            extract_images_from_pdf(pdf_path, folder_path)
        else:
            print(f"PDF not found for folder: {folder_name}")


# Set your paths
gather_data_folder = "./gather_data"
pdfs_folder = "./PDFs"

process_pdfs(gather_data_folder, pdfs_folder)
