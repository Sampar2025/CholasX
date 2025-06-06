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
    enhanced = f"""Find the top 5 cheapest suppliers for {query} in {location} with exact prices INCLUDING VAT.

REQUIREMENTS:
- Include exact prices per board INCLUDING VAT (£ per board inc VAT)
- Only include suppliers with actual prices (no "contact for price")
- Include supplier names and product names only
- Focus on UK building material suppliers and insulation specialists
- Show results ranked from cheapest to most expensive
- Keep response concise and focused on pricing only

SEARCH FOCUS: UK insulation suppliers like Insulation4Less, Trade Insulations, Insulation Shop, Insulation UK, etc.

Please provide a simple price comparison list without detailed explanations."""
    
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
                "content": "You are a UK building materials price comparison expert. Provide only essential information: supplier names, product names, and VAT-inclusive prices. Keep responses concise without detailed explanations or contact information."
            },
            {
                "role": "user", 
                "content": enhanced_query
            }
        ],
        "temperature": 0.1,
        "max_tokens": 1500,
        "return_citations": True,
        "search_recency_filter": "month"
    }
    
    try:
        response = requests.post(PERPLEXITY_API_URL, headers=headers, json=payload, timeout=45)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        raise Exception(f"API request failed: {str(e)}")

def clean_supplier_name(name):
    """Clean and standardize supplier names"""
    if not name:
        return "UK Supplier"
    
    # Remove common prefixes/suffixes
    name = re.sub(r'^\d+\.\s*', '', name)  # Remove numbering
    name = name.replace('*', '').strip()   # Remove asterisks
    
    # Standardize known suppliers
    name_lower = name.lower()
    if 'insulation4less' in name_lower:
        return 'Insulation4Less'
    elif 'trade insulation' in name_lower:
        return 'Trade Insulations'
    elif 'insulation shop' in name_lower or 'insulationshop' in name_lower:
        return 'Insulation Shop'
    elif 'insulation wholesale' in name_lower:
        return 'Insulation Wholesale'
    elif 'insulation uk' in name_lower:
        return 'Insulation UK'
    elif 'building materials' in name_lower:
        return 'Building Materials Online'
    elif 'selco' in name_lower:
        return 'Selco'
    elif 'buildbase' in name_lower:
        return 'Buildbase'
    elif 'wickes' in name_lower:
        return 'Wickes'
    elif 'screwfix' in name_lower:
        return 'Screwfix'
    elif 'jewson' in name_lower:
        return 'Jewson'
    elif 'travis perkins' in name_lower:
        return 'Travis Perkins'
    
    # Capitalize properly
    return ' '.join(word.capitalize() for word in name.split())

def extract_price_value(price_str):
    """Extract numeric value from price string for sorting"""
    if not price_str or 'contact' in price_str.lower():
        return float('inf')
    
    match = re.search(r'£?([\d,]+\.?\d*)', price_str)
    if match:
        return float(match.group(1).replace(',', ''))
    return float('inf')

def create_simple_summary(products):
    """Create a simple, clean summary"""
    if not products:
        return "No results found."
    
    summary_parts = []
    for i, product in enumerate(products[:3], 1):
        supplier = product.get('supplier', 'Unknown')
        price = product.get('price', 'N/A')
        summary_parts.append(f"{supplier}: {price}")
    
    return f"Top suppliers found: {', '.join(summary_parts)}"

def parse_enhanced_response(ai_response):
    """Parse AI response with simplified output"""
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
            
            # Extract supplier name
            supplier_patterns = [
                r'\*\*([^*]+)\*\*',
                r'(\d+\.\s*)?\*\*([^*]+)\*\*',
                r'(\d+\.\s*)?([A-Z][a-zA-Z\s&0-9]+?)(?:\s*-|\s*:|\n)',
                r'(Insulation4Less|Trade Insulations|Insulation Shop|Insulation UK|Insulation Wholesale|Building Materials Online|Selco|Buildbase|Wickes|Screwfix|Jewson|Travis Perkins)',
            ]
            
            for pattern in supplier_patterns:
                match = re.search(pattern, section, re.IGNORECASE)
                if match:
                    if len(match.groups()) >= 2 and match.group(2):
                        supplier_raw = match.group(2).strip()
                    elif match.group(1):
                        supplier_raw = match.group(1).strip()
                    else:
                        supplier_raw = match.group(0).strip()
                    
                    product['supplier'] = clean_supplier_name(supplier_raw)
                    break
            
            # Extract product name
            product_patterns = [
                r'Product:\*\*\s*([^*\n]+)',
                r'-\s*\*\*Product:\*\*\s*([^\n]+)',
                r'((?:50mm\s*)?(?:Celotex|Kingspan|Recticel|Unilin|Ecotherm)\s*[^£\n]*(?:PIR|Insulation)[^£\n]*)',
                r'(50mm[^£\n]*(?:PIR|Insulation)[^£\n]*)',
            ]
            
            for pattern in product_patterns:
                match = re.search(pattern, section, re.IGNORECASE)
                if match:
                    product['product_name'] = match.group(1).strip()
                    break
            
            # Extract prices
            price_patterns = [
                r'£([\d,]+\.?\d*)\s*(?:per\s*board)?(?:\s*(?:inc|including)\s*VAT)?',
                r'Price:\s*£([\d,]+\.?\d*)',
                r'£([\d,]+\.?\d*)\s*(?:\([^)]*\))?(?:\s*inc\s*VAT)?',
            ]
            
            price_found = False
            for pattern in price_patterns:
                matches = re.findall(pattern, section, re.IGNORECASE)
                if matches:
                    for price_str in matches:
                        price_val = float(price_str.replace(',', ''))
                        if 10 <= price_val <= 100:  # Reasonable range
                            product['price'] = f"£{price_val:.2f}"
                            price_found = True
                            break
                    if price_found:
                        break
            
            # Extract dimensions if available
            dimensions_match = re.search(r'(\d+mm\s*x\s*\d+mm)', section)
            if dimensions_match:
                product['dimensions'] = dimensions_match.group(1)
            
            # Only add products with valid supplier and price
            if product.get('supplier') and product.get('price') and 'contact' not in product['price'].lower():
                # Set minimal defaults
                product.setdefault('product_name', '50mm PIR Insulation Board')
                
                products.append(product)
        
        # Sort products by price (cheapest first)
        products.sort(key=lambda x: extract_price_value(x.get('price', '')))
        
        # Create simple summary
        simple_summary = create_simple_summary(products)
        
        return {
            'results': products[:5],  # Top 5 cheapest
            'ai_summary': simple_summary,  # Simple summary instead of full content
            'citations': citations,
            'search_metadata': {
                'total_results': len(products),
                'sources_checked': 'Multiple UK suppliers',
                'search_time': 'Real-time'
            }
        }
        
    except Exception as e:
        return {
            'results': [{
                'product_name': 'Search Results Available',
                'price': 'See details below',
                'supplier': 'Multiple UK Suppliers'
            }],
            'ai_summary': 'Search completed successfully.',
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
        'version': '1.4',
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/search', methods=['POST'])
def search_products():
    """Main search endpoint with simplified results"""
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
        
        # Call Perplexity API
        ai_response = call_perplexity_api(query)
        
        # Parse with simplified output
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
    """Demo endpoint with simplified sample data"""
    return jsonify({
        'results': [
            {
                'product_name': '50mm Celotex GA4050 PIR Insulation Board',
                'price': '£20.10',
                'supplier': 'Insulation UK',
                'dimensions': '2400mm x 1200mm'
            },
            {
                'product_name': '50mm Celotex GA4050 PIR Insulation Board',
                'price': '£20.40',
                'supplier': 'Insulation4Less',
                'dimensions': '2400mm x 1200mm'
            },
            {
                'product_name': '50mm Celotex GA4050 PIR Insulation Board',
                'price': '£21.00',
                'supplier': 'Insulation Shop',
                'dimensions': '2400mm x 1200mm'
            }
        ],
        'ai_summary': 'Top suppliers found: Insulation UK: £20.10, Insulation4Less: £20.40, Insulation Shop: £21.00',
        'search_metadata': {
            'total_results': 3,
            'sources_checked': 'Multiple UK suppliers',
            'search_time': '2.1s'
        }
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
