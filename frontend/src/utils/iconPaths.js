// Tracés des icônes Tabler 3.19.0 (MIT — https://github.com/tabler/tabler-icons), embarquées
// en SVG au lieu d'être chargées depuis un CDN (issue #50). La feuille de style
// jsdelivr pesait 238 kB et tirait une police entière pour les 15 glyphes
// utilisés ici, sans SRI et sans que rien ne rattrape une compromission du CDN.
//
// Chaque tracé est repris tel quel du dépôt Tabler, moins le rectangle de
// cadrage invisible qui préfixe chaque fichier. Les données sont séparées du
// composant qui les rend : un fichier de composant qui exporte autre chose
// qu'un composant casse le Fast Refresh de Vite.
//
// ICON_NAMES sert au test qui vérifie qu'aucun nom utilisé dans l'application
// ne résout dans le vide — c'est ce qui arrivait à 'cloud-sun' et
// 'cloud-drizzle', absents de Tabler 3.19.0 : la police n'affichait rien, sans
// erreur console ni trace serveur.
export const ICON_PATHS = {
  'alert-triangle': [
    'M12 9v4',
    'M10.363 3.591l-8.106 13.534a1.914 1.914 0 0 0 1.636 2.871h16.214a1.914 1.914 0 0 0 1.636 -2.87l-8.106 -13.536a1.914 1.914 0 0 0 -3.274 0z',
    'M12 16h.01',
  ],
  'arrow-left': [
    'M5 12l14 0',
    'M5 12l6 6',
    'M5 12l6 -6',
  ],
  'chart-dots-3': [
    'M5 7m-2 0a2 2 0 1 0 4 0a2 2 0 1 0 -4 0',
    'M16 15m-2 0a2 2 0 1 0 4 0a2 2 0 1 0 -4 0',
    'M18 6m-3 0a3 3 0 1 0 6 0a3 3 0 1 0 -6 0',
    'M6 18m-3 0a3 3 0 1 0 6 0a3 3 0 1 0 -6 0',
    'M9 17l5 -1.5',
    'M6.5 8.5l7.81 5.37',
    'M7 7l8 -1',
  ],
  'cloud': [
    'M6.657 18c-2.572 0 -4.657 -2.007 -4.657 -4.483c0 -2.475 2.085 -4.482 4.657 -4.482c.393 -1.762 1.794 -3.2 3.675 -3.773c1.88 -.572 3.956 -.193 5.444 1c1.488 1.19 2.162 3.007 1.77 4.769h.99c1.913 0 3.464 1.56 3.464 3.486c0 1.927 -1.551 3.487 -3.465 3.487h-11.878',
  ],
  'cloud-fog': [
    'M7 16a4.6 4.4 0 0 1 0 -9a5 4.5 0 0 1 11 2h1a3.5 3.5 0 0 1 0 7h-12',
    'M5 20l14 0',
  ],
  'cloud-rain': [
    'M7 18a4.6 4.4 0 0 1 0 -9a5 4.5 0 0 1 11 2h1a3.5 3.5 0 0 1 0 7',
    'M11 13v2m0 3v2m4 -5v2m0 3v2',
  ],
  'cloud-storm': [
    'M7 18a4.6 4.4 0 0 1 0 -9a5 4.5 0 0 1 11 2h1a3.5 3.5 0 0 1 0 7h-1',
    'M13 14l-2 4l3 0l-2 4',
  ],
  'droplet': [
    'M7.502 19.423c2.602 2.105 6.395 2.105 8.996 0c2.602 -2.105 3.262 -5.708 1.566 -8.546l-4.89 -7.26c-.42 -.625 -1.287 -.803 -1.936 -.397a1.376 1.376 0 0 0 -.41 .397l-4.893 7.26c-1.695 2.838 -1.035 6.441 1.567 8.546z',
  ],
  'droplets': [
    'M4.072 20.3a2.999 2.999 0 0 0 3.856 0a3.002 3.002 0 0 0 .67 -3.798l-2.095 -3.227a.6 .6 0 0 0 -1.005 0l-2.098 3.227a3.003 3.003 0 0 0 .671 3.798z',
    'M16.072 20.3a2.999 2.999 0 0 0 3.856 0a3.002 3.002 0 0 0 .67 -3.798l-2.095 -3.227a.6 .6 0 0 0 -1.005 0l-2.098 3.227a3.003 3.003 0 0 0 .671 3.798z',
    'M10.072 10.3a2.999 2.999 0 0 0 3.856 0a3.002 3.002 0 0 0 .67 -3.798l-2.095 -3.227a.6 .6 0 0 0 -1.005 0l-2.098 3.227a3.003 3.003 0 0 0 .671 3.798z',
  ],
  'haze': [
    'M3 12h1',
    'M12 3v1',
    'M20 12h1',
    'M5.6 5.6l.7 .7',
    'M18.4 5.6l-.7 .7',
    'M8 12a4 4 0 1 1 8 0',
    'M3 16h18',
    'M3 20h18',
  ],
  'home-2': [
    'M5 12l-2 0l9 -9l9 9l-2 0',
    'M5 12v7a2 2 0 0 0 2 2h10a2 2 0 0 0 2 -2v-7',
    'M10 12h4v4h-4z',
  ],
  'snowflake': [
    'M10 4l2 1l2 -1',
    'M12 2v6.5l3 1.72',
    'M17.928 6.268l.134 2.232l1.866 1.232',
    'M20.66 7l-5.629 3.25l.01 3.458',
    'M19.928 14.268l-1.866 1.232l-.134 2.232',
    'M20.66 17l-5.629 -3.25l-2.99 1.738',
    'M14 20l-2 -1l-2 1',
    'M12 22v-6.5l-3 -1.72',
    'M6.072 17.732l-.134 -2.232l-1.866 -1.232',
    'M3.34 17l5.629 -3.25l-.01 -3.458',
    'M4.072 9.732l1.866 -1.232l.134 -2.232',
    'M3.34 7l5.629 3.25l2.99 -1.738',
  ],
  'sun': [
    'M12 12m-4 0a4 4 0 1 0 8 0a4 4 0 1 0 -8 0',
    'M3 12h1m8 -9v1m8 8h1m-9 8v1m-6.4 -15.4l.7 .7m12.1 -.7l-.7 .7m0 11.4l.7 .7m-12.1 -.7l-.7 .7',
  ],
  'wifi-off': [
    'M12 18l.01 0',
    'M9.172 15.172a4 4 0 0 1 5.656 0',
    'M6.343 12.343a7.963 7.963 0 0 1 3.864 -2.14m4.163 .155a7.965 7.965 0 0 1 3.287 2',
    'M3.515 9.515a12 12 0 0 1 3.544 -2.455m3.101 -.92a12 12 0 0 1 10.325 3.374',
    'M3 3l18 18',
  ],
  'wind': [
    'M5 8h8.5a2.5 2.5 0 1 0 -2.34 -3.24',
    'M3 12h15.5a2.5 2.5 0 1 1 -2.34 3.24',
    'M4 16h5.5a2.5 2.5 0 1 1 -2.34 3.24',
  ],
}

export const ICON_NAMES = Object.keys(ICON_PATHS)
