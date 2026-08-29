import { readdirSync, readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join, resolve } from 'node:path'
import { describe, it, expect } from 'vitest'
import { ICON_NAMES, ICON_PATHS } from './iconPaths'
import { WMO_ICONS, wmoIcon } from '../meteoUtils'

// Un nom d'icône inconnu ne produit ni erreur ni trace : il n'affiche
// simplement rien. C'est ce qui est arrivé à 'cloud-sun' et 'cloud-drizzle',
// absents de Tabler 3.19.0 — « Partiellement nuageux » et « Bruine » sont
// restés sans icône en production sans que personne le voie (issue #50).
// Un tracé vide ou tronqué est tout aussi silencieux, d'où les vérifications
// de forme : c'est la même panne, un cran plus loin.
//
// Ce fichier ne teste que la cohérence des noms et des tracés, pas le rendu
// d'Icon.jsx — le vérifier supposerait un DOM, donc jsdom, que le projet évite
// (cf. PLAN.md décision 14). Son nom le dit, pour ne rien promettre de plus.

const srcDir = resolve(dirname(fileURLToPath(import.meta.url)), '..')

function sourcesJsx(dir = srcDir) {
  return readdirSync(dir, { withFileTypes: true }).flatMap(entry => {
    const chemin = join(dir, entry.name)
    if (entry.isDirectory()) return sourcesJsx(chemin)
    return entry.name.endsWith('.jsx') ? [readFileSync(chemin, 'utf8')] : []
  })
}

const nomsLitteraux = () => {
  const trouves = new Set()
  for (const source of sourcesJsx()) {
    for (const m of source.matchAll(/<Icon\s[^>]*name="([^"]+)"/g)) trouves.add(m[1])
  }
  return trouves
}

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

  it('couvre tous les noms littéraux passés à <Icon> dans src/', () => {
    const utilises = nomsLitteraux()
    expect([...utilises].filter(n => !ICON_NAMES.includes(n))).toEqual([])

    // Sans ce comptage, une syntaxe d'appel que la regex ne verrait plus
    // rendrait le test vert et vide. Chaque <Icon> doit être vu, soit avec un
    // nom littéral, soit avec un nom calculé — la somme doit retomber juste.
    const source = sourcesJsx().join('')
    const total = (source.match(/<Icon\s/g) ?? []).length
    const litteraux = (source.match(/<Icon\s[^>]*name="/g) ?? []).length
    const calcules = (source.match(/<Icon\s[^>]*name={/g) ?? []).length
    expect(total).toBeGreaterThanOrEqual(12)
    expect(litteraux + calcules).toBe(total)
  })

  it('n\'embarque aucune icône inutilisée', () => {
    const referencees = new Set([...Object.values(WMO_ICONS), ...nomsLitteraux()])
    expect(ICON_NAMES.filter(n => !referencees.has(n))).toEqual([])
  })
})

describe('tracés', () => {
  it('donne à chaque icône au moins un tracé exploitable', () => {
    const invalides = Object.entries(ICON_PATHS).filter(([, paths]) =>
      !Array.isArray(paths) || paths.length === 0 ||
      paths.some(d => typeof d !== 'string' || !d.trim().startsWith('M'))
    ).map(([name]) => name)
    expect(invalides).toEqual([])
  })
})
