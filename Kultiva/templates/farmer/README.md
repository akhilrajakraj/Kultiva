# Farmer Template Parity

This directory is the canonical Farmer-facing template boundary.

Migration rules:
- Preserve legacy route names and context contracts during migration.
- Do not remove legacy templates until all references and render paths are verified.
- Samsung-specific templates remain explicit variants until responsive parity is proven.
- Keep presentation concerns in templates/static assets; business logic remains in views/services.

Migration status: Phase 2 workflow entrypoints established for proposals, input marketplace, checkout, invoices, orders, seller discovery, and mock payments. Individual templates remain compatibility wrappers until dependency verification and view-path migration are complete.
