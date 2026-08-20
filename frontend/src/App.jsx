import { HashRouter, Routes, Route } from 'react-router-dom'
import NavBar from './components/NavBar.jsx'
import ArenaPage from './pages/ArenaPage.jsx'
import ComparisonPage from './pages/ComparisonPage.jsx'

export default function App() {
  return (
    <HashRouter>
      <NavBar />
      <Routes>
        <Route path="/" element={<ArenaPage />} />
        <Route path="/compare" element={<ComparisonPage />} />
      </Routes>
    </HashRouter>
  )
}
