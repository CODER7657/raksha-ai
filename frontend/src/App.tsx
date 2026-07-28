import { Routes, Route } from 'react-router-dom'
import { HomeGate } from './pages/HomeGate'
import { AuthPage } from './pages/AuthPage'
import { ScanInputPage } from './pages/ScanInputPage'
import { ResultPage } from './pages/ResultPage'
import { ProtectedRoute } from './components/ProtectedRoute'
import { AppShell } from './components/AppShell'

function App() {
  return (
    <Routes>
      <Route path="/" element={<HomeGate />} />
      <Route path="/login" element={<AuthPage />} />
      <Route
        path="/app"
        element={
          <ProtectedRoute>
            <AppShell />
          </ProtectedRoute>
        }
      >
        <Route index element={<ScanInputPage />} />
        <Route path="result" element={<ResultPage />} />
      </Route>
    </Routes>
  )
}

export default App
