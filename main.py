# main.py
import os
import uvicorn
import asyncio
import json
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
from playwright.async_api import async_playwright

# --- Cấu hình ---
# Tạo thư mục để lưu file upload
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Đường dẫn lưu file
COOKIES_PATH = os.path.join(UPLOAD_DIR, "cookies.json")
SCRIPT_PATH = os.path.join(UPLOAD_DIR, "script.js")

# Khởi tạo FastAPI
app = FastAPI(title="Playwright Automation Service")

# --- API Endpoints ---

@app.get("/")
async def root():
    """Endpoint gốc để kiểm tra dịch vụ có hoạt động không."""
    return {"message": "Playwright Automation Service is running. Use the endpoints to upload files and run scripts."}

@app.post("/upload-cookies/")
async def upload_cookies(cookies_file: UploadFile = File(...)):
    """
    Endpoint để tải lên file cookies.
    File cookies phải ở định dạng JSON.
    """
    try:
        contents = await cookies_file.read()
        # Kiểm tra xem có phải JSON hợp lệ không
        json.loads(contents) 
        
        with open(COOKIES_PATH, "wb") as f:
            f.write(contents)
            
        return JSONResponse(status_code=200, content={"message": f"Cookies file '{cookies_file.filename}' uploaded successfully."})
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON format in cookies file.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

@app.post("/upload-script/")
async def upload_script(script_file: UploadFile = File(...)):
    """
    Endpoint để tải lên kịch bản Playwright.
    File phải là file JavaScript (.js).
    """
    if not script_file.filename.endswith('.js'):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a .js file.")
        
    try:
        contents = await script_file.read()
        with open(SCRIPT_PATH, "wb") as f:
            f.write(contents)
        return JSONResponse(status_code=200, content={"message": f"Script file '{script_file.filename}' uploaded successfully."})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

@app.post("/run/")
async def run_script(url: str = Form(...)):
    """
    Endpoint để chạy kịch bản Playwright.
    Cần cung cấp URL của trang web mục tiêu.
    """
    if not os.path.exists(SCRIPT_PATH):
        raise HTTPException(status_code=404, detail="Script file not found. Please upload a script first.")
    
    # Đọc nội dung kịch bản
    with open(SCRIPT_PATH, 'r') as f:
        script_content = f.read()

    # Đọc cookies nếu có
    cookies = None
    if os.path.exists(COOKIES_PATH):
        with open(COOKIES_PATH, 'r') as f:
            try:
                cookies = json.load(f)
            except json.JSONDecodeError:
                 raise HTTPException(status_code=500, detail="Failed to load cookies. Invalid JSON format.")


    # Chạy Playwright
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()

            # Thêm cookies vào context nếu có
            if cookies:
                await context.add_cookies(cookies)

            page = await context.new_page()
            
            # Thay thế biến `targetUrl` trong script bằng URL người dùng cung cấp
            # Điều này giúp kịch bản của bạn linh hoạt hơn
            full_script = f"""
                const targetUrl = '{url}';
                {script_content}
            """

            # Thực thi kịch bản
            # Lưu ý: Kịch bản trong file JS không cần `require('playwright')`
            # Nó sẽ chạy trong ngữ cảnh của trang đã được tạo.
            # Để đơn giản, chúng ta sẽ dùng evaluate để chạy code JS.
            # Một cách tiếp cận tốt hơn là dùng `add_init_script` hoặc cấu trúc lại file JS
            # để nó nhận `page` và `context` làm tham số.
            # Ở đây, chúng ta sẽ điều hướng trước, sau đó chạy script.
            
            await page.goto(url, wait_until='networkidle')

            # Tạo một hàm async trong JS để chạy script
            # Điều này cho phép sử dụng await bên trong script của bạn
            js_code_to_run = f"""
            (async () => {{
                // Định nghĩa lại các hàm locator cơ bản để script có thể chạy
                const locator = (selector) => page.locator(selector);
                
                // Đoạn script của bạn sẽ được chèn vào đây
                try {{
                    {script_content}
                    return {{ success: true, message: "Script executed successfully." }};
                }} catch (err) {{
                    return {{ success: false, message: err.toString() }};
                }}
            }})()
            """
            
            # Chạy script trong ngữ cảnh của trang
            # Lưu ý: Cách này không chạy được các lệnh Playwright trực tiếp
            # như `page.locator`. Đây là một thách thức.
            
            # --- CÁCH TIẾP CẬN TỐT HƠN: DÙNG subprocess ---
            # Để chạy script Playwright một cách độc lập, chúng ta cần
            # gọi nó như một tiến trình con.
            
            process = await asyncio.create_subprocess_exec(
                'node', SCRIPT_PATH, url, COOKIES_PATH,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                return JSONResponse(status_code=200, content={
                    "message": "Script executed successfully.",
                    "output": stdout.decode().strip()
                })
            else:
                raise HTTPException(status_code=500, detail={
                    "message": "Script execution failed.",
                    "error": stderr.decode().strip()
                })

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred during Playwright execution: {str(e)}")

# --- Chạy server (chỉ khi chạy file này trực tiếp) ---
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
