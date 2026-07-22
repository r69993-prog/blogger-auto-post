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

def fetch_latest_news(rss_urls):
    for url in rss_urls:
        try:
            feed = feedparser.parse(url)
            if feed.entries:
                entry = random.choice(feed.entries[:5])
                return {
                    'title': entry.get('title', ''),
                    'link': entry.get('link', ''),
                    'summary': entry.get('summary', '')
                }
        except Exception as e:
            print(f"Error fetching RSS {url}: {e}")
            continue
    return None

def generate_ai_summary(news_item, gemini_api_key, language="en"):
    client = genai.Client(api_key=gemini_api_key)
    
    if language == "th":
        lang_instruction = "Write the ENTIRE blog post (title and content) in THAI language (ภาษาไทย)."
    else:
        lang_instruction = "Write the ENTIRE blog post (title and content) in ENGLISH language."

    prompt = f"""
Summarize the following news article into a comprehensive blog post in HTML format.

{lang_instruction}

News Title: {news_item['title']}
Source Link: {news_item['link']}
Raw Summary: {news_item['summary']}

Instructions:
1. Write a compelling blog title and full body content in HTML format.
2. Structure the body using <h2>, <p>, <ul>, <li>, and <blockquote> tags.
3. Include an embedded credit back to the source link at the end of the post.
4. Do NOT wrap the output in ```html or ``` text blocks. Return ONLY a valid JSON object.

JSON Response Format:
{{
  "title": "Blog Title Here",
  "content": "<p>Content in HTML format...</p>"
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
        
        data = json.loads(text)
        return data
    except Exception as e:
        print(f"Error generating AI summary: {e}")
        return None

def post_to_blogger(blogger_service, blog_id, post_data, labels):
    body = {
        'kind': 'blogger#post',
        'title': post_data['title'],
        'content': post_data['content'],
        'labels': labels
    }
    posts = blogger_service.posts()
    request = posts.insert(blogId=blog_id, body=body)
    response = request.execute()
    return response

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
                
                post_payload = {
                    'title': final_title,
                    'content': ai_data['content']
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
