# Spec: Heroicons Navigation Icons

> Completed: 2026-04-27

## Background / Problem

The bottom navigation currently uses custom inline SVG icons. The requested UI change is to standardize navigation icons on Heroicons, using outline icons by default and solid icons only for the active tab.

## Goals

- Replace bottom navigation custom SVGs with Heroicons wrappers.
- Use outline icons for inactive navigation tabs.
- Use solid icons for active navigation tabs.
- Do not use the brand color for active navigation icons or labels.
- Remove the obsolete custom navigation icon draft asset.

## Design

### Approach

Keep the existing `NavIcons` wrapper module as the single bottom-nav icon interface, but implement each wrapper with paired Heroicons outline/solid components. Pass `active` from `BottomNav` to choose the variant. Update active tab text color from brand to foreground.

### Primary Files

- `app/package.json` - add `@heroicons/react`.
- `app/src/components/base/NavIcons.tsx` - replace inline SVGs with Heroicons wrappers.
- `app/src/components/layout/BottomNav.tsx` - pass active state to icons and remove brand active color.
- `app/public/nav-icons-draft.svg` - remove obsolete custom icon draft.

## Implementation Checklist

- [x] Add Heroicons dependency to the app workspace.
- [x] Replace custom nav SVG wrappers with Heroicons outline/solid wrappers.
- [x] Update bottom navigation active styles to avoid brand color.
- [x] Remove obsolete custom navigation icon draft asset.
- [x] Type check passes (`pnpm -C app exec tsc --noEmit`).
- [x] Tests pass (`pnpm -C app test`).

## Risks / Open Questions

- None.
