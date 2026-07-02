from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from .models import Product, TrackedItem
import cloudscraper
from bs4 import BeautifulSoup
import re
import json

@shared_task
def update_all_prices():
    """Coordinator task: Triggers individual updates for all products."""
    products = Product.objects.all()
    for product in products:
        update_product_price.delay(product.id)

@shared_task
def update_product_price(product_id):
    """Worker task: Scrapes a single product and sends alerts if needed."""
    try:
        product = Product.objects.get(id=product_id)
        
        scraper = cloudscraper.create_scraper(
            browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
        )
        
        response = scraper.get(product.url)
        if response.status_code == 503:
            return f"Error: Hard-blocked (503) for {product.url}"

        soup = BeautifulSoup(response.content, 'html.parser')
        new_price = None

        # 1. THE JEDI SNIPER: Look for hidden Google SEO Data
        seo_scripts = soup.find_all('script', type='application/ld+json')
        for script in seo_scripts:
            if script.string:
                try:
                    data = json.loads(script.string)
                    if isinstance(data, list):
                        for item in data:
                            if item.get('@type') == 'Product' and 'offers' in item:
                                offers = item['offers']
                                new_price = float(offers[0]['price']) if isinstance(offers, list) else float(offers['price'])
                                break
                    elif data.get('@type') == 'Product' and 'offers' in data:
                        offers = data['offers']
                        new_price = float(offers[0]['price']) if isinstance(offers, list) else float(offers['price'])
                except Exception:
                    continue
            if new_price:
                break

        # 2. THE BACKUP: If SEO data fails, use site-specific selectors
        if not new_price:
            if "amazon" in product.url.lower():
                possible_classes = ["a-price-whole", "a-offscreen", "a-color-price", "apexPriceToPay"]
                for css_class in possible_classes:
                    price_element = soup.find(class_=css_class)
                    if price_element:
                        new_price = float(re.sub(r'[^\d.]', '', price_element.text))
                        break  
            elif "flipkart" in product.url.lower():
                possible_classes = ["Nx9bqj CxhGGd", "Nx9bqj", "_30jeq3 _16Jk6d", "_30jeq3"]
                for css_class in possible_classes:
                    price_element = soup.find('div', class_=css_class)
                    if price_element:
                        new_price = float(re.sub(r'[^\d.]', '', price_element.text))
                        break 

        # 3. LAST RESORT: Rupee Hunter (Grabs any valid price)
        if not new_price:
            rupee_texts = soup.find_all(string=re.compile(r'₹[0-9,]+'))
            found_prices = []
            for text in rupee_texts:
                clean_text = text.strip()
                if 0 < len(clean_text) < 15:
                    try:
                        found_prices.append(float(re.sub(r'[^\d.]', '', clean_text)))
                    except:
                        pass
            valid_prices = [p for p in found_prices if p > 100]
            if valid_prices:
                new_price = min(valid_prices) 

        # Final Validation
        if not new_price:
            page_title = soup.title.string if soup.title else "No Title Found"
            return f"Error: No price tag. Page Title: '{page_title}'"

        # Check for price changes and alert
        if product.current_price != new_price:
            product.current_price = new_price
            product.save()

            triggered_alerts = TrackedItem.objects.filter(
                product=product, 
                target_price__gte=new_price
            )
            
            for alert in triggered_alerts:
                user_email = alert.user.email
                if user_email:  
                    subject = f"Price Drop Alert: {product.name}"
                    message = f"Good news! The price of {product.name} has dropped to ₹{new_price}.\n\nBuy it here: {product.url}"
                    send_mail(subject, message, settings.EMAIL_HOST_USER, [user_email], fail_silently=False)
            
            return f"Updated {product.name} to {new_price} and sent {triggered_alerts.count()} alerts."
            
        return f"Checked {product.name}. Price remained {new_price}."

    except Product.DoesNotExist:
        return "Error: Product not found."
    except Exception as e:
        return f"An unexpected error occurred: {str(e)}"