# Fixes applied

## Messaging
- Removed duplicate `openChat` and `sendChat` implementations.
- Added a direct **Chat seller** button to real seller listings.
- Added message navigation for logged-in users.
- Fixed unsafe inline user-name handling that could break chat buttons.
- Added safer conversation opening and self-chat prevention.
- Added message indexes and product validation.
- Buyer orders now expose a Chat seller action when a seller exists.

## Product UI
- Replaced fragile name-based seller matching with real product and seller IDs.
- Combined search, category, price, stock, rating and sorting into one renderer.
- Added review averages to the public products API.

## Backend
- Consolidated marketplace support-table initialization.
- Protected order-tracking access so unrelated users cannot read or update tracking.
- Added database indexes for messages.

## Local startup
- Rebuilt `Run_CampusCart.bat` to create a local virtual environment and install dependencies automatically.

## Cleanup
- Removed old duplicate upgrade/readme files.
- Added a concise README and this fixes list.
