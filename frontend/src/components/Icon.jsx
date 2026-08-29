import { ICON_PATHS } from '../utils/iconPaths'

// Rend un tracé Tabler en 1em et currentColor, comme le faisait le glyphe de
// police qu'il remplace (issue #50) : les `style={{ fontSize, color }}` des
// composants et la règle `.hour-icon` d'App.css s'appliquent sans changement.
// `label` pour une icône qui porte seule une information — sans elle, l'icône
// est décorative et masquée aux lecteurs d'écran. C'était déjà le cas avec la
// police remplacée, dont le glyphe venait d'un `content` sur un codepoint de la
// zone à usage privé : rien d'annonçable. La prop rend le cas réparable au
// point d'appel plutôt qu'au fond du composant.
export default function Icon({ name, className, style, label }) {
  const paths = ICON_PATHS[name]
  // Un nom inconnu ne doit pas casser le rendu de la carte qui le contient.
  // Icon.test.js garantit par ailleurs qu'il n'en existe aucun.
  if (!paths) return null
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"
      width="1em" height="1em" fill="none" stroke="currentColor"
      strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
      className={className ? `icon ${className}` : 'icon'} style={style}
      {...(label ? { role: 'img', 'aria-label': label } : { 'aria-hidden': 'true' })}
    >
      {paths.map(d => <path key={d} d={d} />)}
    </svg>
  )
}
