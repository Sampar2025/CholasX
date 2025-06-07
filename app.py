import pickle
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import os

app = Flask(__name__)
CORS(app)

# Load model when app starts
print("Loading Building Materials Search Model...")
try:
    with open('building_materials_model.pkl', 'rb') as f:
        model_data = pickle.load(f)
    
    knowledge_base = model_data['knowledge_base']
    vectorizer = model_data['vectorizer']
    query_vectors = model_data['query_vectors']
    queries = model_data['queries']
    responses = model_data['responses']
    print("✅ Model loaded successfully!")
except Exception as e:
    print(f"❌ Error loading model: {e}")
    knowledge_base = {}
    vectorizer = None
    query_vectors = None
    queries = []
    responses = []

def search_materials(user_query, top_k=3):
    """Search for building materials based on user query"""
    if not vectorizer:
        return {"results": [], "error": "Model not loaded"}
    
    user_query_lower = user_query.lower()
    
    # Direct match first
    if user_query_lower in knowledge_base:
        response_data = json.loads(knowledge_base[user_query_lower])
        return {
            "results": response_data.get('results', []),
            "confidence": 1.0,
            "query_matched": user_query
        }
    
    # Semantic similarity search
    user_vector = vectorizer.transform([user_query_lower])
    similarities = cosine_similarity(user_vector, query_vectors)[0]
    
    # Get top matches
    top_indices = np.argsort(similarities)[::-1][:top_k]
    
    # Combine results from top matches
    all_results = []
    seen_suppliers = set()
    
    for idx in top_indices:
        if similarities[idx] > 0.1:  # Minimum similarity threshold
            try:
                response_data = json.loads(responses[idx])
                for result in response_data.get('results', []):
                    supplier = result.get('supplier', '')
                    if supplier not in seen_suppliers:
                        all_results.append(result)
                        seen_suppliers.add(supplier)
            except:
                continue
    
    # Sort by price if available
    def extract_price(result):
        price_str = result.get('price', '£0')
        try:
            return float(price_str.replace('£', '').replace(',', ''))
        except:
            return 999999
    
    all_results.sort(key=extract_price)
    
    return {
        "results": all_results[:5],  # Return top 5
        "confidence": float(max(similarities)) if len(similarities) > 0 else 0.0,
        "query_matched": user_query
    }

@app.route('/', methods=['GET'])
def health_check():
    return jsonify({
        "service": "Custom Building Materials Search API",
        "status": "healthy",
        "model": "Custom Trained Model",
        "version": "2.0",
        "products": "PIR Insulation + Plasterboard",
        "suppliers": 5
    })

@app.route('/api/search', methods=['POST'])
def search():
    try:
        data = request.get_json()
        query = data.get('query', '')
        
        if not query:
            return jsonify({"error": "Query is required"}), 400
        
        # Search using our custom model
        results = search_materials(query)
        
        if results.get('error'):
            return jsonify({"error": results['error']}), 500
        
        # Format response to match your WordPress plugin expectations
        return jsonify({
            "ai_summary": f"Found {len(results['results'])} suppliers for: {query}",
            "results": results['results'],
            "search_metadata": {
                "search_time": "0.1s",
                "total_results": len(results['results']),
                "confidence": results.get('confidence', 0.0),
                "model": "Custom Trained"
            }
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/search/demo', methods=['GET'])
def demo():
    return jsonify({
        "ai_summary": "Demo results from custom trained model",
        "results": [
            {
                "supplier": "insulation4less",
                "price": "£13.92",
                "product_name": "25mm Celotex TB4025 PIR Insulation Board 2400mm x 1200mm",
                "category": "PIR Insulation"
            },
            {
                "supplier": "cutpriceinsulation", 
                "price": "£14.13",
                "product_name": "25mm Celotex TB4025 PIR Insulation Board 2400mm x 1200mm",
                "category": "PIR Insulation"
            }
        ],
        "search_metadata": {
            "search_time": "0.1s",
            "total_results": 2,
            "model": "Custom Trained"
        }
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
