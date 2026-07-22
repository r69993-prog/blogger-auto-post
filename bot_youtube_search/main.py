import os
import json
import requests
from googleapiclient.discovery import build
import google.genai as genai

# Load Config
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config = json.load(f)

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def get_youtube_videos(query, max_results=1):
    youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
    request = youtube.search().list(
        q=query,
        part="snippet",
        maxResults=max_results,
        type="video"
    )
    response = request.execute()
    return response.get("items", [])

def generate_article(title, description, language="th"):
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    if language == "en":
        prompt = f"""
Write a comprehensive, professional blog post based on this YouTube video.
Title: {title}
Description: {description}

Requirements:
- Article MUST be entirely in English language.
- Provide a clear introduction, detailed body paragraphs explaining the concept, key takeaways, and a conclusion.
- Do NOT use Markdown headers or bold text formatting. Use plain clean HTML paragraphs (<p>).
"""
    else:
        prompt = f"""
เขียนบทความบล็อกฉบับเต็มอย่างละเอียดยาวและเป็นมืออาชีพจากวิดีโอ YouTube นี้
หัวข้อ: {title}
รายละเอียด: {description}

ข้อกำหนด:
- บทความต้องเป็นภาษาไทยทั้งหมด 100%
- สรุปเนื้อหาสำคัญ อธิบายรายละเอียดอย่างชัดเจน อธิบายความเป็นมา ข้อดี ข้อเสีย และสรุปภาพรวม
- ห้ามใช้ Markdown ให้ใช้แท็ก HTML <p> สำหรับย่อหน้าทั่วไปเท่านั้น
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    return response.text

def post_to_blogger(blog_id, title, content_html, access_token):
    url = f"https://www.googleapis.com/blogger/v3/blogs/{blog_id}/posts/"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    data = {
        "kind": "blogger#post",
        "title": title,
        "content": content_html
    }
    res = requests.post(url, headers=headers, json=data)
    return res.status_code, res.json()

def main():
    print("Starting YouTube Search Bot...")
    # Code execution flow
    print("YouTube Search Bot completed.")

if __name__ == "__main__":
    main()
