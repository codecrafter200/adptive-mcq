def detect_doubt(text):
    # Placeholder logic for detecting doubt
    keywords = ["confused", "unsure", "doubt", "question"]
    return "With doubt" if any(keyword in text.lower() for keyword in keywords) else "No doubt"