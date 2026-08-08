// ABOUTME: The cascading dogma category → group filter, whose option lists come
// ABOUTME: from the server and whose group list is scoped to the chosen categories.
import { useState } from 'react'
import { CheckboxField } from '../../../components/Checkbox'
import { Input } from '../../../components/Input'
import type { ContractSearch } from '../filters'
import { useTaxonomy } from '../hooks/useTaxonomy'

/** The shared shell both fieldsets wear — the region list's, one level in. */
function IdFieldset({
  legend,
  selectedCount,
  describedBy,
  description,
  children,
}: {
  legend: string
  selectedCount: number
  describedBy?: string
  description?: string
  children: React.ReactNode
}) {
  return (
    <fieldset aria-describedby={describedBy}>
      <legend className="text-label mb-1.5">
        {legend}
        {selectedCount > 0 ? (
          <span className="ml-1.5 rounded-sm bg-brand-wash px-1 font-mono text-brand normal-case">
            {selectedCount}
          </span>
        ) : null}
      </legend>
      {description !== undefined ? (
        // Polite live region, not just a description: a described-by sentence is
        // read when focus reaches the fieldset, and the reader who just changed
        // the category is standing on a checkbox two fieldsets up. Criterion 12
        // asks for the change itself to be announced.
        <p id={describedBy} role="status" aria-live="polite" className="mb-1.5 text-xs text-ink-faint">
          {description}
        </p>
      ) : null}
      {children}
    </fieldset>
  )
}

/** The scroll cap the region list uses, so the rail cannot grow without bound. */
const LIST_CLASS =
  'max-h-40 overflow-y-auto rounded-sm border border-line bg-surface px-1.5 py-1'

export function TaxonomyFilter({
  search,
  onUpdate,
}: {
  search: ContractSearch
  onUpdate: (patch: Partial<ContractSearch>) => void
}) {
  const { data } = useTaxonomy()
  const [groupQuery, setGroupQuery] = useState('')

  const selectedCategories = new Set(search.category_id ?? [])
  const selectedGroups = new Set(search.group_id ?? [])
  const categories = data?.categories ?? []
  const groups = data?.groups ?? []

  // With no category chosen the scope is the whole taxonomy: an empty selection
  // is "no category restriction", not "no groups". A group whose category the
  // corpus never named stays reachable only in that unscoped state — it belongs
  // under no checkbox that could bring it back.
  const inScope = (categoryId: number | null | undefined) =>
    selectedCategories.size === 0 || (categoryId != null && selectedCategories.has(categoryId))
  const scopedGroups = groups.filter((group) => inScope(group.category_id))
  const query = groupQuery.trim().toLowerCase()
  const visibleGroups = query
    ? scopedGroups.filter((group) => group.name.toLowerCase().includes(query))
    : scopedGroups

  const toggleCategory = (id: number, checked: boolean) => {
    const next = new Set(selectedCategories)
    if (checked) next.add(id)
    else next.delete(id)
    const categoryIds = [...next].sort((a, b) => a - b)
    // Narrowing the category scope takes its groups with it, in the SAME
    // navigation: a group left behind in the URL keeps filtering with no
    // visible control to clear it. Widening to the empty selection prunes
    // nothing, because everything is back in scope.
    const survivingGroups =
      categoryIds.length === 0
        ? [...selectedGroups]
        : groups
            .filter((group) => selectedGroups.has(group.group_id))
            .filter((group) => group.category_id != null && next.has(group.category_id))
            .map((group) => group.group_id)
    onUpdate({
      category_id: categoryIds.length > 0 ? categoryIds : undefined,
      group_id: survivingGroups.length > 0 ? survivingGroups.sort((a, b) => a - b) : undefined,
    })
  }

  const toggleGroup = (id: number, checked: boolean) => {
    const next = new Set(selectedGroups)
    if (checked) next.add(id)
    else next.delete(id)
    onUpdate({ group_id: next.size > 0 ? [...next].sort((a, b) => a - b) : undefined })
  }

  return (
    <>
      <IdFieldset legend="Category" selectedCount={selectedCategories.size}>
        <div className={LIST_CLASS}>
          {categories.length === 0 ? (
            <p className="px-1 py-2 text-xs text-ink-faint">No category in the corpus yet</p>
          ) : (
            categories.map((category) => (
              <CheckboxField
                key={category.category_id}
                label={category.name}
                checked={selectedCategories.has(category.category_id)}
                onChange={(checked) => toggleCategory(category.category_id, checked)}
              />
            ))
          )}
        </div>
      </IdFieldset>

      <IdFieldset
        legend="Group"
        selectedCount={selectedGroups.size}
        describedBy="group-filter-scope"
        // Criterion 12 wants the cascade announced; plain text says it to
        // everyone rather than to screen readers alone. It follows the selection
        // because a static "within the selected categories" is simply false
        // while none are selected — and it carries the count because that is
        // what makes each category change audible rather than only the first.
        // The count is the CATEGORY scope, not the type-ahead's visible list:
        // one announcement per click, not one per keystroke.
        description={
          selectedCategories.size > 0
            ? `${scopedGroups.length} group${scopedGroups.length === 1 ? '' : 's'} within the selected categories`
            : `All ${groups.length} group${groups.length === 1 ? '' : 's'}; select a category to narrow this list`
        }
      >
        <label className="mb-1.5 block">
          <span className="sr-only">Filter group list</span>
          <Input
            type="search"
            placeholder="Filter groups…"
            value={groupQuery}
            onChange={(event) => setGroupQuery(event.target.value)}
          />
        </label>
        <div className={LIST_CLASS}>
          {visibleGroups.length === 0 ? (
            <p className="px-1 py-2 text-xs text-ink-faint">
              {query ? `No group matches “${groupQuery}”` : 'No group in the selected categories'}
            </p>
          ) : (
            visibleGroups.map((group) => (
              <CheckboxField
                key={group.group_id}
                label={group.name}
                checked={selectedGroups.has(group.group_id)}
                onChange={(checked) => toggleGroup(group.group_id, checked)}
              />
            ))
          )}
        </div>
      </IdFieldset>
    </>
  )
}
