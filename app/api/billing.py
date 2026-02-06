import stripe
from fastapi import APIRouter, Depends, Request, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.database import get_db, SessionLocal
from app.models import Box, BoxStatus, BoxTier, User
from app.models.subscription import Subscription, SubscriptionStatus
from app.schemas.billing import (
    CheckoutSessionCreate,
    CheckoutSessionResponse,
    PortalSessionResponse,
)
from app.api.deps import get_current_user
from app.services.box_provisioning import get_box_provisioning_service
from app.core.exceptions import BadRequestError, NotFoundError, ForbiddenError
from app.config import get_settings

router = APIRouter(prefix="/billing", tags=["billing"])


def _init_stripe():
    """Initialize stripe with secret key."""
    settings = get_settings()
    stripe.api_key = settings.stripe_secret_key


def _get_or_create_stripe_customer(user: User, db: Session, real_email: str = None) -> str:
    """Get existing Stripe customer ID or create new one."""
    # Update user email if we have a real one and current is placeholder
    if real_email and user.email.endswith("@auth0.local"):
        user.email = real_email
        db.commit()

    if user.stripe_customer_id:
        return user.stripe_customer_id

    _init_stripe()
    # Don't send placeholder emails to Stripe
    email = user.email if not user.email.endswith("@auth0.local") else real_email
    customer = stripe.Customer.create(
        email=email,
        metadata={"user_id": str(user.id), "auth0_id": user.auth0_id}
    )
    user.stripe_customer_id = customer.id
    db.commit()
    return customer.id


@router.post("/checkout-session", response_model=CheckoutSessionResponse)
async def create_checkout_session(
    data: CheckoutSessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a Stripe Checkout Session for a new box subscription."""
    settings = get_settings()
    _init_stripe()

    # Validate tier
    try:
        BoxTier(data.tier)
    except ValueError:
        raise BadRequestError(f"Invalid tier: {data.tier}")

    # Get price ID for this tier
    price_id = settings.stripe_prices.get(data.tier)
    if not price_id:
        raise BadRequestError(f"No Stripe price configured for tier: {data.tier}")

    # Get or create Stripe customer (pass real email from frontend)
    customer_id = _get_or_create_stripe_customer(current_user, db, real_email=data.email)

    # Create Checkout Session
    checkout_session = stripe.checkout.Session.create(
        customer=customer_id,
        payment_method_types=["card"],
        line_items=[{
            "price": price_id,
            "quantity": 1,
        }],
        mode="subscription",
        success_url=f"{settings.frontend_url}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{settings.frontend_url}/boxes/create",
        metadata={
            "user_id": str(current_user.id),
            "box_name": data.box_name,
            "tier": data.tier,
            "region": data.region,
        },
        subscription_data={
            "metadata": {
                "user_id": str(current_user.id),
                "box_name": data.box_name,
                "tier": data.tier,
                "region": data.region,
            }
        }
    )

    return CheckoutSessionResponse(
        checkout_url=checkout_session.url,
        session_id=checkout_session.id
    )


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
):
    """Handle Stripe webhook events. No JWT auth - uses Stripe signature."""
    settings = get_settings()
    _init_stripe()

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
    except ValueError:
        raise BadRequestError("Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise BadRequestError("Invalid signature")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        _handle_checkout_completed(session, background_tasks)

    elif event["type"] == "invoice.payment_failed":
        invoice = event["data"]["object"]
        _handle_payment_failed(invoice)

    elif event["type"] == "customer.subscription.deleted":
        sub_data = event["data"]["object"]
        _handle_subscription_deleted(sub_data)

    return {"status": "ok"}


def _handle_checkout_completed(session: dict, background_tasks: BackgroundTasks):
    """Handle successful checkout: create box + subscription."""
    db = SessionLocal()
    try:
        metadata = session.get("metadata", {})
        user_id = metadata.get("user_id")
        box_name = metadata.get("box_name", "My Box")
        tier = metadata.get("tier", "basic")
        region = metadata.get("region", "nyc1")
        stripe_subscription_id = session.get("subscription")
        stripe_customer_id = session.get("customer")

        if not user_id or not stripe_subscription_id:
            return

        # Get user for SSH key
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return

        # Create box record
        box = Box(
            user_id=user_id,
            name=box_name,
            tier=tier,
            region=region,
            status=BoxStatus.PENDING.value,
            status_message="Payment confirmed, provisioning box..."
        )
        db.add(box)
        db.flush()

        # Create subscription record
        settings = get_settings()
        price_id = settings.stripe_prices.get(tier, "")

        subscription = Subscription(
            user_id=user_id,
            box_id=box.id,
            stripe_customer_id=stripe_customer_id,
            stripe_subscription_id=stripe_subscription_id,
            stripe_price_id=price_id,
            status=SubscriptionStatus.ACTIVE.value,
        )
        db.add(subscription)
        db.commit()

        # Capture values for background task
        box_id = box.id
        user_ssh_key = user.ssh_public_key

        # Start provisioning in background
        async def provision_task():
            db_session = SessionLocal()
            try:
                box_obj = db_session.query(Box).filter(Box.id == box_id).first()
                if box_obj:
                    service = get_box_provisioning_service(db_session)
                    await service.provision_box(
                        box_obj,
                        user_ssh_public_key=user_ssh_key
                    )
            finally:
                db_session.close()

        background_tasks.add_task(provision_task)

    finally:
        db.close()


def _handle_payment_failed(invoice: dict):
    """Handle failed payment: mark subscription as past_due."""
    db = SessionLocal()
    try:
        stripe_sub_id = invoice.get("subscription")
        if not stripe_sub_id:
            return

        sub = db.query(Subscription).filter(
            Subscription.stripe_subscription_id == stripe_sub_id
        ).first()

        if sub:
            sub.status = SubscriptionStatus.PAST_DUE.value
            sub.updated_at = datetime.utcnow()

            if sub.box_id:
                box = db.query(Box).filter(Box.id == sub.box_id).first()
                if box:
                    box.status_message = "Payment failed - please update your payment method"
                    box.updated_at = datetime.utcnow()

            db.commit()
    finally:
        db.close()


def _handle_subscription_deleted(stripe_sub: dict):
    """Handle subscription cancellation: start grace period."""
    db = SessionLocal()
    try:
        stripe_sub_id = stripe_sub.get("id")
        if not stripe_sub_id:
            return

        sub = db.query(Subscription).filter(
            Subscription.stripe_subscription_id == stripe_sub_id
        ).first()

        if not sub:
            return

        # Set grace period: 3 days from now
        grace_end = datetime.utcnow() + timedelta(days=3)
        sub.status = SubscriptionStatus.GRACE_PERIOD.value
        sub.grace_period_end = grace_end
        sub.updated_at = datetime.utcnow()

        if sub.box_id:
            box = db.query(Box).filter(Box.id == sub.box_id).first()
            if box:
                box.status_message = f"Subscription canceled. Box will be deleted on {grace_end.strftime('%Y-%m-%d')}"
                box.updated_at = datetime.utcnow()

        db.commit()
    finally:
        db.close()


@router.post("/customer-portal", response_model=PortalSessionResponse)
async def create_customer_portal_session(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a Stripe Customer Portal session for managing subscriptions."""
    settings = get_settings()
    _init_stripe()

    if not current_user.stripe_customer_id:
        raise BadRequestError("No billing account found. Create a box first.")

    portal_session = stripe.billing_portal.Session.create(
        customer=current_user.stripe_customer_id,
        return_url=f"{settings.frontend_url}/dashboard",
    )

    return PortalSessionResponse(portal_url=portal_session.url)
