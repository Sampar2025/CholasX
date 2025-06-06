from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os
import json
import time
from datetime import datetime

app = Flask(__name__)
CORS(app)  # Enable CORS for WordPress integration

# Configuration
PERPLEXITY_API_KEY = os.environ.get('PERPLEXITY_API_KEY')
PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"

# UK Building Material Suppliers for domain filtering
UK_SUPPLIERS = [
    "buildbase.co.uk",
    "wickes.co.uk", 
    "screwfix.com",
    "toolstation.com",
    "jewson.co.uk",
    "travisperkins.co.uk",
    "selco.co.uk",
    "homebase.co.uk",
    "diy.com",
    "machinemart.co.uk",
    "builderdepot.co.uk",
    "roofingoutlet.co.uk",
    "insulationshop.co.uk"
]

def enhance_query(query, location="UK"):
    """Enhance the user query for better AI search results"""
    enhanced = f"Find the cheapest prices for {query} in {location}. "
    enhanced += "Include product specifications, pricing per unit, supplier names, "
    enhanced += "contact information, and availability. Focus on UK building material suppliers."
    return enhanced

def call_perplexity_api(query, max_results=5):
    """Call Perplexity API with enhanced query"""
    if not PERPLEXITY_API_KEY:
        raise Exception("Perplexity API key not configured")
    
    # Create domain filter string
    domain_filter = " OR ".join([f"site:{domain}" for domain in UK_SUPPLIERS])
    
    enhanced_query = enhance_query(query)
    
    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "llama-3.1-sonar-small-128k-online",
        "messages": [
            {
                "role": "system",
                "content": f"You are a building materials price comparison expert. Search only these UK suppliers: {', '.join(UK_SUPPLIERS)}. Always provide specific pricing, supplier names, contact details, and product specifications. Format your response as a structured list with clear product information."
            },
            {
                "role": "user", 
                "content": enhanced_query
            }
        ],
        "search_domain_filter": UK_SUPPLIERS,
        "return_citations": True,
        "search_recency_filter": "month",
        "temperature": 0.2,
        "max_tokens": 2000
    }
    
    try:
        response = requests.post(PERPLEXITY_API_URL, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        raise Exception(f"API request failed: {str(e)}")

def parse_ai_response(ai_response):
    """Parse AI response into structured product data"""
    try:
        content = ai_response['choices'][0]['message']['content']
        citations = ai_response.get('citations', [])
        
        # Extract structured information from the AI response
        products = []
        
        # Simple parsing - in production, you might want more sophisticated NLP
        lines = content.split('\n')
        current_product = {}
        
        for line in lines:
            line = line.strip()
            if not line:
                if current_product:
                    products.append(current_product)
                    current_product = {}
                continue
                
            # Look for product patterns
            if any(keyword in line.lower() for keyword in ['£', 'price', 'cost']):
                # Extract price information
                import re
                price_match = re.search(r'£[\d,]+\.?\d*', line)
                if price_match and 'product_name' in current_product:
                    current_product['price'] = price_match.group()
                    current_product['raw_text'] = line
            
            # Look for supplier information
            for supplier_domain in UK_SUPPLIERS:
                supplier_name = supplier_domain.split('.')[0].title()
                if supplier_name.lower() in line.lower():
                    current_product['supplier'] = supplier_name
                    current_product['supplier_url'] = f"https://{supplier_domain}"
                    break
            
            # If line contains product-like information and no current product
            if not current_product.get('product_name') and len(line) > 10:
                current_product['product_name'] = line
        
        # Add final product if exists
        if current_product:
            products.append(current_product)
        
        # If no structured products found, create a general response
        if not products:
            products = [{
                'product_name': 'Search Results',
                'price': 'See details below',
                'supplier': 'Multiple Suppliers',
                'raw_text': content,
                'supplier_url': '#'
            }]
        
        # Ensure all products have required fields
        for product in products:
            product.setdefault('product_name', 'Building Material')
            product.setdefault('price', 'Contact for price')
            product.setdefault('supplier', 'UK Supplier')
            product.setdefault('availability', 'Contact supplier')
            product.setdefault('location', 'UK')
            product.setdefault('delivery_info', 'Contact for delivery options')
            product.setdefault('supplier_url', '#')
        
        return {
            'results': products[:5],  # Limit to 5 results
            'ai_summary': content,
            'citations': citations,
            'search_metadata': {
                'total_results': len(products),
                'sources_checked': len(UK_SUPPLIERS),
                'search_time': 'Real-time'
            }
        }
        
    except Exception as e:
        raise Exception(f"Failed to parse AI response: {str(e)}")

@app.route('/', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'AI Building Materials Search API',
        'version': '1.0',
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/search', methods=['POST'])
def search_products():
    """Main search endpoint for WordPress integration"""
    try:
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        query = data.get('query', '').strip()
        location = data.get('location', 'UK').strip()
        max_results = min(int(data.get('max_results', 5)), 10)  # Limit to 10 max
        
        if not query:
            return jsonify({'error': 'Query parameter is required'}), 400
        
        if len(query) < 3:
            return jsonify({'error': 'Query must be at least 3 characters long'}), 400
        
        # Record start time
        start_time = time.time()
        
        # Call Perplexity API
        ai_response = call_perplexity_api(query, max_results)
        
        # Parse response
        parsed_results = parse_ai_response(ai_response)
        
        # Add timing information
        search_time = round(time.time() - start_time, 2)
        parsed_results['search_metadata']['search_time'] = f"{search_time}s"
        
        return jsonify(parsed_results)
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'message': 'Search failed. Please try again or contact support.'
        }), 500

@app.route('/api/search/demo', methods=['GET'])
def demo_search():
    """Demo endpoint with sample data"""
    return jsonify({
        'results': [
            {
                'product_name': 'Kingspan Therma PIR Insulation Board 50mm',
                'price': '£24.99',
                'price_per_unit': '£8.33 per m²',
                'supplier': 'Buildbase',
                'availability': 'In Stock',
                'location': 'Multiple UK locations',
                'delivery_info': 'Next day delivery available',
                'supplier_phone': '0330 123 4567',
                'supplier_url': 'https://buildbase.co.uk'
            },
            {
                'product_name': 'Celotex GA4050 PIR Board 50mm',
                'price': '£26.50',
                'price_per_unit': '£8.83 per m²',
                'supplier': 'Wickes',
                'availability': 'In Stock',
                'location': 'UK Wide',
                'delivery_info': 'Free delivery on orders over £75',
                'supplier_phone': '0330 123 4321',
                'supplier_url': 'https://wickes.co.uk'
            }
        ],
        'ai_summary': 'Found multiple PIR insulation boards available from UK suppliers. Kingspan offers the best value at £8.33 per m², while Celotex provides premium quality at £8.83 per m². Both suppliers offer reliable delivery options.',
        'search_metadata': {
            'total_results': 2,
            'sources_checked': 13,
            'search_time': '2.1s'
        }
    })

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

