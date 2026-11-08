from django.urls import path
from myapp import views

urlpatterns = [
    path('', views.index, name='index'),
    path('accounts/login/', views.StoreLoginView.as_view(), name='login'),
    path('accounts/signup/', views.signup, name='signup'),
    path('accounts/', views.account_dashboard, name='account'),
    path('accounts/logout/', views.StoreLogoutView.as_view(), name='logout'),
    path('cart/', views.cart, name='cart'),
    path('cart/add/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/update/<int:product_id>/', views.update_cart, name='update_cart'),
    path('checkout/', views.checkout, name='checkout'),
    path('orders/<int:order_id>/payment/', views.order_payment, name='order_payment'),
    path('orders/<int:order_id>/success/', views.order_success, name='order_success'),
    path('orders/<int:order_id>/paypal/create/', views.create_paypal_order, name='create_paypal_order'),
    path('orders/<int:order_id>/paypal/capture/', views.capture_paypal_order, name='capture_paypal_order'),
]