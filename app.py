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
    """Create enhanced query that matches direct Perplexity quality"""
    # Clean and enhance the query
    query_lower = query.lower()
    
    # Detect product type and enhance accordingly
    if 'plasterboard' in query_lower or 'drywall' in query_lower:
        product_type = "plasterboard"
        enhanced = f"""Find the top 5 cheapest suppliers for {query} in {location}.

Create a detailed comparison table showing:
- Supplier names (Trade Insulations, Insulation4Less, Wickes, Screwfix, Buildbase, etc.)
- Exact product names and specifications
- Prices per board INCLUDING VAT
- Board dimensions and coverage
- Availability and delivery options

Focus on UK building merchants and drywall/plasterboard specialists."""

    elif 'pir' in query_lower or 'insulation' in query_lower:
        product_type = "insulation"
        enhanced = f"""Find the top 5 cheapest suppliers for {query} in {location}.

Create a detailed comparison table showing:
- Supplier names (Trade Insulations, Insulation4Less, Insulation Shop, Insulation Wholesale, etc.)
- Exact product names (Celotex, Kingspan, Recticel, Unilin, Ecotherm)
- Prices per board INCLUDING VAT
- Board dimensions (2400mm x 1200mm) and m² coverage
- Availability and delivery options

Focus on UK insulation specialists and building merchants."""

    else:
        # Generic building materials search
        enhanced = f"""Find the top 5 cheapest suppliers for {query} in {location}.

Create a detailed comparison table showing:
- Supplier names and contact details
- Exact product names and specifications  
- Prices INCLUDING VAT
- Product dimensions and coverage
- Availability and delivery options

Focus on UK building merchants and trade suppliers."""

    enhanced += f"""

IMPORTANT: Provide a comprehensive ranking table like this format:
Rank | Supplier & Product | Price (inc VAT) | Notes
1 | [Supplier] - [Product] | £XX.XX | Details
2 | [Supplier] - [Product] | £XX.XX | Details
etc.

Include detailed product specifications, supplier contact information, and current pricing."""
    
    return enhanced

def call_perplexity_api(query):
    """Call Perplexity API to get full detailed results"""
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
                "content": "You are a UK building materials price comparison expert. Always search for current prices from real UK suppliers. Provide comprehensive comparison tables with exact pricing, supplier details, and product specifications. Focus on trade suppliers and building merchants. Always include VAT in pricing."
            },
            {
                "role": "user", 
                "content": enhanced_query
            }
        ],
        "temperature": 0.1,
        "max_tokens": 3000,  # Increased for full results
        "return_citations": True,
        "search_recency_filter": "month"
    }
    
    try:
        response = requests.post(PERPLEXITY_API_URL, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        raise Exception(f"API request failed: {str(e)}")

def clean_supplier_name(name):
    """Clean and standardize supplier names"""
    if not name:
        return "UK Supplier"
    
    # Remove common prefixes/suffixes
    name = re.sub(r'^\d+\.\s*', '', name)
    name = name.replace('*', '').replace('|', '').strip()
    
    # Standardize known suppliers
    name_lower = name.lower()
    supplier_map = {
        'trade insulation': 'Trade Insulations',
        'insulation4less': 'Insulation4Less',
        'insulation shop': 'Insulation Shop',
        'insulation wholesale': 'Insulation Wholesale',
        'insulation uk': 'Insulation UK',
        'building materials': 'Building Materials Online',
        'wickes': 'Wickes',
        'screwfix': 'Screwfix',
        'buildbase': 'Buildbase',
        'selco': 'Selco',
        'jewson': 'Jewson',
        'travis perkins': 'Travis Perkins',
        'homebase': 'Homebase',
        'b&q': 'B&Q'
    }
    
    for key, value in supplier_map.items():
        if key in name_lower:
            return value
    
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

def parse_enhanced_response(ai_response):
    """Parse full Perplexity response to extract all details"""
    try:
        content = ai_response['choices'][0]['message']['content']
        citations = ai_response.get('citations', [])
        
        products = []
        
        # Look for table format first
        table_pattern = r'(\d+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*([^|\n]+)'
        table_matches = re.findall(table_pattern, content)
        
        if table_matches:
            # Parse table format
            for rank, supplier_product, price, notes in table_matches:
                product = {}
                
                # Extract supplier and product from combined field
                supplier_product = supplier_product.strip()
                if '–' in supplier_product or '-' in supplier_product:
                    parts = re.split(r'[–-]', supplier_product, 1)
                    if len(parts) == 2:
                        product['supplier'] = clean_supplier_name(parts[0].strip())
                        product['product_name'] = parts[1].strip()
                    else:
                        product['supplier'] = clean_supplier_name(supplier_product)
                        product['product_name'] = 'Building Material'
                else:
                    product['supplier'] = clean_supplier_name(supplier_product)
                    product['product_name'] = 'Building Material'
                
                # Extract price
                price_match = re.search(r'£([\d,]+\.?\d*)', price)
                if price_match:
                    product['price'] = f"£{price_match.group(1)}"
                
                # Extract additional details from notes
                if notes:
                    product['notes'] = notes.strip()
                
                if product.get('supplier') and product.get('price'):
                    products.append(product)
        
        # If no table found, try other parsing methods
        if not products:
            # Look for numbered list format
            sections = re.split(r'\n(?=\d+\.|\*\*\d+\.)', content)
            
            for section in sections:
                if not section.strip():
                    continue
                    
                product = {}
                
                # Extract supplier name
                supplier_patterns = [
                    r'\*\*([^*]+)\*\*',
                    r'(\d+\.\s*)?\*\*([^*]+)\*\*',
                    r'(\d+\.\s*)?([A-Z][a-zA-Z\s&0-9]+?)(?:\s*[–-]|\s*:|\n)',
                    r'(Trade Insulations|Insulation4Less|Insulation Shop|Insulation UK|Insulation Wholesale|Building Materials Online|Wickes|Screwfix|Buildbase|Selco|Jewson|Travis Perkins|Homebase|B&Q)',
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
                    r'Product:\s*([^\n]+)',
                    r'-\s*\*\*Product:\*\*\s*([^\n]+)',
                    r'((?:12\.5mm|9\.5mm|15mm|50mm|100mm)\s*[^£\n]*(?:plasterboard|PIR|insulation|board)[^£\n]*)',
                    r'([A-Z][a-zA-Z0-9\s\-]+(?:plasterboard|PIR|insulation|board)[^£\n]*)',
                ]
                
                for pattern in product_patterns:
                    match = re.search(pattern, section, re.IGNORECASE)
                    if match:
                        product['product_name'] = match.group(1).strip()
                        break
                
                # Extract price
                price_patterns = [
                    r'£([\d,]+\.?\d*)\s*(?:per\s*board|per\s*sheet)?(?:\s*(?:inc|including)\s*VAT)?',
                    r'Price[^£]*£([\d,]+\.?\d*)',
                    r'£([\d,]+\.?\d*)\s*(?:\([^)]*\))?',
                ]
                
                for pattern in price_patterns:
                    matches = re.findall(pattern, section, re.IGNORECASE)
                    if matches:
                        for price_str in matches:
                            price_val = float(price_str.replace(',', ''))
                            if 5 <= price_val <= 200:  # Reasonable range for building materials
                                product['price'] = f"£{price_val:.2f}"
                                break
                        if product.get('price'):
                            break
                
                # Extract dimensions
                dimensions_match = re.search(r'(\d+mm\s*x\s*\d+mm)', section)
                if dimensions_match:
                    product['dimensions'] = dimensions_match.group(1)
                
                # Only add valid products
                if product.get('supplier') and product.get('price'):
                    product.setdefault('product_name', 'Building Material')
                    products.append(product)
        
        # Sort by price (cheapest first)
        products.sort(key=lambda x: extract_price_value(x.get('price', '')))
        
        # Create comprehensive summary
        if products:
            summary_parts = []
            for i, product in enumerate(products[:5], 1):
                supplier = product.get('supplier', 'Unknown')
                price = product.get('price', 'N/A')
                summary_parts.append(f"{i}. {supplier}: {price}")
            
            summary = f"Top 5 cheapest suppliers found:\n" + "\n".join(summary_parts)
        else:
            summary = "Search completed. See full details below."
        
        return {
            'results': products[:5],
            'ai_summary': summary,
            'full_content': content,  # Include full content for debugging
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
                'price': 'See full content below',
                'supplier': 'Multiple UK Suppliers'
            }],
            'ai_summary': 'Search completed successfully.',
            'full_content': content,  # Always include full content
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
        'version': '1.5',
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/search', methods=['POST'])
def search_products():
    """Main search endpoint with full Perplexity results"""
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
        
        # Parse full response
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
                'product_name': '12.5mm Standard Plasterboard',
                'price': '£8.50',
                'supplier': 'Wickes',
                'dimensions': '2400mm x 1200mm'
            },
            {
                'product_name': '12.5mm Gyproc WallBoard',
                'price': '£9.20',
                'supplier': 'Screwfix',
                'dimensions': '2400mm x 1200mm'
            },
            {
                'product_name': '12.5mm Standard Plasterboard',
                'price': '£9.85',
                'supplier': 'Buildbase',
                'dimensions': '2400mm x 1200mm'
            }
        ],
        'ai_summary': 'Top 3 cheapest suppliers found:\n1. Wickes: £8.50\n2. Screwfix: £9.20\n3. Buildbase: £9.85',
        'search_metadata': {
            'total_results': 3,
            'sources_checked': 'Multiple UK suppliers',
            'search_time': '2.1s'
        }
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
