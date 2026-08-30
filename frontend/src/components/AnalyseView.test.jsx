// @vitest-environment jsdom
import { render, screen, waitFor, fireEvent, cleanup } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import AnalyseView from './AnalyseView'

// Couvre le rendu du bandeau « plage trop large » et sa distinction d'avec le
// bandeau d'échec générique de #36. Sans ces tests, masquer le message ne
// faisait échouer aucune vérification — c'est ce qu'a montré la review de #58.

const SONDES = [{ slug: 'salon', nom: 'Salon' }]

beforeEach(() => {
  window.fetch = vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve([]) }))
  window.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
  window.localStorage.clear()
})
afterEach(() => { cleanup(); vi.restoreAllMocks() })

// Le texte du bandeau est coupé en plusieurs nœuds par l'interpolation JSX
// ({MAX_RANGE_HOURS / 24}), que les requêtes par texte de testing-library ne
// recollent pas. On interroge donc l'élément et son textContent.
const bandeau = () => document.querySelector('.analyse-error')

function saisirPlage(from, to) {
  const champs = document.querySelectorAll('input[type="datetime-local"]')
  expect(champs).toHaveLength(2)
  fireEvent.change(champs[0], { target: { value: from } })
  fireEvent.change(champs[1], { target: { value: to } })
}

describe('AnalyseView — bandeau de plage trop large', () => {
  it('n\'affiche rien tant que la plage est admise', async () => {
    render(<AnalyseView sondes={SONDES} onBack={() => {}} />)
    await waitFor(() => expect(screen.getByText(/Vue Analyse/)).toBeTruthy())
    saisirPlage('2026-01-01T00:00', '2026-02-01T00:00')
    await waitFor(() => expect(window.fetch).toHaveBeenCalledWith(expect.stringContaining('from=')))
    expect(bandeau()).toBeNull()
  })

  it('affiche le bandeau et son mode d\'emploi au-delà du plafond', async () => {
    render(<AnalyseView sondes={SONDES} onBack={() => {}} />)
    await waitFor(() => expect(screen.getByText(/Vue Analyse/)).toBeTruthy())
    saisirPlage('2020-01-01T00:00', '2026-01-01T00:00')
    // Le message doit dire la limite ET quoi faire : un simple « erreur » ne
    // permettrait pas à l'utilisateur de corriger sa saisie
    await waitFor(() => expect(bandeau()?.textContent).toMatch(/Plage trop large/))
    expect(bandeau().textContent).toMatch(/365 jours/)
    expect(bandeau().textContent).toMatch(/[Rr]esserrez/)
  })

  it('ne conseille pas de cocher une case alors qu\'une sonde est déjà cochée', async () => {
    render(<AnalyseView sondes={SONDES} onBack={() => {}} />)
    await waitFor(() => expect(screen.getByText(/Vue Analyse/)).toBeTruthy())
    saisirPlage('2020-01-01T00:00', '2026-01-01T00:00')
    await waitFor(() => expect(bandeau()).not.toBeNull())
    // La zone du graphique affichait « Cochez au moins une donnée » — un
    // contresens quand la sonde est cochée et que le problème est la plage
    const carte = document.querySelector('.chart-card')
    expect(carte.textContent).not.toMatch(/Cochez/)
    expect(carte.textContent).toMatch(/resserrez les dates/i)
  })

  it('disparaît dès que les dates sont resserrées', async () => {
    render(<AnalyseView sondes={SONDES} onBack={() => {}} />)
    await waitFor(() => expect(screen.getByText(/Vue Analyse/)).toBeTruthy())
    saisirPlage('2020-01-01T00:00', '2026-01-01T00:00')
    await waitFor(() => expect(bandeau()).not.toBeNull())
    saisirPlage('2025-12-01T00:00', '2026-01-01T00:00')
    await waitFor(() => expect(bandeau()).toBeNull())
  })
})
