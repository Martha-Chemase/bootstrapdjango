import json
import logging
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.db import transaction
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from myapp.forms import CheckoutForm, ContactForm, SignUpForm, StoreAuthenticationForm
from myapp.models import Order, OrderItem, Product
from myapp.payments import PayPalError, paypal_request


logger = logging.getLogger(__name__)
CENT = Decimal("0.01")


def _paypal_configured():
    return bool(settings.PAYPAL_CLIENT_ID and settings.PAYPAL_CLIENT_SECRET)


def _cart_summary(request):
    session_cart = request.session.get("cart", {})
    products = {str(product.pk): product for product in Product.objects.filter(is_active=True)}
    items = []
    subtotal = Decimal("0.00")
    normalized_cart = {}

    for product_id, raw_quantity in session_cart.items():
        product = products.get(str(product_id))
        try:
            quantity = int(raw_quantity)
        except (TypeError, ValueError):
            quantity = 0

        if product is None or quantity < 1:
            continue

        quantity = min(quantity, 99)
        normalized_cart[str(product.pk)] = quantity
        line_total = product.price_kes * quantity
        subtotal += line_total
        items.append({
            "product": product,
            "quantity": quantity,
            "line_total": line_total,
        })

    if normalized_cart != session_cart:
        request.session["cart"] = normalized_cart

    return items, subtotal.quantize(CENT)


def _base_context(request):
    items, _subtotal = _cart_summary(request)
    return {
        "cart_count": sum(item["quantity"] for item in items),
        "shop_contact_email": settings.SHOP_CONTACT_EMAIL,
        "shop_contact_phone": settings.SHOP_CONTACT_PHONE,
        "shop_socials": settings.SHOP_SOCIALS,
        "shop_location": settings.SHOP_LOCATION,
    }


def index(request):
    contact_form = ContactForm(request.POST if request.method == "POST" else None)
    if request.method == "POST":
        if contact_form.is_valid():
            contact_form.save()
            messages.success(request, "Thanks for your message. The Meine team will get back to you.")
            return redirect(f"{reverse('index')}#contact")
        messages.error(request, "Please check the contact form and try again.")

    context = _base_context(request)
    context.update({
        "products": Product.objects.filter(is_active=True),
        "contact_form": contact_form,
        "team": [
            {
                "name": "Customer care",
                "role": "Here to help you find your fit",
                "image": "assets/img/team/team_1.jpg",
            },
            {
                "name": "Style desk",
                "role": "Ideas for wearing and layering",
                "image": "assets/img/team/team_2.jpg",
            },
            {
                "name": "Orders & gifting",
                "role": "A thoughtful touch for every order",
                "image": "assets/img/team/team_3.jpg",
            },
        ],
    })
    return render(request, "index.html", context)


class StoreLoginView(LoginView):
    template_name = "registration/login.html"
    authentication_form = StoreAuthenticationForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(_base_context(self.request))
        return context


def signup(request):
    if request.user.is_authenticated:
        return redirect("index")
    form = SignUpForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Your account is ready. Welcome to Meine!")
        next_url = request.GET.get("next", "")
        if url_has_allowed_host_and_scheme(
            next_url,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            return redirect(next_url)
        return redirect("index")
    context = _base_context(request)
    context["form"] = form
    return render(request, "registration/signup.html", context)


@login_required
def account_dashboard(request):
    context = _base_context(request)
    context["orders"] = request.user.orders.prefetch_related("items")
    return render(request, "registration/account.html", context)


class StoreLogoutView(LogoutView):
    http_method_names = ["post", "options"]
    next_page = "index"


def cart(request):
    items, subtotal = _cart_summary(request)
    context = _base_context(request)
    context.update({"items": items, "subtotal": subtotal})
    return render(request, "shop/cart.html", context)


@require_POST
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, pk=product_id, is_active=True)
    try:
        quantity = int(request.POST.get("quantity", "1"))
    except (TypeError, ValueError):
        return HttpResponseBadRequest("Quantity must be a whole number.")
    if not 1 <= quantity <= 99:
        return HttpResponseBadRequest("Quantity must be between 1 and 99.")

    session_cart = request.session.get("cart", {})
    key = str(product.pk)
    session_cart[key] = min(int(session_cart.get(key, 0)) + quantity, 99)
    request.session["cart"] = session_cart
    messages.success(request, f"{product.name} added to your cart.")
    next_url = request.POST.get("next", "")
    if url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(next_url)
    return redirect("index")


@require_POST
def update_cart(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    try:
        quantity = int(request.POST.get("quantity", ""))
    except (TypeError, ValueError):
        return HttpResponseBadRequest("Quantity must be a whole number.")

    session_cart = request.session.get("cart", {})
    if str(product.pk) not in session_cart:
        return HttpResponseBadRequest("That product is not in your cart.")
    if quantity <= 0:
        session_cart.pop(str(product.pk))
    elif quantity <= 99:
        session_cart[str(product.pk)] = quantity
    else:
        return HttpResponseBadRequest("Quantity cannot be more than 99.")
    request.session["cart"] = session_cart
    return redirect("cart")


@login_required
def checkout(request):
    items, subtotal = _cart_summary(request)
    if not items:
        messages.info(request, "Your cart is empty. Add a piece from the collection to begin checkout.")
        return redirect("index")

    delivery = Decimal(settings.SHOP_DELIVERY_FEE_KES).quantize(CENT)
    total = subtotal + delivery
    exchange_rate = Decimal(settings.PAYPAL_KES_PER_USD)
    if exchange_rate <= 0:
        raise ValueError("PAYPAL_KES_PER_USD must be greater than zero.")
    paypal_total = (total / exchange_rate).quantize(CENT, rounding=ROUND_HALF_UP)

    initial = {
        "full_name": request.user.get_full_name() or request.user.username,
        "email": request.user.email,
        "city": settings.SHOP_DEFAULT_CITY,
        "county": settings.SHOP_DEFAULT_COUNTY,
    }
    form = CheckoutForm(
        request.POST if request.method == "POST" else None,
        initial=initial,
    )
    if request.method == "POST":
        if form.is_valid():
            with transaction.atomic():
                order = Order.objects.create(
                    user=request.user,
                    subtotal_kes=subtotal,
                    delivery_kes=delivery,
                    total_kes=total,
                    paypal_kes_per_usd=exchange_rate,
                    paypal_total_usd=paypal_total,
                    **form.cleaned_data,
                )
                OrderItem.objects.bulk_create([
                    OrderItem(
                        order=order,
                        product=item["product"],
                        product_name=item["product"].name,
                        unit_price_kes=item["product"].price_kes,
                        quantity=item["quantity"],
                    )
                    for item in items
                ])
            return redirect("order_payment", order_id=order.pk)
        messages.error(request, "Please check your delivery details and try again.")

    context = _base_context(request)
    context.update({
        "items": items,
        "subtotal": subtotal,
        "delivery": delivery,
        "total": total,
        "paypal_total": paypal_total,
        "paypal_rate": exchange_rate,
        "paypal_mode": settings.PAYPAL_MODE,
        "form": form,
    })
    return render(request, "shop/checkout.html", context)


@login_required
def order_payment(request, order_id):
    order = get_object_or_404(Order, pk=order_id, user=request.user)
    context = _base_context(request)
    context.update({
        "order": order,
        "paypal_configured": _paypal_configured(),
        "paypal_client_id": settings.PAYPAL_CLIENT_ID,
        "paypal_currency": "USD",
        "paypal_mode": settings.PAYPAL_MODE,
    })
    return render(request, "shop/order_payment.html", context)


@login_required
@require_POST
def create_paypal_order(request, order_id):
    order = get_object_or_404(Order, pk=order_id, user=request.user)
    if order.status == Order.Status.PAID:
        return JsonResponse({"error": "This order has already been paid."}, status=400)
    if not _paypal_configured():
        return JsonResponse({"error": "PayPal sandbox credentials are not configured."}, status=503)
    if order.paypal_order_id:
        return JsonResponse({"orderID": order.paypal_order_id})

    payload = {
        "intent": "CAPTURE",
        "purchase_units": [{
            "reference_id": str(order.pk),
            "custom_id": str(order.pk),
            "description": f"Meine Accessories order {order.pk}",
            "amount": {"currency_code": "USD", "value": f"{order.paypal_total_usd:.2f}"},
        }],
    }
    try:
        result = paypal_request(
            "POST",
            "/v2/checkout/orders",
            payload=payload,
            request_id=f"create-order-{order.pk}",
        )
    except PayPalError as error:
        return JsonResponse({"error": str(error)}, status=502)

    paypal_order_id = result.get("id")
    if not paypal_order_id:
        logger.error("PayPal create-order response did not contain an order ID: %r", result)
        return JsonResponse({"error": "PayPal did not create an order. Please try again."}, status=502)
    order.paypal_order_id = paypal_order_id
    order.save(update_fields=["paypal_order_id"])
    return JsonResponse({"orderID": paypal_order_id})


@login_required
@require_POST
def capture_paypal_order(request, order_id):
    order = get_object_or_404(Order, pk=order_id, user=request.user)
    if order.status == Order.Status.PAID:
        return JsonResponse({"status": "paid", "redirect": reverse("order_success", args=[order.pk])})
    if not order.paypal_order_id:
        return JsonResponse({"error": "Create a PayPal order before capturing payment."}, status=400)

    try:
        submitted = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({"error": "Invalid payment response."}, status=400)
    if not isinstance(submitted, dict):
        return JsonResponse({"error": "Invalid payment response."}, status=400)
    submitted_order_id = submitted.get("orderID")
    if submitted_order_id != order.paypal_order_id:
        return JsonResponse({"error": "The PayPal order does not match this checkout."}, status=400)

    try:
        result = paypal_request(
            "POST",
            f"/v2/checkout/orders/{order.paypal_order_id}/capture",
            payload={},
            request_id=f"capture-order-{order.pk}",
        )
    except PayPalError as error:
        return JsonResponse({"error": str(error)}, status=502)

    purchase_units = result.get("purchase_units", [])
    captures = (
        purchase_units[0].get("payments", {}).get("captures", [])
        if purchase_units else []
    )
    if result.get("status") != "COMPLETED" or not captures:
        return JsonResponse({"error": "PayPal has not confirmed this payment."}, status=402)

    capture = captures[0]
    captured_amount = capture.get("amount", {})
    try:
        captured_value = Decimal(captured_amount.get("value", "0"))
    except (InvalidOperation, TypeError):
        captured_value = Decimal("0")
    if (
        capture.get("status") != "COMPLETED"
        or captured_amount.get("currency_code") != "USD"
        or captured_value != order.paypal_total_usd
        or purchase_units[0].get("reference_id") != str(order.pk)
    ):
        logger.error("PayPal capture details did not match order %s.", order.pk)
        return JsonResponse({"error": "The confirmed payment did not match this order."}, status=400)

    order.status = Order.Status.PAID
    order.save(update_fields=["status"])
    cart_items = request.session.get("cart", {})
    for item in order.items.all():
        key = str(item.product_id)
        remaining_quantity = int(cart_items.get(key, 0)) - item.quantity
        if remaining_quantity > 0:
            cart_items[key] = remaining_quantity
        else:
            cart_items.pop(key, None)
    request.session["cart"] = cart_items
    return JsonResponse({
        "status": "paid",
        "redirect": reverse("order_success", args=[order.pk]),
    })


@login_required
def order_success(request, order_id):
    order = get_object_or_404(Order, pk=order_id, user=request.user)
    if order.status != Order.Status.PAID:
        return redirect("order_payment", order_id=order.pk)
    context = _base_context(request)
    context["order"] = order
    return render(request, "shop/order_success.html", context)
