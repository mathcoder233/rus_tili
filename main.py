"""
QuizRoom - Online Test Platform
Copyright © 2026 Abduazim
Author: Abduazim
Email: fanwaguriservant@gmail.com
License: All rights reserved
"""

import sqlite3
import json
import uuid
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List

app = FastAPI()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# HTML fayllar turadigan papkani ulaymiz
templates = Jinja2Templates(directory="templates")

# --- DATABASE SOZLAMALARI ---
def init_db():
    conn = sqlite3.connect('quiz.db')
    cursor = conn.cursor()
    # Xonalar uchun jadval
    cursor.execute('''CREATE TABLE IF NOT EXISTS rooms 
                      (id TEXT PRIMARY KEY, name TEXT, status TEXT)''')
    # Savollar uchun jadval
    cursor.execute('''CREATE TABLE IF NOT EXISTS questions 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                       room_id TEXT, question_text TEXT, options TEXT, correct_index INTEGER)''')
    # Natijalar uchun jadval
    cursor.execute('''CREATE TABLE IF NOT EXISTS results 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                       room_id TEXT, user_name TEXT, score INTEGER, total INTEGER)''')
    conn.commit()
    conn.close()

# Dastur ishga tushganda bazani yaratish
init_db()

# --- MAXFIY PAROL ---
ADMIN_PASSWORD = "rustili.2508" # O'zingiz xohlagan parolni qo'ying

# --- MODELLAR ---
class CreateRoom(BaseModel):
    name: str
    raw_test: str
    password: str

class SubmitAnswer(BaseModel):
    user_name: str
    answers: List[int]

# --- YO'NALISHLAR (ROUTES) ---

# 1. Asosiy sahifa (Talabalar kirishi uchun)
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# 2. Admin sahifasi
@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    return templates.TemplateResponse("admin.html", {"request": request})

# 2.5 Test sahifasi (admin bilan bir xil)
@app.get("/test", response_class=HTMLResponse)
async def test_page(request: Request):
    return templates.TemplateResponse("admin.html", {"request": request})

# 3. API: Admin test yuklashi va xona ochishi
@app.post("/api/admin/create")
async def api_create_room(data: CreateRoom):
    if data.password != ADMIN_PASSWORD:
        return {"error": "Parol xato!"}
    
    # 6 xonali qisqa ID yaratamiz (Masalan: 'A1B2C3')
    room_id = str(uuid.uuid4())[:6].upper()
    conn = sqlite3.connect('quiz.db')
    cursor = conn.cursor()
    
    # Xonani yaratish
    cursor.execute("INSERT INTO rooms (id, name, status) VALUES (?, ?, ?)", (room_id, data.name, 'active'))
    
    # Testni matndan ajratib olish (Parser)
    blocks = data.raw_test.strip().split('---')
    for block in blocks:
        lines = [l.strip() for l in block.strip().split('\n') if l.strip()]
        q_text = ""
        opts = []
        correct = 0
        mapping = {"A": 0, "B": 1, "C": 2, "D": 3}
        
        for line in lines:
            if line.startswith("Savol:"): 
                q_text = line.replace("Savol:", "").strip()
            elif line.startswith("A:"): opts.append(line.replace("A:", "").strip())
            elif line.startswith("B:"): opts.append(line.replace("B:", "").strip())
            elif line.startswith("C:"): opts.append(line.replace("C:", "").strip())
            elif line.startswith("D:"): opts.append(line.replace("D:", "").strip())
            elif line.startswith("Javob:"):
                ans = line.replace("Javob:", "").strip().upper()
                correct = mapping.get(ans, 0)
        
        # Agar savol topilsa, bazaga saqlash
        if q_text:
            cursor.execute("INSERT INTO questions (room_id, question_text, options, correct_index) VALUES (?, ?, ?, ?)",
                           (room_id, q_text, json.dumps(opts), correct))
    
    conn.commit()
    conn.close()
    return {"room_id": room_id}

# 4. API: Talaba test xonasiga kirganda savollarni olishi
@app.get("/api/room/{room_id}")
async def get_room(room_id: str):
    conn = sqlite3.connect('quiz.db')
    cursor = conn.cursor()
    cursor.execute("SELECT name, status FROM rooms WHERE id=?", (room_id,))
    room = cursor.fetchone()
    if not room: 
        conn.close()
        return {"error": "Xona topilmadi"}
    
    # Savollarni olamiz, lekin to'g'ri javoblarni FRONTEND ga yubormaymiz (xavfsizlik)
    cursor.execute("SELECT question_text, options FROM questions WHERE room_id=?", (room_id,))
    qs = [{"q": r[0], "options": json.loads(r[1])} for r in cursor.fetchall()]
    conn.close()
    
    return {"name": room[0], "status": room[1], "questions": qs}

# 5. API: Talaba testni yakunlab, javoblarni yuborishi
@app.post("/api/submit/{room_id}")
async def submit_test(room_id: str, data: SubmitAnswer):
    conn = sqlite3.connect('quiz.db')
    cursor = conn.cursor()
    
    # To'g'ri javoblarni bazadan tortib olamiz
    cursor.execute("SELECT correct_index FROM questions WHERE room_id=? ORDER BY id", (room_id,))
    correct_answers = [r[0] for r in cursor.fetchall()]
    
    if not correct_answers:
        conn.close()
        return {"error": "Xona topilmadi yoki savollar yo'q"}
    
    # Ballni hisoblaymiz
    score = 0
    for i, ans in enumerate(data.answers):
        if i < len(correct_answers) and ans == correct_answers[i]:
            score += 1
            
    # Natijani saqlaymiz
    cursor.execute("INSERT INTO results (room_id, user_name, score, total) VALUES (?, ?, ?, ?)",
                   (room_id, data.user_name, score, len(correct_answers)))
    conn.commit()
    conn.close()
    
    return {"score": score, "total": len(correct_answers)}

# 6. API: Admin natijalarni ko'rishi
@app.get("/api/admin/results/{room_id}")
async def view_results(room_id: str, password: str):
    if password != ADMIN_PASSWORD: 
        return {"error": "Xato parol"}
        
    conn = sqlite3.connect('quiz.db')
    cursor = conn.cursor()
    cursor.execute("SELECT user_name, score, total FROM results WHERE room_id=?", (room_id,))
    res = [{"user": r[0], "score": r[1], "total": r[2]} for r in cursor.fetchall()]
    conn.close()
    
    return res