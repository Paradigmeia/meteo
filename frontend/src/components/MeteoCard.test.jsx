// @vitest-environment jsdom
import { render, screen, cleanup } from '@testing-library/react'
import { describe, it, expect, afterEach } from 'vitest'
import MeteoCard from './MeteoCard'
import { wmoLabel } from '../meteoUtils'

// Couvre le versant accessibilité de l'issue #55 : la condition météo d'un
// créneau horaire et la grandeur d'une valeur d'humidité sont portées
// uniquement par leur icône — masquées (aria-hidden) par défaut, elles
// n'étaient annoncées par aucun lecteur d'écran. La prop `label` d'Icon
// (role="img" + aria-label) les rend annonçables sans toucher aux icônes
// décoratives, dont le silence est lui-même un comportement recherché.

const HEURES = 26
// Codes WMO des créneaux rendus : les huit premiers distincts, le reste en
// « ciel dégagé » pour couvrir la largeur du strip de 24.
const CODES = Array.from({ length: HEURES }, (_, i) => [0, 3, 61, 63, 95, 1, 2, 45][i] ?? 0)

const prochaineHeure = () => {
  const t = new Date()
  t.setHours(t.getHours() + 1, 0, 0, 0)
  return t
}

// Tous les créneaux dans le futur certain : le strip part de l'index 0, le
// premier créneau est « Maint. », les 24 suivants sont rendus tels quels.
function meteoFixture() {
  const t0 = prochaineHeure()
  const times = [], temps = [], precip = [], codes = []
  for (let i = 0; i < HEURES; i++) {
    times.push(new Date(t0.getTime() + i * 3600 * 1000).toISOString())
    temps.push(20 + (i % 5))
    precip.push(i % 3 === 0 ? 30 : 0)
    codes.push(CODES[i])
  }
  return {
    current: { temperature_2m: 21.4, weathercode: 0, relative_humidity_2m: 63, wind_speed_10m: 6, wind_direction_10m: 337 },
    hourly: { time: times, temperature_2m: temps, precipitation_probability: precip, weathercode: codes },
    daily: { temperature_2m_min: [14, 12], temperature_2m_max: [24, 25], weathercode: [0, 61] },
  }
}

afterEach(cleanup)

describe('MeteoCard', () => {
  it('annonce la condition météo de chacun des 24 créneaux horaires', () => {
    const { container } = render(<MeteoCard meteo={meteoFixture()} />)
    const slots = [...container.querySelectorAll('.hour-slot')]
    expect(slots).toHaveLength(24)
    slots.forEach((slot, i) => {
      const ic = slot.querySelector('svg[role="img"]')
      expect(ic, `créneau ${i}`).not.toBeNull()
      expect(ic.getAttribute('aria-label')).toBe(wmoLabel(CODES[i]))
    })
  })

  it('annonce la grandeur de la goutte d\'humidité du bloc « maintenant »', () => {
    render(<MeteoCard meteo={meteoFixture()} />)
    expect(screen.getByRole('img', { name: 'Humidité' })).toBeTruthy()
  })

  it('laisse les icônes décoratives sans nom accessible', () => {
    render(<MeteoCard meteo={meteoFixture()} />)
    const nommees = screen.getAllByRole('img')
    expect(nommees).toHaveLength(25) // 24 créneaux + la goutte d'humidité
    nommees.forEach(ic => expect(ic.getAttribute('aria-label')).toBeTruthy())
    // Grande icône météo, vent et « Demain » : leur information est déjà dans
    // le texte adjacent, elles doivent rester masquées (aria-hidden).
    expect(document.querySelectorAll('svg[aria-hidden="true"]')).toHaveLength(3)
  })
})