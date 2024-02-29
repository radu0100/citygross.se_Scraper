from datetime import datetime
from dateutil import parser
import csv
import pytz
import requests
import re
import time


class CityGrossScraper:
    def __init__(self):
        self.headers = {    # HTTP headers to mimic a browser request
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
        self.base_url = 'https://www.citygross.se/api/v1/esales/products?categoryId='
        self.delay_seconds = 3  # Delay between requests to avoid overwhelming the server
        self.responses_with_products = []  # Store fetched product data
        self.unique_product_signatures = set()  # Track unique products to avoid duplicates
        self.current_date = datetime.now(pytz.timezone('Europe/Stockholm'))  # Current date for promotion validation
        # CSV headers for the output file
        self.csv_headers = ["Product name", "Brand", "GTIN", "Ordinary Price", "Active Promotion Price", "Min Quantity", "Total for x items"]

    def fetch_navigation(self):  # Fetch navigation data to find category IDs
        response = requests.get("https://www.citygross.se/api/v1/navigation", headers=self.headers)
        data = response.text
        return data

    @staticmethod   # Static method to extract category IDs from the navigation data
    def extract_category_ids(data):
        pattern = r'id" *: *[^,]+.+?type" *: *"ProductCategoryPage'  # Regular expression patterns to find category IDs
        matches = re.findall(pattern, data)
        id_pattern = r'(?<=id":)[^,]+'
        ids = [re.search(id_pattern, match).group() for match in matches if re.search(id_pattern, match)]
        return ids[:4]  # Return the first 4 category IDs, you can change this or remove it to slice all the available ids, there are over 1600 of them

    def fetch_product_data(self, category_ids):  # Fetch product data for each category
        for category_id in category_ids:
            page = 0
            while True:
                full_url = f"{self.base_url}{category_id}&page={page}&size=24&store"
                response = requests.get(full_url, headers=self.headers)
                print(f"Making request to {full_url}...")
                if response.status_code == 200:
                    response_json = response.json()
                    product_data = response_json.get('data', [])
                    if not product_data:
                        print("No more products found.")
                        break   # No more products found, exit the loop
                    self.responses_with_products.extend(product_data)   # Add fetched data to the list
                else:
                    print(f"Failed to retrieve data from {full_url}. Status code: {response.status_code}")
                    break
                page += 1
                time.sleep(self.delay_seconds)  # Delay to prevent server overload

    def save_to_csv(self, filename='products_data.csv'):    # Save the collected data into a CSV file
        with open(filename, mode='w', newline='', encoding='utf-8-sig') as file:
            writer = csv.DictWriter(file, fieldnames=self.csv_headers)
            writer.writeheader()

            for product_data in self.responses_with_products:
                if isinstance(product_data, dict):  # Ensure the data is a dictionary
                    product_signature = (
                        product_data.get('name', 'N/A'),
                        product_data.get('brand', 'N/A'),
                        product_data.get('gtin', 'N/A'),
                        product_data.get('prices', [{}])[0].get('ordinaryPrice', {}).get('price', 'N/A'),
                    )

                    if product_signature in self.unique_product_signatures:
                        continue    # Skip duplicate products

                    self.unique_product_signatures.add(product_signature)   # Mark product as processed

                    product_info = self.prepare_product_info(product_data, product_signature)   # Write product info to the CSV
                    writer.writerow(product_info)

    def prepare_product_info(self, product_data, product_signature):     # Prepare product information for CSV writing, including promotion checks
        product_info = {     # Basic product information and handling promotions
            "Product name": product_signature[0],
            "Brand": product_signature[1],
            "GTIN": f"=\"{product_signature[2]}\"",
            "Ordinary Price": product_signature[3],
            "Active Promotion Price": 'N/A',
            "Min Quantity": 'N/A',
            "Total for x items": 'N/A'
        }

        promotions = product_data.get('prices', [{}])[0].get('promotions', [])
        for promo in promotions:
            if promo.get('from') is not None and promo.get('to') is not None:   # Ensure promotion has start and end dates
                promo_start = parser.parse(promo['from'])
                promo_end = parser.parse(promo['to'])
                if promo_start <= self.current_date <= promo_end:   # If current date is within the promotion period, update the product info
                    product_info["Active Promotion Price"] = str(promo.get('priceDetails', {}).get('price', 'N/A'))
                    product_info["Min Quantity"] = str(promo.get('minQuantity', 'N/A'))  # Calculate total price for promotions requiring purchase of multiple items
                    if product_info["Min Quantity"].isdigit():
                        min_quantity = int(product_info["Min Quantity"])
                        if min_quantity > 1:
                            total_promotion_price = float(product_info["Active Promotion Price"]) * min_quantity
                            product_info["Total for x items"] = str(round(total_promotion_price, 2))
                        else:
                            product_info["Total for x items"] = product_info["Active Promotion Price"]
                    break   # Exit after processing the first applicable promotion
        return product_info

    def run(self):  # Main method to run the scraper
        data = self.fetch_navigation()  # Fetch navigation data
        category_ids = self.extract_category_ids(data)  # Extract category IDs
        self.fetch_product_data(category_ids)    # Fetch product data
        self.save_to_csv()   # Save data to CSV


if __name__ == "__main__":
    scraper = CityGrossScraper()
    scraper.run()
