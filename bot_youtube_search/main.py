import os
import json
import random
import time
import googleapiclient.discovery
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
import pickle

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
    youtube = build('youtube', 'v3', developerKey=youtube_api_key)
    request = youtube.search().list(
        q=keyword,
        part='snippet',
        maxResults=10,
        type='video',
        order='date'
    )
    response = request.execute()
    items = response.get('items', [])
    if items:
        selected_item = random.choice(items)
        video_id = selected_item['id']['videoId']
        title = selected_item['snippet']['title']
        description = selected_item['snippet']['description']
        return {
            'video_id': video_id,
            'title': title,
            'description': description,
            'url': f"https://www.youtube.com/watch?v={video_id}"
        }
    return None

def generate_simple_content(video_info, keyword, blog_config):
    video_id = video_info['video_id']
    video_title = video_info['title']
    video_desc = video_info['description']
    suffix = blog_config.get('seo_title_suffix', '')
    
    title = f"{video_title} - {suffix}" if suffix else video_title
    
    content = f"""
<div style="text-align: center; margin-bottom: 20px;">
    <iframe width="100%" height="450" src="https://www.youtube.com/embed/{video_id}" frameborder="0" allowfullscreen></iframe>
</div>
<div style="font-family: Arial, sans-serif; line-height: 1.6;">
    <h2>{video_title}</h2>
    <p>{video_desc}</p>
    <p>Watch full video on YouTube: <a href="{video_info['url']}" target="_blank">{video_info['url']}</a></p>
</div>
"""
    labels = blog_config.get('blogger_labels', ['YouTube', 'Video'])
    if keyword not in labels:
        labels.append(keyword)
        
    return {
        'title': title,
        'content': content,
        'labels': labels
    }

def post_to_blogger_with_retry(blogger_service, blog_id, post_data, max_retries=3):
    body = {
        'kind': 'blogger#post',
        'title': post_data['title'],
        'content': post_data['content'],
        'labels': post_data['labels']
    }
    posts = blogger_service.posts()
    
    for attempt in range(1, max_retries + 1):
        try:
            request = posts.insert(blogId=blog_id, body=body)
            response = request.execute()
            return response
        except HttpError as e:
            if e.resp.status == 429:
                if attempt < max_retries:
                    wait_time = attempt * 60
                    print(f"Rate limit hit (429). Retrying in {wait_time} seconds... (Attempt {attempt}/{max_retries})")
                    time.sleep(wait_time)
                else:
                    raise e
            else:
                raise e

def main():
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
        
    youtube_api_key = config.get('YOUTUBE_API_KEY')
    blogger_service = get_blogger_service()
    
    blogs = config.get('blogs', [])
    for idx, blog in enumerate(blogs, start=1):
        print(f"\n--- Processing Blog #{idx} (Name: {blog.get('blog_name')} | ID: {blog.get('BLOG_ID')}) ---")
        keywords = blog.get('youtube_search_keywords', [])
        if not keywords:
            continue
            
        keyword = random.choice(keywords)
        print(f"Searching YouTube for keyword: {keyword}")
        video_info = search_youtube_video(keyword, youtube_api_key)
        
        if video_info:
            print(f"Found Video: {video_info['title']} ({video_info['url']})")
            print("Generating content without AI...")
            post_data = generate_simple_content(video_info, keyword, blog)
            
            try:
                res = post_to_blogger_with_retry(blogger_service, blog.get('BLOG_ID'), post_data)
                print(f"SUCCESS: Posted to Blog ID: {blog.get('BLOG_ID')}")
                print(f"Post URL: {res.get('url')}")
                print(f"Post Title: {res.get('title')}")
            except Exception as e:
                print(f"Failed to post to Blogger: {e}")
        else:
            print("No video found.")
            
        if idx < len(blogs):
            print("Waiting 30 seconds before processing next blog...")
            time.sleep(30)

if __name__ == '__main__':
    main()
