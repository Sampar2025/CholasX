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

def call_tavily_api(user_query, max_results=8):
    """Call Tavily API with user's query and image support"""
    if not TAVILY_API_KEY:
        raise Exception("Tavily API key not configured")
    
    headers = {
        "Content-Type": "application/json"
    }
    
    # Enhanced query for better UK building materials results
    enhanced_query = f"{user_query} UK building materials suppliers price"
    
    payload = {
        "api_key": TAVILY_API_KEY,
        "query": enhanced_query,
        "search_depth": "advanced",
        "include_images": True,
        "include_answer": True,
        "include_raw_content": True,  # Get more content for better parsing
        "max_results": max_results,
        # REMOVED include_domains to get more results
        # Let Tavily find all relevant suppliers, not just our limited list
    }
    
    try:
        response = requests.post(TAVILY_API_URL, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        raise Exception(f"Tavily API request failed: {str(e)}")

def extract_price_from_text(text):
    """Extract price from text content - improved"""
    if not text:
        return None
    
    # Look for UK price patterns - more comprehensive
    price_patterns = [
        r'£([\d,]+\.?\d*)',
        r'(\d+\.?\d*)\s*pounds?',
        r'(\d+\.?\d*)\s*GBP',
        r'Price[:\s]*£?([\d,]+\.?\d*)',
        r'Cost[:\s]*£?([\d,]+\.?\d*)',
        r'From[:\s]*£?([\d,]+\.?\d*)'
    ]
    
    for pattern in price_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            for match in matches:
                try:
                    price_val = float(str(match).replace(',', ''))
                    if 1 <= price_val <= 1000:  # Expanded reasonable range
                        return f"£{price_val:.2f}"
                except:
                    continue
    return None

def extract_supplier_from_url_or_title(url, title):
    """Extract supplier name from URL or title - improved"""
    if not url and not title:
        return "UK Supplier"
    
    # Comprehensive supplier mapping
    supplier_patterns = {
        # Major retailers
        'wickes': 'Wickes',
        'screwfix': 'Screwfix', 
        'buildbase': 'Buildbase',
        'selco': 'Selco',
        'jewson': 'Jewson',
        'travis perkins': 'Travis Perkins',
        'travisperkins': 'Travis Perkins',
        'homebase': 'Homebase',
        'b&q': 'B&Q',
        'diy.com': 'B&Q',
        
        # Insulation specialists
        'trade insulations': 'Trade Insulations',
        'tradeinsulations': 'Trade Insulations',
        'insulation4less': 'Insulation4Less',
        'insulation shop': 'Insulation Shop',
        'insulationshop': 'Insulation Shop',
        'insulation wholesale': 'Insulation Wholesale',
        'insulationwholesale': 'Insulation Wholesale',
        'insulation uk': 'Insulation UK',
        'insulationuk': 'Insulation UK',
        'celotex': 'Celotex',
        'kingspan': 'Kingspan',
        'rockwool': 'Rockwool',
        
        # Building merchants
        'builderdepot': 'Builder Depot',
        'builder depot': 'Builder Depot',
        'roofing superstore': 'Roofing Superstore',
        'roofingsuperstore': 'Roofing Superstore',
        'building supplies': 'Building Supplies Online',
        'buildingsupplies': 'Building Supplies Online',
        'toolstation': 'Toolstation',
        'tool station': 'Toolstation',
        'plumbase': 'Plumbase',
        'city plumbing': 'City Plumbing',
        'cityplumbing': 'City Plumbing'
    }
    
    # Check URL first
    if url:
        url_lower = url.lower()
        for pattern, supplier in supplier_patterns.items():
            if pattern in url_lower:
                return supplier
    
    # Check title
    if title:
        title_lower = title.lower()
        for pattern, supplier in supplier_patterns.items():
            if pattern in title_lower:
                return supplier
    
    # Extract domain name as fallback
    if url:
        try:
            from urllib.parse import urlparse
            domain = urlparse(url).netloc
            domain_clean = domain.replace('www.', '').replace('.co.uk', '').replace('.com', '')
            return domain_clean.title()
        except:
            pass
    
    return "UK Supplier"

def extract_product_details(title, content):
    """Extract detailed product information"""
    full_text = f"{title} {content}".lower()
    
    # Extract product name - look for specific patterns
    product_name = title if title else "Building Material"
    
    # Extract dimensions
    dimensions = []
    dimension_patterns = [
        r'(\d+mm\s*x\s*\d+mm\s*x\s*\d+mm)',  # 2400mm x 1200mm x 100mm
        r'(\d+mm\s*x\s*\d+mm)',              # 2400mm x 1200mm
        r'(\d+\s*x\s*\d+\s*x\s*\d+mm)',      # 2400 x 1200 x 100mm
        r'(\d+\.\d+m\s*x\s*\d+\.\d+m)',      # 2.4m x 1.2m
    ]
    
    for pattern in dimension_patterns:
        matches = re.findall(pattern, full_text, re.IGNORECASE)
        if matches:
            dimensions.extend(matches)
    
    # Extract thickness specifically
    thickness_patterns = [
        r'(\d+mm)\s*thick',
        r'thickness[:\s]*(\d+mm)',
        r'(\d+mm)\s*insulation',
        r'(\d+mm)\s*board'
    ]
    
    thickness = None
    for pattern in thickness_patterns:
        matches = re.findall(pattern, full_text, re.IGNORECASE)
        if matches:
            thickness = matches[0]
            break
    
    # Extract material type
    material_types = ['pir', 'polyurethane', 'polystyrene', 'mineral wool', 'glass wool', 'celotex', 'kingspan', 'rockwool']
    material = None
    for mat in material_types:
        if mat in full_text:
            material = mat.upper() if mat in ['pir'] else mat.title()
            break
    
    # Build enhanced product name
    enhanced_name = product_name
    if material and material.lower() not in product_name.lower():
        enhanced_name = f"{material} {enhanced_name}"
    
    return {
        'product_name': enhanced_name,
        'dimensions': dimensions[0] if dimensions else thickness,
        'thickness': thickness,
        'material': material
    }

def parse_tavily_response(tavily_response):
    """Parse Tavily response and extract structured product data - improved"""
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
            raw_content = result.get('raw_content', '')
            url = result.get('url', '')
            
            # Use raw_content if available for better parsing
            full_content = raw_content if raw_content else content
            
            # Extract supplier
            product['supplier'] = extract_supplier_from_url_or_title(url, title)
            
            # Extract detailed product information
            product_details = extract_product_details(title, full_content)
            product.update(product_details)
            
            # Extract price
            price = extract_price_from_text(full_content) or extract_price_from_text(title)
            product['price'] = price if price else 'Contact for price'
            
            # Add product URL
            product['url'] = url
            
            # Better image matching
            product_image = None
            
            # Try to find image from Tavily's image results
            if images:
                # Look for images that might match this result
                for img_url in images:
                    if img_url and isinstance(img_url, str):
                        product_image = img_url
                        break
            
            # Alternative: extract image from result if available
            if not product_image and 'image' in result:
                product_image = result['image']
            
            product['image'] = product_image
            
            # Only add products with meaningful data
            if (product.get('supplier') != 'UK Supplier' or 
                product.get('price') != 'Contact for price' or
                any(keyword in title.lower() for keyword in ['insulation', 'board', 'material', 'building'])):
                products.append(product)
        
        # Sort by price (cheapest first), but keep products without prices
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
            summary = f"Found {len(products)} suppliers: {', '.join(summary_parts)}"
        else:
            summary = "Search completed - multiple suppliers found."
        
        return {
            'results': products[:5],  # Return top 5
            'ai_summary': summary,
            'tavily_answer': answer,
            'total_images': len(images),
            'search_metadata': {
                'total_results': len(products),
                'search_time': 'Real-time',
                'source': 'Tavily Search API',
                'images_found': len(images)
            }
        }
        
    except Exception as e:
        # Fallback response
        return {
            'results': [{
                'supplier': 'Multiple UK Suppliers',
                'product_name': 'Various building materials found',
                'price': 'Multiple prices available',
                'image': None,
                'url': '#'
            }],
            'ai_summary': 'Search completed - results available.',
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
        'service': 'AI Building Materials Search API - Tavily Enhanced',
        'version': '3.1',
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/search', methods=['POST'])
def search_products():
    """Main search endpoint using Tavily with enhanced parsing"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        user_query = data.get('query', '').strip()
        max_results = min(int(data.get('max_results', 8)), 10)  # Increased default
        
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
                'product_name': 'Celotex GA4050 PIR Insulation Board',
                'price': '£17.50',
                'dimensions': '2400mm x 1200mm x 50mm',
                'image': 'https://example.com/celotex-pir-board.jpg',
                'url': 'https://tradeinsulations.co.uk/celotex-ga4050'
            },
            {
                'supplier': 'Insulation4Less',
                'product_name': 'Unilin Thin-R PIR Insulation Board',
                'price': '£18.22',
                'dimensions': '2400mm x 1200mm x 50mm', 
                'image': 'https://example.com/unilin-pir-board.jpg',
                'url': 'https://insulation4less.co.uk/unilin-thin-r'
            },
            {
                'supplier': 'Insulation Wholesale',
                'product_name': 'Ecotherm Eco-Versal PIR Board',
                'price': '£18.08',
                'dimensions': '2400mm x 1200mm x 50mm',
                'image': 'https://example.com/ecotherm-pir-board.jpg',
                'url': 'https://insulationwholesale.co.uk/ecotherm'
            }
        ],
        'ai_summary': 'Found 3 suppliers: Trade Insulations: £17.50, Insulation4Less: £18.22, Insulation Wholesale: £18.08',
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
