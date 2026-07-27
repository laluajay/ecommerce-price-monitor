from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('add/', views.add_tracker_view, name='add_tracker'),
    path('delete/<int:item_id>/', views.delete_tracker_view, name='delete_tracker'),
    path('edit/<int:item_id>/', views.edit_tracker_view, name='edit_tracker'),
    path('register/', views.register_view, name='register'),
    path('activate/<str:uidb64>/<str:token>/', views.activate_view, name='activate'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    # Add your product status API path if needed:
    path('api/status/<int:product_id>/', views.get_product_status, name='product_status'),
]