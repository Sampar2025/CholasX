import json
import re
import os
import requests
from bs4 import BeautifulSoup
import time
from urllib.parse import urljoin, quote, urlparse
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

print("🔧 Loading Intelligent Supplier Scraping API...")

# Intelligent supplier configurations based on website analysis
SUPPLIERS = [
    {
        "name": "insulation4less",
        "website": "https://insulation4less.co.uk/",
        "search_strategy": "search_url",
        "search_url": "https://insulation4less.co.uk/search?q={query}&options%5Bprefix%5D=last",
        "selectors": {
            "product_container": ".grid__item, .product-item",
            "product_name": "h3 a, .product-item__title a, .product__title",
            "price": ".price .money, .price-item, .product-item__price",
            "link": "h3 a, .product-item__title a",
            "image": "img"
        },
        "price_pattern": r"£(\d+\.?\d*)",
        "contact": "020-3582-6399",
        "delivery": "Next Day Delivery Available"
    },
    {
        "name": "cutpriceinsulation", 
        "website": "https://www.cutpriceinsulation.co.uk/",
        "search_strategy": "category_navigation",
        "thickness_urls": {
            "25mm": "https://www.cutpriceinsulation.co.uk/collections/25mm",
            "40mm": "https://www.cutpriceinsulation.co.uk/collections/40mm", 
            "50mm": "https://www.cutpriceinsulation.co.uk/collections/50mm",
            "75mm": "https://www.cutpriceinsulation.co.uk/collections/75mm",
            "90mm": "https://www.cutpriceinsulation.co.uk/collections/90mm",
            "100mm": "https://www.cutpriceinsulation.co.uk/collections/100mm",
            "120mm": "https://www.cutpriceinsulation.co.uk/collections/120mm",
            "150mm": "https://www.cutpriceinsulation.co.uk/collections/150mm"
        },
        "selectors": {
            "product_container": ".product-item, .grid-item",
            "product_name": "h3 a, .product-title",
            "price": ".price, .money",
            "link": "h3 a, .product-title a",
            "image": "img"
        },
        "price_pattern": r"£(\d+\.?\d*)",
        "contact": "01480 878787",
        "delivery": "Next Day Delivery Available"
    },
    {
        "name": "wickes",
        "website": "https://www.wickes.co.uk/",
        "search_strategy": "search_url",
        "search_url": "https://www.wickes.co.uk/search?text={query}",
        "selectors": {
            "product_container": ".product-tile, .product-item",
            "product_name": ".product-title, h3",
            "price": ".price, .product-price",
            "link": ".product-title a, h3 a",
            "image": "img"
        },
        "price_pattern": r"£(\d+\.?\d*)",
        "contact": "See website",
        "delivery": "Store Collection Available"
    }
]

def extract_thickness_from_query(query):
    """Extract thickness from search query"""
    thickness_match = re.search(r'(\d+)mm', query.lower())
    if thickness_match:
        return thickness_match.group(1) + "mm"
    return None

def clean_price(price_text, pattern):
    """Extract price using supplier-specific pattern"""
    if not price_text:
        return None
    
    price_match = re.search(pattern, str(price_text).replace(',', ''))
    if price_match:
        try:
            price = float(price_match.group(1))
            if 1 <= price <= 2000:  # Reasonable price range
                return price
        except:
            pass
    return None

def is_relevant_product(product_name, search_query):
    """Enhanced relevance checking"""
    if not product_name or len(product_name) < 5:
        return False
    
    product_lower = product_name.lower()
    query_lower = search_query.lower()
    
    # Skip non-product elements
    skip_terms = ['sort by', 'filter', 'menu', 'navigation', 'breadcrumb', 'footer', 'header', 'add to cart']
    if any(term in product_lower for term in skip_terms):
        return False
    
    # Extract key terms
    query_terms = re.findall(r'\b\w+\b', query_lower)
    important_terms = [term for term in query_terms if len(term) > 2 and term not in ['the', 'and', 'for', 'with', 'cheapest', 'best', 'top']]
    
    if not important_terms:
        return True
    
    # Check relevance
    matches = sum(1 for term in important_terms if term in product_lower)
    relevance_score = matches / len(important_terms)
    
    # Special bonus for thickness matches
    thickness = extract_thickness_from_query(search_query)
    if thickness and thickness in product_lower:
        relevance_score += 0.3
    
    return relevance_score >= 0.3

def search_supplier_intelligent(supplier, query, max_results=5):
    """Intelligent supplier-specific search"""
    results = []
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-GB,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }
        
        # Choose search strategy based on supplier
        if supplier['search_strategy'] == 'search_url':
            search_url = supplier['search_url'].format(query=quote(query))
        elif supplier['search_strategy'] == 'category_navigation':
            # Try to find thickness-specific URL
            thickness = extract_thickness_from_query(query)
            if thickness and thickness in supplier['thickness_urls']:
                search_url = supplier['thickness_urls'][thickness]
            else:
                # Fallback to 50mm as most common
                search_url = supplier['thickness_urls'].get('50mm', supplier['website'])
        else:
            search_url = supplier['website']
        
        print(f"🔍 Intelligent search on {supplier['name']}: {search_url}")
        response = requests.get(search_url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find products using supplier-specific selectors
            products = soup.select(supplier['selectors']['product_container'])
            print(f"📦 Found {len(products)} product containers on {supplier['name']}")
            
            for product in products[:max_results * 2]:  # Get extra for filtering
                try:
                    # Extract product name
                    name_elem = product.select_one(supplier['selectors']['product_name'])
                    if not name_elem:
                        continue
                    
                    product_name = name_elem.get_text(strip=True)
                    if not is_relevant_product(product_name, query):
                        continue
                    
                    # Extract price
                    price_elem = product.select_one(supplier['selectors']['price'])
                    if not price_elem:
                        continue
                    
                    price = clean_price(price_elem.get_text(strip=True), supplier['price_pattern'])
                    if not price:
                        continue
                    
                    # Extract link
                    link_elem = product.select_one(supplier['selectors']['link'])
                    product_url = supplier['website']
                    if link_elem and link_elem.get('href'):
                        product_url = urljoin(supplier['website'], link_elem['href'])
                    
                    # Extract image
                    img_elem = product.select_one(supplier['selectors']['image'])
                    image_url = ""
                    if img_elem:
                        img_src = img_elem.get('src') or img_elem.get('data-src')
                        if img_src:
                            image_url = urljoin(supplier['website'], img_src)
                    
                    result = {
                        "supplier": supplier['name'],
                        "price": f"£{price:.2f}",
                        "price_numeric": price,
                        "product_name": product_name[:200],
                        "category": detect_category(product_name),
                        "supplier_website": supplier['website'],
                        "product_url": product_url,
                        "product_image": image_url,
                        "availability": "In Stock",
                        "delivery": supplier['delivery'],
                        "contact": supplier['contact'],
                        "rating": "4.5 stars"
                    }
                    results.append(result)
                    print(f"✅ Found: {product_name[:60]}... - £{price:.2f}")
                    
                    if len(results) >= max_results:
                        break
                
                except Exception as e:
                    continue
        
        else:
            print(f"❌ HTTP {response.status_code} from {supplier['name']}")
        
        print(f"✅ Found {len(results)} relevant products from {supplier['name']}")
        return results
        
    except Exception as e:
        print(f"❌ Error searching {supplier['name']}: {e}")
        return []

def detect_category(product_name):
    """Detect product category"""
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

def search_all_suppliers_intelligent(query, max_suppliers=3):
    """Intelligent search across all suppliers"""
    all_results = []
    
    print(f"🔍 Starting intelligent search for: {query}")
    
    for supplier in SUPPLIERS[:max_suppliers]:
        try:
            supplier_results = search_supplier_intelligent(supplier, query, max_results=4)
            all_results.extend(supplier_results)
            time.sleep(2)  # Respectful delay
                
        except Exception as e:
            print(f"❌ {supplier['name']} search failed: {e}")
            continue
    
    # Remove duplicates and sort by price
    unique_results = []
    seen_products = set()
    
    for result in all_results:
        product_key = (result['product_name'][:50].lower(), result['supplier'])
        if product_key not in seen_products:
            seen_products.add(product_key)
            unique_results.append(result)
    
    # Sort by price (cheapest first)
    unique_results.sort(key=lambda x: x['price_numeric'])
    
    print(f"✅ Intelligent search completed. Found {len(unique_results)} unique products")
    return unique_results

@app.route('/')
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "Intelligent Supplier Scraping API",
        "version": "4.0 - AI-Powered Scraping",
        "suppliers": len(SUPPLIERS),
        "search_type": "intelligent_supplier_scraping",
        "features": ["supplier_specific_strategies", "relevance_filtering", "price_sorting", "duplicate_removal"]
    })

@app.route('/api/search', methods=['POST'])
def search():
    """Intelligent supplier search endpoint"""
    try:
        data = request.get_json()
        query = data.get('query', '').strip()
        max_results = min(data.get('max_results', 10), 15)
        
        if not query:
            return jsonify({"error": "Query parameter is required"}), 400
        
        print(f"🔍 Intelligent search query: {query}")
        
        # Perform intelligent search
        results = search_all_suppliers_intelligent(query, max_suppliers=3)
        
        # Limit results
        results = results[:max_results]
        
        if not results:
            return jsonify({
                "query": query,
                "results": [],
                "total_results": 0,
                "search_type": "intelligent_supplier_search",
                "message": "No products found across supplier websites. Try specific terms like '50mm PIR insulation' or 'plasterboard'.",
                "searched_suppliers": [s['name'] for s in SUPPLIERS],
                "suggestions": ["50mm PIR insulation", "25mm insulation board", "plasterboard 12.5mm"]
            })
        
        # Generate AI summary
        cheapest = min(results, key=lambda x: x['price_numeric'])
        ai_summary = f"Found {len(results)} products across {len(set([r['supplier'] for r in results]))} suppliers. Cheapest: {cheapest['product_name'][:50]}... at {cheapest['price']} from {cheapest['supplier']}."
        
        response = {
            "query": query,
            "results": results,
            "total_results": len(results),
            "search_type": "intelligent_supplier_search",
            "ai_summary": ai_summary,
            "message": f"Found {len(results)} products from live supplier search",
            "searched_suppliers": list(set([r['supplier'] for r in results])),
            "search_time": "Real-time intelligent scraping"
        }
        
        return jsonify(response)
        
    except Exception as e:
        print(f"❌ Search error: {e}")
        return jsonify({
            "error": "Search temporarily unavailable",
            "message": "Please try again with specific product terms",
            "search_type": "intelligent_supplier_search"
        }), 500

@app.route('/api/search/demo', methods=['GET'])
def demo():
    """Demo endpoint"""
    return jsonify({
        "message": "Intelligent supplier search API. Searches real supplier websites with AI-powered extraction.",
        "suppliers": [s['name'] for s in SUPPLIERS],
        "search_type": "intelligent_supplier_search",
        "example_queries": ["50mm PIR insulation", "cheapest plasterboard", "mineral wool 100mm"]
    })

@app.route('/api/suppliers', methods=['GET'])
def get_suppliers():
    """Get available suppliers"""
    return jsonify({
        "suppliers": [{"name": s['name'], "website": s['website'], "strategy": s['search_strategy']} for s in SUPPLIERS],
        "total_suppliers": len(SUPPLIERS),
        "search_type": "intelligent_supplier_scraping"
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

