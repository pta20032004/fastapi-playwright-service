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
async def upload_cookies(cookies_text: str = Form(...)):
    """
    Endpoint để tải lên nội dung cookies dưới dạng văn bản.
    Nội dung phải là một chuỗi JSON hợp lệ.
    """
    try:
        # Kiểm tra xem có phải JSON hợp lệ không
        json.loads(cookies_text) 
        
        with open(COOKIES_PATH, "w", encoding="utf-8") as f:
            f.write(cookies_text)
            
        return JSONResponse(status_code=200, content={"message": "Cookies text uploaded successfully."})
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON format in cookies text.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

@app.post("/upload-script/")
async def upload_script(script_text: str = Form(...)):
    """
    Endpoint để tải lên kịch bản Playwright dưới dạng văn bản.
    """
    try:
        with open(SCRIPT_PATH, "w", encoding="utf-8") as f:
            f.write(script_text)
        return JSONResponse(status_code=200, content={"message": "Script text uploaded successfully."})
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
    with open(SCRIPT_PATH, 'r', encoding="utf-8") as f:
        script_content = f.read()

    # Đọc cookies nếu có
    cookies = None
    if os.path.exists(COOKIES_PATH):
        with open(COOKIES_PATH, 'r', encoding="utf-8") as f:
            try:
                cookies = json.load(f)
            except json.JSONDecodeError:
                 raise HTTPException(status_code=500, detail="Failed to load cookies. Invalid JSON format.")


    # Chạy Playwright
    try:
        # --- CÁCH TIẾP CẬN DÙNG subprocess ---
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


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
