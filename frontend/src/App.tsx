import { Routes, Route } from 'react-router-dom'
import { AuthPage } from './pages/AuthPage'
import { ScanInputPage } from './pages/ScanInputPage'
import { ResultPreview } from './pages/ResultPreview'
import { ProtectedRoute } from './components/ProtectedRoute'
import { AppShell } from './components/AppShell'

function App() {
  return (
    <Routes>
      <Route path="/login" element={<AuthPage />} />
      <Route
        element={
          <ProtectedRoute>
            <AppShell />
          </ProtectedRoute>
        }
      >
        <Route path="/" element={<ScanInputPage />} />
        <Route path="/result" element={<ResultPreview />} />
      </Route>
    </Routes>
  )
}

export default App
