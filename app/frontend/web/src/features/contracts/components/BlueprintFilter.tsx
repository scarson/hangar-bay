// ABOUTME: The runs / material-efficiency / time-efficiency bounds — three
// ABOUTME: independent windows over a contract's offered blueprint copies.
import { Input } from '../../../components/Input'
import type { ContractSearch } from '../filters'

/**
 * The three families are separate EXISTS clauses on the wire (§3.1): the two
 * bounds of one family must land on the SAME offered item, while different
 * families may be satisfied by different ones. That is why they are three
 * labelled pairs rather than one composite control — a reader filtering on ME
 * should not have to state a runs window they do not care about.
 */
const FAMILIES: { legend: string; min: keyof ContractSearch; max: keyof ContractSearch; noun: string }[] = [
  { legend: 'Runs', min: 'min_runs', max: 'max_runs', noun: 'runs' },
  { legend: 'Material efficiency', min: 'min_me', max: 'max_me', noun: 'material efficiency' },
  { legend: 'Time efficiency', min: 'min_te', max: 'max_te', noun: 'time efficiency' },
]

export function BlueprintFilter({
  search,
  onUpdate,
}: {
  search: ContractSearch
  /** Typed bounds fire per keystroke, so they navigate with replace like the price pair. */
  onUpdate: (patch: Partial<ContractSearch>, options?: { replace?: boolean }) => void
}) {
  // An emptied box is the ABSENCE of a bound, not a zero: min_me=0 matches every
  // blueprint that has any ME at all, which is a filter rather than the lack of
  // one. Same contract the price pair keeps.
  const bound = (key: keyof ContractSearch, raw: string) =>
    onUpdate({ [key]: raw === '' ? undefined : Number(raw) }, { replace: true })

  return (
    <>
      {FAMILIES.map((family) => (
        <fieldset key={family.legend}>
          <legend className="text-label mb-1.5">{family.legend}</legend>
          <div className="flex items-center gap-2">
            <label className="flex-1">
              <span className="sr-only">Minimum {family.noun}</span>
              <Input
                type="number"
                min="0"
                placeholder="Min"
                className="text-data"
                value={(search[family.min] as number | undefined) ?? ''}
                onChange={(event) => bound(family.min, event.target.value)}
              />
            </label>
            <span aria-hidden="true" className="text-ink-faint">
              –
            </span>
            <label className="flex-1">
              <span className="sr-only">Maximum {family.noun}</span>
              <Input
                type="number"
                min="0"
                placeholder="Max"
                className="text-data"
                value={(search[family.max] as number | undefined) ?? ''}
                onChange={(event) => bound(family.max, event.target.value)}
              />
            </label>
          </div>
        </fieldset>
      ))}
    </>
  )
}
