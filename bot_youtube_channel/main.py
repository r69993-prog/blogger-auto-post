import os
import pickle
import time
import json
from datetime import datetime, timedelta, timezone
import feedparser
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

def load_config():
    """ โหลดค่าคอนฟิกจากไฟล์ภายนอกอัตโนมัติ """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(current_dir, 'config.json')
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)

# โหลดค่าคอนฟิกเข้าสู่ระบบหลัก
CONFIG = load_config()
BLOG_ID = CONFIG["BLOG_ID"]
YOUTUBE_CHANNELS = CONFIG["YOUTUBE_CHANNELS"]

def get_blogger_service():
    creds = None
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    token_path = os.path.join(BASE_DIR, 'token.pickle')
    
    if os.path.exists(token_path):
        with open(token_path, 'rb') as token:
            creds = pickle.load(token)
            
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(token_path, 'wb') as token:
            pickle.dump(creds, token)
            
    return build('blogger', 'v3', credentials=creds)

def get_existing_posts_data(service):
    existing_titles = set()
    latest_schedule_time = None
    
    try:
        request_live = service.posts().list(blogId=BLOG_ID, maxResults=50, status="LIVE")
        response_live = request_live.execute()
        if "items" in response_live:
            for post in response_live["items"]:
                existing_titles.add(post["title"])
    except Exception as e:
        print(f"ไม่สามารถดึงข้อมูลโพสต์ LIVE ได้: {e}")
        
    try:
        request_scheduled = service.posts().list(blogId=BLOG_ID, maxResults=50, status="SCHEDULED")
        response_scheduled = request_scheduled.execute()
        if "items" in response_scheduled:
            for post in response_scheduled["items"]:
                existing_titles.add(post["title"])
                pub_time_str = post["published"].replace("Z", "+00:00")
                pub_time = datetime.fromisoformat(pub_time_str)
                if latest_schedule_time is None or pub_time > latest_schedule_time:
                    latest_schedule_time = pub_time
    except Exception as e:
        print(f"ไม่สามารถดึงข้อมูลโพสต์ SCHEDULED ได้: {e}")
        
    return existing_titles, latest_schedule_time

def fetch_youtube_videos():
    all_videos = []
    for channel_id in YOUTUBE_CHANNELS:
        feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
        feed = feedparser.parse(feed_url)
        
        for entry in feed.entries:
            video_id = entry.yt_videoid if hasattr(entry, 'yt_videoid') else entry.id.split(':')[-1]
            thumbnail_url = f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"
            if hasattr(entry, 'media_thumbnail') and len(entry.media_thumbnail) > 0:
                thumbnail_url = entry.media_thumbnail[0]['url']
                
            video_data = {
                'title': entry.title,
                'link': entry.link,
                'video_id': video_id,
                'thumbnail': thumbnail_url,
                'description': entry.summary if hasattr(entry, 'summary') else ""
            }
            all_videos.append(video_data)
    return all_videos

def run_schedule_posting():
    try:
        service = get_blogger_service()
        existing_titles, latest_schedule_time = get_existing_posts_data(service)
        videos = fetch_youtube_videos()
        
        if not videos:
            print("ไม่พบวิดีโอจากช่องที่กำหนด")
            return
            
        print(f"พบวิดีโออุตสาหกรรมทั้งหมด {len(videos)} รายการ จาก YouTube Feed")
        print(f"กำลังเริ่มตั้งเวลาโพสต์กระจายทุกๆ {CONFIG['HOURS_INTERVAL']} ชั่วโมง...")
        
        if latest_schedule_time:
            print(f"พบโพสต์ล่าสุดในคิวเวลา: {latest_schedule_time.isoformat()} ระบบจะตั้งเวลาต่อจากนี้")
            current_schedule = latest_schedule_time + timedelta(hours=CONFIG['HOURS_INTERVAL'])
        else:
            current_schedule = datetime.now(timezone.utc) + timedelta(minutes=CONFIG['START_DELAY_MINUTES'])
            
        posted_count = 0
        
        for video in videos:
            if video['title'] in existing_titles:
                print(f"[-] ข้ามโพสต์ซ้ำ: {video['title']}")
                continue
                
            html_content = f"""
            <div style="text-align: center; margin-bottom: 20px;">
                <img src="{video['thumbnail']}" alt="{video['title']}" style="max-width: 100%; height: auto; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1);"/>
            </div>
            <div style="text-align: center; margin-bottom: 20px;">
                <iframe width="100%" height="450" 
                        src="https://www.youtube.com/embed/{video['video_id']}" 
                        frameborder="0" 
                        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" 
                        allowfullscreen>
                </iframe>
            </div>
            <h3 style="color: #111111; font-family: Arial, sans-serif;">Video Description</h3>
            <p style="font-size: 16px; line-height: 1.6; color: #333333; font-family: Arial, sans-serif; white-space: pre-wrap;">{video['description']}</p>
            <br/>
            <p style="font-size: 14px; color: #666666; font-family: Arial, sans-serif;">Source video: <a href="{video['link']}" target="_blank" style="color: #0066cc;">{video['title']}</a></p>
            """
            
            scheduled_iso = current_schedule.isoformat()
            
            body = {
                "kind": "blogger#post",
                "title": video['title'],
                "content": html_content,
                "published": scheduled_iso,
                "labels": CONFIG["POST_LABELS"]
            }
            
            try:
                request = service.posts().insert(blogId=BLOG_ID, body=body, isDraft=False)
                response = request.execute()
                posted_count += 1
                print(f"[+] [{posted_count}] ตั้งเวลาสำเร็จ: {video['title']} -> (เวลาปล่อยโพสต์: {scheduled_iso})")
                
                current_schedule += timedelta(hours=CONFIG['HOURS_INTERVAL'])
                time.sleep(CONFIG['API_REQUEST_DELAY_SECONDS'])
                
            except Exception as api_err:
                if "rateLimitExceeded" in str(api_err) or "429" in str(api_err):
                    print("\n[!] โควตา Blogger API เต็มสำหรับรอบนี้ ระบบหยุดทำงานอย่างปลอดภัย")
                    break
                else:
                    print(f"[x] เกิดข้อผิดพลาดในบทความนี้: {api_err}")
            
        print("\n====================================")
        print(f"เสร็จสิ้นการรันระบบรอบนี้ ตั้งเวลาเพิ่มได้ {posted_count} บทความ")
        print("====================================")
        
    except Exception as e:
        print(f"เกิดข้อผิดพลาดในการทำงาน: {e}")

if __name__ == "__main__":
    run_schedule_posting()