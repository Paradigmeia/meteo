import { useState } from 'react'
import Dashboard from './components/Dashboard'
import Detail from './components/Detail'
import AnalyseView from './components/AnalyseView'
import { useSondes } from './hooks/useSondes'
import { useMeteo } from './hooks/useMeteo'
import './App.css'

export default function App() {
  const [selected, setSelected] = useState(null)
  const [analyseOpen, setAnalyseOpen] = useState(false)
  const { sondes } = useSondes()
  const { meteo } = useMeteo()

  if (analyseOpen) {
    return <AnalyseView sondes={sondes} meteo={meteo} onBack={() => setAnalyseOpen(false)} />
  }

  if (selected) {
    return <Detail slug={selected} nom={sondes.find(s => s.slug === selected)?.nom} onBack={() => setSelected(null)} />
  }

  return <Dashboard sondes={sondes} meteo={meteo} onSelectSonde={setSelected} onOpenAnalyse={() => setAnalyseOpen(true)} />
}
