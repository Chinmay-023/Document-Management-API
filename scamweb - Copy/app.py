import streamlit as st
import requests
import sounddevice as sd
import numpy as np
import tempfile
import os
from scipy.io.wavfile import write

API_URL = "http://127.0.0.1:8000"

st.set_page_config(page_title="Guardian Angel AI", layout="centered")

# =========================
# SESSION STATE (PER TAB)
# =========================

if "text_result" not in st.session_state:
    st.session_state.text_result = None

if "upload_result" not in st.session_state:
    st.session_state.upload_result = None

if "live_result" not in st.session_state:
    st.session_state.live_result = None


# =========================
# PREMIUM UI STYLING
# =========================

st.markdown("""
<style>
body { background-color:#0e1117; }

.main-title {
    font-size:42px;
    font-weight:800;
    text-align:center;
    color:white;
}

.subtitle {
    text-align:center;
    color:gray;
    margin-bottom:30px;
}

.safe-card {
    background: linear-gradient(135deg,#0f2027,#2c5364);
    padding:25px;
    border-radius:16px;
    color:#00ffae;
    border:1px solid #00ffae;
}

.scam-card {
    background: linear-gradient(135deg,#2b0f0f,#5f0f0f);
    padding:25px;
    border-radius:16px;
    color:#ff4d4d;
    border:1px solid #ff4d4d;
}

.listening {
    font-size:20px;
    color:#ffa726;
    font-weight:600;
}

.analyzing {
    font-size:20px;
    color:#29b6f6;
    font-weight:600;
}

.llm-box {
    background:#1a1f2b;
    padding:20px;
    border-radius:12px;
    border:1px solid #2c3e50;
    margin-top:15px;
    color:#e0e0e0;
}
</style>
""", unsafe_allow_html=True)

st.markdown("<div class='main-title'>🛡 Guardian Angel AI</div>", unsafe_allow_html=True)
st.markdown("<div class='subtitle'>Real-time Scam Call & Message Protection</div>", unsafe_allow_html=True)


# =========================
# RESULT DISPLAY FUNCTION
# =========================

def show_result(data, state_key):

    if data["prediction"] == "SAFE":
        st.markdown(f"""
        <div class='safe-card'>
        <h2>✅ SAFE</h2>
        <p><b>Confidence:</b> {data['confidence_percent']}%</p>
        <p><b>Risk:</b> {data['risk_level']}</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class='scam-card'>
        <h2>🚨 SCAM DETECTED</h2>
        <p><b>Confidence:</b> {data['confidence_percent']}%</p>
        <p><b>Risk:</b> {data['risk_level']}</p>
        </div>
        """, unsafe_allow_html=True)

    # Transcript
    if "transcript" in data and data["transcript"]:
        st.info("Transcript: " + data["transcript"])
    
    # Red flags
    if "red_flags" in data and data["red_flags"]:
        st.write("### 🔎 Detection Reasons")
        for f in data["red_flags"]:
            st.write("•", f)

    # ✅ LLM RESPONSE DISPLAY
    if "llm_analysis" in data and data["llm_analysis"]:
        st.write("### 🤖 AI Explanation")
        st.markdown(f"""
        <div class='llm-box'>
        {data["llm_analysis"]}
        </div>
        """, unsafe_allow_html=True)

    # Clear only this tab
    if st.button("🧹 Clear Results", key=f"clear_{state_key}"):
        st.session_state[state_key] = None
        st.rerun()


# =========================
# TABS
# =========================

tab1, tab2, tab3 = st.tabs(["📝 Text", "🎧 Upload Audio", "🎤 Live Detection"])


# =====================================================
# TEXT TAB
# =====================================================

with tab1:
    msg = st.text_area("Enter suspicious message")

    if st.button("Analyze Text", key="analyze_text_btn"):
        if msg.strip() != "":
            res = requests.post(f"{API_URL}/predict", json={"message": msg})
            if res.status_code == 200:
                st.session_state.text_result = res.json()

    if st.session_state.text_result:
        show_result(st.session_state.text_result, "text_result")


# =====================================================
# UPLOAD TAB
# =====================================================

with tab2:
    audio_file = st.file_uploader("Upload audio", type=["wav","mp3","m4a"])

    if st.button("Analyze Audio", key="analyze_audio_btn") and audio_file:
        files = {"file": (audio_file.name, audio_file, audio_file.type)}
        res = requests.post(f"{API_URL}/voice_predict", files=files)
        if res.status_code == 200:
            st.session_state.upload_result = res.json()

    if st.session_state.upload_result:
        show_result(st.session_state.upload_result, "upload_result")


# =====================================================
# LIVE TAB
# =====================================================

def record_until_silence(max_silence=5, sample_rate=16000):
    chunk = 1024
    threshold = 500
    silence_chunks = int((max_silence * sample_rate) / chunk)

    recording = []
    silent = 0

    status_text = st.empty()
    level_bar = st.empty()

    status_text.markdown("<div class='listening'>🎙 Listening...</div>", unsafe_allow_html=True)

    with sd.InputStream(samplerate=sample_rate, channels=1, dtype='int16') as stream:
        while True:
            data, _ = stream.read(chunk)
            recording.append(data)

            volume = np.abs(data).mean()
            level_bar.progress(min(int(volume / 1000 * 100), 100))

            if volume < threshold:
                silent += 1
            else:
                silent = 0

            if silent > silence_chunks and len(recording) > 20:
                break

    status_text.markdown("<div class='analyzing'>⚡ Analyzing...</div>", unsafe_allow_html=True)

    audio = np.concatenate(recording)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    write(tmp.name, sample_rate, audio)
    return tmp.name


with tab3:

    if st.button("🎤 Start Live Detection", key="live_detect_btn"):
        path = record_until_silence()

        if path:
            with open(path, "rb") as f:
                res = requests.post(f"{API_URL}/voice_predict", files={"file": f})
            os.remove(path)

            if res.status_code == 200:
                st.session_state.live_result = res.json()

    if st.session_state.live_result:
        show_result(st.session_state.live_result, "live_result")