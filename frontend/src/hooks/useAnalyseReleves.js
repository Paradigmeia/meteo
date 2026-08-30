import { useState, useEffect } from 'react'
import { isRangeTooLong } from '../utils/analyseUtils'

const API = import.meta.env.VITE_API_URL ?? ''

// Récupère en une fois les relevés bruts de toutes les sondes actives,
// indépendamment des cases cochées. Ce n'est pas un oubli : `key` sert de
// dépendance à l'effet ci-dessous, et la faire dépendre des cases relancerait un
// chargement complet à chaque coche — timer de rafraîchissement 30s remis à zéro
// et clignotement des courbes déjà affichées. Le surcoût est marginal,
// /api/sondes ne renvoyant que les sondes actives (cf. PLAN.md décision 9).
export function useAnalyseReleves(slugs, period, customRange) {
  const [data, setData] = useState({})
  const [failed, setFailed] = useState(false)
  const key = slugs.join(',')
  // Le serveur refuse une plage de plus d'un an (400, issue #37). Sans ce
  // contrôle en amont, l'échec remonterait par `failed` et l'utilisateur lirait
  // « certaines données n'ont pas pu être chargées » là où le problème est sa
  // sélection de dates, qu'il est le seul à pouvoir corriger.
  const tooLong = isRangeTooLong(customRange)

  useEffect(() => {
    const currentSlugs = key ? key.split(',') : []
    if (!currentSlugs.length || tooLong) return
    let cancelled = false
    let timer

    function buildQuery() {
      if (customRange?.from && customRange?.to) {
        return `from=${encodeURIComponent(customRange.from)}&to=${encodeURIComponent(customRange.to)}`
      }
      return `period=${period}`
    }

    // `first` distingue le chargement initial d'une plage d'un rafraîchissement.
    async function load(first) {
      const qs = buildQuery()
      // `null` = la requête de cette sonde a échoué, `[]` = elle a réussi et il
      // n'y a pas de relevé sur la plage. Confondre les deux faisait disparaître
      // le graphique sans le moindre message quand l'API renvoyait une erreur
      // (issue #36). Chaque sonde est isolée : une seule en échec ne doit pas
      // emporter l'affichage des autres.
      const results = await Promise.all(
        currentSlugs.map(slug =>
          window.fetch(`${API}/api/releves/${slug}?${qs}`)
            .then(res => (res.ok ? res.json() : null))
            .catch(() => null)
        )
      )
      if (!cancelled) {
        setData(prev => {
          const next = {}
          currentSlugs.forEach((slug, i) => {
            // Sur un rafraîchissement, un échec conserve la dernière donnée
            // bonne : c'est ce qu'annonce le bandeau (« affichage incomplet »),
            // et c'est déjà ce que font useSondes et useReleves. Au premier
            // chargement d'une plage en revanche, il faut vider — garder les
            // relevés de la plage précédente les dessinerait sur le mauvais axe.
            next[slug] = results[i] ?? (first ? [] : prev[slug] ?? [])
          })
          return next
        })
        setFailed(results.some(r => r === null))
      }
      if (!cancelled) timer = setTimeout(() => load(false), 30_000)
    }
    load(true)
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [key, period, customRange?.from, customRange?.to, tooLong])

  return { data, failed, rangeTooLong: tooLong }
}
