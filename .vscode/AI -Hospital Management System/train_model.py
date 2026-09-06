import pandas as pd
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.naive_bayes import MultinomialNB
import pickle

# Training data
data = {
    "symptoms": [
        "fever cough cold",
        "fever headache body pain",
        "stomach pain vomiting diarrhea",
        "chest pain breathing difficulty",
        "sneezing runny nose cough",
        "headache nausea",
        "stomach pain diarrhea",
        "cough sore throat fever"
    ],

    "disease": [
        "Flu",
        "Viral Infection",
        "Gastrointestinal Infection",
        "Requires Medical Evaluation",
        "Common Cold",
        "Migraine",
        "Gastrointestinal Infection",
        "Flu"
    ]
}

df = pd.DataFrame(data)

# Convert symptoms into numbers
vectorizer = CountVectorizer()

X = vectorizer.fit_transform(df["symptoms"])
y = df["disease"]

# Create and train AI model
model = MultinomialNB()
model.fit(X, y)

# Save model
with open("model.pkl", "wb") as file:
    pickle.dump(model, file)

# Save vectorizer
with open("vectorizer.pkl", "wb") as file:
    pickle.dump(vectorizer, file)

print("AI model trained successfully!")