// @vitest-environment jsdom
import { render, screen, cleanup } from '@testing-library/react'
import { describe, it, expect, afterEach } from 'vitest'
import SondeCard from './SondeCard'

// Couvre le versant affichage de l'issue #43. Le backend renvoie désormais dans
// `recu_le` le plus récent des deux horodatages : une sonde dont seule
// l'humidité remonte n'est donc plus déclarée « hors ligne ». Encore faut-il
// que sa température figée soit signalée, sans quoi le correctif remplacerait
// un badge indu par un silence — la card paraîtrait saine avec une valeur
// vieille de plusieurs mois.

const MINUTE = 60 * 1000
const HEURE = 60 * MINUTE

const ilYA = ms => new Date(Date.now() - ms).toISOString()

function carte(dernier_releve, props = {}) {
  render(<SondeCard sonde={{ slug: 'salon', nom: 'Salon', dernier_releve }} {...props} />)
}

const marqueurs = () => [...document.querySelectorAll('.mesure-retard')].map(n => n.textContent)
const horsLigne = () => document.querySelector('.offline-badge') || screen.queryByLabelText('Hors ligne')

afterEach(cleanup)

describe.each([
  ['card compacte', {}],
  ['card pleine largeur', { fullWidth: true }],
])('%s', (_nom, props) => {
  it('ne marque rien quand les deux grandeurs arrivent ensemble', () => {
    const t = ilYA(5 * MINUTE)
    carte({ temperature: 21, humidite: 55, recu_le: t, recu_le_temp: t, recu_le_hum: t }, props)
    expect(marqueurs()).toEqual([])
    expect(horsLigne()).toBeNull()
  })

  it('marque la température quand elle seule a cessé de remonter', () => {
    // Le cas de l'issue : l'humidité arrive encore, la température date de 5 h.
    const hum = ilYA(2 * MINUTE)
    carte(
      { temperature: 21, humidite: 55, recu_le: hum, recu_le_temp: ilYA(5 * HEURE), recu_le_hum: hum },
      props,
    )
    // La sonde donne signe de vie : pas de badge hors ligne…
    expect(horsLigne()).toBeNull()
    // …mais la valeur affichée, elle, est périmée et le dit.
    expect(marqueurs()).toEqual(['il y a 5 h'])
  })

  it('marque l\'humidité quand elle seule a cessé de remonter', () => {
    const temp = ilYA(2 * MINUTE)
    carte(
      { temperature: 21, humidite: 55, recu_le: temp, recu_le_temp: temp, recu_le_hum: ilYA(5 * HEURE) },
      props,
    )
    expect(horsLigne()).toBeNull()
    expect(marqueurs()).toEqual(['il y a 5 h'])
  })

  it('ne marque pas un écart inférieur à 30 min', () => {
    // Deux relevés séparés de quelques minutes sont le cas nominal : le Shelly
    // envoie ses deux actions l'une après l'autre.
    const recent = ilYA(MINUTE)
    carte(
      { temperature: 21, humidite: 55, recu_le: recent, recu_le_temp: ilYA(20 * MINUTE), recu_le_hum: recent },
      props,
    )
    expect(marqueurs()).toEqual([])
  })

  it('garde le badge hors ligne quand plus rien ne remonte', () => {
    const vieux = ilYA(6 * HEURE)
    carte(
      { temperature: 21, humidite: 55, recu_le: vieux, recu_le_temp: vieux, recu_le_hum: vieux },
      props,
    )
    expect(horsLigne()).not.toBeNull()
    // Les deux grandeurs sont aussi vieilles l'une que l'autre : rien à
    // distinguer, le badge dit déjà tout.
    expect(marqueurs()).toEqual([])
  })

  it('ne marque rien quand le backend ne renvoie pas les horodatages par grandeur', () => {
    // Tolérance à une réponse ancienne : `recu_le_temp` est un champ ajouté par
    // #43, et le front est servi en statique — il peut tourner face à un backend
    // qui n'a pas encore redémarré.
    carte({ temperature: 21, humidite: 55, recu_le: ilYA(MINUTE) }, props)
    expect(marqueurs()).toEqual([])
  })
})
