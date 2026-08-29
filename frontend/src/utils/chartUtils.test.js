import { describe, it, expect } from 'vitest'
import { viewBoxXFromRect, viewBoxXFromClient, viewBoxXFromPointerEvent } from './chartUtils'

// Géométrie curseur → viewBox (issues #26 et #30). viewBoxXFromRect est
// l'équivalent arithmétique de la conversion par matrice pour le
// preserveAspectRatio par défaut ("xMidYMid meet") : c'est elle qu'on teste,
// la matrice étant fournie par le navigateur.

const rect = (left, width, height) => ({ left, width, height })
const matrix = (a, b, c, d, e, f) => ({ a, b, c, d, e, f })

describe('viewBoxXFromRect', () => {
  it('remplit la largeur quand la boîte est plus étroite que le viewBox (vue Détail mobile)', () => {
    // Shell mobile : boîte de 360px pour un viewBox de 360 → échelle 1, pas de vide
    expect(viewBoxXFromRect(0, rect(0, 360, 200), 360, 200)).toBe(0)
    expect(viewBoxXFromRect(180, rect(0, 360, 200), 360, 200)).toBe(180)
    // Boîte de 300px : le contenu est réduit, toujours sans vide latéral
    expect(viewBoxXFromRect(150, rect(0, 300, 166.67), 360, 200)).toBeCloseTo(180, 1)
  })

  it('tient compte du letterboxing horizontal quand la boîte est plus large', () => {
    // Carte de 1500px, viewBox de 900 de large sur 220 de haut : la hauteur
    // limite l'échelle à 1, le contenu est centré et laisse 300px de vide à gauche
    expect(viewBoxXFromRect(300, rect(0, 1500, 220), 900, 220)).toBe(0)
    expect(viewBoxXFromRect(1200, rect(0, 1500, 220), 900, 220)).toBe(900)
    expect(viewBoxXFromRect(750, rect(0, 1500, 220), 900, 220)).toBe(450)
    // C'était le bug #26 : la règle de trois donnait 180 au lieu de 0
    expect((300 / 1500) * 900).toBe(180)
  })

  it('décale l\'origine avec la position de la boîte dans la page', () => {
    expect(viewBoxXFromRect(500, rect(200, 1500, 220), 900, 220)).toBe(0)
  })

  it('renvoie null sur une boîte dégénérée plutôt qu\'une abscisse absurde', () => {
    expect(viewBoxXFromRect(100, rect(0, 0, 0), 900, 220)).toBeNull()
    expect(viewBoxXFromRect(100, rect(0, 1500, 0), 900, 220)).toBeNull()
    expect(viewBoxXFromRect(100, null, 900, 220)).toBeNull()
  })
})

describe('vue Détail mobile — équivalence avec l\'ancienne règle de trois', () => {
  // HistoriqueChart : viewBox 360×200, hauteur rendue fixée à 200px, largeur
  // capée par .app-shell (max-width 390px) donc toujours ≤ 360 une fois les
  // marges retirées. Dans ce régime le contenu remplit la largeur sans vide
  // latéral et le nouveau calcul doit rendre exactement l'ancien.
  const legacy = (clientX, box) => ((clientX - box.left) / box.width) * 360

  it('rend les mêmes abscisses que l\'ancien calcul tant que la boîte reste sous 360px', () => {
    for (const width of [280, 320, 358, 360]) {
      const box = rect(16, width, 200)
      for (const clientX of [16, 100, 16 + width / 2, 16 + width]) {
        expect(viewBoxXFromRect(clientX, box, 360, 200)).toBeCloseTo(legacy(clientX, box), 10)
      }
    }
  })

  it('diverge de l\'ancien calcul dès que la boîte dépasse 360px (le bug #26 qui reviendrait)', () => {
    const box = rect(0, 800, 200)
    expect(viewBoxXFromRect(220, box, 360, 200)).toBe(0)
    expect(legacy(220, box)).toBeCloseTo(99, 0)
  })
})

describe('viewBoxXFromClient', () => {
  it('renvoie null sans matrice', () => {
    expect(viewBoxXFromClient(100, 50, null)).toBeNull()
    expect(viewBoxXFromClient(100, 50, undefined)).toBeNull()
  })

  it('renvoie null si la matrice ne sait pas s\'inverser', () => {
    expect(viewBoxXFromClient(100, 50, {})).toBeNull()
  })

  it('applique la matrice inverse', () => {
    // Matrice inverse équivalant au cas letterboxé ci-dessus :
    // échelle 1, contenu décalé de 300px vers la droite
    const ctm = { inverse: () => matrix(1, 0, 0, 1, -300, 0) }
    expect(viewBoxXFromClient(300, 10, ctm)).toBe(0)
    expect(viewBoxXFromClient(1200, 10, ctm)).toBe(900)
  })

  it('renvoie null si la matrice n\'est pas inversible', () => {
    // inverse() d'une matrice singulière rend une matrice de NaN
    const ctm = { inverse: () => matrix(NaN, NaN, NaN, NaN, NaN, NaN) }
    expect(viewBoxXFromClient(300, 10, ctm)).toBeNull()
  })
})

describe('viewBoxXFromPointerEvent', () => {
  const svg = (overrides = {}) => ({
    getBoundingClientRect: () => rect(0, 1500, 220),
    viewBox: { baseVal: { x: 0, width: 900, height: 220 } },
    ...overrides,
  })

  it('utilise la matrice quand elle est disponible', () => {
    const target = svg({ getScreenCTM: () => ({ inverse: () => matrix(1, 0, 0, 1, -300, 0) }) })
    expect(viewBoxXFromPointerEvent({ currentTarget: target, clientX: 1200, clientY: 10 })).toBe(900)
  })

  it('retombe sur la géométrie de la boîte sans matrice', () => {
    expect(viewBoxXFromPointerEvent({ currentTarget: svg(), clientX: 300, clientY: 10 })).toBe(0)
  })

  it('lit le viewBox de l\'élément survolé, pas une dimension passée par l\'appelant', () => {
    // Mode Séparé : deux panneaux de hauteurs différentes partagent les
    // gestionnaires. Panneau de 110 de haut rendu sur 110px → échelle 1500/900
    // impossible, c'est la hauteur qui limite : 110/110 = 1, vide de 300px
    const panel = svg({
      getBoundingClientRect: () => rect(0, 1500, 110),
      viewBox: { baseVal: { x: 0, width: 900, height: 110 } },
    })
    expect(viewBoxXFromPointerEvent({ currentTarget: panel, clientX: 300, clientY: 10 })).toBe(0)
  })

  it('prend le premier point de contact sur un évènement tactile', () => {
    const event = { currentTarget: svg(), touches: [{ clientX: 1200, clientY: 10 }] }
    expect(viewBoxXFromPointerEvent(event)).toBe(900)
  })

  it('renvoie null sur un évènement tactile sans point de contact', () => {
    expect(viewBoxXFromPointerEvent({ currentTarget: svg(), touches: [] })).toBeNull()
  })
})
