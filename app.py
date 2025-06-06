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

def create_enhanced_query(query, location="UK"):
    """Create enhanced query for better Perplexity results"""
    enhanced = f"""Find the top 5 cheapest suppliers for {query} in {location}. 

REQUIREMENTS:
- Include exact prices per board (£ per board) as the main price
- Include price per m² as additional information
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
    
    payload = {
        "model": "llama-3.1-sonar-large-128k-online",
        "messages": [
            {
                "role": "system",
                "content": "You are a UK building materials price comparison expert. Always search for current prices from real UK suppliers. Provide specific pricing per board and per m², supplier names, contact details, and product specifications. Focus on trade suppliers and building merchants."
            },
            {
                "role": "user", 
                "content": enhanced_query
            }
        ],
        "temperature": 0.1,
        "max_tokens": 2000,
        "return_citations": True,
        "search_recency_filter": "month"
    }
    
    try:
        response = requests.post(PERPLEXITY_API_URL, headers=headers, json=payload, timeout=45)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        raise Exception(f"API request failed: {str(e)}")

def parse_enhanced_response(ai_response):
    """Parse AI response with improved price extraction"""
    try:
        content = ai_response['choices'][0]['message']['content']
        citations = ai_response.get('citations', [])
        
        products = []
        
        # Split content into sections for each supplier
        sections = re.split(r'\n(?=\d+\.\s|\*\*\d+\.|\#{1,3}\s*\d+)', content)
        
        for section in sections:
            if not section.strip():
                continue
                
            product = {}
            
            # Extract supplier name - look for common patterns
            supplier_patterns = [
                r'\*\*([^*]+)\*\*',  # **Supplier Name**
                r'(\d+\.\s*)?\*\*([^*]+)\*\*',  # 1. **Supplier Name**
                r'(\d+\.\s*)?([A-Z][a-zA-Z\s&]+?)(?:\s*-|\s*:|\n)',  # 1. Supplier Name -
                r'(Insulation4Less|Trade Insulations|Insulation Shop|Building Materials Online|Selco|Buildbase|Wickes|Screwfix|Jewson|Travis Perkins)'
            ]
            
            for pattern in supplier_patterns:
                match = re.search(pattern, section, re.IGNORECASE)
                if match:
                    # Get the supplier name from the appropriate group
                    if len(match.groups()) >= 2 and match.group(2):
                        product['supplier'] = match.group(2).strip()
                    elif match.group(1):
                        product['supplier'] = match.group(1).strip()
                    else:
                        product['supplier'] = match.group(0).strip()
                    
                    # Clean up supplier name
                    product['supplier'] = re.sub(r'^\d+\.\s*', '', product['supplier'])
                    product['supplier'] = product['supplier'].replace('*', '').strip()
                    break
            
            # Extract product name
            product_patterns = [
                r'Product:\*\*\s*([^*\n]+)',
                r'-\s*\*\*Product:\*\*\s*([^\n]+)',
                r'(Celotex|Kingspan|Recticel|Unilin|Ecotherm|PIR)[^£\n]*',
                r'50mm[^£\n]*(?:PIR|Insulation)[^£\n]*'
            ]
            
            for pattern in product_patterns:
                match = re.search(pattern, section, re.IGNORECASE)
                if match:
                    product['product_name'] = match.group(1) if len(match.groups()) >= 1 else match.group(0)
                    product['product_name'] = product['product_name'].strip()
                    break
            
            # Extract prices - prioritize per board price
            board_price_patterns = [
                r'£([\d,]+\.?\d*)\s*per\s*board',
                r'Price:\*\*\s*£([\d,]+\.?\d*)\s*per\s*board',
                r'£([\d,]+\.?\d*)\s*per\s*board\s*\([^)]+\)',
                r'£([\d,]+\.?\d*)\s*(?:per\s*board)?(?:\s*\([\d.]+m²\))?(?:\s*-\s*£[\d.]+\s*per\s*m²)?'
            ]
            
            per_m2_price_patterns = [
                r'£([\d,]+\.?\d*)\s*per\s*m²',
                r'-\s*£([\d,]+\.?\d*)\s*per\s*m²',
                r'£([\d,]+\.?\d*)\s*per\s*m²'
            ]
            
            # Try to find board price first
            board_price_found = False
            for pattern in board_price_patterns:
                match = re.search(pattern, section, re.IGNORECASE)
                if match:
                    product['price'] = f"£{match.group(1)}"
                    board_price_found = True
                    break
            
            # If no board price found, look for any price and try to determine context
            if not board_price_found:
                all_prices = re.findall(r'£([\d,]+\.?\d*)', section)
                if all_prices:
                    # If multiple prices, try to pick the higher one (likely per board)
                    prices_float = [float(p.replace(',', '')) for p in all_prices]
                    if len(prices_float) >= 2:
                        # Pick the higher price (likely per board)
                        max_price = max(prices_float)
                        product['price'] = f"£{max_price:.2f}"
                    else:
                        product['price'] = f"£{all_prices[0]}"
            
            # Extract per m² price separately
            for pattern in per_m2_price_patterns:
                match = re.search(pattern, section, re.IGNORECASE)
                if match:
                    product['price_per_unit'] = f"£{match.group(1)} per m²"
                    break
            
            # Extract contact information
            phone_match = re.search(r'Phone:\s*([\d\s]+)', section)
            if phone_match:
                product['supplier_phone'] = phone_match.group(1).strip()
            
            # Extract dimensions and coverage
            dimensions_match = re.search(r'(\d+mm\s*x\s*\d+mm)', section)
            if dimensions_match:
                product['dimensions'] = dimensions_match.group(1)
            
            coverage_match = re.search(r'([\d.]+m²)', section)
            if coverage_match:
                product['coverage'] = coverage_match.group(1)
            
            # Set defaults and clean up
            if product.get('supplier'):
                product.setdefault('product_name', '50mm PIR Insulation Board')
                product.setdefault('price', 'Contact for price')
                product.setdefault('availability', 'Contact supplier')
                product.setdefault('location', 'UK')
                product.setdefault('delivery_info', 'Contact for delivery options')
                
                # Generate supplier URL
                supplier_clean = product['supplier'].lower().replace(' ', '').replace('&', '').replace('materials', '').replace('online', '')
                product['supplier_url'] = f"https://{supplier_clean}.co.uk"
                
                products.append(product)
        
        # If no products extracted, create a fallback
        if not products:
            products = [{
                'product_name': 'Search Results Available',
                'price': 'See summary below',
                'supplier': 'Multiple UK Suppliers',
                'availability': 'Various',
                'location': 'UK',
                'delivery_info': 'Contact suppliers',
                'supplier_url': '#'
            }]
        
        return {
            'results': products[:5],
            'ai_summary': content,
            'citations': citations,
            'search_metadata': {
                'total_results': len(products),
                'sources_checked': 'Multiple UK suppliers',
                'search_time': 'Real-time'
            }
        }
        
    except Exception as e:
        # Fallback response
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
        'version': '1.2',
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/search', methods=['POST'])
def search_products():
    """Main search endpoint with fixed price parsing"""
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
        
        # Parse enhanced response with fixed price extraction
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
                'price': '£24.95',
                'price_per_unit': '£8.63 per m²',
                'supplier': 'Insulation4Less',
                'availability': 'In Stock',
                'location': 'UK Wide',
                'delivery_info': 'Free delivery on orders over £300',
                'supplier_phone': '0203 639 4959',
                'supplier_url': 'https://insulation4less.co.uk'
            },
            {
                'product_name': 'Celotex GA4050 PIR Board 50mm',
                'price': '£26.99',
                'price_per_unit': '£9.38 per m²',
                'supplier': 'Trade Insulations',
                'availability': 'In Stock',
                'location': 'UK Wide',
                'delivery_info': 'Express delivery available',
                'supplier_phone': '0141 375 7488',
                'supplier_url': 'https://tradeinsulations.co.uk'
            },
            {
                'product_name': 'Celotex GA4050 PIR Board 50mm',
                'price': '£28.50',
                'price_per_unit': '£9.90 per m²',
                'supplier': 'Insulation Shop',
                'availability': 'In Stock',
                'location': 'UK Wide',
                'delivery_info': 'Free delivery on orders over £200',
                'supplier_phone': '020 3582 6399',
                'supplier_url': 'https://insulationshop.co'
            }
        ],
        'ai_summary': 'Found multiple 50mm PIR insulation boards from specialist UK suppliers. Insulation4Less offers the best value at £24.95 per board (£8.63 per m²), followed by Trade Insulations at £26.99 per board and Insulation Shop at £28.50 per board.',
        'search_metadata': {
            'total_results': 3,
            'sources_checked': 'Multiple UK suppliers',
            'search_time': '2.1s'
        }
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
    
    
    
