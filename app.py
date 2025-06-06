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
    """Call Perplexity API with user's exact query"""
    if not PERPLEXITY_API_KEY:
        raise Exception("Perplexity API key not configured")
    
    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "llama-3.1-sonar-large-128k-online",
        "messages": [
            {
                "role": "user", 
                "content": user_query
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

def robust_parse_response(content):
    """Robust parsing that handles multiple response formats"""
    products = []
    
    # Method 1: Look for table format with | separators
    lines = content.split('\n')
    for line in lines:
        line = line.strip()
        if '|' in line and '£' in line and any(char.isdigit() for char in line):
            parts = [part.strip() for part in line.split('|')]
            if len(parts) >= 3:
                # Skip header rows
                if 'rank' in parts[0].lower() or 'supplier' in parts[1].lower():
                    continue
                
                rank_part = parts[0]
                supplier_part = parts[1] if len(parts) > 1 else ""
                price_part = parts[2] if len(parts) > 2 else ""
                
                # Extract supplier and product
                if '–' in supplier_part or '-' in supplier_part:
                    split_parts = re.split(r'[–-]', supplier_part, 1)
                    supplier = split_parts[0].strip()
                    product_name = split_parts[1].strip() if len(split_parts) > 1 else ""
                else:
                    supplier = supplier_part.strip()
                    product_name = ""
                
                # Extract price
                price_match = re.search(r'£([\d,]+\.?\d*)', price_part)
                price = f"£{price_match.group(1)}" if price_match else ""
                
                if supplier and price:
                    products.append({
                        'supplier': supplier,
                        'product_name': product_name or "Building Material",
                        'price': price
                    })
    
    # Method 2: Look for numbered list format if no table found
    if not products:
        current_item = {}
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Look for numbered items
            if re.match(r'^\d+\.?\s', line):
                # Save previous item
                if current_item.get('supplier') and current_item.get('price'):
                    products.append(current_item)
                
                # Start new item
                current_item = {}
                
                # Extract supplier from numbered line
                line_clean = re.sub(r'^\d+\.?\s*', '', line)
                
                # Look for supplier name patterns
                supplier_patterns = [
                    r'^([^–-]+)(?:[–-](.+))?',
                    r'^(.+?)(?:\s*-\s*(.+))?$'
                ]
                
                for pattern in supplier_patterns:
                    match = re.search(pattern, line_clean)
                    if match:
                        current_item['supplier'] = match.group(1).strip()
                        if match.group(2):
                            current_item['product_name'] = match.group(2).strip()
                        break
                
                if not current_item.get('supplier'):
                    current_item['supplier'] = line_clean
            
            # Look for price in current or next lines
            elif '£' in line and current_item.get('supplier'):
                price_match = re.search(r'£([\d,]+\.?\d*)', line)
                if price_match:
                    current_item['price'] = f"£{price_match.group(1)}"
            
            # Look for product information
            elif any(keyword in line.lower() for keyword in ['product', 'board', 'plasterboard', 'insulation', 'celotex', 'kingspan']):
                if current_item.get('supplier') and not current_item.get('product_name'):
                    current_item['product_name'] = line.strip()
        
        # Add final item
        if current_item.get('supplier') and current_item.get('price'):
            products.append(current_item)
    
    # Method 3: Simple text extraction if other methods fail
    if not products:
        # Find all prices and suppliers mentioned
        all_prices = re.findall(r'£([\d,]+\.?\d*)', content)
        
        # Common supplier names to look for
        suppliers = [
            'Trade Insulations', 'Insulation4Less', 'Insulation Shop', 'Insulation Wholesale',
            'Insulation UK', 'Wickes', 'Screwfix', 'Buildbase', 'Selco', 'Jewson',
            'Travis Perkins', 'Homebase', 'B&Q', 'Building Materials Online'
        ]
        
        found_suppliers = []
        for supplier in suppliers:
            if supplier.lower() in content.lower():
                found_suppliers.append(supplier)
        
        # Match suppliers with prices (simple approach)
        for i, supplier in enumerate(found_suppliers[:len(all_prices)]):
            if i < len(all_prices):
                products.append({
                    'supplier': supplier,
                    'product_name': 'Building Material',
                    'price': f"£{all_prices[i]}"
                })
    
    # Clean up and set defaults
    for product in products:
        if not product.get('product_name'):
            if 'plasterboard' in content.lower():
                product['product_name'] = 'Plasterboard'
            elif 'pir' in content.lower() or 'insulation' in content.lower():
                product['product_name'] = 'PIR Insulation Board'
            else:
                product['product_name'] = 'Building Material'
    
    return products

def parse_perplexity_response(ai_response):
    """Parse Perplexity response with robust fallbacks"""
    try:
        content = ai_response['choices'][0]['message']['content']
        citations = ai_response.get('citations', [])
        
        # Use robust parsing
        products = robust_parse_response(content)
        
        # Sort by price (cheapest first)
        products.sort(key=lambda x: extract_price_value(x.get('price', '')))
        
        # Create summary
        if products:
            summary_parts = []
            for product in products[:3]:
                supplier = product.get('supplier', 'Unknown')
                price = product.get('price', 'N/A')
                summary_parts.append(f"{supplier}: {price}")
            summary = f"Top suppliers: {', '.join(summary_parts)}"
        else:
            summary = "Search completed - see full response below."
        
        return {
            'results': products[:5],
            'ai_summary': summary,
            'full_response': content,  # Always include for debugging
            'citations': citations,
            'search_metadata': {
                'total_results': len(products),
                'search_time': 'Real-time'
            }
        }
        
    except Exception as e:
        # Always return something, even if parsing fails
        content = ai_response.get('choices', [{}])[0].get('message', {}).get('content', 'No content')
        
        return {
            'results': [{
                'supplier': 'Search Results Available',
                'product_name': 'See full response below',
                'price': 'Various'
            }],
            'ai_summary': 'Search completed - check full response.',
            'full_response': content,
            'citations': ai_response.get('citations', []),
            'search_metadata': {
                'total_results': 1,
                'search_time': 'Real-time',
                'parsing_error': str(e)
            }
        }

@app.route('/', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'AI Building Materials Search API',
        'version': '2.1',
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/search', methods=['POST'])
def search_products():
    """Main search endpoint with robust parsing"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        user_query = data.get('query', '').strip()
        
        if not user_query:
            return jsonify({'error': 'Query parameter is required'}), 400
        
        if len(user_query) < 3:
            return jsonify({'error': 'Query must be at least 3 characters long'}), 400
        
        start_time = time.time()
        
        # Call Perplexity API
        ai_response = call_perplexity_api(user_query)
        
        # Parse with robust fallbacks
        parsed_results = parse_perplexity_response(ai_response)
        
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
    """Demo endpoint with sample data"""
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
