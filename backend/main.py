import uuid
from fastapi import FastAPI, Request, Response
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from pypinyin import lazy_pinyin, Style
import httpx
from fastapi import HTTPException
from storage import init_db, save_record, get_history
from datetime import datetime, timezone
import os
from dotenv import load_dotenv

load_dotenv()                        # ← 读同目录下的 .env

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS").split(",")


init_db()  # 初始化数据库（如果不存在则创建）

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
    allow_credentials=True,
)

def get_session_id(request: Request, response: Response) -> str:
    sid = request.cookies.get("session_id")      # 先看有没有纸条
    if not sid:                                  # 第一次来，没有——发一张
        sid = uuid.uuid4().hex                    # 一串随机、不重复的 id
        response.set_cookie(
            "session_id", sid,
            httponly=True, samesite="lax",
            max_age=60 * 60 * 24 * 30,            # 记 30 天
        )
    return sid


profile = {
    "heroTitle": "关于我",
    "heroSubtitle": "项目，创意，灵感，心得，我的作品",
    "featuredWork": {
        "kicker": "作品",
        "title": "文字实验室",
        "copy": "拼音和情绪，挖掘中文里的细节",
        "linkLabel": "打开作品",
    },
    "identity": {
        "motto": "已识乾坤大，尤怜草木青",
        "learning": "零到全栈",
    },
}

class AnalyzeRequest(BaseModel):
    text: str

@app.get("/api/profile")
def get_profile():
    return profile

def score_label(score):
    if score >= 0.6:
        return "偏积极"
    elif score <= 0.4:
        return "偏消极"
    else:
        return "中性"


@app.post("/api/analyze")
def analyze(req: AnalyzeRequest, request: Request, response: Response):
    sid = get_session_id(request, response)
    text = req.text
    # score = round(SnowNLP(text).sentiments, 2)
    score, label = jev_sentiment(text)
    result = {
        "text": text,
        "score": score,
        "label": label,
        "pinyin": " ".join(lazy_pinyin(text, style=Style.TONE)),
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    save_record(sid, result)          # 存的时候盖上这个会话的记号
    return result                     # ← 返回体一个字没变，session_id 只走 cookie

@app.get("/api/history")
def history(request: Request, response: Response, limit: int = 10):
    sid = get_session_id(request, response)
    return get_history(sid, limit)    # 只回这个会话自己的

def jev_sentiment(text: str):
    key = os.getenv("TYPESAFE_API_KEY")
    if not key:
        raise HTTPException(status_code=503, detail="未配置 TYPESAFE_API_KEY")

    try:
        res = httpx.post(
            "https://api.typesafe.ai/v1/systemone",
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": "jev-latest",
                "state": text,
                "questions": {
                    "sentiment": {
                        "type": "choice",
                        "instructions": "判断这段中文表达的整体情感倾向，而不是仅根据个别褒贬词判断。",
                        "criteria": {
                            "negative": "整体偏消极，包括失望、难过、不满等",
                            "neutral": "整体中性，或积极与消极并存且无明显倾向",
                            "positive": "整体偏积极，包括喜悦、满意、期待等",
                        },
                    }
                },
            },
            timeout=10.0,
        )
        res.raise_for_status()
        answer = res.json()["answers"]["sentiment"]
        probabilities = answer["probabilities"]
        # 情感位置：0=消极，0.5=中性，1=积极；不是“预测正确率”
        score = round(
            probabilities["positive"] + 0.5 * probabilities["neutral"], 2
        )
        label = {
            "negative": "偏消极",
            "neutral": "中性",
            "positive": "偏积极",
        }[answer["choice"]]
        return score, label
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        raise HTTPException(status_code=502, detail="Jev 情感分析服务暂不可用") from exc
