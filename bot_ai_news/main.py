import os
import json
import requests
import feedparser
from google import genai

# Load Config
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config = json.load(f)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
BLOGGER_ACCESS_TOKEN = os.getenv("BLOGGER_ACCESS_TOKEN")

def extract_image_url(entry):
    """
    ดึงลิงก์รูปภาพจาก RSS Entry (รองรับ media_content, enclosures และลิงก์ใน summary)
    """
    # ตรวจสอบจาก media_content
    if hasattr(entry, 'media_content') and entry.media_content:
        for media in entry.media_content:
            if 'url' in media:
                return media['url']
                
    # ตรวจสอบจาก enclosures
    if hasattr(entry, 'enclosures') and entry.enclosures:
        for enc in entry.enclosures:
            if 'type' in enc and 'image' in enc['type'] and 'href' in enc:
                return enc['href']
                
    return None

def generate_seo_article_and_labels(title, summary, image_url):
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    img_tag_instruction = ""
    if image_url:
        img_tag_instruction = f"แทรกแท็กรูปภาพ HTML ด้านบนสุดของบทความให้ด้วย: <img src='{image_url}' alt='{title}' style='max-width:100%; height:auto; border-radius:8px; margin-bottom:15px;' />"
    else:
        img_tag_instruction = "ไม่ต้องแทรกแท็กรูปภาพหากไม่มีลิงก์รูปภาพ"

    prompt = f"""
วิเคราะห์ข่าวนี้แล้วสร้าง 2 อย่าง:
1. บทความบล็อกฉบับเต็มอย่างละเอียด เป็นมืออาชีพ รองรับ SEO เป็นภาษาไทยทั้งหมด หัวข้อและเนื้อหาต้องเป็นภาษาไทย จัดโครงสร้างด้วยแท็ก HTML (เช่น <h2>, <p>, <ul>, <li>, <strong>) และ{img_tag_instruction}
2. ป้ายกำกับ (Labels) จำนวน 4 คำที่ไม่ซ้ำกัน ซึ่งเกี่ยวข้องกับเนื้อหาในข่าว

หัวข้อข่าว: {title}
เนื้อหาย่อ: {summary}

ส่งออกผลลัพธ์เป็น JSON object ที่มี 2 คีย์เท่านั้น คือ "content" (สตริง HTML) และ "labels" (อาเรย์ของสตริง 4 คำ) ห้ามใส่ markdown block ครอบ
"""

    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt
    )
    
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
        return response.text, ["ข่าวเทคโนโลยี", "ปัญญาประดิษฐ์", "นวัตกรรม", "ไอที"]

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
    print("Starting AI News Bot...")
    
    blogs = config.get("blogs", [])
    for blog in blogs:
        blog_id = blog.get("BLOG_ID")
        rss_feeds = blog.get("rss_feeds", [])
        
        for rss_url in rss_feeds:
            print(f"Processing Blog ID: {blog_id} from RSS: {rss_url}")
            feed = feedparser.parse(rss_url)
            
            if not feed.entries:
                print("No news found in this feed.")
                continue
                
            entry = feed.entries[0]
            title = entry.title
            summary = entry.get('summary', title)
            image_url = extract_image_url(entry)
            
            print(f"Generating SEO article and labels for: {title}")
            article_html, labels = generate_seo_article_and_labels(title, summary, image_url)
            
            post_title = f"สรุปข่าว: {title}"
            
            status_code, response_data = post_to_blogger(blog_id, post_title, article_html, labels, BLOGGER_ACCESS_TOKEN)
            if status_code == 200:
                print(f"Successfully posted to Blogger with labels {labels}: {post_title}")
            else:
                print(f"Failed to post ({status_code}): {response_data}")

    print("AI News Bot completed.")

if __name__ == "__main__":
    main()
