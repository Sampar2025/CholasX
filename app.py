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

print("🔧 Loading Supplier-Specific Search API...")

# Supplier configurations with specific search patterns
SUPPLIERS = [
    {
        "name": "insulation4less",
        "website": "https://insulation4less.co.uk/",
        "search_url": "https://insulation4less.co.uk/search?q={query}",
        "product_selector": ".product-item, .grid__item",
        "name_selector": ".product-item__title, h3, .product__title",
        "price_selector": ".price, .product-item__price, .money",
        "delivery": "All UK"
    },
    {
        "name": "cutpriceinsulation", 
        "website": "https://www.cutpriceinsulation.co.uk/",
        "search_url": "https://www.cutpriceinsulation.co.uk/search?q={query}",
        "product_selector": ".product, .product-item, .item",
        "name_selector": "h2, h3, .product-title, .title",
        "price_selector": ".price, .cost, .amount",
        "delivery": "All UK"
    },
    {
        "name": "wickes",
        "website": "https://www.wickes.co.uk/",
        "search_url": "https://www.wickes.co.uk/search?text={query}",
        "product_selector": ".product-tile, .product-item, .product",
        "name_selector": ".product-title, h3, .title",
        "price_selector": ".price, .product-price, .cost",
        "delivery": "All UK"
    }
]

def clean_price(price_text):
    """Extract price from text"""
    if not price_text:
        return None
    
    # Remove currency symbols and extract numbers
    price_match = re.search(r'£?(\d+\.?\d*)', str(price_text).replace(',', ''))
    if price_match:
        try:
            return float(price_match.group(1))
        except:
            return None
    return None

def search_supplier_website(supplier, query, max_results=3):
    """Search specific supplier with tailored selectors"""
    results = []
    
    try:
        # Use supplier-specific search URL
        search_url = supplier['search_url'].format(query=quote(query))
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }
        
        print(f"🔍 Searching {supplier['name']}: {search_url}")
        response = requests.get(search_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Use supplier-specific product selector
            products = soup.select(supplier['product_selector'])
            
            if not products:
                # Fallback: look for any elements containing prices
                products = soup.find_all(string=re.compile(r'£\d+'))
                products = [p.parent.parent for p in products if p.parent and p.parent.parent][:max_results]
            
            print(f"📦 Found {len(products)} product containers on {supplier['name']}")
            
            for product in products[:max_results]:
                try:
                    # Extract product name using supplier-specific selector
                    product_name = None
                    for selector in supplier['name_selector'].split(', '):
                        name_elem = product.select_one(selector.strip())
                        if name_elem:
                            product_name = name_elem.get_text(strip=True)
                            break
                    
                    if not product_name:
                        # Fallback: get any text from the product container
                        product_name = product.get_text(strip=True)[:100]
                    
                    # Extract price using supplier-specific selector
                    price = None
                    for selector in supplier['price_selector'].split(', '):
                        price_elem = product.select_one(selector.strip())
                        if price_elem:
                            price = clean_price(price_elem.get_text(strip=True))
                            if price:
                                break
                    
                    if not price:
                        # Fallback: look for any price in the product text
                        price_text = product.get_text()
                        price = clean_price(price_text)
                    
                    # Extract product URL
                    product_url = supplier['website']
                    link_elem = product.find('a', href=True)
                    if link_elem:
                        href = link_elem.get('href')
                        if href:
                            product_url = urljoin(supplier['website'], href)
                    
                    # Extract image
                    image_url = ""
                    img_elem = product.find('img')
                    if img_elem:
                        img_src = img_elem.get('src') or img_elem.get('data-src') or img_elem.get('data-lazy-src')
                        if img_src:
                            image_url = urljoin(supplier['website'], img_src)
                    
                    if product_name and price and price > 0:
                        result = {
                            "supplier": supplier['name'],
                            "price": f"£{price:.2f}",
                            "price_numeric": price,
                            "product_name": product_name[:150],
                            "category": "Building Materials",
                            "supplier_website": supplier['website'],
                            "product_url": product_url,
                            "product_image": image_url,
                            "availability": "In Stock",
                            "delivery": supplier['delivery'],
                            "contact": "See website",
                            "rating": "N/A"
                        }
                        results.append(result)
                        print(f"✅ Found: {product_name[:50]}... - £{price:.2f}")
                
                except Exception as e:
                    print(f"⚠️ Error parsing product: {e}")
                    continue
        
        else:
            print(f"❌ HTTP {response.status_code} from {supplier['name']}")
        
        print(f"✅ Found {len(results)} valid products from {supplier['name']}")
        return results
        
    except Exception as e:
        print(f"❌ Error searching {supplier['name']}: {e}")
        return []

def search_suppliers_with_fallback(query, max_suppliers=3):
    """Search suppliers with fallback strategies"""
    all_results = []
    
    print(f"🔍 Starting targeted search for: {query}")
    
    # Search each supplier
    for supplier in SUPPLIERS[:max_suppliers]:
        try:
            supplier_results = search_supplier_website(supplier, query, max_results=3)
            all_results.extend(supplier_results)
            
            # Small delay between requests
            time.sleep(1)
                
        except Exception as e:
            print(f"❌ {supplier['name']} search failed: {e}")
            continue
    
    # If no results, try with simplified query
    if not all_results and len(query.split()) > 2:
        simple_query = ' '.join(query.split()[:2])  # Take first 2 words
        print(f"🔄 Retrying with simplified query: {simple_query}")
        
        for supplier in SUPPLIERS[:2]:  # Try fewer suppliers
            try:
                supplier_results = search_supplier_website(supplier, simple_query, max_results=2)
                all_results.extend(supplier_results)
                time.sleep(1)
            except:
                continue
    
    # Sort by price
    all_results.sort(key=lambda x: x.get('price_numeric', float('inf')))
    
    print(f"✅ Search completed. Found {len(all_results)} total products")
    return all_results

@app.route('/')
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "Supplier-Specific Search API",
        "version": "3.2 - Targeted Scraping",
        "suppliers": len(SUPPLIERS),
        "search_type": "supplier_specific_scraping",
        "supplier_list": [s['name'] for s in SUPPLIERS]
    })

@app.route('/api/search', methods=['POST'])
def search():
    """Targeted supplier search endpoint"""
    try:
        data = request.get_json()
        query = data.get('query', '').strip()
        max_results = min(data.get('max_results', 8), 12)
        
        if not query:
            return jsonify({"error": "Query parameter is required"}), 400
        
        print(f"🔍 Targeted search query: {query}")
        
        # Perform targeted search
        results = search_suppliers_with_fallback(query, max_suppliers=3)
        
        # Limit results
        results = results[:max_results]
        
        if not results:
            return jsonify({
                "query": query,
                "results": [],
                "total_results": 0,
                "search_type": "supplier_specific_search",
                "message": "No products found. Try simpler terms like 'insulation', 'plasterboard', or specific thicknesses like '50mm'.",
                "searched_suppliers": [s['name'] for s in SUPPLIERS],
                "suggestion": "Try searching for: '50mm insulation', 'plasterboard', 'mineral wool'"
            })
        
        response = {
            "query": query,
            "results": results,
            "total_results": len(results),
            "search_type": "supplier_specific_search",
            "message": f"Found {len(results)} products from {len(set([r['supplier'] for r in results]))} suppliers",
            "searched_suppliers": list(set([r['supplier'] for r in results])),
            "search_time": "Real-time"
        }
        
        return jsonify(response)
        
    except Exception as e:
        print(f"❌ Search error: {e}")
        return jsonify({
            "error": "Search temporarily unavailable",
            "message": "Please try again with simpler search terms",
            "search_type": "supplier_specific_search",
            "suggestion": "Try: 'insulation', 'plasterboard', or '50mm'"
        }), 500

@app.route('/api/search/demo', methods=['GET'])
def demo():
    """Demo endpoint with test search"""
    try:
        # Perform a test search
        test_results = search_suppliers_with_fallback("insulation", max_suppliers=2)
        
        return jsonify({
            "query": "insulation (demo)",
            "results": test_results[:3],
            "total_results": len(test_results),
            "search_type": "demo_supplier_search",
            "message": f"Demo found {len(test_results)} products",
            "suppliers": [s['name'] for s in SUPPLIERS]
        })
    except:
        return jsonify({
            "query": "demo",
            "message": "Supplier-specific search API ready. Use POST /api/search with queries like 'insulation' or '50mm'.",
            "suppliers": [s['name'] for s in SUPPLIERS],
            "search_type": "demo"
        })

@app.route('/api/suppliers', methods=['GET'])
def get_suppliers():
    """Get available suppliers"""
    return jsonify({
        "suppliers": [{"name": s['name'], "website": s['website'], "delivery": s['delivery']} for s in SUPPLIERS],
        "total_suppliers": len(SUPPLIERS),
        "search_type": "supplier_specific_scraping"
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

