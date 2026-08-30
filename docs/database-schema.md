# Database Schema

Stage 3 defines the first persistent game-state schema in a single reproducible migration.
Supabase PostgreSQL is the authoritative source for every table in this document.

## Relationships

```text
auth.users
  ├─ profiles
  ├─ campaigns.owner_id
  ├─ campaign_members.user_id
  └─ characters.user_id

campaigns
  ├─ campaign_members
  ├─ characters
  ├─ scenes
  │    └─ entities
  ├─ pending_checks
  └─ game_events

characters
  ├─ inventory_items
  ├─ pending_checks
  └─ game_events
```

## Tables

| Table | Purpose |
|---|---|
| `profiles` | User-facing identity attached to `auth.users` |
| `campaigns` | Campaign ownership and current scene |
| `campaign_members` | Campaign membership and owner/player/GM role |
| `characters` | HP, four ability modifiers and character status |
| `scenes` | Persistent locations and scene-local state |
| `entities` | NPCs, enemies and interactable scene objects |
| `inventory_items` | Stackable character inventory |
| `pending_checks` | Server-authoritative unresolved and completed checks |
| `game_events` | Append-oriented history of meaningful game changes |

## Enforced invariants

- Auth user creation creates exactly one profile.
- Campaign creation registers its owner as an `owner` member.
- Campaign ownership cannot be transferred in the MVP.
- A campaign's current scene must belong to that campaign.
- An entity's scene and a check's character must belong to the same campaign as the row.
- Character modifiers are exactly one each of `0`, `1`, `2`, and `3`.
- `max_hp` is `10 + STR`, and current HP remains within `0..max_hp`.
- JSON state and event payload columns contain objects rather than arbitrary JSON values.
- Stored inventory quantity is positive; a zero quantity item must be deleted.
- Dice specifications contain only integer `count` and `sides` values in supported ranges.
- A campaign can have at most one `pending` check.
- A `resolved` check has a resolution timestamp, and other statuses do not.
- Mutable game-state rows refresh `updated_at` through database triggers.

## Security boundary

This migration establishes relational integrity but intentionally does not enable RLS. Stage 4
will enable RLS on every user-data table and add authenticated access policies. Until then, the
local schema is for development only and must not be exposed as a production Data API.

## Verification

```powershell
supabase db reset --local
supabase test db --local
supabase db lint --local --level warning
```

The pgTAP suite runs inside a transaction and rolls back all fixture data.

