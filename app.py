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
- Include supplier names and contact details
- Include product specifications and availability
- Focus on UK building material suppliers and insulation specialists
- Compare prices from multiple suppliers
- Show results ranked from cheapest to most expensive

SEARCH FOCUS: UK insulation suppliers like Insulation4Less, Trade Insulations, Insulation Shop, Insulation Wholesale, etc.

Please provide detailed pricing comparison with VAT-inclusive prices and supplier contact information."""
    
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
                "content": "You are a UK building materials price comparison expert. Always search for current prices INCLUDING VAT from real UK suppliers. Only include suppliers with actual prices, not 'contact for price'. Provide specific VAT-inclusive pricing, supplier names, contact details, and product specifications. Focus on insulation specialists and building merchants."
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
        return float('inf')  # Put "contact for price" at the end
    
    # Extract number from price string
    match = re.search(r'£?([\d,]+\.?\d*)', price_str)
    if match:
        return float(match.group(1).replace(',', ''))
    return float('inf')

def parse_enhanced_response(ai_response):
    """Parse AI response with optimized price extraction and sorting"""
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
            
            # Extract supplier name with improved patterns
            supplier_patterns = [
                r'\*\*([^*]+)\*\*',  # **Supplier Name**
                r'(\d+\.\s*)?\*\*([^*]+)\*\*',  # 1. **Supplier Name**
                r'(\d+\.\s*)?([A-Z][a-zA-Z\s&0-9]+?)(?:\s*-|\s*:|\n)',  # 1. Supplier Name -
                r'(Insulation4Less|Trade Insulations|Insulation Shop|Insulation UK|Insulation Wholesale|Building Materials Online|Selco|Buildbase|Wickes|Screwfix|Jewson|Travis Perkins)',
                r'([A-Z][a-zA-Z\s&]+?)(?:\s*-\s*\*\*Product)',  # Supplier - **Product
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
            
            # Extract prices with VAT handling
            price_patterns = [
                r'£([\d,]+\.?\d*)\s*(?:per\s*board)?(?:\s*(?:inc|including)\s*VAT)?',
                r'Price:\s*£([\d,]+\.?\d*)',
                r'£([\d,]+\.?\d*)\s*(?:\([^)]*\))?(?:\s*inc\s*VAT)?',
            ]
            
            price_found = False
            for pattern in price_patterns:
                matches = re.findall(pattern, section, re.IGNORECASE)
                if matches:
                    # Get the first reasonable price (between £10-£100 for PIR boards)
                    for price_str in matches:
                        price_val = float(price_str.replace(',', ''))
                        if 10 <= price_val <= 100:  # Reasonable range for PIR boards
                            product['price'] = f"£{price_val:.2f}"
                            price_found = True
                            break
                    if price_found:
                        break
            
            # Extract per m² price if available
            per_m2_match = re.search(r'£([\d,]+\.?\d*)\s*per\s*m²', section, re.IGNORECASE)
            if per_m2_match:
                product['price_per_unit'] = f"£{per_m2_match.group(1)} per m²"
            
            # Extract contact information
            phone_patterns = [
                r'Phone:\s*([\d\s\-\(\)]+)',
                r'Tel:\s*([\d\s\-\(\)]+)',
                r'Contact:\s*([\d\s\-\(\)]+)',
                r'(\d{4}\s*\d{3}\s*\d{4})',  # UK phone format
                r'(\d{3}\s*\d{3}\s*\d{4})',  # Alternative format
            ]
            
            for pattern in phone_patterns:
                match = re.search(pattern, section)
                if match:
                    product['supplier_phone'] = match.group(1).strip()
                    break
            
            # Extract availability
            if 'in stock' in section.lower():
                product['availability'] = 'In Stock'
            elif 'available' in section.lower():
                product['availability'] = 'Available'
            
            # Extract delivery info
            if 'free delivery' in section.lower():
                delivery_match = re.search(r'free delivery[^.]*', section, re.IGNORECASE)
                if delivery_match:
                    product['delivery_info'] = delivery_match.group(0).capitalize()
            elif 'delivery' in section.lower():
                product['delivery_info'] = 'Delivery available'
            
            # Only add products with valid supplier and price
            if product.get('supplier') and product.get('price') and 'contact' not in product['price'].lower():
                # Set defaults
                product.setdefault('product_name', '50mm PIR Insulation Board')
                product.setdefault('availability', 'Contact supplier')
                product.setdefault('location', 'UK')
                product.setdefault('delivery_info', 'Contact for delivery options')
                
                # Generate supplier URL
                supplier_clean = product['supplier'].lower().replace(' ', '').replace('&', '').replace('materials', '').replace('online', '')
                if 'insulation4less' in supplier_clean:
                    product['supplier_url'] = 'https://insulation4less.co.uk'
                elif 'tradeinsulations' in supplier_clean:
                    product['supplier_url'] = 'https://tradeinsulations.co.uk'
                elif 'insulationshop' in supplier_clean:
                    product['supplier_url'] = 'https://insulationshop.co'
                elif 'insulationuk' in supplier_clean:
                    product['supplier_url'] = 'https://insulationuk.co.uk'
                elif 'insulationwholesale' in supplier_clean:
                    product['supplier_url'] = 'https://insulationwholesale.co.uk'
                else:
                    product['supplier_url'] = f"https://{supplier_clean}.co.uk"
                
                products.append(product)
        
        # Sort products by price (cheapest first)
        products.sort(key=lambda x: extract_price_value(x.get('price', '')))
        
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
            'results': products[:5],  # Top 5 cheapest
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
        'version': '1.3',
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/search', methods=['POST'])
def search_products():
    """Main search endpoint with optimized results"""
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
        
        # Parse enhanced response with optimized sorting
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
                'product_name': '50mm Celotex GA4050 PIR Insulation Board',
                'price': '£20.10',
                'price_per_unit': '£6.98 per m²',
                'supplier': 'Insulation UK',
                'availability': 'In Stock',
                'location': 'UK Wide',
                'delivery_info': 'Free delivery on orders over £200',
                'supplier_phone': '020 3582 6399',
                'supplier_url': 'https://insulationuk.co.uk'
            },
            {
                'product_name': '50mm Celotex GA4050 PIR Insulation Board',
                'price': '£20.40',
                'price_per_unit': '£7.08 per m²',
                'supplier': 'Insulation4Less',
                'availability': 'In Stock',
                'location': 'UK Wide',
                'delivery_info': 'Free delivery on orders over £300',
                'supplier_phone': '0203 639 4959',
                'supplier_url': 'https://insulation4less.co.uk'
            },
            {
                'product_name': '50mm Celotex GA4050 PIR Insulation Board',
                'price': '£21.00',
                'price_per_unit': '£7.29 per m²',
                'supplier': 'Insulation Shop',
                'availability': 'In Stock',
                'location': 'UK Wide',
                'delivery_info': 'Next day delivery available',
                'supplier_url': 'https://insulationshop.co'
            }
        ],
        'ai_summary': 'Found multiple 50mm PIR insulation boards from specialist UK suppliers with VAT-inclusive pricing. Insulation UK offers the best value at £20.10 per board, followed by Insulation4Less at £20.40 and Insulation Shop at £21.00.',
        'search_metadata': {
            'total_results': 3,
            'sources_checked': 'Multiple UK suppliers',
            'search_time': '2.1s'
        }
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
