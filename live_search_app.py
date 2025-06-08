import json
import re
import pickle
import os
import requests
from bs4 import BeautifulSoup
import time
import concurrent.futures
from urllib.parse import urljoin, quote
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

print("🔧 Loading Live Supplier Search API...")

# Load supplier data
SUPPLIERS = [
    {"name": "insulation4less", "website": "https://insulation4less.co.uk/", "delivery": "All UK", "country": "UK"},
    {"name": "cutpriceinsulation", "website": "https://www.cutpriceinsulation.co.uk/", "delivery": "All UK", "country": "UK"},
    {"name": "nationalinsulationsupplies", "website": "https://www.nationalinsulationsupplies.com/", "delivery": "All UK", "country": "UK"},
    {"name": "buildersinsulation", "website": "https://buildersinsulation.co.uk/", "delivery": "All UK", "country": "UK"},
    {"name": "insulationuk", "website": "https://www.insulationuk.co.uk/", "delivery": "All UK", "country": "UK"},
    {"name": "buyinsulation", "website": "https://buyinsulation.co.uk/", "delivery": "All UK", "country": "UK"},
    {"name": "constructionmegastore", "website": "https://constructionmegastore.co.uk/", "delivery": "All UK", "country": "UK"},
    {"name": "insulationsuperstore", "website": "https://www.insulationsuperstore.co.uk/", "delivery": "All UK", "country": "UK"},
    {"name": "tradeinsulations", "website": "https://www.tradeinsulations.co.uk/", "delivery": "All UK", "country": "UK"},
    {"name": "wickes", "website": "https://www.wickes.co.uk/", "delivery": "All UK", "country": "UK"},
    {"name": "diy.com", "website": "https://www.diy.com/", "delivery": "All UK", "country": "UK"}
]

def clean_price(price_text):
    """Extract price from text"""
    if not price_text:
        return None
    
    # Remove currency symbols and extract numbers
    price_match = re.search(r'£?(\d+\.?\d*)', str(price_text).replace(',', ''))
    if price_match:
        return float(price_match.group(1))
    return None

def search_supplier_website(supplier, query, max_results=5):
    """Search a specific supplier website for products"""
    results = []
    
    try:
        # Create search URL - try common search patterns
        search_patterns = [
            f"{supplier['website']}search?q={quote(query)}",
            f"{supplier['website']}search/{quote(query)}",
            f"{supplier['website']}?s={quote(query)}",
            f"{supplier['website']}products?search={quote(query)}"
        ]
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        for search_url in search_patterns:
            try:
                print(f"🔍 Searching {supplier['name']}: {search_url}")
                response = requests.get(search_url, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    # Look for product containers - common selectors
                    product_selectors = [
                        '.product', '.product-item', '.product-card',
                        '.woocommerce-product', '.shop-item',
                        '[data-product]', '.product-list-item',
                        '.grid-item', '.catalog-item'
                    ]
                    
                    products_found = []
                    for selector in product_selectors:
                        products_found.extend(soup.select(selector))
                        if len(products_found) >= max_results:
                            break
                    
                    if not products_found:
                        # Try generic containers
                        products_found = soup.select('div:contains("£"), li:contains("£"), article:contains("£")')
                    
                    for product in products_found[:max_results]:
                        try:
                            # Extract product name
                            name_selectors = [
                                '.product-title', '.product-name', 'h2', 'h3', 'h4',
                                '.title', '.name', 'a[href*="product"]'
                            ]
                            
                            product_name = None
                            for name_sel in name_selectors:
                                name_elem = product.select_one(name_sel)
                                if name_elem:
                                    product_name = name_elem.get_text(strip=True)
                                    break
                            
                            if not product_name:
                                continue
                            
                            # Extract price
                            price_selectors = [
                                '.price', '.product-price', '.cost', '.amount',
                                '[class*="price"]', '[data-price]'
                            ]
                            
                            price = None
                            for price_sel in price_selectors:
                                price_elem = product.select_one(price_sel)
                                if price_elem:
                                    price = clean_price(price_elem.get_text(strip=True))
                                    if price:
                                        break
                            
                            # Extract product URL
                            product_url = supplier['website']
                            link_elem = product.select_one('a[href]')
                            if link_elem:
                                href = link_elem.get('href')
                                if href:
                                    product_url = urljoin(supplier['website'], href)
                            
                            # Extract image
                            image_url = ""
                            img_elem = product.select_one('img')
                            if img_elem:
                                img_src = img_elem.get('src') or img_elem.get('data-src')
                                if img_src:
                                    image_url = urljoin(supplier['website'], img_src)
                            
                            if product_name and price:
                                result = {
                                    "supplier": supplier['name'],
                                    "price": f"£{price:.2f}",
                                    "price_numeric": price,
                                    "product_name": product_name,
                                    "category": "Building Materials",
                                    "supplier_website": supplier['website'],
                                    "product_url": product_url,
                                    "product_image": image_url,
                                    "availability": "Check with supplier",
                                    "delivery": supplier['delivery'],
                                    "contact": "See website",
                                    "rating": "N/A"
                                }
                                results.append(result)
                        
                        except Exception as e:
                            print(f"Error parsing product from {supplier['name']}: {e}")
                            continue
                    
                    if results:
                        break  # Found results, no need to try other search patterns
                        
            except Exception as e:
                print(f"Error searching {supplier['name']} with pattern: {e}")
                continue
        
        print(f"✅ Found {len(results)} products from {supplier['name']}")
        return results
        
    except Exception as e:
        print(f"❌ Error searching {supplier['name']}: {e}")
        return []

def search_all_suppliers(query, max_results_per_supplier=3):
    """Search all suppliers concurrently"""
    all_results = []
    
    print(f"🔍 Starting live search across {len(SUPPLIERS)} suppliers for: {query}")
    
    # Use ThreadPoolExecutor for concurrent searches
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        # Submit search tasks for all suppliers
        future_to_supplier = {
            executor.submit(search_supplier_website, supplier, query, max_results_per_supplier): supplier 
            for supplier in SUPPLIERS
        }
        
        # Collect results as they complete
        for future in concurrent.futures.as_completed(future_to_supplier, timeout=30):
            supplier = future_to_supplier[future]
            try:
                supplier_results = future.result()
                all_results.extend(supplier_results)
            except Exception as e:
                print(f"❌ {supplier['name']} search failed: {e}")
    
    # Sort by price (cheapest first)
    all_results.sort(key=lambda x: x.get('price_numeric', float('inf')))
    
    print(f"✅ Live search completed. Found {len(all_results)} total products")
    return all_results

@app.route('/')
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "Live Supplier Search API",
        "version": "3.0 - Live Search",
        "suppliers": len(SUPPLIERS),
        "search_type": "live_web_scraping",
        "supplier_list": [s['name'] for s in SUPPLIERS]
    })

@app.route('/api/search', methods=['POST'])
def search():
    """Live supplier search endpoint"""
    try:
        data = request.get_json()
        query = data.get('query', '').strip()
        max_results = min(data.get('max_results', 10), 20)
        
        if not query:
            return jsonify({"error": "Query parameter is required"}), 400
        
        print(f"🔍 Live supplier search query: {query}")
        
        # Perform live search across all suppliers
        results = search_all_suppliers(query, max_results_per_supplier=3)
        
        # Limit total results
        results = results[:max_results]
        
        if not results:
            return jsonify({
                "query": query,
                "results": [],
                "total_results": 0,
                "search_type": "live_supplier_search",
                "message": "No products found across supplier websites. Try different keywords.",
                "searched_suppliers": [s['name'] for s in SUPPLIERS]
            })
        
        response = {
            "query": query,
            "results": results,
            "total_results": len(results),
            "search_type": "live_supplier_search",
            "message": f"Found {len(results)} products from live supplier search",
            "searched_suppliers": list(set([r['supplier'] for r in results])),
            "search_time": "Real-time"
        }
        
        return jsonify(response)
        
    except Exception as e:
        print(f"❌ Search error: {e}")
        return jsonify({
            "error": "Search failed",
            "message": str(e),
            "search_type": "live_supplier_search"
        }), 500

@app.route('/api/search/demo', methods=['GET'])
def demo():
    """Demo endpoint"""
    return jsonify({
        "query": "demo search",
        "message": "This is the live supplier search API. Use POST /api/search with a query to search across real supplier websites.",
        "suppliers": [s['name'] for s in SUPPLIERS],
        "search_type": "live_supplier_search"
    })

@app.route('/api/suppliers', methods=['GET'])
def get_suppliers():
    """Get available suppliers"""
    return jsonify({
        "suppliers": SUPPLIERS,
        "total_suppliers": len(SUPPLIERS),
        "search_type": "live_web_scraping"
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

