import json
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from myapp.models import ContactMessage, Order, OrderItem, Product


class StorefrontTests(TestCase):
    def test_homepage_renders_all_seeded_products_and_team(self):
        response = self.client.get(reverse("index"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["products"]), 15)
        self.assertEqual(len(response.context["team"]), 3)
        self.assertContains(response, "Nairobi")

    def test_contact_form_saves_message(self):
        response = self.client.post(reverse("index"), {
            "name": "Amina",
            "email": "amina@example.com",
            "subject": "Gift question",
            "message": "Can you help me choose a gift?",
        })

        self.assertRedirects(response, f"{reverse('index')}#contact")
        self.assertEqual(ContactMessage.objects.count(), 1)

    def test_add_and_update_cart(self):
        product = Product.objects.get(slug="midnight-garden-drops")

        response = self.client.post(reverse("add_to_cart", args=[product.pk]))
        self.assertRedirects(response, reverse("index"))
        self.assertEqual(self.client.session["cart"], {str(product.pk): 1})

        response = self.client.post(reverse("update_cart", args=[product.pk]), {"quantity": 3})
        self.assertRedirects(response, reverse("cart"))
        self.assertEqual(self.client.session["cart"], {str(product.pk): 3})

    def test_add_to_cart_rejects_external_redirects(self):
        product = Product.objects.get(slug="midnight-garden-drops")

        response = self.client.post(
            reverse("add_to_cart", args=[product.pk]),
            {"next": "https://example.com"},
        )

        self.assertRedirects(response, reverse("index"))

    def test_guest_checkout_redirects_to_login(self):
        response = self.client.get(reverse("checkout"))

        self.assertRedirects(response, f"{reverse('login')}?next={reverse('checkout')}")

    def test_signup_creates_user_and_logs_them_in(self):
        response = self.client.post(reverse("signup"), {
            "username": "amina",
            "email": "amina@example.com",
            "password1": "A-strong-test-password-2026",
            "password2": "A-strong-test-password-2026",
        })

        self.assertRedirects(response, reverse("index"))
        self.assertTrue(get_user_model().objects.filter(username="amina").exists())
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_logout_returns_to_the_storefront(self):
        user = get_user_model().objects.create_user(
            username="logout-shopper",
            password="Strong-test-password-2026",
        )
        self.client.force_login(user)

        response = self.client.post(reverse("logout"))

        self.assertRedirects(response, reverse("index"))


class CheckoutTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="shopper",
            email="shopper@example.com",
            password="Strong-test-password-2026",
        )
        self.client.force_login(self.user)
        self.product = Product.objects.get(slug="midnight-garden-drops")
        session = self.client.session
        session["cart"] = {str(self.product.pk): 2}
        session.save()

    def test_account_shows_the_signed_in_users_orders(self):
        response = self.client.get(reverse("account"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Your orders")

    @override_settings(SHOP_DELIVERY_FEE_KES=Decimal("300.00"), PAYPAL_KES_PER_USD=Decimal("130.00"))
    def test_checkout_uses_catalog_prices_and_configured_currency_rate(self):
        response = self.client.post(reverse("checkout"), {
            "full_name": "Amina",
            "email": "amina@example.com",
            "phone": "+254700000000",
            "address": "Example Road",
            "city": "Nairobi",
            "county": "Nairobi",
        })

        order = Order.objects.get(user=self.user)
        self.assertRedirects(response, reverse("order_payment", args=[order.pk]))
        self.assertEqual(order.subtotal_kes, Decimal("4900.00"))
        self.assertEqual(order.delivery_kes, Decimal("300.00"))
        self.assertEqual(order.total_kes, Decimal("5200.00"))
        self.assertEqual(order.paypal_total_usd, Decimal("40.00"))
        self.assertEqual(order.paypal_kes_per_usd, Decimal("130.0000"))

    @override_settings(PAYPAL_CLIENT_ID="sandbox-client", PAYPAL_CLIENT_SECRET="sandbox-secret")
    @patch("myapp.views.paypal_request")
    def test_paypal_order_uses_saved_server_calculated_total(self, paypal_request):
        order = Order.objects.create(
            user=self.user,
            full_name="Amina",
            email="amina@example.com",
            phone="+254700000000",
            address="Example Road",
            subtotal_kes=Decimal("4900.00"),
            delivery_kes=Decimal("300.00"),
            total_kes=Decimal("5200.00"),
            paypal_kes_per_usd=Decimal("130.00"),
            paypal_total_usd=Decimal("40.00"),
        )
        paypal_request.return_value = {"id": "PAYPAL-ORDER-123"}

        response = self.client.post(reverse("create_paypal_order", args=[order.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"orderID": "PAYPAL-ORDER-123"})
        paypal_request.assert_called_once()
        payload = paypal_request.call_args.kwargs["payload"]
        self.assertEqual(payload["purchase_units"][0]["amount"]["value"], "40.00")
        order.refresh_from_db()
        self.assertEqual(order.paypal_order_id, "PAYPAL-ORDER-123")

    @override_settings(PAYPAL_CLIENT_ID="", PAYPAL_CLIENT_SECRET="")
    def test_paypal_order_requires_sandbox_credentials(self):
        order = Order.objects.create(
            user=self.user,
            full_name="Amina",
            email="amina@example.com",
            phone="+254700000000",
            address="Example Road",
            subtotal_kes=Decimal("4900.00"),
            delivery_kes=Decimal("300.00"),
            total_kes=Decimal("5200.00"),
            paypal_total_usd=Decimal("40.00"),
        )

        response = self.client.post(reverse("create_paypal_order", args=[order.pk]))

        self.assertEqual(response.status_code, 503)
        self.assertIn("not configured", response.json()["error"])

    @override_settings(PAYPAL_CLIENT_ID="sandbox-client", PAYPAL_CLIENT_SECRET="sandbox-secret")
    @patch("myapp.views.paypal_request")
    def test_paypal_capture_marks_only_confirmed_matching_order_paid(self, paypal_request):
        order = Order.objects.create(
            user=self.user,
            full_name="Amina",
            email="amina@example.com",
            phone="+254700000000",
            address="Example Road",
            subtotal_kes=Decimal("4900.00"),
            delivery_kes=Decimal("300.00"),
            total_kes=Decimal("5200.00"),
            paypal_total_usd=Decimal("40.00"),
            paypal_order_id="PAYPAL-ORDER-123",
        )
        OrderItem.objects.create(
            order=order,
            product=self.product,
            product_name=self.product.name,
            unit_price_kes=self.product.price_kes,
            quantity=1,
        )
        paypal_request.return_value = {
            "status": "COMPLETED",
            "purchase_units": [{
                "reference_id": str(order.pk),
                "payments": {
                    "captures": [{
                        "status": "COMPLETED",
                        "amount": {"currency_code": "USD", "value": "40.00"},
                    }],
                },
            }],
        }

        response = self.client.post(
            reverse("capture_paypal_order", args=[order.pk]),
            data=json.dumps({"orderID": "PAYPAL-ORDER-123"}),
            content_type="application/json",
        )

        order.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(order.status, Order.Status.PAID)
        self.assertEqual(response.json()["redirect"], reverse("order_success", args=[order.pk]))
        self.assertEqual(self.client.session["cart"], {str(self.product.pk): 1})

    @override_settings(PAYPAL_CLIENT_ID="sandbox-client", PAYPAL_CLIENT_SECRET="sandbox-secret")
    @patch("myapp.views.paypal_request")
    def test_paypal_capture_rejects_an_unrelated_order_id(self, paypal_request):
        order = Order.objects.create(
            user=self.user,
            full_name="Amina",
            email="amina@example.com",
            phone="+254700000000",
            address="Example Road",
            subtotal_kes=Decimal("4900.00"),
            delivery_kes=Decimal("300.00"),
            total_kes=Decimal("5200.00"),
            paypal_total_usd=Decimal("40.00"),
            paypal_order_id="PAYPAL-ORDER-123",
        )

        response = self.client.post(
            reverse("capture_paypal_order", args=[order.pk]),
            data=json.dumps({"orderID": "OTHER-ORDER"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        paypal_request.assert_not_called()
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING)

    @override_settings(PAYPAL_CLIENT_ID="sandbox-client", PAYPAL_CLIENT_SECRET="sandbox-secret")
    @patch("myapp.views.paypal_request")
    def test_paypal_capture_rejects_an_incorrect_amount(self, paypal_request):
        order = Order.objects.create(
            user=self.user,
            full_name="Amina",
            email="amina@example.com",
            phone="+254700000000",
            address="Example Road",
            subtotal_kes=Decimal("4900.00"),
            delivery_kes=Decimal("300.00"),
            total_kes=Decimal("5200.00"),
            paypal_total_usd=Decimal("40.00"),
            paypal_order_id="PAYPAL-ORDER-123",
        )
        paypal_request.return_value = {
            "status": "COMPLETED",
            "purchase_units": [{
                "reference_id": str(order.pk),
                "payments": {
                    "captures": [{
                        "status": "COMPLETED",
                        "amount": {"currency_code": "USD", "value": "1.00"},
                    }],
                },
            }],
        }

        response = self.client.post(
            reverse("capture_paypal_order", args=[order.pk]),
            data=json.dumps({"orderID": "PAYPAL-ORDER-123"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING)
