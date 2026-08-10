# Farmer Template Parity

This directory is the canonical Farmer-facing template boundary.

Migration rules:
- Preserve legacy route names and context contracts during migration.
- Do not remove legacy templates until all references and render paths are verified.
- Samsung-specific templates remain explicit variants until responsive parity is proven.
- Keep presentation concerns in templates/static assets; business logic remains in views/services.

Migration status: Phase 1 boundary established; individual templates are migrated only after dependency verification.
