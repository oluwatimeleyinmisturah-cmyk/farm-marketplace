from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction

from .models import Order, Notification



@receiver(post_save, sender=Order)
def order_notifications(sender, instance, created, **kwargs):
    if created:
        pk = instance.pk
        transaction.on_commit(lambda: _notify_farmers_new_order(pk))
    else:
        _notify_on_status_change(instance)



def _notify_farmers_new_order(order_pk):
    try:
        order = Order.objects.get(pk=order_pk)
    except Order.DoesNotExist:
        return

    seen_farmers = set()
    for item in order.items.select_related('product__farmer').all():
        if not item.product:
            continue
        farmer = item.product.farmer
        if farmer.pk in seen_farmers:
            continue
        seen_farmers.add(farmer.pk)
        Notification.objects.create(
            user=farmer,
            message=(
                f"New order {order.order_number} received from {order.full_name}. "
                f"Total: \u20a6{order.total:,.0f}"
            ),
            notif_type=Notification.ORDER,
        )


def _notify_on_status_change(order):
    
    buyer = order.buyer
    events = []

    if order.status == 'sent_out':
        events.append((
            buyer,
            f"Your order {order.order_number} has been accepted and is on its way.",
            Notification.UPDATE,
        ))

    elif order.status == 'delivered':
        events.append((
            buyer,
            f"Your order {order.order_number} has been marked as delivered.",
            Notification.UPDATE,
        ))

    elif order.status == 'completed':
        events.append((
            buyer,
            f"Your order {order.order_number} is complete. Thank you for shopping with us!",
            Notification.UPDATE,
        ))
        seen = set()
        for item in order.items.select_related('product__farmer').all():
            if not item.product:
                continue
            farmer = item.product.farmer
            if farmer.pk in seen or farmer.pk == buyer.pk:
                continue
            seen.add(farmer.pk)
            events.append((
                farmer,
                f"Order {order.order_number} has been confirmed received by {order.full_name}.",
                Notification.UPDATE,
            ))

    elif order.status == 'rejected':
        events.append((
            buyer,
            f"Your order {order.order_number} was rejected by the farmer.",
            Notification.ALERT,
        ))

    elif order.status == 'cancelled':
        seen = set()
        for item in order.items.select_related('product__farmer').all():
            if not item.product:
                continue
            farmer = item.product.farmer
            if farmer.pk in seen:
                continue
            seen.add(farmer.pk)
            events.append((
                farmer,
                f"Order {order.order_number} was cancelled by the buyer ({order.full_name}).",
                Notification.ALERT,
            ))

    for recipient, message, notif_type in events:
        already = Notification.objects.filter(
            user=recipient,
            message=message,
            notif_type=notif_type,
        ).exists()
        if not already:
            Notification.objects.create(
                user=recipient,
                message=message,
                notif_type=notif_type,
            )