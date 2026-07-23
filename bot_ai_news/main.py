import os
import json
import feedparser
import requests
import google.generativeai as genai

# Load Config
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config = json.load(f)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def fetch_rss_news(feed_url):
    feed = feedparser.parse(feed_url)
    if feed.entries:
        entry = feed.entries[0]
        return entry.title, entry.link, entry.get("summary", "")
    return None, None, None

def generate_article(title, summary, language="th"):
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("models/gemini-1.5-flash")
    
    if language == "en":
        prompt = f"""
Write a comprehensive, professional blog post based on this AI news.
Title: {title}
Summary: {summary}

Requirements:
- Article MUST be entirely in English language.
- Provide a clear introduction, detailed body paragraphs explaining the concept, key takeaways, and a conclusion.
- Do NOT use Markdown headers or bold text formatting. Use plain clean HTML paragraphs (<p>).
"""
    else:
        prompt = f"""
เขียนบทความบล็อกฉบับเต็มอย่างละเอียดยาวและเป็นมืออาชีพจากข่าว AI นี้
หัวข้อ: {title}
เนื้อหาย่อ: {summary}

ข้อกำหนด:
- บทความต้องเป็นภาษาไทยทั้งหมด 100%
- สรุปเนื้อหาสำคัญ อธิบายรายละเอียดอย่างชัดเจน อธิบายความเป็นมา ผลกระทบ และสรุปภาพรวม
- ห้ามใช้ Markdown ให้ใช้แท็ก HTML <p> สำหรับย่อหน้าทั่วไปเท่านั้น
"""

    response = model.generate_content(prompt)
    return response.text

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
    
    access_token = os.getenv("BLOGGER_ACCESS_TOKEN")
    blogs = config.get("blogs", [])
    
    for blog in blogs:
        blog_name = blog.get("blog_name")
        blog_id = blog.get("BLOG_ID")
        language = blog.get("language", "th")
        rss_feeds = blog.get("rss_feeds", [])
        labels = blog.get("blogger_labels", [])
        
        print(f"Processing Blog: {blog_name} (ID: {blog_id})")
        
        for feed_url in rss_feeds:
            print(f"Fetching news from: {feed_url}")
            title, link, summary = fetch_rss_news(feed_url)
            
            if not title:
                print("No news found.")
                continue
                
            print(f"Generating article for: {title}")
            article_content = generate_article(title, summary, language)
            
            html_content = f"<p>แหล่งที่มา: <a href='{link}'>อ่านเพิ่มเติมที่นี่</a></p>" + article_content
            
            print("Posting to Blogger...")
            status_code, res_data = post_to_blogger(blog_id, title, html_content, labels, access_token)
            
            if status_code == 200:
                print(f"Successfully posted: {title}")
            else:
                print(f"Failed to post: {res_data}")

    print("AI News Bot completed.")

if __name__ == "__main__":
    main()
