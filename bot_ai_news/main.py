import os
import json
import random
import time
import pickle
import feedparser
import requests
from google import genai
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request

SCOPES = ['https://www.googleapis.com/auth/blogger']

def get_blogger_service():
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
            
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)
        else:
            raise Exception("token.pickle Invalid or Expired")

    discovery_url = 'https://blogger.googleapis.com/$discovery/rest?version=v3'
    return build('blogger', 'v3', credentials=creds, discoveryServiceUrl=discovery_url)

def extract_image_url(entry):
    if 'media_content' in entry and len(entry.media_content) > 0:
        return entry.media_content[0].get('url')
    if 'media_thumbnail' in entry and len(entry.media_thumbnail) > 0:
        return entry.media_thumbnail[0].get('url')
    if 'links' in entry:
        for link in entry.links:
            if link.get('type', '').startswith('image/'):
                return link.get('href')
    return "https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=800&q=80"

def fetch_latest_news(rss_urls):
    for url in rss_urls:
        try:
            feed = feedparser.parse(url)
            if feed.entries:
                entry = random.choice(feed.entries[:5])
                image_url = extract_image_url(entry)
                return {
                    'title': entry.get('title', ''),
                    'link': entry.get('link', ''),
                    'summary': entry.get('summary', ''),
                    'image': image_url
                }
        except Exception as e:
            print(f"Error fetching RSS {url}: {e}")
            continue
    return None

def generate_ai_summary(news_item, gemini_api_key, language="en"):
    client = genai.Client(api_key=gemini_api_key)
    
    if language == "th":
        lang_instruction = "Write the ENTIRE blog post (title and content) strictly in THAI language (ภาษาไทย)."
    else:
        lang_instruction = "Write the ENTIRE blog post (title and content) strictly in ENGLISH language."

    prompt = f"""
Summarize the following news article into a comprehensive, professional blog post.

{lang_instruction}

News Title: {news_item['title']}
Source Link: {news_item['link']}
Raw Summary: {news_item['summary']}

Instructions:
1. Write a compelling blog title and full body content in HTML format.
2. Structure the body using <h2>, <p>, <ul>, <li>, and <blockquote> tags.
3. Do NOT include html/head/body wrappers or markdown code blocks (```json). Return ONLY a valid JSON object.

JSON Response Format:
{{
  "title": "Blog Title Here",
  "content": "<h2>Overview</h2><p>Content in HTML format...</p>"
}}
"""
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        text = response.text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        return json.loads(text)
    except Exception as e:
        print(f"Error generating AI summary: {e}")
        return None

def build_styled_html(news_item, ai_data):
    image_url = news_item.get('image')
    article_html = ai_data.get('content', '')
    source_link = news_item.get('link', '#')
    
    html = f"""
<div style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto;">
  <div style="text-align: center; margin-bottom: 25px;">
    <img src="{image_url}" alt="News Featured Image" style="width: 100%; max-width: 750px; height: auto; border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.12);" />
  </div>
  
  <div style="margin-bottom: 30px;">
    {article_html}
  </div>

  <hr style="border: 0; border-top: 1px solid #eee; margin: 30px 0;" />

  <blockquote style="background-color: #f9f9f9; border-left: 4px solid #007bff; padding: 12px 20px; margin: 20px 0; font-size: 0.9em;">
    <strong>Reference / ที่มาของข่าว:</strong> <a href="{source_link}" target="_blank" rel="noopener noreferrer" style="color: #007bff; text-decoration: none;">อ่านข่าวต้นฉบับเต็มคลิกที่นี่</a>
  </blockquote>
</div>
"""
    return html

def post_to_blogger(blogger_service, blog_id, post_data, labels):
    body = {
        'kind': 'blogger#post',
        'title': post_data['title'],
        'content': post_data['content'],
        'labels': labels
    }
    posts = blogger_service.posts()
    request = posts.insert(blogId=blog_id, body=body)
    return request.execute()

def main():
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
        
    gemini_api_key = os.environ.get('GEMINI_API_KEY') or config.get('GEMINI_API_KEY')
    blogger_service = get_blogger_service()
    
    blogs = config.get('blogs', [])
    quota_exceeded = False

    for idx, blog in enumerate(blogs, start=1):
        if quota_exceeded:
            print(f"\nSkipping Blog #{idx} (Name: {blog.get('blog_name')}) due to daily Blogger API quota limit.")
            continue

        print(f"\n--- Processing Blog #{idx} (Name: {blog.get('blog_name')} | ID: {blog.get('BLOG_ID')} | Lang: {blog.get('language', 'en')}) ---")
        rss_feeds = blog.get('rss_feeds', [])
        if not rss_feeds:
            continue
            
        print("Fetching RSS feeds...")
        news_item = fetch_latest_news(rss_feeds)
        
        if news_item:
            print(f"Found News: {news_item['title']}")
            print("Generating AI summary with Gemini...")
            lang = blog.get('language', 'en')
            ai_data = generate_ai_summary(news_item, gemini_api_key, language=lang)
            
            if ai_data:
                suffix = blog.get('seo_title_suffix', '')
                final_title = f"{ai_data['title']} - {suffix}" if suffix else ai_data['title']
                
                styled_content = build_styled_html(news_item, ai_data)
                
                post_payload = {
                    'title': final_title,
                    'content': styled_content
                }
                
                labels = blog.get('blogger_labels', ['AI', 'News'])
                try:
                    res = post_to_blogger(blogger_service, blog.get('BLOG_ID'), post_payload, labels)
                    print(f"SUCCESS: Posted to Blog ID: {blog.get('BLOG_ID')}")
                    print(f"Post URL: {res.get('url')}")
                except HttpError as e:
                    if e.resp.status == 429:
                        print("\n[CRITICAL] Blogger API Daily Quota Exceeded (429). Stopping process for today.")
                        quota_exceeded = True
                    else:
                        print(f"Failed to post to Blogger: {e}")
                except Exception as e:
                    print(f"Failed to post to Blogger: {e}")
            else:
                print("Failed to generate AI content.")
        else:
            print("No news found from RSS feeds.")
            
        if idx < len(blogs) and not quota_exceeded:
            print("Waiting 10 seconds before processing next blog...")
            time.sleep(10)

if __name__ == '__main__':
    main()
