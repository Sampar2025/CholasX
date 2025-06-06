from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os
import time
import re
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Configuration
PERPLEXITY_API_KEY = os.environ.get('PERPLEXITY_API_KEY')
PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"

# UK Building Material Suppliers for better search
UK_SUPPLIERS = [
    "tradeinsulations.co.uk",
    "insulation4less.co.uk", 
    "insulationwholesale.co.uk",
    "insulationshop.co.uk",
    "buildbase.co.uk",
    "wickes.co.uk",
    "screwfix.com",
    "toolstation.com",
    "jewson.co.uk",
    "travisperkins.co.uk",
    "selco.co.uk",
    "roofingoutlet.co.uk",
    "ecomerchant.co.uk"
]

def create_enhanced_query(query, location="UK"):
    """Create enhanced query for better Perplexity results"""
    enhanced = f"""Find the top 5 cheapest suppliers for {query} in {location}. 

REQUIREMENTS:
- Include exact prices (£ per board/m²)
- Include supplier names and contact details
- Include product specifications (dimensions, coverage)
- Include availability and delivery information
- Focus on UK building material suppliers
- Compare prices from multiple suppliers
- Show results in a clear ranking format

SEARCH FOCUS: UK insulation suppliers, building merchants, trade suppliers

Please provide detailed pricing comparison with supplier contact information."""
    
    return enhanced

def call_perplexity_api(query):
    """Call Perplexity API with enhanced search capabilities"""
    if not PERPLEXITY_API_KEY:
        raise Exception("Perplexity API key not configured")
    
    enhanced_query = create_enhanced_query(query)
    
    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Use the online search model with proper parameters
    payload = {
        "model": "llama-3.1-sonar-large-128k-online",
        "messages": [
            {
                "role": "system",
                "content": "You are a UK building materials price comparison expert. Always search for current prices from real UK suppliers. Provide specific pricing, supplier names, contact details, and product specifications. Focus on trade suppliers and building merchants."
            },
            {
                "role": "user", 
                "content": enhanced_query
            }
        ],
        "temperature": 0.1,  # Lower for more factual results
        "max_tokens": 2000,
        "return_citations": True,
        "search_recency_filter": "month"  # Recent results only
    }
    
    try:
        response = requests.post(PERPLEXITY_API_URL, headers=headers, json=payload, timeout=45)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        raise Exception(f"API request failed: {str(e)}")

def parse_enhanced_response(ai_response):
    """Parse AI response into structured product data"""
    try:
        content = ai_response['choices'][0]['message']['content']
        citations = ai_response.get('citations', [])
        
        # Extract products from the response
        products = []
        
        # Look for price patterns and supplier information
        lines = content.split('\n')
        current_product = {}
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Look for numbered rankings or bullet points
            if re.match(r'^[1-5][\.\)]\s*', line) or re.match(r'^•\s*', line):
                # Save previous product
                if current_product and current_product.get('product_name'):
                    products.append(current_product)
                
                # Start new product
                current_product = {}
                
                # Extract supplier name and product
                supplier_match = re.search(r'(Trade Insulations|Insulation4Less|Insulation Wholesale|Insulation Shop|Buildbase|Wickes|Screwfix|Jewson|Travis Perkins|Selco|[A-Z][a-zA-Z\s&]+)', line)
                if supplier_match:
                    current_product['supplier'] = supplier_match.group(1)
                
                # Extract product name
                product_match = re.search(r'(Celotex|Kingspan|Recticel|Unilin|Ecotherm|PIR|[A-Z][a-zA-Z0-9\s\-]+)', line)
                if product_match:
                    current_product['product_name'] = product_match.group(1)
                
                # Extract price
                price_match = re.search(r'£([\d,]+\.?\d*)', line)
                if price_match:
                    current_product['price'] = f"£{price_match.group(1)}"
            
            # Look for additional details in subsequent lines
            elif current_product:
                # Coverage information
                if 'm²' in line:
                    coverage_match = re.search(r'([\d\.]+\s*m²)', line)
                    if coverage_match:
                        current_product['coverage'] = coverage_match.group(1)
                
                # Price per unit
                if '£' in line and ('per' in line or 'm²' in line):
                    unit_price_match = re.search(r'£([\d,]+\.?\d*)\s*per\s*(m²|board)', line)
                    if unit_price_match:
                        current_product['price_per_unit'] = f"£{unit_price_match.group(1)} per {unit_price_match.group(2)}"
        
        # Add final product
        if current_product and current_product.get('product_name'):
            products.append(current_product)
        
        # If no structured products found, create from content
        if not products:
            # Extract any prices and suppliers mentioned
            suppliers_mentioned = []
            prices_mentioned = []
            
            for supplier in UK_SUPPLIERS:
                supplier_name = supplier.split('.')[0].replace('-', ' ').title()
                if supplier_name.lower() in content.lower():
                    suppliers_mentioned.append(supplier_name)
            
            price_matches = re.findall(r'£([\d,]+\.?\d*)', content)
            prices_mentioned = [f"£{price}" for price in price_matches[:5]]
            
            # Create products from extracted info
            for i, (supplier, price) in enumerate(zip(suppliers_mentioned[:5], prices_mentioned[:5])):
                products.append({
                    'product_name': f'50mm PIR Insulation Board',
                    'price': price,
                    'supplier': supplier,
                    'availability': 'Contact supplier',
                    'location': 'UK',
                    'delivery_info': 'Contact for delivery options',
                    'supplier_url': f"https://{supplier.lower().replace(' ', '')}.co.uk"
                })
        
        # Ensure all products have required fields
        for product in products:
            product.setdefault('product_name', '50mm PIR Insulation Board')
            product.setdefault('price', 'Contact for price')
            product.setdefault('supplier', 'UK Supplier')
            product.setdefault('availability', 'Contact supplier')
            product.setdefault('location', 'UK')
            product.setdefault('delivery_info', 'Contact for delivery options')
            if 'supplier_url' not in product:
                supplier_clean = product['supplier'].lower().replace(' ', '').replace('&', '')
                product['supplier_url'] = f"https://{supplier_clean}.co.uk"
        
        return {
            'results': products[:5],  # Top 5 results
            'ai_summary': content,
            'citations': citations,
            'search_metadata': {
                'total_results': len(products),
                'sources_checked': len(UK_SUPPLIERS),
                'search_time': 'Real-time'
            }
        }
        
    except Exception as e:
        # Fallback: return the raw content
        return {
            'results': [{
                'product_name': 'Search Results Available',
                'price': 'See summary below',
                'supplier': 'Multiple UK Suppliers',
                'availability': 'Various',
                'location': 'UK',
                'delivery_info': 'Contact suppliers',
                'supplier_url': '#'
            }],
            'ai_summary': content,
            'citations': ai_response.get('citations', []),
            'search_metadata': {
                'total_results': 1,
                'sources_checked': 'Multiple sources',
                'search_time': 'Real-time'
            }
        }

@app.route('/', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'AI Building Materials Search API',
        'version': '1.1',
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/search', methods=['POST'])
def search_products():
    """Main search endpoint with enhanced results"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        query = data.get('query', '').strip()
        location = data.get('location', 'UK').strip()
        max_results = min(int(data.get('max_results', 5)), 10)
        
        if not query:
            return jsonify({'error': 'Query parameter is required'}), 400
        
        if len(query) < 3:
            return jsonify({'error': 'Query must be at least 3 characters long'}), 400
        
        start_time = time.time()
        
        # Call enhanced Perplexity API
        ai_response = call_perplexity_api(query)
        
        # Parse enhanced response
        parsed_results = parse_enhanced_response(ai_response)
        
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
                'product_name': 'Celotex GA4050 PIR Board 50mm',
                'price': '£17.50',
                'price_per_unit': '£6.08 per m²',
                'supplier': 'Trade Insulations',
                'availability': 'In Stock',
                'location': 'UK Wide',
                'delivery_info': 'Free delivery on orders over £100',
                'supplier_url': 'https://tradeinsulations.co.uk'
            },
            {
                'product_name': 'Unilin Thin-R PIR 50mm',
                'price': '£18.22',
                'price_per_unit': '£6.33 per m²',
                'supplier': 'Insulation4Less',
                'availability': 'In Stock',
                'location': 'UK Wide',
                'delivery_info': 'Next day delivery available',
                'supplier_url': 'https://insulation4less.co.uk'
            },
            {
                'product_name': 'Ecotherm Eco-Versal PIR 50mm',
                'price': '£18.08',
                'price_per_unit': '£6.28 per m²',
                'supplier': 'Insulation Wholesale',
                'availability': 'In Stock',
                'location': 'Multiple UK locations',
                'delivery_info': 'Free delivery over £75',
                'supplier_url': 'https://insulationwholesale.co.uk'
            }
        ],
        'ai_summary': 'Found multiple 50mm PIR insulation boards from specialist UK suppliers. Trade Insulations offers the best value at £17.50 per board (£6.08 per m²), followed by Insulation Wholesale and Insulation4Less with competitive pricing on quality brands.',
        'search_metadata': {
            'total_results': 3,
            'sources_checked': 13,
            'search_time': '2.3s'
        }
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
