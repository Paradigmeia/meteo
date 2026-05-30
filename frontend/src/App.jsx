import { useState } from 'react'
import Dashboard from './components/Dashboard'
import Detail from './components/Detail'
import { useSondes } from './hooks/useSondes'
import { useMeteo } from './hooks/useMeteo'
import './App.css'

export default function App() {
  const [selected, setSelected] = useState(null)
  const { sondes } = useSondes()
  const { meteo } = useMeteo()

  if (selected) {
    return <Detail slug={selected} nom={sondes.find(s => s.slug === selected)?.nom} onBack={() => setSelected(null)} />
  }

  return <Dashboard sondes={sondes} meteo={meteo} onSelectSonde={setSelected} />
}
