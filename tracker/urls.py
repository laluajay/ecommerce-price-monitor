from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('add/', views.add_tracker_view, name='add_tracker'),
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    # Add your product status API path if needed:
    path('api/status/<int:product_id>/', views.get_product_status, name='product_status'),
]