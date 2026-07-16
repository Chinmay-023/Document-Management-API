import pickle
import numpy as np
import re
from scipy.sparse import hstack

# Load model + vectorizer
model = pickle.load(open("data/models/model.pkl", "rb"))
vectorizer = pickle.load(open("data/models/vectorizer.pkl", "rb"))

# SAME feature function as FastAPI
def extract_features(message):
    message_lower = message.lower()

    url_count = len(re.findall(r'http[s]?://|www\.', message))
    number_count = len(re.findall(r'\d+', message))
    exclamation_count = message.count("!")
    capital_ratio = sum(1 for c in message if c.isupper()) / max(len(message), 1)
    contains_money = int(bool(re.search(r'\$|₹|€|rs|inr', message_lower)))
    contains_otp = int("otp" in message_lower)
    urgency_words = int(any(w in message_lower for w in ["urgent", "immediately", "now", "verify"]))
    reward_words = int(any(w in message_lower for w in ["won", "prize", "lottery", "reward"]))
    financial_words = int(any(w in message_lower for w in ["bank", "account", "credit", "debit"]))

    return np.array([[ 
        url_count, number_count, exclamation_count, capital_ratio,
        contains_money, contains_otp, urgency_words,
        reward_words, financial_words
    ]])

def predict_message(text):
    text_vec = vectorizer.transform([text])
    extra = extract_features(text)
    final = hstack([text_vec, extra])

    probability = model.predict_proba(final)[0][1]

    if probability > 0.60:
        label = 1
    else:
        label = 0

    return label, probability

# Test
messages = [
    "Congratulations! You have won 50000 rupees. Click this link now.",
    "Hey bro, are we meeting today?",
    "Your bank account will be suspended. Verify immediately."
]

for msg in messages:
    pred, prob = predict_message(msg)

    print("\nMessage:", msg)
    print("Prediction:", "SCAM" if pred == 1 else "SAFE")
    print("Confidence:", round(prob * 100, 2), "%")