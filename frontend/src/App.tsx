import { Routes, Route } from 'react-router-dom'
import { HomeGate } from './pages/HomeGate'
import { AuthPage } from './pages/AuthPage'
import { ScanInputPage } from './pages/ScanInputPage'
import { ResultPage } from './pages/ResultPage'
import { HistoryPage } from './pages/HistoryPage'
import { BenchmarkPage } from './pages/BenchmarkPage'
import { ReviewQueuePage } from './pages/ReviewQueuePage'
import { AboutPage } from './pages/AboutPage'
import { PracticePage } from './pages/PracticePage'
import { ChatPage } from './pages/ChatPage'
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
        <Route path="practice" element={<PracticePage />} />
        <Route path="chat" element={<ChatPage />} />
        <Route path="history" element={<HistoryPage />} />
        {/* Reviewer tooling. Reachable by URL but deliberately not in the main
            nav — it is internal, and there is no role system to gate it with
            yet. See the PR for why that gate is still needed. */}
        <Route path="benchmark" element={<BenchmarkPage />} />
        <Route path="review" element={<ReviewQueuePage />} />
        <Route path="about" element={<AboutPage />} />
      </Route>
    </Routes>
  )
}

export default App
