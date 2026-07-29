# Module RBAC

## Roles

- `superadmin`: global system role.
- `admin`: module membership role.
- `user`: module membership role.

## Example

```text
User A
  system_role: null
  memberships:
    HQA: admin
    HQS: user
```

## Enforcement

The identity service embeds module permissions in short-lived access tokens. Every domain service verifies the token signature and required permission. Frontend guards do not replace backend authorization.

## Default HQA permissions

Admin:

- `hqa.dashboard.view`
- `hqa.listings.view`
- `hqa.listings.export`
- `hqa.sync.run`
- `hqa.sync.view`
- `hqa.users.view`
- `hqa.users.manage`

User:

- `hqa.dashboard.view`
- `hqa.listings.view`
- `hqa.sync.view`
