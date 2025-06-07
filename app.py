import json
from flask import Flask, request, jsonify
from flask_cors import CORS
import re

app = Flask(__name__)
CORS(app)

# Simple knowledge base - no external dependencies needed
KNOWLEDGE_BASE = {
    # PIR Insulation 25mm
    "cheapest 25mm pir insulation": {
        "results": [
            {"supplier": "insulation4less", "price": "£13.92", "product_name": "25mm Celotex TB4025 PIR Insulation Board 2400mm x 1200mm", "category": "PIR Insulation"},
            {"supplier": "cutpriceinsulation", "price": "£14.13", "product_name": "25mm Celotex TB4025 PIR Insulation Board 2400mm x 1200mm", "category": "PIR Insulation"},
            {"supplier": "nationalinsulationsupplies", "price": "£14.33", "product_name": "25mm Celotex TB4025 PIR Insulation Board 2400mm x 1200mm", "category": "PIR Insulation"},
            {"supplier": "buildersinsulation", "price": "£15.05", "product_name": "25mm Celotex TB4025 PIR Insulation Board 2400mm x 1200mm", "category": "PIR Insulation"},
            {"supplier": "insulationuk", "price": "£15.84", "product_name": "25mm Celotex TB4025 PIR Insulation Board 2400mm x 1200mm", "category": "PIR Insulation"}
        ]
    },
    # Plasterboard 9.5mm
    "plasterboard 9.5mm price": {
        "results": [
            {"supplier": "insulation4less", "price": "£8.32", "product_name": "Siniat Standard Plasterboard 2400mm x 1200mm x 9.5mm", "category": "Plasterboard"},
            {"supplier": "cutpriceinsulation", "price": "£8.88", "product_name": "Siniat Standard Plasterboard 2400mm x 1200mm x 9.5mm", "category": "Plasterboard"},
            {"supplier": "nationalinsulationsupplies", "price": "£9.00", "product_name": "Siniat Standard Plasterboard 2400mm x 1200mm x 9.5mm", "category": "Plasterboard"},
            {"supplier": "buildersinsulation", "price": "£9.39", "product_name": "Siniat Standard Plasterboard 2400mm x 1200mm x 9.5mm", "category": "Plasterboard"},
            {"supplier": "insulationuk", "price": "£10.58", "product_name": "Siniat Standard Plasterboard 2400mm x 1200mm x 9.5mm", "category": "Plasterboard"}
        ]
    }
}

# Keywords for matching
PIR_KEYWORDS = ["pir", "insulation", "celotex", "thermal", "25mm", "50mm", "100mm"]
PLASTERBOARD_KEYWORDS = ["plasterboard", "plaster", "board", "siniat", "9.5mm", "12.5mm", "wall"]

def simple_search(query):
    """Simple keyword-based search"""
    query_lower = query.lower()
    
    # Direct matches first
    for key, data in KNOWLEDGE_BASE.items():
        if key in query_lower:
            return data["results"]
    
    # Keyword matching
    pir_score = sum(1 for keyword in PIR_KEYWORDS if keyword in query_lower)
    plaster_score = sum(1 for keyword in PLASTERBOARD_KEYWORDS if keyword in query_lower)
    
    if pir_score > plaster_score:
        # Return PIR results
        return KNOWLEDGE_BASE["cheapest 25mm pir insulation"]["results"]
    elif plaster_score > 0:
        # Return plasterboard results
        return KNOWLEDGE_BASE["plasterboard 9.5mm price"]["results"]
    else:
        # Default to PIR if unclear
        return KNOWLEDGE_BASE["cheapest 25mm pir insulation"]["results"]

@app.route('/', methods=['GET'])
def health_check():
    return jsonify({
        "service": "Custom Building Materials Search API",
        "status": "healthy",
        "model": "Simple Keyword Matching",
        "version": "3.0",
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
        
        # Search using simple keyword matching
        results = simple_search(query)
        
        return jsonify({
            "ai_summary": f"Found {len(results)} suppliers for: {query}",
            "results": results,
            "search_metadata": {
                "search_time": "0.1s",
                "total_results": len(results),
                "model": "Simple Keyword Matching"
            }
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/search/demo', methods=['GET'])
def demo():
    return jsonify({
        "ai_summary": "Demo results from simple keyword matching",
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
            "model": "Simple Keyword Matching"
        }
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
