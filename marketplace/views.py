from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from django.db import transaction
from django.db.models import Sum, Count
from django.core.mail import send_mail, EmailMessage
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from .models import Profile, Product, Order, OrderItem, OTP, Notification
from .forms import SignupForm
from django.contrib import messages
from decimal import Decimal
import requests
import json
import uuid
from django.http import Http404



# ═══════════════════════════════════════════════
# EMAIL HELPER
# ═══════════════════════════════════════════════

def _send_otp_email(email, code, purpose):
    """Send a 6-digit OTP to the given address."""
    if purpose == OTP.PURPOSE_SIGNUP:
        subject = "Verify Your Farm Market Africa Account"
        body = (
            f"Welcome to Farm Market Africa!\n\n"
            f"Your email verification code is:\n\n"
            f"    {code}\n\n"
            f"This code expires in 10 minutes. Do not share it with anyone.\n\n"
            f"If you did not create an account, you can ignore this email.\n\n"
            f"— Farm Market Africa Team"
        )
    else:
        subject = "Reset Your Farm Market Africa Password"
        body = (
            f"You requested a password reset on Farm Market Africa.\n\n"
            f"Your reset code is:\n\n"
            f"    {code}\n\n"
            f"This code expires in 10 minutes. If you did not request this, "
            f"please ignore this email.\n\n"
            f"— Farm Market Africa Team"
        )
    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [email], fail_silently=False)


# ═══════════════════════════════════════════════
# AUTH  — SIGNUP WITH OTP EMAIL VERIFICATION
# ═══════════════════════════════════════════════

def signup_view(request):
    
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            # The signup form labels the username field as "Email Address",
            # so username IS the email. Fall back gracefully if a separate
            # email field exists on the form.
            email = form.cleaned_data.get('email', '').strip() or username

            if User.objects.filter(username=username).exists():
                messages.error(request, "That username is already taken.")
                return render(request, "auth/signup.html", {"form": form})

            if email and User.objects.filter(email=email).exists():
                messages.error(request, "An account with that email already exists.")
                return render(request, "auth/signup.html", {"form": form})

            # Store form data in session; don't create the user yet
            request.session['pending_signup'] = {
                'username': username,
                'email':    email,
                'password': request.POST.get('password1') or request.POST.get('password'),
                'role':     request.POST.get('role', 'buyer'),
                'first_name': request.POST.get('first_name', ''),
                'last_name':  request.POST.get('last_name', ''),
            }

            otp = OTP.generate_for(email, OTP.PURPOSE_SIGNUP)
            try:
                _send_otp_email(email, otp.code, OTP.PURPOSE_SIGNUP)
                messages.success(request, f"A 6-digit code was sent to {email}. Please verify to complete your registration.")
            except Exception:
                messages.error(request, "Could not send verification email. Please check the address and try again.")
                return render(request, "auth/signup.html", {"form": form})

            return redirect('verify_signup_otp')

    else:
        form = SignupForm()

    return render(request, "auth/signup.html", {"form": form})


def verify_signup_otp(request):
    """Verify the 6-digit OTP and create the user account."""
    pending = request.session.get('pending_signup')
    if not pending:
        messages.error(request, "Session expired. Please sign up again.")
        return redirect('signup')

    if request.method == "POST":
        entered = request.POST.get('otp', '').strip()
        email   = pending['email']

        otp_obj = OTP.objects.filter(
            email=email, purpose=OTP.PURPOSE_SIGNUP, is_used=False
        ).order_by('-created_at').first()

        if not otp_obj:
            messages.error(request, "No active code found. Please sign up again.")
            return redirect('signup')

        if otp_obj.is_expired():
            messages.error(request, "That code has expired. Please sign up again.")
            return redirect('signup')

        if otp_obj.code != entered:
            messages.error(request, "Incorrect code. Please try again.")
            return render(request, "auth/verify_otp.html", {"purpose": "signup", "email": email})

        # Code is correct — create the account
        otp_obj.is_used = True
        otp_obj.save()

        user = User.objects.create_user(
            username   = pending['username'],
            email      = email,
            password   = pending['password'],
            first_name = pending.get('first_name', ''),
            last_name  = pending.get('last_name', ''),
            is_active  = True,
        )
        Profile.objects.get_or_create(user=user, defaults={'role': pending.get('role', 'buyer')})

        del request.session['pending_signup']
        # Set flag in session so login page shows verification success message
        request.session['email_verified'] = True
        messages.success(request, "Email verified! Your account is ready. Please log in.")
        return redirect('login')

    return render(request, "auth/verify_otp.html", {
        "purpose": "signup",
        "email":   pending.get('email', ''),
    })


def resend_otp(request):
    """Re-send a fresh OTP for signup or password reset."""
    purpose = request.GET.get('purpose', OTP.PURPOSE_SIGNUP)

    if purpose == OTP.PURPOSE_SIGNUP:
        pending = request.session.get('pending_signup')
        if not pending:
            return redirect('signup')
        email = pending['email']
    else:
        email = request.session.get('reset_email')
        if not email:
            return redirect('forgot_password')

    otp = OTP.generate_for(email, purpose)
    try:
        _send_otp_email(email, otp.code, purpose)
        messages.success(request, f"A new code was sent to {email}.")
    except Exception:
        messages.error(request, "Could not resend the code. Please try again.")

    redirect_to = 'verify_signup_otp' if purpose == OTP.PURPOSE_SIGNUP else 'verify_reset_otp'
    return redirect(redirect_to)


# ═══════════════════════════════════════════════
# AUTH  — LOGIN / LOGOUT
# ═══════════════════════════════════════════════

def login_view(request):
    if request.user.is_authenticated:
        profile = getattr(request.user, 'profile', None)
        if profile and profile.role == "farmer":
            return redirect("farmer_dashboard")
        return redirect("home")

    # Check if we're coming from email verification
    email_verified = request.session.pop('email_verified', False)
    
    if request.method == "POST":
        email       = request.POST.get("email", "").strip()
        password    = request.POST.get("password", "").strip()
        remember_me = request.POST.get("remember_me")
        next_url    = request.POST.get("next")

        if not email or not password:
            messages.error(request, "Please fill in all fields.")
            return render(request, "auth/login.html", {"email": email, "next": next_url})

        user = authenticate(request, username=email, password=password)

        if user is not None:
            if not user.is_active:
                messages.error(request, "This account is disabled.")
                return render(request, "auth/login.html", {"email": email, "next": next_url})

            login(request, user)
            request.session.set_expiry(1209600 if remember_me else 0)

            # Show verification success message only on first login after signup
            if email_verified:
                messages.success(request, "Email verified successfully! Welcome to Farm Market Africa.")

            if next_url:
                return redirect(next_url)

            profile = getattr(user, 'profile', None)
            if profile and profile.role == "farmer":
                return redirect("farmer_dashboard")
            return redirect("home")

        messages.error(request, "Invalid email or password.")
        return render(request, "auth/login.html", {"email": email, "next": next_url})

    return render(request, "auth/login.html", {
        "next": request.GET.get("next", ""),
        "email_verified": email_verified,  # Pass to template for display
    })


def logout_view(request):
    logout(request)
    return redirect("landing")


# ═══════════════════════════════════════════════
# AUTH  — FORGOT PASSWORD WITH OTP
# ═══════════════════════════════════════════════

def forgot_password(request):
    """Step 1: ask for email, send OTP."""
    if request.method == "POST":
        email = request.POST.get("email", "").strip()

        if not User.objects.filter(email=email, is_active=True).exists():
            # Don't reveal whether the account exists; just show the same message
            messages.info(request, f"If {email} is registered, a reset code has been sent.")
            return render(request, "auth/forgot_password.html")

        otp = OTP.generate_for(email, OTP.PURPOSE_RESET)
        try:
            _send_otp_email(email, otp.code, OTP.PURPOSE_RESET)
        except Exception:
            messages.error(request, "Could not send the reset email. Please try again.")
            return render(request, "auth/forgot_password.html")

        request.session['reset_email'] = email
        messages.success(request, f"A 6-digit code was sent to {email}.")
        return redirect('verify_reset_otp')

    return render(request, "auth/forgot_password.html")


def verify_reset_otp(request):
    """Step 2: user enters the OTP."""
    email = request.session.get('reset_email')
    if not email:
        messages.error(request, "Session expired. Please start again.")
        return redirect('forgot_password')

    if request.method == "POST":
        entered = request.POST.get('otp', '').strip()

        otp_obj = OTP.objects.filter(
            email=email, purpose=OTP.PURPOSE_RESET, is_used=False
        ).order_by('-created_at').first()

        if not otp_obj or otp_obj.is_expired():
            messages.error(request, "Code expired or not found. Please request a new one.")
            return redirect('forgot_password')

        if otp_obj.code != entered:
            messages.error(request, "Incorrect code. Please try again.")
            return render(request, "auth/verify_otp.html", {"purpose": "reset", "email": email})

        otp_obj.is_used = True
        otp_obj.save()

        # Mark session so the set-password step knows OTP passed
        request.session['reset_verified'] = True
        return redirect('set_new_password')

    return render(request, "auth/verify_otp.html", {"purpose": "reset", "email": email})


def set_new_password(request):
    """Step 3: user sets a new password (must differ from the old one)."""
    email = request.session.get('reset_email')
    if not email or not request.session.get('reset_verified'):
        messages.error(request, "Please complete OTP verification first.")
        return redirect('forgot_password')

    if request.method == "POST":
        password1 = request.POST.get("password1", "")
        password2 = request.POST.get("password2", "")

        if password1 != password2:
            messages.error(request, "Passwords do not match.")
            return render(request, "auth/set_new_password.html")

        if len(password1) < 8:
            messages.error(request, "Password must be at least 8 characters.")
            return render(request, "auth/set_new_password.html")

        try:
            user = User.objects.get(email=email, is_active=True)
        except User.DoesNotExist:
            messages.error(request, "Account not found.")
            return redirect('forgot_password')

        if user.check_password(password1):
            messages.error(request, "Your new password must be different from your current password.")
            return render(request, "auth/set_new_password.html")

        user.set_password(password1)
        user.save()

        # Clear reset session keys
        for key in ('reset_email', 'reset_verified'):
            request.session.pop(key, None)

        messages.success(request, "Password updated successfully. Please log in.")
        return redirect('login')

    return render(request, "auth/set_new_password.html")


# ═══════════════════════════════════════════════
# BUYER — GENERAL
# ═══════════════════════════════════════════════

def home(request):
    
    # Ensure cart exists
    if 'cart' not in request.session:
        request.session['cart'] = {}

    products = Product.objects.all()
    farmers  = User.objects.filter(profile__role='farmer')

    cart_count_value = sum(request.session.get('cart', {}).values())

    return render(request, "buyers/home.html", {
        "products": products,
        "farmers": farmers,
        "cart_count": cart_count_value,
    })

def landing_page(request):
    if request.user.is_authenticated:
        profile = getattr(request.user, 'profile', None)
        if profile and profile.role == "farmer":
            return redirect("farmer_dashboard")
        return redirect("home")
    return render(request, "landing.html")


def product_list(request):
    category = request.GET.get('category')
    query    = request.GET.get('q', '').strip()
    products = Product.objects.all()
    if category:
        products = products.filter(category=category)
    if query:
        products = products.filter(name__icontains=query)
    categories              = Product.CATEGORY_CHOICES
    selected_category_label = dict(categories).get(category, '')
    return render(request, 'buyers/product_list.html', {
        'products':                products,
        'selected_category':       category,
        'selected_category_label': selected_category_label,
        'query':                   query,
        'categories':              categories,
    })


def product_detail(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    return render(request, 'buyers/product_detail.html', {'product': product})


# ═══════════════════════════════════════════════
# CONTACT FORM
# ═══════════════════════════════════════════════

def contact_form(request):
    """
    Handles the contact form submission on the homepage.
    Sends the message to the admin email set in settings.
    """
    if request.method == "POST":
        name    = request.POST.get("name", "").strip()
        email   = request.POST.get("email", "").strip()
        message = request.POST.get("message", "").strip()

        if not name or not email or not message:
            messages.error(request, "Please fill in all fields.")
            return redirect('home')

        subject = f"Farm Market Africa — Message from {name}"
        body    = (
            f"Name:    {name}\n"
            f"Email:   {email}\n\n"
            f"Message:\n{message}"
        )

        try:
            # Send to admin
            send_mail(
                subject,
                body,
                settings.DEFAULT_FROM_EMAIL,
                [settings.CONTACT_EMAIL],
                fail_silently=False,
            )

            # Auto-reply to the sender
            send_mail(
                "We received your message — Farm Market Africa",
                (
                    f"Hi {name},\n\n"
                    f"Thank you for reaching out to Farm Market Africa. "
                    f"We have received your message and will get back to you within 24 hours.\n\n"
                    f"— Farm Market Africa Support"
                ),
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=True,  # don't fail the request if auto-reply fails
            )

            messages.success(request, "Your message has been sent. We will be in touch soon.")
        except Exception:
            messages.error(request, "Could not send your message right now. Please try again later.")

    return redirect('home')

# ═══════════════════════════════════════════════
# CART  (session-based)
# ═══════════════════════════════════════════════

def _get_cart(request):
    return request.session.get('cart', {})


def _save_cart(request, cart):
    request.session['cart'] = cart
    request.session.modified = True


def _cart_total_count(cart):
    """TOTAL quantity of all products in cart"""
    return sum(cart.values())


def _build_cart_context(cart):
    cart_items = []
    subtotal   = Decimal('0')

    for pid, qty in cart.items():
        try:
            product = Product.objects.get(id=int(pid))
        except Product.DoesNotExist:
            continue

        quantity    = min(max(int(qty), 1), product.quantity if product.quantity > 0 else 1)
        total_price = product.price * quantity
        subtotal   += total_price

        cart_items.append({
            'product': product,
            'quantity': quantity,
            'total_price': total_price
        })

    shipping = Decimal('2000') if subtotal > 0 else Decimal('0')
    tax      = subtotal * Decimal('0.075')
    total    = subtotal + shipping + tax

    return cart_items, subtotal, tax, shipping, total


def cart_view(request):
    cart = _get_cart(request)

    cart_items, subtotal, tax, shipping, total = _build_cart_context(cart)

    return render(request, 'buyers/cart.html', {
        'cart_items': cart_items,
        'subtotal': subtotal,
        'tax': tax,
        'shipping': shipping,
        'total': total,

        # ✅ THIS IS WHAT YOUR BADGE WILL USE
        'cart_count': _cart_total_count(cart),
    })


def add_to_cart(request, product_id):
    if request.method != 'POST':
        return redirect('product_detail', product_id=product_id)

    product  = get_object_or_404(Product, id=product_id)
    quantity = max(int(request.POST.get('quantity') or 1), 1)

    cart = _get_cart(request)

    cart[str(product_id)] = cart.get(str(product_id), 0) + quantity
    _save_cart(request, cart)

    # ✅ AJAX RESPONSE (for instant update if you use JS later)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'message': f'"{product.name}" added.',
            'cart_count': _cart_total_count(cart)
        })

    messages.success(request, f'"{product.name}" has been added to cart.')
    return redirect(request.POST.get('next') or request.META.get('HTTP_REFERER') or 'product_list')


def update_cart_item(request, product_id):
    if request.method != 'POST':
        return redirect('cart')

    cart = _get_cart(request)

    if str(product_id) in cart:
        cart[str(product_id)] = max(int(request.POST.get('quantity') or 1), 1)
        _save_cart(request, cart)

    messages.success(request, 'Cart updated.')
    return redirect('cart')


def remove_cart_item(request, product_id):
    cart = _get_cart(request)
    cart.pop(str(product_id), None)
    _save_cart(request, cart)

    messages.success(request, 'Item removed from cart.')
    return redirect('cart')


def buy_now(request, product_id):
    if request.method != 'POST':
        return redirect('product_detail', product_id=product_id)

    product  = get_object_or_404(Product, id=product_id)
    quantity = max(int(request.POST.get('quantity') or 1), 1)

    cart = _get_cart(request)
    cart[str(product_id)] = cart.get(str(product_id), 0) + quantity
    _save_cart(request, cart)

    return redirect('checkout')


# ═══════════════════════════════════════════════
# CHECKOUT
# ═══════════════════════════════════════════════

@login_required
@transaction.atomic
def checkout(request):
    cart = _get_cart(request)
    if not cart:
        messages.warning(request, 'Your cart is empty.')
        return redirect('cart')

    SHIPPING_COSTS = {
        'standard': Decimal('2000'),
        'express':  Decimal('4500'),
        'pickup':   Decimal('0'),
    }

    if request.method == 'POST':
        delivery_method = request.POST.get('delivery_method', 'standard')
        shipping_cost   = SHIPPING_COSTS.get(delivery_method, Decimal('2000'))
        cart_items, subtotal, _, _, _ = _build_cart_context(cart)
        tax   = subtotal * Decimal('0.075')
        total = subtotal + tax + shipping_cost

        order = Order.objects.create(
            buyer           = request.user,
            full_name       = request.POST.get('full_name', ''),
            email           = request.POST.get('email', ''),
            phone           = request.POST.get('phone', ''),
            address         = request.POST.get('address', ''),
            city            = request.POST.get('city', ''),
            state           = request.POST.get('state', ''),
            notes           = request.POST.get('notes', ''),
            delivery_method = delivery_method,
            subtotal        = subtotal,
            tax             = tax,
            shipping_cost   = shipping_cost,
            total           = total,
            status          = 'pending',
            payment_status  = 'unpaid',
        )

        for item in cart_items:
            OrderItem.objects.create(
                order        = order,
                product      = item['product'],
                farmer       = item['product'].farmer,
                product_name = item['product'].name,
                unit_price   = item['product'].price,
                quantity     = item['quantity'],
                total_price  = item['total_price'],
            )

        _save_cart(request, {})
        messages.success(request, f'Order {order.order_number} created. Please complete payment.')
        return redirect('payment_page', order_id=order.id)

    cart_items, subtotal, _, _, _ = _build_cart_context(cart)
    default_shipping = Decimal('2000')
    tax   = subtotal * Decimal('0.075')
    total = subtotal + tax + default_shipping

    return render(request, 'buyers/checkout.html', {
        'cart_items': cart_items,
        'subtotal':   subtotal,
        'tax':        tax,
        'shipping':   default_shipping,
        'total':      total,
    })


# ═══════════════════════════════════════════════
# PAYSTACK PAYMENT
# ═══════════════════════════════════════════════

@login_required
def payment_page(request, order_id):
    """Show a payment page with the Paystack inline popup."""
    order = get_object_or_404(Order, id=order_id, buyer=request.user)

    if order.payment_status == 'paid':
        messages.info(request, 'This order has already been paid for.')
        return redirect('profile')

    return render(request, 'payment.html', {
        'order':               order,
        'paystack_public_key': settings.PAYSTACK_PUBLIC_KEY,
    })


@login_required
def paystack_verify(request, order_id):
    """
    Called after the Paystack popup closes successfully.
    Verifies the transaction with Paystack's API and marks the order paid.
    """
    order = get_object_or_404(Order, id=order_id, buyer=request.user)
    ref   = request.GET.get('reference', '')

    if not ref:
        messages.error(request, 'Payment reference missing.')
        return redirect('payment_page', order_id=order.id)

    # Verify with Paystack
    headers  = {'Authorization': f'Bearer {settings.PAYSTACK_SECRET_KEY}'}
    response = requests.get(
        f'https://api.paystack.co/transaction/verify/{ref}',
        headers=headers,
        timeout=30,
    )

    if response.status_code != 200:
        messages.error(request, 'Could not verify payment. Please contact support.')
        return redirect('profile')

    data = response.json().get('data', {})

    if data.get('status') == 'success' and data.get('amount') == order.total_kobo:
        order.paystack_ref   = ref
        order.payment_status = 'paid'
        order.paid_at        = timezone.now()
        order.save()
        messages.success(request, f'Payment confirmed for {order.order_number}.')
        return redirect('profile')

    order.payment_status = 'failed'
    order.save()
    messages.error(request, 'Payment could not be confirmed. Please try again.')
    return redirect('payment_page', order_id=order.id)


@csrf_exempt
def paystack_webhook(request):
    """
    Paystack sends POST webhooks for async events (charge.success etc.).
    Verify the signature and update the order.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    # Verify Paystack signature
    import hmac
    import hashlib
    sig = request.headers.get('x-paystack-signature', '')
    expected = hmac.new(
        settings.PAYSTACK_SECRET_KEY.encode(),
        request.body,
        hashlib.sha512,
    ).hexdigest()

    if sig != expected:
        return JsonResponse({'error': 'Invalid signature'}, status=401)

    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Bad payload'}, status=400)

    if payload.get('event') == 'charge.success':
        data = payload.get('data', {})
        ref  = data.get('reference', '')
        try:
            order = Order.objects.get(paystack_ref=ref)
        except Order.DoesNotExist:
            # Try matching by metadata
            meta = data.get('metadata', {})
            order_id = meta.get('order_id')
            if order_id:
                try:
                    order = Order.objects.get(id=order_id)
                except Order.DoesNotExist:
                    return JsonResponse({'status': 'ok'})
            else:
                return JsonResponse({'status': 'ok'})

        if order.payment_status != 'paid':
            order.paystack_ref   = ref
            order.payment_status = 'paid'
            order.paid_at        = timezone.now()
            order.save()

    return JsonResponse({'status': 'ok'})


# ═══════════════════════════════════════════════
# BUYER PROFILE
# ═══════════════════════════════════════════════

@login_required
def buyer_profile(request):
    profile = getattr(request.user, 'profile', None)
    if profile and profile.role == 'farmer':
        return redirect('farmer_profile')

    first_time_profile_visit = request.session.pop('first_time_profile_visit', False)

    if request.method == 'POST':
        request.user.first_name = request.POST.get('first_name', request.user.first_name)
        request.user.last_name  = request.POST.get('last_name',  request.user.last_name)
        request.user.email      = request.POST.get('email',      request.user.email)
        request.user.save()
        if profile:
            profile.phone   = request.POST.get('phone',   profile.phone)
            profile.address = request.POST.get('address', profile.address)
            profile.bio     = request.POST.get('bio',     profile.bio)
            if request.FILES.get('image'):
                profile.image = request.FILES['image']
            profile.save()
        messages.success(request, 'Profile updated successfully.')
        return redirect('profile')

    orders           = Order.objects.filter(buyer=request.user).prefetch_related('items__product')
    pending_orders   = orders.filter(status='pending')
    sent_orders      = orders.filter(status='sent_out')
    completed_orders = orders.filter(status__in=['delivered', 'completed'])
    rejected_orders  = orders.filter(status='rejected')
    cancelled_orders = orders.filter(status='cancelled')

    return render(request, 'buyers/profile.html', {
        'profile':          profile,
        'orders':           orders,
        'pending_orders':   pending_orders,
        'sent_orders':      sent_orders,
        'completed_orders': completed_orders,
        'rejected_orders':  rejected_orders,
        'cancelled_orders': cancelled_orders,
    })


@login_required
def confirm_delivery(request, order_id):
    order = get_object_or_404(Order, id=order_id, buyer=request.user)
    if order.status == 'sent_out':
        order.status       = 'completed'
        order.completed_at = timezone.now()
        order.save()
        messages.success(request, f'Order {order.order_number} marked as received.')
    return redirect('profile')


@login_required
def cancel_order(request, order_id):
    order = get_object_or_404(Order, id=order_id, buyer=request.user)
    if order.status == 'pending':
        order.status = 'cancelled'
        order.save()
        messages.success(request, f'Order {order.order_number} has been cancelled.')
    else:
        messages.error(request, 'Only pending orders can be cancelled.')
    return redirect('profile')


# ═══════════════════════════════════════════════
# FARMER PROFILE
# ═══════════════════════════════════════════════

@login_required
def farmer_profile(request):
    profile = getattr(request.user, 'profile', None)
    if profile and profile.role == 'buyer':
        return redirect('profile')

    # Check if this is the farmer's first-time profile visit
    first_time_profile_visit = request.session.pop('first_time_profile_visit', False)

    if request.method == 'POST':
        request.user.first_name = request.POST.get('first_name', request.user.first_name)
        request.user.last_name  = request.POST.get('last_name',  request.user.last_name)
        request.user.email      = request.POST.get('email',      request.user.email)
        request.user.save()
        if profile:
            profile.farm_name = request.POST.get('farm_name', profile.farm_name)
            profile.phone     = request.POST.get('phone',     profile.phone)
            profile.location  = request.POST.get('location',  profile.location)
            profile.bio       = request.POST.get('bio',       profile.bio)
            if request.FILES.get('image'):
                profile.image = request.FILES['image']
            profile.save()
        messages.success(request, 'Profile updated successfully.')
        return redirect('farmer_profile')

    products       = Product.objects.filter(farmer=request.user)
    my_order_items = OrderItem.objects.filter(farmer=request.user).select_related('order', 'order__buyer')
    my_order_ids   = my_order_items.values_list('order_id', flat=True).distinct()
    all_orders     = Order.objects.filter(id__in=my_order_ids).prefetch_related('items', 'buyer')

    pending_orders   = all_orders.filter(status='pending')
    active_orders    = all_orders.filter(status='sent_out')
    completed_orders = all_orders.filter(status__in=['completed', 'delivered'])
    rejected_orders  = all_orders.filter(status='rejected')
    cancelled_orders = all_orders.filter(status='cancelled')

    total_products  = products.count()
    total_orders    = all_orders.count()
    total_pending   = pending_orders.count()
    total_completed = completed_orders.count()

    # Completed orders only — money actually received
    top_customers_qs = (
        my_order_items
        .filter(order__status='completed')
        .values('order__buyer', 'order__buyer__first_name', 'order__buyer__last_name', 'order__buyer__username')
        .annotate(total_spent=Sum('total_price'), order_count=Count('order', distinct=True))
        .order_by('-total_spent')[:3]
    )
    top_customers = []
    for tc in top_customers_qs:
        name = (
            f"{tc['order__buyer__first_name']} {tc['order__buyer__last_name']}".strip()
            or tc['order__buyer__username']
        )
        top_customers.append({
            'name':        name,
            'total_spent': tc['total_spent'] or Decimal('0'),
            'order_count': tc['order_count'],
        })

    return render(request, 'farmers/profile.html', {
        'profile':                    profile,
        'products':                   products,
        'all_orders':                 all_orders,
        'pending_orders':             pending_orders,
        'active_orders':              active_orders,
        'completed_orders':           completed_orders,
        'rejected_orders':            rejected_orders,
        'cancelled_orders':           cancelled_orders,
        'top_customers':              top_customers,
        'total_products':             total_products,
        'total_orders':               total_orders,
        'total_pending':              total_pending,
        'total_completed':            total_completed,
        'first_time_profile_visit':   first_time_profile_visit,  # Pass to template for pop-up
    })


@login_required
def accept_order(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    if not OrderItem.objects.filter(order=order, farmer=request.user).exists():
        messages.error(request, 'Not authorized.')
        return redirect('farmer_profile')
    if order.status == 'pending':
        order.status = 'sent_out'
        order.save()
        messages.success(request, f'Order {order.order_number} accepted.')
    return redirect('farmer_profile')


@login_required
def reject_order(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    if not OrderItem.objects.filter(order=order, farmer=request.user).exists():
        messages.error(request, 'Not authorized.')
        return redirect('farmer_profile')
    if order.status == 'pending':
        order.status = 'rejected'
        order.save()
        messages.success(request, f'Order {order.order_number} rejected.')
    return redirect('farmer_profile')

@login_required
def order_detail(request, order_id):
    order = Order.objects.filter(
        id=order_id,
        items__product__farmer=request.user
    ).distinct().first()

    if not order:
        raise Http404("Order not found")

    return render(request, 'farmers/order_detail.html', {'order': order})
# ═══════════════════════════════════════════════
# FARMER — PRODUCT MANAGEMENT
# ═══════════════════════════════════════════════

@login_required
def farmer_dashboard(request):
    products       = Product.objects.filter(farmer=request.user)
    my_order_items = OrderItem.objects.filter(farmer=request.user).select_related('order', 'order__buyer')
    my_order_ids   = my_order_items.values_list('order_id', flat=True).distinct()
    recent_orders  = Order.objects.filter(id__in=my_order_ids).prefetch_related('items')[:5]
    total_products = products.count()
    total_orders   = Order.objects.filter(id__in=my_order_ids).count()
    return render(request, "farmers/dashboard.html", {
        "products":       products,
        "recent_orders":  recent_orders,
        "total_products": total_products,
        "total_orders":   total_orders,
    })


@login_required
def my_products(request):
    products = Product.objects.filter(farmer=request.user)
    return render(request, "farmers/my_products.html", {"products": products})


@login_required
def add_product(request):
    if request.method == "POST":
        Product.objects.create(
            farmer      = request.user,
            name        = request.POST.get("name"),
            category    = request.POST.get("category"),
            description = request.POST.get("description"),
            price       = request.POST.get("price"),
            quantity    = request.POST.get("quantity"),
            location    = request.POST.get("location"),
            image       = request.FILES.get("image"),
            is_new      = request.POST.get("is_new") == "on",
            is_hot      = request.POST.get("is_hot") == "on",
        )
        return redirect("my_products")
    return render(request, "farmers/add_product.html")


@login_required
def edit_product(request, id):
    product = get_object_or_404(Product, id=id, farmer=request.user)
    source  = request.GET.get('source', request.POST.get('source', 'my_products'))
    if request.method == "POST":
        product.name        = request.POST.get("name")
        product.category    = request.POST.get("category")
        product.description = request.POST.get("description")
        product.price       = request.POST.get("price")
        product.quantity    = request.POST.get("quantity")
        product.location    = request.POST.get("location")
        product.is_new      = request.POST.get("is_new") == "on"
        product.is_hot      = request.POST.get("is_hot") == "on"
        if request.FILES.get("image"):
            product.image = request.FILES["image"]
        product.save()
        messages.success(request, f'"{product.name}" updated.')
        return redirect("farmer_dashboard" if source == 'dashboard' else "my_products")
    return render(request, "farmers/edit_product.html", {"product": product, "source": source})


@login_required
def delete_product(request, id):
    product = get_object_or_404(Product, id=id, farmer=request.user)
    source  = request.POST.get('source', 'my_products')
    name    = product.name
    product.delete()
    messages.success(request, f'"{name}" deleted.')
    return redirect("farmer_dashboard" if source == 'dashboard' else "my_products")


# ═══════════════════════════════════════════════
# SEARCH & MISC
# ═══════════════════════════════════════════════

def search(request):
    query    = request.GET.get("q")
    products = Product.objects.filter(name__icontains=query) if query else []
    return render(request, "search.html", {"products": products})


def farmer_detail(request, id):
    farmer   = get_object_or_404(User, id=id)
    products = Product.objects.filter(farmer=farmer)
    return render(request, "farmer_detail.html", {"farmer": farmer, "products": products})


# ═══════════════════════════════════════════════
# NOTIFICATIONS
# ═══════════════════════════════════════════════

@login_required
def get_notifications(request):
    notifs       = Notification.objects.filter(user=request.user)[:20]
    unread_count = Notification.objects.filter(user=request.user, is_read=False).count()
    data = [{
        'id':      n.pk,
        'message': n.message,
        'type':    n.notif_type,
        'is_read': n.is_read,
        'time':    n.created_at.strftime('%b %d, %I:%M %p'),
    } for n in notifs]
    return JsonResponse({'notifications': data, 'count': unread_count})


@login_required
@require_POST
def mark_notifications_read(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return JsonResponse({'success': True})


@login_required
@require_POST
def toggle_notification_read(request, notif_id):
    try:
        notif         = Notification.objects.get(pk=notif_id, user=request.user)
        notif.is_read = not notif.is_read
        notif.save(update_fields=['is_read'])
        return JsonResponse({'success': True, 'is_read': notif.is_read})
    except Notification.DoesNotExist:
        return JsonResponse({'success': False}, status=404)