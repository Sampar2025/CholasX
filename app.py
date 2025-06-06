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

def call_perplexity_api(user_query):
    """Call Perplexity API with user's exact query - no modifications"""
    if not PERPLEXITY_API_KEY:
        raise Exception("Perplexity API key not configured")
    
    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Use the user's exact query, just like they would type on Perplexity website
    payload = {
        "model": "llama-3.1-sonar-large-128k-online",
        "messages": [
            {
                "role": "user", 
                "content": user_query  # Exact user query, no modifications
            }
        ],
        "temperature": 0.1,
        "max_tokens": 4000,
        "return_citations": True,
        "search_recency_filter": "month"
    }
    
    try:
        response = requests.post(PERPLEXITY_API_URL, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        raise Exception(f"API request failed: {str(e)}")

def extract_price_value(price_str):
    """Extract numeric value from price string for sorting"""
    if not price_str:
        return float('inf')
    
    match = re.search(r'£?([\d,]+\.?\d*)', price_str)
    if match:
        return float(match.group(1).replace(',', ''))
    return float('inf')

def parse_perplexity_response(ai_response):
    """Parse Perplexity response and extract structured data"""
    try:
        content = ai_response['choices'][0]['message']['content']
        citations = ai_response.get('citations', [])
        
        products = []
        
        # Look for table format (like your example)
        # Rank | Supplier & Product | Price | Notes
        table_lines = []
        lines = content.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Look for table rows with | separators
            if '|' in line and any(char.isdigit() for char in line) and '£' in line:
                parts = [part.strip() for part in line.split('|')]
                if len(parts) >= 3:
                    table_lines.append(parts)
        
        # Parse table format
        for parts in table_lines:
            if len(parts) >= 3:
                rank_part = parts[0] if parts[0] else ""
                supplier_part = parts[1] if len(parts) > 1 else ""
                price_part = parts[2] if len(parts) > 2 else ""
                notes_part = parts[3] if len(parts) > 3 else ""
                
                # Extract supplier and product
                supplier_product = supplier_part.strip()
                supplier = ""
                product_name = ""
                
                if '–' in supplier_product or '-' in supplier_product:
                    split_parts = re.split(r'[–-]', supplier_product, 1)
                    if len(split_parts) == 2:
                        supplier = split_parts[0].strip()
                        product_name = split_parts[1].strip()
                else:
                    supplier = supplier_product
                    product_name = "Building Material"
                
                # Extract price
                price_match = re.search(r'£([\d,]+\.?\d*)', price_part)
                price = f"£{price_match.group(1)}" if price_match else ""
                
                if supplier and price:
                    products.append({
                        'supplier': supplier,
                        'product_name': product_name,
                        'price': price,
                        'notes': notes_part.strip() if notes_part else ""
                    })
        
        # If no table found, look for numbered list format
        if not products:
            current_product = {}
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Look for numbered items (1., 2., etc.)
                if re.match(r'^\d+\.?\s', line):
                    # Save previous product
                    if current_product.get('supplier') and current_product.get('price'):
                        products.append(current_product)
                    
                    # Start new product
                    current_product = {}
                    
                    # Extract supplier from numbered line
                    supplier_match = re.search(r'^\d+\.?\s*(.+?)(?:\s*[–-]|$)', line)
                    if supplier_match:
                        current_product['supplier'] = supplier_match.group(1).strip()
                
                # Look for product information
                elif 'product:' in line.lower() or 'board' in line.lower() or 'plasterboard' in line.lower():
                    product_match = re.search(r'(?:product:?\s*)?(.+)', line, re.IGNORECASE)
                    if product_match:
                        current_product['product_name'] = product_match.group(1).strip()
                
                # Look for price information
                elif '£' in line:
                    price_match = re.search(r'£([\d,]+\.?\d*)', line)
                    if price_match:
                        current_product['price'] = f"£{price_match.group(1)}"
            
            # Add final product
            if current_product.get('supplier') and current_product.get('price'):
                products.append(current_product)
        
        # Clean up and set defaults
        for product in products:
            if not product.get('product_name'):
                # Try to guess product type from query or content
                if 'plasterboard' in content.lower():
                    product['product_name'] = 'Plasterboard'
                elif 'pir' in content.lower() or 'insulation' in content.lower():
                    product['product_name'] = 'PIR Insulation Board'
                else:
                    product['product_name'] = 'Building Material'
        
        # Sort by price (cheapest first)
        products.sort(key=lambda x: extract_price_value(x.get('price', '')))
        
        # Create simple summary
        if products:
            summary_parts = []
            for i, product in enumerate(products[:3], 1):
                supplier = product.get('supplier', 'Unknown')
                price = product.get('price', 'N/A')
                summary_parts.append(f"{supplier}: {price}")
            summary = f"Top suppliers: {', '.join(summary_parts)}"
        else:
            summary = "Search completed."
        
        return {
            'results': products[:5],
            'ai_summary': summary,
            'full_response': content,  # Include full response for debugging
            'citations': citations,
            'search_metadata': {
                'total_results': len(products),
                'search_time': 'Real-time'
            }
        }
        
    except Exception as e:
        # Return full content if parsing fails
        return {
            'results': [{
                'supplier': 'Multiple Suppliers',
                'product_name': 'See full response below',
                'price': 'Various prices'
            }],
            'ai_summary': 'Search completed - see full response.',
            'full_response': content,
            'citations': ai_response.get('citations', []),
            'search_metadata': {
                'total_results': 1,
                'search_time': 'Real-time'
            }
        }

@app.route('/', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'AI Building Materials Search API',
        'version': '2.0',
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/search', methods=['POST'])
def search_products():
    """Main search endpoint - uses exact user query"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        # Get user's exact query
        user_query = data.get('query', '').strip()
        
        if not user_query:
            return jsonify({'error': 'Query parameter is required'}), 400
        
        if len(user_query) < 3:
            return jsonify({'error': 'Query must be at least 3 characters long'}), 400
        
        start_time = time.time()
        
        # Call Perplexity API with user's exact query
        ai_response = call_perplexity_api(user_query)
        
        # Parse the response
        parsed_results = parse_perplexity_response(ai_response)
        
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
    """Demo endpoint"""
    return jsonify({
        'results': [
            {
                'supplier': 'Trade Insulations',
                'product_name': 'Celotex GA4050 / Recticel GP',
                'price': '£17.50'
            },
            {
                'supplier': 'Insulation4Less',
                'product_name': 'Unilin Thin-R PIR',
                'price': '£18.22'
            },
            {
                'supplier': 'Insulation Wholesale',
                'product_name': 'Ecotherm Eco-Versal PIR',
                'price': '£18.08'
            }
        ],
        'ai_summary': 'Top suppliers: Trade Insulations: £17.50, Insulation4Less: £18.22, Insulation Wholesale: £18.08',
        'search_metadata': {
            'total_results': 3,
            'search_time': '2.1s'
        }
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
