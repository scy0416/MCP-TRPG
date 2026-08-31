# Database Security

Stage 4 establishes the database authorization boundary. Relational constraints still enforce
data integrity, while grants and Row Level Security (RLS) decide which authenticated identity can
see or change each row.

## Trust model

- Every public application table has RLS enabled.
- `anon` has no application-table privileges and cannot call authorization helpers.
- Normal MCP requests use the caller's authenticated JWT, so `auth.uid()` remains the authority.
- Server secrets map to the trusted `service_role`, bypass RLS, and are reserved for explicit
  maintenance or transaction paths that cannot safely run as the caller.
- `SECURITY DEFINER` authorization helpers live in the non-exposed `private` schema, use an empty
  `search_path`, and are executable only by `authenticated`.
- RLS is defense in depth. MCP Tools must still validate inputs and legal game-state transitions.

## Access matrix

| Resource | Read | Create | Update | Delete |
|---|---|---|---|---|
| Profiles | self and shared-campaign users | Auth trigger only | self display name | No |
| Campaigns | members | authenticated owner | owner or GM, mutable fields only | owner |
| Memberships | campaign members | owner adds player/GM | owner changes non-owner role | owner removes non-owner |
| Characters | campaign members | member for self | character owner or campaign manager; identity fields fixed | campaign owner |
| Scenes and entities | campaign members | owner or GM | owner or GM; relationship fields fixed | owner or GM |
| Inventory | campaign members | character controller | character controller; relationship fields fixed | character controller |
| Pending checks | campaign members | character controller | character controller; resolution fields only | character controller |
| Game events | campaign members | character controller, or manager for campaign-level events | No | No |

Here, a character controller is its owning user or a campaign `owner`/`gm`. A campaign manager is
an `owner`/`gm`. The owner membership row cannot be changed or deleted through authenticated
policies.

`game_events` is append-only for authenticated users: the role has no `UPDATE` or `DELETE` grant,
not merely a filtering policy. Trusted maintenance access remains available to `service_role`.

Core campaign and character creation uses authenticated-only, fixed-search-path Supabase RPCs.
They derive `owner_id`/`user_id` from `auth.uid()`, enforce membership for character creation,
and append the corresponding creation event in the same transaction. The MCP server never accepts
an arbitrary owner or caller identity from the AI.

## Structural immutability

Authenticated `UPDATE` grants are limited to mutable columns. IDs, campaign/character foreign
keys, ownership, creator identity, ability modifiers and creation timestamps cannot be rewritten
through the Data API. This prevents a user from moving an otherwise authorized row into a different
campaign or character by supplying another UUID.

## Verification

```powershell
.\scripts\supabase.ps1 db reset --local
.\scripts\supabase.ps1 test db --local
.\scripts\supabase.ps1 db lint --local --level warning
```

The pgTAP security suite runs as `authenticated` identities for an owner, player and outsider. It
checks membership-scoped reads, cross-user UUID attacks, role-specific writes, relationship-column
immutability, append-only events, anonymous denial and trusted service access. All fixtures are
rolled back after the test.
