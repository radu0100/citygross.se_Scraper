from datetime import datetime
from dateutil import parser
import csv
import pytz
import requests
import re
import time

# Headers for the HTTP request
headers = {
    'authority': 'www.citygross.se',
    'Accept': 'application/json',
    'Accept-Language': 'ro-RO,ro;q=0.9,en-US;q=0.8,en;q=0.7',
    'Cookie': 'CookieConsent={stamp:%27Ft3p7o83LhvhUKS17FxppRGLV347+aj+TKBvILnw48R1Zg78LuVPIQ==%27%2Cnecessary:true'
              '%2Cpreferences:true%2Cstatistics:true%2Cmarketing:true%2Cmethod:%27explicit%27%2Cver:1%2Cutc'
              ':1708426692129%2Cregion:%27ro%27}; _gcl_au=1.1.2127162353.1708426694; '
              '_fbp=fb.1.1708426701595.468333489; imbox={"imboxUid":"2cd1aSWjmWO5QzEXzJDDzi4txNy"}; '
              '_hjSessionUser_1254138'
              '=eyJpZCI6IjVlM2QzOGY4LTcwZTktNWU4ZS05M2ZmLWJmNDgzZTExMmNmYyIsImNyZWF0ZWQiOjE3MDg0MjY2OTkxMjIsImV4aXN0aW5nIjp0cnVlfQ==; _tt_enable_cookie=1; _ttp=bWwhiVRNh4l7CwvtMsRXfMIYqH3; _pin_unauth=dWlkPU56TmlNbU14WmpNdFpUQXdZaTAwWWpZeUxXRmhZMll0TUdOalpUWmxaRGN3WTJReg; _gid=GA1.2.466555441.1708608575; _ga=GA1.2.815106290.1708426696; _uetsid=6b7089e0d18611ee8be061b30910c76b; _uetvid=f3e671b0cfde11ee84c617e5576287a2; _ga_CT371S5MF9=GS1.1.1708952411.16.0.1708952411.60.0.0; e_sk=8ac088c6-065d-432d-a777-a21181d0006e',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
}

# Fetching the navigation data from the website
response = requests.get("https://www.citygross.se/api/v1/navigation", headers=headers)
data = response.text

# Regex pattern to extract category IDs from the navigation data
pattern = r'id" *: *[^,]+.+?type" *: *"ProductCategoryPage'
x = re.findall(pattern, data)

# Extracting IDs from the matched patterns
id_pattern = r'(?<=id":)[^,]+'
id_pattern2 = r'(?<=id":")[^"]+'
ids = [re.search(id_pattern, match).group() for match in x if re.search(id_pattern, match)]

# Selecting the first 4 category IDs for scraping
first_X_ids = ids[:4]  # Please change the number based on how many urls you want to scrape
full_urls = []
delay_seconds = 3
responses_with_products = []

# Base URL for fetching product data
baseurl2 = 'https://www.citygross.se/api/v1/esales/products?categoryId='

# Building full URLs for each category ID
for extracted_ids in first_X_ids:
    full_urls.append(baseurl2 + extracted_ids + '&page=0&size=24&store')

# Pattern to identify product ID strings within network responses
network_response_productsIds_pattern = r'"id":"[^"]+".{1,100}"gtin'

# Fetching product data for each category
for category_id in first_X_ids:
    page = 0
    while True:
        full_url = f"{baseurl2}{category_id}&page={page}&size=24&store"
        response = requests.get(full_url, headers=headers)
        print(f"Making request to {full_url}...")
        if response.status_code == 200:
            response_json = response.json()
            product_data = response_json.get('data', [])
            if not product_data:
                print("No more products found.")
                break
            responses_with_products.extend(product_data)
        else:
            print(f"Failed to retrieve data from {full_url}. Status code: {response.status_code}")
            break
        page += 1
        time.sleep(delay_seconds)

# Fetching detailed product data using product IDs
for i, full_url in enumerate(full_urls):
    response = requests.get(full_url, headers=headers)
    print(f"Making request to {full_url}...")
    if response.status_code == 200:
        print(f"Response extracted {i + 1}")
        search_results = re.findall(network_response_productsIds_pattern, response.text)
        product_ids = [re.search(id_pattern2, match).group() for match in search_results if re.search(id_pattern2, match)]
        for product_id in product_ids:
            response = requests.get('https://www.citygross.se/api/v1/esales/pdp/' + product_id + '/product', headers=headers)
            product_data = response.json()
            if isinstance(product_data, list):
                responses_with_products.extend(product_data)
            else:
                responses_with_products.append(product_data)
    else:
        pass
        # print(f"Failed to retrieve data from {full_url}. Status code: {response.status_code}")

    time.sleep(delay_seconds)

# Current date for promotion validation
current_date = datetime.now(pytz.timezone('Europe/Stockholm'))
csv_headers = ["Product name", "Brand", "GTIN", "Ordinary Price", "Active Promotion Price", "Min Quantity", "Total for x items"]

# Set to keep track of unique product signatures to avoid duplicates
unique_product_signatures = set()

# Writing collected product data to a CSV file
with open('../products_data.csv', mode='w', newline='', encoding='utf-8-sig') as file:
    writer = csv.DictWriter(file, fieldnames=csv_headers)
    writer.writeheader()

    for product_data in responses_with_products:
        if isinstance(product_data, dict):
            # Creating a unique signature for each product based on specific attributes
            product_signature = (
                product_data.get('name', 'N/A'),
                product_data.get('brand', 'N/A'),
                product_data.get('gtin', 'N/A'),
                product_data.get('prices', [{}])[0].get('ordinaryPrice', {}).get('price', 'N/A'),
            )

            # Skipping duplicate products based on their signature
            if product_signature in unique_product_signatures:
                continue

            unique_product_signatures.add(product_signature)

            # Collecting product info, including checking for active promotions
            product_info = {
                "Product name": product_signature[0],
                "Brand": product_signature[1],
                "GTIN": f"=\"{product_signature[2]}\"",
                "Ordinary Price": product_signature[3],
                "Active Promotion Price": 'N/A',
                "Min Quantity": 'N/A',
                "Total for x items": 'N/A'
            }

            # Processing promotions to find active ones
            promotions = product_data.get('prices', [{}])[0].get('promotions', [])
            for promo in promotions:
                if promo.get('from') is not None and promo.get('to') is not None:
                    promo_start = parser.parse(promo['from'])
                    promo_end = parser.parse(promo['to'])
                    if promo_start <= current_date <= promo_end:
                        product_info["Active Promotion Price"] = str(promo.get('priceDetails', {}).get('price', 'N/A'))
                        product_info["Min Quantity"] = str(promo.get('minQuantity', 'N/A'))
                        if product_info["Min Quantity"].isdigit():
                            min_quantity = int(product_info["Min Quantity"])
                            if min_quantity > 1:
                                total_promotion_price = float(product_info["Active Promotion Price"]) * min_quantity
                                product_info["Total for x items"] = str(round(total_promotion_price, 2))
                            else:
                                product_info["Total for x items"] = product_info["Active Promotion Price"]
                        break

            writer.writerow(product_info)

            # Uncomment the following lines if you want to see the results in the console
            # print(f"Product name: {product_info['Product name']}")
            # print(f"Brand: {product_info['Brand']}")
            # print(f"GTIN: {product_info['GTIN']}")
            # print(f"Ordinary Price: {product_info['Ordinary Price']}")
            # print(f"Active Promotion Price: {product_info['Active Promotion Price']}")
            # print(f"Min Quantity: {product_info['Min Quantity']}")
            # print(f"Total for {product_info['Min Quantity']} items: {product_info['Total for x items']}")
            # print()

print("Data saved to products_data.csv.")
