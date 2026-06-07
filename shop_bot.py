"""
shop_bot v3.0 — Cafe Shop Bot with Dual Payment System
Based on official balethon examples:
  - message.author.id  for user identification
  - LabeledPrice from balethon.objects
  - successful_payment from balethon.conditions
  - at_state for managing custom amount state
"""

from balethon import Client
from balethon.conditions import private, successful_payment, at_state
from balethon.objects import LabeledPrice, ReplyKeyboard
import logging
import os

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

# ─────────────────────────── Configuration ───────────────────────────
from dotenv import load_dotenv
load_dotenv()   
BOT_TOKEN     = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
PAYMENT_TOKEN = os.getenv("PAYMENT_TOKEN", "YOUR_PAYMENT_TOKEN_HERE")

# Fixed products: button label → (title, description, price in Rials)
PRODUCTS = {
    "☕ Special Coffee — 50,000":  ("☕ Special Coffee",  "A fresh cup of coffee",          50_000),
    "🎂 Cake of the Day — 80,000": ("🎂 Cake of the Day", "Freshly baked chocolate cake",    80_000),
    "🍵 Premium Tea — 30,000":     ("🍵 Premium Tea",     "Fine Iranian black tea",          30_000),
}

CUSTOM_BTN = "💰 Custom Amount"
MENU_BTNS  = list(PRODUCTS.keys()) + [CUSTOM_BTN]

bot = Client(token=BOT_TOKEN)


# ══════════════════════════ Successful Payment Handler ════════════════════════
# This handler must be registered BEFORE other handlers so it is matched first.
@bot.on_message(successful_payment)
async def show_payment(client, message):
    """
    Triggered automatically by Bale after the user completes a payment.

    What it does:
      1. Reads the successful_payment object attached to the message.
      2. Logs the user ID and the provider's charge ID for auditing.
      3. Clears any lingering state the user may have been in
         (e.g., if they were in WAITING_AMOUNT when the payment arrived).
      4. Sends a confirmation message with a tracking code.

    Key objects used:
      - message.successful_payment  : payment details sent by Bale
      - payment.provider_payment_charge_id : unique charge ID from the payment provider
      - message.author.del_state()  : removes the user's current FSM state
    """
    payment = message.successful_payment
    logger.info(
        "✅ Successful payment | user=%s | charge_id=%s",
        message.author.id,
        payment.provider_payment_charge_id,
    )

    # Clear FSM state if the user was in the custom-amount flow
    try:
        message.author.del_state()
    except Exception:
        pass

    await message.reply(
        "✅ **Payment completed successfully!**\n\n"
        "Your order has been placed 🎉\n"
        f"🔢 **Tracking code:** `{payment.provider_payment_charge_id}`\n\n"
        "Thank you for your purchase 🙏\n\n"
        "Type /start to order again."
    )


# ══════════════════════════ Custom Amount State Handler ═══════════════════════
@bot.on_message(private & at_state("WAITING_AMOUNT"))
async def receive_amount(client, message):
    """
    Handles user input while in the WAITING_AMOUNT FSM state.

    Flow:
      1. The user previously tapped "💰 Custom Amount".
      2. handle_menu_buttons set their state to "WAITING_AMOUNT".
      3. This handler catches their next text message.
      4. It validates the input (digits only, within allowed range).
      5. On success it clears the state and sends a payment invoice.

    Validation rules:
      - Must be a digit-only string (commas are stripped first).
      - Minimum: 1,000 Rials.
      - Maximum: 100,000,000 Rials.

    Key balethon calls:
      - message.author.del_state()   : exits the WAITING_AMOUNT state
      - client.send_invoice(...)     : creates and sends the payment invoice
      - LabeledPrice(label, amount)  : line-item for the invoice
    """
    user_id = message.author.id

    if not message.text:
        await message.reply("❌ Please enter a number.")
        return

    # Normalize: remove Persian/English commas
    text = message.text.strip().replace(",", "").replace("،", "")

    if not text.isdigit():
        await message.reply(
            "❌ Please enter digits only.\n"
            "Example: `75000`\n\n"
            "Or type /start to return to the menu."
        )
        return

    amount = int(text)

    if amount < 1_000:
        await message.reply("❌ Minimum amount is 1,000 Rials.")
        return

    if amount > 100_000_000:
        await message.reply("❌ Maximum amount is 100,000,000 Rials.")
        return

    # Exit WAITING_AMOUNT state before sending invoice
    message.author.del_state()
    logger.info("💰 Custom amount | user=%s | amount=%s", user_id, amount)

    try:
        await client.send_invoice(
            chat_id=message.chat.id,
            title="Custom Payment",
            description=f"Payment of {amount:,} Rials",
            payload=str(user_id),          # arbitrary data echoed back in successful_payment
            provider_token=PAYMENT_TOKEN,
            prices=[LabeledPrice(label="Custom Amount", amount=amount)],
        )
        logger.info("📄 Custom invoice sent | amount=%s", amount)
    except Exception as exc:
        logger.error("❌ Error sending custom invoice: %s", exc)
        await message.reply(f"❌ Error creating invoice:\n`{exc}`")


# ══════════════════════════ Main Menu Handler ══════════════════════════════════
@bot.on_message(private & at_state(None))
async def handle_menu_buttons(client, message):
    """
    Handles all messages when the user has no active FSM state (state=None).

    Responsibilities:
      1. /start command → display the product menu with a ReplyKeyboard.
      2. "💰 Custom Amount" button → set state to WAITING_AMOUNT and prompt for input.
      3. Product buttons → look up the product and send a fixed-price invoice.

    Why at_state(None)?
      balethon's at_state(None) matches users who currently have NO state set.
      This prevents menu buttons from being processed while the user is in
      WAITING_AMOUNT (that state is handled by receive_amount above).

    ReplyKeyboard layout:
      Each list passed to ReplyKeyboard() becomes one row of buttons.

    Key balethon calls:
      - message.author.set_state("WAITING_AMOUNT") : enter custom-amount flow
      - client.send_invoice(...)                   : send fixed-price invoice
      - LabeledPrice(label, amount)                : price line-item
    """
    text    = message.text or ""
    user_id = message.author.id

    # ── /start or unrecognized text → show menu ──
    if text.startswith("/start") or text not in MENU_BTNS:
        logger.info("▶️  Menu | user=%s", user_id)
        await message.reply(
            "☕ **Welcome to our Cafe!**\n\n"
            "Choose a product or enter a custom amount:",
            ReplyKeyboard(
                [MENU_BTNS[0]],
                [MENU_BTNS[1]],
                [MENU_BTNS[2]],
                [CUSTOM_BTN],
            )
        )
        return

    # ── Custom amount button ──
    if text == CUSTOM_BTN:
        message.author.set_state("WAITING_AMOUNT")
        await message.reply(
            "💰 **Custom Payment**\n\n"
            "Enter the amount in Rials:\n"
            "_(Example: 75000)_"
        )
        return

    # ── Fixed product buttons ──
    if text in PRODUCTS:
        title, description, amount = PRODUCTS[text]
        logger.info("🛒 Purchase %s | user=%s", title, user_id)

        try:
            await client.send_invoice(
                chat_id=message.chat.id,
                title=title,
                description=description,
                payload=str(user_id),
                provider_token=PAYMENT_TOKEN,
                prices=[LabeledPrice(label=title, amount=amount)],
            )
            logger.info("📄 Invoice for %s sent", title)
        except Exception as exc:
            logger.error("❌ Error sending invoice for %s: %s", title, exc)
            await message.reply(f"❌ Error creating invoice:\n`{exc}`")


# ══════════════════════════ Pre-Checkout Query Handler ═════════════════════════
@bot.on_pre_checkout_query()
async def handle_pre_checkout(client, pre_checkout_query):
    """
    Called by Bale right before it processes payment — the bot's final chance
    to approve or reject the transaction.

    How it works:
      - Bale sends a pre_checkout_query object with the pending order details.
      - The bot MUST respond within 10 seconds with ok=True (approve) or
        ok=False + error_message (reject).
      - Here we always approve; in a real shop you would verify stock,
        user eligibility, etc.

    Key object fields:
      - pre_checkout_query.id            : must be echoed back in the answer
      - pre_checkout_query.total_amount  : amount the user is about to pay
      - pre_checkout_query.invoice_payload: the payload string we set in send_invoice

    Key balethon call:
      - pre_checkout_query.answer(ok=True)  : approve the payment
      - pre_checkout_query.answer(ok=False, error_message="...")  : reject
    """
    logger.info(
        "🔍 PreCheckout | id=%s | amount=%s | payload=%s",
        pre_checkout_query.id,
        pre_checkout_query.total_amount,
        pre_checkout_query.invoice_payload,
    )

    await pre_checkout_query.answer(ok=True)
    logger.info("✅ PreCheckout approved")


# ══════════════════════════ Entry Point ════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 55)
    print("  🤖  Cafe Shop Bot — v3.0")
    print("=" * 55)
    print("  ✅  Uses official LabeledPrice & successful_payment")
    print("  ✅  ReplyKeyboard instead of InlineKeyboard")
    print("  ✅  message.author.id for user identification")
    print("-" * 55)
    print("  💡  Send /start in Bale to begin")
    print("=" * 55)
    bot.run()
