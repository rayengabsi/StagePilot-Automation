import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Layout } from './components/Sidebar'
import Dashboard from './pages/Dashboard'
import Jobs from './pages/Jobs'
import Matches from './pages/Matches'
import Filters from './pages/Filters'
import Scheduler from './pages/Scheduler'
import Profile from './pages/Profile'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="jobs" element={<Jobs />} />
          <Route path="matches" element={<Matches />} />
          <Route path="filters" element={<Filters />} />
          <Route path="scheduler" element={<Scheduler />} />
          <Route path="profile" element={<Profile />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
