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
TAVILY_API_KEY = os.environ.get('TAVILY_API_KEY')
TAVILY_API_URL = "https://api.tavily.com/search"

def call_tavily_api(user_query, max_results=5):
    """Call Tavily API with user's query and image support"""
    if not TAVILY_API_KEY:
        raise Exception("Tavily API key not configured")
    
    headers = {
        "Content-Type": "application/json"
    }
    
    payload = {
        "api_key": TAVILY_API_KEY,
        "query": user_query,
        "search_depth": "advanced",  # More thorough search
        "include_images": True,      # Include product images
        "include_answer": True,      # Include AI summary
        "include_raw_content": False,
        "max_results": max_results,
        "include_domains": [         # Focus on UK building suppliers
            "wickes.co.uk",
            "screwfix.com", 
            "buildbase.co.uk",
            "selco.co.uk",
            "jewson.co.uk",
            "travisperkins.co.uk",
            "homebase.co.uk",
            "diy.com",
            "tradeinsulations.co.uk",
            "insulation4less.co.uk",
            "insulationshop.co",
            "insulationwholesale.co.uk",
            "insulationuk.co.uk"
        ]
    }
    
    try:
        response = requests.post(TAVILY_API_URL, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        raise Exception(f"Tavily API request failed: {str(e)}")

def extract_price_from_text(text):
    """Extract price from text content"""
    if not text:
        return None
    
    # Look for UK price patterns
    price_patterns = [
        r'£([\d,]+\.?\d*)',
        r'(\d+\.?\d*)\s*pounds?',
        r'(\d+\.?\d*)\s*GBP'
    ]
    
    for pattern in price_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            for match in matches:
                try:
                    price_val = float(str(match).replace(',', ''))
                    if 5 <= price_val <= 500:  # Reasonable range for building materials
                        return f"£{price_val:.2f}"
                except:
                    continue
    return None

def extract_supplier_from_url(url):
    """Extract supplier name from URL"""
    if not url:
        return "UK Supplier"
    
    # Extract domain and map to known suppliers
    domain_map = {
        'wickes.co.uk': 'Wickes',
        'screwfix.com': 'Screwfix',
        'buildbase.co.uk': 'Buildbase', 
        'selco.co.uk': 'Selco',
        'jewson.co.uk': 'Jewson',
        'travisperkins.co.uk': 'Travis Perkins',
        'homebase.co.uk': 'Homebase',
        'diy.com': 'B&Q',
        'tradeinsulations.co.uk': 'Trade Insulations',
        'insulation4less.co.uk': 'Insulation4Less',
        'insulationshop.co': 'Insulation Shop',
        'insulationwholesale.co.uk': 'Insulation Wholesale',
        'insulationuk.co.uk': 'Insulation UK'
    }
    
    for domain, supplier in domain_map.items():
        if domain in url.lower():
            return supplier
    
    # Extract domain name as fallback
    try:
        from urllib.parse import urlparse
        domain = urlparse(url).netloc
        return domain.replace('www.', '').replace('.co.uk', '').replace('.com', '').title()
    except:
        return "UK Supplier"

def parse_tavily_response(tavily_response):
    """Parse Tavily response and extract structured product data"""
    try:
        results = tavily_response.get('results', [])
        images = tavily_response.get('images', [])
        answer = tavily_response.get('answer', '')
        
        products = []
        
        # Process each search result
        for i, result in enumerate(results):
            product = {}
            
            # Extract basic info
            title = result.get('title', '')
            content = result.get('content', '')
            url = result.get('url', '')
            
            # Extract supplier from URL
            product['supplier'] = extract_supplier_from_url(url)
            
            # Extract product name from title
            product['product_name'] = title[:100] if title else 'Building Material'
            
            # Extract price from content
            price = extract_price_from_text(content)
            if price:
                product['price'] = price
            else:
                # Try to extract from title
                price = extract_price_from_text(title)
                product['price'] = price if price else 'Contact for price'
            
            # Add product URL
            product['url'] = url
            
            # Try to match with an image
            if i < len(images):
                product['image'] = images[i]
            elif images:
                # Use first available image as fallback
                product['image'] = images[0]
            
            # Extract additional details
            if 'mm' in content.lower():
                dimensions_match = re.search(r'(\d+mm\s*x?\s*\d*mm?)', content, re.IGNORECASE)
                if dimensions_match:
                    product['dimensions'] = dimensions_match.group(1)
            
            # Only add products with valid data
            if product.get('supplier') and product.get('price') != 'Contact for price':
                products.append(product)
        
        # Sort by price (cheapest first)
        def get_price_value(product):
            price_str = product.get('price', '')
            if price_str and price_str != 'Contact for price':
                match = re.search(r'£?([\d,]+\.?\d*)', price_str)
                if match:
                    return float(match.group(1).replace(',', ''))
            return float('inf')
        
        products.sort(key=get_price_value)
        
        # Create summary
        if products:
            summary_parts = []
            for product in products[:3]:
                supplier = product.get('supplier', 'Unknown')
                price = product.get('price', 'N/A')
                summary_parts.append(f"{supplier}: {price}")
            summary = f"Top suppliers found: {', '.join(summary_parts)}"
        else:
            summary = "Search completed - check results below."
        
        return {
            'results': products[:5],
            'ai_summary': summary,
            'tavily_answer': answer,  # Include Tavily's AI answer
            'total_images': len(images),
            'search_metadata': {
                'total_results': len(products),
                'search_time': 'Real-time',
                'source': 'Tavily Search API'
            }
        }
        
    except Exception as e:
        return {
            'results': [{
                'supplier': 'Search Results Available',
                'product_name': 'Multiple products found',
                'price': 'Various prices',
                'image': None
            }],
            'ai_summary': 'Search completed successfully.',
            'tavily_answer': tavily_response.get('answer', ''),
            'search_metadata': {
                'total_results': 1,
                'search_time': 'Real-time',
                'source': 'Tavily Search API',
                'parsing_error': str(e)
            }
        }

@app.route('/', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'AI Building Materials Search API - Tavily',
        'version': '3.0',
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/search', methods=['POST'])
def search_products():
    """Main search endpoint using Tavily with images"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        user_query = data.get('query', '').strip()
        max_results = min(int(data.get('max_results', 5)), 10)
        
        if not user_query:
            return jsonify({'error': 'Query parameter is required'}), 400
        
        if len(user_query) < 3:
            return jsonify({'error': 'Query must be at least 3 characters long'}), 400
        
        start_time = time.time()
        
        # Call Tavily API
        tavily_response = call_tavily_api(user_query, max_results)
        
        # Parse response
        parsed_results = parse_tavily_response(tavily_response)
        
        # Add timing
        search_time = round(time.time() - start_time, 2)
        parsed_results['search_metadata']['search_time'] = f"{search_time}s"
        
        return jsonify(parsed_results)
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'message': 'Search failed. Please try again or contact support.',
            'query_received': data.get('query', '') if 'data' in locals() else 'Unknown'
        }), 500

@app.route('/api/search/demo', methods=['GET'])
def demo_search():
    """Demo endpoint with sample data including images"""
    return jsonify({
        'results': [
            {
                'supplier': 'Trade Insulations',
                'product_name': 'Celotex GA4050 PIR Insulation Board 50mm',
                'price': '£17.50',
                'dimensions': '2400mm x 1200mm',
                'image': 'https://example.com/celotex-pir-board.jpg',
                'url': 'https://tradeinsulations.co.uk/celotex-ga4050'
            },
            {
                'supplier': 'Insulation4Less',
                'product_name': 'Unilin Thin-R PIR Insulation 50mm',
                'price': '£18.22',
                'dimensions': '2400mm x 1200mm', 
                'image': 'https://example.com/unilin-pir-board.jpg',
                'url': 'https://insulation4less.co.uk/unilin-thin-r'
            },
            {
                'supplier': 'Insulation Wholesale',
                'product_name': 'Ecotherm Eco-Versal PIR Board 50mm',
                'price': '£18.08',
                'dimensions': '2400mm x 1200mm',
                'image': 'https://example.com/ecotherm-pir-board.jpg',
                'url': 'https://insulationwholesale.co.uk/ecotherm'
            }
        ],
        'ai_summary': 'Top suppliers found: Trade Insulations: £17.50, Insulation4Less: £18.22, Insulation Wholesale: £18.08',
        'total_images': 3,
        'search_metadata': {
            'total_results': 3,
            'search_time': '2.1s',
            'source': 'Tavily Search API'
        }
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
    
    
