from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib.auth.forms import UserCreationForm
from .models import Product, TrackedItem
from .tasks import update_product_price
from django.contrib.auth import authenticate, login, logout


# --- 1. Dashboard (The Main View) ---
@login_required(login_url='/login/')
def index(request):
    # Fetch all items tracked by the currently logged-in user
    user_items = TrackedItem.objects.filter(user=request.user)
    return render(request, "tracker/index.html", {"items": user_items})

# --- 2. Add Tracker (Handles form submissions) ---
@login_required(login_url='/login/')
def add_tracker_view(request):
    if request.method == "POST":
        url = request.POST.get("url")
        target_price = request.POST.get("target_price")

        # Get or create the product
        product, created = Product.objects.get_or_create(url=url)
        if created:
            product.name = "New Product" # Ideally, add logic to fetch the title
            product.save()

        # Link product to user with their specific target price
        TrackedItem.objects.get_or_create(
            user=request.user,
            product=product,
            defaults={'target_price': float(target_price)}
        )

        # Trigger the Celery background task for this specific product
        update_product_price.delay(product.id)
        return redirect("index")
    
    return render(request, 'tracker/add.html')

# --- 3. API View (For Real-time UI updates) ---
def get_product_status(request, product_id):
    try:
        product = Product.objects.get(id=product_id)
        return JsonResponse({
            'current_price': str(product.current_price) if product.current_price else None
        })
    except Product.DoesNotExist:
        return JsonResponse({'error': 'Product not found'}, status=404)

# --- 4. Auth Views ---
def register_view(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('index')
    else:
        form = UserCreationForm()
    return render(request, 'tracker/register.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        user = authenticate(
            username=request.POST.get('username'),
            password=request.POST.get('password')
        )
        if user is not None:
            login(request, user)
            return redirect('index')
        else:
            return render(request, 'tracker/login.html', {'error': 'Invalid credentials'})
    return render(request, 'tracker/login.html')


def logout_view(request):
    logout(request)
    return redirect('login') # This sends them back to the login page