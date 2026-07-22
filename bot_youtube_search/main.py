import json
import os
import re
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import google.generativeai as genai

# Load configuration paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
TOKEN_PATH = os.path.join(BASE_DIR, "token.pickle")

def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def clean_key(key):
    if not key:
        return ""
    cleaned = re.sub(r'[^\x00-\x7F]+', '', str(key))
    return cleaned.replace('"', '').replace("'", "").strip()

def get_blogger_service():
    import pickle
    with open(TOKEN_PATH, "rb") as token:
        creds = pickle.load(token)
    return build("blogger", "v3", credentials=creds)

def search_youtube_videos(api_key, query, max_results=5):
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

def generate_blog_content(gemini_api_key, video, search_query, language="TH"):
    try:
        cleaned_gemini_key = clean_key(gemini_api_key)
        if not cleaned_gemini_key:
            raise ValueError("gemini_api_key is missing or empty after cleaning")
            
        genai.configure(api_key=cleaned_gemini_key)
        model = genai.GenerativeModel("gemini-1.5-flash-latest")

        prompt = f"""
        คุณคือ Senior Content Creator และ SEO Specialist
        สร้างบทความจากคลิปวิดีโอ YouTube ดังนี้:
        - หัวข้อคลิป: {video['title']}
        - คำอธิบายคลิป: {video['description']}
        - ลิงก์รูปภาพปก: {video['thumbnail']}
        - ลิงก์ฝังคลิป: https://www.youtube.com/embed/{video['id']}
        - คีย์เวิร์ดค้นหา: {search_query}
        - ภาษาหลักของบทความ: {language}

        คำสั่งในการสร้างเนื้อหาภาษา {language}:
        ส่วนที่ 1 (title): สร้างหัวข้อบทความที่ดึงดูด ทำ SEO ใส่ Keyword เป็นธรรมชาติและน่าสนใจไม่ซ้ำใคร
        ส่วนที่ 2 (content_html): เขียนบทความภาษา {language} จัดวางโครงสร้างสวยงาม มีหัวข้อรอง (h2, h3) เนื้อหาละเอียด อ่านง่าย โดยในเนื้อหาต้องใส่รูปปก <img src="{video['thumbnail']}" style="max-width:100%; height:auto;" /> และฝังวิดีโอ <iframe width="560" height="315" src="https://www.youtube.com/embed/{video['id']}" frameborder="0" allowfullscreen></iframe>
        ส่วนที่ 3 (labels): กำหนดป้ายกำกับ Label ที่เกี่ยวข้อง แยกหมวดหมู่ชัดเจน ความยาวไม่เกิน 4 คำต่อ Label (ให้คืนค่าเป็นอาร์เรย์ของสตริง)

        ให้ตอบกลับเป็นโครงสร้าง JSON ดังนี้เท่านั้น:
        {{
          "title": "...",
          "content_html": "...",
          "labels": ["คำที่1", "คำที่2", "คำที่3"]
        }}
        """

        response = model.generate_content(prompt)
        text = response.text.strip()
        
        # Clean potential markdown code blocks
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        data = json.loads(text)
        return data
    except Exception as e:
        print(f"Gemini API Error or JSON Parse Error: {e}")
        print("Using fallback content generator...")
        return {
            "title": f"{video['title']} - {search_query}",
            "content_html": f"<h2>{video['title']}</h2><p><img src='{video['thumbnail']}' alt='Cover' style='max-width:100%; height:auto;' /></p><p>{video['description']}</p><p><iframe width='560' height='315' src='[https://www.youtube.com/embed/](https://www.youtube.com/embed/){video['id']}' frameborder='0' allowfullscreen></iframe></p>",
            "labels": [search_query, "YouTube", "Video"]
        }

def post_to_blogger(service, blog_id, title, content_html, labels):
    try:
        body = {
            "kind": "blogger#post",
            "title": title,
            "content": content_html,
            "labels": labels
        }
        posts = service.posts()
        result = posts.insert(blogId=blog_id, body=body).execute()
        print(f"SUCCESS: Posted to Blog ID: {blog_id}")
        print(f"Post URL: {result.get('url')}")
        print(f"Post Title: {result.get('title')}")
    except Exception as e:
        print(f"ERROR posting to Blog ID {blog_id}: {e}")

def main():
    config = load_config()
    blogger_service = get_blogger_service()
    
    gemini_key = config.get("gemini_api_key")
    youtube_key = clean_key(config.get("YOUTUBE_API_KEY"))
    
    cleaned_gemini = clean_key(gemini_key)
    if cleaned_gemini:
        print(f"Explicit Config Gemini Key Loaded (Cleaned): {cleaned_gemini[:8]}...")
    else:
        print("ERROR: gemini_api_key is completely missing in config.json")
        
    blogs = config.get("blogs", [])
    print(f"Total blogs in config: {len(blogs)}")
    
    for index, blog in enumerate(blogs):
        blog_id = blog.get("BLOG_ID") or blog.get("blog_id") or blog.get("blogId") or blog.get("id")
        print(f"\n--- Processing Blog #{index + 1} (Name: {blog.get('blog_name', '')} | ID: {blog_id}) ---")
        if not blog_id:
            print("Skipping blog entry: missing blog_id")
            continue

        keywords = blog.get("youtube_search_keywords") or blog.get("keywords", ["ข่าวด่วน"])
        language = blog.get("language", "TH")
        
        for kw in keywords:
            print(f"Searching YouTube for keyword: {kw}")
            videos = search_youtube_videos(youtube_key, kw, max_results=5)
            if videos:
                video = videos[0]
                print(f"Found Video: {video['title']} ({video['url']})")
                
                print("Generating content...")
                content_data = generate_blog_content(gemini_key, video, kw, language)
                
                print(f"Generated Title: {content_data.get('title')}")
                print(f"Generated Labels: {content_data.get('labels')}")
                
                post_to_blogger(
                    service=blogger_service,
                    blog_id=blog_id,
                    title=content_data.get("title", video["title"]),
                    content_html=content_data.get("content_html", ""),
                    labels=content_data.get("labels", [])
                )
                break
            else:
                print(f"No videos found for keyword: {kw}")

if __name__ == "__main__":
    main()
