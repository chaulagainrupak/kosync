#super simple python implementation for koreader progress sync server.

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import sqlite3

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

def init():
    conn = sqlite3.connect("users.db")
    db = conn.cursor()
    #password is basically the key provided by koreader
    db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS syncs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            document TEXT,
            progress TEXT,
            percentage REAL,
            device TEXT,
            deviceId TEXT,
            UNIQUE(username, document)
        )
    """)
    conn.commit()
    conn.close()

init()

@app.post("/users/create", status_code=201)
async def createUserAPI(request: Request):
    data = await request.json()
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        raise HTTPException(status_code=400, detail="Missing username or password")

    try:
        conn = sqlite3.connect("users.db")
        db = conn.cursor()
        db.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
        conn.commit()
        conn.close()
        return {"status": "user registered"}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=402, detail="User already exists")


@app.get("/users/auth")
async def verifyUser(request: Request):
    
    username = request.headers.get('x-auth-user')
    password = request.headers.get('x-auth-key')
    if not username or not password:
        raise HTTPException(status_code=400, detail="Missing username or password")

    conn = sqlite3.connect("users.db")
    db = conn.cursor()
    db.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
    result = db.fetchone()
    conn.close()

    if result:
        return {"status": "authorized"}
    else:
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.put("/syncs/progress")
async def updateProgress(request: Request):
    username = request.headers.get('x-auth-user')
    password = request.headers.get('x-auth-key')

    if not username or not password:
        raise HTTPException(status_code=400, detail="Missing username or password")

    # Verify user
    conn = sqlite3.connect("users.db")
    db = conn.cursor()
    db.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
    if not db.fetchone():
        conn.close()
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    try:
        data = await request.json()
        requiredFields = ["document", "progress", "percentage", "device", "device_id"]
        if not all(k in data for k in requiredFields):
            raise HTTPException(status_code=400, detail="Missing fields in sync payload")

        db.execute("""
            INSERT INTO syncs (username, document, progress, percentage, device, deviceId)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(username, document) DO UPDATE SET
                progress = excluded.progress,
                percentage = excluded.percentage,
                device = excluded.device,
                deviceId = excluded.deviceId
        """, (
            username, data["document"], data["progress"],
            data["percentage"], data["device"], data["device_id"]
        ))
        conn.commit()
        conn.close()

        return {"status": "progress updated"}
    except Exception as e:
        print("Sync error:", e)
        raise HTTPException(status_code=500, detail="Internal error")



@app.get("/syncs/progress/{document}")
def getProgress(document: str, request: Request):
    username = request.headers.get('x-auth-user')

    conn = sqlite3.connect("users.db")
    db = conn.cursor()
    db.execute("SELECT * FROM syncs WHERE username = ? AND document = ?", (username, document))
    result = db.fetchone()
    conn.close()

    if result:
        _, _, doc, progress, percentage, device, deviceId = result
        return {
            "document": doc,
            "progress": progress,
            "percentage": percentage,
            "device": device,
            "device_id": deviceId
        }
    else:
        raise HTTPException(status_code=401, detail="No progress found")


@app.exception_handler(404)
async def notFoundHandler(request: Request, exc):
    return JSONResponse(status_code=404, content={"error": "Route not found"})
