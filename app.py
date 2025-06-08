import json
import re
import os
import requests
from bs4 import BeautifulSoup
import time
from urllib.parse import urljoin, quote
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

print("🔧 Loading High-Accuracy Supplier Search API...")

# Enhanced supplier configurations with better selectors
SUPPLIERS = [
    {
        "name": "insulation4less",
        "website": "https://insulation4less.co.uk/",
        "search_url": "https://insulation4less.co.uk/search?q={query}",
        "product_selector": ".product-item, .grid__item, .product-card",
        "name_selector": ".product-item__title, .product__title, h3 a, .product-title",
        "price_selector": ".price .money, .product-item__price, .price-item",
        "link_selector": ".product-item__title a, .product__title a, h3 a",
        "delivery": "All UK"
    },
    {
        "name": "cutpriceinsulation", 
        "website": "https://www.cutpriceinsulation.co.uk/",
        "search_url": "https://www.cutpriceinsulation.co.uk/search?q={query}",
        "product_selector": ".product, .product-item, .search-result",
        "name_selector": ".product-title, h2 a, h3 a, .title a",
        "price_selector": ".price, .product-price, .cost, .amount",
        "link_selector": ".product-title a, h2 a, h3 a",
        "delivery": "All UK"
    },
    {
        "name": "wickes",
        "website": "https://www.wickes.co.uk/",
        "search_url": "https://www.wickes.co.uk/search?text={query}",
        "product_selector": ".product-tile, .product-item, .search-result-item",
        "name_selector": ".product-title, .tile-title, h3 a, .product-name",
        "price_selector": ".price, .product-price, .cost, .price-current",
        "link_selector": ".product-title a, .tile-title a, h3 a",
        "delivery": "All UK"
    }
]

def clean_price(price_text):
    """Enhanced price extraction"""
    if not price_text:
        return None
    
    # Remove common text and extract price
    price_text = str(price_text).replace(',', '').replace('from', '').replace('From', '')
    price_match = re.search(r'£\s*(\d+\.?\d*)', price_text)
    if price_match:
        try:
            price = float(price_match.group(1))
            # Filter out unrealistic prices
            if 1 <= price <= 1000:
                return price
        except:
            pass
    return None

def is_relevant_product(product_name, search_query):
    """Check if product is relevant to search query"""
    if not product_name or len(product_name) < 5:
        return False
    
    product_lower = product_name.lower()
    query_lower = search_query.lower()
    
    # Skip navigation/UI elements
    skip_terms = ['sort by', 'filter', 'menu', 'navigation', 'breadcrumb', 'footer', 'header']
    if any(term in product_lower for term in skip_terms):
        return False
    
    # Extract key terms from query
    query_terms = re.findall(r'\b\w+\b', query_lower)
    important_terms = []
    
    for term in query_terms:
        if len(term) > 2 and term not in ['the', 'and', 'for', 'with', 'cheapest', 'best']:
            important_terms.append(term)
    
    # Check if product contains important terms
    if important_terms:
        matches = sum(1 for term in important_terms if term in product_lower)
        relevance_score = matches / len(important_terms)
        return relevance_score >= 0.3  # At least 30% of terms must match
    
    return True

def extract_product_info(product_elem, supplier, search_query):
    """Enhanced product information extraction"""
    try:
        # Extract product name with multiple attempts
        product_name = None
        for selector in supplier['name_selector'].split(', '):
            name_elem = product_elem.select_one(selector.strip())
            if name_elem:
                product_name = name_elem.get_text(strip=True)
                if product_name and len(product_name) > 5:
                    break
        
        # Fallback: get text from any link or heading
        if not product_name:
            for tag in ['a', 'h1', 'h2', 'h3', 'h4']:
                elem = product_elem.find(tag)
                if elem:
                    text = elem.get_text(strip=True)
                    if text and len(text) > 5:
                        product_name = text
                        break
        
        if not product_name or not is_relevant_product(product_name, search_query):
            return None
        
        # Extract price with multiple attempts
        price = None
        for selector in supplier['price_selector'].split(', '):
            price_elem = product_elem.select_one(selector.strip())
            if price_elem:
                price = clean_price(price_elem.get_text(strip=True))
                if price:
                    break
        
        # Fallback: look for any price in the product element
        if not price:
            price_text = product_elem.get_text()
            price = clean_price(price_text)
        
        if not price:
            return None
        
        # Extract product URL
        product_url = supplier['website']
        if 'link_selector' in supplier:
            for selector in supplier['link_selector'].split(', '):
                link_elem = product_elem.select_one(selector.strip())
                if link_elem and link_elem.get('href'):
                    product_url = urljoin(supplier['website'], link_elem['href'])
                    break
        
        if product_url == supplier['website']:
            # Fallback: find any link in the product
            link_elem = product_elem.find('a', href=True)
            if link_elem:
                product_url = urljoin(supplier['website'], link_elem['href'])
        
        # Extract image
        image_url = ""
        img_elem = product_elem.find('img')
        if img_elem:
            img_src = img_elem.get('src') or img_elem.get('data-src') or img_elem.get('data-lazy-src')
            if img_src and 'placeholder' not in img_src.lower():
                image_url = urljoin(supplier['website'], img_src)
        
        # Calculate relevance score
        relevance_score = calculate_relevance(product_name, search_query)
        
        return {
            "supplier": supplier['name'],
            "price": f"£{price:.2f}",
            "price_numeric": price,
            "product_name": product_name[:200],
            "category": detect_category(product_name),
            "supplier_website": supplier['website'],
            "product_url": product_url,
            "product_image": image_url,
            "availability": "Check with supplier",
            "delivery": supplier['delivery'],
            "contact": "See website",
            "rating": "N/A",
            "relevance_score": relevance_score
        }
        
    except Exception as e:
        print(f"⚠️ Error extracting product info: {e}")
        return None

def calculate_relevance(product_name, search_query):
    """Calculate relevance score between product and query"""
    product_lower = product_name.lower()
    query_lower = search_query.lower()
    
    # Extract important terms
    query_terms = re.findall(r'\b\w+\b', query_lower)
    important_terms = [term for term in query_terms if len(term) > 2 and term not in ['the', 'and', 'for', 'with', 'cheapest', 'best', 'top']]
    
    if not important_terms:
        return 0.5
    
    matches = sum(1 for term in important_terms if term in product_lower)
    base_score = matches / len(important_terms)
    
    # Bonus for exact phrase matches
    if len(important_terms) >= 2:
        phrase = ' '.join(important_terms[:2])
        if phrase in product_lower:
            base_score += 0.2
    
    # Bonus for thickness/size matches
    thickness_match = re.search(r'(\d+)mm', query_lower)
    if thickness_match:
        thickness = thickness_match.group(1)
        if thickness in product_lower:
            base_score += 0.3
    
    return min(base_score, 1.0)

def detect_category(product_name):
    """Detect product category from name"""
    name_lower = product_name.lower()
    
    if any(term in name_lower for term in ['pir', 'polyisocyanurate']):
        return 'PIR Insulation'
    elif any(term in name_lower for term in ['mineral wool', 'rockwool', 'glasswool']):
        return 'Mineral Wool Insulation'
    elif 'plasterboard' in name_lower:
        return 'Plasterboard'
    elif 'insulation' in name_lower:
        return 'General Insulation'
    else:
        return 'Building Materials'

def search_supplier_website(supplier, query, max_results=4):
    """Enhanced supplier search with better accuracy"""
    results = []
    
    try:
        search_url = supplier['search_url'].format(query=quote(query))
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-GB,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }
        
        print(f"🔍 Searching {supplier['name']}: {search_url}")
        response = requests.get(search_url, headers=headers, timeout=12)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find product containers
            products = soup.select(supplier['product_selector'])
            print(f"📦 Found {len(products)} product containers on {supplier['name']}")
            
            valid_products = []
            for product in products[:max_results * 2]:  # Check more products for better filtering
                product_info = extract_product_info(product, supplier, query)
                if product_info and product_info['relevance_score'] > 0.2:
                    valid_products.append(product_info)
                    print(f"✅ Found: {product_info['product_name'][:60]}... - £{product_info['price_numeric']:.2f} (relevance: {product_info['relevance_score']:.2f})")
            
            # Sort by relevance score, then by price
            valid_products.sort(key=lambda x: (-x['relevance_score'], x['price_numeric']))
            results = valid_products[:max_results]
        
        else:
            print(f"❌ HTTP {response.status_code} from {supplier['name']}")
        
        print(f"✅ Found {len(results)} relevant products from {supplier['name']}")
        return results
        
    except Exception as e:
        print(f"❌ Error searching {supplier['name']}: {e}")
        return []

def search_suppliers_accurate(query, max_suppliers=3):
    """Accurate search with relevance filtering"""
    all_results = []
    
    print(f"🔍 Starting accurate search for: {query}")
    
    for supplier in SUPPLIERS[:max_suppliers]:
        try:
            supplier_results = search_supplier_website(supplier, query, max_results=3)
            all_results.extend(supplier_results)
            time.sleep(1.5)  # Longer delay for better reliability
                
        except Exception as e:
            print(f"❌ {supplier['name']} search failed: {e}")
            continue
    
    # Remove duplicates and sort by relevance + price
    unique_results = []
    seen_products = set()
    
    for result in all_results:
        product_key = (result['product_name'][:50], result['supplier'])
        if product_key not in seen_products:
            seen_products.add(product_key)
            unique_results.append(result)
    
    # Sort by relevance score (desc) then price (asc)
    unique_results.sort(key=lambda x: (-x['relevance_score'], x['price_numeric']))
    
    print(f"✅ Accurate search completed. Found {len(unique_results)} relevant products")
    return unique_results

@app.route('/')
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "High-Accuracy Supplier Search API",
        "version": "3.3 - Enhanced Accuracy",
        "suppliers": len(SUPPLIERS),
        "search_type": "accurate_supplier_search",
        "features": ["relevance_scoring", "duplicate_removal", "category_detection"]
    })

@app.route('/api/search', methods=['POST'])
def search():
    """High-accuracy search endpoint"""
    try:
        data = request.get_json()
        query = data.get('query', '').strip()
        max_results = min(data.get('max_results', 8), 15)
        
        if not query:
            return jsonify({"error": "Query parameter is required"}), 400
        
        print(f"🔍 High-accuracy search query: {query}")
        
        # Perform accurate search
        results = search_suppliers_accurate(query, max_suppliers=3)
        
        # Limit results
        results = results[:max_results]
        
        if not results:
            return jsonify({
                "query": query,
                "results": [],
                "total_results": 0,
                "search_type": "accurate_supplier_search",
                "message": "No relevant products found. Try more specific terms like '50mm PIR insulation' or 'plasterboard 12.5mm'.",
                "searched_suppliers": [s['name'] for s in SUPPLIERS],
                "suggestions": ["50mm insulation", "plasterboard", "mineral wool", "PIR board"]
            })
        
        response = {
            "query": query,
            "results": results,
            "total_results": len(results),
            "search_type": "accurate_supplier_search",
            "message": f"Found {len(results)} relevant products from {len(set([r['supplier'] for r in results]))} suppliers",
            "searched_suppliers": list(set([r['supplier'] for r in results])),
            "search_time": "Real-time with accuracy filtering"
        }
        
        return jsonify(response)
        
    except Exception as e:
        print(f"❌ Search error: {e}")
        return jsonify({
            "error": "Search temporarily unavailable",
            "message": "Please try again with specific product terms",
            "search_type": "accurate_supplier_search"
        }), 500

@app.route('/api/search/demo', methods=['GET'])
def demo():
    """Demo endpoint"""
    return jsonify({
        "message": "High-accuracy supplier search API. Use POST /api/search with specific queries like '50mm PIR insulation'.",
        "suppliers": [s['name'] for s in SUPPLIERS],
        "search_type": "accurate_supplier_search",
        "features": ["Relevance scoring", "Duplicate removal", "Category detection", "Price validation"]
    })

@app.route('/api/suppliers', methods=['GET'])
def get_suppliers():
    """Get available suppliers"""
    return jsonify({
        "suppliers": [{"name": s['name'], "website": s['website'], "delivery": s['delivery']} for s in SUPPLIERS],
        "total_suppliers": len(SUPPLIERS),
        "search_type": "accurate_supplier_search"
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

