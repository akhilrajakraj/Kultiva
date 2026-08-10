# Kultiva Template Migration

This directory is the new template boundary for the legacy-to-domain migration.

## Migration rule

Legacy templates under `templates/` remain the compatibility source until each template has been:

1. inventoried against the legacy view that renders it;
2. checked for every `{% url %}`, `{% include %}`, `{% extends %}`, `{% static %}`, form action, AJAX endpoint, JavaScript selector, context variable, and media reference;
3. copied into the appropriate domain directory without changing behavior;
4. wired to the extracted view and URL name;
5. covered by a render/integration regression test;
6. verified for desktop and Samsung-specific variants where both existed;
7. removed from the legacy location only after parity is proven.

## Domain layout

```text
frontend/templates/
├── shared/       # public/auth/shared layouts and reusable fragments
├── admin/        # administration UI
├── farmers/      # farmer workflows
├── buyers/       # buyer workflows
├── sellers/      # seller workflows
├── payments/     # payment gateway/checkout UI
└── trade/        # proposal/escrow/trade UI
```

The legacy template tree contains a large set of role-specific HTML files, including separate `-samsung.html` variants. Those variants are intentionally retained during parity verification; they must not be silently discarded.

## Do not delete legacy templates yet

The old `templates/` directory is still a compatibility boundary. A template is eligible for removal only when its new location has the same rendered behavior and the final reference scan shows no remaining dependency on the old path.
