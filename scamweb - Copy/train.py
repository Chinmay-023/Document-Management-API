import pandas as pd
import pickle
import numpy as np
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import SGDClassifier
from sklearn.preprocessing import LabelEncoder
from scipy.sparse import hstack

# Load dataset
df = pd.read_csv("data/spam.csv", encoding="latin-1")[["v1","v2"]]
df.columns = ["label","message"]

label_encoder = LabelEncoder()
y = label_encoder.fit_transform(df["label"])

vectorizer = TfidfVectorizer(max_features=5000)
X_text = vectorizer.fit_transform(df["message"])

def extract_features(message):
    message_lower = message.lower()

    url_count = len(re.findall(r'http[s]?://|www\.', message))
    number_count = len(re.findall(r'\d+', message))
    exclamation_count = message.count("!")
    capital_ratio = sum(1 for c in message if c.isupper()) / max(len(message), 1)
    contains_money = int(bool(re.search(r'\$|₹|€|rs|inr', message_lower)))
    contains_otp = int("otp" in message_lower)

    urgency_words = int(any(w in message_lower for w in [
        "urgent","immediately","now","verify","today","action required"
    ]))

    reward_words = int(any(w in message_lower for w in [
        "won","prize","lottery","reward"
    ]))

    financial_words = int(any(w in message_lower for w in [
        "bank","account","credit","debit","transaction"
    ]))

    authority_words = int(any(w in message_lower for w in [
        "verification officer","compliance desk",
        "background check","identity profile",
        "security department","legal notice"
    ]))

    isolation_words = int(any(w in message_lower for w in [
        "do not involve","remain on this call",
        "keep this confidential","internal review"
    ]))

    escalation_words = int(any(w in message_lower for w in [
        "system escalation","legal action",
        "case will be filed","profile suspended"
    ]))

    return [
        url_count, number_count, exclamation_count, capital_ratio,
        contains_money, contains_otp, urgency_words,
        reward_words, financial_words,
        authority_words, isolation_words, escalation_words
    ]

X_extra = np.array([extract_features(msg) for msg in df["message"]])

X_final = hstack([X_text, X_extra])

model = SGDClassifier(loss="log_loss")
model.fit(X_final, y)

# Save
pickle.dump(model, open("data/models/model.pkl","wb"))
pickle.dump(vectorizer, open("data/models/vectorizer.pkl","wb"))
pickle.dump(label_encoder, open("data/models/label_encoder.pkl","wb"))

print("Model retrained successfully with 12 features.")