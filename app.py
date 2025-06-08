import json
import re
import pickle
import os
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

print("🔧 Loading Enhanced Building Materials Search API...")

# Load the enhanced AI model
try:
    with open('enhanced_building_materials_model.pkl', 'rb') as f:
        MODEL_DATA = pickle.load(f)
    print("✅ Enhanced AI model loaded successfully")
    print(f"📊 Model contains {len(MODEL_DATA['knowledge_base']['products'])} products")
except Exception as e:
    print(f"❌ Error loading enhanced model: {e}")
    MODEL_DATA = None

# Load enhanced knowledge base
try:
    with open('enhanced_knowledge_base.json', 'r') as f:
        ENHANCED_KNOWLEDGE_BASE = json.load(f)
    print(f"✅ Enhanced knowledge base loaded with {len(ENHANCED_KNOWLEDGE_BASE['products'])} products")
except Exception as e:
    print(f"❌ Error loading enhanced knowledge base: {e}")
    ENHANCED_KNOWLEDGE_BASE = None

def enhanced_search_products(query, max_results=5):
    """Enhanced product search using the trained AI model"""
    if not MODEL_DATA or not MODEL_DATA.get('vectorizer'):
        return []
    
    try:
        from sklearn.metrics.pairwise import cosine_similarity
        
        # Vectorize the query
        query_vector = MODEL_DATA['vectorizer'].transform([query])
        
        # Calculate similarities
        similarities = cosine_similarity(query_vector, MODEL_DATA['tfidf_matrix']).flatten()
        
        # Get top results
        top_indices = similarities.argsort()[-max_results:][::-1]
        
        results = []
        for idx in top_indices:
            if similarities[idx] > 0.1:  # Minimum similarity threshold
                product = MODEL_DATA['knowledge_base']['products'][idx]
                
                # Format result for API response
                result = {
                    "supplier": "CholasX",
                    "price": f"£{product['price']:.2f}",
                    "product_name": product['name'],
                    "category": product['product_type'],
                    "supplier_website": "https://cholasx.co.uk",
                    "product_image": product.get('image_url', ''),
                    "availability": "In Stock",
                    "delivery": "Next Day Delivery",
                    "contact": "020-3582-6399",
                    "rating": "5 stars",
                    "brand": product['brand'],
                    "thickness_mm": product.get('thickness_mm'),
                    "dimensions": f"{product.get('length_mm', 'N/A')}mm x {product.get('width_mm', 'N/A')}mm" if product.get('length_mm') else "N/A",
                    "price_per_sqm": f"£{product.get('price_per_sqm', 0):.2f}/m²" if product.get('price_per_sqm') else "N/A",
                    "similarity_score": float(similarities[idx])
                }
                results.append(result)
        
        return results
        
    except Exception as e:
        print(f"Error in enhanced search: {e}")
        return []

def enhanced_answer_query(query):
    """Enhanced query answering using the trained AI model"""
    if not MODEL_DATA or not MODEL_DATA.get('query_vectorizer'):
        return "I'm sorry, I don't have enough information to answer that question."
    
    try:
        from sklearn.metrics.pairwise import cosine_similarity
        
        # Vectorize user query
        user_vector = MODEL_DATA['query_vectorizer'].transform([query])
        
        # Find most similar queries
        similarities = cosine_similarity(user_vector, MODEL_DATA['query_vectors']).flatten()
        top_indices = similarities.argsort()[-3:][::-1]
        
        if similarities[top_indices[0]] > 0.3:  # Minimum similarity threshold
            return MODEL_DATA['responses'][top_indices[0]]
        else:
            # Try product search as fallback
            search_results = enhanced_search_products(query, max_results=3)
            if search_results:
                result_text = "Here are some relevant products:\\n"
                for result in search_results[:3]:
                    result_text += f"- {result['product_name']} ({result['price']})\\n"
                return result_text
            else:
                return "I'm sorry, I couldn't find relevant information for your query."
                
    except Exception as e:
        print(f"Error in enhanced query answering: {e}")
        return "I'm sorry, there was an error processing your query."

def get_category_products(category, max_results=10):
    """Get products by category"""
    if not ENHANCED_KNOWLEDGE_BASE:
        return []
    
    category_products = [
        p for p in ENHANCED_KNOWLEDGE_BASE['products'] 
        if category.lower() in p['product_type'].lower()
    ]
    
    # Sort by price
    category_products.sort(key=lambda x: x['price'])
    
    results = []
    for product in category_products[:max_results]:
        result = {
            "supplier": "CholasX",
            "price": f"£{product['price']:.2f}",
            "product_name": product['name'],
            "category": product['product_type'],
            "supplier_website": "https://cholasx.co.uk",
            "product_image": product.get('image_url', ''),
            "availability": "In Stock",
            "delivery": "Next Day Delivery",
            "contact": "020-3582-6399",
            "rating": "5 stars",
            "brand": product['brand'],
            "thickness_mm": product.get('thickness_mm'),
            "dimensions": f"{product.get('length_mm', 'N/A')}mm x {product.get('width_mm', 'N/A')}mm" if product.get('length_mm') else "N/A",
            "price_per_sqm": f"£{product.get('price_per_sqm', 0):.2f}/m²" if product.get('price_per_sqm') else "N/A"
        }
        results.append(result)
    
    return results

def get_price_range_products(min_price=0, max_price=1000, max_results=10):
    """Get products within price range"""
    if not ENHANCED_KNOWLEDGE_BASE:
        return []
    
    filtered_products = [
        p for p in ENHANCED_KNOWLEDGE_BASE['products'] 
        if min_price <= p['price'] <= max_price
    ]
    
    # Sort by price
    filtered_products.sort(key=lambda x: x['price'])
    
    results = []
    for product in filtered_products[:max_results]:
        result = {
            "supplier": "CholasX",
            "price": f"£{product['price']:.2f}",
            "product_name": product['name'],
            "category": product['product_type'],
            "supplier_website": "https://cholasx.co.uk",
            "product_image": product.get('image_url', ''),
            "availability": "In Stock",
            "delivery": "Next Day Delivery",
            "contact": "020-3582-6399",
            "rating": "5 stars",
            "brand": product['brand'],
            "thickness_mm": product.get('thickness_mm'),
            "dimensions": f"{product.get('length_mm', 'N/A')}mm x {product.get('width_mm', 'N/A')}mm" if product.get('length_mm') else "N/A",
            "price_per_sqm": f"£{product.get('price_per_sqm', 0):.2f}/m²" if product.get('price_per_sqm') else "N/A"
        }
        results.append(result)
    
    return results

@app.route('/')
def health_check():
    """Health check endpoint"""
    status = {
        "status": "healthy",
        "service": "Enhanced Building Materials Search API",
        "version": "2.0",
        "model_loaded": MODEL_DATA is not None,
        "knowledge_base_loaded": ENHANCED_KNOWLEDGE_BASE is not None
    }
    
    if ENHANCED_KNOWLEDGE_BASE:
        status.update({
            "total_products": len(ENHANCED_KNOWLEDGE_BASE['products']),
            "total_suppliers": len(ENHANCED_KNOWLEDGE_BASE['suppliers']),
            "categories": ENHANCED_KNOWLEDGE_BASE['product_types'],
            "brands": ENHANCED_KNOWLEDGE_BASE['brands']
        })
    
    return jsonify(status)

@app.route('/api/search', methods=['POST'])
def search():
    """Enhanced search endpoint"""
    try:
        data = request.get_json()
        query = data.get('query', '').strip()
        max_results = min(data.get('max_results', 5), 20)  # Limit to 20 results
        
        if not query:
            return jsonify({"error": "Query parameter is required"}), 400
        
        print(f"🔍 Enhanced search query: {query}")
        
        # Check for specific search types
        query_lower = query.lower()
        
        # Category search
        if any(cat.lower() in query_lower for cat in ['insulation', 'plasterboard', 'timber', 'cement']):
            for cat in ['insulation', 'plasterboard', 'timber', 'cement']:
                if cat in query_lower:
                    results = get_category_products(cat, max_results)
                    break
        # Price range search
        elif 'cheap' in query_lower or 'budget' in query_lower or 'under' in query_lower:
            # Extract price if mentioned
            price_match = re.search(r'under\s*£?(\d+)', query_lower)
            max_price = int(price_match.group(1)) if price_match else 50
            results = get_price_range_products(0, max_price, max_results)
        elif 'expensive' in query_lower or 'premium' in query_lower or 'over' in query_lower:
            price_match = re.search(r'over\s*£?(\d+)', query_lower)
            min_price = int(price_match.group(1)) if price_match else 100
            results = get_price_range_products(min_price, 1000, max_results)
        else:
            # General enhanced search
            results = enhanced_search_products(query, max_results)
        
        # If no results from enhanced search, try answering as a question
        if not results:
            answer = enhanced_answer_query(query)
            return jsonify({
                "query": query,
                "answer": answer,
                "results": [],
                "total_results": 0,
                "search_type": "conversational"
            })
        
        response = {
            "query": query,
            "results": results,
            "total_results": len(results),
            "search_type": "product_search",
            "message": f"Found {len(results)} products matching your search"
        }
        
        return jsonify(response)
        
    except Exception as e:
        print(f"❌ Search error: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/api/search/demo', methods=['GET'])
def demo():
    """Demo endpoint with sample enhanced data"""
    sample_results = enhanced_search_products("25mm insulation board", max_results=3)
    
    if not sample_results:
        # Fallback demo data
        sample_results = [
            {
                "supplier": "CholasX",
                "price": "£13.60",
                "product_name": "25mm Celotex TB4025 PIR Insulation Board 2400mm x 1200mm",
                "category": "PIR Insulation",
                "supplier_website": "https://cholasx.co.uk",
                "product_image": "https://cholasx.co.uk/wp-content/uploads/2024/12/25mm-celotex-tb4025-pir-insulation-board-2400mm-x-1200mm-2.jpg",
                "availability": "In Stock",
                "delivery": "Next Day Delivery",
                "contact": "020-3582-6399",
                "rating": "5 stars",
                "brand": "Celotex",
                "thickness_mm": 25,
                "dimensions": "2400mm x 1200mm",
                "price_per_sqm": "£4.72/m²"
            }
        ]
    
    return jsonify({
        "query": "25mm insulation board (demo)",
        "results": sample_results,
        "total_results": len(sample_results),
        "search_type": "demo",
        "message": "Demo results from enhanced AI model"
    })

@app.route('/api/categories', methods=['GET'])
def get_categories():
    """Get available product categories"""
    if ENHANCED_KNOWLEDGE_BASE:
        return jsonify({
            "categories": ENHANCED_KNOWLEDGE_BASE['product_types'],
            "brands": ENHANCED_KNOWLEDGE_BASE['brands'],
            "price_range": ENHANCED_KNOWLEDGE_BASE['price_ranges']
        })
    else:
        return jsonify({"error": "Knowledge base not available"}), 500

@app.route('/api/suppliers', methods=['GET'])
def get_suppliers():
    """Get available suppliers"""
    if ENHANCED_KNOWLEDGE_BASE:
        return jsonify({
            "suppliers": ENHANCED_KNOWLEDGE_BASE['suppliers'],
            "total_suppliers": len(ENHANCED_KNOWLEDGE_BASE['suppliers'])
        })
    else:
        return jsonify({"error": "Knowledge base not available"}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

