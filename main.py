import os
import google.oauth2.credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
import pickle

# Blog ID ของคุณ
BLOG_ID = "8092017257208773186"

SCOPES = ['https://www.googleapis.com/auth/blogger']

def get_blogger_service():
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
            
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # โหมดดึงสิทธิ์แบบระบุตำแหน่งคงที่ ป้องกันปัญหา CSRF บนคลาวด์
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', 
                SCOPES,
                redirect_uri='https://developers.google.com/oauthplayground'
            )
            auth_url, _ = flow.authorization_url(prompt='consent', access_type='offline')
            
            print("\n====================================")
            print("1. ให้คัดลอกลิงก์ด้านล่างนี้ไปเปิดในบราวเซอร์แท็บใหม่เพื่อกดยอมรับสิทธิ์:")
            print(auth_url)
            print("====================================")
            
            print("\n2. หลังจากกดยอมรับสิทธิ์เสร็จสิ้น หน้าเว็บจะเด้งไปที่ OAuth Playground")
            print("3. ให้สังเกตแถบ URL ด้านบนสุดของบราวเซอร์ในหน้านั้น จะมีข้อความคำว่า code=...")
            
            code_url = input("\n4. ให้ก๊อปปี้ URL ทั้งหมดบนแถบ Address Bar ของหน้านั้นมาวางตรงนี้ แล้วกด Enter: ").strip()
            
            # ดึงเฉพาะค่า code ออกจาก URL มาใช้งาน
            if "code=" in code_url:
                start = code_url.find("code=") + 5
                end = code_url.find("&", start)
                auth_code = code_url[start:end] if end != -1 else code_url[start:]
            else:
                auth_code = code_url

            flow.fetch_token(code=auth_code)
            creds = flow.credentials
            
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    return build('blogger', 'v3', credentials=creds)

def test_post():
    try:
        service = get_blogger_service()
        
        body = {
            "kind": "blogger#post",
            "title": "ทดสอบโพสต์อัตโนมัติครั้งที่ 1",
            "content": "เนื้อหาทดสอบระบบโพสต์อัตโนมัติฟรี 100% ผ่าน Python และ GitHub Codespaces แบบ Web Flow"
        }
        
        posts = service.posts()
        request = posts.insert(blogId=BLOG_ID, body=body)
        response = request.execute()
        
        print("\n====================================")
        print("สำเร็จ! โพสต์บทความเรียบร้อยแล้ว")
        print(f"ลิงก์บทความ: {response.get('url')}")
        print("====================================")
        
    except Exception as e:
        print(f"\nเกิดข้อผิดพลาด: {e}")

if __name__ == "__main__":
    test_post()