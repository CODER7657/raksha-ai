import { Routes, Route } from 'react-router-dom'
import { AuthPage } from './pages/AuthPage'
import { HomePlaceholder } from './pages/HomePlaceholder'
import { ProtectedRoute } from './components/ProtectedRoute'

function App() {
  return (
    <Routes>
      <Route path="/login" element={<AuthPage />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <HomePlaceholder />
          </ProtectedRoute>
        }
      />
    </Routes>
  )
}

export default App
