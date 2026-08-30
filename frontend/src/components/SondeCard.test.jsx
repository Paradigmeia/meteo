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

// Chaque marqueur est lu SOUS sa grandeur : les collecter à plat laisserait
// passer une inversion température/humidité, les deux cas symétriques ayant
// alors le même contenu attendu (relevé en review de #64).
const marqueur = grandeur =>
  document.querySelector(`.sonde-${grandeur} .mesure-retard`)?.textContent ?? null

const horsLigne = () => document.querySelector('.offline-badge') || screen.queryByLabelText('Hors ligne')

afterEach(cleanup)

describe.each([
  ['card compacte', {}],
  ['card pleine largeur', { fullWidth: true }],
])('%s', (_nom, props) => {
  it('ne marque rien quand les deux grandeurs arrivent ensemble', () => {
    const t = ilYA(5 * MINUTE)
    carte({ temperature: 21, humidite: 55, recu_le: t, recu_le_temp: t, recu_le_hum: t }, props)
    expect([marqueur('temp'), marqueur('hum')]).toEqual([null, null])
    expect(horsLigne()).toBeNull()
  })

  it('marque la température, et elle seule, quand elle a cessé de remonter', () => {
    // Le cas de l'issue : l'humidité arrive encore, la température date de 5 h.
    const hum = ilYA(2 * MINUTE)
    carte(
      { temperature: 21, humidite: 55, recu_le: hum, recu_le_temp: ilYA(5 * HEURE), recu_le_hum: hum },
      props,
    )
    // La sonde donne signe de vie : pas de badge hors ligne…
    expect(horsLigne()).toBeNull()
    // …mais la valeur affichée, elle, est périmée et le dit.
    expect(marqueur('temp')).toBe('il y a 5 h')
    expect(marqueur('hum')).toBeNull()
  })

  it('marque l\'humidité, et elle seule, quand elle a cessé de remonter', () => {
    // Âge volontairement différent du cas précédent : si les deux marqueurs
    // étaient intervertis, le texte attendu changerait, pas seulement sa place.
    const temp = ilYA(2 * MINUTE)
    carte(
      { temperature: 21, humidite: 55, recu_le: temp, recu_le_temp: temp, recu_le_hum: ilYA(3 * HEURE) },
      props,
    )
    expect(horsLigne()).toBeNull()
    expect(marqueur('hum')).toBe('il y a 3 h')
    expect(marqueur('temp')).toBeNull()
  })

  it('ne marque pas un écart inférieur à 30 min', () => {
    // Deux relevés séparés de quelques minutes sont le cas nominal : le Shelly
    // envoie ses deux actions l'une après l'autre.
    const recent = ilYA(MINUTE)
    carte(
      { temperature: 21, humidite: 55, recu_le: recent, recu_le_temp: ilYA(20 * MINUTE), recu_le_hum: recent },
      props,
    )
    expect([marqueur('temp'), marqueur('hum')]).toEqual([null, null])
  })

  it('marque juste au-delà du seuil', () => {
    // Borne haute du seuil, celle qui fait la différence entre « nominal » et
    // « en retard » : sans elle, un seuil doublé passerait inaperçu.
    const recent = ilYA(MINUTE)
    carte(
      { temperature: 21, humidite: 55, recu_le: recent, recu_le_temp: ilYA(32 * MINUTE), recu_le_hum: recent },
      props,
    )
    expect(marqueur('temp')).toBe('il y a 32 min')
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
    expect([marqueur('temp'), marqueur('hum')]).toEqual([null, null])
  })

  it('affiche la card sans marqueur quand le backend ne renvoie pas les horodatages par grandeur', () => {
    // Le front est servi en statique : un bundle à jour peut tourner face à un
    // backend qui n'a pas encore redémarré, et `recu_le_temp` est un champ
    // ajouté par #43. On vérifie que la card reste lisible — pas seulement
    // qu'aucun marqueur n'apparaît, ce qui serait vrai même en cas d'exception.
    carte({ temperature: 21, humidite: 55, recu_le: ilYA(MINUTE) }, props)
    expect(screen.getByText('21.0°')).toBeTruthy()
    expect(screen.getByText(/il y a 1 min/)).toBeTruthy()
    expect([marqueur('temp'), marqueur('hum')]).toEqual([null, null])
  })

  it('reste affichable quand la sonde n\'a jamais envoyé de température', () => {
    // `dernier_releve` existe dès qu'UNE des deux grandeurs est présente : une
    // sonde configurée en humidité seule renvoie `temperature: null`. Sans
    // garde, `toFixed` lève et le dashboard entier disparaît — il n'y a pas
    // d'error boundary.
    const t = ilYA(2 * MINUTE)
    carte({ temperature: null, humidite: 55, recu_le: t, recu_le_temp: null, recu_le_hum: t }, props)
    expect(screen.getByText('55%')).toBeTruthy()
    expect(document.querySelector('.sonde-card')).not.toBeNull()
  })
})
