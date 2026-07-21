import json
import os
import re
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import google.generativeai as genai

# Load configuration
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
TOKEN_PATH = os.path.join(os.path.dirname(__file__), "token.pickle")

def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def get_blogger_service():
    import pickle
    with open(TOKEN_PATH, "rb") as token:
        creds = pickle.load(token)
    return build("blogger", "v3", credentials=creds)

def search_youtube_videos(api_key, query, max_results=3):
    youtube = build("youtube", "v3", developerKey=api_key)
    request = youtube.search().list(
        q=query,
        part="snippet",
        type="video",
        maxResults=max_results,
        relevanceLanguage="th"
    )
    response = request.execute()
    videos = []
    for item in response.get("items", []):
        video_id = item["id"]["videoId"]
        snippet = item["snippet"]
        thumbnail = snippet["thumbnails"].get("high", {}).get("url", "")
        videos.append({
            "id": video_id,
            "title": snippet["title"],
            "description": snippet["description"],
            "thumbnail": thumbnail,
            "url": f"https://www.youtube.com/watch?v={video_id}"
        })
    return videos

def generate_blog_content(gemini_api_key, video, search_query, language="th"):
    genai.configure(api_key=gemini_api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")

    prompt = f"""
    คุณคือ Senior Content Creator และ SEO Specialist
    สร้างบทความจากคลิปวิดีโอ YouTube ดังนี้:
    - หัวข้อคลิป: {video['title']}
    - คำอธิบายคลิป: {video['description']}
    - ลิงก์รูปภาพปก: {video['thumbnail']}
    - ลิงก์ฝังคลิป: https://www.youtube.com/embed/{video['id']}
    - คีย์เวิร์ด/คีย์เวิร์ดค้นหา: {search_query}
    - ภาษาหลักของบทความ: {language}

    กรุณาสร้างเนื้อหาแยกเป็น 3 ส่วนในรูปแบบ JSON ดังนี้ (ห้ามใส่สัญลักษณ์ Markdown code block ซ้อนในค่า JSON):
    {{
      "title": "หัวข้อบทความที่ดึงดูด น่าสนใจ ทำ SEO ใส่ Keyword เป็นธรรมชาติ ไม่ซ้ำใคร",
      "content_html": "เนื้อหาบทความแบบ HTML ภาษา {language} โดยรวมรูปภาพหน้าปก <img src='{video['thumbnail']}' /> และฝังคลิป <iframe src='https://www.youtube.com/embed/{video['id']}'></iframe> ประกอบบทความ จัดวางโครงสร้างให้สวยงาม เหมาะสม อ่านง่าย ทำ SEO ธรรมชาติ",
      "labels": ["ป้ายกำกับ1", "ป้ายกำกับ2", "ป้ายกำกับ3", "ป้ายกำกับ4"]
    }}
    หมายเหตุสำหรับ labels: ติดป้ายกำกับ Label ที่เกี่ยวข้องแยกหมวดหมู่ชัดเจน ไม่เกิน 4 คำ
    """

    response = model.generate_content(prompt)
    text = response.text.strip()
    
    # Clean output JSON if needed
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
        
    try:
        data = json.loads(text.strip())
        return data
    except Exception as e:
        # Fallback if AI output is not strict JSON
        return {
            "title": f"{video['title']} - เจาะลึกน่าสนใจ",
            "content_html": f"<h2>{video['title']}</h2><p><img src='{video['thumbnail']}' alt='Cover' /></p><p>{video['description']}</p><p><iframe width='560' height='315' src='[https://www.youtube.com/embed/](https://www.youtube.com/embed/){video['id']}' frameborder='0' allowfullscreen></iframe></p>",
            "labels": [search_query, "YouTube", "สาระน่ารู้"]
        }

def post_to_blogger(service, blog_id, title, content_html, labels):
    body = {
        "kind": "blogger#post",
        "title": title,
        "content": content_html,
        "labels": labels
    }
    posts = service.posts()
    result = posts.insert(blogId=blog_id, body=body).execute()
    print(f"Successfully posted to Blog ID {blog_id}: {result.get('url')}")

def main():
    config = load_config()
    blogger_service = get_blogger_service()
    
    gemini_key = config.get("gemini_api_key", "")
    youtube_key = config.get("youtube_api_key", gemini_key)
    
    for blog in config.get("blogs", []):
        blog_id = blog["blog_id"]
        keywords = blog.get("keywords", ["ข่าวด่วน"])
        language = blog.get("language", "th")
        
        for kw in keywords:
            videos = search_youtube_videos(youtube_key, kw, max_results=1)
            if videos:
                video = videos[0]
                content_data = generate_blog_content(gemini_key, video, kw, language)
                
                post_to_blogger(
                    service=blogger_service,
                    blog_id=blog_id,
                    title=content_data.get("title", video["title"]),
                    content_html=content_data.get("content_html", ""),
                    labels=content_data.get("labels", [])
                )
                break

if __name__ == "__main__":
    main()
