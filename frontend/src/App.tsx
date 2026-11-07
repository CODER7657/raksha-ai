import { lazy, Suspense, type ComponentType } from 'react'
import { Routes, Route } from 'react-router-dom'
import { HomeGate } from './pages/HomeGate'
import { NotFoundPage } from './pages/NotFoundPage'
import { ProtectedRoute } from './components/ProtectedRoute'

// The public entry points (landing, 404) load eagerly; everything behind sign-in
// is split out, so a first visit does not download the whole app before the
// landing page can paint. Same routes, same components — only the loading.
const named = <K extends string>(load: () => Promise<Record<K, ComponentType>>, name: K) =>
  lazy(() => load().then((m) => ({ default: m[name] })))

const AuthPage = named(() => import('./pages/AuthPage'), 'AuthPage')
const AppShell = named(() => import('./components/AppShell'), 'AppShell')
const ScanInputPage = named(() => import('./pages/ScanInputPage'), 'ScanInputPage')
const ResultPage = named(() => import('./pages/ResultPage'), 'ResultPage')
const HistoryPage = named(() => import('./pages/HistoryPage'), 'HistoryPage')
const BenchmarkPage = named(() => import('./pages/BenchmarkPage'), 'BenchmarkPage')
const ReviewQueuePage = named(() => import('./pages/ReviewQueuePage'), 'ReviewQueuePage')
const EvasionQueuePage = named(() => import('./pages/EvasionQueuePage'), 'EvasionQueuePage')
const OperatorConsolePage = named(() => import('./pages/OperatorConsolePage'), 'OperatorConsolePage')
const AboutPage = named(() => import('./pages/AboutPage'), 'AboutPage')
const PracticePage = named(() => import('./pages/PracticePage'), 'PracticePage')
const ChatPage = named(() => import('./pages/ChatPage'), 'ChatPage')

function App() {
  return (
    <Suspense fallback={null}>
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
          <Route path="evasions" element={<EvasionQueuePage />} />
          <Route path="operator" element={<OperatorConsolePage />} />
          <Route path="about" element={<AboutPage />} />
        </Route>
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </Suspense>
  )
}

export default App
