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

print("🔧 Loading Memory-Optimized Supplier Search API...")

# Reduced supplier list for memory optimization
SUPPLIERS = [
    {"name": "insulation4less", "website": "https://insulation4less.co.uk/", "delivery": "All UK"},
    {"name": "cutpriceinsulation", "website": "https://www.cutpriceinsulation.co.uk/", "delivery": "All UK"},
    {"name": "buildersinsulation", "website": "https://buildersinsulation.co.uk/", "delivery": "All UK"},
    {"name": "constructionmegastore", "website": "https://constructionmegastore.co.uk/", "delivery": "All UK"},
    {"name": "wickes", "website": "https://www.wickes.co.uk/", "delivery": "All UK"}
]

def clean_price(price_text):
    """Extract price from text"""
    if not price_text:
        return None
    
    price_match = re.search(r'£?(\d+\.?\d*)', str(price_text).replace(',', ''))
    if price_match:
        return float(price_match.group(1))
    return None

def search_supplier_website(supplier, query, max_results=2):
    """Memory-optimized supplier search"""
    results = []
    
    try:
        # Simplified search URL
        search_url = f"{supplier['website']}search?q={quote(query)}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        print(f"🔍 Searching {supplier['name']}")
        response = requests.get(search_url, headers=headers, timeout=8)
        
        if response.status_code == 200:
            # Use lxml parser for better memory efficiency
            soup = BeautifulSoup(response.content, 'lxml')
            
            # Look for products with simpler selectors
            products = soup.find_all(['div', 'article'], class_=lambda x: x and 'product' in x.lower())[:max_results]
            
            if not products:
                # Fallback to any element containing price
                products = soup.find_all(string=re.compile(r'£\d+'))[:max_results]
                products = [p.parent for p in products if p.parent]
            
            for product in products[:max_results]:
                try:
                    # Extract product name
                    name_elem = product.find(['h2', 'h3', 'h4', 'a'])
                    product_name = name_elem.get_text(strip=True) if name_elem else "Product"
                    
                    # Extract price
                    price_elem = product.find(string=re.compile(r'£\d+'))
                    if not price_elem:
                        price_elem = product.find(class_=lambda x: x and 'price' in x.lower())
                    
                    price = None
                    if price_elem:
                        price = clean_price(price_elem if isinstance(price_elem, str) else price_elem.get_text())
                    
                    # Extract link
                    link_elem = product.find('a', href=True)
                    product_url = urljoin(supplier['website'], link_elem['href']) if link_elem else supplier['website']
                    
                    if product_name and price and price > 0:
                        result = {
                            "supplier": supplier['name'],
                            "price": f"£{price:.2f}",
                            "price_numeric": price,
                            "product_name": product_name[:100],  # Limit length
                            "category": "Building Materials",
                            "supplier_website": supplier['website'],
                            "product_url": product_url,
                            "availability": "Check with supplier",
                            "delivery": supplier['delivery'],
                            "contact": "See website",
                            "rating": "N/A"
                        }
                        results.append(result)
                
                except Exception as e:
                    continue
        
        print(f"✅ Found {len(results)} products from {supplier['name']}")
        return results
        
    except Exception as e:
        print(f"❌ Error searching {supplier['name']}: {e}")
        return []

def search_suppliers_sequential(query, max_suppliers=3):
    """Sequential search to reduce memory usage"""
    all_results = []
    
    print(f"🔍 Starting optimized search for: {query}")
    
    # Search suppliers one by one (sequential, not concurrent)
    for i, supplier in enumerate(SUPPLIERS[:max_suppliers]):
        try:
            supplier_results = search_supplier_website(supplier, query, max_results=2)
            all_results.extend(supplier_results)
            
            # Small delay to prevent overwhelming servers
            if i < len(SUPPLIERS) - 1:
                time.sleep(0.5)
                
        except Exception as e:
            print(f"❌ {supplier['name']} search failed: {e}")
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
        "service": "Memory-Optimized Supplier Search API",
        "version": "3.1 - Optimized",
        "suppliers": len(SUPPLIERS),
        "search_type": "sequential_web_search",
        "memory_optimized": True
    })

@app.route('/api/search', methods=['POST'])
def search():
    """Optimized search endpoint"""
    try:
        data = request.get_json()
        query = data.get('query', '').strip()
        max_results = min(data.get('max_results', 6), 10)  # Reduced limit
        
        if not query:
            return jsonify({"error": "Query parameter is required"}), 400
        
        print(f"🔍 Optimized search query: {query}")
        
        # Perform sequential search (memory efficient)
        results = search_suppliers_sequential(query, max_suppliers=3)
        
        # Limit results
        results = results[:max_results]
        
        if not results:
            return jsonify({
                "query": query,
                "results": [],
                "total_results": 0,
                "search_type": "optimized_supplier_search",
                "message": "No products found. Try simpler keywords like '50mm insulation' or 'plasterboard'.",
                "searched_suppliers": [s['name'] for s in SUPPLIERS[:3]]
            })
        
        response = {
            "query": query,
            "results": results,
            "total_results": len(results),
            "search_type": "optimized_supplier_search",
            "message": f"Found {len(results)} products from supplier search",
            "searched_suppliers": list(set([r['supplier'] for r in results])),
            "search_time": "Optimized"
        }
        
        return jsonify(response)
        
    except Exception as e:
        print(f"❌ Search error: {e}")
        return jsonify({
            "error": "Search failed",
            "message": "Please try simpler search terms",
            "search_type": "optimized_supplier_search"
        }), 500

@app.route('/api/search/demo', methods=['GET'])
def demo():
    """Demo endpoint"""
    return jsonify({
        "query": "demo search",
        "message": "Memory-optimized supplier search API. Use POST /api/search with simple queries like '50mm insulation'.",
        "suppliers": [s['name'] for s in SUPPLIERS],
        "search_type": "optimized_supplier_search"
    })

@app.route('/api/suppliers', methods=['GET'])
def get_suppliers():
    """Get available suppliers"""
    return jsonify({
        "suppliers": SUPPLIERS,
        "total_suppliers": len(SUPPLIERS),
        "search_type": "optimized_web_search"
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

