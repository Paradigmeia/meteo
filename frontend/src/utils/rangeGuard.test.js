import { describe, it, expect } from 'vitest'
import { isRangeTooLong, MAX_RANGE_HOURS } from './analyseUtils'

// Le serveur refuse une plage de plus d'un an par un 400 (issue #37). Ce garde-
// fou client existe pour que l'utilisateur lise « plage trop large » plutôt que
// « certaines données n'ont pas pu être chargées » — le seul message qu'il peut
// agir. Il doit donc refuser exactement ce que le serveur refuse : ni plus, ni
// moins, sinon on retombe soit sur le bandeau opaque, soit sur un blocage
// d'une plage que l'API aurait acceptée.

const jours = n => n * 24 * 3_600_000
const plage = (ms, depuis = Date.UTC(2026, 0, 1)) => ({
  from: new Date(depuis).toISOString(),
  to: new Date(depuis + ms).toISOString(),
})

describe('isRangeTooLong', () => {
  it('accepte une plage d\'exactement un an — la borne est inclusive des deux côtés', () => {
    expect(isRangeTooLong(plage(MAX_RANGE_HOURS * 3_600_000))).toBe(false)
  })

  it('refuse une seconde de plus', () => {
    expect(isRangeTooLong(plage(MAX_RANGE_HOURS * 3_600_000 + 1000))).toBe(true)
  })

  it('accepte les plages courantes', () => {
    for (const j of [1, 7, 30, 90, 364]) expect(isRangeTooLong(plage(jours(j)))).toBe(false)
  })

  it('refuse la plage absurde qui motivait l\'issue', () => {
    expect(isRangeTooLong({ from: '1970-01-01T00:00:00Z', to: '2100-01-01T00:00:00Z' })).toBe(true)
  })

  it('ne bloque rien quand la plage est absente ou incomplète — c\'est le mode période', () => {
    expect(isRangeTooLong(null)).toBe(false)
    expect(isRangeTooLong(undefined)).toBe(false)
    expect(isRangeTooLong({ from: '2026-01-01T00:00:00Z' })).toBe(false)
    expect(isRangeTooLong({ to: '2026-01-01T00:00:00Z' })).toBe(false)
  })

  it('ne bloque pas sur une date illisible — c\'est au serveur de la rejeter', () => {
    // Un NaN rendrait la comparaison fausse dans les deux sens ; on laisse
    // partir la requête, le 400 « format de date invalide » est plus précis
    expect(isRangeTooLong({ from: 'pas-une-date', to: '2026-01-01T00:00:00Z' })).toBe(false)
  })

  it('reste aligné sur le plafond du serveur', () => {
    expect(MAX_RANGE_HOURS).toBe(8760)
  })
})
