import os
import json
import random
import time
import pickle
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

def search_youtube_video(keyword, youtube_api_key):
    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        'part': 'snippet',
        'q': keyword,
        'type': 'video',
        'maxResults': 5,
        'key': youtube_api_key
    }
    res = requests.get(url, params=params)
    if res.status_code == 200:
        data = res.json()
        items = data.get('items', [])
        if items:
            item = random.choice(items)
            video_id = item['id']['videoId']
            snippet = item['snippet']
            thumbnail = snippet.get('thumbnails', {}).get('high', {}).get('url', f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg")
            return {
                'video_id': video_id,
                'title': snippet.get('title', ''),
                'description': snippet.get('description', ''),
                'channel': snippet.get('channelTitle', ''),
                'thumbnail': thumbnail
            }
    return None

def generate_ai_content(video_info, gemini_api_key, language="en"):
    client = genai.Client(api_key=gemini_api_key)
    
    if language == "th":
        lang_instruction = "Write the ENTIRE blog post (title and detailed article) strictly in THAI language (ภาษาไทย)."
    else:
        lang_instruction = "Write the ENTIRE blog post (title and detailed article) strictly in ENGLISH language."

    prompt = f"""
You are an expert technical blogger. Write a well-structured and engaging blog post based on the following YouTube video details.

{lang_instruction}

Video Title: {video_info['title']}
Channel: {video_info['channel']}
Description: {video_info['description']}

Instructions:
1. Write a catchy and informative blog post title.
2. Write a detailed, comprehensive article based on the video context.
3. Structure the article nicely using <h2>, <p>, <ul>, <li>, and <blockquote> tags.
4. Do NOT include html/head/body wrappers or markdown code blocks (```json). Return strictly valid JSON.

JSON Response Format:
{{
  "title": "Blog Title",
  "article_html": "<h2>Section Title</h2><p>Detailed explanation...</p><ul><li>Key point 1</li></ul>"
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
        print(f"Error generating AI content: {e}")
        return None

def build_full_html_post(video_info, ai_data):
    video_id = video_info['video_id']
    thumbnail = video_info['thumbnail']
    article_html = ai_data.get('article_html', '')
    
    html = f"""
<div style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto;">
  <div style="text-align: center; margin-bottom: 25px;">
    <img src="{thumbnail}" alt="{video_info['title']}" style="width: 100%; max-width: 700px; height: auto; border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.1);" />
  </div>
  
  <div style="margin-bottom: 30px;">
    {article_html}
  </div>

  <hr style="border: 0; border-top: 1px solid #eee; margin: 30px 0;" />

  <h3 style="color: #2c3e50; margin-bottom: 15px;">Watch Video / รับชมวิดีโอประกอบ</h3>
  <div style="position: relative; padding-bottom: 56.25%; height: 0; overflow: hidden; max-width: 100%; border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.15);">
    <iframe src="https://www.youtube.com/embed/{video_id}" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen style="position: absolute; top: 0; left: 0; width: 100%; height: 100%;"></iframe>
  </div>
  
  <p style="font-size: 0.85em; color: #777; text-align: right; margin-top: 10px;">
    Source Channel: {video_info['channel']}
  </p>
</div>
"""
    return html

def post_to_blogger(blogger_service, blog_id, title, content_html, labels):
    body = {
        'kind': 'blogger#post',
        'title': title,
        'content': content_html,
        'labels': labels
    }
    posts = blogger_service.posts()
    request = posts.insert(blogId=blog_id, body=body)
    return request.execute()

def main():
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
        
    youtube_api_key = os.environ.get('YOUTUBE_API_KEY') or config.get('YOUTUBE_API_KEY')
    gemini_api_key = os.environ.get('GEMINI_API_KEY')
    blogger_service = get_blogger_service()
    
    blogs = config.get('blogs', [])
    quota_exceeded = False

    for idx, blog in enumerate(blogs, start=1):
        if quota_exceeded:
            print(f"\nSkipping Blog #{idx} (Name: {blog.get('blog_name')}) due to daily Blogger API quota limit.")
            continue

        print(f"\n--- Processing Blog #{idx} (Name: {blog.get('blog_name')} | ID: {blog.get('BLOG_ID')} | Lang: {blog.get('language', 'en')}) ---")
        keywords = blog.get('keywords', [])
        if not keywords:
            continue
            
        keyword = random.choice(keywords)
        print(f"Searching YouTube with keyword: '{keyword}'...")
        video_info = search_youtube_video(keyword, youtube_api_key)
        
        if video_info:
            print(f"Found Video: {video_info['title']}")
            print("Generating AI content with Gemini...")
            lang = blog.get('language', 'en')
            ai_data = generate_ai_content(video_info, gemini_api_key, language=lang)
            
            if ai_data:
                suffix = blog.get('seo_title_suffix', '')
                final_title = f"{ai_data['title']} - {suffix}" if suffix else ai_data['title']
                
                full_html = build_full_html_post(video_info, ai_data)
                labels = blog.get('blogger_labels', ['YouTube', 'Video'])
                
                try:
                    res = post_to_blogger(blogger_service, blog.get('BLOG_ID'), final_title, full_html, labels)
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
            print("No YouTube video found.")
            
        if idx < len(blogs) and not quota_exceeded:
            print("Waiting 10 seconds before processing next blog...")
            time.sleep(10)

if __name__ == '__main__':
    main()
