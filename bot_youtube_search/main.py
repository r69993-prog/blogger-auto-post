import os
import json
import requests
from googleapiclient.discovery import build
from google import genai

# Load Config
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config = json.load(f)

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
BLOGGER_ACCESS_TOKEN = os.getenv("BLOGGER_ACCESS_TOKEN")

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

def generate_seo_article_and_labels(title, description, language="th"):
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    if language == "en":
        prompt = f"""
Analyze the following YouTube video and generate two things:
1. A comprehensive, professional, and SEO-optimized blog post in English using clean HTML tags (such as <h2>, <p>, <ul>, <li>, <strong>).
2. Exactly 4 unique, relevant labels (tags) related to the content, separated by commas.

Video Title: {title}
Video Description: {description}

Format your response strictly as a JSON object with two keys: "content" (string) and "labels" (array of 4 strings). Do not wrap in markdown code blocks.
"""
    else:
        prompt = f"""
วิเคราะห์วิดีโอ YouTube นี้แล้วสร้าง 2 อย่าง:
1. บทความบล็อกฉบับเต็มอย่างละเอียด เป็นมืออาชีพ รองรับ SEO เป็นภาษาไทยทั้งหมด จัดโครงสร้างด้วยแท็ก HTML (เช่น <h2>, <p>, <ul>, <li>, <strong>)
2. ป้ายกำกับ (Labels) จำนวน exactamente 4 คำที่ไม่ซ้ำกัน ซึ่งเกี่ยวข้องกับเนื้อหาในวิดีโอ

หัวข้อวิดีโอ: {title}
รายละเอียดวิดีโอ: {description}

ส่งออกผลลัพธ์เป็น JSON object ที่มี 2 คีย์เท่านั้น คือ "content" (สตริง HTML) และ "labels" (อาเรย์ของสตริง 4 คำ) ห้ามใส่ markdown block ครอบ
"""

    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt
    )
    
    # พยายามแปลงผลลัพธ์เป็น JSON เพื่อดึงเนื้อหาและป้ายกำกับแยกกัน
    text_res = response.text.strip()
    if text_res.startswith("```json"):
        text_res = text_res[7:]
    if text_res.endswith("```"):
        text_res = text_res[:-3]
    text_res = text_res.strip()
    
    try:
        data = json.loads(text_res)
        return data.get("content", text_res), data.get("labels", [])
    except Exception:
        # กรณี AI ตอบกลับมาเป็น HTML ตรงๆ ให้ใช้ค่าสำรอง
        return response.text, ["Tech", "News", "Tutorial", "Review"]

def post_to_blogger(blog_id, title, content_html, labels, access_token):
    url = f"https://www.googleapis.com/blogger/v3/blogs/{blog_id}/posts/"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    data = {
        "kind": "blogger#post",
        "title": title,
        "content": content_html,
        "labels": labels
    }
    res = requests.post(url, headers=headers, json=data)
    return res.status_code, res.json()

def main():
    print("Starting YouTube Search Bot...")
    
    blogs = config.get("blogs", [])
    for blog in blogs:
        blog_id = blog.get("blog_id")
        query = blog.get("query")
        language = blog.get("language", "th")
        
        print(f"Processing Blog ID: {blog_id} with query: {query} (Language: {language})")
        videos = get_youtube_videos(query, max_results=1)
        
        if not videos:
            print("No videos found.")
            continue
            
        video = videos[0]
        snippet = video.get("snippet", {})
        title = snippet.get("title")
        description = snippet.get("description")
        
        print(f"Generating SEO article and labels for video: {title}")
        article_html, labels = generate_seo_article_and_labels(title, description, language)
        
        post_title = f"Review: {title}" if language == "en" else f"สรุปและรีวิว: {title}"
        
        status_code, response_data = post_to_blogger(blog_id, post_title, article_html, labels, BLOGGER_ACCESS_TOKEN)
        if status_code == 200:
            print(f"Successfully posted to Blogger with labels {labels}: {post_title}")
        else:
            print(f"Failed to post ({status_code}): {response_data}")

    print("YouTube Search Bot completed.")

if __name__ == "__main__":
    main()
