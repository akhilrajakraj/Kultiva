# Kultiva architecture migration

The repository is being transitioned from the legacy single Django application into bounded domain apps under `backend/apps`, an isolated AI layer, an explicit ML workspace, infrastructure configuration, and project documentation.

## Compatibility policy

The existing legacy application is intentionally preserved during the migration. Domain extraction will move behavior into the new apps incrementally, with tests and CI guarding each step.

## Domain map

- accounts: identity, authentication, roles
- farmers: farmer profiles and farm operations
- buyers: buyer and procurement workflows
- sellers: agricultural input sellers
- marketplace: listings and discovery
- orders: order lifecycle
- payments: payment orchestration
- escrow: trade escrow and settlement
- soil: soil reports and soil data
- weather: weather history and intelligence inputs
- advisory: agronomic advisory workflows
- reviews: unified reviews and trust
- notifications: user notifications
- analytics: reporting and metrics
- admin_portal: administrative workflows
