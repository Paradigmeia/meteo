import { readdirSync, readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import { describe, it, expect } from 'vitest'
import { ICON_NAMES } from '../utils/iconPaths'
import { WMO_ICONS, wmoIcon } from '../meteoUtils'

// Un nom d'icône inconnu ne produit ni erreur ni trace : il n'affiche
// simplement rien. C'est ce qui est arrivé à 'cloud-sun' et 'cloud-drizzle',
// absents de Tabler 3.19.0 — « Partiellement nuageux » et « Bruine » sont
// restés sans icône en production sans que personne le voie (issue #50).
// Ces tests ferment la porte à la répétition du cas.

const componentsDir = dirname(fileURLToPath(import.meta.url))

describe('noms d\'icônes', () => {
  it('couvre tous les codes météo WMO', () => {
    const manquants = Object.entries(WMO_ICONS)
      .filter(([, name]) => !ICON_NAMES.includes(name))
      .map(([code, name]) => `${code} → ${name}`)
    expect(manquants).toEqual([])
  })

  it('couvre l\'icône de repli des codes météo inconnus', () => {
    expect(ICON_NAMES).toContain(wmoIcon(-1))
  })

  it('couvre tous les noms littéraux passés à <Icon> dans les composants', () => {
    const utilises = new Set()
    for (const fichier of readdirSync(componentsDir).filter(f => f.endsWith('.jsx'))) {
      const source = readFileSync(join(componentsDir, fichier), 'utf8')
      for (const m of source.matchAll(/<Icon\s[^>]*name="([^"]+)"/g)) utilises.add(m[1])
    }
    // Le test ne vaut que s'il voit réellement des usages : sans cette borne,
    // un changement de syntaxe le rendrait vert et vide
    expect(utilises.size).toBeGreaterThanOrEqual(7)
    expect([...utilises].filter(n => !ICON_NAMES.includes(n))).toEqual([])
  })

  it('n\'embarque aucune icône inutilisée', () => {
    const sourcesJsx = readdirSync(componentsDir)
      .filter(f => f.endsWith('.jsx'))
      .map(f => readFileSync(join(componentsDir, f), 'utf8'))
      .join('')
    const referencees = new Set([
      ...Object.values(WMO_ICONS),
      ...[...sourcesJsx.matchAll(/<Icon\s[^>]*name="([^"]+)"/g)].map(m => m[1]),
    ])
    expect(ICON_NAMES.filter(n => !referencees.has(n))).toEqual([])
  })
})
