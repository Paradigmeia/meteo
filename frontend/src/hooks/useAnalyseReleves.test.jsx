// @vitest-environment jsdom
import { renderHook, waitFor, cleanup } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useAnalyseReleves } from './useAnalyseReleves'

// Les tests d'isRangeTooLong ne couvrent que la fonction pure. Ceux-ci couvrent
// son *câblage* : c'est là qu'était le défaut trouvé en review de #58 — le
// graphique restait dessiné avec les relevés de la plage précédente, sous un
// bandeau annonçant qu'aucune donnée n'avait été chargée. Retirer le garde-fou
// du hook ne faisait alors échouer aucun test.

const PLAGE_OK = { from: '2026-01-01T00:00:00Z', to: '2026-01-08T00:00:00Z' }
const PLAGE_TROP_LONGUE = { from: '2020-01-01T00:00:00Z', to: '2026-01-01T00:00:00Z' }

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  window.fetch = vi.fn(() =>
    Promise.resolve({ ok: true, json: () => Promise.resolve([{ temperature: 20, humidite: 50, recu_le: '2026-01-02T00:00:00Z' }]) })
  )
})
afterEach(() => { cleanup(); vi.useRealTimers(); vi.restoreAllMocks() })

describe('useAnalyseReleves — garde-fou de plage', () => {
  it('charge normalement une plage admise', async () => {
    const { result } = renderHook(() => useAnalyseReleves(['salon'], '24h', PLAGE_OK))
    await waitFor(() => expect(result.current.data.salon).toHaveLength(1))
    expect(result.current.rangeTooLong).toBe(false)
    expect(window.fetch).toHaveBeenCalledTimes(1)
  })

  it('n\'envoie aucune requête quand la plage dépasse le plafond', async () => {
    const { result } = renderHook(() => useAnalyseReleves(['salon'], '24h', PLAGE_TROP_LONGUE))
    await waitFor(() => expect(result.current.rangeTooLong).toBe(true))
    expect(window.fetch).not.toHaveBeenCalled()
  })

  it('vide les données en passant à une plage trop longue', async () => {
    const { result, rerender } = renderHook(
      ({ plage }) => useAnalyseReleves(['salon'], '24h', plage),
      { initialProps: { plage: PLAGE_OK } },
    )
    await waitFor(() => expect(result.current.data.salon).toHaveLength(1))

    rerender({ plage: PLAGE_TROP_LONGUE })
    // Sans ce vidage, le graphique restait dessiné avec les relevés de la plage
    // précédente, sur un axe ne correspondant à aucune des dates saisies
    await waitFor(() => expect(result.current.data.salon ?? []).toHaveLength(0))
    expect(result.current.rangeTooLong).toBe(true)
  })

  it('ne remonte pas d\'échec de chargement : ce n\'est pas une panne mais une saisie', async () => {
    const { result } = renderHook(() => useAnalyseReleves(['salon'], '24h', PLAGE_TROP_LONGUE))
    await waitFor(() => expect(result.current.rangeTooLong).toBe(true))
    // `failed` déclenche le bandeau générique de #36 (« nouvelle tentative
    // automatique »), inactionnable ici : l'utilisateur doit corriger ses dates
    expect(result.current.failed).toBe(false)
  })

  it('repart quand la plage redevient admise', async () => {
    const { result, rerender } = renderHook(
      ({ plage }) => useAnalyseReleves(['salon'], '24h', plage),
      { initialProps: { plage: PLAGE_TROP_LONGUE } },
    )
    await waitFor(() => expect(result.current.rangeTooLong).toBe(true))
    rerender({ plage: PLAGE_OK })
    await waitFor(() => expect(result.current.data.salon).toHaveLength(1))
    expect(result.current.rangeTooLong).toBe(false)
  })
})
