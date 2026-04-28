from django.urls import path
from . import views
from .views import setup_admin

urlpatterns = [
    # ── Auth ──
    path("",                         views.landing_page,       name="landing"),
    path("signup/",                  views.signup_view,        name="signup"),
    path("signup/verify/",           views.verify_signup_otp,  name="verify_signup_otp"),
    path("signup/resend/",           views.resend_otp,         name="resend_otp"),
    path("login/",                   views.login_view,         name="login"),
    path("logout/",                  views.logout_view,        name="logout"),
    path("forgot-password/",         views.forgot_password,    name="forgot_password"),
    path("forgot-password/verify/",  views.verify_reset_otp,   name="verify_reset_otp"),
    path("forgot-password/reset/",   views.set_new_password,   name="set_new_password"),
    

    # ── Buyer ──
    path("home/",                         views.home,           name="home"),
    path("search/",                       views.search,         name="search"),
    path("contact/",                      views.contact_form,   name="contact"),
    path("products/",                     views.product_list,   name="product_list"),
    path("product/<int:product_id>/",     views.product_detail, name="product_detail"),

    path("cart/",                          views.cart_view,        name="cart"),
    path("cart/add/<int:product_id>/",     views.add_to_cart,      name="add_to_cart"),
    path("cart/update/<int:product_id>/",  views.update_cart_item, name="update_cart_item"),
    path("cart/remove/<int:product_id>/",  views.remove_cart_item, name="remove_cart_item"),
    path("cart/buy-now/<int:product_id>/", views.buy_now,          name="buy_now"),

    path("checkout/",                      views.checkout,         name="checkout"),

    # ── Payment ──
    path("payment/<int:order_id>/",           views.payment_page,    name="payment_page"),
    path("payment/<int:order_id>/verify/",    views.paystack_verify, name="paystack_verify"),
    path("payment/webhook/",                  views.paystack_webhook, name="paystack_webhook"),

    # ── Buyer profile ──
    path("profile/",                           views.buyer_profile,    name="profile"),
    path("buyer/profile/",                     views.buyer_profile,    name="buyer_profile"),
    path("orders/confirm/<int:order_id>/",     views.confirm_delivery, name="confirm_delivery"),
    path("orders/cancel/<int:order_id>/",      views.cancel_order,     name="cancel_order"),

    # ── Farmer ──
    path("farmer/dashboard/",                        views.farmer_dashboard, name="farmer_dashboard"),
    path("farmer/profile/",                          views.farmer_profile,   name="farmer_profile"),
    path("farmer/<int:id>/",                         views.farmer_detail,    name="farmer_detail"),
    path("farmer/orders/accept/<int:order_id>/",     views.accept_order,     name="accept_order"),
    path("farmer/orders/reject/<int:order_id>/",     views.reject_order,     name="reject_order"),
    path("farmer/products/",                         views.my_products,      name="my_products"),
    path("farmer/products/add/",                     views.add_product,      name="add_product"),
    path("farmer/products/edit/<int:id>/",           views.edit_product,     name="edit_product"),
    path("farmer/products/delete/<int:id>/",         views.delete_product,   name="delete_product"),
    path("farmer/orders/<int:order_id>/",            views.order_detail,     name="order_detail"),

    # ── Notifications ──
    path("notifications/",                       views.get_notifications,        name="get_notifications"),
    path("notifications/read/",                  views.mark_notifications_read,  name="mark_notifications_read"),
    path("notifications/<int:notif_id>/toggle/", views.toggle_notification_read, name="toggle_notification_read"),
      # ── Admin Setup ──
    path('setup-admin/', setup_admin),


]
