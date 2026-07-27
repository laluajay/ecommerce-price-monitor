from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .forms import CustomUserCreationForm
from .models import Product, TrackedItem
from .tasks import update_product_price
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.sites.shortcuts import get_current_site
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.core.mail import send_mail
from django.conf import settings
from .tokens import account_activation_token


# --- 1. Main View (Landing Page or Dashboard) ---
def index(request):
    if request.user.is_authenticated:
        # Fetch all items tracked by the currently logged-in user
        user_items = TrackedItem.objects.filter(user=request.user).order_by('-created_at')
        return render(request, "tracker/index.html", {"items": user_items})
    else:
        # Show guest landing page
        return render(request, "tracker/landing.html")

# --- 2. Add Tracker (Handles form submissions) ---
@login_required(login_url='/login/')
def add_tracker_view(request):
    if request.method == "POST":
        url = request.POST.get("url")
        target_price = request.POST.get("target_price")

        if not url or not target_price:
            return redirect("index")

        # Get or create the product
        product, created = Product.objects.get_or_create(url=url)
        if created:
            product.name = "New Product" # Celery task will fetch the title asynchronously
            product.save()

        # Link product to user with their specific target price, updating if already existing
        tracked_item, item_created = TrackedItem.objects.get_or_create(
            user=request.user,
            product=product,
            defaults={'target_price': float(target_price)}
        )
        if not item_created:
            tracked_item.target_price = float(target_price)
            tracked_item.save()

        # Trigger the Celery background task for this specific product
        update_product_price.delay(product.id)
        return redirect("index")
    
    return redirect("index")

# --- 3. Delete Tracker ---
@login_required(login_url='/login/')
def delete_tracker_view(request, item_id):
    tracked_item = get_object_or_404(TrackedItem, id=item_id, user=request.user)
    tracked_item.delete()
    return redirect("index")

# --- 4. Edit Tracker Target Price ---
@login_required(login_url='/login/')
def edit_tracker_view(request, item_id):
    if request.method == "POST":
        target_price = request.POST.get("target_price")
        if target_price:
            tracked_item = get_object_or_404(TrackedItem, id=item_id, user=request.user)
            tracked_item.target_price = float(target_price)
            tracked_item.save()
    return redirect("index")

# --- 5. API View (For Real-time UI updates) ---
def get_product_status(request, product_id):
    try:
        product = Product.objects.get(id=product_id)
        return JsonResponse({
            'current_price': str(product.current_price) if product.current_price else None,
            'name': product.name
        })
    except Product.DoesNotExist:
        return JsonResponse({'error': 'Product not found'}, status=404)

# --- 6. Auth Views ---
def register_view(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False # Deactivate account until email verification
            user.save()
            
            # Send activation email
            current_site = get_current_site(request)
            subject = 'Activate your Price Sniper Account'
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = account_activation_token.make_token(user)
            activation_link = f"http://{current_site.domain}/activate/{uid}/{token}/"
            
            message = (
                f"Hi {user.username},\n\n"
                f"Please click on the link below to verify your email address and activate your account:\n\n"
                f"{activation_link}\n\n"
                f"Thank you,\nPrice Sniper Team"
            )
            
            send_mail(
                subject,
                message,
                settings.EMAIL_HOST_USER,
                [user.email],
                fail_silently=False
            )
            return render(request, 'tracker/register.html', {
                'success': 'Please confirm your email address to complete the registration. Check your inbox!'
            })
    else:
        form = CustomUserCreationForm()
    return render(request, 'tracker/register.html', {'form': form})


def activate_view(request, uidb64, token):
    User = get_user_model()
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and account_activation_token.check_token(user, token):
        user.is_active = True
        user.save()
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        return redirect('index')
    else:
        return render(request, 'tracker/register.html', {
            'error': 'The activation link is invalid or has expired.'
        })

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