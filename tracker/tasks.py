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

        # Update product title if it's default "New Product" or empty
        if product.name == "New Product" or not product.name:
            title = None
            if "amazon" in product.url.lower():
                title_el = soup.find(id="productTitle")
                if title_el:
                    title = title_el.text.strip()
            elif "flipkart" in product.url.lower():
                title_el = soup.find(class_="B_NuCI") or soup.find(class_="VU-ZEz")
                if title_el:
                    title = title_el.text.strip()
            
            if not title:
                title_el = soup.find('title')
                if title_el:
                    title = title_el.text.strip()
            
            if title:
                # Normalize spaces and truncate if too long
                title = re.sub(r'\s+', ' ', title).strip()[:255]
                product.name = title
                product.save()

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

        # Update current price in DB if it changed
        price_changed = (product.current_price != new_price)
        if price_changed:
            product.current_price = new_price
            product.save()

        # Find all trackers for this product where target price is met
        alerts = TrackedItem.objects.filter(product=product, target_price__gte=new_price)
        sent_alerts_count = 0

        for alert in alerts:
            # Send alert if never notified before, OR if the price is lower than the last notified price
            if alert.last_notified_price is None or new_price < alert.last_notified_price:
                user_email = alert.user.email
                if user_email:
                    subject = f"🎯 Target Met: {product.name}"
                    message = (
                        f"Good news! The price of {product.name} has hit your target of ₹{alert.target_price}.\n"
                        f"Current Price: ₹{new_price}\n\n"
                        f"Buy it here: {product.url}"
                    )
                    send_mail(subject, message, settings.EMAIL_HOST_USER, [user_email], fail_silently=False)
                    sent_alerts_count += 1
                
                # Update last notified price to prevent duplicate emails
                alert.last_notified_price = new_price
                alert.save()
            
        if price_changed or sent_alerts_count > 0:
            return f"Updated {product.name} to {new_price} and sent {sent_alerts_count} alerts."
            
        return f"Checked {product.name}. Price remained {new_price}."

    except Product.DoesNotExist:
        return "Error: Product not found."
    except Exception as e:
        return f"An unexpected error occurred: {str(e)}"