# Exploration report: Sign in, add Wireless Earbuds to the cart, open the cart, apply promo code SAVE20 and checkout

- Platform: android
- Goal reached: no (error screen)
- Steps: 8

## Steps

| # | Action | Element | Locator | Why |
| --- | --- | --- | --- | --- |
| 1 | type 'demo@shoplite.test' | Email | `id=com.shoplite:id/email` | fill email from test data |
| 2 | type | Password | `id=com.shoplite:id/password` | fill password from test data |
| 3 | tap | Sign in | `id=com.shoplite:id/submit_signin` | submit the field just filled |
| 4 | tap | Add to cart | `accessibility id=Add Wireless Earbuds to cart` | matches the goal: Add to cart |
| 5 | tap | Cart (1) | `id=com.shoplite:id/open_cart` | matches the goal: Cart |
| 6 | type 'SAVE20' | Promo code | `id=com.shoplite:id/promo_code` | fill promo from test data |
| 7 | tap | Apply | `id=com.shoplite:id/apply_promo` | submit the field just filled |
| 8 | tap | Checkout | `id=com.shoplite:id/checkout` | matches the goal: Checkout |

## Findings

### [Medium] ACCESSIBILITY: ImageButton (id=cart_icon) has no accessibility label

### [High] ERROR_SCREEN: "Something went wrong. Please try again." shown

Steps to reproduce:
1. Enter 'demo@shoplite.test' in Email
2. Enter <password> in Password
3. Tap Sign in
4. Tap Add to cart
5. Tap Cart (1)
6. Enter 'SAVE20' in Promo code
7. Tap Apply
8. Tap Checkout
