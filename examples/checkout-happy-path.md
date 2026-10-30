# Exploration report: Sign in, add Wireless Earbuds to the cart, open the cart and checkout

- Platform: android
- Goal reached: yes (saw "Order placed")
- Steps: 6

## Steps

| # | Action | Element | Locator | Why |
| --- | --- | --- | --- | --- |
| 1 | type 'demo@shoplite.test' | Email | `id=com.shoplite:id/email` | fill email from test data |
| 2 | type | Password | `id=com.shoplite:id/password` | fill password from test data |
| 3 | tap | Sign in | `id=com.shoplite:id/submit_signin` | submit the field just filled |
| 4 | tap | Add to cart | `accessibility id=Add Wireless Earbuds to cart` | matches the goal: Add to cart |
| 5 | tap | Cart (1) | `id=com.shoplite:id/open_cart` | matches the goal: Cart |
| 6 | tap | Checkout | `id=com.shoplite:id/checkout` | matches the goal: Checkout |

## Findings

### [Medium] ACCESSIBILITY: ImageButton (id=cart_icon) has no accessibility label
