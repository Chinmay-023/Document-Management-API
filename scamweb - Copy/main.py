# =============================
# IMPORTS
# =============================

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import pickle
import sqlite3
import os
import re
import whisper
import numpy as np
from datetime import datetime
from scipy.sparse import hstack
import tempfile
import traceback
from groq import Groq
from deep_translator import GoogleTranslator
from langdetect import detect, LangDetectException


# =============================
# CONFIG
# =============================

SUPPORTED_LANGS = ["en", "hi", "kn"]

client = Groq(api_key="YOUR_API_KEY")
LLM_MODEL = "openai/gpt-oss-20b"


# =============================
# LOAD ML MODELS
# =============================

scam_model = pickle.load(open("data/models/model.pkl", "rb"))
vectorizer = pickle.load(open("data/models/vectorizer.pkl", "rb"))
label_encoder = pickle.load(open("data/models/label_encoder.pkl", "rb"))

speech_model = whisper.load_model("tiny")


# =============================
# DATABASE
# =============================

conn = sqlite3.connect("guardian_memory.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS scam_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message TEXT,
    prediction TEXT,
    confidence REAL,
    risk TEXT,
    timestamp TEXT
)
""")
conn.commit()


# =============================
# FASTAPI INIT
# =============================

app = FastAPI(title="Guardian Angel AI")

class MessageRequest(BaseModel):
    message: str


# =============================
# LANGUAGE HELPERS
# =============================

def detect_language_safe(text):
    try:
        lang = detect(text)
        if lang in SUPPORTED_LANGS:
            return lang
        return "en"
    except LangDetectException:
        return "en"


def translate_to_english(text):
    try:
        return GoogleTranslator(source="auto", target="en").translate(text)
    except:
        return text


def translate_from_english(text, target_lang):
    try:
        if target_lang == "en":
            return text
        return GoogleTranslator(source="en", target=target_lang).translate(text)
    except:
        return text


# =============================
# FEATURE ENGINEERING (UPGRADED)
# =============================

def extract_features(message):
    message_lower = message.lower()

    url_count = len(re.findall(r'http[s]?://|www\.', message))
    number_count = len(re.findall(r'\d+', message))
    exclamation_count = message.count("!")
    capital_ratio = sum(1 for c in message if c.isupper()) / max(len(message), 1)

    contains_money = int(bool(re.search(r'\$|₹|€|rs|inr', message_lower)))
    contains_otp = int("otp" in message_lower)

    urgency_words = int(any(w in message_lower for w in [
        "urgent", "immediately", "now", "verify", "today",
        "right now", "action required"
    ]))

    reward_words = int(any(w in message_lower for w in [
        "won", "prize", "lottery", "reward"
    ]))

    financial_words = int(any(w in message_lower for w in [
        "bank", "account", "credit", "debit", "transaction"
    ]))

    # 🔥 NEW: Social Engineering Detection
    authority_words = int(any(w in message_lower for w in [
        "verification officer", "compliance desk",
        "background check", "identity profile",
        "security department", "legal notice"
    ]))

    isolation_words = int(any(w in message_lower for w in [
        "do not involve", "remain on this call",
        "keep this confidential", "internal review"
    ]))

    escalation_words = int(any(w in message_lower for w in [
        "system escalation", "legal action",
        "case will be filed", "profile suspended"
    ]))

    return np.array([[
        url_count, number_count, exclamation_count, capital_ratio,
        contains_money, contains_otp, urgency_words,
        reward_words, financial_words,
        authority_words, isolation_words, escalation_words
    ]])


# =============================
# RISK CALCULATION
# =============================

def calculate_risk(prob):
    if prob > 0.85:
        return "HIGH"
    elif prob > 0.60:
        return "MEDIUM"
    else:
        return "LOW"


# =============================
# LLM CLASSIFIER (OVERRIDE)
# =============================

def llm_classify_scam(message):
    prompt = f"""
You are a cybersecurity expert.

Analyze this message and decide if it is a SCAM or SAFE.

Message:
"{message}"

Answer ONLY with one word:
SCAM or SAFE
"""

    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )

    return response.choices[0].message.content.strip().upper()


# =============================
# LLM ADVICE
# =============================

def generate_llm_advice(message, prediction, confidence, risk):

    prompt = f"""
You are a cybersecurity assistant.

Message:
"{message}"

Final Prediction: {prediction}
Confidence: {confidence}%
Risk Level: {risk}

Explain:
1. Why it is {prediction}
2. What the user should do

Keep it simple and practical.
Respond only in English.
"""

    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )

    return response.choices[0].message.content


# =============================
# CORE ANALYSIS (HYBRID AI)
# =============================

# =============================
# CORE ANALYSIS (HYBRID AI) - UPDATED
# =============================

def analyze_message(message: str):
    detected_lang = detect_language_safe(message)
    message_en = translate_to_english(message) if detected_lang != "en" else message

    # --- 1. ML Prediction (The "Original" Stats) ---
    text_vector = vectorizer.transform([message_en])
    extra = extract_features(message_en)
    final_features = hstack([text_vector, extra])

    # Get the raw probability from the ML model
    ml_prob = float(scam_model.predict_proba(final_features)[0][1])
    ml_pred_idx = 1 if ml_prob > 0.55 else 0
    ml_prediction = label_encoder.inverse_transform([ml_pred_idx])[0]

    # --- 2. LLM Override ---
    llm_prediction = llm_classify_scam(message_en)

    # Logic: Determine Final Prediction
    # We prioritize the LLM if it flags a SCAM the ML missed
    if llm_prediction == "SCAM":
        final_prediction = "SCAM"
        # Adjusted confidence: if ML was low but LLM caught it, we report a higher "Final" confidence
        final_confidence = max(ml_prob, 0.82) 
    else:
        final_prediction = ml_prediction
        final_confidence = ml_prob

    risk_level = calculate_risk(final_confidence)

    # --- 3. Generate Advice ---
    llm_en_advice = generate_llm_advice(
        message_en,
        final_prediction,
        round(final_confidence * 100, 2),
        risk_level
    )
    
    # Translate advice back to user's native language
    llm_final_advice = translate_from_english(llm_en_advice, detected_lang)

    # --- 4. Database Logging ---
    cursor.execute("""
        INSERT INTO scam_logs (message, prediction, confidence, risk, timestamp)
        VALUES (?, ?, ?, ?, ?)
    """, (
        message,
        final_prediction,
        final_confidence,
        risk_level,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))
    conn.commit()

    # --- 5. Clean UI Response ---
    return {
        "status": "success",
        "data": {
            "prediction": final_prediction,
            "risk_level": risk_level,
            "final_confidence": round(final_confidence * 100, 2),
            "original_ml_score": round(ml_prob * 100, 2), # This is your original scam %
            "llm_verdict": llm_prediction,
            "detected_language": detected_lang,
            "analysis_report": llm_final_advice,
            "metadata": {
                "is_translated": detected_lang != "en",
                "processed_at": datetime.now().isoformat()
            }
        }
    }


# =============================
# TEXT ENDPOINT
# =============================

@app.post("/predict")
def predict(data: MessageRequest):
    return analyze_message(data.message)


# =============================
# VOICE ENDPOINT
# =============================

@app.post("/voice_predict")
async def voice_predict(file: UploadFile = File(...)):

    temp_path = None
    try:
        extension = os.path.splitext(file.filename)[1].lower()
        allowed = [".wav",".mp3",".m4a",".aac",".flac",".ogg",".webm"]

        if extension not in allowed:
            raise HTTPException(status_code=400, detail="Unsupported audio format")

        with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as tmp:
            tmp.write(await file.read())
            temp_path = tmp.name

        result = speech_model.transcribe(temp_path, fp16=False)
        transcript = result.get("text","").strip()

        if not transcript:
            raise HTTPException(status_code=400, detail="No speech detected")

        analysis = analyze_message(transcript)

        return {
            "whisper_detected_language": result.get("language"),
            "transcript": transcript,
            **analysis
        }

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)