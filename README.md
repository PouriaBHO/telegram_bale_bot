# ☕ Cafe Shop Bot — v3.0

A step-by-step tutorial bot built with **[balethon](https://github.com/balethon/balethon)** for the **Bale** messenger platform.  
This is **Part N** of a slow, beginner-friendly series published on GitHub.

---

## 📌 What This Bot Does

| Feature | Description |
|---|---|
| Product menu | Shows 3 fixed-price items via a `ReplyKeyboard` |
| Fixed invoice | Sends a payment invoice for the chosen product |
| Custom amount | Lets the user type any amount and pay it |
| Pre-checkout | Approves every payment before it is processed |
| Confirmation | Sends a tracking code after a successful payment |

---

## 🗂️ File Structure

```
shop_bot/
├── shop_bot.py      ← main bot file (this tutorial)
├── .env.example     ← template for your secret tokens
├── .gitignore       ← keeps your real .env out of git
└── README.md        ← you are here
```

---

## 🔑 Getting Your Tokens

### 1 — Bot Token

1. Open **Bale** and search for **@BotFather**.
2. Send `/newbot` and follow the prompts.
3. BotFather will give you a token that looks like:  
   `720374772:1_ABCdefGHIjklMNOpqrSTUvwxYZ`
4. Copy it — this is your **BOT_TOKEN**.

### 2 — Payment Token

1. In Bale, search for **@BaleWallet** (the official payment provider).
2. Follow the instructions to connect your bot to a wallet.
3. You will receive a token that looks like:  
   `WALLET-xxxxxxxxxxxxxxxxxxxxxx`
4. Copy it — this is your **PAYMENT_TOKEN**.

> **Never share these tokens publicly.**  
> Anyone who has them can control your bot and receive payments on your behalf.

---

## ⚙️ Configuration

### Option A — Environment Variables (recommended)

Create a file called `.env` in the project folder:

```env
BOT_TOKEN=720374772:1_YOUR_REAL_TOKEN_HERE
PAYMENT_TOKEN=WALLET-YOUR_REAL_PAYMENT_TOKEN_HERE
```

The bot reads them automatically with `os.getenv(...)`.

### Option B — Direct edit (quick local test only)

Open `shop_bot.py` and replace the placeholder strings:

```python
BOT_TOKEN     = "720374772:1_YOUR_REAL_TOKEN_HERE"
PAYMENT_TOKEN = "WALLET-YOUR_REAL_PAYMENT_TOKEN_HERE"
```

> ⚠️ If you use Option B, **add `.env` and `shop_bot.py` to `.gitignore`** or your tokens will be exposed on GitHub.

---

## 🚀 Running the Bot

```bash
# Install the library
pip install balethon

# Run
python shop_bot.py
```

Then open Bale and send `/start` to your bot.

---

## 📖 Code Walkthrough — Handler by Handler

> Each section below explains **one function** in `shop_bot.py`.

---

### 1. `show_payment` — Successful Payment Handler

```python
@bot.on_message(successful_payment)
async def show_payment(client, message):
```

**When does it run?**  
After the user completes a payment, Bale sends a special message of type `successful_payment`. This handler catches it.

**What it does step by step:**

| Step | Code | Explanation |
|---|---|---|
| 1 | `message.successful_payment` | Access the payment details object |
| 2 | `payment.provider_payment_charge_id` | Unique ID assigned by the payment provider — use this as your order tracking code |
| 3 | `message.author.del_state()` | Clear any FSM state the user had (e.g., if they were typing a custom amount) |
| 4 | `await message.reply(...)` | Send a confirmation message to the user |

> **Why is this handler registered first?**  
> balethon matches handlers in registration order. `successful_payment` must come before the general `private & at_state(None)` handler, otherwise the payment confirmation message might be swallowed by the menu handler.

---

### 2. `receive_amount` — Custom Amount State Handler

```python
@bot.on_message(private & at_state("WAITING_AMOUNT"))
async def receive_amount(client, message):
```

**When does it run?**  
Only when the user is in the `"WAITING_AMOUNT"` FSM state **and** sends a private message.

**What is `at_state`?**  
balethon has a built-in finite state machine (FSM). You can attach a named state to any user with `message.author.set_state("NAME")` and read/clear it later. `at_state("WAITING_AMOUNT")` is a **filter** — the handler only fires for users currently in that state.

**Validation logic:**

```
raw text
  → strip whitespace
  → remove commas (English "," and Persian "،")
  → check all characters are digits
  → convert to int
  → check 1,000 ≤ amount ≤ 100,000,000
```

**Key balethon calls:**

| Call | Purpose |
|---|---|
| `message.author.del_state()` | Exit WAITING_AMOUNT before sending the invoice |
| `client.send_invoice(...)` | Create and deliver a Bale payment invoice |
| `LabeledPrice(label, amount)` | One line-item on the invoice; `amount` is in **Rials** |

---

### 3. `handle_menu_buttons` — Main Menu Handler

```python
@bot.on_message(private & at_state(None))
async def handle_menu_buttons(client, message):
```

**When does it run?**  
For any private message when the user has **no** active state (`at_state(None)`).

**Why `at_state(None)`?**  
This prevents menu logic from interfering while the user is in the `WAITING_AMOUNT` flow. balethon's FSM cleanly separates the two branches.

**Three branches inside the function:**

```
message.text
  ├─ "/start" or unknown text  →  show ReplyKeyboard menu
  ├─ "💰 Custom Amount"        →  set_state("WAITING_AMOUNT"), prompt for number
  └─ product button text       →  look up product, send fixed-price invoice
```

**ReplyKeyboard layout:**

```python
ReplyKeyboard(
    [MENU_BTNS[0]],   # row 1: Coffee button
    [MENU_BTNS[1]],   # row 2: Cake button
    [MENU_BTNS[2]],   # row 3: Tea button
    [CUSTOM_BTN],     # row 4: Custom amount button
)
```

Each inner list is one **row**. Put multiple strings in the same list for a multi-column row.

---

### 4. `handle_pre_checkout` — Pre-Checkout Query Handler

```python
@bot.on_pre_checkout_query()
async def handle_pre_checkout(client, pre_checkout_query):
```

**When does it run?**  
Bale calls this **automatically** right before processing a payment. The bot has **10 seconds** to respond or the payment is cancelled.

**What it does:**

| Response | Code | Effect |
|---|---|---|
| Approve | `pre_checkout_query.answer(ok=True)` | Payment proceeds |
| Reject | `pre_checkout_query.answer(ok=False, error_message="Out of stock")` | Payment is cancelled, user sees the error message |

**Pre-checkout object fields:**

| Field | Description |
|---|---|
| `pre_checkout_query.id` | Must be echoed back (handled automatically by `.answer()`) |
| `pre_checkout_query.total_amount` | Amount the user is about to pay |
| `pre_checkout_query.invoice_payload` | The `payload` string you set in `send_invoice` |

> In a real shop you would check inventory, user eligibility, etc. here before approving.

---

## 🔄 Full Payment Flow Diagram

```
User taps a product button
        │
        ▼
handle_menu_buttons  →  client.send_invoice(...)
                                │
                                ▼
                    User sees invoice, taps "Pay"
                                │
                                ▼
                    handle_pre_checkout  →  answer(ok=True)
                                │
                                ▼
                    Bale processes payment
                                │
                                ▼
                    show_payment  →  reply with tracking code
```

---

## 🛡️ Security Checklist Before Pushing to GitHub

- [ ] Tokens are in `.env`, **not** hardcoded in `shop_bot.py`
- [ ] `.env` is listed in `.gitignore`
- [ ] You have run `git log` to confirm no previous commit contains real tokens
- [ ] `BOT_TOKEN` and `PAYMENT_TOKEN` placeholders in the code say `"YOUR_..._HERE"`

---

## 📦 Dependencies

```
balethon
```

Install with:

```bash
pip install balethon
```

---

## 📄 License

MIT — feel free to use this tutorial code in your own projects.
