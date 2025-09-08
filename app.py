from pdf2image import convert_from_path
import easyocr
from PIL import Image
from docx2pdf import convert
from skimage.metrics import structural_similarity as ssim
import cv2
import os
from pydantic import BaseModel
import json
from groq import Groq
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

def pdf_to_PNG(path):
    pages = convert_from_path(path, dpi=300)
    pngPath = r"temporary_files\output.png"
    index = 0
    while os.path.isfile(pngPath):
        pngPath = rf"temporary_files\output{index}.png"
        index += 1
    pages[0].save(pngPath, "PNG")
    return pngPath 
    
def jpg_to_PNG(path):
    img = Image.open(path)
    pngPath = r"temporary_files\output.png"
    index = 0
    while os.path.isfile(pngPath):
        pngPath = rf"temporary_files\output{index}.png"
        index += 1
    img.convert("RGB").save(pngPath, "PNG")
    return pngPath

def convert_to_png(file_path):
    if file_path.lower().endswith((".jpg", ".jpeg", ".bmp", ".tiff", ".gif")):
        return jpg_to_PNG(file_path)
    
    elif file_path.lower().endswith(".pdf"):
        return pdf_to_PNG(file_path)
    
    elif file_path.lower().endswith(".docx"):
        # DOCX -> PDF -> PNG
        convert(file_path, r"temporary_files\temp.pdf")
        return pdf_to_PNG(r"temporary_files\temp.pdf")
    else:
        raise ValueError("Unsupported file format")
        
def get_text(path):
    reader = easyocr.Reader(['en'])
    results = reader.readtext(path)
    ans = ""
    for (bbox, text, prob) in results:
        print(f"Detected text: {text} (Confidence: {prob:.2f})")
        ans += " " + text
    return ans
    
file_path = "test2.jpg" 
base_certificate = "base_certificate.jpg"
if file_path.lower().endswith(".png") == False:
    file_path = convert_to_png(file_path)

if base_certificate.lower().endswith(".png") == False:
    base_certificate = convert_to_png(base_certificate)

img1 = cv2.imread(file_path, cv2.IMREAD_GRAYSCALE)
img2 = cv2.imread(base_certificate, cv2.IMREAD_GRAYSCALE)

img2 = cv2.resize(img2, (img1.shape[1], img1.shape[0]))

score, diff = ssim(img1, img2, full=True)
print("Structural Similarity (SSIM):", score)

certificate_text = get_text(file_path)

class Student_Data(BaseModel):
    student_name : str
    enrollment_number : str
    cgpa : float

client = Groq(
    api_key = os.getenv("GROQ_API_KEY"),
)

response = client.chat.completions.create(
    messages=[
        {"role": "system", "content": "Extract the name of student, enrollment number and cgpa in json format.\n"
         f" The JSON object must use the schema: {json.dumps(Student_Data.model_json_schema(), indent=2)}"},
        {
            "role": "user",
            "content": f"use this {certificate_text}"
        },
    ],
    model="openai/gpt-oss-120b",
    temperature=0,
    stream=False,
    response_format={"type": "json_object"},
)

target_data = Student_Data.model_validate_json(response.choices[0].message.content)
print(target_data.enrollment_number)
print(target_data.student_name)
print(target_data.cgpa)
query = {
    "enrollmentNo": target_data.enrollment_number,
    "name": {"$regex": f"^{target_data.student_name}$", "$options": "i"},  # case-insensitive match
    "cgpa": target_data.cgpa
}

client = MongoClient(os.getenv("MONGO_API_KEY"))
db = client["test"]
collection = db["students"]  
record = collection.find_one(query)

if record:
    print("Record found:", record)
else:
    print("No matching record found")