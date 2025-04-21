from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

def get_alignment_score(journal, objectives):
    # Combine the journal text with learning objectives
    all_text = [journal] + objectives
    
    # Compute TF-IDF vectors
    tfidf = TfidfVectorizer().fit_transform(all_text)
    
    # Calculate cosine similarity between the journal and each objective
    similarity = cosine_similarity(tfidf[0:1], tfidf[1:])[0]
    
    # Return alignment scores as a dictionary
    return {f"LO_{i+1}": round(score, 2) for i, score in enumerate(similarity)}